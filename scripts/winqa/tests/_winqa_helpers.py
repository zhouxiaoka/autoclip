"""Shared fake-VM harness for the winqa tests (R29 #333: one helper module instead of tests importing tests).
The fake VM is a directory; the fake ssh runs the REAL scripts that sit in the VM's C:\\winqa\\py with the local
Python; the fake scp really copies."""
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

ROOT = Path(__file__).resolve().parents[1]
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



STEPS_OK = [{'run_id': 'r1', 'step': 'collect_logs', 'attempt': 1, 'status': 'ok', 'exit_code': 0}]


def _export(tmp_path, src, keys=KEY, extra=(), steps=STEPS_OK):
    sf = tmp_path / 'ctl-steps.json'
    sf.write_text(json.dumps(steps))
    return subprocess.run([sys.executable, str(EXPORTER), 'export', '--src', str(src), '--dest', str(tmp_path / 'exp'),
                           '--bundle', 'b1', '--steps', str(sf), '--keys-stdin', *extra], input=(keys + '\n').encode(),
                          capture_output=True)


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



__all__ = [n for n in dir() if not n.startswith('__')]
