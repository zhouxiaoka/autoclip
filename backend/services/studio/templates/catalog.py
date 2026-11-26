"""Remote GitHub Releases template catalog sync and safe hot-installation.

Templates are distributed as versioned zip packs referenced by a ``catalog.json``
manifest (by default hosted on GitHub Releases, configurable via
``AUTOCLIP_TEMPLATE_CATALOG_URL``). Every downloaded archive is verified for:
  1. Size cap (15 MB compressed, 30 MB uncompressed)
  2. Exact SHA-256 digest match
  3. Safe zip paths (no path traversal, no absolute paths, no symlinks)
  4. Full ``TemplateSpec`` + page security/determinism contract via ``load_folder``

Only after all checks pass is the template atomically moved into
``<data_dir>/templates/<id>/``.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import shutil
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.core.failure_codes import UserFacingError
from backend.services.studio.templates import registry
from backend.services.studio.templates.registry import TemplateRegistryError, load_folder, user_templates_root
from backend.services.studio.templates.spec import LocalizedText, NameSpec, is_valid_template_slug

logger = logging.getLogger(__name__)

DEFAULT_CATALOG_URL = 'https://github.com/zhouxiaoka/autoclip/releases/download/templates-catalog/catalog.json'
CATALOG_CACHE_TTL_SEC = 3600
CATALOG_TIMEOUT_SEC = 5.0
ARCHIVE_TIMEOUT_SEC = 30.0
MAX_CATALOG_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_BYTES = 15 * 1024 * 1024
MAX_EXTRACTED_BYTES = 30 * 1024 * 1024
PREVIEW_ASSET_NAMES = ('poster.webp', 'preview.mp4', 'preview.webm')


class TemplateCatalogError(UserFacingError):
    """Raised when catalog sync, verification, or archive installation fails."""


def _allowed_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == 'https' and bool(parsed.netloc):
        return True
    if parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost', '::1'}:
        return True
    return False


class CatalogEntry(BaseModel):
    model_config = ConfigDict(extra='ignore')
    id: str
    version: str = Field(pattern=r'^\d+\.\d+\.\d+([-.][a-zA-Z0-9.]+)?$')
    name: NameSpec
    desc: LocalizedText | None = None
    tags: list[str] = Field(default_factory=list, max_length=12)
    category: str = Field(default='general', min_length=1, max_length=32)
    order: int = Field(default=100, ge=0, le=10000)
    sha256: str = Field(pattern=r'^[0-9a-fA-F]{64}$')
    download_url: str = Field(min_length=8, max_length=2048)
    size_bytes: int = Field(default=0, ge=0, le=MAX_ARCHIVE_BYTES)
    min_app_version: str | None = Field(default=None, max_length=32)
    author: str = Field(default='AutoClip', max_length=64)
    featured: bool = False
    badge: str | None = Field(default=None, max_length=24)
    status: str = Field(default='published', max_length=24)
    target_locales: list[str] = Field(default_factory=list, max_length=16)
    poster_url: str | None = Field(default=None, max_length=2048)
    preview_mp4_url: str | None = Field(default=None, max_length=2048)
    preview_webm_url: str | None = Field(default=None, max_length=2048)

    @field_validator('id')
    @classmethod
    def valid_id(cls, value: str) -> str:
        if not is_valid_template_slug(value):
            raise ValueError(f'无效的模板 ID: {value}')
        return value

    @field_validator('download_url', 'poster_url', 'preview_mp4_url', 'preview_webm_url')
    @classmethod
    def valid_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not _allowed_url(value):
            raise ValueError('模板下载地址仅支持 HTTPS（或本地回环测试地址）')
        return value


class CatalogOverride(BaseModel):
    model_config = ConfigDict(extra='ignore')
    order: int | None = Field(default=None, ge=0, le=10000)
    featured: bool | None = None
    badge: str | None = Field(default=None, max_length=24)
    status: str | None = Field(default=None, max_length=24)
    target_locales: list[str] | None = Field(default=None, max_length=16)
    min_app_version: str | None = Field(default=None, max_length=32)


class CatalogManifest(BaseModel):
    model_config = ConfigDict(extra='ignore')
    schema_version: Literal[1] = 1
    catalog_revision: int | None = None
    updated_at: str = ''
    templates: list[CatalogEntry] = Field(default_factory=list)
    overrides: dict[str, CatalogOverride] = Field(default_factory=dict)
    removed_ids: list[str] = Field(default_factory=list)


def catalog_urls() -> list[str]:
    """Return ordered list of catalog.json URLs (primary + mirrors). Empty when disabled."""
    raw = os.getenv('AUTOCLIP_TEMPLATE_CATALOG_URL')
    if raw is None:
        primary = [DEFAULT_CATALOG_URL]
    else:
        cleaned = raw.strip()
        if not cleaned or cleaned.lower() in {'off', 'none', 'disabled', '0', 'false'}:
            return []
        primary = [u.strip() for u in cleaned.split(',') if u.strip()]
    mirrors_raw = os.getenv('AUTOCLIP_TEMPLATE_CATALOG_MIRRORS', '').strip()
    mirrors = [u.strip() for u in mirrors_raw.split(',') if u.strip()] if mirrors_raw else []
    seen: set[str] = set()
    ordered: list[str] = []
    for item in (*primary, *mirrors):
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def catalog_url() -> str | None:
    urls = catalog_urls()
    return urls[0] if urls else None


def _cache_path(user_root: Path | None = None) -> Path:
    base = user_root if user_root is not None else user_templates_root()
    return base / '.catalog-cache.json'


def read_cached_catalog(*, user_root: Path | None = None) -> tuple[CatalogManifest | None, dict]:
    path = _cache_path(user_root)
    if not path.is_file():
        return None, {}
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
        manifest = CatalogManifest.model_validate(raw.get('manifest') or {})
        meta = {'etag': raw.get('etag', ''), 'fetched_at': float(raw.get('fetched_at') or 0)}
        return manifest, meta
    except Exception:
        return None, {}


_cache_write_lock = threading.Lock()


def _write_cached_catalog(manifest: CatalogManifest, *, etag: str = '', user_root: Path | None = None) -> None:
    path = _cache_path(user_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'etag': etag,
        'fetched_at': time.time(),
        'manifest': manifest.model_dump(mode='json'),
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    with _cache_write_lock:
        tmp = path.with_name(f'{path.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex[:8]}.tmp')
        try:
            tmp.write_text(encoded, encoding='utf-8')
            tmp.replace(path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise


def _http_get(url: str, *, headers: dict[str, str] | None = None, timeout: float = CATALOG_TIMEOUT_SEC, max_bytes: int = MAX_CATALOG_BYTES) -> tuple[int, bytes, dict[str, str]]:
    if not _allowed_url(url):
        raise TemplateCatalogError('模板目录地址不安全，仅支持 HTTPS')
    req = urllib.request.Request(url, headers={'User-Agent': 'AutoClip-TemplateCatalog/1.0', **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            chunks: list[bytes] = []
            total = 0
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise TemplateCatalogError('远端模板文件超过体积上限')
                chunks.append(chunk)
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            return int(resp.status), b''.join(chunks), resp_headers
    except urllib.error.HTTPError as error:
        if error.code in (304, 404):
            return int(error.code), b'', {}
        raise TemplateCatalogError(f'拉取模板目录失败（HTTP {error.code}）') from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise TemplateCatalogError('无法连接模板目录，请稍后重试') from error


Fetcher = Callable[..., tuple[int, bytes, dict[str, str]]]


_bg_sync_lock = threading.Lock()
_bg_sync_running = False


def sync_catalog(
    *,
    force: bool = False,
    url: str | None = None,
    urls: list[str] | None = None,
    user_root: Path | None = None,
    fetcher: Fetcher | None = None,
) -> CatalogManifest:
    """Fetch remote ``catalog.json`` with ETag/TTL caching and multi-mirror fallback."""
    if urls is not None:
        candidates = [u for u in urls if u]
    elif url is not None:
        candidates = [url] if url else []
    else:
        candidates = catalog_urls()
    cached, meta = read_cached_catalog(user_root=user_root)
    if not candidates:
        return cached or CatalogManifest()
    if not force and cached is not None and (time.time() - meta.get('fetched_at', 0)) < CATALOG_CACHE_TTL_SEC:
        return cached

    headers: dict[str, str] = {}
    if meta.get('etag') and cached is not None and not force:
        headers['If-None-Match'] = meta['etag']

    do_fetch = fetcher or _http_get
    last_error: TemplateCatalogError | None = None
    saw_404 = False
    for target_url in candidates:
        try:
            status, body, resp_headers = do_fetch(
                target_url, headers=headers, timeout=CATALOG_TIMEOUT_SEC, max_bytes=MAX_CATALOG_BYTES,
            )
        except TemplateCatalogError as error:
            last_error = error
            logger.debug('Catalog mirror failed (%s): %s', target_url, error)
            continue
        if status == 304 and cached is not None:
            _write_cached_catalog(cached, etag=meta.get('etag', ''), user_root=user_root)
            return cached
        if status == 404:
            saw_404 = True
            continue
        try:
            parsed = json.loads(body.decode('utf-8'))
            manifest = CatalogManifest.model_validate(parsed)
        except Exception as error:
            last_error = TemplateCatalogError('远端模板目录格式无效')
            logger.debug('Catalog mirror returned invalid payload (%s): %s', target_url, error)
            continue
        _write_cached_catalog(manifest, etag=resp_headers.get('etag', ''), user_root=user_root)
        return manifest

    if saw_404 and last_error is None:
        empty = CatalogManifest()
        _write_cached_catalog(empty, etag='', user_root=user_root)
        return empty
    if last_error is not None:
        raise last_error
    return cached or CatalogManifest()


def trigger_background_sync(*, user_root: Path | None = None) -> bool:
    """Silently refresh a stale catalog in a daemon thread without blocking callers."""
    global _bg_sync_running
    if os.getenv('PYTEST_CURRENT_TEST') or not catalog_urls():
        return False
    cached, meta = read_cached_catalog(user_root=user_root)
    if cached is not None and (time.time() - meta.get('fetched_at', 0)) < CATALOG_CACHE_TTL_SEC:
        return False
    with _bg_sync_lock:
        if _bg_sync_running:
            return False
        _bg_sync_running = True

    def _run() -> None:
        global _bg_sync_running
        try:
            sync_catalog(force=False, user_root=user_root)
        except Exception:
            pass
        finally:
            with _bg_sync_lock:
                _bg_sync_running = False

    threading.Thread(target=_run, name='template-catalog-sync', daemon=True).start()
    return True


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


def _safe_extract_zip(archive_bytes: bytes, staging_dir: Path) -> Path:
    """Extract a template zip safely and return the folder containing ``template.yaml``."""
    if len(archive_bytes) > MAX_ARCHIVE_BYTES:
        raise TemplateCatalogError('模板包体积超过 15MB 上限')
    try:
        zf = zipfile.ZipFile(io.BytesIO(archive_bytes))
    except zipfile.BadZipFile as error:
        raise TemplateCatalogError('模板包不是有效的 ZIP 文件') from error

    with zf:
        total_uncompressed = 0
        members: list[tuple[zipfile.ZipInfo, Path]] = []
        for info in zf.infolist():
            if _is_symlink(info):
                raise TemplateCatalogError('模板包不允许包含符号链接')
            rel = Path(info.filename)
            if rel.is_absolute() or '..' in rel.parts:
                raise TemplateCatalogError('模板包包含非法路径')
            if any(part.startswith('__MACOSX') for part in rel.parts):
                continue
            total_uncompressed += info.file_size
            if total_uncompressed > MAX_EXTRACTED_BYTES:
                raise TemplateCatalogError('模板包解压后超过 30MB 上限')
            members.append((info, rel))

        for info, rel in members:
            dest = (staging_dir / rel).resolve()
            if not str(dest).startswith(str(staging_dir.resolve())):
                raise TemplateCatalogError('模板包路径越界')
            if info.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, 'r') as src, dest.open('wb') as dst:
                    shutil.copyfileobj(src, dst)

    if (staging_dir / 'template.yaml').is_file():
        return staging_dir
    subdirs = [p for p in staging_dir.iterdir() if p.is_dir() and not p.name.startswith('.')]
    if len(subdirs) == 1 and (subdirs[0] / 'template.yaml').is_file():
        return subdirs[0]
    raise TemplateCatalogError('模板包缺少 template.yaml')


def install_from_archive(
    archive_bytes: bytes,
    *,
    expected_sha256: str | None = None,
    expected_id: str | None = None,
    source_url: str = '',
    user_root: Path | None = None,
) -> registry.LoadedTemplate:
    """Verify, validate, and atomically install a template zip archive."""
    digest = hashlib.sha256(archive_bytes).hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.strip().lower():
        raise TemplateCatalogError('模板包 SHA-256 校验失败，已中止安装')

    base = user_root if user_root is not None else user_templates_root()
    base.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix='.stage-', dir=str(base)) as tmp:
        stage_root = Path(tmp)
        extracted = _safe_extract_zip(archive_bytes, stage_root)

        # Peek at template.yaml id so folder name matches spec.id before load_folder.
        raw_yaml = registry._read_yaml(extracted / 'template.yaml')
        declared_id = str(raw_yaml.get('id') or '').strip()
        if not is_valid_template_slug(declared_id):
            raise TemplateCatalogError(f'模板 ID 无效: {declared_id}')
        if expected_id and declared_id != expected_id:
            raise TemplateCatalogError(f'模板包 ID ({declared_id}) 与预期 ({expected_id}) 不一致')

        named_dir = stage_root / declared_id
        if extracted != named_dir:
            if named_dir.exists():
                shutil.rmtree(named_dir)
            if extracted == stage_root:
                named_dir.mkdir(parents=True)
                for item in list(stage_root.iterdir()):
                    if item != named_dir:
                        shutil.move(str(item), str(named_dir / item.name))
            else:
                extracted.rename(named_dir)

        try:
            spec = load_folder(named_dir)
        except TemplateRegistryError as error:
            raise TemplateCatalogError(f'模板未通过安全与契约校验: {error}') from error

        installed_meta = {
            'id': spec.id,
            'version': spec.effective_meta().package_version,
            'sha256': digest,
            'source_url': source_url,
            'installed_at': datetime.now(timezone.utc).isoformat(),
        }
        (named_dir / '.installed.json').write_text(
            json.dumps(installed_meta, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )

        target = base / spec.id
        backup: Path | None = None
        if target.exists():
            backup = base / f'.backup-{spec.id}-{uuid.uuid4().hex[:8]}'
            target.rename(backup)
        try:
            shutil.move(str(named_dir), str(target))
        except Exception:
            if backup and backup.exists() and not target.exists():
                backup.rename(target)
            raise
        else:
            if backup and backup.exists():
                shutil.rmtree(backup, ignore_errors=True)

    return registry.get_loaded(spec.id, user_root=base)


def install_remote_template(
    template_id: str,
    *,
    catalog: CatalogManifest | None = None,
    user_root: Path | None = None,
    fetcher: Fetcher | None = None,
) -> registry.LoadedTemplate:
    """Download and install a template by ID from the remote catalog."""
    manifest = catalog
    if manifest is None:
        manifest, _ = read_cached_catalog(user_root=user_root)
    if manifest is None:
        manifest = sync_catalog(force=True, user_root=user_root, fetcher=fetcher)

    entry = next((item for item in manifest.templates if item.id == template_id), None)
    if entry is None:
        manifest = sync_catalog(force=True, user_root=user_root, fetcher=fetcher)
        entry = next((item for item in manifest.templates if item.id == template_id), None)
    if entry is None:
        raise TemplateCatalogError(f'模板目录中未找到模板: {template_id}')

    do_fetch = fetcher or _http_get
    status, archive_bytes, _ = do_fetch(entry.download_url, timeout=ARCHIVE_TIMEOUT_SEC, max_bytes=MAX_ARCHIVE_BYTES)
    if status != 200 or not archive_bytes:
        raise TemplateCatalogError(f'下载模板包失败: {template_id}')
    return install_from_archive(
        archive_bytes,
        expected_sha256=entry.sha256,
        expected_id=entry.id,
        source_url=entry.download_url,
        user_root=user_root,
    )


def uninstall_template(template_id: str, *, user_root: Path | None = None) -> bool:
    """Remove a user-installed template folder. Built-in templates cannot be deleted."""
    if not is_valid_template_slug(template_id):
        raise TemplateCatalogError(f'无效的模板 ID: {template_id}')
    base = user_root if user_root is not None else user_templates_root()
    target = base / template_id
    if not target.is_dir():
        raise TemplateCatalogError(f'未安装可卸载的用户模板: {template_id}')
    shutil.rmtree(target)
    return True


def _local_preview_path(folder: Path, filename: str) -> Path | None:
    for candidate in (folder / 'preview' / filename, folder / filename):
        if candidate.is_file():
            return candidate
    return None


def resolve_preview_asset(template_id: str, filename: str, *, user_root: Path | None = None) -> Path | None:
    if filename not in PREVIEW_ASSET_NAMES:
        return None
    if not registry.is_html_template(template_id, user_root=user_root):
        return None
    folder = registry.resolve_dir(template_id, user_root=user_root)
    return _local_preview_path(folder, filename)


def _version_gt(candidate: str, current: str) -> bool:
    return registry._version_tuple(candidate) > registry._version_tuple(current)


def _current_app_version() -> str:
    env_ver = (os.getenv('AUTOCLIP_APP_VERSION') or '').strip()
    if env_ver:
        return env_ver
    try:
        from backend import __version__
        return str(__version__)
    except Exception:
        return '0.0.0'


def _app_version_allowed(min_app_version: str | None, current_app_version: str) -> bool:
    if not min_app_version or not min_app_version.strip():
        return True
    return registry._version_tuple(current_app_version) >= registry._version_tuple(min_app_version)


def _locale_allowed(target_locales: list[str], locale: str | None) -> bool:
    if not target_locales:
        return True
    if not locale or not locale.strip():
        return True
    norm = locale.strip().lower().replace('_', '-')
    short = norm.split('-', 1)[0]
    targets = {item.strip().lower().replace('_', '-') for item in target_locales if item and item.strip()}
    if not targets or 'global' in targets or '*' in targets:
        return True
    if 'overseas' in targets and short != 'zh':
        return True
    return norm in targets or short in targets


def list_template_items(
    *,
    include_remote: bool = True,
    user_root: Path | None = None,
    asset_prefix: str = '/api/v1/studio/templates',
    locale: str | None = None,
    app_version: str | None = None,
) -> dict:
    """Build the unified template catalog payload for frontend / CLI / MCP."""
    loaded_list = registry.list_loaded(user_root=user_root)
    loaded_map = {item.spec.id: item for item in loaded_list}
    remote_manifest, meta = read_cached_catalog(user_root=user_root) if include_remote else (None, {})
    remote_map = {entry.id: entry for entry in (remote_manifest.templates if remote_manifest else [])}
    overrides = remote_manifest.overrides if remote_manifest else {}
    removed_set = set(remote_manifest.removed_ids) if remote_manifest else set()
    effective_app_version = app_version or _current_app_version()

    def _resolve_shelf(
        item_id: str,
        *,
        default_order: int,
        remote: CatalogEntry | None = None,
    ) -> tuple[bool, int, bool, str | None]:
        """Resolve cloud shelf overrides -> (visible, order, featured, badge)."""
        ov = overrides.get(item_id)
        status = (
            ov.status if (ov and ov.status is not None)
            else (remote.status if remote else 'published')
        )
        if item_id in removed_set or (status or 'published').strip().lower() != 'published':
            return False, default_order, False, None
        min_ver = (
            ov.min_app_version if (ov and ov.min_app_version is not None)
            else (remote.min_app_version if remote else None)
        )
        if not _app_version_allowed(min_ver, effective_app_version):
            return False, default_order, False, None
        target_locales = (
            ov.target_locales if (ov and ov.target_locales is not None)
            else (remote.target_locales if remote else [])
        )
        if not _locale_allowed(target_locales, locale):
            return False, default_order, False, None
        order = (
            ov.order if (ov and ov.order is not None)
            else (remote.order if remote else default_order)
        )
        featured = bool(
            ov.featured if (ov and ov.featured is not None)
            else (remote.featured if remote else False)
        )
        badge = (
            ov.badge if (ov and ov.badge is not None)
            else (remote.badge if remote else None)
        )
        return True, order, featured, badge

    items: list[dict] = []
    for loaded in loaded_list:
        spec = loaded.spec
        m = spec.effective_meta()
        remote = remote_map.get(spec.id)
        visible, eff_order, eff_featured, eff_badge = _resolve_shelf(
            spec.id, default_order=m.order, remote=remote,
        )
        if not visible:
            # Soft-hide from new selection while keeping installed/built-in files intact for existing drafts.
            continue
        has_poster = _local_preview_path(loaded.root, 'poster.webp') is not None
        has_mp4 = _local_preview_path(loaded.root, 'preview.mp4') is not None
        has_webm = _local_preview_path(loaded.root, 'preview.webm') is not None
        items.append({
            'id': spec.id,
            'name': spec.name.model_dump(mode='json'),
            'desc': m.desc.model_dump(mode='json') if m.desc else {'zh': spec.name.zh, 'en': spec.name.en, 'locales': {}},
            'tags': m.tags,
            'category': m.category,
            'order': eff_order,
            'featured': eff_featured,
            'version': m.package_version,
            'source': loaded.source,
            'installed': True,
            'removable': loaded.source == 'installed',
            'update_available': bool(remote and _version_gt(remote.version, m.package_version)),
            'latest_version': remote.version if remote else m.package_version,
            'badge': eff_badge,
            'poster_url': f'{asset_prefix}/{spec.id}/assets/poster.webp' if has_poster else (remote.poster_url if remote else None),
            'preview_mp4_url': f'{asset_prefix}/{spec.id}/assets/preview.mp4' if has_mp4 else (remote.preview_mp4_url if remote else None),
            'preview_webm_url': f'{asset_prefix}/{spec.id}/assets/preview.webm' if has_webm else (remote.preview_webm_url if remote else None),
        })

    # Append built-in classic fallback unless cloud overrides hide it.
    classic_visible, classic_order, classic_featured, classic_badge = _resolve_shelf('classic', default_order=900)
    if classic_visible:
        items.append({
            'id': 'classic',
            'name': {'zh': '经典', 'en': 'Classic', 'locales': {}},
            'desc': {'zh': '经典清晰字幕与居中画框，稳定兼容所有设备', 'en': 'Classic clean captions compatible with every device', 'locales': {}},
            'tags': ['classic', 'fallback'],
            'category': 'classic',
            'order': classic_order,
            'featured': classic_featured,
            'version': '1.0.0',
            'source': 'builtin',
            'installed': True,
            'removable': False,
            'update_available': False,
            'latest_version': '1.0.0',
            'badge': classic_badge,
            'poster_url': None,
            'preview_mp4_url': None,
            'preview_webm_url': None,
        })

    # Append installable remote templates not yet installed locally.
    if remote_manifest:
        for entry in remote_manifest.templates:
            if entry.id in loaded_map:
                continue
            visible, eff_order, eff_featured, eff_badge = _resolve_shelf(
                entry.id, default_order=entry.order, remote=entry,
            )
            if not visible:
                continue
            items.append({
                'id': entry.id,
                'name': entry.name.model_dump(mode='json'),
                'desc': entry.desc.model_dump(mode='json') if entry.desc else {'zh': entry.name.zh, 'en': entry.name.en, 'locales': {}},
                'tags': entry.tags,
                'category': entry.category,
                'order': eff_order,
                'featured': eff_featured,
                'version': entry.version,
                'source': 'remote',
                'installed': False,
                'removable': False,
                'update_available': False,
                'latest_version': entry.version,
                'badge': eff_badge,
                'size_bytes': entry.size_bytes,
                'poster_url': entry.poster_url,
                'preview_mp4_url': entry.preview_mp4_url,
                'preview_webm_url': entry.preview_webm_url,
            })

    # Unified shelf sort across built-in, installed, and cloud templates:
    # featured desc, order asc, id asc.
    items.sort(key=lambda item: (not bool(item.get('featured')), int(item.get('order', 100)), str(item.get('id', ''))))

    remote_count = sum(1 for item in items if not item['installed'])
    return {
        'templates': items,
        'remote_count': remote_count,
        'catalog_url': catalog_url(),
        'catalog_updated_at': remote_manifest.updated_at if remote_manifest else '',
        'catalog_synced_at': meta.get('fetched_at', 0),
    }
