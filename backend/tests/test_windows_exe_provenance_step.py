"""#417: the inline pwsh step "Record Windows installer sha256" in desktop-build.yml must write exactly the bytes
the former scripts/winqa/exe_provenance.py (#414) wrote on the Windows runner, and fail closed where it was lax.

Reference: fixtures/exe_provenance_ref_414.py is a verbatim copy of exe_provenance.py from #414. On Windows its
Path.write_text(..., encoding='utf-8') writes in text mode, so every "\\n" becomes "\\r\\n" and there is no BOM;
reference() reproduces that with newline='\\r\\n'. Byte identity is claimed for ASCII installer names only.
Deliberate differences (fail instead of the original's silent behaviour): duplicate names (original kept the last
one), empty sha (original wrote ""); new checks: non-ASCII names, installer count != nsis bundle targets in
src-tauri/tauri.windows.conf.json. Hidden entries: Windows' hidden attribute cannot be set on Linux, so the
samples cover dot-files and dot-directories, which pwsh hides on Unix without -Force the same way.

The step is run with a real pwsh. In CI (CI env set) a missing pwsh is an error, never a skip.
"""
import importlib.util
import io
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github' / 'workflows' / 'desktop-build.yml'
REF = Path(__file__).resolve().parent / 'fixtures' / 'exe_provenance_ref_414.py'
NSIS = Path('src-tauri/target/release/bundle/nsis')
RUN_ID, SHA = '18555123456', '0123456789abcdef0123456789abcdef01234567'
PWSH = shutil.which('pwsh')
if not PWSH:
    if os.environ.get('CI'):
        raise RuntimeError('pwsh is required in CI for the Windows provenance step test (no silent skip)')
    pytest.skip('pwsh not installed', allow_module_level=True)

_spec = importlib.util.spec_from_file_location('exe_provenance_ref_414', REF)
ref_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ref_mod)


def step_script(text: str | None = None) -> str:
    lines = (text if text is not None else WORKFLOW.read_text(encoding='utf-8')).splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == '- name: Record Windows installer sha256')
    run = next(i for i in range(start, len(lines)) if lines[i].strip() == 'run: |')
    assert any(lines[i].strip() == 'shell: pwsh' for i in range(start, run))
    body, indent = [], None
    for line in lines[run + 1:]:
        if line.strip() and indent is None:
            indent = len(line) - len(line.lstrip())
        if line.strip() and len(line) - len(line.lstrip()) < indent:
            break
        body.append(line[indent:] if line.strip() else '')
    return '\n'.join(body).rstrip('\n') + '\n'


def reference(tmp_path: Path) -> bytes:
    """Run the #414 script's own main() with Windows text-mode newline translation."""
    out = io.BytesIO()
    real = Path.write_text

    def windows_write_text(self, data, encoding=None, errors=None, newline=None):
        # Text mode on Windows: newline=None translates '\n' to os.linesep ('\r\n'); utf-8 codec adds no BOM.
        out.write(data.replace('\n', '\r\n').encode(encoding))

    Path.write_text = windows_write_text
    try:
        assert ref_mod.main([str(tmp_path / NSIS), 'unused.json', '--run-id', RUN_ID, '--commit', SHA]) == 0
    finally:
        Path.write_text = real
    return out.getvalue()


REAL_CONF = ROOT / 'src-tauri' / 'tauri.windows.conf.json'


def run_step(tmp_path, files, env_extra=None, script_text=None, nsis_targets=None):
    conf = tmp_path / 'src-tauri' / 'tauri.windows.conf.json'
    conf.parent.mkdir(parents=True, exist_ok=True)
    if nsis_targets is None:
        shutil.copyfile(REAL_CONF, conf)
    else:
        conf.write_text(json.dumps({'bundle': {'targets': ['nsis'] * nsis_targets}}), encoding='utf-8')
    for rel, data in files.items():
        p = tmp_path / NSIS / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    script = tmp_path / 'step.ps1'
    script.write_text(script_text or step_script(), encoding='utf-8')
    env = {**os.environ, 'GITHUB_RUN_ID': RUN_ID, 'GITHUB_SHA': SHA, **(env_extra or {})}
    return subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-File', str(script)], cwd=tmp_path, env=env,
                          capture_output=True, text=True, timeout=120)


OK_SAMPLES = {
    'single': {'AutoClip_1.5.7_x64-setup.exe': b'one'},
    'multiple-nested': {'AutoClip_1.5.7_x64-setup.exe': b'a', 'beta-setup.exe': b'b', 'sub/Zed-setup.exe': b'c',
                        'sub/deep/_x-setup.exe': b'd'},
    'mixed-case': {'a_lower-setup.exe': b'1', 'B_upper-setup.exe': b'2', 'A_upper-setup.exe': b'3', 'b-setup.exe': b'4',
                   'sub/Ab-setup.exe': b'5', 'aB-setup.exe': b'6'},
    'hidden-dot-entries': {'.hidden/A-setup.exe': b'h', '.B-setup.exe': b'dot', 'C-setup.exe': b'c'},
    'json-specials': {"it's & {x} =+ ~ ! @ # $ % ^ ( ) [ ] ; , -setup.exe": b'q', 'tab and space-setup.exe': b's'},
    'other-files-ignored': {'AutoClip-setup.exe': b'x', 'notes.txt': b'ignored', 'AutoClip.msi': b'ignored',
                            'AutoClip-setup.exe.sig': b'sig'},
}


@pytest.mark.parametrize('files', list(OK_SAMPLES.values()), ids=list(OK_SAMPLES))
def test_step_output_is_byte_identical_to_exe_provenance_py(tmp_path, files):
    count = sum(1 for k in files if k.endswith('-setup.exe'))
    done = run_step(tmp_path, files, nsis_targets=count)
    assert done.returncode == 0, done.stderr
    got = (tmp_path / 'windows-exe-provenance.json').read_bytes()
    want = reference(tmp_path)
    assert want.endswith(b'}\r\n') and b'\n' not in want.replace(b'\r\n', b'') and not want.startswith(b'\xef\xbb\xbf')
    assert len(json.loads(want)['assets']) == count
    assert got == want


def test_real_tauri_config_expects_one_installer(tmp_path):
    done = run_step(tmp_path, {'AutoClip_1.5.7_x64-setup.exe': b'one'})
    assert done.returncode == 0, done.stderr
    assert (tmp_path / 'windows-exe-provenance.json').read_bytes() == reference(tmp_path)


@pytest.mark.parametrize('files,env,message', [
    ({'AutoClip-setup.exe': b'1', 'sub/AutoClip-setup.exe': b'2'}, None, 'duplicate installer name'),
    ({'notes.txt': b'x'}, None, 'no *-setup.exe'),
    ({}, None, ''),
    ({'AutoClip-setup.exe': b'1'}, {'GITHUB_RUN_ID': ''}, 'GITHUB_RUN_ID'),
    ({'AutoClip-setup.exe': b'1'}, {'GITHUB_RUN_ID': 'abc'}, 'GITHUB_RUN_ID'),
    ({'AutoClip-setup.exe': b'1'}, {'GITHUB_SHA': ''}, 'GITHUB_SHA'),
    ({'剪辑助手_1.5.7_x64-setup.exe': b'zh'}, None, 'non-ASCII installer name'),
    ({'🎬-setup.exe': b'emoji', 'A-setup.exe': b'a'}, None, 'non-ASCII installer name'),
    ({'e\u0301-setup.exe': b'nfd', '\u00e9-setup.exe': b'nfc'}, None, 'non-ASCII installer name'),
    ({'.hidden/\u00e9-setup.exe': b'h'}, None, 'non-ASCII installer name'),
    ({'a\x7f-setup.exe': b'del'}, None, 'non-ASCII installer name'),
], ids=['duplicate-name', 'no-exe', 'no-bundle-dir', 'missing-run-id', 'bad-run-id', 'missing-sha', 'chinese', 'emoji', 'nfc-nfd', 'hidden-non-ascii', 'del-char'])
def test_step_fails_closed(tmp_path, files, env, message):
    done = run_step(tmp_path, files, env, nsis_targets=max(1, len(files)))
    assert done.returncode != 0
    assert message in done.stderr + done.stdout
    assert not (tmp_path / 'windows-exe-provenance.json').exists()


def test_step_keeps_artifact_contract():
    text = WORKFLOW.read_text(encoding='utf-8')
    script = step_script(text)
    assert 'scripts/winqa' not in script and 'python' not in script and 'secrets.' not in script
    assert "'windows-exe-provenance.json'" in script
    assert 'name: internal-desktop-provenance-windows-x64' in text and 'path: windows-exe-provenance.json' in text


@pytest.mark.parametrize('files,targets', [
    ({'A-setup.exe': b'1', 'B-setup.exe': b'2'}, None),
    ({'A-setup.exe': b'1', '.hidden/B-setup.exe': b'2'}, None),
    ({'A-setup.exe': b'1'}, 2),
], ids=['extra-installer', 'extra-hidden-installer', 'missing-installer'])
def test_installer_count_must_match_nsis_targets(tmp_path, files, targets):
    done = run_step(tmp_path, files, nsis_targets=targets)
    assert done.returncode != 0
    assert 'expected' in done.stderr + done.stdout
    assert not (tmp_path / 'windows-exe-provenance.json').exists()


def test_no_nsis_target_fails(tmp_path):
    done = run_step(tmp_path, {'A-setup.exe': b'1'}, nsis_targets=0)
    assert done.returncode != 0 and 'no nsis target' in done.stderr + done.stdout
