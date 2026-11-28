"""Per-template user brand variable overrides stored under ``<data_dir>/templates/.user-vars.json``."""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path
from typing import Any

from backend.services.studio.templates.registry import user_templates_root
from backend.services.studio.templates.spec import TemplateSpec, TemplateVariableSpec

_HEX_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
_write_lock = threading.Lock()


def _vars_path(user_root: Path | None = None) -> Path:
    base = user_root if user_root is not None else user_templates_root()
    return base / '.user-vars.json'


def _read_all(user_root: Path | None = None) -> dict[str, dict[str, Any]]:
    path = _vars_path(user_root)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _write_all(data: dict[str, dict[str, Any]], user_root: Path | None = None) -> None:
    path = _vars_path(user_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(data, ensure_ascii=False, indent=2)
    with _write_lock:
        tmp = path.with_name(f'{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex[:8]}.tmp')
        try:
            tmp.write_text(encoded, encoding='utf-8')
            tmp.replace(path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise


def coerce_var_value(spec_var: TemplateVariableSpec, value: Any) -> str | float | bool | None:
    """Validate and coerce one candidate value against its variable schema. Returns None if invalid."""
    if spec_var.kind == 'color':
        if isinstance(value, str) and _HEX_COLOR_RE.match(value.strip()):
            return value.strip()
        return None
    if spec_var.kind == 'boolean':
        if isinstance(value, bool):
            return value
        return None
    if spec_var.kind == 'number':
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        num = float(value)
        if spec_var.min is not None and num < spec_var.min:
            num = float(spec_var.min)
        if spec_var.max is not None and num > spec_var.max:
            num = float(spec_var.max)
        return num
    if spec_var.kind == 'select':
        if isinstance(value, str) and value in spec_var.options:
            return value
        return None
    return None


def read_user_vars(template_id: str, *, user_root: Path | None = None) -> dict[str, Any]:
    all_vars = _read_all(user_root)
    entry = all_vars.get(template_id)
    return dict(entry) if isinstance(entry, dict) else {}


def write_user_vars(
    spec: TemplateSpec,
    overrides: dict[str, Any],
    *,
    user_root: Path | None = None,
) -> dict[str, str | float | bool]:
    """Validate and persist user variable overrides for a template, returning resolved values."""
    by_key = {v.key: v for v in spec.variables}
    cleaned: dict[str, str | float | bool] = {}
    for key, val in (overrides or {}).items():
        if key not in by_key:
            continue
        coerced = coerce_var_value(by_key[key], val)
        if coerced is not None:
            cleaned[key] = coerced
    all_vars = _read_all(user_root)
    if cleaned:
        all_vars[spec.id] = cleaned
    else:
        all_vars.pop(spec.id, None)
    _write_all(all_vars, user_root)
    return resolved_vars(spec, overrides=cleaned, user_root=user_root)


def resolved_vars(
    spec: TemplateSpec,
    *,
    overrides: dict[str, Any] | None = None,
    user_root: Path | None = None,
) -> dict[str, str | float | bool]:
    """Merge spec defaults, persisted user overrides, and explicit runtime overrides."""
    merged: dict[str, str | float | bool] = spec.default_vars()
    if not spec.variables:
        return merged
    by_key = {v.key: v for v in spec.variables}
    saved = read_user_vars(spec.id, user_root=user_root)
    for src in (saved, overrides or {}):
        for key, val in src.items():
            if key not in by_key:
                continue
            coerced = coerce_var_value(by_key[key], val)
            if coerced is not None:
                merged[key] = coerced
    return merged
