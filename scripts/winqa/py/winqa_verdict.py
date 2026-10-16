#!/usr/bin/env python3
"""R29 #414 point 3: the ONE function that decides a run (evidence complete + step results + overall).
summarize.py only renders the verdict this writes; nothing else judges pass/fail.

    winqa_verdict.py final --out OUT --run-id ID [--manifest FILE --bundle-sha256 HEX] --dest FILE
        exit 0 when overall == pass, else 1.

Retry semantics (one rule): inside a run a FAIL latches. It is only cleared by a later ok receipt of the same
step that names it (retry_of = its seq) for a step the plan marks retryable. Across runs: a resumed run that
executes a step again decides that step; a FAIL of an earlier run whose step was not executed again stays a FAIL.
A migrated receipt whose exit code was inferred never proves success (the step is unknown -> incomplete).
"""
import hashlib, json, sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent)]
import winqa_plan as wp  # noqa: E402

SCHEMA = 'winqa-verdict/1'
_ORDER = ('pass', 'incomplete', 'fail', 'rejected')


def _worst(a, b):
    return a if _ORDER.index(a) >= _ORDER.index(b) else b


def _chain(out, plan):
    chain, p = [plan], plan
    while p.get('resumes'):
        p = wp.load_plan(out, p['resumes']['run_id'])
        chain.append(p)
    return chain


def step_results(plan, rows, retryable):
    """{step: 'ok'|'FAIL'|'unknown'} for the receipts of ONE run, failure latched."""
    res, failed = {}, {}
    for r in rows:
        s = r['step']
        if r['status'] == 'FAIL' or r['exit_code'] != 0 and r['status'] == 'ok':
            failed.setdefault(s, set()).add(r['seq'])
            res[s] = 'FAIL'
            continue
        if r.get('exit_code_source') == 'inferred':
            res.setdefault(s, 'unknown')
            continue
        if s in failed:
            if s in retryable and r.get('retry_of') in failed[s]:
                failed[s].discard(r['retry_of'])
                res[s] = 'FAIL' if failed[s] else 'ok'
            continue                                    # an ok without an explicit retry never covers a FAIL
        res[s] = 'ok'
    return res


def evaluate(out: Path, run_id: str, manifest=None, bundle_sha256=None):
    plan = wp.load_plan(out, run_id)
    mine = wp.receipts(out, run_id)
    reasons, overall = [], 'pass'
    # evidence: the manifest must be the one exported for THIS plan's full obligations (#318)
    if manifest is None:
        overall, reasons = 'incomplete', ['no final bundle']
        evidence = None
    else:
        evidence = {'status': manifest.get('status'), 'missing': manifest.get('missing_required'),
                    'contract_problems': manifest.get('contract_problems'), 'error_codes': manifest.get('error_codes'),
                    'withheld': [w.get('name') for w in manifest.get('withheld') or []]}
        if manifest.get('plan_sha256') != plan['plan_sha256'] or sorted(manifest.get('required') or []) != plan['required']:
            overall = 'rejected'; reasons.append('bundle not bound to this plan')
        elif manifest.get('status') != 'complete':
            overall = _worst(overall, 'incomplete'); reasons.append('evidence incomplete: ' + ','.join(manifest.get('missing_required') or []))
    if plan.get('required_unknown'):
        overall = _worst(overall, 'incomplete'); reasons.append('required evidence of a legacy run is unknown: rerun from step 0')
    # steps: this run decides what it executed; earlier runs of the chain decide the rest
    retry = {s['id'] for s in plan['steps'] if s.get('retryable')}
    results = step_results(plan, mine, retry)
    for older in _chain(out, plan)[1:]:
        for s, v in step_results(older, wp.receipts(out, older['run_id']), set()).items():
            results.setdefault(s, v)
    # point 2: a step that says ok while its own result file says ok:false is a contradiction -> FAIL
    bad = set((manifest or {}).get('ok_false') or [])
    for st in plan['steps']:
        if results.get(st['id']) == 'ok' and bad & set(st['produces']):
            results[st['id']] = 'FAIL'
    for s, v in sorted(results.items()):
        if v == 'FAIL':
            overall = _worst(overall, 'fail'); reasons.append(f'step {s} failed')
        elif v == 'unknown':
            overall = _worst(overall, 'incomplete'); reasons.append(f'step {s} only has an inferred result')
    for s in plan['steps']:
        if s['id'] not in results and s['id'] not in wp.NO_RECEIPT:
            overall = _worst(overall, 'incomplete'); reasons.append(f'step {s["id"]} has no receipt')
    rfile = wp.runs_dir(out) / run_id / 'receipts.jsonl'
    return {'schema': SCHEMA, 'run_id': run_id, 'overall': overall, 'reasons': reasons, 'steps': results,
            'evidence': evidence,
            'binding': {'plan_sha256': plan['plan_sha256'], 'bundle_sha256': bundle_sha256,
                        'receipts_upto_seq': len(mine),
                        'receipts_sha256': hashlib.sha256(rfile.read_bytes() if rfile.exists() else b'').hexdigest()}}


def check_binding(out: Path, verdict) -> bool:
    """summarize.py calls this before rendering: a verdict whose plan/receipts moved on is not rendered."""
    b = verdict.get('binding') or {}
    try:
        plan = wp.load_plan(out, verdict['run_id'])
    except Exception:
        return False
    rfile = wp.runs_dir(out) / verdict['run_id'] / 'receipts.jsonl'
    data = rfile.read_bytes() if rfile.exists() else b''
    return b.get('plan_sha256') == plan['plan_sha256'] and \
        b.get('receipts_sha256') == hashlib.sha256(data).hexdigest() and \
        b.get('receipts_upto_seq') == len([l for l in data.splitlines() if l.strip()])


def main(a):
    if not a or a[0] != 'final':
        print(__doc__, file=sys.stderr); return 2
    out = Path(wp._arg(a, '--out'))
    mf = wp._arg(a, '--manifest')
    manifest = json.loads(Path(mf).read_text(encoding='utf-8')) if mf and Path(mf).exists() else None
    v = evaluate(out, wp._arg(a, '--run-id'), manifest, wp._arg(a, '--bundle-sha256'))
    dest = Path(wp._arg(a, '--dest'))
    dest.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # steps.txt: a read-only view of the verdict (never read back to decide anything)
    (out / 'steps.txt').write_text(''.join(f'{k}={v_}\n' for k, v_ in sorted(v['steps'].items())), encoding='utf-8')
    return 0 if v['overall'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
