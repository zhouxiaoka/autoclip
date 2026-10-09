"""Windows NSIS hooks (RC156 Win QA #2, #4, #15): static checks, no Windows needed.

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
    install_side = '\n'.join(
        _macro('AUTOCLIP_REMOVE_OLD_BACKEND') + _macro('AUTOCLIP_KILL_BUNDLED_PROCESSES') + _macro('NSIS_HOOK_PREINSTALL')
    )
    for user_location in ('$APPDATA', '$LOCALAPPDATA', '$PROFILE', '$DOCUMENTS', 'resources\\python"'):
        assert user_location not in install_side


def test_upgrade_smoke_asserts_stale_backend_removed_and_user_data_kept():
    smoke = SMOKE.read_text(encoding='utf-8')
    assert 'resources\\backend\\stale_marker.py' in smoke
    assert "Join-Path $env:APPDATA 'AutoClip'" in smoke
    assert smoke.index('stale_marker') < smoke.index("Write-Host '==> 静默覆盖安装新包'") < smoke.index('仍有旧版残留文件')


# ---- #15: uninstall may delete %APPDATA%\AutoClip, but only on an explicit request ----

LANG_DIR = ROOT / 'src-tauri' / 'windows' / 'lang'
# Keys of tauri-bundler 2.10.1 languages/*.nsh. A custom language file replaces the built-in
# one, so a missing key would show an empty string in the installer.
TAURI_LANG_KEYS = {
    'addOrReinstall', 'alreadyInstalled', 'alreadyInstalledLong', 'appRunning', 'appRunningOkKill',
    'chooseMaintenanceOption', 'choowHowToInstall', 'createDesktop', 'dontUninstall',
    'dontUninstallDowngrade', 'failedToKillApp', 'installingWebview2', 'newerVersionInstalled', 'older',
    'olderOrUnknownVersionInstalled', 'silentDowngrades', 'unableToUninstall', 'uninstallApp',
    'uninstallBeforeInstalling', 'unknown', 'webview2AbortError', 'webview2DownloadError',
    'webview2DownloadSuccess', 'webview2Downloading', 'webview2InstallError', 'webview2InstallSuccess',
    'deleteAppData',
}
LANGS = {'SimpChinese': 'LANG_SIMPCHINESE', 'English': 'LANG_ENGLISH'}
CHECKBOX = {
    'SimpChinese': '同时删除 AutoClip 数据（项目、设置、API 密钥）',
    'English': 'Also delete my AutoClip data (projects, settings, API keys)',
}


def _lang_strings(lang):
    strings = {}
    for line in (LANG_DIR / f'{lang}.nsh').read_text(encoding='utf-8').splitlines():
        match = re.match(r'^LangString (\w+) \$\{(\w+)\} "(.*)"$', line)
        if match:
            assert match.group(2) == LANGS[lang], line
            strings[match.group(1)] = match.group(3)
    return strings


def test_post_uninstall_hook_only_runs_the_guarded_removals():
    assert _macro('NSIS_HOOK_POSTUNINSTALL') == [
        '!insertmacro AUTOCLIP_DELETE_USER_DATA',
        '!insertmacro AUTOCLIP_REMOVE_INSTALL_LEFTOVERS',
    ]


# The template's GUI checkbox block (tauri-bundler 2.10.1 installer.nsi, Section Uninstall) deletes
#   RmDir /r "$APPDATA\${BUNDLEID}" and RmDir /r "$LOCALAPPDATA\${BUNDLEID}"
# and only runs for the ticked checkbox. Silent /DELETEAPPDATA never reaches it (RC156 #24), so the
# hook deletes the same two plus %APPDATA%\AutoClip for every "delete my data" decision.
USER_DATA_DIRS = ['$APPDATA\\AutoClip', '$APPDATA\\${BUNDLEID}', '$LOCALAPPDATA\\${BUNDLEID}']


def test_user_data_removal_deletes_exactly_the_gui_checkbox_directories():
    body = _macro('AUTOCLIP_DELETE_USER_DATA')
    removals = [line for line in body if line.startswith(('RMDir', 'RmDir', 'Delete'))]
    assert removals == [f'RMDir /r "{path}"' for path in USER_DATA_DIRS]
    code = _code(HOOKS.read_text(encoding='utf-8'))
    assert re.findall(r'(?im)^\s*(?:RMDir|Delete)\b.*$', code) == [
        '    RMDir /r "$INSTDIR\\resources\\backend"',
        *[f'      RMDir /r "{path}"' for path in USER_DATA_DIRS],
        *[f'    {line}' for line in LEFTOVER_REMOVALS],
    ]
    for forbidden in ('*', '..', '$PROFILE', '$DOCUMENTS', '$TEMP', 'SetShellVarContext all', '$INSTDIR'):
        assert not any(forbidden in line for line in removals), forbidden
    # Each removal is guarded by: shell folders resolved for the current user, non-empty, and the dir exists.
    context = body.index('SetShellVarContext current')
    for path in USER_DATA_DIRS:
        rmdir = body.index(f'RMDir /r "{path}"')
        root = path.split('\\', 1)[0]
        assert context < rmdir
        assert body[rmdir - 2:rmdir] == [f'${{If}} "{root}" != ""', f'${{AndIf}} ${{FileExists}} "{path}\\*.*"'] or \
            body[rmdir - 3:rmdir - 1] == [f'${{If}} "{root}" != ""', f'${{AndIf}} ${{FileExists}} "{path}\\*.*"'], path


def test_silent_delete_appdata_and_gui_checkbox_share_one_removal_block():
    body = _macro('AUTOCLIP_DELETE_USER_DATA')
    block = body[body.index('${If} $R9 = 1'):body.index('Pop $R9')]
    # Both decisions only set $R9; the one removal block (all three directories) follows.
    assert sum(line == '${If} $R9 = 1' for line in body) == 1
    assert [line for line in block if line.startswith('RMDir')] == [f'RMDir /r "{path}"' for path in USER_DATA_DIRS]


def test_user_data_removal_is_never_done_on_update_or_installer_driven_uninstall():
    body = _macro('AUTOCLIP_DELETE_USER_DATA')
    # The outer guard wraps every way of setting the decision flag.
    assert body[:5] == ['Push $R8', 'Push $R9', 'StrCpy $R9 0', '${If} $UpdateMode <> 1', '${AndIf} "$EXEDIR" != "$INSTDIR"']
    decision = body[body.index('${AndIf} "$EXEDIR" != "$INSTDIR"'):body.index('${If} $R9 = 1')]
    assert decision[-1] == '${EndIf}'
    assert [line for line in body if line == 'StrCpy $R9 1'] == [line for line in decision if line == 'StrCpy $R9 1']
    assert len([line for line in decision if line == 'StrCpy $R9 1']) == 2
    assert body[-2:] == ['Pop $R9', 'Pop $R8']


def test_silent_or_passive_uninstall_needs_the_explicit_flag_and_gui_needs_the_checkbox():
    body = _macro('AUTOCLIP_DELETE_USER_DATA')
    start = body.index('${If} ${Silent}')
    assert body[start:start + 9] == [
        '${If} ${Silent}',
        '${OrIf} $PassiveMode = 1',
        'ClearErrors',
        '${GetOptions} $CMDLINE "/DELETEAPPDATA" $R8',
        '${IfNot} ${Errors}',
        'StrCpy $R9 1',
        '${EndIf}',
        '${ElseIf} $DeleteAppDataCheckboxState = 1',
        'StrCpy $R9 1',
    ]
    # The checkbox state is never consulted on the silent/passive branch.
    assert body.count('${ElseIf} $DeleteAppDataCheckboxState = 1') == 1
    assert sum('DeleteAppDataCheckboxState' in line for line in body) == 1


def test_custom_language_files_keep_every_tauri_key_and_name_what_is_deleted():
    config = json.loads((ROOT / 'src-tauri' / 'tauri.windows.conf.json').read_text(encoding='utf-8'))
    nsis = config['bundle']['windows']['nsis']
    assert nsis['customLanguageFiles'] == {lang: f'windows/lang/{lang}.nsh' for lang in nsis['languages']}
    assert set(nsis['languages']) == set(LANGS)
    for lang in LANGS:
        text = (LANG_DIR / f'{lang}.nsh').read_text(encoding='utf-8')
        assert '{{' not in text.split('\n', 5)[-1]  # the bundler never renders language files
        strings = _lang_strings(lang)
        assert set(strings) == TAURI_LANG_KEYS | {'autoclipUninstallNote'}
        assert strings['deleteAppData'] == CHECKBOX[lang]
        assert '%APPDATA%\\AutoClip' in strings['autoclipUninstallNote']
    assert '!define MUI_UNCONFIRMPAGE_TEXT_TOP "$(autoclipUninstallNote)"' in _code(HOOKS.read_text(encoding='utf-8'))


def test_privacy_docs_match_the_uninstaller():
    zh = (ROOT / 'docs' / 'PRIVACY.md').read_text(encoding='utf-8')
    en = (ROOT / 'docs' / 'PRIVACY.en.md').read_text(encoding='utf-8')
    for doc, lang in ((zh, 'SimpChinese'), (en, 'English')):
        assert CHECKBOX[lang] in doc
        assert '`%APPDATA%\\AutoClip`' in doc
        assert '`/DELETEAPPDATA`' in doc
    assert '卸载软件或删除项目即清除' not in zh
    assert 'uninstalling the Software or deleting a project removes it' not in en


# ---- #23: uninstall leaves resources\python\...\__pycache__\*.pyc, so the install dir stays ----

LEFTOVER_REMOVALS = [
    'RMDir /r "$INSTDIR\\resources\\python"',
    'RMDir /r "$INSTDIR\\resources\\backend"',
    'RMDir /r "$INSTDIR\\resources\\ffmpeg"',
    'RMDir "$INSTDIR\\resources"',
    'RMDir "$INSTDIR"',
]


def test_uninstall_removes_runtime_leftovers_in_the_bundled_resource_dirs_only():
    body = _macro('AUTOCLIP_REMOVE_INSTALL_LEFTOVERS')
    removals = [line for line in body if line.startswith(('RMDir', 'RmDir', 'Delete'))]
    assert removals == LEFTOVER_REMOVALS
    # Recursive removal only for the directories the bundle installs (tauri.windows.conf.json),
    # the resources dir and the install dir itself only when empty (non-recursive).
    config = json.loads((ROOT / 'src-tauri' / 'tauri.windows.conf.json').read_text(encoding='utf-8'))
    bundled = {target.replace('/', '\\') for target in config['bundle']['resources'].values()}
    recursive = {re.match(r'RMDir /r "\$INSTDIR\\(.+)"$', line).group(1) for line in removals if line.startswith('RMDir /r')}
    assert recursive == bundled
    for forbidden in ('*', '..', '$APPDATA', '$LOCALAPPDATA', '$PROFILE', '$DOCUMENTS', '$TEMP', 'RMDir /r "$INSTDIR"'):
        assert not any(forbidden in line for line in removals), forbidden


def test_install_leftovers_are_only_removed_on_a_real_uninstall():
    body = _macro('AUTOCLIP_REMOVE_INSTALL_LEFTOVERS')
    first_removal = body.index(LEFTOVER_REMOVALS[0])
    guards = body[:first_removal]
    assert guards == [
        '${If} $UpdateMode <> 1',                          # never on /UPDATE
        '${AndIf} "$EXEDIR" != "$INSTDIR"',                # never in the installer's pre-install uninstall
        '${AndIf} "$INSTDIR" != ""',
        '${AndIfNot} ${FileExists} "$INSTDIR\\${MAINBINARYNAME}.exe"',  # the template really removed the app
    ]
    assert body[-1] == '${EndIf}' and body.count('${EndIf}') == 1
    # Runs after the user-data decision, and never from the install side.
    assert _macro('NSIS_HOOK_POSTUNINSTALL')[-1] == '!insertmacro AUTOCLIP_REMOVE_INSTALL_LEFTOVERS'
    assert 'AUTOCLIP_REMOVE_INSTALL_LEFTOVERS' not in '\n'.join(_macro('NSIS_HOOK_PREINSTALL') + _macro('NSIS_HOOK_PREUNINSTALL'))
