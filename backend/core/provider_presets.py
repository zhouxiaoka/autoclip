"""Single loader for ``backend/presets/provider_presets.json``.

This is first-party AutoClip data. The JSON is the product catalog; this module
only finds, validates and projects it. Installed wheels and the CLI/MCP ZIP
locate it as a package resource (``importlib.resources``). Remote fetch is
out of scope.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from importlib.resources import files as package_files
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

SCHEMA_VERSION = 1
KNOWN_GROUPS = frozenset({"recommended", "popular", "local", "more"})
KNOWN_PURPOSES = ("analysis", "vision", "asr", "image")
_REQUIRED = ("kind", "display_name", "group", "protocol")


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    kind: str
    display_name: str
    ui_name: str
    short_name: str
    catalog_label: str
    group: str
    protocol: str
    base_url: str
    auth: str
    capabilities: Tuple[str, ...]
    docs_url: str
    locked: bool
    accepted_hosts: Tuple[str, ...]
    default_model: str
    catalog: Optional[Tuple[str, ...]]
    catalog_image: Tuple[str, ...]
    candidates: Dict[str, Tuple[str, ...]]
    openai_compat_remap: bool
    local_compat_remap: bool
    legacy_ui: bool
    api_key_setting: str
    placeholder: str
    hint: str
    cloud_hint: str
    context_hint: str
    local_app: str
    sponsor: Optional[Dict[str, str]]
    referral: str


@dataclass(frozen=True)
class ProviderCatalog:
    schema_version: int
    version: int
    issued_at: str
    local_context_hint: str
    console_hosts: Tuple[str, ...]
    console_suffixes: Tuple[str, ...]
    aliases: Dict[str, str]
    providers: Dict[str, ProviderPreset]
    path: Path


_cache: Optional[ProviderCatalog] = None
_RESOURCE_NAME = "provider_presets.json"


def _env_presets_path() -> Optional[Path]:
    env = (os.environ.get("AUTOCLIP_PROVIDER_PRESETS") or "").strip()
    if not env:
        return None
    path = Path(env).expanduser()
    if path.is_file():
        return path
    raise FileNotFoundError(f"AUTOCLIP_PROVIDER_PRESETS not found: {path}")


def _resource_presets_path() -> Optional[Path]:
    """Installed wheel / editable checkout: ``backend/presets/provider_presets.json``."""
    try:
        resource = package_files("backend").joinpath("presets", _RESOURCE_NAME)
        path = Path(os.fspath(resource))
        return path if path.is_file() else None
    except (ModuleNotFoundError, FileNotFoundError, TypeError, OSError, ValueError):
        return None


def _walk_presets(start: Path) -> Optional[Path]:
    seen: set[Path] = set()
    for parent in (start.resolve(), *start.resolve().parents):
        candidate = parent / "backend" / "presets" / _RESOURCE_NAME
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return candidate
    return None


def find_provider_presets_path(start: Optional[Path] = None) -> Path:
    """Locate the catalog by env, optional walk-up, packaged resource, then cwd."""
    found = _env_presets_path()
    if found:
        return found
    if start is not None:
        found = _walk_presets(Path(start))
        if found:
            return found
    found = _resource_presets_path()
    if found:
        return found
    found = _walk_presets(Path(__file__).resolve().parent) or _walk_presets(Path.cwd())
    if found:
        return found
    raise FileNotFoundError("backend/presets/provider_presets.json not found")


def _strings(value: Any) -> Tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _sponsor(raw: Any) -> Optional[Dict[str, str]]:
    if not isinstance(raw, Mapping):
        return None
    out = {
        key: str(raw[key])
        for key in ("register_url", "guide_url", "offer", "description")
        if isinstance(raw.get(key), str) and raw[key]
    }
    return out or None


def _parse_provider(key: str, raw: Any) -> Optional[ProviderPreset]:
    if not key or not isinstance(raw, Mapping):
        return None
    if any(not isinstance(raw.get(field), str) or not str(raw.get(field)).strip() for field in _REQUIRED):
        return None
    group = str(raw["group"]).strip()
    if group not in KNOWN_GROUPS:
        return None
    kind = str(raw["kind"]).strip()
    if kind != "preset":
        return None
    display = str(raw["display_name"]).strip()
    candidates_raw = raw.get("candidates") if isinstance(raw.get("candidates"), Mapping) else {}
    candidates = {
        purpose: _strings(candidates_raw.get(purpose))
        for purpose in KNOWN_PURPOSES
    }
    has_catalog = "catalog" in raw
    default_model = raw.get("default_model")
    if not isinstance(default_model, str):
        default_model = candidates["analysis"][0] if candidates["analysis"] else ""
    return ProviderPreset(
        id=key,
        kind=kind,
        display_name=display,
        ui_name=str(raw.get("ui_name") or display).strip(),
        short_name=str(raw.get("short_name") or display).strip(),
        catalog_label=str(raw.get("catalog_label") or raw.get("short_name") or display).strip(),
        group=group,
        protocol=str(raw["protocol"]).strip(),
        base_url=str(raw.get("base_url") or "").strip(),
        auth=str(raw.get("auth") or "api_key").strip(),
        capabilities=_strings(raw.get("capabilities")) or ("language",),
        docs_url=str(raw.get("docs_url") or "").strip(),
        locked=bool(raw.get("locked", True)),
        accepted_hosts=tuple(host.lower() for host in _strings(raw.get("accepted_hosts"))),
        default_model=default_model,
        catalog=_strings(raw.get("catalog")) if has_catalog else None,
        catalog_image=_strings(raw.get("catalog_image")),
        candidates=candidates,
        openai_compat_remap=bool(raw.get("openai_compat_remap")),
        local_compat_remap=bool(raw.get("local_compat_remap")),
        legacy_ui=bool(raw.get("legacy_ui")),
        api_key_setting=str(raw.get("api_key_setting") or f"{key}_api_key").strip(),
        placeholder=str(raw.get("placeholder") or "sk-…"),
        hint=str(raw.get("hint") or "").strip(),
        cloud_hint=str(raw.get("cloud_hint") or raw.get("hint") or "").strip(),
        context_hint=str(raw.get("context_hint") or "").strip(),
        local_app=str(raw.get("local_app") or "").strip(),
        sponsor=_sponsor(raw.get("sponsor")),
        referral=str(raw.get("referral") or "").strip() if isinstance(raw.get("referral"), str) else "",
    )


def load_provider_catalog(path: Optional[Path] = None) -> ProviderCatalog:
    """Load and validate a catalog file. Unknown schema versions raise; bad rows are skipped."""
    catalog_path = Path(path) if path else find_provider_presets_path()
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("provider presets must be a JSON object")
    schema_version = data.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ValueError(f"unsupported provider presets schema_version: {schema_version!r}")
    version = data.get("version")
    if not isinstance(version, int) or version < 1:
        raise ValueError(f"invalid provider presets version: {version!r}")
    raw_providers = data.get("providers")
    if not isinstance(raw_providers, Mapping):
        raise ValueError("provider presets missing providers object")
    providers: Dict[str, ProviderPreset] = {}
    for key, raw in raw_providers.items():
        if not isinstance(key, str):
            continue
        parsed = _parse_provider(key.strip(), raw)
        if parsed:
            providers[parsed.id] = parsed
    aliases: Dict[str, str] = {}
    raw_aliases = data.get("aliases") if isinstance(data.get("aliases"), Mapping) else {}
    for alias, target in raw_aliases.items():
        if isinstance(alias, str) and isinstance(target, str) and alias.strip() and target.strip():
            aliases[alias.strip().lower()] = target.strip()
    address_rules = data.get("address_rules") if isinstance(data.get("address_rules"), Mapping) else {}
    return ProviderCatalog(
        schema_version=int(schema_version),
        version=version,
        issued_at=str(data.get("issued_at") or ""),
        local_context_hint=str(data.get("local_context_hint") or ""),
        console_hosts=_strings(address_rules.get("console_hosts")),
        console_suffixes=_strings(address_rules.get("console_suffixes")),
        aliases=aliases,
        providers=providers,
        path=catalog_path,
    )


def reset_catalog_cache() -> None:
    global _cache
    _cache = None


def get_catalog() -> ProviderCatalog:
    global _cache
    if _cache is None:
        _cache = load_provider_catalog()
    return _cache


def resolve_provider_id(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    key = name.strip().lower()
    catalog = get_catalog()
    key = catalog.aliases.get(key, key)
    return key if key in catalog.providers else None


def get_provider(name: Optional[str]) -> Optional[ProviderPreset]:
    key = resolve_provider_id(name)
    return get_catalog().providers.get(key) if key else None


def iter_providers() -> Iterable[ProviderPreset]:
    return get_catalog().providers.values()


def candidates_for(name: Optional[str], purpose: str) -> Tuple[str, ...]:
    provider = get_provider(name)
    if not provider:
        return ()
    return provider.candidates.get(purpose, ())


def default_models_map() -> Dict[str, str]:
    return {
        item.id: item.default_model
        for item in iter_providers()
        if item.catalog is not None
    }


def curated_models_map() -> Dict[str, list[str]]:
    return {
        item.id: list(item.catalog)
        for item in iter_providers()
        if item.catalog is not None
    }


def provider_labels_map() -> Dict[str, str]:
    return {
        item.id: item.catalog_label
        for item in iter_providers()
        if item.catalog is not None
    }


def image_catalog_map() -> Dict[str, list[str]]:
    return {
        item.id: list(item.catalog_image)
        for item in iter_providers()
        if item.catalog_image
    }


#: Non-catalog provider slugs telemetry also accepts (custom OpenAI-compatible and the unknown bucket).
EXTRA_TELEMETRY_PROVIDERS: Tuple[str, ...] = ("compatible", "other")


def telemetry_provider_slugs() -> Tuple[str, ...]:
    """1.5.7 single source for the telemetry ``provider`` enum: every catalog preset id, in catalog
    order, plus ``compatible`` / ``other``. Frontend and event_catalog.json derive the same list."""
    return tuple(get_catalog().providers) + EXTRA_TELEMETRY_PROVIDERS
