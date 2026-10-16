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

Usage
  export_evidence.py export --src DIR --dest DIR --bundle NAME [--require a.json,real/b.json] --keys-stdin
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

SCHEMA, POLICY = 'winqa-evidence-bundle/1', 'winqa-export/1'
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


def export(src: Path, dest: Path, bundle: str, required, keys):
    if not _BUNDLE.match(bundle):
        raise ExportError('bad bundle name')
    before = tree(src)                                                      # I1
    files, withheld, members = [], [], []
    for rel, src_sha in before.items():
        raw = (src / rel).read_bytes()                                       # the copy: read once into memory
        if sha(raw) != src_sha:
            raise ExportError('source changed while exporting')
        entry = {'source_sha256': src_sha, 'size': len(raw)}
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
    exported = {f['name'] for f in files}
    missing = sorted(r for r in required if r not in exported)
    status = 'incomplete' if missing else 'complete'
    manifest = {'schema': SCHEMA, 'policy': POLICY, 'bundle': bundle, 'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                'source_tree_sha256': tree_hash(before), 'status': status, 'required': sorted(required),
                'missing_required': missing, 'files': files, 'withheld': withheld}
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
    digest = sha(part.read_bytes())
    os.replace(part, final)                                                  # commit
    return status, final.name, digest, len(files), len(withheld)


def verify(bundle: Path, digest: str, into: Path, keys):
    raw = bundle.read_bytes()
    if sha(raw) != digest.lower():
        raise ExportError('bundle hash mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names = z.namelist()
        if len(set(names)) != len(names) or 'manifest.json' not in names:
            raise ExportError('bad member list')
        mtext = z.read('manifest.json').decode('utf-8')
        check_clean(mtext, keys)
        m = json.loads(mtext)
        if m.get('schema') != SCHEMA or m.get('policy') != POLICY:
            raise ExportError('unknown bundle schema/policy')
        listed = {f['name']: f['sha256'] for f in m['files']}
        if set(names) - {'manifest.json'} != set(listed):
            raise ExportError('members differ from manifest')
        out = {}
        for n in listed:
            if not name_ok(n, keys):                                         # I5
                raise ExportError('member name fails the name policy')
            data = z.read(n)
            if sha(data) != listed[n]:
                raise ExportError('member hash mismatch')
            check_clean(data.decode('utf-8'), keys)                         # I6 again, on the control machine
            out[n] = data
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
            status, name, digest, n, w = export(Path(_arg(argv, '--src')), Path(_arg(argv, '--dest')), _arg(argv, '--bundle'), req, keys)
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
