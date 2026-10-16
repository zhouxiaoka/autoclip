"""R27 #414 acceptance (design-retro.md, #414 section): evidence leaves the Windows test machine only as a bundle
built, scrubbed, verified and committed there (scripts/winqa/py/export_evidence.py).

The fake VM is a directory; the fake ssh runs the REAL scripts that sit in the VM's C:\\winqa\\py (copied from the
repo, as step 1 would upload them) with the local Python, and the fake scp really copies. The stub does not know
which implementation is running: older run_winqa.sh versions execute against it unchanged and the assertions decide.
Failures are injected at copy/scrub (VM Python missing), commit (exporter killed before rename), transfer (scp error,
truncated transfer, TERM during scp) and local verification (tampered bundle).

Every case asserts: nothing raw ever reached the control machine (bytes delivered by scp, zip members unpacked, and
every file left under the evidence/tmp/home dirs), the VM originals are byte-for-byte unchanged, and a failure gives a
non-zero exit."""
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from _winqa_helpers import *  # noqa: F401,F403  (ROOT, KEY, LEAKS, fakes, _env, _run, ...)
from _winqa_helpers import _ee, _rebuild, _verify, _export, STEPS_OK, _env, _run, _steps, _manifest, _tree, _vm_fixture, _py_bin, _assert_no_raw_on_control, _save_failure_evidence  # noqa: F401

# ---- acceptance: the happy path exports structured evidence only, withholds the rest, keeps originals ----

@pytest.mark.parametrize('bash', BASHES)
def test_a1_complete_export_brings_back_only_scrubbed_json_and_lists_the_rest_as_withheld(tmp_path, bash):
    done = _run(tmp_path, bash)
    assert done.returncode == 0, done.stdout[-800:]
    ev = tmp_path / 'ev'
    env = json.loads((ev / 'env.json').read_text(encoding='utf-8'))
    assert env['home'] == 'C:\\Users\\<user>' and env['api_token'] == '***' and env['url'] == '<url>'
    assert 'pull_final=ok' in _steps(tmp_path)
    m = _manifest(tmp_path)
    assert m['status'] == 'complete' and m['policy'] == 'winqa-export/1'
    why = {w['name']: w['reason'] for w in m['withheld']}
    # #256 png, #254 zip (member names never leave), #255 raw text/log, #257 mixed BOM/UTF-16, media
    assert why == {'shot.png': 'image', 'app-logs.zip': 'archive', 'real/r.log': 'raw_text_or_binary',
                   'mixed.json': 'encoding', 'media/clip.mp4': 'raw_text_or_binary'}, why
    assert not (ev / 'app-logs.zip').exists() and not (ev / 'shot.png').exists() and not (ev / 'real' / 'r.log').exists()
    # #306: the three things PM's report needs are in the bundle: step results, error codes, withheld list
    steps = json.loads((ev / 'steps.json').read_text())
    assert [(r['step'], r['status'], r['exit_code']) for r in steps] == [('collect_logs', 'ok', 0)], steps
    assert m['required'] == ['collect-logs-final.json', 'steps.json'] and m['missing_required'] == []
    assert m['error_codes'] == {'collect-logs-final.json': ['LLM_TIMEOUT']}


# ---- acceptance: failure injected at every point of the boundary ----

@pytest.mark.parametrize('bash', BASHES)
@pytest.mark.parametrize('mode', ['no-python', 'export-killed', 'scp-fail', 'scp-truncated', 'tampered', 'verify-crash'])
def test_a2_failure_at_any_point_leaves_no_raw_file_keeps_originals_and_exits_non_zero(tmp_path, bash, mode):
    """#251 (VM-side scrub without the exact key), #253 (scp failure swallowed): copy/scrub, commit, transfer,
    truncated transfer and local verification failures all give FAIL + non-zero exit and an untouched $OUT."""
    done = _run(tmp_path, bash, mode)
    if done.returncode == 0 or 'pull_final=FAIL' not in _steps(tmp_path):   # #414: keep evidence of a one-off failure
        ev = _save_failure_evidence(tmp_path, done, mode)
        pytest.fail(f'{mode}: rc={done.returncode} steps={_steps(tmp_path)!r} evidence={ev} '
                    f'stderr={done.stderr[-300:]!r} stdout={done.stdout[-800:]!r}')
    assert not (tmp_path / 'ev' / 'env.json').exists(), mode
    # #311: every failure mode (TERM is a3) leaves no staging dir behind
    assert not list((tmp_path / 'home' / '.cache' / 'autoclip-winqa-stage').glob('winqa-stage.*')), mode
    if mode == 'export-killed':
        exp = tmp_path / 'vm' / 'export'
        assert not list(exp.glob('*.zip')), 'a killed exporter must not leave a committed bundle'



@pytest.mark.parametrize('bash', BASHES)
def test_a2b_log_channel_lost_during_export_is_announced_not_silent(tmp_path, bash):
    """#414 test_a2 flake, deterministic: the live-log channel dies while the exporter runs (the exact signature seen
    once on zhoukaka: output ends at collect_logs, no pull_final receipt, rc 141). The run must still stop non-zero,
    leave nothing raw and no staging dir, AND say on stderr that the log channel was lost (it used to be silent)."""
    env, args = _env(tmp_path, 'export-killed')
    ssh = tmp_path / 'bin' / 'ssh'
    ssh.write_text(ssh.read_text().replace("    if req['op'] == 'py':\n", (
        "    if req['op'] == 'py' and req['args']['script'] == 'export_evidence':\n"
        "        import signal\n"
        "        st = glob.glob(os.environ['TMPDIR'] + '/winqa-lp.*/status')[0]\n"
        "        os.kill(int(open(st).read().split()[1]), signal.SIGKILL)\n"
        "    if req['op'] == 'py':\n"), 1))
    before = _tree(tmp_path / 'vm' / 'out')
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=60)
    assert _tree(tmp_path / 'vm' / 'out') == before
    _assert_no_raw_on_control(tmp_path, done)
    assert done.stdout.rstrip().endswith('-> collect_logs: ok (rc=0)'.encode()), done.stdout[-300:]   # the flake's shape
    assert done.returncode == 141, (done.returncode, done.stderr[-300:])
    assert done.stderr.count(b'WINQA_E_LOGPIPE 70') == 1, done.stderr[-300:]
    assert not list((tmp_path / 'home' / '.cache' / 'autoclip-winqa-stage').glob('winqa-stage.*'))

@pytest.mark.parametrize('bash', BASHES)
def test_a3_term_during_transfer_exits_143_and_leaves_nothing_raw(tmp_path, bash):
    done = _run(tmp_path, bash, 'scp-killed')
    assert done.returncode == 143, done.stdout[-500:]
    assert not list((tmp_path / 'home' / '.cache' / 'autoclip-winqa-stage').glob('winqa-stage.*'))


# ---- acceptance: #252 resume - an old ok never covers a new FAIL ----

@pytest.mark.parametrize('bash', BASHES)
def test_a4_resume_old_ok_never_covers_new_fail(tmp_path, bash):
    first = _run(tmp_path, bash)
    assert first.returncode == 0 and 'pull_final=ok' in _steps(tmp_path), first.stdout[-600:]
    second = _run(tmp_path, bash, 'no-python')
    assert second.returncode != 0, second.stdout[-600:]
    assert 'pull_final=FAIL' in _steps(tmp_path) and 'pull_final=ok' not in _steps(tmp_path), _steps(tmp_path)
    rows = [json.loads(l) for f in sorted((tmp_path / 'ev' / 'runs').glob('*/receipts.jsonl')) for l in f.read_text().splitlines()]
    rows.sort(key=lambda r: r['attempt'])
    final = [r for r in rows if r['step'] == 'pull_final']
    assert [r['status'] for r in final] == ['ok', 'FAIL'] and [r['attempt'] for r in final] == [1, 2]
    assert final[0]['run_id'] != final[1]['run_id']


@pytest.mark.parametrize('bash', BASHES)
def test_a4b_legacy_steps_txt_ok_does_not_hide_a_new_fail(tmp_path, bash):
    (tmp_path / 'ev').mkdir()
    (tmp_path / 'ev' / 'steps.txt').write_text('pull_final=ok\nclean=ok\n')
    done = _run(tmp_path, bash, 'scp-fail')
    assert done.returncode != 0 and 'pull_final=FAIL' in _steps(tmp_path), _steps(tmp_path)


# ---- acceptance: required evidence missing -> FAIL (withheld/dropped is never success) ----

@pytest.mark.parametrize('bash', BASHES)
def test_a5_missing_required_evidence_fails(tmp_path, bash):
    done = _run(tmp_path, bash, required=False)
    assert done.returncode != 0 and 'pull_final=FAIL' in _steps(tmp_path), done.stdout[-600:]
    assert _manifest(tmp_path)['missing_required'] == ['collect-logs-final.json']


@pytest.mark.parametrize('bash', BASHES)
def test_a5b_empty_required_evidence_is_not_evidence(tmp_path, bash):
    """#306: a required file whose content is {} counts as missing."""
    _env(tmp_path)
    (tmp_path / 'vm' / 'out' / 'collect-logs-final.json').write_text('{}')
    done = _run(tmp_path, bash)
    assert done.returncode != 0 and 'pull_final=FAIL' in _steps(tmp_path), done.stdout[-600:]
    m = _manifest(tmp_path)
    assert m['missing_required'] == ['collect-logs-final.json'] and m['contract_problems'] == {'collect-logs-final.json': 'empty'}


@pytest.mark.parametrize('bash', BASHES)
def test_a7_resume_restores_the_required_evidence_of_earlier_steps(tmp_path, bash):
    """#306: step 2 declares clean.json; a later --from-step 8 run must still require it."""
    _env(tmp_path)
    (tmp_path / 'vm' / 'out' / 'clean.json').write_text('{"removed": ["x"]}')
    first = _run(tmp_path, bash, steps=('2', '2'))
    assert first.returncode == 0, first.stdout[-800:]
    assert 'clean.json' in _manifest(tmp_path)['required']
    (tmp_path / 'vm' / 'out' / 'clean.json').unlink()
    second = _run(tmp_path, bash)
    assert second.returncode != 0 and 'pull_final=FAIL' in _steps(tmp_path), second.stdout[-800:]
    assert _manifest(tmp_path)['missing_required'] == ['clean.json']


@pytest.mark.parametrize('bash', BASHES)
def test_a8_key_is_not_in_the_environment_of_ssh_scp_or_the_log_scrubber(tmp_path, bash):
    """#308: after reading the key the script unsets it; the log scrubber gets it over --keys-fd."""
    done = _run(tmp_path, bash)
    assert done.returncode == 0, done.stdout[-600:]
    probe = (tmp_path / 'envleak.txt').read_text() if (tmp_path / 'envleak.txt').exists() else ''
    assert 'LEAK' not in probe, probe
    if sys.platform.startswith('linux'):
        assert 'scanned redact' in probe, 'the probe must have seen the live log scrubber'
    # and the live log still masks the exact key (it did reach the scrubber, over the pipe)
    log = (tmp_path / 'ev' / 'run.log').read_bytes()
    assert KEY.encode() not in log


@pytest.mark.parametrize('bash', BASHES)
@pytest.mark.parametrize('mode', ['cp-fail', 'mkdir-fail'])
def test_a9_local_mkdir_mv_cp_failure_is_a_fail(tmp_path, bash, mode):
    """#309: a local write that fails records FAIL and exits non-zero (was pull_final=ok, exit 0)."""
    done = _run(tmp_path, bash, mode)
    assert done.returncode != 0, (mode, done.stdout[-600:])
    assert 'pull_final=FAIL' in _steps(tmp_path) and 'pull_final=ok' not in _steps(tmp_path), _steps(tmp_path)
    expect = {'cp-fail': '证据落盘失败（cp）', 'mkdir-fail': '建不了 bundles 目录'}[mode]
    assert expect in (tmp_path / 'ev' / 'run.log').read_text(encoding='utf-8'), mode


@pytest.mark.parametrize('bash', BASHES)
def test_a10_required_list_reaches_the_exporter_intact_through_cmd_and_powershell_file(tmp_path, bash):
    """#310: the fake ssh passes arguments like cmd + powershell -File (single quotes stay literal)."""
    done = _run(tmp_path, bash)
    assert done.returncode == 0, done.stdout[-600:]
    assert _manifest(tmp_path)['required'] == ['collect-logs-final.json', 'steps.json']


@pytest.mark.parametrize('bash', BASHES)
def test_a11_log_scrubber_crash_stops_the_run_and_leaves_nothing_raw(tmp_path, bash):
    """#311: the local live-log scrubber is killed -> non-zero exit, staging removed, nothing raw."""
    done = _run(tmp_path, bash, 'redact-crash')
    assert done.returncode == 141, done.returncode          # stopped through the trap, so EXIT cleanup ran
    assert not list((tmp_path / 'home' / '.cache' / 'autoclip-winqa-stage').glob('winqa-stage.*'))
    assert not (tmp_path / 'ev' / 'env.json').exists()


# ---- acceptance: #259 private dirs on the control machine ----

@pytest.mark.parametrize('bash', BASHES)
def test_a6_evidence_and_staging_dirs_are_700(tmp_path, bash):
    done = _run(tmp_path, bash)
    assert done.returncode == 0, done.stdout[-600:]
    assert oct((tmp_path / 'ev').stat().st_mode & 0o777) == '0o700'
    modes = (tmp_path / 'modes.txt').read_text().split()
    assert modes and set(modes) == {'700'}, modes
    root = tmp_path / 'home' / '.cache' / 'autoclip-winqa-stage'
    assert oct(root.stat().st_mode & 0o777) == '0o700'


# ---- exporter unit level: key over stdin only, name policy, originals guard, commit atomicity ----

def test_u1_exact_key_comes_from_stdin_never_argv_and_is_never_printed(tmp_path):
    src = tmp_path / 'out'; src.mkdir()
    (src / 'a.json').write_text(json.dumps({'k': f'x{KEY}y', 'nested': [{'v': KEY}]}))
    done = _export(tmp_path, src)
    assert done.returncode == 0 and KEY.encode() not in done.stdout + done.stderr
    with zipfile.ZipFile(tmp_path / 'exp' / 'b1.zip') as z:
        assert KEY.encode() not in b''.join(z.read(n) for n in z.namelist())
    # R29 #323: the remote exporter is called through the fixed entry; the key only ever goes to a stdin pipe
    sh = (ROOT / 'run_winqa.sh').read_text()
    assert 'rcall_key export_evidence export' in sh and '--keys-stdin' in sh
    for l in sh.splitlines():
        if 'MODEL_API_KEY' in l and not l.lstrip().startswith('#'):
            assert "printf '%s\\n' \"$MODEL_API_KEY\"" in l or l.strip().startswith(('MODEL_API_KEY=', 'export -n', 'unset ', '--real ', '[ -n "$MODEL_API_KEY" ]')), l


def test_u2_names_and_members_follow_the_content_policy(tmp_path):
    src = tmp_path / 'out'; src.mkdir()
    (src / f'{KEY}.json').write_text('{}')
    (src / 'kris dir').mkdir(); (src / 'kris dir' / 'x.json').write_text('{}')
    (src / 'ok.json').write_text('{}')
    done = _export(tmp_path, src)
    assert done.returncode == 0
    with zipfile.ZipFile(tmp_path / 'exp' / 'b1.zip') as z:
        assert sorted(z.namelist()) == ['manifest.json', 'ok.json', 'steps.json']
        m = json.loads(z.read('manifest.json'))
    assert sorted(w['reason'] for w in m['withheld']) == ['name', 'name'] and all(w['name'] is None for w in m['withheld'])


def test_u3_originals_changing_during_export_abort_without_commit(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / 'py'))
    import export_evidence as ee
    src = tmp_path / 'out'; src.mkdir(); (src / 'a.json').write_text('{}')
    real_tree, calls = ee.tree, []

    def tree(p):
        calls.append(1)
        if len(calls) == 2:
            (src / 'a.json').write_text('{"changed": 1}')
        return real_tree(p)
    monkeypatch.setattr(ee, 'tree', tree)
    with pytest.raises(ee.ExportError):
        ee.export(src, tmp_path / 'exp', 'b1', [], [KEY], _steps_file(tmp_path))
    assert not (tmp_path / 'exp').exists() or not list((tmp_path / 'exp').glob('*.zip'))


def _steps_file(tmp_path):
    sf = tmp_path / 'ctl-steps.json'
    sf.write_text(json.dumps(STEPS_OK))
    return sf


def test_u4_verify_rejects_extra_member_bad_hash_and_unscrubbed_content(tmp_path):
    src = tmp_path / 'out'; src.mkdir(); (src / 'a.json').write_text('{"v": 1}')
    done = _export(tmp_path, src, extra=('--require', 'a.json'))
    assert done.returncode == 0, done.stderr
    digest = done.stdout.decode().split()[-1]
    good = (tmp_path / 'exp' / 'b1.zip').read_bytes()
    assert _verify(tmp_path, good, digest) == 0
    assert _verify(tmp_path, good, 'f' * 64) == 1
    assert _verify(tmp_path, _rebuild(good)) == 0, 'the rebuild itself must be a valid bundle'
    # an extra member not in the manifest
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(good)) as zi, zipfile.ZipFile(buf, 'w') as zo:
        for n in zi.namelist():
            zo.writestr(n, zi.read(n))
        zo.writestr('extra.json', b'{"x": 1}')
    assert _verify(tmp_path, buf.getvalue()) == 1
    # #311: unscrubbed content with CONSISTENT hashes - only the content check (check_clean) can catch it
    assert _verify(tmp_path, _rebuild(good, {'a.json': json.dumps({'v': KEY}).encode()})) == 1
    assert _verify(tmp_path, _rebuild(good, {'a.json': json.dumps({'api_token': 'VISIBLE'}).encode()})) == 1
    assert not (tmp_path / 'x').exists()


def test_u5_credential_values_are_masked_whole_however_long_and_whatever_they_start_with(tmp_path):
    """#303 P1: the 4096-character cap and the '***' prefix skip let the tail of a credential through."""
    ee = _ee()
    import redact
    cookie = 'Cookie: padding=' + 'a' * 4100 + '; sid=WHOLE_SESSION_COOKIE'
    assert 'WHOLE_SESSION_COOKIE' not in redact.scrub(cookie)
    assert 'VISIBLEPRIVATE' not in redact.scrub('token=***VISIBLEPRIVATE')
    assert 'VISIBLEPRIVATE' not in redact.scrub('api_key: ***VISIBLEPRIVATE')
    assert 'PRIVTAIL' not in redact.scrub('credentials={"a":"}","b":"PRIVTAIL"} after')
    assert redact.scrub('token=*** rest') == 'token=*** rest'          # a value that IS the mark stays a fixed point
    import time
    t0 = time.perf_counter()                                           # no cap must not mean quadratic
    assert redact.scrub('token=' * 8000) == 'token=***'
    assert time.perf_counter() - t0 < 2.0
    src = tmp_path / 'out'; src.mkdir()
    (src / 'h.json').write_text(json.dumps({'note': cookie, 'log': 'token=***VISIBLEPRIVATE',
                                            'raw': 'credentials={"a":"}","b":"PRIVTAIL"}'}))
    done = _export(tmp_path, src, extra=('--require', 'h.json'))
    assert done.returncode == 0, done.stderr
    with zipfile.ZipFile(tmp_path / 'exp' / 'b1.zip') as z:
        blob = b''.join(z.read(n) for n in z.namelist())
    for leak in (b'WHOLE_SESSION_COOKIE', b'VISIBLEPRIVATE', b'PRIVTAIL'):
        assert leak not in blob, leak
    assert ee.SCHEMA


def test_u6_written_part_is_reopened_and_rechecked_before_the_rename(tmp_path, monkeypatch):
    """#304: what is on disk is checked, not the in-memory object. Fault injection: the key lands in the .part
    between writing and committing; the export must abort with no .zip and no .part left."""
    ee = _ee()
    src = tmp_path / 'out'; src.mkdir(); (src / 'a.json').write_text('{"v": 1}')
    real_fsync = os.fsync

    def fsync(fd):
        real_fsync(fd)
        part = next((tmp_path / 'exp').glob('*.part'))
        data = part.read_bytes()
        with zipfile.ZipFile(io.BytesIO(data)) as zi:
            members = {n: zi.read(n) for n in zi.namelist()}
        members['a.json'] = json.dumps({'v': KEY}).encode()
        m = json.loads(members['manifest.json'])
        for f in m['files']:
            f['sha256'] = hashlib.sha256(members[f['name']]).hexdigest()
        members['manifest.json'] = json.dumps(m).encode()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zo:
            for n, d in members.items():
                zo.writestr(n, d)
        os.pwrite(fd, buf.getvalue(), 0); os.ftruncate(fd, len(buf.getvalue()))
    monkeypatch.setattr(ee.os, 'fsync', fsync)
    with pytest.raises(ee.ExportError):
        ee.export(src, tmp_path / 'exp', 'b1', ['a.json'], [KEY], _steps_file(tmp_path))
    assert not list((tmp_path / 'exp').glob('*.zip')) and not list((tmp_path / 'exp').glob('*.part'))


def test_u7_evidence_contract_steps_error_codes_and_empty_files(tmp_path):
    """#306: steps.json is always required and must be well formed; {} is not evidence; error codes are listed."""
    src = tmp_path / 'out'; src.mkdir()
    (src / 'failure.json').write_text(json.dumps({'analysis': {'error_code': 'AUTH_FAILED'}, 'jobs': [{'error_code': 'E2'}]}))
    (src / 'empty.json').write_text('{}')
    done = _export(tmp_path, src, extra=('--require', 'failure.json,empty.json'))
    assert done.returncode == 3, done.stdout
    with zipfile.ZipFile(tmp_path / 'exp' / 'b1.zip') as z:
        m = json.loads(z.read('manifest.json'))
    assert m['status'] == 'incomplete' and m['missing_required'] == ['empty.json']
    assert m['contract_problems'] == {'empty.json': 'empty'}
    assert m['error_codes'] == {'empty.json': [], 'failure.json': ['AUTH_FAILED', 'E2']}
    assert 'steps.json' in m['required']
    for bad_steps in ([], [{'run_id': 'r1', 'step': 'x', 'attempt': 1, 'status': 'ok'}],
                      [{'run_id': 'r1', 'step': 'x', 'attempt': 1, 'status': 'maybe', 'exit_code': 0}]):
        shutil.rmtree(tmp_path / 'exp')
        (src / 'empty.json').unlink(missing_ok=True)
        done = _export(tmp_path, src, steps=bad_steps)
        assert done.returncode == 3, bad_steps
        with zipfile.ZipFile(tmp_path / 'exp' / 'b1.zip') as z:
            assert json.loads(z.read('manifest.json'))['missing_required'] == ['steps.json'], bad_steps
    # a steps.json inside C:\winqa\out is not the control machine's record: withheld as reserved
    shutil.rmtree(tmp_path / 'exp')
    (src / 'steps.json').write_text(json.dumps(STEPS_OK))
    done = _export(tmp_path, src)
    with zipfile.ZipFile(tmp_path / 'exp' / 'b1.zip') as z:
        m = json.loads(z.read('manifest.json'))
    assert {'name': 'steps.json', 'reason': 'reserved'}.items() <= next(w for w in m['withheld'] if w['name'] == 'steps.json').items()


def test_u8_verify_recomputes_required_missing_status_and_classification(tmp_path):
    """#307: a hash-consistent bundle that claims complete while missing required evidence, or carries a JSON
    member named like an image, is rejected on the control machine."""
    src = tmp_path / 'out'; src.mkdir(); (src / 'a.json').write_text('{"v": 1}')
    _export(tmp_path, src, extra=('--require', 'a.json'))
    good = (tmp_path / 'exp' / 'b1.zip').read_bytes()

    def drop_required(m, members):
        members.pop('a.json'); m['files'] = [f for f in m['files'] if f['name'] != 'a.json']
        m['error_codes'].pop('a.json')
    assert _verify(tmp_path, _rebuild(good, manifest_edit=drop_required)) == 1      # still says complete

    def add_required(m, members):
        m['required'] = sorted(m['required'] + ['b.json'])
    assert _verify(tmp_path, _rebuild(good, manifest_edit=add_required)) == 1       # b.json missing, says complete

    def empty_required(m, members):
        members['a.json'] = b'{}'
        m['error_codes']['a.json'] = []
    assert _verify(tmp_path, _rebuild(good, manifest_edit=empty_required)) == 1     # {} is not evidence

    def wrong_codes(m, members):
        m['error_codes']['a.json'] = ['MADE_UP']
    assert _verify(tmp_path, _rebuild(good, manifest_edit=wrong_codes)) == 1
    assert _verify(tmp_path, _rebuild(good, add=[('shot.png', b'{"v": 2}')])) == 1  # JSON member named .png


def test_u9_bash32_reads_rc_before_fullwidth_paren():
    """#305: "$rc）" is one variable name in Bash 3.2 under UTF-8; every expansion before a non-ASCII byte is braced."""
    import re
    for sh in ('run_winqa.sh', 'pull_run_installer.sh'):
        text = (ROOT / sh).read_text(encoding='utf-8')
        code = '\n'.join(l.split(' #', 1)[0] for l in text.splitlines())
        assert not re.findall(r'\$[A-Za-z_][A-Za-z0-9_]*[^\x00-\x7f]', code), sh


def test_u10_every_step_declares_the_evidence_it_produces():
    """#306 / R29 #318: the required evidence comes from ONE static table (py/winqa_plan.py), not from require()
    calls in the shell; every producer's JSON is in it (whisper-hfmirror only as optional: it exists only after a
    failed first try)."""
    sys.path.insert(0, str(ROOT / 'py'))
    import winqa_plan
    produced = {f for rows in winqa_plan.TABLE.values() for _, prod, _, _ in rows for f in prod}
    optional = {f for rows in winqa_plan.TABLE.values() for _, _, _, opt in rows for f in opt}
    for f in ('stop-candidate.json', 'smoke.json', 'windows-smoke.json', 'windows-smoke-desktop.json',
              'windows-sensevoice-installed.json', 'windows-whisper-installed.json', 'real/model.json',
              'real/whisper.json', 'real/local.json', 'real/link.json', 'real/final.json',
              'collect-logs-final.json', 'failure.json', 'check-candidate.json', 'clean.json', 'env.json'):
        assert f in produced, f
    assert optional == {'real/whisper-hfmirror.json'}
    assert 'require ' not in (ROOT / 'run_winqa.sh').read_text(encoding='utf-8').replace('--require', '')
