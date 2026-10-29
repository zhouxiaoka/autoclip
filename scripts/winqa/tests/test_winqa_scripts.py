"""E9 / R16 #49–#53: acceptance-machine puller exit codes (bash 5 and macOS bash 3.2),
PowerShell exit codes and HTTP/hash handling, provenance helper, evidence redaction."""
import hashlib
import io
import time
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

ROOT = Path(__file__).resolve().parents[1]
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
@pytest.mark.parametrize('case', ['download_fails', 'no_json', 'garbage_hash', 'no_hash', 'two_hashes', 'not_json', 'valid_plus_null', 'valid_plus_number', 'only_null',
                                  'valid_plus_empty_dict', 'valid_plus_empty_list', 'valid_plus_null_sha_dict', 'named_empty_dict_sha'])
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
        # R18 #87: unusable entry values next to one valid hash must not pass.
        'valid_plus_empty_dict': ('ok', {'assets': {'a-setup.exe': EXE_SHA, 'b-setup.exe': {}}}),
        'valid_plus_empty_list': ('ok', {'assets': {'a-setup.exe': EXE_SHA, 'b-setup.exe': []}}),
        'valid_plus_null_sha_dict': ('ok', {'assets': {'a-setup.exe': EXE_SHA, 'b-setup.exe': {'sha256': None}}}),
        'named_empty_dict_sha': ('ok', {'assets': [{'name': 'a-setup.exe', 'sha256': EXE_SHA}, {'name': 'b-setup.exe', 'sha256': {}}]}),
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


def _ps(tmp_path, *, want_zip, want_exe='', curl_mode='ok', data=b'', run='9', raw=False):
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
    args = [PWSH, '-NoProfile', '-File', str(PS1), '-Run', run, '-Total', str(len(data) or 10), '-N', '2', '-WantZip', want_zip]
    if want_exe:
        args += ['-WantExe', want_exe]
    env = {**os.environ, 'WINQA_INST': str(inst), 'WINQA_CURL': str(shim)}
    return subprocess.run(args, env=env, capture_output=True, text=not raw), inst


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
    text = '\n'.join(p.read_text(encoding='utf-8') for p in ROOT.rglob('*') if p.is_file() and p.suffix in ('.sh', '.ps1', '.py', '.md')
                     and p.relative_to(ROOT).parts[0] != 'tests')
    for needle in ('ghp_', 'github_pat_', '101.35.', 'BEGIN OPENSSH'):
        assert needle not in text


def _stream_bytes(raw, keys=()):
    """#414 R31: the one streaming path (redact.Stream, as --stdin / --lines / logpipe use it) on one byte string."""
    redact = _module('redact')
    out = []
    s = redact.Stream(list(keys), out.append)
    s.feed(raw)
    s.close()
    return b''.join(out)


def _scrub_stream_files(folder):
    """R27 #312: redact.py no longer rewrites evidence directories. These byte-level rule tests now drive the live
    entry point (#414 R31: redact.Stream, the only byte path; each file as one stream) on every file."""
    redact = _module('redact')
    keys = redact._env_keys()
    for p in sorted(Path(folder).rglob('*')):
        if p.is_file():
            raw = p.read_bytes()
            out = _stream_bytes(raw, keys)
            if out != raw:
                p.write_bytes(out)


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


ZH_JSON_CASES = ['/Users/张三/AutoClipQA', '/home/张三', 'C:\\Users\\张三\\AppData', 'C:\\Users\\张 三\\x', 'c:/users/张三/a.log']




def test_redact_json_colliding_keys_are_all_kept(tmp_path):
    """R20 #119: two users' paths as keys scrub to one key; both entries must survive."""
    redact = _module('redact')
    doc = {'/Users/alice/a.log': 1, '/Users/bob/a.log': 2, '/Users/<user>/a.log#2': 3, 'other': 4}
    data = redact.scrub_obj(doc)   # R27 #312: JSON evidence goes through scrub_obj (export_evidence.clean_json)
    assert sorted(data.values()) == [1, 2, 3, 4]
    assert all('alice' not in k and 'bob' not in k for k in data)
    assert data['/Users/<user>/a.log'] == 1 and data['other'] == 4


def test_redact_json_is_scrubbed_after_parsing(tmp_path):
    """R20 #122: escaped letters inside the root (U\\u0073ers) only decode through json.loads (text rules miss them)."""
    redact = _module('redact')
    raw = '{"p": "\\/U\\u0073ers\\/kris\\/a", "w": "C:\\\\U\\u0073ers\\\\qa\\\\x"}'
    assert json.loads(raw) == {'p': '/Users/kris/a', 'w': 'C:\\Users\\qa\\x'}
    # R22 #150: the text scanner now decodes these escapes too (it used to miss them entirely).
    assert redact.scrub_homes(raw) == '{"p": "\\/U\\u0073ers\\/<user>\\/a", "w": "C:\\\\U\\u0073ers\\\\<user>\\\\x"}'
    (tmp_path / 'e.json').write_text(raw, encoding='utf-8')
    _scrub_stream_files(tmp_path)
    assert json.loads((tmp_path / 'e.json').read_text(encoding='utf-8')) == {'p': '/Users/<user>/a', 'w': 'C:\\Users\\<user>\\x'}


@need_pwsh
def test_pwsh_verify_only_replaces_its_own_files(tmp_path):
    """R20 #121: other files in the install folder (and prev-setup.exe) are left alone."""
    data = _zip_with_exe()
    inst = tmp_path / 'inst'
    inst.mkdir()
    keep = {'prev-setup.exe': b'prev', 'notes.txt': b'n', 'other-setup.exe': b'o', 'candidate.sha256': b'old'}
    for name, body in keep.items():
        (inst / name).write_bytes(body)
    (inst / 'candidate-setup.exe').write_bytes(b'old candidate')
    done, inst = _ps(tmp_path, want_zip=hashlib.sha256(data).hexdigest(), want_exe=hashlib.sha256(b'installer').hexdigest(), data=data)
    assert done.returncode == 0, done.stdout + done.stderr
    assert (inst / 'candidate-setup.exe').read_bytes() == b'installer'
    assert 'candidate-setup.exe' in (inst / 'candidate.sha256').read_text()
    for name in ('prev-setup.exe', 'notes.txt', 'other-setup.exe'):
        assert (inst / name).read_bytes() == keep[name], name


# ---------------- R21: one rule for every spelling (#127 #128 #130 #131 #132) ----------------



@pytest.mark.parametrize('suffix', ['.log', '.json'])
def test_redact_non_utf8_file_is_replaced_bytewise(tmp_path, suffix):
    """R21 #128 / #414 R31: a GBK (or broken) line is not UTF-8: it is written only as the encoding marker, so the
    name in it cannot leak through a second byte-level reader."""
    redact = _module('redact')
    head = '错误 C:\\Users\\'.encode('gbk')
    tail = '\\AppData 日志\r\n'.encode('gbk') + b'\xff\xfe raw\n'
    raw = head + b'kris' + tail
    (tmp_path / ('e' + suffix)).write_bytes(raw)
    _scrub_stream_files(tmp_path)
    assert (tmp_path / ('e' + suffix)).read_bytes() == b'[REDACTED:encoding]\r\n[REDACTED:encoding]\n'


def test_redact_utf8_key_is_masked_in_byte_mode(tmp_path, monkeypatch):
    """Byte mode still masks the QA key and its masked form (matched as UTF-8 bytes)."""
    redact = _module('redact')
    key = 'sk-' + 'q' * 20 + 'Z9x'
    monkeypatch.setenv('WINQA_MODEL_API_KEY', key)
    raw = ('k=' + key + ' m=' + key[:3] + '…' + key[-3:] + ' \n').encode('utf-8') + b'\xff' + key.encode()
    (tmp_path / 'e.log').write_bytes(raw)
    _scrub_stream_files(tmp_path)
    assert (tmp_path / 'e.log').read_bytes() == b'k=*** m=*** \n[REDACTED:encoding]'


# R22: GBK trail byte 0x5C ('\\', e.g. 乗 81 5C, 淺 9C 5C) or 0x7C ('|', e.g. 億 83 7C) inside a user
# name used to end the name early in byte mode, leaking every byte after it.
GBK_5C_NAMES = ['乗', '张乗', '淺野', '乗a', '億x', '张三']
GBK_5C_ROOTS = [('C:\\Users\\', '\\AppData\\x.log'), ('/home/', '/x'), ('/Users/', '/拒绝访问 x')]


@pytest.mark.parametrize('name', GBK_5C_NAMES)
@pytest.mark.parametrize('root', GBK_5C_ROOTS)
def test_redact_gbk_name_with_5c_trail_byte_masked_whole(tmp_path, name, root):
    redact = _module('redact')
    pre, suf = (s.encode('gbk') for s in root)
    raw = '错误 '.encode('gbk') + pre + name.encode('gbk') + suf + b'\r\n'
    (tmp_path / 'e.log').write_bytes(raw)
    _scrub_stream_files(tmp_path)
    assert (tmp_path / 'e.log').read_bytes() == b'[REDACTED:encoding]\r\n'   # #414 R31: GBK is not UTF-8


@pytest.mark.parametrize('name', GBK_5C_NAMES)
def test_redact_stdin_gbk_name_with_5c_trail_byte(name):
    raw = 'C:\\Users\\'.encode('gbk') + name.encode('gbk') + '\\AppData 日志 https://x.invalid/s?sig=1\n'.encode('gbk')
    p = subprocess.run([sys.executable, str(ROOT / 'redact.py'), '--stdin'], input=raw, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert p.stdout == b'[REDACTED:encoding]\n'                              # #414 R31: GBK is not UTF-8


def test_redact_utf8_log_keeps_plain_rule(tmp_path):
    """UTF-8 logs are not read in GBK units: 张 (E5 BC A0) before '\\' must not swallow the separator."""
    redact = _module('redact')
    raw = 'C:\\Users\\张\\AppData\\x.log /home/乗/y\n'.encode('utf-8')
    (tmp_path / 'e.log').write_bytes(raw)
    _scrub_stream_files(tmp_path)
    assert (tmp_path / 'e.log').read_bytes() == b'C:\\Users\\<user>\\AppData\\x.log /home/<user>/y\n'




# ---------------- R22: one implementation, one corpus (#129 #150-#156, SJIS/Big5) ----------------
# scripts/winqa/tests/fixtures/winqa_redact_corpus.json holds every R16-R22 sample (input/expected). The same
# file drives four chains: redact.scrub_homes, --stdin bytes, evidence files in every supported
# encoding/line ending, and pull_run_installer.ps1 output through the .sh redact pipe.

CORPUS = json.loads((Path(__file__).parent / 'fixtures' / 'winqa_redact_corpus.json').read_text(encoding='utf-8'))['cases']
CASE_IDS = [c['id'] for c in CORPUS]
# (label, codec used to write the text, BOM bytes)
FILE_ENCODINGS = [('utf-8', 'utf-8', b''), ('utf-8-bom', 'utf-8', b'\xef\xbb\xbf'),
                  ('utf-16-le', 'utf-16-le', b'\xff\xfe'), ('utf-16-be', 'utf-16-be', b'\xfe\xff'),
                  ('gbk', 'gbk', b''), ('shift_jis', 'shift_jis', b''), ('big5', 'big5', b'')]


def _expected(case, label=None):
    return case.get('expected_by_encoding', {}).get(label, case['expected'])


def test_corpus_covers_every_round_and_encoding():
    rounds = {c['round'].split()[0] for c in CORPUS}
    assert {'R16-R20', 'R21', 'R18-R20', 'R22'} <= rounds
    tags = ' '.join(c['round'] for c in CORPUS)
    for tag in ('#150', '#151', '#152', '#153', '#156', 'GBK', 'SJIS', 'Big5'):
        assert tag in tags, tag
    assert any('\r\n' in c['text'] for c in CORPUS)


@pytest.mark.parametrize('case', CORPUS, ids=CASE_IDS)
def test_corpus_python(case):
    redact = _module('redact')
    fn = redact.scrub_stream if case.get('chains') else redact.scrub_homes
    assert fn(case['text']) == case['expected']
    assert fn(case['expected']) == case['expected'], 'scrubbing is idempotent'


@pytest.mark.parametrize('case', CORPUS, ids=CASE_IDS)
def test_corpus_stdin_bytes(case):
    redact = _module('redact')
    assert _stream_bytes(case['text'].encode('utf-8')) == redact.scrub_stream(case['text']).encode('utf-8')


@pytest.mark.parametrize('case', [c for c in CORPUS if not c.get('chains')], ids=[c['id'] for c in CORPUS if not c.get('chains')])
def test_corpus_files_every_encoding_and_line_ending(tmp_path, case):
    """#129 CRLF kept, #155 UTF-16: same expectation as text, original bytes elsewhere. #414 R31: GBK / SJIS / Big5
    lines are not UTF-8, so the one stream path writes each of them only as [REDACTED:encoding] (fail closed)."""
    redact = _module('redact')
    tried = 0
    for label, codec, bom in FILE_ENCODINGS:
        exp = _expected(case, label)
        for eol in ('\n', '\r\n'):
            body, want = f'head{eol}{case["text"]}{eol}tail 日志{eol}', f'head{eol}{exp}{eol}tail 日志{eol}'
            try:
                raw, out = bom + body.encode(codec), bom + want.encode(codec)
            except UnicodeEncodeError:
                continue   # sample not representable in this encoding
            if label in LEGACY:
                out = _legacy_lines(raw, out)
            f = tmp_path / f'{label}{len(eol)}.log'
            f.write_bytes(raw)
            _scrub_stream_files(tmp_path)
            assert f.read_bytes() == out, (label, repr(eol), f.read_bytes())
            f.unlink()
            tried += 1
    assert tried >= 4


LEGACY = ('gbk', 'shift_jis', 'big5')


def _legacy_lines(raw, want):
    """#414 R31: a line that is valid UTF-8 is scrubbed as text; any other line becomes the encoding marker."""
    got = []
    for r, w in zip(raw.split(b'\n'), want.split(b'\n')):
        try:
            r.decode('utf-8')
            got.append(w)
        except UnicodeDecodeError:
            got.append(b'[REDACTED:encoding]' + (b'\r' if r.endswith(b'\r') else b''))
    return b'\n'.join(got)


SH_REDACT = [sys.executable, str(ROOT / 'redact.py'), '--stdin']


@need_pwsh
@pytest.mark.parametrize('case', CORPUS, ids=CASE_IDS)
def test_corpus_pwsh_output_through_sh_redact_pipe(tmp_path, case):
    """The ps1 has no rule of its own; what it prints, piped through redact.py like the .sh does, equals the corpus."""
    done, _ = _ps(tmp_path, want_zip='', run=case['text'], raw=True)
    assert done.returncode == 4, done.stdout + done.stderr
    piped = subprocess.run(SH_REDACT, input=done.stderr, capture_output=True, check=True).stdout
    want = 'artifact digest missing or invalid; refusing to download run ' + case['expected']
    assert piped.decode('utf-8').rstrip('\r\n') == want.rstrip('\r\n')


def test_ps1_has_no_scrubbing_rule_and_sh_pipes_it_through_redact():
    """R22 code health: no second implementation (no patterns, no Scrub-Homes port) in the ps1."""
    text = PS1.read_text(encoding='utf-8')
    for gone in ('$WinPattern', '$PosixPattern', 'Scrub-Homes', 'Mask-HomeName', '<user>'):
        assert gone not in text
    sh = SH.read_text(encoding='utf-8')
    # R23 #186: one outer wrapper pipes the whole script (stdout and stderr) through redact.py
    head, body = sh.split('RUN="${1:?run_id}"', 1)
    assert '--stdin <"${FIFO_DIR}/out"' in head and '--stdin <"${FIFO_DIR}/err" >&2' in head
    assert 'redact' not in body, 'no second, partial redact pipe'


@pytestmark_bash
@pytest.mark.parametrize('bash', BASHES)
def test_sh_redacts_everything_the_machine_prints_and_keeps_its_exit_code(tmp_path, bash):
    done, _ = _run(tmp_path, bash)   # sets up the fake gh/curl/scp
    assert done.returncode == 0
    bins = tmp_path / 'bin'
    _bin(bins, 'ssh', '''case "$*" in
  *pull_run_installer.ps1*) echo 'round 1 C:\\Users\\Jane Doe\\x /Users/kris/y https://s.invalid/z?sig=1'
                            echo 'zip sha256 mismatch C:\\Users\\乗张三\\dl' >&2; exit 7;;
esac; exit 0''')
    env = {**os.environ, 'PATH': f'{bins}:{os.environ["PATH"]}', 'WINQA_HOST': 'qa.invalid',
           'WINQA_IDENTITY': str(tmp_path / 'id'), 'LANG': UTF8, 'LC_ALL': UTF8}
    done = subprocess.run([bash, str(SH), '999'], env=env, capture_output=True, text=True)
    assert done.returncode == 7, done.stderr
    assert 'round 1 C:\\Users\\<user>\\x /Users/<user>/y <url>' in done.stdout
    assert 'zip sha256 mismatch C:\\Users\\<user>\\dl' in done.stderr
    for leak in ('Jane', 'kris', 'sig=1', '张三', '乗'):
        assert leak not in done.stdout + done.stderr


@pytest.mark.parametrize('raw', ['C:' + '\\' * 5000 + 'x', 'C:' + '\\' * 4000 + 'Users' + '\\' * 4000 + 'a',
                                 '/home/' + '\\u005c' * 3000 + 'x', ('/Users/' + 'a ' * 20000 + '\n') * 5],
                         ids=['backslash-run', 'root-backslash-runs', 'escaped-sep-run', 'long-spaced-names'])
def test_redact_is_linear_on_hostile_input(raw):
    """R22 #154: the old regex took >3 s on 28 backslashes; the scanner must stay well under a second."""
    import time
    redact = _module('redact')
    t = time.perf_counter()
    redact.scrub_stream(raw)
    assert time.perf_counter() - t < 1.0


def test_redact_json_crlf_and_bom_are_kept(tmp_path):
    """R22 #129: a scrubbed JSON keeps CRLF line ends and its BOM."""
    redact = _module('redact')
    doc = json.dumps({'p': '/Users/alice/x', 'n': [1, 2]}, indent=2).replace('\n', '\r\n') + '\r\n'
    for name, bom in (('a.json', b''), ('b.json', b'\xef\xbb\xbf')):
        (tmp_path / name).write_bytes(bom + doc.encode('utf-8'))
    _scrub_stream_files(tmp_path)
    for name, bom in (('a.json', b''), ('b.json', b'\xef\xbb\xbf')):
        out = (tmp_path / name).read_bytes()
        assert out.startswith(bom) and b'\r\n' in out and b'\n' not in out.replace(b'\r\n', b'')
        assert json.loads(out.decode('utf-8-sig')) == {'p': '/Users/<user>/x', 'n': [1, 2]}


@pytest.mark.parametrize('codec,bom', [('utf-16-le', b'\xff\xfe'), ('utf-16-be', b'\xfe\xff')])
def test_redact_utf16_files(tmp_path, codec, bom):
    """R22 #155: UTF-16 (BOM) logs and JSON are masked and written back in UTF-16 with the BOM."""
    redact = _module('redact')
    (tmp_path / 'e.log').write_bytes(bom + 'C:\\Users\\张三\\x\r\n'.encode(codec))
    (tmp_path / 'e.json').write_bytes(bom + json.dumps({'p': '/home/bob/x'}).encode(codec))
    _scrub_stream_files(tmp_path)
    assert (tmp_path / 'e.log').read_bytes() == bom + 'C:\\Users\\<user>\\x\r\n'.encode(codec)
    assert json.loads((tmp_path / 'e.json').read_bytes()[2:].decode(codec)) == {'p': '/home/<user>/x'}


def test_redact_lone_surrogate_json_is_masked_and_does_not_stop_the_run(tmp_path):
    """R22 #156: '\\ud800' in JSON used to raise UnicodeEncodeError and stop every later file."""
    redact = _module('redact')
    (tmp_path / 'a.json').write_text('{"p": "\\ud800 /Users/bob/x"}', encoding='utf-8')
    (tmp_path / 'b.log').write_text('/Users/carol/x\n', encoding='utf-8')
    _scrub_stream_files(tmp_path)
    out = (tmp_path / 'a.json').read_text(encoding='utf-8')
    assert '\\ud800' in out and 'bob' not in out and json.loads(out) == {'p': '\ud800 /Users/<user>/x'}
    assert (tmp_path / 'b.log').read_text(encoding='utf-8') == '/Users/<user>/x\n'




BOUNDARY_TO_EOL = [("x '/home/kris' y", "x '/home/<user>"), ("open '/home/kris' now\nnext", "open '/home/<user>\nnext"),
                   ("x '/home/D''Arcy' y", "x '/home/<user>"), ("say '/Users/Jane Doe' ok", "say '/Users/<user>"),
                   ("x '/home/D' Artagnan y", "x '/home/<user>"), ("x 'C:\\Users\\D' Artagnan' y", "x 'C:\\Users\\<user>")]
BOUNDARY_NO_LEAK = [('/home/Jane Doe /x', 'Doe'), ("x '/home/D' Artagnan/x' y", 'Artagnan'),
                    ('C:\\Users\\Jane Doe \\x', 'Doe'), ("/Users/D' Artagnan/x", 'Artagnan')]


@pytest.mark.parametrize('raw,expected', BOUNDARY_TO_EOL)
def test_r23_179_no_quote_rule_name_runs_to_separator_or_line_end(raw, expected):
    """R23 #179: no quote cut-off; without a separator the name runs to the end of the line (mask more)."""
    assert _module('redact').scrub_homes(raw) == expected


@pytest.mark.parametrize('raw,leak', BOUNDARY_NO_LEAK)
def test_boundary_rule_never_leaks_the_rest_of_a_spaced_or_quoted_name(raw, leak):
    """#151 stays fixed: a run that reaches a separator is one path segment, masked whole."""
    assert leak not in _module('redact').scrub_homes(raw)


def test_home_and_users_roots_are_both_case_insensitive():
    out = _module('redact').scrub_homes('/HOME/qa\n/Home/bob\n/USERS/kris\n/users/amy')
    assert out == '/HOME/<user>\n/Home/<user>\n/USERS/<user>\n/users/<user>'


# ---------------- R23 (#179-#193, #154 #184): one boundary rule, union of readings ----------------

@pytest.mark.parametrize('raw,expected', [
    ('C:\\Users\\u0022Alice\\x', 'C:\\Users\\<user>\\x'), ('C:\\Users\\u003aAlice\\x', 'C:\\Users\\<user>\\x'),
    ('C:\\Users\\u003aAlice', 'C:\\Users\\<user>'), ('/home/\\u0022Alice/x', '/home/<user>/x')])
def test_r23_180_escape_ambiguity_masks_union_of_raw_and_decoded(raw, expected):
    out = _module('redact').scrub_homes(raw)
    assert out == expected and 'Alice' not in out


@pytest.mark.parametrize('raw', ['/home/<user>alice/x', 'C:\\Users\\<user>alice\\x', '/Users/<user>alice'])
def test_r23_182_only_an_exact_user_segment_is_left_alone(raw):
    redact = _module('redact')
    out = redact.scrub_homes(raw)
    assert 'alice' not in out and out == redact.scrub_homes(out)


@pytest.mark.parametrize('raw', ['/home/A\\B/x', '/Users/A"B/x', '/home/A:B/x'])
def test_r23_183_posix_names_end_only_at_slash(raw):
    assert _module('redact').scrub_homes(raw) == raw[:raw.index('/', 1) + 1] + '<user>/x'


@pytest.mark.parametrize('raw,expected', [('/home/./kris/x', '/home/./<user>/x'), ('/home/../kris/x', '/home/../<user>/x'),
                                          ('C:\\Users\\.\\kris\\x', 'C:\\Users\\.\\<user>\\x')])
def test_r23_189_dot_segments_are_skipped(raw, expected):
    assert _module('redact').scrub_homes(raw) == expected


@pytest.mark.parametrize('raw', ['HTTPS://x.invalid/y?sig=1', 'https:\\/\\/x.invalid\\/y?sig=1',
                                 'https:\\u002f\\u002fx.invalid/y?sig=1', 'HtTp://x.invalid/y?sig=1'])
def test_r23_185_urls_any_case_and_escaped(raw):
    redact = _module('redact')
    assert redact.scrub_stream('a ' + raw + ' b') == 'a <url> b'
    assert _stream_bytes(('a ' + raw + ' b').encode()) == b'a <url> b'


@pytest.mark.parametrize('name', ['ｱソAlice', 'ｶﾞソ太郎', 'ﾃｽﾄ表示'])
def test_r23_181_shift_jis_halfwidth_names_masked_whole(tmp_path, name):
    redact = _module('redact')
    raw = ('ログ C:\\Users\\' + name + '\\AppData\\x /home/' + name + '/y\r\n').encode('shift_jis')
    want = b'[REDACTED:encoding]\r\n'                                    # #414 R31: SJIS is not UTF-8
    (tmp_path / 'e.log').write_bytes(raw)
    _scrub_stream_files(tmp_path)
    assert (tmp_path / 'e.log').read_bytes() == want
    p = subprocess.run(SH_REDACT, input=raw, capture_output=True)
    assert p.returncode == 0 and p.stdout == want


def _layered(text):
    """Reference: undo escapes (\\\\ \\/ \\uXXXX %XX) by repeated full left-to-right passes."""
    hexd = set('0123456789abcdefABCDEF')
    ch = list(text)
    while True:
        out, i, changed = [], 0, False
        while i < len(ch):
            if ch[i] == '\\' and i + 1 < len(ch) and ch[i + 1] in '\\/':
                out.append(ch[i + 1]); i += 2; changed = True
            elif ch[i] == '\\' and i + 5 < len(ch) and ch[i + 1] == 'u' and all(x in hexd for x in ch[i + 2:i + 6]):
                out.append(chr(int(''.join(ch[i + 2:i + 6]), 16))); i += 6; changed = True
            elif ch[i] == '%' and i + 2 < len(ch) and all(x in hexd for x in ch[i + 1:i + 3]):
                out.append(chr(int(''.join(ch[i + 1:i + 3]), 16))); i += 3; changed = True
            else:
                out.append(ch[i]); i += 1
        ch = out
        if not changed:
            return ''.join(ch)


def test_r23_184_single_pass_decoder_equals_repeated_passes():
    import random
    rnd = random.Random(414)
    parts = ['\\', 'u', '0', '5', 'c', '2', 'f', '/', 'a', '\\u005c', '\\u0075', '4', '1', '\\\\', '%', '%5C', '%25', 'F']
    redact = _module('redact')
    for _ in range(20000):
        t = ''.join(rnd.choice(parts) for _ in range(rnd.randint(0, 16)))
        ch, st, en = redact._decoded_view(t)
        assert ''.join(ch) == _layered(t), t
        assert all(e <= s2 for e, s2 in zip(en, st[1:])) and (not en or en[-1] == len(t))


@pytest.mark.parametrize('unit', ['u005c', 'u005cu005c', '\\\\'], ids=['u005c-chain', 'double', 'backslash-pairs'])
def test_r23_184_multi_layer_escapes_scale_linearly(unit):
    """R23 #184: 40 KB of nested \\u005c took 13 s; now < 1 s and doubling the input at most ~doubles the time."""
    import time
    redact = _module('redact')

    def cost(size):
        raw = '/home/\\' + unit * (size // len(unit)) + 'kris/x'
        t = time.perf_counter()
        out = redact.scrub_stream(raw)
        assert 'kris' not in out
        return time.perf_counter() - t
    cost(2000)
    small, big = min(cost(20000) for _ in range(3)), min(cost(40000) for _ in range(3))
    assert big < 1.0
    assert big < 3.5 * small + 0.02, (small, big)




@pytest.mark.parametrize('codec', ['utf-16-le', 'utf-16-be'])
def test_r23_190_utf16_without_bom_is_masked_and_written_back(tmp_path, codec):
    redact = _module('redact')
    (tmp_path / 'e.log').write_bytes('C:\\Users\\kris\\x /home/bob/y\r\n'.encode(codec))
    _scrub_stream_files(tmp_path)
    assert (tmp_path / 'e.log').read_bytes() == 'C:\\Users\\<user>\\x /home/<user>/y\r\n'.encode(codec)
    assert _stream_bytes('/Users/kris/x'.encode(codec)) == '/Users/<user>/x'.encode(codec)




def test_r23_187_stdin_error_prints_nothing_and_exits_non_zero():
    bad = b'\xff\xfe' + '/Users/bob'.encode('utf-16-le') + b'\x00'
    p = subprocess.run(SH_REDACT, input=bad, capture_output=True)
    # #414 R31 I432: a dangling UTF-16 byte at EOF is not an internal error: the rest is the marker, a warning, rc 0
    assert p.returncode == 0 and b'b\x00o\x00b' not in p.stdout and b'bob' not in p.stdout
    assert p.stdout == b'\xff\xfe' + '[REDACTED:encoding]'.encode('utf-16-le') and b'WINQA_W_REDACT_TRUNCATED' in p.stderr
    assert b'Traceback' not in p.stderr and b'bob' not in p.stderr


def _sh_env(tmp_path):
    return {**os.environ, 'PATH': f'{tmp_path / "bin"}:{os.environ["PATH"]}', 'WINQA_HOST': 'qa.invalid',
            'WINQA_IDENTITY': '/Users/kris/.ssh/id_winqa', 'LANG': UTF8, 'LC_ALL': UTF8}


@pytestmark_bash
@pytest.mark.parametrize('bash', BASHES)
@pytest.mark.parametrize('tool', ['gh', 'curl', 'ssh', 'scp'])
def test_r23_186_every_command_output_goes_through_redact(tmp_path, bash, tool):
    """R23 #186: gh, curl, ssh (mkdir, ps1, cleanup) and scp output is scrubbed, not only the ps1 call."""
    _run(tmp_path, bash)
    bins = tmp_path / 'bin'
    leak = 'warn: Identity file /Users/kris/.ssh/id_winqa C:\\\\Users\\\\Jane Doe\\\\x https://s.invalid/z?sig=1'
    body = (bins / tool).read_text().split('\n', 1)[1]
    out = '' if tool == 'curl' else f'echo "{tool} out {leak}"; '   # curl's stdout is the signed URL
    _bin(bins, tool, f'{out}echo "{tool} err {leak}" >&2\n' + body)
    done = subprocess.run([bash, str(SH), '999'], env=_sh_env(tmp_path), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert f'{tool} err' in done.stderr and '/Users/<user>/.ssh' in done.stderr
    for bad in ('kris', 'Jane', 'sig=1'):
        assert bad not in done.stdout + done.stderr, (bad, done.stdout, done.stderr)


@pytestmark_bash
@pytest.mark.parametrize('bash', BASHES)
@pytest.mark.parametrize('remote_rc', [0, 7])
def test_r23_187_redact_failure_never_exits_0(tmp_path, bash, remote_rc):
    """R23 #187: a redact failure (#414 R31: a key with a line break; odd-length UTF-16 is no longer an error, I432)
    prints nothing raw and the script exits non-zero (8 if the run itself succeeded, else the run's own code)."""
    _run(tmp_path, bash)
    bins = tmp_path / 'bin'
    payload = (b'\xff\xfe' + '/Users/bob'.encode('utf-16-le') + b'\x00')
    (tmp_path / 'bad.bin').write_bytes(payload)
    _bin(bins, 'ssh', 'case "$*" in\n  *pull_run_installer.ps1*) cat "' + str(tmp_path / 'bad.bin') + '" >&2; exit '
         + str(remote_rc) + ';;\nesac; exit 0')
    done = subprocess.run([bash, str(SH), '999'], env=dict(_sh_env(tmp_path), WINQA_MODEL_API_KEY='a\nb'),
                          capture_output=True)
    # a bad key makes redact exit before it reads anything, so the script's own writes may die on SIGPIPE (141,
    # seen on macOS CI); either way the exit is non-zero and the output is withheld
    assert done.returncode in ((8 if remote_rc == 0 else remote_rc), 141), done.stderr
    assert '脱敏失败'.encode() in done.stderr and b'Traceback' not in done.stderr
    assert b'b\x00o\x00b' not in done.stdout + done.stderr


def test_r23_193_readme_keeps_the_harness_documentation():
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    for kept in ('run_winqa.sh', '每次运行都会先卸载 AutoClip 并删除用户数据', '仍需人工 / 界面的部分', 'WINQA_MODEL_API_KEY',
                 '验收机拉包脚本（E9）', '测试依赖（必需）'):
        assert kept in text, kept


def _probe(monkeypatch, tmp_path):
    pytest.importorskip('requests')
    import importlib.util
    monkeypatch.setenv('APPDATA', str(tmp_path))
    spec = importlib.util.spec_from_file_location('winqa_probe_r23', ROOT / 'py' / 'winqa_probe.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize('raw,leaks', [
    ('err C:\\Users\\Jane Doe\\AppData x', ['Jane', 'Doe']), ('err /home/kris/x and /Users/amy/y', ['kris', 'amy']),
    ('err C:\\Users\\u0022Alice\\x', ['Alice']), ('POST https://api.invalid/v1?sig=abc failed', ['sig=abc']),
    ('auth sk-abcdefgh1234 Bearer tok123 api_key=zzz999', ['abcdefgh1234', 'tok123', 'zzz999'])])
def test_r23_probe_evidence_uses_redact_py(monkeypatch, tmp_path, raw, leaks):
    """R23 (Dong): winqa_probe.py output lands in check-*.json / failure.json in the evidence dir; it must use
    redact.py (one scrubber), not its own C:\\Users-only regex."""
    probe = _probe(monkeypatch, tmp_path)
    out = probe.redact(raw)
    assert out == _module('redact').scrub_diagnostic(raw)
    for leak in leaks:
        assert leak not in out, (leak, out)
    src = (ROOT / 'py' / 'winqa_probe.py').read_text(encoding='utf-8')
    assert 'def redact(' not in src and 'Users\\\\' not in src


def test_r23_run_winqa_uploads_redact_py_next_to_the_probe():
    sh = (ROOT / 'run_winqa.sh').read_text(encoding='utf-8')
    assert '"${SCP[@]}" "$HERE/redact.py" "$USER_@$HOST:C:/winqa/py/"' in sh


# ---------------- R24 (#213-#219): property guard with mutation self-proof, one scrubber, nothing raw kept ----------

PROP_NAMES = ['kris', 'Public', 'Default', '张三', 'Jane Doe', "D'Arcy", 'a_b', 'x.y', '<user>alice', 'u0022Al',
              'u003aBob', '%41nn', 'ｱソAl', 'Ünïco', 'a:b', 'a"b', 'émile', '😀xy', 'qa ']
PROP_ACCOUNTS = ['Administrator', 'Guest', 'DefaultAccount', 'WDAGUtilityAccount', 'runneradmin', 'root', 'ubuntu']
_NAME_POOLS = ['abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ', '0123456789', " '-_.~!@#$&()+,;=[]{}`^", ':"<>|',
               '张三李四王五赵六钱孙', 'éüñçøåßÉÖ', 'ｱｲｳソﾄ', '😀🎉', 'абвгдежзЖЯ']


def _random_names(seed, count=40):
    """R25 #246: user names are generated, not picked: any characters except separators, '%', CR/LF."""
    import random
    rnd = random.Random(seed)
    out = []
    while len(out) < count:
        n = ''.join(rnd.choice(rnd.choice(_NAME_POOLS)) for _ in range(rnd.randint(1, 24)))
        if n.strip('.') and n.strip() and n not in out:
            out.append(n)
    return out


PROP_SEED = int(os.environ.get('WINQA_PROP_SEED', '20261016'))
PROP_NAMES = PROP_NAMES + PROP_ACCOUNTS + _random_names(PROP_SEED)
PROP_TEMPLATES = ['C:\\Users\\{n}\\AppData\\x', 'c:/users/{n}/a.log', '/home/{n}/x', '/Users/{n}/y z', '/home/{n}',
                  'C:\\Users\\{n}', '\\\\srv\\c$\\Users\\{n}\\x', '"C:\\\\Users\\\\{n}\\\\a"', '%2Fhome%2F{n}%2Fx',
                  'C:%5CUsers%5C{n}%5Cx', '\\u002fhome\\u002f{n}\\u002fx', '%252Fhome%252F{n}%252Fx',
                  'C:\\u005cUsers\\u005c{n}\\u005cx']
PROP_PREFIXES = ['', ' ', '启动失败', '_', '"', "'", '(', '错误：', 'x.', 'a-', '-']
PROP_POSIX_ONLY = [('/home/{n}/x', 'A\\B'), ('/Users/{n}/x', 'A\\u005cB')]


def _leak_tokens(name):
    return [t for t in re.split(r'[^0-9A-Za-z\u00c0-\uffff]+', name.replace('<user>', ' ')) if len(t) >= 2]


def _property_violations(redact, first=False):
    """Generated and listed user names, the listed root spellings and left contexts: the path keeps its shape and
    the name is gone."""
    bad = []
    cases = [(t, n, p) for t in PROP_TEMPLATES for n in PROP_NAMES for p in PROP_PREFIXES]
    cases += [(t, n, p) for t, n in PROP_POSIX_ONLY for p in PROP_PREFIXES]
    for tpl, name, pre in cases:
        raw, want = pre + tpl.format(n=name), pre + tpl.format(n='<user>')
        out = redact.scrub_homes(raw)
        if tpl.endswith('{n}') or tpl.endswith('{n}"'):
            ok = out.startswith(pre + tpl.split('{n}')[0]) and '<user>' in out
        else:
            ok = out == want
        leaked = [t for t in _leak_tokens(name) if t in out.replace('<user>', '')]
        if not ok or leaked or redact.scrub_homes(out) != out:
            bad.append((raw, out, leaked))
            if first:
                break
    return bad


def test_r24_217_property_any_name_any_context_is_masked():
    bad = _property_violations(_module('redact'))
    assert not bad, bad[:5]


REDACT_MUTATIONS = {   # name: (anchor, replacement) — each re-adds a per-sample special case or drops a rule
    'skip-public': ("        return (max(st[t], s), en[e - 1]) if e > t else None",
                    "        if ''.join(ch[t:e]).lower() == 'public':\n            return None\n"
                    "        return (max(st[t], s), en[e - 1]) if e > t else None"),
    'quote-cut': ("        while e < n and ch[e] not in seps and ch[e] not in _EOL:",
                  "        while e < n and ch[e] not in seps and ch[e] not in _EOL and ch[e] != \"'\":"),
    'user-prefix-exempt': ("            seg = _segment(v, s, seps, (s, seps) in own)",
                           "            if text.startswith(USER, s):\n                continue\n"
                           "            seg = _segment(v, s, seps, (s, seps) in own)"),
    'unicode-word-boundary': ("if prev and prev.isascii() and prev.isalnum():",
                              "if prev and (prev.isalnum() or prev in '_.-'):"),
    'skip-administrator': ("        return (max(st[t], s), en[e - 1]) if e > t else None",
                           "        if ''.join(ch[t:e]).lower() == 'administrator':\n            return None\n"
                           "        return (max(st[t], s), en[e - 1]) if e > t else None"),
    'skip-long-names': ("        return (max(st[t], s), en[e - 1]) if e > t else None",
                        "        if e - t > 16:\n            return None\n"
                        "        return (max(st[t], s), en[e - 1]) if e > t else None"),
    'skip-digits': ("        return (max(st[t], s), en[e - 1]) if e > t else None",
                    "        if any(c.isdigit() for c in ch[t:e]):\n            return None\n"
                    "        return (max(st[t], s), en[e - 1]) if e > t else None"),
    'dot-dash-exempt': ("if prev and prev.isascii() and prev.isalnum():",
                        "if prev and prev.isascii() and (prev.isalnum() or prev in '.-'):"),
    'no-decoded-view': ("    return out + [dec]", "    return out"),
    'posix-stops-at-backslash': ("_WIN_SEPS, _POSIX_SEPS = '\\\\/', '/'", "_WIN_SEPS, _POSIX_SEPS = '\\\\/', '/\\\\'"),
    'no-percent': ("        if ch[i] == '%':", "        if False:"),
    'no-unc-drive': ("in ':$':", "in ':':"),
    'colon-stops-name': ("        while e < n and ch[e] not in seps and ch[e] not in _EOL:",
                         "        while e < n and ch[e] not in seps and ch[e] not in _EOL and ch[e] != ':':"),
}


def _mutant(name):
    import types
    src = (ROOT / 'redact.py').read_text(encoding='utf-8')
    anchor, repl = REDACT_MUTATIONS[name]
    assert anchor in src, f'mutation anchor moved: {name}'
    mod = types.ModuleType(f'redact_mut_{name.replace("-", "_")}')
    exec(compile(src.replace(anchor, repl, 1), mod.__name__, 'exec'), mod.__dict__)
    return mod


@pytest.mark.parametrize('mutation', sorted(REDACT_MUTATIONS))
def test_r24_217_property_guard_catches_special_case_mutations(mutation):
    """R24 #217: the guard is behavioural; re-adding a per-sample special case must make it fail."""
    assert _property_violations(_mutant(mutation), first=True), f'mutation {mutation} survived the property guard'


SCRUB_CODE = re.compile(
    r"""(?i)(?:\bre\.(?:sub|subn|compile|search|findall|finditer|match|fullmatch|split)\(|-c?replace\b|\bsed\b|"""
    r"""\.replace\(|\btr\s).*(?:users|home|userprofile|username|sk-|bearer|api_?key|authorization|\btokens?\b|"""
    r"""\\\?|\?\.\*)|<user>|<url>|['"]\*\*\*['"]|sk-\*\*\*|r['"][^'"\n]*(?:Users|home)[^'"\n]*(?:\[\^|\\\\\[|\+|\*)""")
CODE_SUFFIXES = ('.py', '.sh', '.ps1', '.psm1', '.bat', '.cmd', '.js', '')
REDACT_EXEMPT = 'redact.py'   # the one exempt file, as an exact path relative to the scanned tree


def _scrub_code_outside_redact(root):
    """Lines that look like a scrubbing rule (regex/-replace/sed/replace with a home, key or query token, a mask
    literal, or a home regex in a raw string) in any code file of the tree, except the exact path redact.py."""
    hits = []
    for p in sorted(root.rglob('*')):
        rel = p.relative_to(root).as_posix()
        if not p.is_file() or rel == REDACT_EXEMPT or p.suffix not in CODE_SUFFIXES or '__pycache__' in rel \
                or rel.startswith('tests/'):   # the harness's own tests hold planted samples, not shipped code
            continue
        for i, line in enumerate(p.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            if SCRUB_CODE.search(line) and not line.lstrip().startswith('#'):
                hits.append(f'{rel}:{i}: {line.strip()}')
    return hits


PLANTED_SCRUBBERS = ["t = re.sub(r'(?i)(bearer\\s+)[A-Za-z0-9._-]{8,}', r'\\1***', t)",
                     "p = str(h).replace(os.environ.get('USERNAME', '~'), '<user>')",
                     "find . | xargs sed -i -E 's/sk-[a-z]+/x/'",
                     "return re.sub(r'C:\\\\Users\\\\[^\\\\]+', 'X', text)",
                     "'final_url': re.sub(r'\\?.*', '', u.url)",                       # R25 #247: probe:209
                     "HOME_RX = r'/home/[^/]+'",                                         # variable regex ...
                     "t = HOME_RX.sub('x', t); u = re.sub(home_rx, 'x', u)",              # ... and its use
                     "$t = $t -replace [regex]::Escape($env:USERPROFILE), '~'",           # PowerShell -replace
                     "$s = $s -creplace 'Bearer \\S+', 'x'"]


def test_r24_216_only_redact_py_scrubs(tmp_path):
    """R24 #216 / R25 #247: no scrubbing rule anywhere under scripts/winqa except the exact file redact.py; the
    scanner proves itself on planted samples, including in a file that is merely named redact.py elsewhere."""
    assert _scrub_code_outside_redact(ROOT) == []
    planted = tmp_path / 'w'
    (planted / 'py').mkdir(parents=True)
    for i, line in enumerate(PLANTED_SCRUBBERS):
        ext = 'sh' if 'sed' in line else 'ps1' if line.startswith('$') else 'py'
        (planted / 'py' / f'm{i}.{ext}').write_text(line + '\n', encoding='utf-8')
    (planted / 'py' / 'redact.py').write_text(PLANTED_SCRUBBERS[0] + '\n', encoding='utf-8')   # name is not enough
    (planted / REDACT_EXEMPT).write_text(PLANTED_SCRUBBERS[0] + '\n', encoding='utf-8')
    hits = _scrub_code_outside_redact(planted)
    assert len(hits) == len(PLANTED_SCRUBBERS) + 1, hits


def _load(path, monkeypatch, tmp_path, name):
    pytest.importorskip('requests')
    import importlib.util
    monkeypatch.setenv('APPDATA', str(tmp_path))
    monkeypatch.setenv('WINQA_OUT', str(tmp_path / 'out'))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RAW_EVIDENCE = {'body': {'detail': 'open C:\\Users\\kris\\AppData failed', 'cwd': '/Users/kris/x'},
                'C:\\Users\\kris\\k': ['https://s.invalid/z?sig=SIG1', {'err': 'Authorization: Bearer abcdefgh123'}],
                'updater_error': "HTTPSConnectionPool: /home/kris/.cache sk-abcdefghijk", 'api_key_masked': 'sk-…xyz'}
RAW_TOKENS = ('kris', 'SIG1', 'abcdefgh123', 'abcdefghijk', 'xyz')


@pytest.mark.parametrize('script', ['winqa_probe.py', 'winqa_real.py'])
def test_r24_215_216_save_scrubs_the_whole_value_before_writing(monkeypatch, tmp_path, script):
    mod = _load(ROOT / 'py' / script, monkeypatch, tmp_path, 'r24_' + script[:-3])
    mod.OUT = tmp_path / 'ev'
    mod.OUT.mkdir()
    if script == 'winqa_real.py':
        mod.SECRETS.append('qa-real-key-1234567890')
        RAW = dict(RAW_EVIDENCE, echoed='key=qa-real-key-1234567890')
    else:
        RAW = RAW_EVIDENCE
    mod.save('e.json', RAW)
    text = (mod.OUT / 'e.json').read_text(encoding='utf-8')
    json.loads(text)
    for tok in RAW_TOKENS + ('qa-real-key',):
        assert tok not in text, (tok, text)
    assert mod.scrub_text('x C:\\Users\\kris\\y') if script == 'winqa_real.py' else True


def test_r24_214_mixed_utf8_and_utf16_runs_are_both_masked(tmp_path):
    """R24 #214: PS 5.1 `>>` appends UTF-16LE to a UTF-8 log (and the reverse); every run is masked."""
    redact = _module('redact')
    u8 = 'start 启动 /Users/kris/a\r\n'.encode('utf-8')
    u16 = 'C:\\Users\\bob\\x\r\n'.encode('utf-16-le')
    files = {'u8u16.log': u8 + u16, 'u8u16odd.log': u8 + b'!' + u16, 'u16u8.log': u16 * 6 + u8,
             'u16u8odd.log': u16 * 6 + b'!' + u8 + b'!'}
    for name, raw in files.items():
        (tmp_path / name).write_bytes(raw)
    _scrub_stream_files(tmp_path)
    for name in files:
        out = (tmp_path / name).read_bytes()
        for leak in (b'kris', 'kris'.encode('utf-16-le'), b'bob', 'bob'.encode('utf-16-le'), 'bob'.encode('utf-16-le')[1:]):
            assert leak not in out, (name, leak, out)
    p = subprocess.run(SH_REDACT, input=files['u8u16odd.log'], capture_output=True)
    assert p.returncode == 0 and b'kris' not in p.stdout and 'bob'.encode('utf-16-le') not in p.stdout




# ---- end to end: run_winqa.sh export boundary -> test_winqa_export.py (R27 rewrite; the R24/R25 pull-then-scrub
# harness and its test_r24_215 were removed with that design) ----

def _winqa_env(tmp_path, mode):
    from _winqa_helpers import _env
    return _env(tmp_path, '' if mode == 'vm-python' else mode)


def _stage_root(tmp_path):
    return tmp_path / 'home' / '.cache' / 'autoclip-winqa-stage'


@pytestmark_bash
@pytest.mark.parametrize('bash', BASHES)
def test_r24_stale_stage_from_killed_run_is_removed_and_stage_is_700(tmp_path, bash):
    """Dong + R25 #248: leftovers of a killed run are deleted before starting: dead pid, old unnumbered form, pid
    reused by a program that is not run_winqa, older than 24 h, and legacy dirs under $TMPDIR. The staging root does
    not depend on $TMPDIR (changed here between runs); the staging dir is mode 700 (seen from inside the run)."""
    env, args = _winqa_env(tmp_path, 'vm-python')
    tmpd, root = tmp_path / 'tmp', _stage_root(tmp_path)
    root.mkdir(parents=True)
    dead = subprocess.Popen(['true']); dead.wait()
    other = subprocess.Popen(['sleep', '60'])                                   # alive, but not run_winqa
    live_run = subprocess.Popen(['bash', '-c', 'exec -a run_winqa.sh sleep 60'])
    try:
        stale = [root / f'winqa-stage.{dead.pid}.abcdef', root / 'winqa-stage.Xy12ab',
                 root / f'winqa-stage.{other.pid}.reused', root / f'winqa-stage.{live_run.pid}.old24h',
                 tmpd / f'winqa-stage.{dead.pid}.legacy']
        for d in stale:
            d.mkdir()
            (d / 'env.json').write_text('{"home": "C:\\\\Users\\\\kris"}')
        old = time.time() - 25 * 3600
        os.utime(root / f'winqa-stage.{live_run.pid}.old24h', (old, old))
        live = root / f'winqa-stage.{live_run.pid}.keep12'   # a run that is still alive is left alone
        live.mkdir()
        modes = tmp_path / 'modes.txt'   # the fake scp records the mode of every download target dir
        env['TMPDIR'] = str(tmp_path / 'tmp2')
        (tmp_path / 'tmp2').mkdir()
        env_old = dict(env, TMPDIR=str(tmpd))
        done = subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env, capture_output=True, timeout=120)
        assert [d for d in stale if d.exists() and d.parent == root] == [], done.stdout[-400:]
        assert live.exists()
        got = modes.read_text().split()
        assert got and set(got) == {'700'}, got   # $STAGE/b, where the bundle lands
        assert not [p for p in root.glob('winqa-stage.*') if p != live]
        subprocess.run([bash, str(ROOT / 'run_winqa.sh')] + args, env=env_old, capture_output=True, timeout=120)
        assert not stale[-1].exists(), 'legacy dir under $TMPDIR is swept too'
    finally:
        other.kill(); live_run.kill()


# ---------------- R25 (#242-#250) ----------------

def test_r25_242_bom_file_also_gets_mixed_encoding_readings(tmp_path):
    """R25 #242: a UTF-8 BOM file with an appended UTF-16LE run (PS 5.1 `>>`) leaks nothing; same for a UTF-16 BOM
    file with a UTF-8 run."""
    redact = _module('redact')
    u16 = 'C:\\Users\\bob\\x\r\n'.encode('utf-16-le')
    files = {'bom8.log': b'\xef\xbb\xbf' + 'start /Users/kris/a\r\n'.encode() + u16,
             'bom8odd.log': b'\xef\xbb\xbf' + b'start!' + u16,
             'bom16.log': b'\xff\xfe' + 'C:\\Users\\amy\\y\r\n'.encode('utf-16-le') + b'tail /home/kris/z\n'}
    for name, raw in files.items():
        (tmp_path / name).write_bytes(raw)
    _scrub_stream_files(tmp_path)
    for name in files:
        out = (tmp_path / name).read_bytes()
        for w in ('kris', 'bob', 'amy'):
            for leak in (w.encode(), w.encode('utf-16-le'), w.encode('utf-16-le')[1:]):
                assert leak not in out, (name, leak, out)
        assert out[:2] in (b'\xef\xbb', b'\xff\xfe')


R25_SECRET_JSON = {'api_key': 'qa-plain-value-1', 'Authorization': 'Token abc-def-ghi', 'access_token': 'at.1.2',
                   'refresh_token': 'rt-xyz', 'token': 'tok-777', 'client_secret': 'cs-888', 'password': 'pw-999',
                   'Cookie': 'sid=s3ss10n', 'x-api-key': 'xk-111', 'nested': [{'apiKey': 'ak-222'}],
                   'note': 'plain text stays', 'tokens_used': 42}


def test_r25_243_json_values_masked_by_field_name(tmp_path):
    """R25 #243: credential fields are masked by name whatever their value looks like (structured save and file
    mode); other fields keep their values; the result stays valid JSON."""
    redact = _module('redact')
    obj = redact.scrub_obj(R25_SECRET_JSON)
    (tmp_path / 'e.json').write_text(json.dumps(R25_SECRET_JSON), encoding='utf-8')
    _scrub_stream_files(tmp_path)
    from_file = json.loads((tmp_path / 'e.json').read_text(encoding='utf-8'))
    for got in (obj, from_file):
        text = json.dumps(got)
        for v in ('qa-plain-value-1', 'abc-def-ghi', 'at.1.2', 'rt-xyz', 'tok-777', 'cs-888', 'pw-999', 's3ss10n',
                  'xk-111', 'ak-222'):
            assert v not in text, (v, text)
        assert got['note'] == 'plain text stays' and got['tokens_used'] == 42


def test_r25_244_directory_mode_masks_urls(tmp_path):
    """R25 #244: one rule table: file/directory mode masks URLs like the stream modes."""
    redact = _module('redact')
    (tmp_path / 'a.log').write_text('GET https://oss.invalid/f?Signature=SIG1&x=1 done\n', encoding='utf-8')
    _scrub_stream_files(tmp_path)
    assert (tmp_path / 'a.log').read_text(encoding='utf-8') == 'GET <url> done\n'
    assert redact.scrub_obj({'u': 'http://h.invalid/p?t=SIG2'}) == {'u': '<url>'}
    assert redact.scrub('see https://x.invalid/?k=1') == 'see <url>'






@pytest.mark.parametrize('raw,want', [
    ('x.C:\\Users\\kris\\a', 'x.C:\\Users\\<user>\\a'), ('a-/home/kris/b', 'a-/home/<user>/b'),
    ('v1.0-/Users/kris/c', 'v1.0-/Users/<user>/c'), ('-C:/Users/kris/d', '-C:/Users/<user>/d'),
    ('.C:\\Users\\kris', '.C:\\Users\\<user>'), ('see ./home/kris/x', 'see ./home/kris/x'),
    ('cd ../home/kris', 'cd ../home/kris'), ('api/home/kris', 'api/home/kris')])
def test_r25_250_dot_dash_before_root(raw, want):
    """R25 #250: '.' or '-' right before a root does not protect it; only POSIX relative ./ ../ paths (and a root
    continuing an ASCII word/path) are not roots."""
    assert _module('redact').scrub(raw) == want


def test_r25_247_probe_keeps_no_own_query_stripping():
    src = (ROOT / 'py' / 'winqa_probe.py').read_text(encoding='utf-8')
    assert "re.sub(r'\\?.*'" not in src


# ---------------- R26 (#251-#259) ----------------

R26_FIELD_TEXT = [('token=tv-111 next', 'tv-111'), ('Cookie: sid=cv-222; theme=dark', 'cv-222'),
                  ('Set-Cookie: a=sc-333; Path=/', 'sc-333'), ('"api_token": "at-444", "ok": 1', 'at-444'),
                  ('session_token: st-555', 'st-555'), ('secret_access_key=sk9-666', 'sk9-666'),
                  ('&sessionToken=ct-777&x=1', 'ct-777'), ("{'password': 8888}", '8888'),
                  ('x-api-key: xk-999 tail', 'xk-999'), ('"credentials": {"u": "cr-000"}', 'cr-000'),
                  ('Authorization: Token tk-aaa', 'tk-aaa')]
R26_FIELD_JSON = {'api_token': 'at-1', 'session_token': 'st-2', 'secret_access_key': 'sa-3', 'sessionToken': 'ss-4',
                  'pin': {'password': 5551}, 'credentials': {'u': 'cr-6'}, 'auth': {'refresh_token': ['rt-7']},
                  'tokens_used': 42, 'max_tokens': 9, 'note': 'kept'}


@pytest.mark.parametrize('raw,leak', R26_FIELD_TEXT)
def test_r26_255_text_lines_use_the_json_field_rule(tmp_path, raw, leak):
    """R26 #255: the credential-field rule is the same in text (.log, .jsonl, stdin, lines) as in JSON."""
    redact = _module('redact')
    assert leak not in redact.scrub(raw)
    for name in ('a.log', 'b.jsonl', 'c.txt'):
        (tmp_path / name).write_text(raw + '\n', encoding='utf-8')
    _scrub_stream_files(tmp_path)
    for name in ('a.log', 'b.jsonl', 'c.txt'):
        assert leak not in (tmp_path / name).read_text(encoding='utf-8'), name
    for mode in ('--stdin', '--lines'):
        p = subprocess.run([sys.executable, str(ROOT / 'redact.py'), mode], input=(raw + '\n').encode(), capture_output=True)
        assert p.returncode == 0 and leak.encode() not in p.stdout, (mode, p.stdout)


def test_r26_255_json_fields_any_value_type_and_more_names(tmp_path):
    redact = _module('redact')
    for got in (redact.scrub_obj(R26_FIELD_JSON),):
        text = json.dumps(got)
        for v in ('at-1', 'st-2', 'sa-3', 'ss-4', '5551', 'cr-6', 'rt-7'):
            assert v not in text, (v, text)
        assert got['tokens_used'] == 42 and got['max_tokens'] == 9 and got['note'] == 'kept'
