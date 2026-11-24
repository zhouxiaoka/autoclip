"""Load and validate shipping + user-installed HTML packaging templates.

Built-in templates live under ``backend/assets/templates/<id>/``.
User-installed / hot-updated templates live under ``<data_dir>/templates/<id>/``.

Invalid built-in templates raise at import time. Invalid user-installed folders
are logged and skipped so a corrupted download never breaks app startup.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import ValidationError

from backend.core.path_utils import get_data_directory
from backend.services.studio.templates.spec import (
    BUILTIN_TEMPLATE_IDS,
    HTML_TEMPLATE_IDS,
    TemplateSpec,
    is_valid_template_slug,
)

logger = logging.getLogger(__name__)

ASSET_ROOT = Path(__file__).resolve().parents[3] / 'assets' / 'templates'
PAGE_FILES = ('index.html', 'template.js', 'style.css')
PAGE_HOOKS = ('window.setData', 'window.renderFrame', 'window.occupiedRects')

# Network / runtime-clock / non-deterministic patterns forbidden inside templates.
_FORBIDDEN_SCRIPT_TOKENS = (
    'Date.now',
    'performance.now',
    'fetch(',
    'XMLHttpRequest',
    'WebSocket',
    'importScripts',
    'sendBeacon',
)
_EXTERNAL_URL_RE = re.compile(r'https?://', re.IGNORECASE)
_ALLOWED_XMLNS_RE = re.compile(r'https?://www\.w3\.org/(2000/svg|1999/xlink)\b', re.IGNORECASE)


class TemplateRegistryError(RuntimeError):
    """One or more template folders failed validation."""


@dataclass(frozen=True)
class LoadedTemplate:
    spec: TemplateSpec
    root: Path
    source: Literal['builtin', 'installed']
    installed_meta: dict | None = None


def user_templates_root() -> Path:
    """User-installed template directory under the isolated app data directory."""
    return get_data_directory() / 'templates'


def _strip_allowed_xmlns(text: str) -> str:
    return _ALLOWED_XMLNS_RE.sub('', text)


def _read_yaml(path: Path) -> dict:
    try:
        loaded = yaml.safe_load(path.read_text(encoding='utf-8'))
    except (OSError, yaml.YAMLError) as error:
        raise TemplateRegistryError(f'{path.parent.name}: 无法读取 template.yaml') from error
    if not isinstance(loaded, dict):
        raise TemplateRegistryError(f'{path.parent.name}: template.yaml 必须是映射')
    return loaded


def _page_contract(folder: Path) -> None:
    missing = [name for name in PAGE_FILES if not (folder / name).is_file()]
    if missing:
        raise TemplateRegistryError(f'{folder.name}: 缺少 {", ".join(missing)}')
    html = (folder / 'index.html').read_text(encoding='utf-8')
    script = (folder / 'template.js').read_text(encoding='utf-8')
    style = (folder / 'style.css').read_text(encoding='utf-8')
    if 'template.js' not in html or 'style.css' not in html:
        raise TemplateRegistryError(f'{folder.name}: index.html 必须引用 template.js 和 style.css')
    absent = [hook for hook in PAGE_HOOKS if hook not in script]
    if absent:
        raise TemplateRegistryError(f'{folder.name}: template.js 缺少 {", ".join(absent)}')
    if 'Date.now' in script or 'performance.now' in script or '@keyframes' in style or 'animation:' in style:
        raise TemplateRegistryError(f'{folder.name}: 画面不能依赖真实时钟或 CSS 动画')
    for token in _FORBIDDEN_SCRIPT_TOKENS:
        if token in script:
            raise TemplateRegistryError(f'{folder.name}: template.js 包含禁止的调用 {token}')
    for filename, content in (('index.html', html), ('template.js', script), ('style.css', style)):
        if _EXTERNAL_URL_RE.search(_strip_allowed_xmlns(content)):
            raise TemplateRegistryError(f'{folder.name}: {filename} 不能引用外部网络资源')


def load_folder(folder: Path) -> TemplateSpec:
    """Validate one template directory. A failure never returns a partial spec."""
    if not is_valid_template_slug(folder.name):
        raise TemplateRegistryError(f'{folder.name}: 目录名不是合法的模板 slug')
    spec_path = folder / 'template.yaml'
    if not spec_path.is_file():
        raise TemplateRegistryError(f'{folder.name}: 缺少 template.yaml')
    _page_contract(folder)
    try:
        spec = TemplateSpec.model_validate(_read_yaml(spec_path))
    except ValidationError as error:
        raise TemplateRegistryError(f'{folder.name}: 模板配置未通过校验') from error
    if spec.id != folder.name:
        raise TemplateRegistryError(f'{folder.name}: id 与目录名不一致')
    return spec


def load_directory(root: Path, *, require_builtins: bool = False) -> dict[str, TemplateSpec]:
    """Validate every template folder under ``root``. The first failure aborts the load."""
    if not root.is_dir():
        raise TemplateRegistryError(f'模板目录不存在: {root.name}')
    found: dict[str, TemplateSpec] = {}
    for folder in sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith('.')):
        spec = load_folder(folder)
        found[spec.id] = spec
    if require_builtins and not set(HTML_TEMPLATE_IDS).issubset(found):
        missing = [name for name in HTML_TEMPLATE_IDS if name not in found]
        raise TemplateRegistryError('缺少内置模板目录: ' + '、'.join(missing))
    return found


def load_shipping() -> dict[str, TemplateSpec]:
    return load_directory(ASSET_ROOT, require_builtins=True)


def _read_installed_meta(folder: Path) -> dict | None:
    meta_path = folder / '.installed.json'
    if not meta_path.is_file():
        return None
    try:
        parsed = json.loads(meta_path.read_text(encoding='utf-8'))
        return parsed if isinstance(parsed, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _version_tuple(version: str) -> tuple[int, ...]:
    core = (version or '0.0.0').split('-', 1)[0]
    parts: list[int] = []
    for piece in core.split('.'):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def load_user_templates(root: Path | None = None) -> dict[str, LoadedTemplate]:
    """Scan user-installed templates; invalid folders are skipped rather than crashing."""
    base = root if root is not None else user_templates_root()
    if not base.is_dir():
        return {}
    found: dict[str, LoadedTemplate] = {}
    for folder in sorted(path for path in base.iterdir() if path.is_dir() and not path.name.startswith('.')):
        try:
            spec = load_folder(folder)
        except TemplateRegistryError as error:
            logger.warning('Skipping invalid user template %s: %s', folder.name, error)
            continue
        found[spec.id] = LoadedTemplate(
            spec=spec,
            root=folder,
            source='installed',
            installed_meta=_read_installed_meta(folder),
        )
    return found


TEMPLATES = load_shipping()
_BUILTIN_LOADED: dict[str, LoadedTemplate] = {
    tid: LoadedTemplate(spec=spec, root=ASSET_ROOT / tid, source='builtin')
    for tid, spec in TEMPLATES.items()
}


def all_templates(*, user_root: Path | None = None) -> dict[str, LoadedTemplate]:
    """Merge built-in templates with user-installed templates.

    User-installed templates with a newer package_version may override a built-in
    template of the same id.
    """
    merged = dict(_BUILTIN_LOADED)
    for tid, loaded in load_user_templates(user_root).items():
        existing = merged.get(tid)
        if existing is None:
            merged[tid] = loaded
            continue
        new_v = _version_tuple(loaded.spec.effective_meta().package_version)
        old_v = _version_tuple(existing.spec.effective_meta().package_version)
        if new_v >= old_v:
            merged[tid] = loaded
    return merged


def _ordered_entries(entries: dict[str, LoadedTemplate]) -> list[LoadedTemplate]:
    builtin_rank = {tid: idx for idx, tid in enumerate(BUILTIN_TEMPLATE_IDS)}
    return sorted(
        entries.values(),
        key=lambda item: (
            item.spec.effective_meta().order,
            builtin_rank.get(item.spec.id, 999),
            item.spec.id,
        ),
    )


def list_loaded(*, user_root: Path | None = None) -> list[LoadedTemplate]:
    return _ordered_entries(all_templates(user_root=user_root))


def get_loaded(template_id: str, *, user_root: Path | None = None) -> LoadedTemplate:
    entries = all_templates(user_root=user_root)
    try:
        return entries[template_id]
    except KeyError as error:
        raise TemplateRegistryError(f'未知 HTML 模板: {template_id}') from error


def get(template_id: str, *, user_root: Path | None = None) -> TemplateSpec:
    return get_loaded(template_id, user_root=user_root).spec


def resolve_dir(template_id: str, *, user_root: Path | None = None) -> Path:
    return get_loaded(template_id, user_root=user_root).root


def ids(*, user_root: Path | None = None) -> tuple[str, ...]:
    return tuple(item.spec.id for item in list_loaded(user_root=user_root))


def style_ids(*, user_root: Path | None = None) -> tuple[str, ...]:
    return (*ids(user_root=user_root), 'classic')


def is_html_template(template_id: str | None, *, user_root: Path | None = None) -> bool:
    if not template_id or not isinstance(template_id, str):
        return False
    return template_id in all_templates(user_root=user_root)


def is_valid_style(template_id: str | None, *, user_root: Path | None = None) -> bool:
    if template_id == 'classic':
        return True
    return is_html_template(template_id, user_root=user_root)
