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

ROOT = Path(__file__).resolve().parents[2] / 'scripts' / 'winqa'
EXPORTER = ROOT / 'py' / 'export_evidence.py'
UTF8 = 'en_US.UTF-8' if sys.platform == 'darwin' else 'C.UTF-8'
BASHES = ['bash'] + ([os.environ['WINQA_TEST_BASH32']] if os.environ.get('WINQA_TEST_BASH32') else []) \
    + (['/bin/bash'] if sys.platform == 'darwin' else [])
pytestmark = pytest.mark.skipif(sys.platform == 'win32', reason='bash harness')

KEY = 'QAzz9Kx7nonstd42'            # non-generic key shape: no sk-/Bearer prefix, only the exact key can catch it
LEAKS = (KEY.encode(), b'kris', b'SIG1', b'TOKVAL', (KEY[:3] + '\u2026' + KEY[-3:]).encode())

FAKE_SSH = r'''
import glob, os, re, shlex, subprocess, sys
VM, MODE = os.environ['FAKE_VM'], os.environ.get('FAKE_MODE', '')
a = sys.argv[1:]; i = 0
while i < len(a) and a[i].startswith('-'):
    i += 2 if a[i] in ('-i', '-o') else 1
cmd = ' '.join(a[i + 1:])
def tr(p):
    q = p.replace('\\', '/')
    return VM + '/' + q[9:] if q.lower().startswith('c:/winqa/') else q
if 'hostname' in cmd:
    print('vm'); sys.exit(0)
if 'Copy-Item' in cmd and 'out-scrubbed' in cmd:
    import shutil; shutil.rmtree(VM + '/out-scrubbed', ignore_errors=True); shutil.copytree(VM + '/out', VM + '/out-scrubbed'); sys.exit(0)
if 'Remove-Item' in cmd and 'media' in cmd:
    import shutil
    for d in ('out/media', 'out/real/media'):
        shutil.rmtree(VM + '/' + d, ignore_errors=True)
    sys.exit(0)
def _leak_probe():
    # R27 #308: neither this ssh nor the local log scrubber may hold the key in its environment
    import hashlib
    want, out = os.environ.get('FAKE_KEY_SHA'), os.environ.get('FAKE_ENVLEAK')
    if not want or not out:
        return
    hit = lambda vals: any(hashlib.sha256(v).hexdigest() == want for v in vals)
    lines = []
    if hit([v.encode() for v in os.environ.values()]):
        lines.append('LEAK ssh env')
    for d in glob.glob('/proc/[0-9]*'):
        try:
            if b'redact.py' not in open(d + '/cmdline', 'rb').read():
                continue
            vals = [e.split(b'=', 1)[-1] for e in open(d + '/environ', 'rb').read().split(b'\0')]
        except OSError:
            continue
        lines.append('scanned redact')
        if hit(vals):
            lines.append('LEAK redact env')
    with open(out, 'a') as fh:
        fh.write(''.join(l + '\n' for l in lines))
_leak_probe()
m = re.search(r'runpy\.ps1\s+(\S+)(.*)$', cmd)
if m:
    if MODE == 'no-python':
        sys.exit(1)
    script = tr(m.group(1))
    # cmd.exe + powershell -File: single quotes are NOT removed (#310); split on blanks like Windows argv does
    rest = [tr(t) for t in m.group(2).replace('\\', '/').split()]
    env = dict(os.environ, WINQA_OUT=VM + '/out')
    if MODE == 'export-killed' and script.endswith('export_evidence.py'):
        code = ("import os, runpy, sys; os.replace = lambda *a: os._exit(137); sys.argv = sys.argv[1:]; "
                "runpy.run_path(sys.argv[0], run_name='__main__')")
        sys.exit(subprocess.run([sys.executable, '-c', code, script] + rest, env=env).returncode)
    sys.exit(subprocess.run([sys.executable, script] + rest, env=env).returncode)
print('remote: C:\\Users\\kris\\Desktop ok')
sys.exit(0)
'''

FAKE_SCP = r'''
import glob, io, os, shutil, signal, sys, zipfile
VM, MODE, LOG, MODES = os.environ['FAKE_VM'], os.environ.get('FAKE_MODE', ''), os.environ['FAKE_DELIVERED'], os.environ['FAKE_MODES']
a = sys.argv[1:]; i = 0; pos = []
while i < len(a):
    if a[i] in ('-i', '-o'):
        i += 2; continue
    if a[i].startswith('-'):
        i += 1; continue
    pos.append(a[i]); i += 1
*srcs, dst = pos
import hashlib
if os.environ.get('FAKE_KEY_SHA') and any(hashlib.sha256(v.encode()).hexdigest() == os.environ['FAKE_KEY_SHA'] for v in os.environ.values()):
    open(os.environ['FAKE_ENVLEAK'], 'a').write('LEAK scp env\n')
def tr(p):
    q = p.split(':', 1)[1] if '@' in p.split(':', 1)[0] else p
    q = q.replace('\\', '/')
    return VM + '/' + q[9:] if q.lower().startswith('c:/winqa/') else q
def log(path):
    with open(LOG, 'ab') as fh:
        for root, _, files in (os.walk(path) if os.path.isdir(path) else [(os.path.dirname(path), [], [os.path.basename(path)])]):
            for f in files:
                p = os.path.join(root, f); data = open(p, 'rb').read()
                fh.write(p.encode() + b'\n' + data + b'\n')
                try:
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        for n in z.namelist():
                            fh.write(n.encode() + b'\n' + z.read(n) + b'\n')
                except zipfile.BadZipFile:
                    pass
if '@' in dst.split(':', 1)[0]:                      # upload to the VM
    for s in srcs:
        t = tr(dst); os.makedirs(t, exist_ok=True); shutil.copy(s, t)
    sys.exit(0)
with open(MODES, 'a') as fh:
    d = dst if dst.endswith('/') or os.path.isdir(dst) else os.path.dirname(dst)
    fh.write(oct(os.stat(d).st_mode & 0o777)[2:] + '\n')
if MODE == 'scp-fail':
    sys.exit(1)
for s in srcs:
    for f in glob.glob(tr(s)):
        t = os.path.join(dst, os.path.basename(f)) if os.path.isdir(dst) else dst
        if os.path.isdir(f):
            shutil.copytree(f, t, dirs_exist_ok=True)
        else:
            data = open(f, 'rb').read()
            if MODE == 'scp-truncated':
                data = data[: len(data) // 2]
            if MODE == 'tampered' and f.endswith('.zip'):
                data = data.replace(b'manifest.json', b'manifest.jsoN')
            open(t, 'wb').write(data)
        log(t)
if MODE == 'scp-killed':
    os.kill(os.getppid(), signal.SIGTERM)
sys.exit(0)
'''


def _py_bin(folder, name, body):
    p = folder / name
    p.write_text(f'#!{sys.executable}\n' + body)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)


FAKE_PY = r'''
import os, signal, sys
mode, a = os.environ.get('FAKE_MODE', ''), sys.argv[1:]
if mode == 'verify-crash' and 'verify' in a:
    os.kill(os.getpid(), signal.SIGKILL)
if mode == 'redact-crash' and '--lines' in a:
    # the real scrubber runs until the run reaches step 8 (staging dir exists by then), then the scrubber dies
    import subprocess
    child = subprocess.Popen([os.environ['FAKE_REAL_PY']] + a, stdin=subprocess.PIPE, pass_fds=(3,))
    for line in sys.stdin.buffer:
        if '8. '.encode() in line and b'====' in line:
            child.kill(); os.kill(os.getpid(), signal.SIGKILL)
        child.stdin.write(line); child.stdin.flush()
    sys.exit(0)
os.execv(os.environ['FAKE_REAL_PY'], [os.environ['FAKE_REAL_PY']] + a)
'''


def _vm_fixture(vm, required=True):
    out = vm / 'out'
    (out / 'real').mkdir(parents=True)
    (out / 'media').mkdir()
    env = {'home': 'C:\\Users\\kris', 'note': f'model said {KEY} back', 'url': 'https://h.invalid/q?sig=SIG1',
           'api_token': 'TOKVAL', 'masked': KEY[:3] + '\u2026' + KEY[-3:]}
    (out / 'env.json').write_bytes(b'\xef\xbb\xbf' + json.dumps(env, ensure_ascii=False).encode())   # PS 5.1 BOM
    if required:
        (out / 'collect-logs-final.json').write_text('{"ok": true, "zip": "C:\\\\winqa\\\\out\\\\app-logs.zip", '
                                                     '"jobs": [{"error_code": "LLM_TIMEOUT"}, {"error_code": null}]}')
    (out / 'real' / 'r.log').write_text(f'err /Users/kris/x token=TOKVAL {KEY}\n')
    (out / 'shot.png').write_bytes(b'\x89PNG\r\n\x1a\n' + f'{KEY} kris'.encode())
    (out / 'mixed.json').write_bytes(b'\xef\xbb\xbf{"a": "x"}' + f'{KEY} kris'.encode('utf-16-le'))
    (out / 'media' / 'clip.mp4').write_bytes(b'\x00\x00\x00 ftyp kris')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr(f'backend/{KEY}-kris.log', 'boot ok\n')
        z.writestr('backend/app.log', f'boot C:\\Users\\kris\\AppData {KEY}\n')
    (out / 'app-logs.zip').write_bytes(buf.getvalue())
    # step 1 uploads the repo's scripts; the fake VM gets the same files
    (vm / 'py').mkdir()
    for f in list((ROOT / 'py').glob('*.py')) + [ROOT / 'redact.py']:
        shutil.copy(f, vm / 'py')


def _tree(folder):
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob('*')) if p.is_file()}


def _env(tmp_path, mode='', key=KEY, required=True, steps=('8', '8')):
    vm, bins, home, tmpd = tmp_path / 'vm', tmp_path / 'bin', tmp_path / 'home', tmp_path / 'tmp'
    if not vm.exists():
        _vm_fixture(vm, required)
    for d in (bins, home, tmpd):
        d.mkdir(exist_ok=True)
    _py_bin(bins, 'ssh', FAKE_SSH)
    _py_bin(bins, 'scp', FAKE_SCP)
    _py_bin(bins, 'python3', FAKE_PY)
    inst = tmp_path / 'p.exe'
    inst.write_bytes(b'MZ')
    env = {k: v for k, v in os.environ.items() if k not in ('XDG_CACHE_HOME', 'WINQA_STAGE_ROOT', 'AUTOCLIP_QA_DASHSCOPE_KEY')}
    env.update({'PATH': f'{bins}:{os.environ["PATH"]}', 'WINQA_HOST': 'qa.invalid', 'WINQA_USER': 'qa', 'HOME': str(home),
                'TMPDIR': str(tmpd), 'LANG': UTF8, 'LC_ALL': UTF8, 'WINQA_MODEL_API_KEY': key, 'FAKE_VM': str(vm),
                'FAKE_MODE': mode, 'FAKE_DELIVERED': str(tmp_path / 'delivered.bin'), 'FAKE_MODES': str(tmp_path / 'modes.txt'),
                'FAKE_REAL_PY': sys.executable, 'FAKE_ENVLEAK': str(tmp_path / 'envleak.txt'),
                'FAKE_KEY_SHA': hashlib.sha256(key.encode()).hexdigest()})
    args = ['--prev', str(inst), '--candidate', str(inst), '--version', '1.5.8', '--out', str(tmp_path / 'ev'),
            '--from-step', steps[0], '--to-step', steps[1]]
    return env, args


def _run(tmp_path, bash, mode='', required=True, steps=('8', '8')):
    env, args = _env(tmp_path, mode, required=required, steps=steps)
    if mode == 'cp-fail':        # #309: a directory where the bundle's env.json must land -> cp fails
        (tmp_path / 'ev' / 'env.json').mkdir(parents=True, exist_ok=True)
    if mode == 'mkdir-fail':     # #309: a file where bundles/ must be created -> mkdir fails
        (tmp_path / 'ev').mkdir(exist_ok=True); (tmp_path / 'ev' / 'bundles').write_text('x')
    before = _tree(tmp_path / 'vm' / 'out')
    done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=180)
    assert _tree(tmp_path / 'vm' / 'out') == before, 'VM originals must stay byte-for-byte unchanged'
    _assert_no_raw_on_control(tmp_path, done)
    return done


def _assert_no_raw_on_control(tmp_path, done):
    blobs = [('stdout', done.stdout + done.stderr)]
    d = tmp_path / 'delivered.bin'
    if d.exists():
        blobs.append(('delivered by scp', d.read_bytes()))
    for sub in ('ev', 'tmp', 'home'):
        for p in (tmp_path / sub).rglob('*'):
            if p.is_file():
                data = p.read_bytes()
                try:
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        data += b''.join(n.encode() + z.read(n) for n in z.namelist())
                except zipfile.BadZipFile:
                    pass
                blobs.append((str(p), p.as_posix().encode() + data))
    for where, data in blobs:
        for leak in LEAKS:
            assert leak not in data, (where, leak, data[:400])


def _steps(tmp_path):
    p = tmp_path / 'ev' / 'steps.txt'
    return p.read_text() if p.exists() else ''


def _manifest(tmp_path):
    ms = sorted((tmp_path / 'ev' / 'bundles').glob('*.manifest.json')) if (tmp_path / 'ev' / 'bundles').exists() else []
    return json.loads(ms[-1].read_text()) if ms else None


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
    assert done.returncode != 0, (mode, done.stdout[-800:])
    assert 'pull_final=FAIL' in _steps(tmp_path), (mode, _steps(tmp_path), done.stdout[-800:])
    assert not (tmp_path / 'ev' / 'env.json').exists(), mode
    # #311: every failure mode (TERM is a3) leaves no staging dir behind
    assert not list((tmp_path / 'home' / '.cache' / 'autoclip-winqa-stage').glob('winqa-stage.*')), mode
    if mode == 'export-killed':
        exp = tmp_path / 'vm' / 'export'
        assert not list(exp.glob('*.zip')), 'a killed exporter must not leave a committed bundle'


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
    rows = [json.loads(l) for l in (tmp_path / 'ev' / 'steps.jsonl').read_text().splitlines()]
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

STEPS_OK = [{'run_id': 'r1', 'step': 'collect_logs', 'attempt': 1, 'status': 'ok', 'exit_code': 0}]


def _export(tmp_path, src, keys=KEY, extra=(), steps=STEPS_OK):
    sf = tmp_path / 'ctl-steps.json'
    sf.write_text(json.dumps(steps))
    return subprocess.run([sys.executable, str(EXPORTER), 'export', '--src', str(src), '--dest', str(tmp_path / 'exp'),
                           '--bundle', 'b1', '--steps', str(sf), '--keys-stdin', *extra], input=(keys + '\n').encode(),
                          capture_output=True)


def test_u1_exact_key_comes_from_stdin_never_argv_and_is_never_printed(tmp_path):
    src = tmp_path / 'out'; src.mkdir()
    (src / 'a.json').write_text(json.dumps({'k': f'x{KEY}y', 'nested': [{'v': KEY}]}))
    done = _export(tmp_path, src)
    assert done.returncode == 0 and KEY.encode() not in done.stdout + done.stderr
    with zipfile.ZipFile(tmp_path / 'exp' / 'b1.zip') as z:
        assert KEY.encode() not in b''.join(z.read(n) for n in z.namelist())
    sh = (ROOT / 'run_winqa.sh').read_text()
    line = next(l for l in sh.splitlines() if 'export_evidence.py export' in l)
    assert 'MODEL_API_KEY' not in line.split('remote', 1)[1] and '--keys-stdin' in line


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


def _ee():
    sys.path.insert(0, str(ROOT / 'py'))
    import export_evidence as ee
    return ee


def _rebuild(good, replace=None, add=(), manifest_edit=None):
    """A bundle with the given member changes whose manifest hashes are made consistent again, so only the content
    / contract checks can reject it (#311: the old u4 case was caught by the hash check alone)."""
    with zipfile.ZipFile(io.BytesIO(good)) as zi:
        members = {n: zi.read(n) for n in zi.namelist()}
    m = json.loads(members.pop('manifest.json'))
    members.update(replace or {})
    for n, data in add:
        members[n] = data
        m['files'].append({'name': n, 'sha256': '', 'source_sha256': '0' * 64, 'size': len(data)})
    for f in m['files']:
        f['sha256'] = hashlib.sha256(members[f['name']]).hexdigest()
    if manifest_edit:
        manifest_edit(m, members)
        for f in m['files']:
            f['sha256'] = hashlib.sha256(members[f['name']]).hexdigest()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zo:
        for n, data in members.items():
            zo.writestr(n, data)
        zo.writestr('manifest.json', json.dumps(m, ensure_ascii=False, indent=2) + '\n')
    return buf.getvalue()


def _verify(tmp_path, data, dg=None):
    p = tmp_path / 'v.zip'; p.write_bytes(data)
    return subprocess.run([sys.executable, str(EXPORTER), 'verify', '--bundle', str(p), '--sha256',
                           dg or hashlib.sha256(data).hexdigest(), '--into', str(tmp_path / 'x'), '--keys-stdin'],
                          input=(KEY + '\n').encode(), capture_output=True).returncode


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
    """#306: stop-candidate, the smoke detail reports and the step 10-14 real/*.json are required evidence, declared
    right after the command that writes them (a step that "succeeds" without its JSON is then incomplete)."""
    import re
    sh = (ROOT / 'run_winqa.sh').read_text(encoding='utf-8')
    declared = set(re.findall(r'\brequire ([A-Za-z0-9._/-]+)', sh))
    for f in ('stop-candidate.json', 'smoke.json', 'windows-smoke.json', 'windows-smoke-desktop.json',
              'windows-sensevoice-installed.json', 'windows-whisper-installed.json', 'real/model.json',
              'real/whisper.json', 'real/whisper-hfmirror.json', 'real/local.json', 'real/link.json', 'real/final.json',
              'collect-logs-final.json', 'failure.json', 'check-candidate.json'):
        assert f in declared, f
