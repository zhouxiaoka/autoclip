#!/usr/bin/env python3
"""Evidence export boundary for Windows QA (R27 rewrite, design-retro #414).

The Windows test machine keeps its originals (C:\\winqa\\out) untouched. Evidence leaves it only as a committed,
versioned EvidenceBundle that was produced and checked ON the test machine:

    export  (runs on the test machine, bundled Python)   copy -> classify -> scrub -> verify -> commit
    verify  (runs on the control machine)                 hash -> manifest -> policy re-check -> extract

The control machine never pulls raw files and never "rescues" them afterwards.

Invariants
  I1  Originals are read only; their tree hash is taken before and after, and a difference aborts the export.
  I2  Nothing is transferable before it is fully scrubbed and verified: the bundle is written as *.part and renamed
      to *.zip only at the end (commit). A crash or kill leaves no *.zip.
  I3  Exact keys arrive on stdin only (never argv, env or logs) and are never printed.
  I4  Unknown, binary, image, archive, raw log and mixed/odd-encoding files are recorded as `withheld` (name if it
      passes the name policy, else only its hash) - never deleted, never counted as exported. A required evidence
      file that is missing or withheld makes the bundle `incomplete` (exit 3, the caller records FAIL).
  I5  File names, ZIP member names and contents follow one policy: a member name must pass the same name rule and
      the same scrubber (unchanged) as the content.
  I6  Exported content is structured JSON only (policy winqa-export/1, the reduced scope until 10/20): decoded
      strictly (UTF-8, UTF-8 BOM, or UTF-16 with BOM and an exact round trip), scrubbed with redact.scrub_obj and
      the exact keys, re-serialised as UTF-8 without BOM, and must be a fixed point of the scrubber with no key
      form left - otherwise the whole export aborts (a verification failure is a bug, not a file to drop).

  I7  Evidence contract (R27 #306): `steps.json` (the control machine's step records: run_id, step, attempt,
      status ok|FAIL, exit_code) is always required; every required file must be a non-empty JSON object or list
      (`{}` is not evidence); the manifest carries `withheld` and `error_codes` (every `error_code` value found in
      each exported required file). One validator (validate_bundle) checks all of it, recomputing classification,
      required/missing/status and error_codes from the members: on the test machine against the re-opened .part
      before the rename (#304) and again on the control machine (#307).

Usage
  export_evidence.py export --src DIR --dest DIR --bundle NAME [--require a.json,real/b.json] [--steps FILE] --keys-stdin
      last stdout line: "EXPORT <complete|incomplete> <NAME>.zip <sha256>"; exit 0 complete, 3 incomplete,
      1 nothing committed.
  export_evidence.py verify --bundle FILE --sha256 HEX --into DIR --keys-stdin
      exit 0 and DIR holds the members + manifest.json; any mismatch exits 1 and DIR is removed.
"""
import hashlib, io, json, os, re, shutil, sys, time, zipfile
from pathlib import Path

_here = Path(__file__).resolve().parent
sys.path[:0] = [str(_here), str(_here.parent)]   # on the VM redact.py sits next to this file; in the repo one up
import redact  # noqa: E402

SCHEMA, POLICY = 'winqa-evidence-bundle/2', 'winqa-export/1'
STEPS = 'steps.json'
_STEP_STATUS = ('ok', 'FAIL')
_SEG = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
_BUNDLE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$')
_UTF16_BOMS = ((b'\xff\xfe', 'utf-16-le'), (b'\xfe\xff', 'utf-16-be'))


class ExportError(Exception):
    """Aborts the whole export; nothing is committed."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_keys(stream):
    return [k for k in (line.rstrip('\r\n') for line in stream) if k]


def key_forms(keys):
    forms = set()
    for k in redact._key_forms(keys):
        forms.add(k)
        forms.add(json.dumps(k, ensure_ascii=True)[1:-1])
    return [f for f in forms if f]


def name_ok(rel: str, keys) -> bool:
    """I5: one rule for file names and ZIP member names."""
    parts = rel.split('/')
    if not parts or any(not _SEG.match(p) or p in ('.', '..') for p in parts):
        return False
    if redact.scrub(rel, keys) != rel:
        return False
    return not any(f in rel for f in key_forms(keys))


def tree(src: Path):
    out = {}
    for p in sorted(src.rglob('*')):
        if p.is_file() and not p.is_symlink():
            out[p.relative_to(src).as_posix()] = sha(p.read_bytes())
    return out


def tree_hash(t) -> str:
    return sha(json.dumps(sorted(t.items())).encode())


def decode_json_text(raw: bytes):
    """I6 strict decode; None means 'withheld: encoding'."""
    for bom, codec in _UTF16_BOMS:
        if raw.startswith(bom):
            body = raw[len(bom):]
            try:
                text = body.decode(codec)
            except UnicodeDecodeError:
                return None
            if text.encode(codec) != body or '\x00' in text:
                return None
            return text
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    if b'\x00' in raw:
        return None
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return None


def kind_of(raw: bytes, rel: str) -> str:
    if raw[:8] == b'\x89PNG\r\n\x1a\n' or raw[:3] == b'\xff\xd8\xff' or raw[:4] in (b'GIF8', b'RIFF') \
            or rel.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
        return 'image'
    if raw[:4] == b'PK\x03\x04' or rel.lower().endswith('.zip'):
        return 'archive'
    if rel.lower().endswith('.json'):
        return 'json'
    return 'raw_text_or_binary'


def clean_json(raw: bytes, keys):
    """-> (exported bytes, None) or (None, withheld reason). Raises ExportError when verification fails."""
    text = decode_json_text(raw)
    if text is None:
        return None, 'encoding'
    try:
        data = json.loads(text)
    except ValueError:
        return None, 'not_json'
    clean = redact.scrub_obj(data, keys)
    out = json.dumps(clean, ensure_ascii=False, indent=2) + '\n'
    check_clean(out, keys)
    return out.encode('utf-8'), None


def check_clean(text: str, keys):
    """I6 verification, shared by export and verify."""
    data = json.loads(text)
    if redact.scrub_obj(data, keys) != data:
        raise ExportError('scrubbed JSON is not a fixed point of the scrubber')
    if any(f in text for f in key_forms(keys)):
        raise ExportError('key form left after scrubbing')


def error_codes(data):
    """Every `error_code` value at any depth (strings and numbers), sorted, unique."""
    found = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == 'error_code' and isinstance(v, (str, int)) and not isinstance(v, bool) and v != '':
                    found.add(str(v))
                walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(data)
    return sorted(found)


def contract_problem(name: str, data):
    """I7 content contract of one required file; None when it is evidence."""
    if not isinstance(data, (dict, list)) or not data:
        return 'empty'
    if name == STEPS:
        if not isinstance(data, list):
            return 'steps_not_a_list'
        for r in data:
            if not isinstance(r, dict) or not isinstance(r.get('run_id'), str) or not isinstance(r.get('step'), str) \
                    or not r['step'] or r.get('status') not in _STEP_STATUS \
                    or not isinstance(r.get('attempt'), int) or isinstance(r.get('attempt'), bool) or r['attempt'] < 1 \
                    or not isinstance(r.get('exit_code'), int) or isinstance(r.get('exit_code'), bool):
                return 'steps_record'
    return None


def export(src: Path, dest: Path, bundle: str, required, keys, steps: Path = None):
    if not _BUNDLE.match(bundle):
        raise ExportError('bad bundle name')
    required = sorted(set(required) | {STEPS})                              # I7: step results always required
    before = tree(src)                                                      # I1
    inputs = [(rel, src / rel, src_sha) for rel, src_sha in before.items()]
    if steps is not None:
        inputs.append((STEPS, steps, sha(steps.read_bytes())))
    files, withheld, members = [], [], []
    for rel, path, src_sha in inputs:
        raw = path.read_bytes()                                              # the copy: read once into memory
        if sha(raw) != src_sha:
            raise ExportError('source changed while exporting')
        entry = {'source_sha256': src_sha, 'size': len(raw)}
        if rel == STEPS and path.parent == src:
            withheld.append(dict(entry, name=rel, reason='reserved'))       # only the control machine's records
            continue
        if not name_ok(rel, keys):
            withheld.append(dict(entry, name=None, name_sha256=sha(rel.encode('utf-8', 'surrogateescape')), reason='name'))
            continue
        kind = kind_of(raw, rel)
        if kind != 'json':
            withheld.append(dict(entry, name=rel, reason=kind))
            continue
        data, why = clean_json(raw, keys)
        if why:
            withheld.append(dict(entry, name=rel, reason=why))
            continue
        files.append(dict(entry, name=rel, sha256=sha(data)))
        members.append((rel, data))
    if tree(src) != before:                                                  # I1
        raise ExportError('originals changed during export')
    parsed = {rel: json.loads(data) for rel, data in members}
    problems, missing, codes = derive(required, parsed)
    manifest = {'schema': SCHEMA, 'policy': POLICY, 'bundle': bundle, 'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'source_tree_sha256': tree_hash(before), 'status': 'incomplete' if missing else 'complete',
                'required': required, 'missing_required': missing, 'contract_problems': problems,
                'error_codes': codes, 'files': files, 'withheld': withheld}
    mtext = json.dumps(manifest, ensure_ascii=False, indent=2) + '\n'
    check_clean(mtext, keys)
    dest.mkdir(parents=True, exist_ok=True)
    final, part = dest / f'{bundle}.zip', dest / f'{bundle}.zip.part'
    if final.exists():
        raise ExportError('bundle already committed')
    with open(part, 'wb') as fh:                                             # I2
        with zipfile.ZipFile(fh, 'w', zipfile.ZIP_DEFLATED) as z:
            for rel, data in members:
                z.writestr(zipfile.ZipInfo(rel, (1980, 1, 1, 0, 0, 0)), data)
            z.writestr(zipfile.ZipInfo('manifest.json', (1980, 1, 1, 0, 0, 0)), mtext.encode('utf-8'))
        fh.flush()
        os.fsync(fh.fileno())
    # #304: re-open what is actually on disk and run the full validator on it before the commit
    try:
        written = part.read_bytes()
        m, _ = validate_bundle(written, keys)
        if m['bundle'] != bundle or {f['name'] for f in m['files']} != {rel for rel, _ in members}:
            raise ExportError('written bundle differs from what was exported')
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    digest = sha(written)
    os.replace(part, final)                                                  # commit
    return m['status'], final.name, digest, len(files), len(withheld)


def derive(required, parsed):
    """I7: missing required evidence, contract problems and error codes, all derived from the members."""
    problems = {}
    for r in required:
        if r in parsed:
            why = contract_problem(r, parsed[r])
            if why:
                problems[r] = why
    missing = sorted(r for r in required if r not in parsed or r in problems)
    codes = {r: error_codes(parsed[r]) for r in required if r in parsed and r != STEPS}
    return problems, missing, codes


_WITHHELD_KEYS = {'source_sha256', 'size', 'name', 'reason'}


def validate_bundle(raw: bytes, keys):
    """The one complete bundle check (I5-I7), used before the commit on the test machine and by verify on the
    control machine. Returns (manifest, {member: bytes}); raises ExportError."""
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise ExportError('not a zip') from exc
    with z:
        names = z.namelist()
        if len(set(names)) != len(names) or 'manifest.json' not in names:
            raise ExportError('bad member list')
        mtext = z.read('manifest.json').decode('utf-8')
        check_clean(mtext, keys)
        m = json.loads(mtext)
        if not isinstance(m, dict) or m.get('schema') != SCHEMA or m.get('policy') != POLICY:
            raise ExportError('unknown bundle schema/policy')
        if not isinstance(m.get('files'), list) or not isinstance(m.get('withheld'), list) \
                or not isinstance(m.get('required'), list):
            raise ExportError('manifest lacks files/withheld/required')
        for w in m['withheld']:
            if not isinstance(w, dict) or not _WITHHELD_KEYS <= set(w) or not w['reason']:
                raise ExportError('bad withheld entry')
        if STEPS not in m['required']:
            raise ExportError('manifest does not require the step results')
        listed = {f['name']: f['sha256'] for f in m['files']}
        if len(listed) != len(m['files']) or set(names) - {'manifest.json'} != set(listed):
            raise ExportError('members differ from manifest')
        out, parsed = {}, {}
        for n in listed:
            if not name_ok(n, keys):                                         # I5
                raise ExportError('member name fails the name policy')
            data = z.read(n)
            if sha(data) != listed[n]:
                raise ExportError('member hash mismatch')
            if kind_of(data, n) != 'json' or decode_json_text(data) is None:  # #307: same classification
                raise ExportError('member is not structured JSON')
            text = data.decode('utf-8')
            check_clean(text, keys)                                          # I6
            out[n], parsed[n] = data, json.loads(text)
    problems, missing, codes = derive(m['required'], parsed)                 # #307: recomputed, not trusted
    status = 'incomplete' if missing else 'complete'
    if m.get('missing_required') != missing or m.get('status') != status or m.get('contract_problems') != problems \
            or m.get('error_codes') != codes:
        raise ExportError('manifest status/required/missing/error_codes do not match the members')
    return m, out


def verify(bundle: Path, digest: str, into: Path, keys):
    raw = bundle.read_bytes()
    if sha(raw) != digest.lower():
        raise ExportError('bundle hash mismatch')
    m, out = validate_bundle(raw, keys)
    mtext = json.dumps(m, ensure_ascii=False, indent=2) + '\n'
    shutil.rmtree(into, ignore_errors=True)
    into.mkdir(parents=True)
    for n, data in out.items():
        p = into / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    (into / 'manifest.json').write_text(mtext, encoding='utf-8')
    return m


def _arg(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


def main(argv):
    if not argv or argv[0] not in ('export', 'verify') or '--keys-stdin' not in argv:
        print(__doc__.split('Usage')[1], file=sys.stderr)
        return 2
    keys = read_keys(io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8', errors='strict'))
    try:
        if argv[0] == 'export':
            req = [r for r in (_arg(argv, '--require', '') or '').split(',') if r]
            steps = _arg(argv, '--steps')
            status, name, digest, n, w = export(Path(_arg(argv, '--src')), Path(_arg(argv, '--dest')), _arg(argv, '--bundle'),
                                                req, keys, Path(steps) if steps else None)
            print(f'export: {n} file(s) exported, {w} withheld (kept on the test machine)')
            print(f'EXPORT {status} {name} {digest}')
            return 0 if status == 'complete' else 3
        into = Path(_arg(argv, '--into'))
        try:
            m = verify(Path(_arg(argv, '--bundle')), _arg(argv, '--sha256', ''), into, keys)
        except BaseException:
            shutil.rmtree(into, ignore_errors=True)
            raise
        print(f"verify: {m['bundle']} {m['status']}, {len(m['files'])} file(s), {len(m['withheld'])} withheld on the test machine")
        return 0 if m['status'] == 'complete' else 3
    except Exception as exc:   # never echo content or keys
        print(f'{argv[0]}: ERROR {type(exc).__name__}: {exc if isinstance(exc, ExportError) else "see test machine"}; nothing committed',
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
