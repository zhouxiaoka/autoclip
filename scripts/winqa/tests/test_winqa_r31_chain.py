"""#414 design v5 part B (scripts/winqa): one verification point, winqa_chain.verify_chain. Cases marked e2e drive
run_winqa.sh / the CLIs and also run unchanged against the code before v5; the others use make_run(), which writes
a real run directory only through winqa_plan.create/record (M6: no hand-made verdicts)."""
import hashlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from _winqa_helpers import (KEY, ROOT, BASHES, _env, _assert_no_raw_on_control, _ee, _export, _rebuild, _verify,
                            INPUTS, CAND, make_run, make_passing_run, _wpwc)

PLAN_CLI = [sys.executable, str(ROOT / 'py' / 'winqa_plan.py')]
VERDICT_CLI = [sys.executable, str(ROOT / 'py' / 'winqa_verdict.py')]


def _wc():
    return _wpwc()[1]


def _wp():
    return _wpwc()[0]


def _verdict(ev):
    vs = sorted((ev / 'runs').glob('*/verdict-final.json'))
    return json.loads(vs[-1].read_text()) if vs else None


def _sh(tmp_path, bash, env, args, timeout=170):
    return subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=timeout)


def _summarize(ev, verdict_file):
    return subprocess.run([sys.executable, str(ROOT / 'summarize.py'), str(ev), '--verdict', str(verdict_file)],
                          capture_output=True, text=True)


# ---------------------------------------------------------------- T-B1 / T-B2: #384 artifacts bound to receipts
def test_b1_required_file_outside_the_bound_bundle_does_not_count(tmp_path):
    files = {'steps.json': b'[]'}                       # the bundle lacks collect-logs-final.json
    make_run(tmp_path, files=files)
    (tmp_path / 'collect-logs-final.json').write_text('{"ok": true}')   # a stale copy in the evidence view
    r = _wc().verify_chain(tmp_path, 'r1', 'final')
    assert not r.passed and any('incomplete' in x or 'missing' in x for x in r.reasons), r.reasons


@pytest.mark.parametrize('where', ['attempt', 'zip', 'view'])
def test_b2_any_bound_byte_changed_after_the_receipt_is_rejected(tmp_path, where):
    v = make_passing_run(tmp_path)
    if where == 'attempt':
        p = next((tmp_path / 'runs' / 'r1').glob('a*/pull_final/collect-logs-final.json'))
    elif where == 'zip':
        p = next((tmp_path / 'bundles').glob('*.zip'))
    else:
        p = tmp_path / 'collect-logs-final.json'
    p.write_bytes(p.read_bytes() + b' ')
    mode = 'render' if where == 'view' else 'final'
    assert _wc().verify_chain(tmp_path, 'r1', mode).overall == _wc().REJECTED


# ---------------------------------------------------------------- T-B3: #385 resume needs the same candidate (e2e)
@pytest.mark.parametrize('bash', BASHES)
def test_b3_resume_with_another_candidate_installer_is_refused(tmp_path, bash):
    env, args = _env(tmp_path)
    first = _sh(tmp_path, bash, env, args)
    assert first.returncode == 0, first.stdout[-400:]
    other = tmp_path / 'other.exe'; other.write_bytes(b'MZ other build')
    a2 = list(args); a2[a2.index('--candidate') + 1] = str(other)
    second = _sh(tmp_path, bash, env, a2)
    assert second.returncode == 71, (second.returncode, second.stdout[-400:])
    _assert_no_raw_on_control(tmp_path, second)


def test_b3_plan_without_candidate_is_refused_64(tmp_path):
    done = subprocess.run(PLAN_CLI + ['create', '--out', str(tmp_path), '--run-id', 'r1', '--from', '8', '--to', '8'])
    assert done.returncode == 64


# ---------------------------------------------------------------- T-B4: #386 render recomputes (e2e)
@pytest.mark.parametrize('bash', BASHES)
def test_b4_evidence_changed_after_a_pass_is_not_rendered_as_pass(tmp_path, bash):
    env, args = _env(tmp_path)
    done = _sh(tmp_path, bash, env, args)
    assert done.returncode == 0, done.stdout[-400:]
    ev = tmp_path / 'ev'
    vf = sorted((ev / 'runs').glob('*/verdict-final.json'))[-1]
    (ev / 'collect-logs-final.json').write_text('{"ok": false}')
    s = _summarize(ev, vf)
    assert s.returncode == 3 and not s.stdout.startswith('PASS'), s.stdout[:200]


def test_b4_m13_one_receipt_line_changed_with_the_count_unchanged_is_rejected(tmp_path):
    v = make_passing_run(tmp_path)
    rf = tmp_path / 'runs' / 'r1' / 'receipts.jsonl'
    lines = rf.read_text().splitlines()
    row = json.loads(lines[0]); row['exit_code'] = 0; row['at'] = 'x'
    lines[0] = json.dumps(row, sort_keys=True, separators=(',', ':'))
    rf.write_text('\n'.join(lines) + '\n')
    assert _wc().verify_chain(tmp_path, 'r1', 'render').overall == _wc().REJECTED
    vf = tmp_path / 'v.json'; vf.write_text(json.dumps(v))
    assert _summarize(tmp_path, vf).returncode == 3


# ---------------------------------------------------------------- T-B5 / T-B6: #387 migration
def test_b5_migration_interrupted_before_the_index_keeps_the_obligations(tmp_path):
    (tmp_path / 'required.txt').write_text('clean.json,collect-logs-final.json\n')
    (tmp_path / 'steps.txt').write_text('clean=ok\n')
    assert subprocess.run(PLAN_CLI + ['migrate', '--out', str(tmp_path)]).returncode == 0
    (tmp_path / 'runs' / 'index.jsonl').unlink()           # killed after the plan, before the index line
    assert subprocess.run(PLAN_CLI + ['migrate', '--out', str(tmp_path)]).returncode == 0
    done = subprocess.run(PLAN_CLI + ['create', '--out', str(tmp_path), '--run-id', 'r2', '--from', '8', '--to', '8',
                                      '--inputs', json.dumps(INPUTS)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    plan = json.loads((tmp_path / 'runs' / 'r2' / 'plan.json').read_text())
    assert 'clean.json' in plan['required'], plan['required']


def test_b5_tmp_dir_of_an_interrupted_migration_is_redone_and_old_files_are_untouched(tmp_path):
    (tmp_path / 'bundles').mkdir()
    (tmp_path / 'bundles' / 'old.manifest.json').write_text(json.dumps({'required': ['clean.json', 'steps.json']}))
    (tmp_path / 'steps.txt').write_text('clean=ok\n')
    (tmp_path / 'runs' / '.tmp-legacy').mkdir(parents=True)
    (tmp_path / 'runs' / '.tmp-legacy' / 'plan.json').write_text('half')
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file() and 'runs' not in p.parts}
    assert subprocess.run(PLAN_CLI + ['migrate', '--out', str(tmp_path)]).returncode == 0
    assert not (tmp_path / 'runs' / '.tmp-legacy').exists()
    plan = json.loads((tmp_path / 'runs' / 'legacy' / 'plan.json').read_text())
    assert plan['required'] == ['clean.json', 'steps.json'] and plan['required_unknown'] is False   # from the manifest
    assert {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file() and 'runs' not in p.parts} == before


@pytest.mark.parametrize('bash', BASHES)
def test_b6_legacy_measured_ok_never_proves_a_step(tmp_path, bash):
    env, args = _env(tmp_path)
    ev = tmp_path / 'ev'; ev.mkdir()
    (ev / 'required.txt').write_text('collect-logs-final.json\n')
    (ev / 'steps.jsonl').write_text(json.dumps({'step': 'clean', 'status': 'ok', 'exit_code': 0}) + '\n')
    done = _sh(tmp_path, bash, env, args)
    v = _verdict(ev)
    assert done.returncode != 0 and v and not _wc().is_pass(v), (done.returncode, v)
    assert v['steps'].get('clean') == 'unknown', v['steps']


# ---------------------------------------------------------------- T-B7: #388 env returning 4 latches (e2e)
@pytest.mark.parametrize('bash', BASHES)
def test_b7_env_step_returning_4_with_a_leftover_env_json_fails_the_run(tmp_path, bash):
    env, args = _env(tmp_path, steps=('2', '2'))
    (tmp_path / 'vm' / 'out' / 'clean.json').write_text('{"ok": true}')     # env.json is a leftover of an old run
    ssh = tmp_path / 'bin' / 'ssh'
    ssh.write_text(ssh.read_text().replace(
        "    if req['op'] == 'hash':",
        "    if req['op'] == 'ps' and req['args']['script'] == 'env':\n        sys.exit(4)\n    if req['op'] == 'hash':", 1))
    done = _sh(tmp_path, bash, env, args)
    v = _verdict(tmp_path / 'ev')
    assert done.returncode != 0, done.stdout[-400:]
    assert v is None or not _wc().is_pass(v)
    assert v is not None and v['steps'].get('env') == 'FAIL', v and v['steps']


# ---------------------------------------------------------------- T-B8: receipt chain
@pytest.mark.parametrize('how', ['drop_middle', 'duplicate_seq', 'other_plan', 'gap_rechained'])
def test_b8_receipt_chain_tampering_is_rejected(tmp_path, how):
    make_run(tmp_path, receipts=[('collect_logs', 'ok'), ('collect_logs', 'ok')])
    rf = tmp_path / 'runs' / 'r1' / 'receipts.jsonl'
    rows = [json.loads(l) for l in rf.read_text().splitlines()]
    if how == 'drop_middle':
        rows.pop(1)
    elif how == 'duplicate_seq':
        rows[1]['seq'] = 1
    elif how == 'gap_rechained':                    # row 1 removed and the chain recomputed: only the seq gap shows it
        rows.pop(0)
        prev = ''
        for r in rows:
            r['chain'] = _wc().chain_hash(prev, r); prev = r['chain']
    else:
        rows[0]['plan_sha256'] = '0' * 64
    rf.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    assert _wc().verify_chain(tmp_path, 'r1', 'stage').overall == _wc().REJECTED


# ---------------------------------------------------------------- T-B9 / M10: #321 the result file decides
@pytest.mark.parametrize('content', [b'{"ok": false}', None])
def test_b9_result_file_ok_false_or_missing_fails_the_step_whatever_its_exit_code(tmp_path, content):
    files = {'steps.json': b'[]'} if content is None else {'collect-logs-final.json': content}
    make_run(tmp_path, files=files, manifest_edit=(lambda m: None))
    r = _wc().verify_chain(tmp_path, 'r1', 'final')
    assert not r.passed
    assert r.steps['collect_logs'] == 'FAIL', r.steps
    assert r.overall == _wc().FAIL, (r.overall, r.reasons)


def test_b1b_required_file_missing_from_the_bundle_with_a_forged_complete_manifest_is_incomplete(tmp_path):
    make_run(tmp_path, files={'collect-logs-final.json': b'{"ok": true}', 'steps.json': None})   # manifest still says complete
    wp, wc = _wpwc()
    r = wc.verify_chain(tmp_path, 'r1', 'final')
    assert r.overall == wc.INCOMPLETE and any('steps.json' in x for x in r.reasons), (r.overall, r.reasons)


def test_b10_manifest_of_another_plan_is_rejected(tmp_path):
    make_run(tmp_path, manifest_edit=lambda m: m.update(plan_sha256='0' * 64))
    assert _wc().verify_chain(tmp_path, 'r1', 'final').overall == _wc().REJECTED


def test_b15_resume_chain_longer_than_32_is_rejected(tmp_path):
    prev = None
    for i in range(34):
        prev = _plan_file(tmp_path, f'r{i}', prev and {'run_id': prev['run_id'], 'plan_sha256': prev['plan_sha256']})
    r = _wc().verify_chain(tmp_path, 'r33', 'stage')
    assert r.overall == _wc().REJECTED and any('bound' in x for x in r.reasons), r.reasons


def test_b9_every_planned_step_has_a_result_table_entry():
    wc = _wc()
    for rows in _wp().TABLE.values():
        for name, *_ in rows:
            assert name in wc.RESULT_FILES


# ---------------------------------------------------------------- T-B10 / #326 / #396: one field at a time
@pytest.mark.parametrize('field', ['status', 'missing_required', 'error_codes', 'ok_false', 'required'])
def test_b10_each_manifest_field_alone_makes_verify_reject(tmp_path, field):
    src = tmp_path / 'out'; src.mkdir()
    (src / 'a.json').write_text('{"ok": true, "error_code": "X1"}')
    assert _export(tmp_path, src, extra=('--require', 'a.json')).returncode == 0
    good = (tmp_path / 'exp' / 'b1.zip').read_bytes()
    assert _verify(tmp_path, good) == 0

    def edit(m, members):
        if field == 'status':
            m['status'] = 'incomplete'
        elif field == 'missing_required':
            m['missing_required'] = ['a.json']
        elif field == 'error_codes':
            m['error_codes'] = {'a.json': []}
        elif field == 'ok_false':
            m['ok_false'] = ['a.json']
        else:
            m['required'] = ['a.json']                      # steps.json dropped from required only
    assert _verify(tmp_path, _rebuild(good, manifest_edit=edit)) == 1


def test_b10_396_pass_needs_the_receipts_hash_comparison_alone(tmp_path):
    """#396 / #322: same plan, same count, same bundle - only the receipts' content differs from the verdict's."""
    v = make_passing_run(tmp_path)
    rf = tmp_path / 'runs' / 'r1' / 'receipts.jsonl'
    rows = [json.loads(l) for l in rf.read_text().splitlines()]
    wc, wp = _wc(), _wp()
    rows[0]['at'] = 'rewritten'
    prev = ''
    for r in rows:                                          # a consistent rewrite: the chain itself re-made
        r['chain'] = wc.chain_hash(prev, r); prev = r['chain']
    rf.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    vf = tmp_path / 'v.json'; vf.write_text(json.dumps(v))
    assert _summarize(tmp_path, vf).returncode == 3         # the verdict's chain head no longer matches


# ---------------------------------------------------------------- T-B13: only winqa_chain may write pass (M6)
_PASS_LITERAL = re.compile(r'''(?<![A-Za-z_])(['"])pass\1''')


def test_b13_no_pass_literal_outside_winqa_chain_tests_included():
    hits = []
    for p in sorted(ROOT.rglob('*')):
        if p.suffix not in ('.py', '.sh', '.ps1') or '__pycache__' in p.parts:
            continue
        if p == ROOT / 'py' / 'winqa_chain.py':
            continue
        for i, line in enumerate(p.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            if _PASS_LITERAL.search(line):
                hits.append(f'{p.relative_to(ROOT)}:{i}')
    assert not hits, hits


# ---------------------------------------------------------------- T-B14: old schema bundle (regression)
def test_b14_unknown_bundle_schema_is_refused(tmp_path):
    src = tmp_path / 'out'; src.mkdir(); (src / 'a.json').write_text('{"ok": true}')
    assert _export(tmp_path, src, extra=('--require', 'a.json')).returncode == 0
    good = (tmp_path / 'exp' / 'b1.zip').read_bytes()

    def old(m, members):
        m['schema'] = 'winqa-bundle/2'
    assert _verify(tmp_path, _rebuild(good, manifest_edit=old)) == 1


# ---------------------------------------------------------------- T-B15: M11 resume cycle is bounded
def _plan_file(out, rid, resumes):
    plan = {'schema': 'winqa-plan/1', 'run_id': rid, 'created_at': '', 'window': [8, 8], 'flags': [], 'inputs': INPUTS,
            'steps': [], 'required': ['steps.json'], 'required_unknown': False, 'resumes': resumes, 'carried': []}
    body = json.dumps(plan, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    plan['plan_sha256'] = hashlib.sha256(body).hexdigest()       # the plan hash rule, written out (no import)
    (out / 'runs' / rid).mkdir(parents=True, exist_ok=True)
    (out / 'runs' / rid / 'plan.json').write_text(json.dumps(plan))
    return plan


def test_b15_resume_cycle_is_rejected_quickly(tmp_path):
    a = _plan_file(tmp_path, 'ra', {'run_id': 'rb', 'plan_sha256': 'x'})
    b = _plan_file(tmp_path, 'rb', {'run_id': 'ra', 'plan_sha256': a['plan_sha256']})
    a = _plan_file(tmp_path, 'ra', {'run_id': 'rb', 'plan_sha256': b['plan_sha256']})
    # a true hash cycle cannot be built (each link names the other's hash), so the hash binding breaks it first;
    # the visited set stays as defence in depth (MB19 is equivalent while plan hashes bind the links)
    b = _plan_file(tmp_path, 'rb', {'run_id': 'ra', 'plan_sha256': a['plan_sha256']})
    try:
        done = subprocess.run(VERDICT_CLI + ['final', '--out', str(tmp_path), '--run-id', 'ra', '--dest',
                                             str(tmp_path / 'v.json')], capture_output=True, timeout=20)
    except subprocess.TimeoutExpired:
        pytest.fail('a resume cycle made the verdict loop forever')
    assert done.returncode != 0
    v = json.loads((tmp_path / 'v.json').read_text())
    assert v['overall'] == 'rejected' and any('resume' in r for r in v['reasons']), v


# ---------------------------------------------------------------- T-B16: the stage check runs before every step
@pytest.mark.parametrize('bash', BASHES)
def test_b16_tampered_receipts_stop_the_next_step_with_73(tmp_path, bash):
    env, args = _env(tmp_path)
    fake = (tmp_path / 'bin' / 'python3').read_text()
    (tmp_path / 'bin' / 'python3').write_text(fake.replace(
        "os.execv(", "if any(x.endswith('winqa_chain.py') for x in a) and 'check' in a:\n    sys.exit(73)\nos.execv(", 1))
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=180)
    assert done.returncode == 73, (done.returncode, done.stdout[-600:])
    assert '证据链校验失败'.encode() in done.stdout
