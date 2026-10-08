"""Windows NSIS hooks (RC156 Win QA #2, #4): static checks, no Windows needed.

The Tauri 2 template runs NSIS_HOOK_PREINSTALL / PREUNINSTALL *before* its own
CheckIfAppIsRunning. The hooks must therefore confirm the app has exited before they
kill the bundled backend, and only then clear the stale backend sources. The real
behaviour is covered by scripts/windows_upgrade_smoke.ps1 and the Windows QA VM.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / 'src-tauri' / 'windows' / 'installer-hooks.nsh'
SMOKE = ROOT / 'scripts' / 'windows_upgrade_smoke.ps1'


def _code(text):
    return '\n'.join(line.split(';', 1)[0].rstrip() for line in text.splitlines() if not line.lstrip().startswith(';'))


def _macro(name):
    match = re.search(rf'^!macro {name}\b.*?$(.*?)^!macroend', _code(HOOKS.read_text(encoding='utf-8')), re.M | re.S)
    assert match, name
    return [line.strip() for line in match.group(1).splitlines() if line.strip()]


def test_tauri_config_uses_these_hooks():
    config = json.loads((ROOT / 'src-tauri' / 'tauri.windows.conf.json').read_text(encoding='utf-8'))
    assert config['bundle']['windows']['nsis']['installerHooks'] == 'windows/installer-hooks.nsh'
    assert config['bundle']['resources']['resources/backend'] == 'resources/backend'


def test_preinstall_checks_the_app_before_killing_the_backend_then_clears_old_sources():
    body = _macro('NSIS_HOOK_PREINSTALL')
    assert body == [
        '!insertmacro CheckIfAppIsRunning "$INSTDIR\\${MAINBINARYNAME}.exe" "${PRODUCTNAME}"',
        '!insertmacro AUTOCLIP_KILL_BUNDLED_PROCESSES',
        '!insertmacro AUTOCLIP_REMOVE_OLD_BACKEND',
    ]


def test_preuninstall_checks_the_app_before_killing_the_backend():
    assert _macro('NSIS_HOOK_PREUNINSTALL') == [
        '!insertmacro CheckIfAppIsRunning "$INSTDIR\\${MAINBINARYNAME}.exe" "${PRODUCTNAME}"',
        '!insertmacro AUTOCLIP_KILL_BUNDLED_PROCESSES',
    ]


def test_only_the_installed_backend_sources_are_removed():
    body = _macro('AUTOCLIP_REMOVE_OLD_BACKEND')
    removals = [line for line in body if line.startswith(('RMDir', 'Delete'))]
    assert removals == ['RMDir /r "$INSTDIR\\resources\\backend"']
    assert '${If} "$INSTDIR" != ""' in body
    code = _code(HOOKS.read_text(encoding='utf-8'))
    for user_location in ('$APPDATA', '$LOCALAPPDATA', '$PROFILE', '$DOCUMENTS', 'resources\\python"'):
        assert user_location not in code
    assert code.count('RMDir') == 1


def test_upgrade_smoke_asserts_stale_backend_removed_and_user_data_kept():
    smoke = SMOKE.read_text(encoding='utf-8')
    assert 'resources\\backend\\stale_marker.py' in smoke
    assert "Join-Path $env:APPDATA 'AutoClip'" in smoke
    assert smoke.index('stale_marker') < smoke.index("Write-Host '==> 静默覆盖安装新包'") < smoke.index('仍有旧版残留文件')
