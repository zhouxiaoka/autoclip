"""R29 #414 design v4 (scripts/winqa): immutable plan + append-only receipts, one verdict function, migration
that keeps old obligations, multi-line scrubbing (#316), the logpipe channel (#317), the fixed remote entry with
stdin requests (#323), explicit producer failure (#321) and the quality-gate scope (#355, #332)."""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pytest

from _winqa_helpers import (KEY, ROOT, BASHES, _env, _run, _steps, _manifest, _py_bin, _ee, _rebuild, _verify,
                            _export, STEPS_OK, _assert_no_raw_on_control, _tree)

sys.path[:0] = [str(ROOT / 'py'), str(ROOT)]
import winqa_plan as wp  # noqa: E402
import winqa_verdict as wv  # noqa: E402
import redact  # noqa: E402

PWSH = os.environ.get('WINQA_TEST_PWSH') or shutil.which('pwsh')
ENTRY_CMD = 'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File C:\\winqa\\ps\\entry.ps1'


def _receipts(out):
    return [json.loads(l) for f in sorted((out / 'runs').glob('*/receipts.jsonl')) for l in f.read_text().splitlines()]


# ------------------------------------------------------------------ point 1: plan written once, receipts appended

def test_p1_plan_is_written_once_and_a_changed_plan_is_rejected(tmp_path):
    p = wp.create(tmp_path, 'r1', 8, 8, set())
    assert p['required'] == ['collect-logs-final.json', 'steps.json']
    with pytest.raises(FileExistsError):
        wp.create(tmp_path, 'r1', 8, 8, set())
    assert wp.main(['create', '--out', str(tmp_path), '--run-id', 'r1', '--from', '8', '--to', '8']) == wp.E_PLAN
    f = tmp_path / 'runs' / 'r1' / 'plan.json'
    d = json.loads(f.read_text()); d['required'].remove('collect-logs-final.json'); f.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        wp.load_plan(tmp_path, 'r1')


def test_p1_steps_json_is_required_unconditionally_and_stage_exports_only_owe_due_files(tmp_path):
    p = wp.create(tmp_path, 'r1', 0, 99, {'smoke', 'failure', 'real'})
    assert 'steps.json' in p['required'] and 'real/final.json' in p['required']
    assert wp.due(p, 3) == ['install-prev.json', 'launch-prev.json', 'seed.json', 'clean.json', 'env.json', 'steps.json'] \
        or set(wp.due(p, 3)) == {'clean.json', 'env.json', 'install-prev.json', 'launch-prev.json', 'seed.json', 'steps.json'}
    assert 'failure.json' not in wp.due(p, 3) and 'failure.json' in wp.due(p, 6)
    assert 'collect-logs-final.json' not in wp.due(p, 6)        # step 8 is final, never due at a stage export


def test_p1_receipt_rows_are_appended_with_seq_and_a_failed_write_stops_the_run(tmp_path):
    wp.create(tmp_path, 'r1', 8, 8, set())
    wp.record(tmp_path, 'r1', 'collect_logs', 'FAIL', 3)
    wp.record(tmp_path, 'r1', 'collect_logs', 'ok', 0)
    rows = wp.receipts(tmp_path, 'r1')
    assert [(r['seq'], r['attempt'], r['status'], r['exit_code']) for r in rows] == [(1, 1, 'FAIL', 3), (2, 2, 'ok', 0)]
    (tmp_path / 'runs' / 'r1' / 'receipts.jsonl').unlink()
    (tmp_path / 'runs' / 'r1' / 'receipts.jsonl').mkdir()
    assert wp.main(['record', '--out', str(tmp_path), '--run-id', 'r1', '--step', 'x', '--status', 'ok',
                    '--exit-code', '0']) == wp.E_RECEIPT


@pytest.mark.parametrize('bash', BASHES)
def test_p1_shell_stops_with_72_when_a_receipt_cannot_be_written(tmp_path, bash):
    env, args = _env(tmp_path)
    fake = (tmp_path / 'bin' / 'python3').read_text()
    (tmp_path / 'bin' / 'python3').write_text(fake.replace(
        "os.execv(", "if any(x.endswith('winqa_plan.py') for x in a) and 'record' in a:\n    sys.exit(1)\nos.execv(", 1))
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=180)
    assert done.returncode == 72, (done.returncode, done.stdout[-600:])


def test_p1_bundle_must_match_the_local_plan_not_its_own_claim(tmp_path):
    """#318: verify takes required and plan_sha256 from the control machine's plan."""
    plan = wp.create(tmp_path / 'ev', 'r1', 8, 8, set())
    pf = tmp_path / 'ev' / 'runs' / 'r1' / 'plan.json'
    src = tmp_path / 'out'; src.mkdir()
    (src / 'collect-logs-final.json').write_text('{"ok": true}')
    done = _export(tmp_path, src, extra=('--require', 'collect-logs-final.json', '--plan-sha256', plan['plan_sha256']))
    assert done.returncode == 0, done.stderr
    good = (tmp_path / 'exp' / 'b1.zip').read_bytes()

    def run(data):
        p = tmp_path / 'v.zip'; p.write_bytes(data)
        return subprocess.run([sys.executable, str(ROOT / 'py' / 'export_evidence.py'), 'verify', '--bundle', str(p),
                               '--sha256', hashlib.sha256(data).hexdigest(), '--into', str(tmp_path / 'x'),
                               '--plan', str(pf), '--upto', '99', '--keys-stdin'],
                              input=(KEY + '\n').encode(), capture_output=True).returncode
    assert run(good) == 0
    def drop(m, members):   # bundle drops an obligation and stays self-consistent
        m['required'] = ['steps.json']; members.pop('collect-logs-final.json')
        m['files'] = [f for f in m['files'] if f['name'] != 'collect-logs-final.json']
        m['error_codes'] = {}; m['ok_false'] = []
    assert run(_rebuild(good, manifest_edit=drop)) == 1
    def other_plan(m, members):
        m['plan_sha256'] = '0' * 64
    assert run(_rebuild(good, manifest_edit=other_plan)) == 1


# ------------------------------------------------------------------ point 2: producers fail explicitly

def test_p2_receipt_ok_with_nonzero_exit_is_a_contract_problem():
    ee = _ee()
    assert ee.contract_problem('steps.json', [{'run_id': 'r', 'step': 's', 'attempt': 1, 'status': 'ok',
                                               'exit_code': 1}]) == 'steps_contradiction'


def test_p2_step_ok_but_its_file_says_ok_false_fails_the_verdict(tmp_path):
    wp.create(tmp_path, 'r1', 8, 8, set())
    wp.record(tmp_path, 'r1', 'collect_logs', 'ok', 0); wp.record(tmp_path, 'r1', 'pull_final', 'ok', 0)
    plan = wp.load_plan(tmp_path, 'r1')
    m = {'plan_sha256': plan['plan_sha256'], 'required': plan['required'], 'status': 'complete',
         'missing_required': [], 'ok_false': ['collect-logs-final.json'], 'withheld': []}
    assert wv.evaluate(tmp_path, 'r1', m)['overall'] == 'fail'
    m['ok_false'] = []
    assert wv.evaluate(tmp_path, 'r1', m)['overall'] == 'pass'


def test_p2_winqa_probe_seed_exits_non_zero_when_it_writes_ok_false(tmp_path, monkeypatch):
    pytest.importorskip('requests')
    monkeypatch.setenv('WINQA_OUT', str(tmp_path)); monkeypatch.setenv('APPDATA', str(tmp_path))
    import importlib
    probe = importlib.import_module('winqa_probe')
    saved = {}

    class R:
        status_code = 500
    monkeypatch.setattr(probe, 'get', lambda *a, **k: R())
    monkeypatch.setattr(probe, 'body', lambda *a, **k: {})
    monkeypatch.setattr(probe, 'base', lambda: 'http://127.0.0.1:1')
    monkeypatch.setattr(probe.requests, 'put', lambda *a, **k: R())
    monkeypatch.setattr(probe, 'media', lambda *a, **k: ('v', 's'))
    monkeypatch.setattr(probe, 'studio_import', lambda *a, **k: 'p1')
    monkeypatch.setattr(probe, 'projects_index', lambda: (200, []))
    monkeypatch.setattr(probe.time, 'sleep', lambda s: None)
    monkeypatch.setattr(probe, 'save', lambda n, v: saved.update({n: v}))
    rc = probe.seed(type('A', (), {'media': ''})())
    assert saved['seed.json']['ok'] is False and rc == 1


def test_p2_main_entry_of_winqa_probe_uses_the_phase_exit_code():
    src = (ROOT / 'py' / 'winqa_probe.py').read_text(encoding='utf-8')
    assert "sys.exit({'seed': seed, 'check': check, 'failure': failure}[a.phase](a) or 0)" in src
    assert src.count("return 0 if out['ok'] else 1") == 3


def _pwsh_root(tmp_path):
    root = tmp_path / 'winqa'
    (root / 'ps').mkdir(parents=True); (root / 'py').mkdir()
    for f in (ROOT / 'ps').glob('*.ps1'):
        shutil.copy(f, root / 'ps')
    shutil.copy(ROOT / 'py' / 'argshim.py', root / 'py')
    return root


@pytest.mark.skipif(not PWSH, reason='pwsh required (see README); CI has it')
def test_p2_collect_logs_exits_3_when_a_log_cannot_be_copied(tmp_path):
    if os.geteuid() == 0:
        pytest.skip('root reads unreadable files')
    root = _pwsh_root(tmp_path)
    app = tmp_path / 'appdata' / 'AutoClip' / 'logs'; app.mkdir(parents=True)
    (app / 'ok.log').write_text('x'); bad = app / 'locked.log'; bad.write_text('y'); bad.chmod(0)
    env = dict(os.environ, APPDATA=str(tmp_path / 'appdata'), LOCALAPPDATA=str(tmp_path / 'local'), TEMP=str(tmp_path / 't'))
    (tmp_path / 't').mkdir()
    done = subprocess.run([PWSH, '-NoProfile', '-File', str(root / 'ps' / 'collect_logs.ps1'), '-Label', 'final'],
                          cwd=tmp_path, env=env, capture_output=True, timeout=120)
    bad.chmod(0o600)
    assert done.returncode == 3, (done.returncode, done.stdout[-400:], done.stderr[-400:])


# ------------------------------------------------------------------ point 3: one verdict, summarize renders it

def _verdict_dir(tmp_path, statuses):
    wp.create(tmp_path, 'r1', 8, 8, set())
    for step, st in statuses:
        wp.record(tmp_path, 'r1', step, st, 0 if st == 'ok' else 1)
    plan = wp.load_plan(tmp_path, 'r1')
    return {'plan_sha256': plan['plan_sha256'], 'required': plan['required'], 'status': 'complete',
            'missing_required': [], 'ok_false': [], 'withheld': []}


def test_p3_failure_latches_and_only_an_explicit_retry_of_a_retryable_step_clears_it(tmp_path):
    m = _verdict_dir(tmp_path, [('collect_logs', 'FAIL'), ('collect_logs', 'ok'), ('pull_final', 'ok')])
    assert wv.evaluate(tmp_path, 'r1', m)['overall'] == 'fail'          # a later ok is not a retry
    rows = [{'seq': 1, 'step': 's', 'status': 'FAIL', 'exit_code': 1}, {'seq': 2, 'step': 's', 'status': 'ok',
                                                                         'exit_code': 0, 'retry_of': 1}]
    assert wv.step_results({}, rows, set())['s'] == 'FAIL'              # not retryable
    assert wv.step_results({}, rows, {'s'})['s'] == 'ok'                # retryable + names the failure
    rows[1]['retry_of'] = 7
    assert wv.step_results({}, rows, {'s'})['s'] == 'FAIL'


def test_p3_verdict_is_bound_and_summarize_renders_it_without_judging(tmp_path):
    m = _verdict_dir(tmp_path, [('collect_logs', 'ok'), ('pull_final', 'ok')])
    v = wv.evaluate(tmp_path, 'r1', m, 'ab' * 32)
    vf = tmp_path / 'v.json'; vf.write_text(json.dumps(v))
    (tmp_path / 'check-candidate.json').write_text(json.dumps({'assertions': {'backend_health_200': False}}))
    done = subprocess.run([sys.executable, str(ROOT / 'summarize.py'), str(tmp_path), '--verdict', str(vf)],
                          capture_output=True, text=True)
    assert done.returncode == 0 and done.stdout.startswith('PASS'), done.stdout[:200]   # rows do not decide
    v2 = dict(v, overall='fail', reasons=['step x failed']); vf.write_text(json.dumps(v2))
    done = subprocess.run([sys.executable, str(ROOT / 'summarize.py'), str(tmp_path), '--verdict', str(vf)],
                          capture_output=True, text=True)
    assert done.stdout.startswith('FAIL') and '自动项全部通过' not in done.stdout
    wp.record(tmp_path, 'r1', 'late', 'ok', 0)                           # receipts moved on: stale verdict
    done = subprocess.run([sys.executable, str(ROOT / 'summarize.py'), str(tmp_path), '--verdict', str(vf)],
                          capture_output=True, text=True)
    assert done.returncode == 3 and done.stdout == ''


def test_p3_resume_reruns_decide_and_unrun_old_failures_stay(tmp_path):
    wp.create(tmp_path, 'r1', 2, 2, set())
    wp.record(tmp_path, 'r1', 'clean', 'FAIL', 1); wp.record(tmp_path, 'r1', 'collect_logs', 'FAIL', 3)
    wp.create(tmp_path, 'r2', 8, 8, set())
    wp.record(tmp_path, 'r2', 'collect_logs', 'ok', 0); wp.record(tmp_path, 'r2', 'pull_final', 'ok', 0)
    plan = wp.load_plan(tmp_path, 'r2')
    assert 'clean.json' in plan['required'] and plan['resumes']['run_id'] == 'r1'
    m = {'plan_sha256': plan['plan_sha256'], 'required': plan['required'], 'status': 'complete', 'missing_required': [],
         'ok_false': [], 'withheld': []}
    v = wv.evaluate(tmp_path, 'r2', m)
    assert v['steps']['collect_logs'] == 'ok' and v['steps']['clean'] == 'FAIL' and v['overall'] == 'fail'


# ------------------------------------------------------------------ point 5: migration keeps obligations

def test_p5_migration_keeps_old_required_marks_inferred_and_is_idempotent(tmp_path):
    (tmp_path / 'required.txt').write_text('clean.json,env.json\n')
    (tmp_path / 'steps.txt').write_text('clean=ok\npull_final=FAIL\n')
    wp.migrate(tmp_path)
    before = {p: p.read_bytes() for p in (tmp_path / 'runs').rglob('*') if p.is_file()}
    wp.migrate(tmp_path)
    assert {p: p.read_bytes() for p in (tmp_path / 'runs').rglob('*') if p.is_file()} == before
    plan = wp.load_plan(tmp_path, 'legacy')
    assert plan['required'] == ['clean.json', 'env.json', 'steps.json'] and plan['required_unknown'] is False
    rows = wp.receipts(tmp_path, 'legacy')
    assert [(r['step'], r['status'], r['exit_code_source']) for r in rows] == [('clean', 'ok', 'inferred'),
                                                                                 ('pull_final', 'FAIL', 'inferred')]
    assert wv.step_results(plan, rows, set()) == {'clean': 'unknown', 'pull_final': 'FAIL'}


def test_p5_unrecoverable_legacy_obligations_make_a_resume_incomplete_not_green(tmp_path):
    # measured ok results, but the old required list is gone: only the unknown obligation can stop a green
    (tmp_path / 'steps.jsonl').write_text(json.dumps({'run_id': 'x', 'step': 'clean', 'attempt': 1, 'status': 'ok',
                                                      'exit_code': 0}) + '\n')
    wp.migrate(tmp_path)
    assert wp.load_plan(tmp_path, 'legacy')['required_unknown'] is True
    wp.create(tmp_path, 'r2', 8, 8, set())
    wp.record(tmp_path, 'r2', 'collect_logs', 'ok', 0); wp.record(tmp_path, 'r2', 'pull_final', 'ok', 0)
    plan = wp.load_plan(tmp_path, 'r2')
    m = {'plan_sha256': plan['plan_sha256'], 'required': plan['required'], 'status': 'complete', 'missing_required': [],
         'ok_false': [], 'withheld': []}
    v = wv.evaluate(tmp_path, 'r2', m)
    assert v['overall'] == 'incomplete' and v['steps']['clean'] == 'ok', v
    assert any('legacy' in r for r in v['reasons'])
    # a run from step 0 starts fresh obligations (nothing to resume)
    wp.create(tmp_path, 'r3', 0, 0, set())
    assert wp.load_plan(tmp_path, 'r3')['required_unknown'] is False


# ------------------------------------------------------------------ #316 multi-line state machine

@pytest.mark.parametrize('text', [
    'password="PRIVA\nPRIVB" after\n',
    'credentials={"a":"x",\n "b":"PRIVB"}\n',
    'credentials={"a":"}",\r\n"b":"PRIVB"}\r\n',
    'Authorization: Basic PRIVA\r\n  PRIVB\r\nnext: 1\n',
    'token=)PRIVB\n',
])
def test_316_live_lines_never_release_a_value_that_spans_lines(text):
    for chunking in (None, 1, 3):                      # whole, byte by byte and odd chunks (#316: across reads)
        sc = redact.LineScrubber([])
        out = b''
        data = text.encode()
        lines = data.splitlines(keepends=True)
        if chunking:
            lines = [data[i:i + chunking] for i in range(0, len(data), chunking)]
        for l in lines:
            out += sc.feed(l)
        out += sc.close()
        assert b'PRIVB' not in out and b'PRIVA' not in out, (text, chunking, out)


def test_316_unclosed_value_is_masked_to_eof_and_huge_values_sink(monkeypatch):
    sc = redact.LineScrubber([])
    out = sc.feed(b'ok line\n') + sc.feed(b'password="PRIV1\n') + sc.feed(b'PRIV2\n') + sc.close()
    assert out.startswith(b'ok line\n') and b'PRIV' not in out
    monkeypatch.setattr(redact, 'HOLD_LIMIT', 64)
    sc = redact.LineScrubber([])
    out = sc.feed(b'secret={"a":"' + b'x' * 80 + b'\n') + sc.feed(b'PRIV3"}\n') + sc.close()
    assert b'PRIV3' not in out and b'masked to the end' in out


def test_316_lines_mode_error_exits_non_zero_with_nothing_held():
    code = ("import sys; sys.path.insert(0, sys.argv[1]); import redact; "
            "redact.scrub_bytes = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('x')); sys.exit(redact._lines())")
    done = subprocess.run([sys.executable, '-c', code, str(ROOT)], input=b'password="PRIVA\nb"\n', capture_output=True)
    assert done.returncode == 3 and b'PRIVA' not in done.stdout + done.stderr


@pytest.mark.parametrize('v', ['***suffix', '<url>suffix', '<user>suffix'])
def test_327_only_an_exact_mark_is_skipped(v):
    assert 'suffix' not in redact.scrub(f'token={v} rest')
    assert redact.scrub('token=<url> rest') == 'token=<url> rest'


@pytest.mark.parametrize('bash', BASHES)
def test_316_e2e_multiline_secret_from_the_vm_never_reaches_run_log_or_terminal(tmp_path, bash):
    env, args = _env(tmp_path)
    fake = (tmp_path / 'bin' / 'ssh').read_text()
    (tmp_path / 'bin' / 'ssh').write_text(fake.replace(
        "    print('remote: C:\\\\Users\\\\kris\\\\Desktop ok'); sys.exit(0)",
        "    sys.stdout.write('cfg password=\"PRIVA\\n'); sys.stdout.flush(); sys.stdout.write('PRIVB\" end\\n'); sys.exit(0)", 1))
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=180)
    assert done.returncode == 0, done.stdout[-600:]
    log = (tmp_path / 'ev' / 'run.log').read_bytes()
    assert b'cfg password=' in log
    for blob in (log, done.stdout, done.stderr):
        assert b'PRIVA' not in blob and b'PRIVB' not in blob


# ------------------------------------------------------------------ #317 log channel

def _fake_logpipe(tmp_path, body):
    fake = (tmp_path / 'bin' / 'python3').read_text()
    (tmp_path / 'bin' / 'python3').write_text(fake.replace(
        "os.execv(", "if any(x.endswith('logpipe.py') for x in a):\n" + body + "\nos.execv(", 1))


@pytest.mark.parametrize('bash', BASHES)
@pytest.mark.parametrize('mode', ['start-fails', 'no-handshake', 'log-unwritable'])
def test_317_channel_not_up_exits_70_before_any_business_output(tmp_path, bash, mode):
    env, args = _env(tmp_path)
    if mode == 'start-fails':
        _fake_logpipe(tmp_path, '    sys.exit(1)')
    elif mode == 'no-handshake':
        _fake_logpipe(tmp_path, '    import time; time.sleep(30); sys.exit(0)')
    else:
        (tmp_path / 'ev').mkdir(); (tmp_path / 'ev' / 'run.log').mkdir()
    t0 = time.monotonic()
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=60)
    assert done.returncode == 70, (mode, done.returncode, done.stdout[-300:], done.stderr[-300:])
    assert b'====' not in done.stdout + done.stderr and b'WINQA_E_LOGPIPE 70' in done.stderr
    assert time.monotonic() - t0 < 20
    _assert_no_raw_on_control(tmp_path, done)


@pytest.mark.parametrize('bash', BASHES)
def test_317_channel_dying_after_the_last_step_turns_a_green_run_red(tmp_path, bash):
    """The channel scrubbed and showed every line but was killed before it could report its exit: the run's own
    result is green, the final exit code must not be (the real logpipe exit status decides, kill -0 does not)."""
    env, args = _env(tmp_path)
    _fake_logpipe(tmp_path, (
        "    import subprocess\n"
        "    child = subprocess.Popen([os.environ['FAKE_REAL_PY']] + a, stdin=subprocess.PIPE, pass_fds=(6,))\n"
        "    for line in sys.stdin.buffer:\n"
        "        child.stdin.write(line); child.stdin.flush()\n"
        "    child.kill(); child.wait()\n"
        "    sys.exit(0)"))
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=60)
    assert done.returncode == 70, (done.returncode, done.stderr[-300:])
    assert b'WINQA_E_LOGPIPE 70' in done.stderr
    _assert_no_raw_on_control(tmp_path, done)


@pytest.mark.parametrize('bash', BASHES)
def test_317_child_holding_the_write_end_cannot_hang_the_close(tmp_path, bash):
    env, args = _env(tmp_path)
    fake = (tmp_path / 'bin' / 'ssh').read_text()
    (tmp_path / 'bin' / 'ssh').write_text(fake.replace(
        "if cmd == ENTRY:", "if cmd == ENTRY and 'collect_logs' in open(os.environ['FAKE_REQS']).read() if os.path.exists(os.environ['FAKE_REQS']) else False:\n"
        "    pass\nif cmd == ENTRY:", 1).replace(
        "    if req['op'] == 'hash':",
        "    if req['op'] == 'ps' and req['args']['script'] == 'collect_logs':\n"
        "        subprocess.Popen(['sleep', '40'])   # inherits stdout = the log pipe\n"
        "    if req['op'] == 'hash':", 1))
    t0 = time.monotonic()
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=60)
    assert time.monotonic() - t0 < 30
    assert done.returncode == 70, done.returncode


# ------------------------------------------------------------------ #323 fixed entry + stdin request

@pytest.mark.parametrize('bash', BASHES)
def test_323_every_remote_command_line_is_fixed_and_values_travel_on_stdin(tmp_path, bash):
    done = _run(tmp_path, bash)
    assert done.returncode == 0, done.stdout[-600:]
    cmds = set((tmp_path / 'cmds.txt').read_text().splitlines())
    assert ENTRY_CMD in cmds
    assert cmds <= {ENTRY_CMD, 'hostname', 'powershell -NoProfile -Command "New-Item -ItemType Directory -Force C:\\winqa\\ctl | Out-Null"'}, cmds
    reqs = [json.loads(l) for l in (tmp_path / 'reqs.jsonl').read_text().splitlines()]
    assert {(r['op'], r['args']['script']) for r in reqs} == {('ps', 'collect_logs'), ('py', 'export_evidence')}
    assert all(KEY not in json.dumps(r) for r in reqs)            # the key is never in the request line
    assert [r['has_key'] for r in reqs if r['op'] == 'py'] == [True]


def test_323_request_builder_keeps_hostile_values_as_data():
    sys.path.insert(0, str(ROOT / 'py'))
    import winqa_req
    vals = ['$(whoami)', '%PATH%', '"q"', "'s'", '中文', '', 'a\nb', '`whoami`', '; rm -rf /']
    r = winqa_req.build(['py', 'winqa_real', '--key', 'link', '--url'] + vals)
    assert r == {'op': 'py', 'args': {'script': 'winqa_real', 'args': ['link', '--url'] + vals}, 'has_key': True}
    r = winqa_req.build(['ps', 'install', 'Marker=%TEMP%\\$(x)', 'LockLeftover'])
    assert r['args']['params'] == {'Marker': '%TEMP%\\$(x)', 'LockLeftover': True}


def _entry(tmp_path, root, stdin: bytes, stub_py=True):
    rec = tmp_path / 'got.json'
    stub = root / 'py' / 'winqa_real.py'
    stub.write_text("import json, sys\njson.dump({'argv': sys.argv[1:], 'stdin': sys.stdin.read()}, "
                    f"open({str(rec)!r}, 'w', encoding='utf-8'), ensure_ascii=False)\n", encoding='utf-8')
    (root / 'ps' / 'launch.ps1').write_text(
        "param([string]$Label = 'x')\n[IO.File]::WriteAllText('" + str(tmp_path / 'ps-got.txt') + "', $Label)\nexit 0\n")
    env = dict(os.environ, WINQA_ENTRY_TEST_PYTHON=sys.executable)
    done = subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-File', str(root / 'ps' / 'entry.ps1')], input=stdin,
                          env=env, capture_output=True, timeout=120)
    return done, (json.loads(rec.read_text(encoding='utf-8')) if rec.exists() else None)


@pytest.mark.skipif(not PWSH, reason='pwsh required (see README); CI has it')
def test_323_entry_ps1_delivers_hostile_values_verbatim_to_python_and_ps(tmp_path):
    """pwsh stands in for Windows powershell.exe 5.1 here (#325: partial; the 5.1 x DefaultShell check is on the
    Windows acceptance machine)."""
    root = _pwsh_root(tmp_path)
    vals = ['$(whoami)', '%PATH%', '"q"', "'s'", '中文', '', 'a b', '`whoami`']
    req = {'op': 'py', 'args': {'script': 'winqa_real', 'args': vals}, 'has_key': True}
    done, got = _entry(tmp_path, root, (json.dumps(req, ensure_ascii=False) + '\n' + KEY + '\n').encode())
    assert done.returncode == 0, done.stderr[-400:]
    assert got['argv'] == vals and got['stdin'] == KEY + '\n'
    assert KEY.encode() not in done.stdout + done.stderr
    req = {'op': 'ps', 'args': {'script': 'launch', 'params': {'Label': '$(whoami)%PATH%"\''}}, 'has_key': False}
    done, _ = _entry(tmp_path, root, (json.dumps(req) + '\n').encode())
    assert done.returncode == 0, done.stderr[-400:]
    assert (tmp_path / 'ps-got.txt').read_text() == '$(whoami)%PATH%"\''


@pytest.mark.skipif(not PWSH, reason='pwsh required (see README); CI has it')
@pytest.mark.parametrize('stdin', [
    b'',                                                                               # nothing
    b'{"op":"py","args":{"script":"winqa_real","args":[]},"has_k',                    # truncated
    b'not json\n',
    b'{"op":"rm","args":{},"has_key":false}\n',                                       # unknown op
    b'{"op":"py","args":{"script":"winqa_real","args":[]},"has_key":false,"x":1}\n',  # unknown field
    b'{"op":"py","args":{"script":"../evil","args":[]},"has_key":false}\n',           # bad script
    b'{"op":"py","args":{"script":"winqa_real","args":[1]},"has_key":false}\n',       # wrong type
    b'{"op":"py","args":{"script":"winqa_real","args":[]},"has_key":true}\n',         # key line missing
    b'{"op":"ps","args":{"script":"launch","params":{"Evil":"x"}},"has_key":false}\n',  # unknown param
    b'{"op":"ps","args":{"script":"launch","params":{}},"has_key":true}\nK\n',          # key for a ps op
])
def test_323_entry_ps1_rejects_bad_requests_without_running_anything(tmp_path, stdin):
    root = _pwsh_root(tmp_path)
    done, got = _entry(tmp_path, root, stdin)
    assert done.returncode == 64 and b'WINQA_E_REQUEST' in done.stderr, (done.returncode, done.stderr[-300:])
    assert got is None and not (tmp_path / 'ps-got.txt').exists()


# ------------------------------------------------------------------ #326 independent steps.json counterexample

def test_326_bundle_that_does_not_require_steps_json_is_rejected_on_its_own(tmp_path):
    src = tmp_path / 'out'; src.mkdir()
    (src / 'a.json').write_text('{"v": 1}')
    assert _export(tmp_path, src, extra=('--require', 'a.json')).returncode == 0
    good = (tmp_path / 'exp' / 'b1.zip').read_bytes()
    def no_steps(m, members):      # consistent in itself: steps.json neither required nor present
        m['required'] = ['a.json']; members.pop('steps.json')
        m['files'] = [f for f in m['files'] if f['name'] != 'steps.json']
    assert _verify(tmp_path, _rebuild(good, manifest_edit=no_steps)) == 1


# ------------------------------------------------------------------ #355 / #332 gate scope

def test_355_quality_gate_treats_winqa_tests_like_the_backend_suite(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT.parents[1] / 'scripts'))
    import quality_gate as qg
    monkeypatch.setattr(qg, 'checks', lambda g, py: [('winqa_tests', ['true'], qg.ROOT)])

    def fake_run(cmd, **kw):
        if cmd and cmd[0] == 'git':
            return subprocess.CompletedProcess(cmd, 0, '', '')
        junit = next(c.split('=', 1)[1] for c in cmd if c.startswith('--junitxml='))
        Path(junit).write_text('<testsuite><testcase classname="test_winqa_export" name="t"><skipped/></testcase>'
                               '</testsuite>')
        return subprocess.CompletedProcess(cmd, 0)
    monkeypatch.setattr(qg.subprocess, 'run', fake_run)
    monkeypatch.setattr(qg.subprocess, 'check_output', lambda *a, **k: 'abc\n' if 'rev-parse' in a[0] else '')
    report = tmp_path / 'r.json'
    assert qg.run('backend', report, sys.executable) == 1
    entry = json.loads(report.read_text())['checks'][0]
    assert entry['skipped_tests'] == [{'test': 't', 'allowed': False}]
    assert 'test_winqa_scripts' in entry['coverage']['missing_modules']


def test_332_backend_guard_fires_only_for_a_winqa_only_session(tmp_path):
    t = tmp_path / 'scope'
    shutil.copytree(ROOT / 'tests', t / 'scripts' / 'winqa' / 'tests', ignore=shutil.ignore_patterns('test_*.py', '__pycache__'))
    d = t / 'scripts' / 'winqa' / 'tests'
    (d / 'test_a.py').write_text("import sys, types\ndef test_x():\n    sys.modules['backend.fake'] = types.ModuleType('backend.fake')\n")
    other = t / 'other'; other.mkdir()
    (other / 'test_b.py').write_text('def test_y():\n    pass\n')
    run = lambda *paths: subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-o', 'addopts=',
                                         *paths], cwd=t, capture_output=True, text=True)
    alone = run('scripts/winqa/tests')
    assert alone.returncode == 1 and 'imported backend modules' in alone.stderr, alone.stdout[-300:]
    combined = run('scripts/winqa/tests', 'other')
    assert combined.returncode == 0, combined.stdout[-300:] + combined.stderr[-300:]


# ------------------------------------------------------------------ #320 no child process before the key is unset

@pytest.mark.parametrize('bash', BASHES)
def test_320_first_child_process_never_sees_the_key(tmp_path, bash):
    env, args = _env(tmp_path)
    real = shutil.which('dirname')
    _py_bin(tmp_path / 'bin', 'dirname', (
        "import hashlib, os, sys\n"
        "if any(hashlib.sha256(v.encode()).hexdigest() == os.environ['FAKE_KEY_SHA'] for k, v in os.environ.items() if k != 'FAKE_KEY_SHA'):\n"
        "    open(os.environ['FAKE_ENVLEAK'], 'a').write('LEAK dirname env\\n')\n"
        f"os.execv({real!r}, [{real!r}] + sys.argv[1:])\n"))
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=180)
    assert done.returncode == 0, done.stdout[-400:]
    probe = (tmp_path / 'envleak.txt').read_text() if (tmp_path / 'envleak.txt').exists() else ''
    assert 'LEAK' not in probe, probe
