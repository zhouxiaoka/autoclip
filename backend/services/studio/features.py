"""Feature-flag snapshot for one generation.

The desktop client sends the resolved snapshot with an import. CLI, MCP and
Docker have no PostHog SDK: they read AUTOCLIP_FLAGS, then these defaults.
Unknown keys and values are dropped. autoclip_safe_mode forces every other
flag back to its safe off value unless AUTOCLIP_FLAGS sets that flag explicitly.
"""
from __future__ import annotations

import os

# Keep in lockstep with frontend/src/analytics/flags.defaults.json.
DEFAULTS: dict[str, bool | str] = {
    'autoclip_safe_mode': False,
    'remember_platforms': False,
    'one_click_paste_start': 'button',
    'link_import_without_whisper': False,
    'notify_on_done': False,
    'publish_pack_v2': 'separate',
    'render_top_first': 'limit10',
    'clip_reasons': False,
    'hide_legacy_entrypoints': False,
    'import_drop_zone': False,
    'track_overrides': False,
}

VARIANTS = {
    'one_click_paste_start': ('button', 'autostart'),
    'publish_pack_v2': ('separate', 'combined'),
    'render_top_first': ('limit10', 'top3'),
}


def normalize_flag(name: str, raw: object) -> bool | str | None:
    if name not in DEFAULTS:
        return None
    if name in VARIANTS:
        return raw if isinstance(raw, str) and raw in VARIANTS[name] else None
    if raw is True or raw in ('true', 'on', '1', 1):
        return True
    if raw is False or raw in ('false', 'off', '0', 0):
        return False
    return None


def parse_flag_list(raw: str | None) -> dict[str, bool | str]:
    found: dict[str, bool | str] = {}
    for part in (raw or '').split(','):
        if '=' not in part:
            continue
        key, value = part.split('=', 1)
        normalized = normalize_flag(key.strip(), value.strip())
        if normalized is not None:
            found[key.strip()] = normalized
    return found


def resolve_features(snapshot: dict | None = None, env: str | None = None) -> dict[str, bool | str]:
    """Defaults, then the client snapshot, then safe mode, then AUTOCLIP_FLAGS."""
    if env is None:
        env = os.environ.get('AUTOCLIP_FLAGS', '')
    operator = parse_flag_list(env)
    resolved = dict(DEFAULTS)
    if isinstance(snapshot, dict):
        for key, value in snapshot.items():
            normalized = normalize_flag(str(key), value)
            if normalized is not None:
                resolved[str(key)] = normalized
    if resolved.get('autoclip_safe_mode') is True:
        for key, default in DEFAULTS.items():
            if key != 'autoclip_safe_mode':
                resolved[key] = default
    resolved.update(operator)
    if resolved.get('autoclip_safe_mode') is True:
        for key, default in DEFAULTS.items():
            if key != 'autoclip_safe_mode' and key not in operator:
                resolved[key] = default
    return resolved


def flag_enabled(features: dict | None, name: str) -> bool:
    """True only for the treatment. Missing flags stay off."""
    value = (features or {}).get(name, DEFAULTS.get(name))
    if name in VARIANTS:
        treatments = {'one_click_paste_start': 'autostart', 'publish_pack_v2': 'combined', 'render_top_first': 'top3'}
        return value == treatments[name]
    return value is True
