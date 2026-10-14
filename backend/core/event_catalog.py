"""Machine-readable tracking-plan catalog and payload validator.

``docs/analytics/event_catalog.json`` is the only registry. Unregistered
business events and missing required fields fail validation. Telemetry
callers must still catch errors — this module never raises on emit.
"""
from __future__ import annotations

import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping

_EVENT_NAME = re.compile(r"^[a-z$][a-z0-9_ ]*$")
_URL_WITH_PATH = re.compile(r"https?://\S+/\S+")
_PRODUCER_CALLS = (
    re.compile(r"captureBusinessEvent\(\s*['\"]([a-z$][a-z0-9_]*)['\"]"),
    re.compile(r"posthog\.capture\(\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"emitOnce\([^,]+,\s*[^,]+,\s*['\"]([a-z_][a-z0-9_]*)['\"]"),
    re.compile(r"_post_event\(\s*['\"]([a-z_][a-z0-9_]*)['\"]"),
    re.compile(r"_emit\(\s*['\"]([a-z_][a-z0-9_]*)['\"]"),
    re.compile(r"""['"]event['"]:\s*['"]([a-z_][a-z0-9_]*)['"]"""),
    re.compile(r"\bevent:\s*['\"]([a-z_][a-z0-9_]*)['\"]"),
    re.compile(r"\bevent\s*=\s*['\"]([a-z_][a-z0-9_]*)['\"]"),
    re.compile(r"EVENT_[A-Z0-9_]+\s*=\s*['\"]([a-z_][a-z0-9_]*)['\"]"),
)
_PREFIX_CALLS = (
    (re.compile(r"observeStudioOperation\(\s*['\"]([a-z_][a-z0-9_]*)['\"]"),
     ("requested", "accepted", "request_failed")),
    (re.compile(r"observeOperation\(\s*['\"]([a-z_][a-z0-9_]*)['\"]"),
     ("requested", "accepted", "request_failed")),
    (re.compile(r"beginExperience\(\s*['\"]([a-z_][a-z0-9_]*)['\"]"),
     ("requested", "finished")),
)
_ANALYTICS_CONST = re.compile(
    r"^\s+[A-Z][A-Za-z]+:\s*['\"]([a-z_][a-z0-9_]*)['\"]",
    re.MULTILINE,
)
_FRONTEND_SUFFIXES = {".ts", ".tsx"}
_BACKEND_FILES = (
    "backend/core/llm_emit.py",
    "backend/core/llm_telemetry.py",
    "backend/services/studio/qa/telemetry.py",
    "backend/services/mcp_telemetry.py",
)


def catalog_path() -> Path:
    override = os.environ.get("AUTOCLIP_EVENT_CATALOG")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "docs" / "analytics" / "event_catalog.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    return json.loads(catalog_path().read_text(encoding="utf-8"))


def reload_catalog() -> dict[str, Any]:
    load_catalog.cache_clear()
    return load_catalog()


def normalize_os(value: str | None) -> str | None:
    catalog = load_catalog()
    if not isinstance(value, str):
        return None
    key = value.strip().lower()
    aliases = catalog["common"].get("os_aliases") or {}
    key = aliases.get(key, key)
    if key in catalog["common"]["os"]:
        return key
    return None


def detect_os() -> str:
    return normalize_os(sys.platform) or "unknown"


def app_version() -> str:
    raw = (os.environ.get("AUTOCLIP_APP_VERSION") or os.environ.get("VITE_APP_VERSION") or "").strip()
    if raw[:1] in {"v", "V"} and len(raw) > 1 and raw[1].isdigit():
        raw = raw[1:]
    if raw:
        return raw
    try:
        from backend import __version__
        return str(__version__)
    except Exception:  # noqa: BLE001
        return "unknown"


def analytics_environment() -> str:
    value = (os.environ.get("AUTOCLIP_BUILD_ENVIRONMENT") or "").strip().lower()
    allowed = set(load_catalog()["common"]["analytics_environment"])
    if value in allowed:
        return value
    return "development"


def envelope_properties() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "runtime": "python",
        "app_version": app_version(),
        "os": detect_os(),
        "analytics_environment": analytics_environment(),
    }


def listed_events(catalog: Mapping[str, Any] | None = None) -> set[str]:
    data = catalog or load_catalog()
    names = set(data.get("events") or {})
    for family in (data.get("families") or {}).values():
        verbs = family.get("verbs") or []
        for prefix in (family.get("prefixes") or {}):
            for verb in verbs:
                names.add(f"{prefix}_{verb}")
    return names


def event_spec(name: str, catalog: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
    data = catalog or load_catalog()
    events = data.get("events") or {}
    if name in events:
        return dict(events[name])
    for family in (data.get("families") or {}).values():
        verbs = family.get("verbs") or []
        for prefix, spec in (family.get("prefixes") or {}).items():
            for verb in verbs:
                if name == f"{prefix}_{verb}":
                    out = {"status": spec.get("status") or family.get("status") or "keep"}
                    required_by_verb = (spec.get("required_by_verb") or {})
                    if verb in required_by_verb:
                        out["required"] = list(required_by_verb[verb])
                    elif spec.get("required"):
                        out["required"] = list(spec["required"])
                    return out
    return None


def ignore_events(catalog: Mapping[str, Any] | None = None) -> set[str]:
    data = catalog or load_catalog()
    return set((data.get("scan") or {}).get("ignore_events") or [])


def validate_event(
    name: str,
    properties: Mapping[str, Any] | None = None,
    *,
    envelope: bool = False,
    catalog: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return human-readable errors. Empty list means the payload is allowed."""
    data = catalog or load_catalog()
    errors: list[str] = []
    if name in ignore_events(data):
        return errors
    spec = event_spec(name, data)
    if spec is None:
        return [f"unregistered event: {name}"]
    props = dict(properties or {})
    required = list(spec.get("required") or [])
    for rule, extra in (spec.get("required_when") or {}).items():
        key, _, expected = rule.partition("=")
        if str(props.get(key)) == expected:
            required.extend(extra)
    missing = [field for field in required if field not in props or props[field] in (None, "")]
    if missing:
        errors.append(f"{name} missing required fields: {', '.join(missing)}")
    enums = spec.get("enums") or {}
    enum_sets = data.get("enums") or {}
    for field, enum_name in enums.items():
        if field not in props:
            continue
        allowed = set(enum_sets.get(enum_name) or [])
        if allowed and props[field] not in allowed:
            errors.append(f"{name}.{field}={props[field]!r} not in {enum_name}")
    if envelope:
        for field in data["common"]["required"]:
            if field not in props or props[field] in (None, ""):
                errors.append(f"{name} missing common field: {field}")
        os_value = props.get("os")
        if os_value is not None and os_value not in data["common"]["os"]:
            errors.append(f"{name}.os={os_value!r} is not a canonical os")
    errors.extend(_privacy_errors(name, props, data))
    return errors


def _privacy_errors(name: str, props: Mapping[str, Any], catalog: Mapping[str, Any]) -> list[str]:
    privacy = catalog.get("privacy") or {}
    forbidden_keys = {str(key).lower() for key in privacy.get("forbidden_keys") or []}
    forbidden_sub = [str(item).lower() for item in privacy.get("forbidden_substrings") or []]
    user_content = {str(key).lower() for key in privacy.get("user_content_keys") or []}
    submitted = {str(item) for item in privacy.get("user_submitted_events") or []}
    spec = event_spec(name, catalog) or {}
    if spec.get("kind") == "user_submitted":
        submitted.add(name)
    errors: list[str] = []
    for key, value in props.items():
        lowered_key = str(key).lower()
        if lowered_key in forbidden_keys:
            errors.append(f"{name} has forbidden property {key}")
        if lowered_key in user_content and name not in submitted:
            errors.append(f"{name} has user content {key}")
        if isinstance(value, str):
            lowered = value.lower()
            if any(marker in lowered for marker in forbidden_sub):
                errors.append(f"{name}.{key} looks like a secret")
            if _URL_WITH_PATH.search(value):
                errors.append(f"{name}.{key} contains a full URL path")
    return errors


def collect_producer_events(root: Path | None = None) -> set[str]:
    """Event names referenced by frontend/backend producers."""
    repo = root or catalog_path().parents[1]
    names: set[str] = set()
    frontend = repo / "frontend" / "src"
    if frontend.is_dir():
        for path in frontend.rglob("*"):
            if path.suffix in _FRONTEND_SUFFIXES:
                names.update(_extract_from_text(path.read_text(encoding="utf-8")))
    for relative in _BACKEND_FILES:
        path = repo / relative
        if path.is_file():
            names.update(_extract_from_text(path.read_text(encoding="utf-8")))
    return names


def _extract_from_text(source: str) -> set[str]:
    names: set[str] = set()
    for pattern in _PRODUCER_CALLS:
        names.update(pattern.findall(source))
    for pattern, verbs in _PREFIX_CALLS:
        for prefix in pattern.findall(source):
            for verb in verbs:
                names.add(f"{prefix}_{verb}")
    names.update(_ANALYTICS_CONST.findall(source))
    return {name for name in names if _EVENT_NAME.fullmatch(name)}


def unregistered_producers(
    produced: Iterable[str] | None = None,
    catalog: Mapping[str, Any] | None = None,
) -> list[str]:
    data = catalog or load_catalog()
    allowed = listed_events(data) | ignore_events(data)
    found = set(produced if produced is not None else collect_producer_events())
    return sorted(found - allowed)
