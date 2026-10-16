"""E9 / R16 #49–#53: acceptance-machine puller exit codes (bash 5 and macOS bash 3.2),
PowerShell exit codes and HTTP/hash handling, provenance helper, evidence redaction."""
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / 'scripts' / 'winqa'
SH = ROOT / 'pull_run_installer.sh'
PS1 = ROOT / 'ps' / 'pull_run_installer.ps1'
DIGEST = 'a' * 64
UTF8 = 'en_US.UTF-8' if sys.platform == 'darwin' else 'C.UTF-8'
EXE_SHA = 'b' * 64

# macOS ships bash 3.2; CI/Linux can point WINQA_TEST_BASH32 at a bash-3.2 build.
BASHES = ['bash'] + ([os.environ['WINQA_TEST_BASH32']] if os.environ.get('WINQA_TEST_BASH32') else []) \
    + (['/bin/bash'] if sys.platform == 'darwin' else [])
PWSH = os.environ.get('WINQA_TEST_PWSH') or shutil.which('pwsh')
# R17 #57: pwsh is a required test dependency (scripts/winqa/README.md); a missing pwsh fails the
# PowerShell cases instead of skipping them (quality_gate treats skips as BLOCKED).


def _bin(folder, name, body):
    path = folder / name
    path.write_text('#!/usr/bin/env bash\n' + body + '\n')
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run(tmp_path, bash, *, digest=DIGEST, artifacts=('autoclip-desktop-windows-x64',), prov_download='ok', prov_json=None):
    bins = tmp_path / 'bin'
    bins.mkdir(exist_ok=True)
    calls = tmp_path / 'calls.log'
    calls.write_text('')
    listing = '\n'.join(f'{name} {i + 1} 4096 {digest if name.startswith("autoclip") else ""}'.rstrip()
                        for i, name in enumerate(artifacts))
    (tmp_path / 'listing.txt').write_text(listing + '\n')
    prov = tmp_path / 'prov.json'
    if isinstance(prov_json, str):
        prov.write_text(prov_json)
    else:
        prov.write_text(json.dumps(prov_json if prov_json is not None else {'assets': {'AutoClip_1.5.8_x64-setup.exe': EXE_SHA}}))
    download = {
        'ok': f'mkdir -p "$D"; cp "{prov}" "$D/p.json"; exit 0',
        'fail': 'echo "HTTP 500 for /Users/kris/x https://example.invalid/sig?token=1" >&2; exit 1',
        'empty': 'mkdir -p "$D"; exit 0',
    }[prov_download]
    _bin(bins, 'gh', f'''echo "gh $*" >> "{calls}"
case "$1" in
  api) cat "{tmp_path / 'listing.txt'}";;
  auth) echo tok;;
  run) D=""; while [ $# -gt 0 ]; do [ "$1" = -D ] && D="$2"; shift; done; {download};;
esac''')
    _bin(bins, 'curl', f'cat >/dev/null; echo "curl $*" >> "{calls}"; printf "https://signed.invalid/zip"')
    for tool in ('ssh', 'scp'):
        _bin(bins, tool, f'echo "{tool} $*" >> "{calls}"; exit 0')
    env = {**os.environ, 'PATH': f'{bins}:{os.environ["PATH"]}', 'WINQA_HOST': 'qa.invalid',
           'WINQA_IDENTITY': str(tmp_path / 'id'), 'LANG': UTF8, 'LC_ALL': UTF8}
    done = subprocess.run([bash, str(SH), '999'], env=env, capture_output=True, text=True)
    return done, calls.read_text()


pytestmark_bash = pytest.mark.skipif(sys.platform == 'win32', reason='bash harness')


@pytestmark_bash
@pytest.mark.parametrize('bash', BASHES)
@pytest.mark.parametrize('digest', ['', 'null', 'sha256:', 'sha256:abc'])
def test_missing_or_invalid_digest_exits_4_before_download(tmp_path, bash, digest):
    done, calls = _run(tmp_path, bash, digest=digest)
    assert done.returncode == 4, done.stdout + done.stderr
    assert 'digest' in done.stderr
    assert not re.search(r'^(ssh|scp|curl) ', calls, re.M) and 'run download' not in calls


@pytestmark_bash
@pytest.mark.parametrize('bash', BASHES)
def test_no_artifact_exits_2(tmp_path, bash):
    done, _ = _run(tmp_path, bash, artifacts=('something-else',))
    assert done.returncode == 2, done.stderr


@pytestmark_bash
@pytest.mark.parametrize('bash', BASHES)
@pytest.mark.parametrize('case', ['download_fails', 'no_json', 'garbage_hash', 'no_hash', 'two_hashes', 'not_json', 'valid_plus_null', 'valid_plus_number', 'only_null'])
def test_listed_provenance_that_cannot_be_used_aborts_with_5(tmp_path, bash, case):
    prov_download, prov_json = {
        'download_fails': ('fail', None), 'no_json': ('empty', None),
        'garbage_hash': ('ok', {'assets': {'AutoClip_x64-setup.exe': 'zz'}}),
        'no_hash': ('ok', {'assets': {'AutoClip.dmg': EXE_SHA}}),
        'two_hashes': ('ok', {'assets': {'a-setup.exe': EXE_SHA, 'b-setup.exe': 'c' * 64}}),
        'not_json': ('ok', '{not json'),
        'valid_plus_null': ('ok', {'assets': [{'name': 'a-setup.exe', 'sha256': EXE_SHA}, {'name': 'b-setup.exe', 'sha256': None}]}),
        'valid_plus_number': ('ok', {'assets': {'a-setup.exe': EXE_SHA, 'b-setup.exe': 12345}}),
        'only_null': ('ok', {'assets': [{'name': 'a-setup.exe', 'sha256': None}]}),
    }[case]
    done, calls = _run(tmp_path, bash, artifacts=('autoclip-desktop-windows-x64', 'internal-desktop-provenance-windows-x64'),
                       prov_download=prov_download, prov_json=prov_json)
    assert done.returncode == 5, done.stdout + done.stderr
    assert not re.search(r'^(ssh|scp) ', calls, re.M)
    assert '/Users/kris' not in done.stderr and 'token=1' not in done.stderr


@pytestmark_bash
@pytest.mark.parametrize('bash', BASHES)
def test_valid_provenance_is_passed_to_the_machine(tmp_path, bash):
    done, calls = _run(tmp_path, bash, artifacts=('autoclip-desktop-windows-x64', 'internal-desktop-provenance'))
    assert done.returncode == 0, done.stderr
    assert f'-WantZip {DIGEST} -WantExe {EXE_SHA}' in calls


@pytestmark_bash
@pytest.mark.parametrize('bash', BASHES)
def test_run_without_provenance_says_so_and_checks_zip_only(tmp_path, bash):
    done, calls = _run(tmp_path, bash)
    assert done.returncode == 0, done.stderr
    assert '没有 provenance' in done.stdout
    assert 'run download' not in calls and f'-WantZip {DIGEST}' in calls and '-WantExe' not in calls


def test_every_shell_variable_is_braced_for_bash32():
    """R16 #50: bash 3.2 in a UTF-8 locale glues `$VAR（` into one name; require ${VAR}."""
    code = re.sub(r"<<'PY'.*?^PY$", '', SH.read_text(encoding='utf-8'), flags=re.S | re.M)
    code = re.sub(r"awk -v \S+ '[^']*'", '', code)
    bare = [m.group(0) for m in re.finditer(r'\$[A-Za-z_][A-Za-z0-9_]*', code)]
    assert bare == [], bare


# ---------------- PowerShell (R16 #51 #52) ----------------

def need_pwsh(fn):
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if not PWSH:
            pytest.fail('pwsh (PowerShell 7) is required for scripts/winqa tests; install it or set WINQA_TEST_PWSH (see scripts/winqa/README.md)')
        return fn(*args, **kwargs)
    return wrapper


def _zip_with_exe(payload=b'installer'):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('AutoClip_1.5.8_x64-setup.exe', payload)
    return buf.getvalue()


def _ps(tmp_path, *, want_zip, want_exe='', curl_mode='ok', data=b''):
    inst = tmp_path / 'inst'
    inst.mkdir(exist_ok=True)
    (inst / '.url-9').write_text('https://signed.invalid/zip')
    src = tmp_path / 'artifact.bin'
    src.write_bytes(data)
    fake = tmp_path / 'fakecurl.py'
    fake.write_text(f'''import sys
a = sys.argv[1:]
if {curl_mode!r} == "http_error":
    assert "--fail" in a, "curl must run with --fail"
    sys.exit(22)
lo, hi = map(int, a[a.index("-r") + 1].split("-"))
open(a[a.index("-o") + 1], "wb").write(open({str(src)!r}, "rb").read()[lo:hi + 1])
''')
    # R17 #58: Start-Process needs a real executable on every OS: .cmd on Windows, a shell shim elsewhere.
    if sys.platform == 'win32':
        shim = tmp_path / 'fakecurl.cmd'
        shim.write_text(f'@"{sys.executable}" "{fake}" %*\r\n')
    else:
        shim = tmp_path / 'fakecurl'
        shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{fake}" "$@"\n')
        shim.chmod(0o755)
    args = [PWSH, '-NoProfile', '-File', str(PS1), '-Run', '9', '-Total', str(len(data) or 10), '-N', '2', '-WantZip', want_zip]
    if want_exe:
        args += ['-WantExe', want_exe]
    env = {**os.environ, 'WINQA_INST': str(inst), 'WINQA_CURL': str(shim)}
    return subprocess.run(args, env=env, capture_output=True, text=True), inst


@need_pwsh
@pytest.mark.parametrize('digest', ['', 'zz', 'sha256:' + DIGEST])
def test_pwsh_missing_digest_exits_4(tmp_path, digest):
    done, inst = _ps(tmp_path, want_zip=digest)
    assert done.returncode == 4, done.stdout + done.stderr
    assert 'digest' in done.stderr
    assert (inst / '.url-9').exists(), 'must refuse before reading the signed URL'


@need_pwsh
def test_pwsh_http_failure_exits_6_and_keeps_no_error_body(tmp_path):
    done, inst = _ps(tmp_path, want_zip=DIGEST, curl_mode='http_error', data=_zip_with_exe())
    assert done.returncode == 6, done.stdout + done.stderr
    assert not any(p.stat().st_size for p in (inst / 'dl-9' / 'parts').glob('p*'))
    assert 'signed.invalid' not in done.stdout + done.stderr


@need_pwsh
def test_pwsh_zip_hash_mismatch_exits_7_and_deletes_chunks(tmp_path):
    done, inst = _ps(tmp_path, want_zip=DIGEST, data=_zip_with_exe())
    assert done.returncode == 7, done.stdout + done.stderr
    assert not (inst / 'dl-9').exists()
    assert not (inst / 'candidate-setup.exe').exists()


@need_pwsh
def test_pwsh_exe_mismatch_exits_7_and_valid_package_verifies(tmp_path):
    data = _zip_with_exe()
    zsha = hashlib.sha256(data).hexdigest()
    done, inst = _ps(tmp_path, want_zip=zsha, want_exe=EXE_SHA, data=data)
    assert done.returncode == 7 and not (inst / 'dl-9').exists(), done.stderr
    (tmp_path / 'inst2').mkdir()
    ok_tmp = tmp_path / 'inst2'
    done, inst = _ps(ok_tmp, want_zip=zsha, want_exe=hashlib.sha256(b'installer').hexdigest(), data=data)
    assert done.returncode == 0, done.stdout + done.stderr
    assert (inst / 'candidate-setup.exe').read_bytes() == b'installer'


def test_powershell_digest_guard_does_not_use_write_error():
    source = PS1.read_text(encoding='utf-8')
    guard = source.index("$WantZip -notmatch '^[0-9a-f]{64}$'")
    assert guard < source.index('Get-Content -Raw $uf')
    assert 'Write-Error' not in source
    assert "'--fail'" in source


# ---------------- misc ----------------

def test_no_hardcoded_host_or_token():
    text = '\n'.join(p.read_text(encoding='utf-8') for p in ROOT.rglob('*') if p.is_file() and p.suffix in ('.sh', '.ps1', '.py', '.md'))
    for needle in ('ghp_', 'github_pat_', '101.35.', 'BEGIN OPENSSH'):
        assert needle not in text


def _module(name):
    sys.path.insert(0, str(ROOT))
    try:
        return __import__(name)
    finally:
        sys.path.remove(str(ROOT))


def test_exe_provenance_records_setup_sha256(tmp_path):
    exe_provenance = _module('exe_provenance')
    (tmp_path / 'nsis').mkdir()
    exe = tmp_path / 'nsis' / 'AutoClip_1.5.8_x64-setup.exe'
    exe.write_bytes(b'installer')
    out = tmp_path / 'p.json'
    assert exe_provenance.main([str(tmp_path / 'nsis'), str(out), '--run-id', '7']) == 0
    assert json.loads(out.read_text())['assets'] == {exe.name: hashlib.sha256(b'installer').hexdigest()}
    empty = tmp_path / 'empty'
    empty.mkdir()
    with pytest.raises(SystemExit):
        exe_provenance.build(empty)


@pytest.mark.parametrize('raw,expected', [
    (r'C:\Users\kris\AppData\Local\AutoClip\log.txt', r'C:\Users\<user>\AppData\Local\AutoClip\log.txt'),
    ('"C:\\\\Users\\\\kris\\\\AppData"', '"C:\\\\Users\\\\<user>\\\\AppData"'),
    ('c:/users/kris/a.log', 'c:/Users/<user>/a.log'),
    ('/Users/zhoukk/AutoClipQA/158', '/Users/<user>/AutoClipQA/158'),
    ('/home/runner/work/x', '/home/<user>/work/x'),
    ('GET /api/home/feed', 'GET /api/home/feed'),
    (r'C:\Users\qa', r'C:\Users\<user>'),
    (r'C:\Users\Jane Doe\AppData\x.log', r'C:\Users\<user>\AppData\x.log'),
    ('{"p": "C:\\\\Users\\\\Jane Doe\\\\a"}', '{"p": "C:\\\\Users\\\\<user>\\\\a"}'),
    ('/Users/Jane Doe/AutoClipQA', '/Users/<user>/AutoClipQA'),
    ('/home/Jane Doe', '/home/<user>'),
    ('see /home/a and more /x', 'see /home/<user> and more /x'),
])
def test_redact_scrubs_home_directories(tmp_path, raw, expected):
    redact = _module('redact')
    (tmp_path / 'e.log').write_text(raw, encoding='utf-8')
    redact.main(str(tmp_path))
    assert (tmp_path / 'e.log').read_text(encoding='utf-8') == expected


@pytestmark_bash
@pytest.mark.parametrize('bash', BASHES)
def test_shell_diagnostics_use_redact_py(tmp_path, bash):
    """R17 #55: the .sh scrubber is redact.py (plain C:\\Users\\x, spaced names, /api/home kept)."""
    bins = tmp_path / 'bin'
    bins.mkdir()
    msg = r'fail C:\Users\qa\x and /Users/Jane Doe/y GET /api/home/feed https://signed.invalid/z?sig=1'
    _bin(bins, 'gh', f'''case "$1" in
  api) echo "autoclip-desktop-windows-x64 1 4096 {DIGEST}"; echo "internal-desktop-provenance 2 10";;
  run) echo '{msg}' >&2; exit 1;;
esac''')
    env = {**os.environ, 'PATH': f'{bins}:{os.environ["PATH"]}', 'WINQA_HOST': 'qa.invalid', 'LANG': UTF8, 'LC_ALL': UTF8}
    done = subprocess.run([bash, str(SH), '9'], env=env, capture_output=True, text=True)
    assert done.returncode == 5, done.stderr
    assert r'C:\Users\<user>\x' in done.stderr and '/Users/<user>/y' in done.stderr
    assert 'GET /api/home/feed' in done.stderr and '<url>' in done.stderr
    assert 'qa' not in done.stderr.replace('qa.invalid', '') and 'Jane' not in done.stderr and 'sig=1' not in done.stderr
    assert 'redact.py' in SH.read_text(encoding='utf-8')
