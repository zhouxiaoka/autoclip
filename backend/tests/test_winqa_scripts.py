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


@pytest.mark.parametrize('indent', [None, 2])
def test_redact_json_with_escaped_chinese_names_stays_valid(tmp_path, indent):
    """R18 #85: ensure_ascii JSON writes 张三 as \\u5f20\\u4e09; it must be masked and still parse."""
    redact = _module('redact')
    doc = {'paths': ZH_JSON_CASES, 'nested': {'cwd': ZH_JSON_CASES[0] + ': denied'}, 'api_key_masked': 'sk-…abc', 'n': 3}
    raw = json.dumps(doc, indent=indent)   # ensure_ascii=True by default -> \\uXXXX escapes
    assert '\\u5f20' in raw
    (tmp_path / 'e.json').write_text(raw, encoding='utf-8')
    redact.main(str(tmp_path))
    out = (tmp_path / 'e.json').read_text(encoding='utf-8')
    data = json.loads(out)
    assert '张' not in out and '\\u5f20' not in out and '\\u4e09' not in out and '三' not in json.dumps(data, ensure_ascii=False)
    assert data['paths'] == ['/Users/<user>/AutoClipQA', '/home/<user>', 'C:\\Users\\<user>\\AppData', 'C:\\Users\\<user>\\x', 'c:/users/<user>/a.log']
    assert data['nested']['cwd'] == '/Users/<user>/AutoClipQA: denied'
    assert data['api_key_masked'] == '***' and data['n'] == 3


def test_redact_json_colliding_keys_are_all_kept(tmp_path):
    """R20 #119: two users' paths as keys scrub to one key; both entries must survive."""
    redact = _module('redact')
    doc = {'/Users/alice/a.log': 1, '/Users/bob/a.log': 2, '/Users/<user>/a.log#2': 3, 'other': 4}
    (tmp_path / 'e.json').write_text(json.dumps(doc), encoding='utf-8')
    redact.main(str(tmp_path))
    data = json.loads((tmp_path / 'e.json').read_text(encoding='utf-8'))
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
    redact.main(str(tmp_path))
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

def test_redact_json_with_bom_is_parsed(tmp_path):
    """R21 #131: a BOM must not make the JSON step fall back; BOM is kept on write."""
    redact = _module('redact')
    raw = '\ufeff{"p": "\\/Users\\/alice\\/x", "w": "\\/U\\u0073ers\\/bob"}'
    (tmp_path / 'e.json').write_bytes(raw.encode('utf-8'))
    redact.main(str(tmp_path))
    out = (tmp_path / 'e.json').read_bytes()
    assert out.startswith(b'\xef\xbb\xbf')
    assert json.loads(out.decode('utf-8-sig')) == {'p': '/Users/<user>/x', 'w': '/Users/<user>'}


@pytest.mark.parametrize('suffix', ['.log', '.json'])
def test_redact_non_utf8_file_is_replaced_bytewise(tmp_path, suffix):
    """R21 #128: GBK (or broken) bytes outside the masked name come back unchanged."""
    redact = _module('redact')
    head = '错误 C:\\Users\\'.encode('gbk')
    tail = '\\AppData 日志\r\n'.encode('gbk') + b'\xff\xfe raw\n'
    raw = head + b'kris' + tail
    (tmp_path / ('e' + suffix)).write_bytes(raw)
    redact.main(str(tmp_path))
    assert (tmp_path / ('e' + suffix)).read_bytes() == head + b'<user>' + tail


def test_redact_utf8_key_is_masked_in_byte_mode(tmp_path, monkeypatch):
    """Byte mode still masks the QA key and its masked form (matched as UTF-8 bytes)."""
    redact = _module('redact')
    key = 'sk-' + 'q' * 20 + 'Z9x'
    monkeypatch.setenv('WINQA_MODEL_API_KEY', key)
    raw = ('k=' + key + ' m=' + key[:3] + '…' + key[-3:] + ' ').encode('utf-8') + b'\xff'
    (tmp_path / 'e.log').write_bytes(raw)
    redact.main(str(tmp_path))
    assert (tmp_path / 'e.log').read_bytes() == b'k=*** m=*** \xff'


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
    redact.main(str(tmp_path))
    assert (tmp_path / 'e.log').read_bytes() == '错误 '.encode('gbk') + pre + b'<user>' + suf + b'\r\n'


@pytest.mark.parametrize('name', GBK_5C_NAMES)
def test_redact_stdin_gbk_name_with_5c_trail_byte(name):
    raw = 'C:\\Users\\'.encode('gbk') + name.encode('gbk') + '\\AppData 日志 https://x.invalid/s?sig=1\n'.encode('gbk')
    p = subprocess.run([sys.executable, str(ROOT / 'redact.py'), '--stdin'], input=raw, capture_output=True)
    assert p.returncode == 0, p.stderr
    assert p.stdout == 'C:\\Users\\<user>\\AppData 日志 <url>\n'.encode('gbk')


def test_redact_utf8_log_keeps_plain_rule(tmp_path):
    """UTF-8 logs are not read in GBK units: 张 (E5 BC A0) before '\\' must not swallow the separator."""
    redact = _module('redact')
    raw = 'C:\\Users\\张\\AppData\\x.log /home/乗/y\n'.encode('utf-8')
    (tmp_path / 'e.log').write_bytes(raw)
    redact.main(str(tmp_path))
    assert (tmp_path / 'e.log').read_bytes() == b'C:\\Users\\<user>\\AppData\\x.log /home/<user>/y\n'




# ---------------- R22: one implementation, one corpus (#129 #150-#156, SJIS/Big5) ----------------
# backend/tests/fixtures/winqa_redact_corpus.json holds every R16-R22 sample (input/expected). The same
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
    assert redact.scrub_stream_bytes(case['text'].encode('utf-8')) == redact.scrub_stream(case['text']).encode('utf-8')


@pytest.mark.parametrize('case', [c for c in CORPUS if not c.get('chains')], ids=[c['id'] for c in CORPUS if not c.get('chains')])
def test_corpus_files_every_encoding_and_line_ending(tmp_path, case):
    """#129 CRLF kept, #155 UTF-16, #149 GBK, SJIS/Big5: same expectation as text, original bytes elsewhere."""
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
            f = tmp_path / f'{label}{len(eol)}.log'
            f.write_bytes(raw)
            redact.main(str(tmp_path))
            assert f.read_bytes() == out, (label, repr(eol), f.read_bytes())
            f.unlink()
            tried += 1
    assert tried >= 4


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
    redact.main(str(tmp_path))
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
    redact.main(str(tmp_path))
    assert (tmp_path / 'e.log').read_bytes() == bom + 'C:\\Users\\<user>\\x\r\n'.encode(codec)
    assert json.loads((tmp_path / 'e.json').read_bytes()[2:].decode(codec)) == {'p': '/home/<user>/x'}


def test_redact_lone_surrogate_json_is_masked_and_does_not_stop_the_run(tmp_path):
    """R22 #156: '\\ud800' in JSON used to raise UnicodeEncodeError and stop every later file."""
    redact = _module('redact')
    (tmp_path / 'a.json').write_text('{"p": "\\ud800 /Users/bob/x"}', encoding='utf-8')
    (tmp_path / 'b.log').write_text('/Users/carol/x\n', encoding='utf-8')
    redact.main(str(tmp_path))
    out = (tmp_path / 'a.json').read_text(encoding='utf-8')
    assert '\\ud800' in out and 'bob' not in out and json.loads(out) == {'p': '\ud800 /Users/<user>/x'}
    assert (tmp_path / 'b.log').read_text(encoding='utf-8') == '/Users/<user>/x\n'


def test_redact_undecodable_file_is_reported_left_alone_and_others_continue(tmp_path, capsys):
    redact = _module('redact')
    bad = b'\xff\xfe' + '/Users/bob'.encode('utf-16-le') + b'\x00'   # odd-length UTF-16
    (tmp_path / 'a.log').write_bytes(bad)
    (tmp_path / 'b.log').write_text('/Users/carol/x\n', encoding='utf-8')
    with pytest.raises(SystemExit) as exc:
        redact.main(str(tmp_path))
    assert exc.value.code == 2
    assert (tmp_path / 'a.log').read_bytes() == bad
    assert (tmp_path / 'b.log').read_text(encoding='utf-8') == '/Users/<user>/x\n'
    assert 'a.log' in capsys.readouterr().err


def test_redact_has_one_home_implementation():
    """R22 code health: no home-directory regex and no per-encoding variants left in redact.py."""
    src = (ROOT / 'redact.py').read_text(encoding='utf-8')
    for gone in ('WIN_PATTERN', 'POSIX_PATTERN', 'NAME_GBK', '_mask(', 'gbk=', 'latin-1'):
        assert gone not in src


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

def test_r23_code_health_no_per_sample_branches():
    """R23: no quote rule, no <user>-prefix exemption, no implicit-escape branch, no stop-character sets."""
    src = (ROOT / 'redact.py').read_text(encoding='utf-8')
    for gone in ('implicit', '== "\'"', 'startswith(USER', '_WIN_STOP', '_POSIX_STOP', 'URL.sub'):
        assert gone not in src, gone
    assert "_WIN_SEPS, _POSIX_SEPS = '\\\\/', '/'" in src


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
    assert redact.scrub_stream_bytes(('a ' + raw + ' b').encode()) == b'a <url> b'


@pytest.mark.parametrize('name', ['ｱソAlice', 'ｶﾞソ太郎', 'ﾃｽﾄ表示'])
def test_r23_181_shift_jis_halfwidth_names_masked_whole(tmp_path, name):
    redact = _module('redact')
    raw = ('ログ C:\\Users\\' + name + '\\AppData\\x /home/' + name + '/y\r\n').encode('shift_jis')
    want = 'ログ C:\\Users\\<user>\\AppData\\x /home/<user>/y\r\n'.encode('shift_jis')
    (tmp_path / 'e.log').write_bytes(raw)
    redact.main(str(tmp_path))
    assert (tmp_path / 'e.log').read_bytes() == want
    p = subprocess.run(SH_REDACT, input=raw, capture_output=True)
    assert p.returncode == 0 and p.stdout == want


def _layered(text):
    """Reference: undo escapes by repeated full left-to-right passes (the R22 definition)."""
    hexd = set('0123456789abcdefABCDEF')
    ch = list(text)
    while True:
        out, i, changed = [], 0, False
        while i < len(ch):
            if ch[i] == '\\' and i + 1 < len(ch) and ch[i + 1] in '\\/':
                out.append(ch[i + 1]); i += 2; changed = True
            elif ch[i] == '\\' and i + 5 < len(ch) and ch[i + 1] == 'u' and all(x in hexd for x in ch[i + 2:i + 6]):
                out.append(chr(int(''.join(ch[i + 2:i + 6]), 16))); i += 6; changed = True
            else:
                out.append(ch[i]); i += 1
        ch = out
        if not changed:
            return ''.join(ch)


def test_r23_184_single_pass_decoder_equals_repeated_passes():
    import random
    rnd = random.Random(414)
    parts = ['\\', 'u', '0', '5', 'c', '2', 'f', '/', 'a', '\\u005c', '\\u0075', '4', '1', '\\\\']
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


def test_r23_188_read_or_write_error_on_one_file_does_not_stop_the_rest(tmp_path, monkeypatch, capsys):
    redact = _module('redact')
    (tmp_path / 'a.log').write_text('/Users/bob/x\n', encoding='utf-8')
    (tmp_path / 'b.log').write_text('/Users/carol/x\n', encoding='utf-8')
    real = Path.read_bytes

    def flaky(self):
        if self.name == 'a.log':
            raise PermissionError('denied')
        return real(self)
    monkeypatch.setattr(Path, 'read_bytes', flaky)
    with pytest.raises(SystemExit) as exc:
        redact.main(str(tmp_path))
    assert exc.value.code == 2
    assert (tmp_path / 'b.log').read_text(encoding='utf-8') == '/Users/<user>/x\n'
    assert 'a.log' in capsys.readouterr().err


@pytest.mark.parametrize('codec', ['utf-16-le', 'utf-16-be'])
def test_r23_190_utf16_without_bom_is_masked_and_written_back(tmp_path, codec):
    redact = _module('redact')
    (tmp_path / 'e.log').write_bytes('C:\\Users\\kris\\x /home/bob/y\r\n'.encode(codec))
    redact.main(str(tmp_path))
    assert (tmp_path / 'e.log').read_bytes() == 'C:\\Users\\<user>\\x /home/<user>/y\r\n'.encode(codec)
    assert redact.scrub_stream_bytes('/Users/kris/x'.encode(codec)) == '/Users/<user>/x'.encode(codec)


def test_r23_192_inexact_round_trip_is_refused_and_file_kept(tmp_path, monkeypatch, capsys):
    """R23 #192: a reading that does not map back to the same bytes must leave the file untouched."""
    redact = _module('redact')
    monkeypatch.setattr(redact, '_FALLBACK', ('gb18030', 'replace'))   # lossy on purpose: \xff -> U+FFFD
    bad = b'\xff C:\\Users\\kris\\x\n'
    (tmp_path / 'a.log').write_bytes(bad)
    with pytest.raises(SystemExit) as exc:
        redact.main(str(tmp_path))
    assert exc.value.code == 2
    assert (tmp_path / 'a.log').read_bytes() == bad
    assert 'a.log' in capsys.readouterr().err
    with pytest.raises(ValueError):
        redact.scrub_stream_bytes(bad)


def test_r23_187_stdin_error_prints_nothing_and_exits_non_zero():
    bad = b'\xff\xfe' + '/Users/bob'.encode('utf-16-le') + b'\x00'
    p = subprocess.run(SH_REDACT, input=bad, capture_output=True)
    assert p.returncode != 0 and p.stdout == b''
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
    """R23 #187: undecodable output (odd-length UTF-16 on stderr) makes redact fail: nothing raw is printed and
    the script exits non-zero (8 if the run itself succeeded, else the run's own code)."""
    _run(tmp_path, bash)
    bins = tmp_path / 'bin'
    payload = (b'\xff\xfe' + '/Users/bob'.encode('utf-16-le') + b'\x00')
    (tmp_path / 'bad.bin').write_bytes(payload)
    _bin(bins, 'ssh', 'case "$*" in\n  *pull_run_installer.ps1*) cat "' + str(tmp_path / 'bad.bin') + '" >&2; exit '
         + str(remote_rc) + ';;\nesac; exit 0')
    done = subprocess.run([bash, str(SH), '999'], env=_sh_env(tmp_path), capture_output=True)
    assert done.returncode == (8 if remote_rc == 0 else remote_rc), done.stderr
    assert '脱敏失败'.encode() in done.stderr and b'Traceback' not in done.stderr
    assert b'b\x00o\x00b' not in done.stdout + done.stderr


def test_r23_193_readme_keeps_the_harness_documentation():
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    for kept in ('run_winqa.sh', '每次运行都会先卸载 AutoClip 并删除用户数据', '仍需人工 / 界面的部分', 'WINQA_MODEL_API_KEY',
                 '验收机拉包脚本（E9）', '测试依赖（必需）'):
        assert kept in text, kept
