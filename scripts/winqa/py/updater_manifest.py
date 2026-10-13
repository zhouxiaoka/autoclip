"""Judge a Tauri updater manifest (W157 IA). Kept import-free so CI can test it off Windows."""
import re


def judge_updater_manifest(status, manifest, platform):
    """'ok' when a Tauri updater manifest is usable for `platform`, else a short reason.

    Judges the manifest only: any released version is fine (the live one may be older than the build
    under test). Network failures are handled by the caller and never reported as an unreadable manifest.
    """
    if status != 200:
        return f'http_{status}'
    if not isinstance(manifest, dict):
        return 'not_json_object'
    version = str(manifest.get('version') or '').lstrip('v')
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.\-]+)?', version):
        return 'bad_version'
    platforms = manifest.get('platforms')
    if not isinstance(platforms, dict) or platform not in platforms:
        return 'platform_missing'
    entry = platforms[platform]
    if not isinstance(entry, dict) or not str(entry.get('url') or '').startswith('https://') or not entry.get('signature'):
        return 'platform_entry_incomplete'
    return 'ok'
