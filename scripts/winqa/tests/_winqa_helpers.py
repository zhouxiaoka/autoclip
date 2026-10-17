"""Shared fake-VM harness for the winqa tests (R29 #333: one helper module instead of tests importing tests).
The fake VM is a directory; the fake ssh speaks the entry.ps1 protocol (fixed command line, JSON request on stdin)
and runs the REAL scripts that sit in the VM's C:\\winqa\\py with the local Python; the fake scp really copies."""
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
            if b'logpipe.py' not in open(d + '/cmdline', 'rb').read():
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
ENTRY = 'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File C:\\winqa\\ps\\entry.ps1'
FIXED = ('hostname', 'powershell -NoProfile -Command "New-Item -ItemType Directory -Force C:\\winqa\\ctl | Out-Null"')
with open(os.environ['FAKE_CMDS'], 'a') as fh:     # R29 #323: every remote command line, for the argv assertion
    fh.write(cmd + '\n')
if cmd == ENTRY:
    import json
    raw = sys.stdin.buffer.readline()
    req = json.loads(raw)                           # entry.ps1 reads exactly line 1 (+ the key line if has_key)
    with open(os.environ['FAKE_REQS'], 'a') as fh:
        fh.write(json.dumps(req) + '\n')
    if req['op'] == 'py':
        if MODE == 'no-python':
            sys.exit(1)
        key = sys.stdin.buffer.readline() if req['has_key'] else b''
        script = VM + '/py/' + req['args']['script'] + '.py'
        rest = [tr(t) for t in req['args']['args']]
        env = dict(os.environ, WINQA_OUT=VM + '/out')
        if MODE == 'export-killed' and script.endswith('export_evidence.py'):
            code = ("import os, runpy, sys; os.replace = lambda *a: os._exit(137); sys.argv = sys.argv[1:]; "
                    "runpy.run_path(sys.argv[0], run_name='__main__')")
            sys.exit(subprocess.run([sys.executable, '-c', code, script] + rest, env=env, input=key).returncode)
        sys.exit(subprocess.run([sys.executable, script] + rest, env=env, input=key).returncode)
    if req['op'] == 'hash':
        sys.exit(0)
    if req['op'] == 'ps' and MODE == 'collect-fail' and req['args']['script'] == 'collect_logs':
        sys.exit(3)
    print('remote: C:\\Users\\kris\\Desktop ok'); sys.exit(0)
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
if mode == 'redact-crash' and any(x.endswith('logpipe.py') for x in a):
    # the real log channel runs until the run reaches step 8 (staging dir exists by then), then it dies
    import subprocess
    child = subprocess.Popen([os.environ['FAKE_REAL_PY']] + a, stdin=subprocess.PIPE, pass_fds=(6,))
    for line in sys.stdin.buffer:
        if '8. '.encode() in line and b'====' in line:
            child.kill(); os.kill(os.getpid(), signal.SIGKILL)
        child.stdin.write(line); child.stdin.flush()
    sys.exit(0)
if any(x.endswith('logpipe.py') for x in a) and os.environ.get('FAKE_LP_EVID'):
    # #414 a2 evidence: same process (execv keeps the pid), no extra hop in the channel. A hard link keeps the status
    # file readable after run_winqa.sh removes its LP_DIR.
    ev = os.environ['FAKE_LP_EVID']
    try:
        st = a[a.index('--status') + 1]
        os.link(st, ev + '.status')
    except Exception as exc:
        open(ev + '.status-err', 'w').write(type(exc).__name__)
    open(ev + '.pid', 'w').write(str(os.getpid()))
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
                'FAKE_CMDS': str(tmp_path / 'cmds.txt'), 'FAKE_REQS': str(tmp_path / 'reqs.jsonl'),
                'FAKE_KEY_SHA': hashlib.sha256(key.encode()).hexdigest(), 'FAKE_LP_EVID': str(tmp_path / 'lp')})
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


def classify_a2(rc, final_text):
    """#414 a2 (Dong): which of the three it was. final_text is ev/logpipe-final.txt, written by logpipe_close or
    by the handshake branch. R31 I439: no file only means no close record (bash died, or the script exited before
    the logpipe started, e.g. mktemp failed); a signal is named only for rc > 128 or a negative rc."""
    if final_text is None:
        sig = -rc if rc < 0 else (rc - 128 if rc > 128 else None)
        return f'no_close_record rc={rc}' + (f' signal={sig}' if sig else '')
    reason = next((l.split(' ', 1)[1] for l in final_text.splitlines() if l.startswith('reason ')), 'none')
    kind = reason.split('=', 1)[0]
    return {'killed': 'logpipe_killed', 'exited': 'logpipe_exited_itself', 'exit': 'logpipe_exited_itself',
            'wrapper_gone': 'logpipe_wrapper_gone', 'drain_timeout': 'logpipe_hung_killed_by_script',
            'handshake_timeout': 'logpipe_no_handshake', 'died_before_ready': 'logpipe_died_before_ready',
            'none': 'logpipe_ok'}.get(kind, 'unknown') + f' ({reason}) rc={rc}'


def _save_failure_evidence(tmp_path, done, label):
    """#414 a2: everything needed to place a one-off failure. Written under $WINQA_A2_EVIDENCE (or tmp_path) and
    returned as a path for the assertion message. Contents are already scrubbed/fake (no real key in this harness)."""
    import time
    root = Path(os.environ.get('WINQA_A2_EVIDENCE') or tmp_path) / f'a2-evidence-{label}-{os.getpid()}-{time.time_ns()}'
    root.mkdir(parents=True, exist_ok=True)
    (root / 'rc.txt').write_text(str(done.returncode))
    (root / 'stdout.bin').write_bytes(done.stdout); (root / 'stderr.bin').write_bytes(done.stderr)
    lp = tmp_path / 'lp'
    st = Path(str(lp) + '.status')
    (root / 'logpipe-status.txt').write_text(st.read_text() if st.exists() else '<no status link>')
    pid = Path(str(lp) + '.pid')
    if pid.exists():
        p = pid.read_text().strip()
        alive = subprocess.run(['kill', '-0', p], capture_output=True).returncode == 0
        (root / 'logpipe-pid.txt').write_text(f'{p} alive_after_run={alive}\n')
    for rel in ('ev/run.log', 'ev/steps.txt', 'ev/logpipe-final.txt', 'reqs.jsonl', 'cmds.txt'):
        if (tmp_path / rel).exists():
            shutil.copy(tmp_path / rel, root / rel.replace('/', '_'))
    for f in (tmp_path / 'ev' / 'runs').glob('*/receipts.jsonl'):
        shutil.copy(f, root / 'receipts.jsonl')
    final = tmp_path / 'ev' / 'logpipe-final.txt'
    (root / 'classify.txt').write_text(classify_a2(done.returncode, final.read_text() if final.exists() else None) + '\n')
    (root / 'tree.txt').write_text('\n'.join(sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob('*'))))
    return str(root)


# ------------------------------------------------------------------ #414 v5 part B fixtures (M6: no hand-made verdicts)
CAND = 'c' * 64
INPUTS = {'candidate_sha256': CAND}


def _wpwc():
    sys.path[:0] = [str(ROOT / 'py'), str(ROOT)]
    import winqa_plan as wp
    import winqa_chain as wc
    return wp, wc


def default_result(name):
    """A passing result file for every judge of winqa_chain.RESULT_FILES (smoke.json: every run exit 0)."""
    return b'{"runs": [{"name": "a", "exit_code": 0}]}' if name == 'smoke.json' else b'{"ok": true}'


def make_run(out, run_id='r1', frm=8, to=8, flags=(), receipts=(('collect_logs', 'ok'),), files=None,
             manifest_edit=None, bundle_status='ok', inputs=None, log_channel='ok'):
    """A real run directory written only through winqa_plan.create/record: the receipts given, then a final export
    (pull_final) whose bundle (ZIP + members + manifest) is bound by its receipt, then the log_channel receipt
    (R31 I438), exactly as run_winqa.sh does. log_channel=None leaves that receipt out."""
    wp, _ = _wpwc()
    out = Path(out)
    plan = wp.create(out, run_id, frm, to, set(flags), dict(INPUTS if inputs is None else inputs))
    for step, st in receipts:
        wp.record(out, run_id, step, st, 0 if st == 'ok' else 1)
    if files is None:
        files = {f: default_result(f) for f in plan['required'] if f != 'steps.json'}
    files = dict(files)
    files.setdefault('steps.json', json.dumps(wp.all_receipts(out)).encode())
    files = {k: v for k, v in files.items() if v is not None}     # None = leave that file out of the bundle
    m = {'schema': 'test', 'plan_sha256': plan['plan_sha256'], 'required': plan['required'], 'status': 'complete',
         'missing_required': [], 'ok_false': [], 'withheld': [], 'error_codes': {}, 'contract_problems': {},
         'files': [{'name': n, 'sha256': hashlib.sha256(d).hexdigest()} for n, d in files.items()]}
    if manifest_edit:
        manifest_edit(m)
    stage = out.parent / f'.stage-{run_id}'
    shutil.rmtree(stage, ignore_errors=True)
    (stage / 'x').mkdir(parents=True)
    for n, d in files.items():
        p = stage / 'x' / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(d)
    (stage / 'x' / 'manifest.json').write_text(json.dumps(m))
    with zipfile.ZipFile(stage / 'b.zip', 'w') as z:
        for p in sorted((stage / 'x').rglob('*')):
            if p.is_file():
                z.writestr(p.relative_to(stage / 'x').as_posix(), p.read_bytes())
    adir = Path(wp.record(out, run_id, 'pull_final', bundle_status, 0 if bundle_status == 'ok' else 3,
                          bundle_zip=stage / 'b.zip', bundle_dir=stage / 'x') and
                wp.runs_dir(out) / run_id / f"a{wp.receipts(out, run_id)[-1]['attempt']}" / 'pull_final')
    for p in adir.rglob('*'):                                     # the evidence view, as run_winqa.sh copies it
        if p.is_file() and p.name != 'manifest.json':
            t = out / p.relative_to(adir)
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, t)
    shutil.rmtree(stage)
    if log_channel:
        wp.record(out, run_id, 'log_channel', log_channel, 0 if log_channel == 'ok' else 70)
    return plan


def make_passing_run(out, run_id='r1', **kw):
    """The only way a test gets a passing verdict: a real run directory judged by winqa_chain.verify_chain."""
    _, wc = _wpwc()
    make_run(out, run_id, **kw)
    r = wc.verify_chain(out, run_id, 'final')
    assert r.passed, r.reasons
    return r.as_dict(run_id)
