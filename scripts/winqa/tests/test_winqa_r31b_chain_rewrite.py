"""#414 R31 commit B: one verdict, log_channel as a required step, $SECONDS deadlines, result judges, bundle checks.
Every passing verdict here comes from winqa_chain.verify_chain on a run written through winqa_plan (M6)."""
import json
import re
import subprocess
import sys
import zipfile

import pytest

from _winqa_helpers import *  # noqa: F401,F403
from _winqa_helpers import INPUTS, _wpwc, classify_a2, default_result, make_run
from test_winqa_r31_redact import BASHES, _fake_logpipe, _verdict

PLAN_CLI = ROOT / 'py' / 'winqa_plan.py'
VERDICT_CLI = ROOT / 'py' / 'winqa_verdict.py'


# ------------------------------------------------------------------ I438 / Dong point 3: log_channel is required
def test_i438_run_without_log_channel_receipt_is_not_pass(tmp_path):
    _, wc = _wpwc()
    make_run(tmp_path / 'ev', log_channel=None)
    r = wc.verify_chain(tmp_path / 'ev', 'r1', 'final')
    assert not r.passed and any('log_channel' in x for x in r.reasons), r.reasons


def test_i438_log_channel_fail_fails_the_verdict_and_the_cli_exits_70(tmp_path):
    _, wc = _wpwc()
    make_run(tmp_path / 'ev', log_channel='FAIL')
    r = wc.verify_chain(tmp_path / 'ev', 'r1', 'final')
    assert r.overall == 'fail' and r.steps['log_channel'] == 'FAIL'
    dest = tmp_path / 'v.json'
    cmd = [sys.executable, str(VERDICT_CLI), 'final', '--out', str(tmp_path / 'ev'), '--run-id', 'r1', '--dest', str(dest)]
    assert subprocess.run(cmd, capture_output=True).returncode == 70
    first = dest.read_bytes(), (tmp_path / 'ev' / 'steps.txt').read_bytes()
    assert b'log_channel=FAIL' in first[1]
    assert subprocess.run(cmd, capture_output=True).returncode == 70        # rerunning the verdict: same bytes
    assert (dest.read_bytes(), (tmp_path / 'ev' / 'steps.txt').read_bytes()) == first


def test_dong3_old_plan_without_log_channel_is_unknown_never_pass(tmp_path, monkeypatch):
    wp, wc = _wpwc()
    old = {k: [r for r in v if r[0] != 'log_channel'] for k, v in wp.TABLE.items()}
    monkeypatch.setattr(wp, 'TABLE', old)                       # a plan made by the pre-R31 table (own hash)
    make_run(tmp_path / 'ev', log_channel=None)
    monkeypatch.undo()
    r = wc.verify_chain(tmp_path / 'ev', 'r1', 'final')
    assert not r.passed and r.steps.get('log_channel') == 'unknown', (r.overall, r.steps)
    assert any('before R31' in x for x in r.reasons)


# ------------------------------------------------------------------ I473: only ok / FAIL
def test_i473_record_refuses_any_other_status(tmp_path):
    wp, _ = _wpwc()
    wp.create(tmp_path / 'ev', 'r1', 8, 8, set(), dict(INPUTS))
    done = subprocess.run([sys.executable, str(PLAN_CLI), 'record', '--out', str(tmp_path / 'ev'), '--run-id', 'r1',
                           '--step', 'collect_logs', '--status', 'PASS', '--exit-code', '0'], capture_output=True)
    assert done.returncode == 72 and wp.receipts(tmp_path / 'ev', 'r1') == []


@pytest.mark.parametrize('status', ['skipped', 'PASS', 'passed', 'ok ', ''])
def test_i473_step_results_treat_unknown_status_as_fail(status):
    _, wc = _wpwc()
    rows = [{'seq': 1, 'step': 'collect_logs', 'status': status, 'exit_code': 0, 'exit_code_source': 'measured'}]
    assert wc.step_results({}, rows, set()) == {'collect_logs': 'FAIL'}


def test_i473_reason_is_validated(tmp_path):
    wp, _ = _wpwc()
    wp.create(tmp_path / 'ev', 'r1', 8, 8, set(), dict(INPUTS))
    with pytest.raises(ValueError):
        wp.record(tmp_path / 'ev', 'r1', 'log_channel', 'FAIL', 70, reason='x y\n')
    assert wp.record(tmp_path / 'ev', 'r1', 'log_channel', 'FAIL', 70, reason='killed=SIG9')['reason'] == 'killed=SIG9'


# ------------------------------------------------------------------ I435: every result file judged
def test_i435_smoke_run_with_nonzero_exit_fails(tmp_path):
    _, wc = _wpwc()
    wp, _ = _wpwc()
    plan_files = None
    make_run(tmp_path / 'ev', frm=7, to=8, flags=('smoke',),
             receipts=(('smoke', 'ok'), ('collect_logs', 'ok')),
             files={**{f: default_result(f) for f in ('collect-logs-final.json', 'windows-smoke.json',
                                                         'windows-smoke-desktop.json')},
                    'smoke.json': b'{"runs": [{"name": "a", "exit_code": 0}, {"name": "b", "exit_code": 2}]}'})
    r = wc.verify_chain(tmp_path / 'ev', 'r1', 'final')
    assert r.steps.get('smoke') == 'FAIL', (r.steps, r.reasons)


def test_i435_desktop_smoke_ok_false_fails(tmp_path):
    _, wc = _wpwc()
    make_run(tmp_path / 'ev', frm=7, to=8, flags=('smoke',), receipts=(('smoke', 'ok'), ('collect_logs', 'ok')),
             files={**{f: default_result(f) for f in ('collect-logs-final.json', 'windows-smoke.json', 'smoke.json')},
                    'windows-smoke-desktop.json': b'{"ok": false}'})
    r = wc.verify_chain(tmp_path / 'ev', 'r1', 'final')
    assert r.steps.get('smoke') == 'FAIL', (r.steps, r.reasons)


def test_i435_collect_logs_without_ok_fails(tmp_path):
    _, wc = _wpwc()
    make_run(tmp_path / 'ev', files={'collect-logs-final.json': b'{"zip": "x"}'})
    r = wc.verify_chain(tmp_path / 'ev', 'r1', 'final')
    assert r.steps.get('collect_logs') == 'FAIL', (r.steps, r.reasons)


# ------------------------------------------------------------------ I436: the bundle really is that ZIP
def test_i436_record_rejects_a_non_zip_bundle(tmp_path):
    wp, _ = _wpwc()
    wp.create(tmp_path / 'ev', 'r1', 8, 8, set(), dict(INPUTS))
    (tmp_path / 'x').mkdir(); (tmp_path / 'x' / 'manifest.json').write_text('{}')
    (tmp_path / 'b.zip').write_bytes(b'not a zip')
    with pytest.raises(ValueError):
        wp.record(tmp_path / 'ev', 'r1', 'pull_final', 'ok', 0, bundle_zip=tmp_path / 'b.zip', bundle_dir=tmp_path / 'x')
    assert wp.receipts(tmp_path / 'ev', 'r1') == []


def test_i436_record_rejects_zip_differing_from_dir(tmp_path):
    wp, _ = _wpwc()
    wp.create(tmp_path / 'ev', 'r1', 8, 8, set(), dict(INPUTS))
    (tmp_path / 'x').mkdir(); (tmp_path / 'x' / 'manifest.json').write_text('{}')
    (tmp_path / 'x' / 'a.json').write_text('{"ok": true}')
    with zipfile.ZipFile(tmp_path / 'b.zip', 'w') as z:
        z.writestr('manifest.json', '{}'); z.writestr('a.json', '{"ok": false}')
    with pytest.raises(ValueError):
        wp.record(tmp_path / 'ev', 'r1', 'pull_final', 'ok', 0, bundle_zip=tmp_path / 'b.zip', bundle_dir=tmp_path / 'x')


def test_i436_verify_rejects_a_kept_zip_changed_after_the_receipt(tmp_path):
    _, wc = _wpwc()
    make_run(tmp_path / 'ev')
    z = next((tmp_path / 'ev' / 'bundles').glob('*.zip'))
    z.write_bytes(b'PK\x05\x06' + b'\0' * 18)
    assert wc.verify_chain(tmp_path / 'ev', 'r1', 'final').overall == 'rejected'


# ------------------------------------------------------------------ Dong point 4 / I433: $SECONDS, no date fork
def test_dong4_deadlines_use_seconds_and_never_fork_date_in_a_loop():
    sh = (ROOT / 'run_winqa.sh').read_text()
    assert 'SECONDS' in sh
    for m in re.finditer(r'\bwhile\b(.*?)\bdone\b', sh, re.S):
        assert not re.search(r'(\$\(|`|^\s*)date\b', m.group(0), re.M), m.group(0)[:200]


# ------------------------------------------------------------------ shell: drain / handshake / wrapper_gone
SLOW_DRAIN = ("    import runpy, time\n    sys.argv = a[1:]\n    code = 0\n    try:\n"
              "        runpy.run_path(a[1], run_name='__main__')\n    except SystemExit as e:\n"
              "        code = e.code or 0\n    time.sleep({s})\n    sys.exit(code)")


@pytest.mark.parametrize('bash', BASHES)
def test_i433_drain_inside_the_bound_passes(tmp_path, bash):
    env, args = _env(tmp_path)
    _fake_logpipe(tmp_path, SLOW_DRAIN.format(s=0.5))
    env['WINQA_LOGPIPE_DRAIN_S'] = '6'
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=120)
    assert done.returncode == 0, (done.returncode, done.stderr[-300:])
    assert _wpwc()[1].is_pass(_verdict(tmp_path))


@pytest.mark.parametrize('bash', BASHES)
def test_i433_drain_past_the_bound_is_drain_timeout_and_fail(tmp_path, bash):
    env, args = _env(tmp_path)
    _fake_logpipe(tmp_path, SLOW_DRAIN.format(s=8))
    env['WINQA_LOGPIPE_DRAIN_S'] = '2'
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=120)
    assert done.returncode == 70, (done.returncode, done.stderr[-300:])
    v = _verdict(tmp_path)
    assert v is not None and v['steps'].get('log_channel') == 'FAIL' and not _wpwc()[1].is_pass(v)
    assert 'log_channel=FAIL' in (tmp_path / 'ev' / 'steps.txt').read_text()
    assert 'reason drain_timeout' in (tmp_path / 'ev' / 'logpipe-final.txt').read_text()


@pytest.mark.parametrize('bash', BASHES)
def test_i474_handshake_timeout_leaves_a_close_record(tmp_path, bash):
    env, args = _env(tmp_path)
    _fake_logpipe(tmp_path, '    import time; time.sleep(5)')
    env['WINQA_LOGPIPE_HANDSHAKE_S'] = '1'
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=60)
    assert done.returncode == 70
    final = (tmp_path / 'ev' / 'logpipe-final.txt').read_text()
    assert 'reason handshake_timeout' in final
    assert classify_a2(70, final).startswith('logpipe_no_handshake')


@pytest.mark.parametrize('bash', BASHES)
def test_i434_wrapper_gone_is_named_and_fails(tmp_path, bash):
    env, args = _env(tmp_path)
    _fake_logpipe(tmp_path, ("    import runpy, signal\n    sys.argv = a[1:]\n    try:\n"
                             "        runpy.run_path(a[1], run_name='__main__')\n    except SystemExit:\n        pass\n"
                             "    os.kill(os.getppid(), signal.SIGKILL)\n    sys.exit(0)"))
    env['WINQA_LOGPIPE_DRAIN_S'] = '2'
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=120)
    assert done.returncode == 70, (done.returncode, done.stderr[-300:])
    final = (tmp_path / 'ev' / 'logpipe-final.txt').read_text()
    assert re.search(r'reason (wrapper_gone|exited|killed)', final), final


@pytest.mark.parametrize('bash', BASHES)
def test_i471_early_exit_after_handshake_leaves_a_close_record(tmp_path, bash):
    """an exit the script makes on its own (73 here: tampered receipts before step 8) still writes logpipe-final"""
    env, args = _env(tmp_path)
    ev = tmp_path / 'ev'
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=120)
    assert done.returncode == 0
    (ev / 'logpipe-final.txt').unlink()
    env2, args2 = _env(tmp_path)
    args2[args2.index('--candidate') + 1] = str(tmp_path / 'other.exe')
    (tmp_path / 'other.exe').write_bytes(b'MZ2')
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args2, env=env2, capture_output=True, timeout=120)
    assert done.returncode != 0
    if (ev / 'logpipe-final.txt').exists():
        assert 'script_rc_before_close' in (ev / 'logpipe-final.txt').read_text()


def test_i471_no_verdict_shaped_json_under_tests():
    for p in (ROOT / 'tests').rglob('*.json'):
        t = p.read_text(errors='replace')
        assert not ('"overall"' in t and '"binding"' in t), p


# ------------------------------------------------------------------ M2: a UTF-8 line carrying NUL is the marker only
def test_m2_utf8_line_with_nul_is_only_the_marker():
    sys.path.insert(0, str(ROOT))
    import redact
    out = []
    s = redact.Stream([KEY], out.append)
    s.feed(b'first line\nab\x00cd tail\nlast\n'); s.close()
    assert b''.join(out) == b'first line\n[REDACTED:encoding]\nlast\n', b''.join(out)


# ------------------------------------------------------------------ I434: a producer receipt no export binds
def test_i434_ok_producer_receipt_after_the_last_export_fails(tmp_path):
    wp, wc = _wpwc()
    make_run(tmp_path / 'ev', log_channel=None)
    wp.record(tmp_path / 'ev', 'r1', 'collect_logs', 'ok', 0)            # its output is in no bundle after it
    wp.record(tmp_path / 'ev', 'r1', 'log_channel', 'ok', 0)
    r = wc.verify_chain(tmp_path / 'ev', 'r1', 'final')
    assert not r.passed and r.steps.get('collect_logs') == 'FAIL', (r.steps, r.reasons)


# ------------------------------------------------------------------ M8-b: inherited bundles are re-checked
def test_m8b_inherited_run_whose_bundle_changed_is_rerun_not_trusted(tmp_path):
    _, wc = _wpwc()
    make_run(tmp_path / 'ev', 'r0')
    make_run(tmp_path / 'ev', 'r1')
    assert wc.verify_chain(tmp_path / 'ev', 'r1', 'final').passed      # reference: same runs, nothing changed
    z = next((tmp_path / 'ev' / 'bundles').glob('r0-*.zip'))
    z.write_bytes(z.read_bytes() + b'x')
    r = wc.verify_chain(tmp_path / 'ev', 'r1', 'final')
    assert not r.passed and any('inherited run r0' in x for x in r.reasons), r.reasons


# ------------------------------------------------------------------ I437: legacy required file needs a producer
def test_i437_legacy_required_clean_json_without_a_measured_clean_receipt_is_incomplete(tmp_path):
    wp, wc = _wpwc()
    ev = tmp_path / 'ev'; ev.mkdir()
    (ev / 'required.txt').write_text('clean.json\n')
    wp.migrate(ev)
    plan = make_run(ev, 'r1', files=None)
    assert 'clean.json' in plan['required']
    r = wc.verify_chain(ev, 'r1', 'final')
    assert not r.passed and any('required clean.json' in x for x in r.reasons), (r.overall, r.reasons)


# ------------------------------------------------------------------ D5: a step never starts on a dead channel
@pytest.mark.parametrize('bash', BASHES)
def test_d5_channel_dead_before_a_step_stops_the_run_with_70(tmp_path, bash):
    env, args = _env(tmp_path, steps=('0', '8'))
    _fake_logpipe(tmp_path, (
        "    import subprocess\n"
        "    child = subprocess.Popen([os.environ['FAKE_REAL_PY']] + a, stdin=subprocess.PIPE, pass_fds=(6,))\n"
        "    for line in sys.stdin.buffer:\n"
        "        child.stdin.write(line); child.stdin.flush()\n"
        "        if b'====' in line:\n"
        "            child.stdin.close(); child.wait(); sys.exit(0)\n"
        "    sys.exit(0)"))
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=120)
    assert done.returncode == 70, (done.returncode, done.stderr[-300:])
    cmds = (tmp_path / 'cmds.txt').read_text() if (tmp_path / 'cmds.txt').exists() else ''
    assert 'clean' not in cmds, cmds[-500:]
