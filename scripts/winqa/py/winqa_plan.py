#!/usr/bin/env python3
"""R29 #414 run plan and receipts: the only facts of a Windows QA run (design 414-design-v4, points 1, 2, 5).

    runs/<run_id>/plan.json       written ONCE (atomic: tmp + fsync + link; an existing plan is never replaced)
    runs/<run_id>/receipts.jsonl  append-only: {seq, run_id, plan_sha256, step, attempt, status, exit_code,
                                  exit_code_source, at[, retry_of]}
    runs/index.jsonl              append-only list of the runs of this evidence directory

Commands (run_winqa.sh calls them; the shell never prints JSON itself):
    winqa_plan.py create  --out OUT --run-id ID --from N --to N [--flags smoke,asr,failure,real,bili,hf]
    winqa_plan.py record  --out OUT --run-id ID --step S --status ok|FAIL --exit-code N [--retry-of SEQ]
    winqa_plan.py due     --out OUT --run-id ID --upto N       comma list of the required files due by step N
    winqa_plan.py steps   --out OUT --dest FILE               steps.json view (every receipt, every run)
    winqa_plan.py migrate --out OUT                           legacy evidence -> runs/legacy (idempotent)
Exit codes: 2 usage, 71 plan exists / bad plan, 72 receipt not written (the run must stop).
"""
import hashlib, json, os, sys, time
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent)]
from export_evidence import STEPS, name_ok  # noqa: E402  (#324: one name rule, the exporter's)

SCHEMA = 'winqa-plan/1'
E_PLAN, E_RECEIPT = 71, 72
# step number -> [(record name, produced files, condition flag or None, optional files)]. The one table: required
# evidence is computed from it, never accumulated in the shell (#318).
TABLE = {
    2: [('clean', ['clean.json', 'env.json'], None, [])],
    3: [('install_prev', ['install-prev.json'], None, []), ('launch_prev', ['launch-prev.json'], None, []),
        ('seed_prev', ['seed.json'], None, []), ('export_after_3', [], None, [])],
    4: [('upgrade', ['install-upgrade.json'], None, [])],
    5: [('launch_candidate', ['launch-candidate.json'], None, []), ('check_candidate', ['check-candidate.json'], None, [])],
    6: [('failure_probe', ['failure.json'], 'failure', []), ('stop_candidate', ['stop-candidate.json'], None, []),
        ('export_after_6', [], None, [])],
    7: [('smoke', ['smoke.json', 'windows-smoke.json', 'windows-smoke-desktop.json'], 'smoke', []),
        ('smoke_asr', ['windows-sensevoice-installed.json', 'windows-whisper-installed.json'], 'asr', [])],
    10: [('launch_real', [], 'real', []), ('real_model', ['real/model.json'], 'real', [])],
    11: [('real_whisper', ['real/whisper.json'], 'real', []),
         ('real_whisper_hfmirror', [], 'hf', ['real/whisper-hfmirror.json'])],
    12: [('real_local', ['real/local.json'], 'real', [])],
    13: [('real_link', ['real/link.json'], 'bili', [])],
    14: [('real_final', ['real/final.json'], 'real', [])],
    8: [('collect_logs', ['collect-logs-final.json'], None, []), ('pull_final', [], None, [])],   # always runs
}
NO_RECEIPT = frozenset({'smoke_asr', 'real_whisper_hfmirror'})   # covered by smoke / only after a failed real_whisper
RETRYABLE = frozenset()     # no step may be retried inside one run today; see winqa_verdict (failure latches)


def canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def plan_hash(plan) -> str:
    return hashlib.sha256(canon({k: v for k, v in plan.items() if k != 'plan_sha256'})).hexdigest()


def _flags_ok(cond, flags):
    if cond is None:
        return True
    if cond == 'asr':
        return 'smoke' in flags and 'asr' in flags
    if cond in ('bili', 'hf'):
        return 'real' in flags and cond in flags
    return cond in flags


def compute(frm, to, flags):
    """-> (steps, required) for this window and these switches."""
    steps, required = [], {STEPS}
    for n, rows in TABLE.items():
        if n != 8 and not (frm <= n <= to):
            continue
        for name, produces, cond, optional in rows:
            if not _flags_ok(cond, flags):
                continue
            for f in produces + optional:
                if not name_ok(f, ()):
                    raise SystemExit(E_PLAN)
            steps.append({'n': n, 'id': name, 'produces': produces, 'optional': optional,
                          'retryable': name in RETRYABLE})
            required.update(produces)
    return steps, sorted(required)


def runs_dir(out: Path) -> Path:
    return out / 'runs'


def load_plan(out: Path, run_id: str):
    p = runs_dir(out) / run_id / 'plan.json'
    plan = json.loads(p.read_text(encoding='utf-8'))
    if plan.get('schema') != SCHEMA or plan.get('plan_sha256') != plan_hash(plan):
        raise ValueError('plan hash mismatch')
    for f in plan['required']:
        if not name_ok(f, ()):
            raise ValueError('bad required name')
    return plan


def index(out: Path):
    p = runs_dir(out) / 'index.jsonl'
    return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()] if p.exists() else []


def _append(path: Path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, canon(row) + b'\n')
        os.fsync(fd)
    finally:
        os.close(fd)


def write_once(path: Path, data: bytes):
    """Atomic, never replaces: an existing plan aborts (#318: the plan is immutable)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.tmp{os.getpid()}')
    with open(tmp, 'wb') as fh:
        fh.write(data); fh.flush(); os.fsync(fh.fileno())
    try:
        os.link(tmp, path)            # fails if path exists: no silent overwrite
    finally:
        tmp.unlink()


def create(out: Path, run_id: str, frm: int, to: int, flags, inputs=None):
    if not name_ok(run_id, ()):
        raise SystemExit(E_PLAN)
    steps, required = compute(frm, to, flags)
    plan = {'schema': SCHEMA, 'run_id': run_id, 'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
            'window': [frm, to], 'flags': sorted(flags), 'inputs': inputs or {}, 'steps': steps,
            'required': required, 'required_unknown': False, 'resumes': None, 'carried': []}
    prior = index(out)
    if frm > 0 and prior:                  # a resume keeps every obligation of the run it continues
        last = prior[-1]
        old = load_plan(out, last['run_id'])
        plan['resumes'] = {'run_id': old['run_id'], 'plan_sha256': old['plan_sha256']}
        plan['carried'] = sorted(set(old['required']) - set(required))
        plan['required'] = sorted(set(required) | set(old['required']))
        plan['required_unknown'] = bool(old.get('required_unknown'))
        have = {s['id'] for s in steps}
        plan['steps'] += [dict(s, carried_from=old['run_id']) for s in old['steps'] if s['id'] not in have]
    plan['plan_sha256'] = plan_hash(plan)
    write_once(runs_dir(out) / run_id / 'plan.json', json.dumps(plan, ensure_ascii=False, indent=2).encode() + b'\n')
    _append(runs_dir(out) / 'index.jsonl', {'run_id': run_id, 'plan_sha256': plan['plan_sha256']})
    return plan


def receipts(out: Path, run_id: str):
    p = runs_dir(out) / run_id / 'receipts.jsonl'
    return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()] if p.exists() else []


def all_receipts(out: Path):
    return [r for row in index(out) for r in receipts(out, row['run_id'])]


def record(out: Path, run_id: str, step: str, status: str, exit_code: int, retry_of=None):
    if status not in ('ok', 'FAIL') or not step or not name_ok(step, ()):
        raise ValueError('bad receipt')
    plan = load_plan(out, run_id)
    mine = receipts(out, run_id)
    attempt = 1 + sum(1 for r in all_receipts(out) if r['step'] == step)
    row = {'seq': len(mine) + 1, 'run_id': run_id, 'plan_sha256': plan['plan_sha256'], 'step': step,
           'attempt': attempt, 'status': status, 'exit_code': int(exit_code), 'exit_code_source': 'measured',
           'at': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    if retry_of is not None:
        row['retry_of'] = int(retry_of)
    _append(runs_dir(out) / run_id / 'receipts.jsonl', row)
    return row


def due(plan, upto: int):
    """Required files of the steps up to `upto` (stage export, design point 1): later steps are pending."""
    files = {STEPS}
    for s in plan['steps']:
        if s['n'] <= upto:            # step 8 (n=8) is due only from step 8 on, i.e. at the final export
            files.update(s['produces'])
    return sorted(files & set(plan['required']) | {STEPS})


def migrate(out: Path):
    """Point 5: evidence from before R29 -> runs/legacy. Old required kept (unknown when it cannot be recovered);
    exit codes not measured then are marked inferred; idempotent; never turns FAIL/unknown into ok."""
    if (runs_dir(out) / 'legacy' / 'plan.json').exists() or index(out):
        return None
    rows = []
    if (out / 'steps.jsonl').exists():
        for l in (out / 'steps.jsonl').read_text(encoding='utf-8').splitlines():
            if l.strip():
                r = json.loads(l)
                rows.append((r.get('step'), r.get('status'), r.get('exit_code')))
    elif (out / 'steps.txt').exists():
        for l in (out / 'steps.txt').read_text(encoding='utf-8').splitlines():
            k, _, v = l.partition('=')
            if k:
                rows.append((k, v, None))
    if not rows and not (out / 'required.txt').exists():
        return None
    req_txt = out / 'required.txt'
    required = sorted({r for r in req_txt.read_text(encoding='utf-8').strip().split(',') if r} | {STEPS}) \
        if req_txt.exists() else [STEPS]
    plan = {'schema': SCHEMA, 'run_id': 'legacy', 'created_at': '', 'window': [0, 99], 'flags': [], 'inputs': {},
            'steps': [], 'required': [r for r in required if name_ok(r, ())],
            'required_unknown': not req_txt.exists() or any(not name_ok(r, ()) for r in required),
            'resumes': None, 'carried': [], 'migrated': True}
    plan['plan_sha256'] = plan_hash(plan)
    write_once(runs_dir(out) / 'legacy' / 'plan.json', json.dumps(plan, ensure_ascii=False, indent=2).encode() + b'\n')
    seen = {}
    for i, (step, status, code) in enumerate(rows, 1):
        if not isinstance(step, str) or not name_ok(step, ()):
            continue
        seen[step] = seen.get(step, 0) + 1
        st = 'ok' if status == 'ok' else 'FAIL'
        measured = isinstance(code, int) and not isinstance(code, bool)
        _append(runs_dir(out) / 'legacy' / 'receipts.jsonl', {
            'seq': i, 'run_id': 'legacy', 'plan_sha256': plan['plan_sha256'], 'step': step, 'attempt': seen[step],
            'status': st, 'exit_code': code if measured else (0 if st == 'ok' else 1),
            'exit_code_source': 'measured' if measured else 'inferred', 'migrated': True, 'at': ''})
    _append(runs_dir(out) / 'index.jsonl', {'run_id': 'legacy', 'plan_sha256': plan['plan_sha256']})
    return plan


def _arg(a, name, default=None):
    return a[a.index(name) + 1] if name in a else default


def main(a):
    if not a:
        print(__doc__, file=sys.stderr); return 2
    out = Path(_arg(a, '--out', '.'))
    try:
        if a[0] == 'create':
            flags = {f for f in (_arg(a, '--flags', '') or '').split(',') if f}
            inputs = json.loads(_arg(a, '--inputs', '{}'))
            p = create(out, _arg(a, '--run-id'), int(_arg(a, '--from', '0')), int(_arg(a, '--to', '99')), flags, inputs)
            print(p['plan_sha256']); return 0
        if a[0] == 'record':
            try:
                record(out, _arg(a, '--run-id'), _arg(a, '--step'), _arg(a, '--status'), int(_arg(a, '--exit-code')),
                       _arg(a, '--retry-of'))
            except Exception as exc:
                print(f'winqa_plan: receipt NOT written ({type(exc).__name__})', file=sys.stderr); return E_RECEIPT
            return 0
        if a[0] == 'due':
            print(','.join(due(load_plan(out, _arg(a, '--run-id')), int(_arg(a, '--upto'))))); return 0
        if a[0] == 'steps':
            Path(_arg(a, '--dest')).write_text(json.dumps(all_receipts(out), ensure_ascii=False, indent=2) + '\n')
            return 0
        if a[0] == 'migrate':
            migrate(out); return 0
    except SystemExit:
        raise
    except Exception as exc:
        print(f'winqa_plan {a[0]}: ERROR {type(exc).__name__}', file=sys.stderr)
        return E_PLAN
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
