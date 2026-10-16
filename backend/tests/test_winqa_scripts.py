"""E9: the acceptance-machine puller must refuse an artifact without a digest (exit != 0)
before any download or ssh, and the exe provenance helper records installer sha256."""
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / 'scripts' / 'winqa'


def _bin(folder, name, body):
    path = folder / name
    path.write_text('#!/usr/bin/env bash\n' + body + '\n')
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run(tmp_path, digest):
    bins = tmp_path / 'bin'
    bins.mkdir()
    calls = tmp_path / 'calls.log'
    line = f'123 4096 {digest}'.rstrip()
    _bin(bins, 'gh', f'echo "gh $*" >> "{calls}"; if [ "$1" = api ]; then echo "{line}"; exit 0; fi; exit 1')
    for tool in ('ssh', 'scp', 'curl'):
        _bin(bins, tool, f'echo "{tool} $*" >> "{calls}"; exit 0')
    env = {**os.environ, 'PATH': f'{bins}:{os.environ["PATH"]}', 'WINQA_HOST': 'qa.invalid', 'WINQA_IDENTITY': str(tmp_path / 'id')}
    done = subprocess.run(['bash', str(ROOT / 'pull_run_installer.sh'), '999'], env=env, capture_output=True, text=True)
    return done, calls.read_text() if calls.exists() else ''


@pytest.mark.skipif(sys.platform == 'win32', reason='bash harness')
@pytest.mark.parametrize('digest', ['', 'null', 'sha256:', 'sha256:abc'])
def test_missing_or_invalid_digest_exits_nonzero_before_download(tmp_path, digest):
    done, calls = _run(tmp_path, digest)
    assert done.returncode == 4, done.stdout + done.stderr
    assert 'digest' in done.stderr
    assert 'ssh ' not in calls and 'scp ' not in calls and 'curl ' not in calls
    assert 'run download' not in calls


def test_powershell_side_refuses_missing_digest():
    source = (ROOT / 'ps' / 'pull_run_installer.ps1').read_text(encoding='utf-8')
    guard = source.index("$WantZip -notmatch '^[0-9a-f]{64}$'")
    assert guard < source.index('Get-Content -Raw $uf'), 'digest check must run before the URL is read'
    assert 'exit 4' in source[guard:guard + 200]


def test_no_hardcoded_host_or_token():
    text = '\n'.join(p.read_text(encoding='utf-8') for p in ROOT.rglob('*') if p.is_file() and p.suffix in ('.sh', '.ps1', '.py', '.md'))
    for needle in ('ghp_', 'github_pat_', '101.35.', 'BEGIN OPENSSH'):
        assert needle not in text


def test_exe_provenance_records_setup_sha256(tmp_path):
    sys.path.insert(0, str(ROOT))
    import exe_provenance
    (tmp_path / 'nsis').mkdir()
    exe = tmp_path / 'nsis' / 'AutoClip_1.5.8_x64-setup.exe'
    exe.write_bytes(b'installer')
    out = tmp_path / 'p.json'
    assert exe_provenance.main([str(tmp_path), str(out), '--run-id', '7']) == 0
    data = json.loads(out.read_text())
    assert data['assets'] == {exe.name: hashlib.sha256(b'installer').hexdigest()}
    empty = tmp_path / 'empty'
    empty.mkdir()
    with pytest.raises(SystemExit):
        exe_provenance.build(empty)
