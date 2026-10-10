"""Load and validate the shipping HTML templates.

Invalid templates raise at import time. They are not added to the candidate
set, and a later render never sees a half-loaded page.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from backend.services.studio.templates.spec import HTML_TEMPLATE_IDS, TemplateSpec

ASSET_ROOT = Path(__file__).resolve().parents[3] / 'assets' / 'templates'
PAGE_FILES = ('index.html', 'template.js', 'style.css')
PAGE_HOOKS = ('window.setData', 'window.renderFrame', 'window.occupiedRects')


class TemplateRegistryError(RuntimeError):
    """One or more template folders failed validation."""


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


def load_folder(folder: Path) -> TemplateSpec:
    """Validate one template directory. A failure never returns a partial spec."""
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


def load_directory(root: Path) -> dict[str, TemplateSpec]:
    """Validate every template folder under ``root``. The first failure aborts the load."""
    if not root.is_dir():
        raise TemplateRegistryError(f'模板目录不存在: {root.name}')
    found: dict[str, TemplateSpec] = {}
    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        spec = load_folder(folder)
        found[spec.id] = spec
    if set(found) != set(HTML_TEMPLATE_IDS):
        raise TemplateRegistryError('v1 只接受 editorial 和 street')
    return found


def load_shipping() -> dict[str, TemplateSpec]:
    return load_directory(ASSET_ROOT)


TEMPLATES = load_shipping()


def get(template_id: str) -> TemplateSpec:
    try:
        return TEMPLATES[template_id]
    except KeyError as error:
        raise TemplateRegistryError(f'未知 HTML 模板: {template_id}') from error


def ids() -> tuple[str, ...]:
    return tuple(TEMPLATES)
