"""Optional catalog loader for the provider-e2e matrix.

Reads ``backend/presets/provider_presets.json`` when that file exists (P12) or when
``AUTOCLIP_PROVIDER_PRESETS`` points at a JSON file. This module does not ship
or rewrite a product catalog. Live chat URLs (Gemini ``/openai``) and
fallback models (DashScope ``qwen-plus``) stay in ``matrix.py``. Never print
secrets — the catalog has none, and extra key-like fields are dropped.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = 1
KNOWN_GROUPS = frozenset({'recommended', 'popular', 'local', 'more'})
_REQUIRED = ('kind', 'display_name', 'group', 'protocol')

_cache: dict[str, dict[str, Any]] | None = None
_cache_path: Path | None = None


def reset_catalog_cache() -> None:
    global _cache, _cache_path
    _cache = None
    _cache_path = None


def find_e2e_presets_path(start: Path | None = None) -> Path | None:
    """Env override, then the product JSON. Missing env path is fail-closed."""
    env = (os.environ.get('AUTOCLIP_PROVIDER_PRESETS') or '').strip()
    if env:
        path = Path(env).expanduser()
        if path.is_file():
            return path.resolve()
        raise FileNotFoundError(f'AUTOCLIP_PROVIDER_PRESETS not found: {path}')
    seen: set[Path] = set()
    roots = [Path(start).resolve() if start else Path(__file__).resolve().parent, Path.cwd()]
    for root in roots:
        for parent in (root, *root.parents):
            candidate = parent / 'backend' / 'presets' / 'provider_presets.json'
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate.is_file():
                return candidate.resolve()
    return None


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _row_from_mapping(key: str, raw: Mapping[str, Any]) -> dict[str, Any] | None:
    if not key or any(not isinstance(raw.get(field), str) or not str(raw.get(field)).strip() for field in _REQUIRED):
        return None
    if str(raw['kind']).strip() != 'preset':
        return None
    if str(raw['group']).strip() not in KNOWN_GROUPS:
        return None
    candidates_raw = raw.get('candidates') if isinstance(raw.get('candidates'), Mapping) else {}
    analysis = _strings(candidates_raw.get('analysis'))
    default = raw.get('default_model')
    if not isinstance(default, str) or not default.strip():
        default = analysis[0] if analysis else ''
    display = str(raw['display_name']).strip()
    return {
        'id': key,
        'label': str(raw.get('short_name') or display).strip(),
        'base_url': str(raw.get('base_url') or '').strip(),
        'default_model': default.strip(),
        'analysis_candidates': analysis,
    }


def _parse_json(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, Mapping):
        raise ValueError('provider presets must be a JSON object')
    schema_version = data.get('schema_version')
    if schema_version != SCHEMA_VERSION:
        raise ValueError(f'unsupported provider presets schema_version: {schema_version!r}')
    version = data.get('version')
    if not isinstance(version, int) or version < 1:
        raise ValueError(f'invalid provider presets version: {version!r}')
    raw_providers = data.get('providers')
    if not isinstance(raw_providers, Mapping):
        raise ValueError('provider presets missing providers object')
    providers: dict[str, dict[str, Any]] = {}
    for key, raw in raw_providers.items():
        if not isinstance(key, str) or not isinstance(raw, Mapping):
            continue
        parsed = _row_from_mapping(key.strip(), raw)
        if parsed:
            providers[parsed['id']] = parsed
    return providers


def load_catalog_providers(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return catalog rows keyed by provider id. Empty when no product JSON."""
    global _cache, _cache_path
    if path is not None:
        catalog_path = Path(path).resolve()
    else:
        catalog_path = find_e2e_presets_path()
        if catalog_path is None:
            return {}
    if _cache is not None and _cache_path == catalog_path:
        return _cache
    loaded = _parse_json(catalog_path)
    _cache = loaded
    _cache_path = catalog_path
    return loaded
