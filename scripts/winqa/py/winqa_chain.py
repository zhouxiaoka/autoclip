#!/usr/bin/env python3
"""#414 design v5 part B: the ONE verification point of a Windows QA run. Only this module can produce a passing
verdict (I-B1; the literal and the overall values live here only, M6). winqa_verdict.py serialises its result,
summarize.py renders it, run_winqa.sh asks it before every step; none of them judges anything itself.

    verify_chain(out, run_id, mode)   mode: stage | final | render (stage skips only the final-bundle requirement)
    1 plan        plan_sha256 recomputed; every path through name_ok; candidate_sha256 present; log_channel planned
    2 resumes     walked with a visited set and a depth bound (M11); same candidate on every run (#385); every
                  inherited run has its bundles re-checked (I434): a mismatch makes its steps unknown (rerun)
    3 receipts    run_id / plan_sha256 of this plan; seq 1..n without gaps; hash chain h_n = sha256(h_{n-1}+row);
                  status only ok | FAIL (I473)
    4 bundles     every export receipt: the ZIP in bundles/ re-hashed (#386) and OPENED (I436): its members are
                  exactly the files of runs/<id>/a<n>/<step>/, byte for byte; the final one binds the evidence view (M9)
    5 producers   (I434) an ok producer step is bound to the first export after its receipt: its outputs must be in
                  that bundle, and every later bundle must carry the same bytes
    6 results     RESULT_FILES (one table: step -> [(file, judge)], M10/I435): every result JSON of a step is judged;
                  any FAIL fails the step whatever its exit code said (#321)
    7 obligations required from the plan; required_unknown, inferred-only, or a required file whose producer has no
                  measured ok receipt (I437) -> incomplete; log_channel is measured in THIS run only (I438)
    8 latch       a FAIL stays a FAIL unless a retryable step's later ok names it (retry_of)
"""
import hashlib, io, json, sys, zipfile
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent)]
import winqa_plan as wp  # noqa: E402
from export_evidence import STEPS, name_ok  # noqa: E402

SCHEMA = 'winqa-verdict/2'
PASS, INCOMPLETE, FAIL, REJECTED = 'pass', 'incomplete', 'fail', 'rejected'
ORDER = (PASS, INCOMPLETE, FAIL, REJECTED)
LABELS = {PASS: 'PASS', INCOMPLETE: 'INCOMPLETE', FAIL: 'FAIL', REJECTED: 'REJECTED'}
MAX_RESUME_DEPTH = 32
EXPORT_STEPS = frozenset({'export_after_3', 'export_after_6', 'pull_final'})
FINAL_EXPORT = 'pull_final'
LOG_CHANNEL = wp.LOG_CHANNEL
NOT_INHERITED = frozenset({LOG_CHANNEL, FINAL_EXPORT})


def ok_true(d):
    """the producer writes `ok`: it must be True (absent = FAIL)"""
    return isinstance(d, dict) and d.get('ok') is True


def ok_not_false(d):
    """the producer writes no `ok` of its own (clean, env, stop, the CI smoke reports): ok:false still fails"""
    return isinstance(d, dict) and d.get('ok') is not False


def runs_exit0(d):
    """smoke.json aggregate: every run listed, every exit_code 0"""
    runs = d.get('runs') if isinstance(d, dict) else None
    return isinstance(runs, list) and bool(runs) and all(isinstance(r, dict) and r.get('exit_code') == 0 for r in runs) \
        and d.get('ok') is not False


_JUDGE_OF = {'smoke.json': runs_exit0, 'clean.json': ok_not_false, 'env.json': ok_not_false,
             'stop-candidate.json': ok_not_false, 'windows-smoke.json': ok_not_false,
             'windows-smoke-desktop.json': ok_not_false, 'windows-sensevoice-installed.json': ok_not_false,
             'windows-whisper-installed.json': ok_not_false}


def _result_files():
    """step -> [(result JSON, judge)] for EVERY JSON the step produces (I435). Built once from the plan table; a step
    missing here cannot be planned (M10)."""
    out = {}
    for rows in wp.TABLE.values():
        for name, produces, _cond, optional in rows:
            out[name] = [(f, _JUDGE_OF.get(f, ok_true)) for f in produces + optional if f.endswith('.json')]
    return out


RESULT_FILES = _result_files()
PRODUCER = {f: name for rows in wp.TABLE.values() for name, produces, _c, _o in rows for f in produces}


def worst(a, b):
    return a if ORDER.index(a) >= ORDER.index(b) else b


def is_pass(v) -> bool:
    return v.get('overall') == PASS


class Result:
    def __init__(self):
        self.overall, self.reasons, self.steps, self.binding, self.evidence = PASS, [], {}, {}, None

    def bump(self, level, reason):
        self.overall = worst(self.overall, level)
        if reason not in self.reasons:
            self.reasons.append(reason)

    @property
    def passed(self):
        return self.overall == PASS

    def as_dict(self, run_id):
        return {'schema': SCHEMA, 'run_id': run_id, 'overall': self.overall, 'reasons': self.reasons,
                'steps': self.steps, 'evidence': self.evidence, 'binding': self.binding}


def chain_hash(prev: str, row) -> str:
    body = {k: v for k, v in row.items() if k != 'chain'}
    return hashlib.sha256((prev or '').encode() + wp.canon(body)).hexdigest()


def _sha(p: Path):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def step_results(plan, rows, retryable):
    """{step: 'ok'|'FAIL'|'unknown'} for the receipts of ONE run, failure latched."""
    res, failed = {}, {}
    for r in rows:
        s = r['step']
        if r['status'] != 'ok' or r['exit_code'] != 0:      # I473: anything but ok / FAIL is a FAIL
            failed.setdefault(s, set()).add(r['seq'])
            res[s] = 'FAIL'
            continue
        if r.get('exit_code_source') == 'inferred' or r.get('migrated'):   # M7: legacy never proves success
            res.setdefault(s, 'unknown')
            continue
        if s in failed:
            if s in retryable and r.get('retry_of') in failed[s]:
                failed[s].discard(r['retry_of'])
                res[s] = 'FAIL' if failed[s] else 'ok'
            continue
        res[s] = 'ok'
    return res


def _check_receipts(plan, rows, R, run_id):
    prev = ''
    for i, r in enumerate(rows, 1):
        if r.get('seq') != i:
            R.bump(REJECTED, f'receipts of {run_id}: seq {r.get("seq")} where {i} was expected'); return False
        if r.get('run_id') != run_id or r.get('plan_sha256') != plan['plan_sha256']:
            R.bump(REJECTED, f'receipts of {run_id}: row {i} not bound to this plan'); return False
        if r.get('chain') != chain_hash(prev, r):
            R.bump(REJECTED, f'receipts of {run_id}: hash chain broken at row {i}'); return False
        prev = r['chain']
    return True


def _bundle_ok(out, run_id, r):
    """I436 + M9: the ZIP of one export receipt is re-hashed and opened; its members are exactly the files of the
    attempt dir, byte for byte, and both match the receipt. -> None or the reason."""
    b = r.get('bundle') or {}
    z = wp.runs_dir(out).parent / 'bundles' / b.get('zip', '')
    if not name_ok(b.get('zip', ''), ()) or _sha(z) != b.get('sha256'):
        return 'bundle ZIP missing or changed since its receipt'
    adir = wp.runs_dir(out) / run_id / f'a{r["attempt"]}' / r['step']
    arts = {a['name']: a['sha256'] for a in r.get('artifacts') or []}
    try:
        with zipfile.ZipFile(io.BytesIO(z.read_bytes())) as zf:
            members = {n: hashlib.sha256(zf.read(n)).hexdigest() for n in zf.namelist() if not n.endswith('/')}
            json.loads(zf.read('manifest.json').decode('utf-8'))
    except Exception:
        return 'bundle is not a readable ZIP with a manifest'
    have = {p.relative_to(adir).as_posix(): _sha(p) for p in adir.rglob('*') if p.is_file()} if adir.is_dir() else {}
    if members != have or members != arts:
        changed = sorted(n for n in set(members) | set(have) | set(arts)
                         if not (members.get(n) == have.get(n) == arts.get(n)))
        return 'artifact_changed ' + ','.join(changed[:3])
    return None


def _check_bundles(out, run_id, rows):
    for r in rows:
        if r.get('bundle'):
            why = _bundle_ok(out, run_id, r)
            if why:
                return why
    return None


def _producer_bindings(plan, rows, R, final_arts, results, mode):
    """I434: an ok producer step -> the first export after its receipt carries its outputs; later bundles (and the
    final one) the same bytes. Returns the steps that are not bound."""
    produces = {s['id']: s['produces'] for s in plan['steps']}
    exports = [r for r in rows if r.get('bundle')]
    bad = {}
    for r in rows:
        s = r['step']
        if s in EXPORT_STEPS or not produces.get(s) or results.get(s) != 'ok' or r['status'] != 'ok':
            continue
        after = [e for e in exports if e['seq'] > r['seq']]
        if not after:
            if mode != 'stage':
                bad[s] = f'step {s}: no export after its receipt carries its output'
            continue
        first = {a['name']: a['sha256'] for a in after[0].get('artifacts') or []}
        for f in produces[s]:
            if f not in first:
                bad[s] = f'step {s}: {f} is not in the export right after the step'
                break
            later = [{a['name']: a['sha256'] for a in e.get('artifacts') or []} for e in after[1:]] + \
                ([final_arts] if final_arts is not None else [])
            if any(f in arts and arts[f] != first[f] for arts in later) or \
                    (final_arts is not None and f not in final_arts):
                bad[s] = f'step {s}: {f} changed after the export that bound it'
                break
    return bad


def _resume_chain(out, plan, R):
    """[plan, older, ...] with a visited set and depth bound (I-B7); same candidate everywhere (I-B4)."""
    chain, seen, p = [plan], {plan['run_id']}, plan
    while p.get('resumes'):
        rid = p['resumes'].get('run_id')
        if rid in seen:
            R.bump(REJECTED, f'resume_cycle at {rid}'); return chain
        if len(chain) > MAX_RESUME_DEPTH:
            R.bump(REJECTED, 'resume chain longer than the bound'); return chain
        seen.add(rid)
        try:
            older = wp.load_plan(out, rid)
        except Exception:
            R.bump(REJECTED, f'resumed run {rid} has no valid plan'); return chain
        if older['plan_sha256'] != p['resumes'].get('plan_sha256'):
            R.bump(REJECTED, f'resumed run {rid} plan changed'); return chain
        if not older.get('migrated') and (older.get('inputs') or {}).get('candidate_sha256') != \
                (plan.get('inputs') or {}).get('candidate_sha256'):
            R.bump(REJECTED, f'resumed run {rid} was for another candidate installer'); return chain
        if not _check_receipts(older, wp.receipts(out, rid), R, rid):
            return chain
        older = dict(older, _bundles_bad=_check_bundles(out, rid, wp.receipts(out, rid)))   # I434 / M8-b
        chain.append(older)
        p = older
    return chain


def _final_bundle(out, run_id, rows, R, mode):
    """Step 4: the last export receipt of this run binds a bundle; everything is re-hashed now."""
    fin = [r for r in rows if r['step'] == FINAL_EXPORT]
    if not fin or not fin[-1].get('bundle'):
        R.bump(INCOMPLETE, 'no final bundle'); return None
    r = fin[-1]
    adir = wp.runs_dir(out) / run_id / f'a{r["attempt"]}' / FINAL_EXPORT
    arts = {a['name']: a['sha256'] for a in r.get('artifacts') or []}
    for name, digest in arts.items():
        if not name_ok(name, ()):
            R.bump(REJECTED, f'artifact_changed {name}'); return None
        if mode == 'render' and name != 'manifest.json' and _sha(out / name) != digest:
            R.bump(REJECTED, f'evidence view differs from the bound bundle: {name}'); return None
    return r, adir, arts


def verify_chain(out, run_id, mode='final'):
    out = Path(out)
    R = Result()
    try:
        plan = wp.load_plan(out, run_id)
    except Exception:
        R.bump(REJECTED, 'plan missing or changed'); return R
    if not plan.get('migrated') and not (plan.get('inputs') or {}).get('candidate_sha256'):
        R.bump(REJECTED, 'plan has no candidate_sha256')
    for st in plan['steps']:
        if st['id'] not in RESULT_FILES:
            R.bump(REJECTED, f'step {st["id"]} has no entry in the result table')
    rows = wp.receipts(out, run_id)
    if not _check_receipts(plan, rows, R, run_id):
        return R
    chain = _resume_chain(out, plan, R)
    R.binding = {'plan_sha256': plan['plan_sha256'], 'receipts_upto_seq': len(rows),
                 'receipts_chain_head': rows[-1]['chain'] if rows else '', 'bundle_sha256': None}
    if R.overall == REJECTED:
        return R
    why = _check_bundles(out, run_id, rows)                    # every bundle of THIS run, in every mode (I436)
    if why:
        R.bump(REJECTED, why); return R
    retry = {s['id'] for s in plan['steps'] if s.get('retryable')}
    results = step_results(plan, rows, retry)
    for older in chain[1:]:
        orows = wp.receipts(out, older['run_id'])
        ores = step_results(older, orows, set())
        if older.get('_bundles_bad'):                          # I434 / M8-b: inherited evidence changed -> rerun
            R.bump(INCOMPLETE, f'inherited run {older["run_id"]}: {older["_bundles_bad"]}; rerun its steps')
            ores = {k: ('unknown' if v == 'ok' else v) for k, v in ores.items()}
        else:
            for s, why in _producer_bindings(older, orows, R, None, ores, 'stage').items():
                ores[s] = 'unknown'; R.bump(INCOMPLETE, f'inherited {why}')
        for s, v in ores.items():
            if s not in NOT_INHERITED:                         # I438: the log channel is measured in this run only
                results.setdefault(s, v)
    planned = {s['id'] for s in plan['steps']}
    if LOG_CHANNEL not in planned:                             # Dong R31 point 3: a plan from before log_channel
        results[LOG_CHANNEL] = 'unknown'
        R.bump(INCOMPLETE, 'plan has no log_channel step (made before R31): rerun from step 0')
    final_arts = None
    if mode != 'stage':
        bound = _final_bundle(out, run_id, rows, R, mode)
        if R.overall == REJECTED:
            return R
        if bound:
            r, adir, final_arts = bound
            R.binding['bundle_sha256'] = r['bundle']['sha256']
            try:
                m = json.loads((adir / 'manifest.json').read_text(encoding='utf-8'))
            except Exception:
                R.bump(REJECTED, 'bound bundle has no manifest'); return R
            R.evidence = {'status': m.get('status'), 'missing': m.get('missing_required'),
                          'contract_problems': m.get('contract_problems'), 'error_codes': m.get('error_codes'),
                          'withheld': [w.get('name') for w in m.get('withheld') or []]}
            if m.get('plan_sha256') != plan['plan_sha256'] or sorted(m.get('required') or []) != plan['required']:
                R.bump(REJECTED, 'bundle not bound to this plan')
                return R
            missing = sorted(f for f in plan['required'] if f not in final_arts)
            if missing or m.get('status') != 'complete':
                R.bump(INCOMPLETE, 'evidence incomplete: ' + ','.join(missing or m.get('missing_required') or []))
            # results: EVERY result file of a step in THIS bundle is judged (I435); any FAIL fails the step
            for st in plan['steps']:
                sid = st['id']
                if results.get(sid) != 'ok' or sid in EXPORT_STEPS:
                    continue
                for rf, judge in RESULT_FILES.get(sid) or ():
                    if rf not in final_arts:
                        if rf in plan['required']:
                            results[sid] = 'FAIL'; R.bump(FAIL, f'step {sid}: result file {rf} missing')
                        continue
                    try:
                        data = json.loads((adir / rf).read_text(encoding='utf-8-sig'))
                    except Exception:
                        data = None
                    if not judge(data):
                        results[sid] = 'FAIL'; R.bump(FAIL, f'step {sid}: result file {rf} fails {judge.__name__}')
    for s, why in _producer_bindings(plan, rows, R, final_arts, results, mode).items():
        results[s] = 'FAIL'; R.bump(FAIL, why)
    if plan.get('required_unknown'):
        R.bump(INCOMPLETE, 'required evidence of a legacy run is unknown: rerun from step 0')
    for f in plan['required']:                                 # I437: a required file needs a measured producer
        s = PRODUCER.get(f)
        if s and results.get(s) not in ('ok', 'FAIL') and (mode != 'stage' or s not in planned):
            results.setdefault(s, 'unknown')
            R.bump(INCOMPLETE, f'required {f}: step {s} has no measured receipt; rerun it')
    for s, v in sorted(results.items()):
        if v == 'FAIL':
            R.bump(FAIL, f'step {s} failed')
        elif v == 'unknown':
            R.bump(INCOMPLETE, f'step {s} only has an inferred result')
    for s in plan['steps']:
        if s['id'] not in results and s['id'] not in wp.NO_RECEIPT:
            R.bump(INCOMPLETE, f'step {s["id"]} has no receipt')
    R.steps = results
    return R


def main(a):
    if not a or a[0] != 'check':
        print(__doc__, file=sys.stderr); return 2
    R = verify_chain(Path(wp._arg(a, '--out')), wp._arg(a, '--run-id'), wp._arg(a, '--mode', 'stage'))
    if R.overall == REJECTED:
        print('winqa_chain: REJECTED ' + '; '.join(R.reasons), file=sys.stderr); return 73
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
