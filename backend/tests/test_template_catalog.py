"""End-to-end tests for dynamic template discovery, declarative spec v2,
security gates, remote GitHub Releases catalog sync, hot-installation,
and the automated template_factory.py CLI.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from backend.services.studio.models import Draft, ImportOptions, OutputVariant, Packaging, Scene
from backend.services.studio.overlay_fill import build_fill, caption_line_limit
from backend.services.studio.packaging_html import composite_tail
from backend.services.studio.templates import catalog, registry
from backend.services.studio.templates.registry import TemplateRegistryError, load_folder
from scripts import template_factory


def _scaffold_template(base: Path, slug: str = 'geek_note') -> Path:
    rc = template_factory.main([
        'scaffold', slug,
        '--name-zh', '极客笔记',
        '--name-en', 'Geek Note',
        '--out', str(base),
    ])
    assert rc == 0
    return base / slug


def _zip_dir(folder: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for item in sorted(folder.rglob('*')):
            if item.is_file():
                zf.write(item, f'{folder.name}/{item.relative_to(folder).as_posix()}')
    return buf.getvalue()


def test_scaffold_pack_build_catalog_and_hot_install_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    src_root = tmp_path / 'src_templates'
    dist_dir = tmp_path / 'dist'
    folder = _scaffold_template(src_root, 'geek_note')

    # Add a small dummy preview poster to verify preview asset packaging & serving.
    preview_dir = folder / 'preview'
    preview_dir.mkdir()
    (preview_dir / 'poster.webp').write_bytes(b'RIFF\x00\x00\x00\x00WEBPVP8 ')

    assert template_factory.main(['verify', str(folder)]) == 0
    assert template_factory.main(['pack', str(folder), '--out', str(dist_dir)]) == 0
    catalog_out = dist_dir / 'catalog.json'
    assert template_factory.main([
        'build-catalog', str(dist_dir),
        '--base-url', 'https://github.com/zhouxiaoka/autoclip-templates/releases/download/v1',
        '--out', str(catalog_out),
    ]) == 0

    catalog_bytes = catalog_out.read_bytes()
    zip_bytes = (dist_dir / 'geek_note-1.0.0.zip').read_bytes()

    def fake_fetcher(url: str, **_kwargs):
        if url.endswith('/catalog.json'):
            return 200, catalog_bytes, {'etag': '"v1"'}
        if url.endswith('/geek_note-1.0.0.zip'):
            return 200, zip_bytes, {}
        return 404, b'', {}

    # 1. Sync remote catalog into isolated AUTOCLIP_DATA_DIR.
    manifest = catalog.sync_catalog(
        force=True,
        url='https://github.com/zhouxiaoka/autoclip-templates/releases/download/v1/catalog.json',
        fetcher=fake_fetcher,
    )
    assert [e.id for e in manifest.templates] == ['geek_note']

    # Before install, geek_note appears as source='remote', installed=False.
    before = catalog.list_template_items(include_remote=True)
    remote_item = next(item for item in before['templates'] if item['id'] == 'geek_note')
    assert remote_item['source'] == 'remote' and remote_item['installed'] is False
    assert not registry.is_html_template('geek_note')

    # 2. Hot-install from remote catalog with SHA-256 verification.
    loaded = catalog.install_remote_template('geek_note', fetcher=fake_fetcher)
    assert loaded.spec.id == 'geek_note'
    assert loaded.source == 'installed'
    assert registry.is_html_template('geek_note')
    assert registry.is_valid_style('geek_note')
    assert registry.resolve_dir('geek_note') == loaded.root

    # 3. Dynamic template is immediately accepted by models, overlay_fill, and composite_tail!
    assert ImportOptions(html_template='geek_note').html_template == 'geek_note'
    assert Draft(id='d1', title='T', scenes=[Scene(id='s1', start=0.0, end=2.0)], html_template='geek_note').html_template == 'geek_note'
    assert OutputVariant(id='v1', draft_id='d1', draft_revision=1, strategy_id='xiaohongshu', html_template='geek_note').html_template == 'geek_note'
    pkg = Packaging(
        version=2, template='geek_note', audience_language='zh',
        title_lines=['Agent 自动合 PR'],
        cues=[{'start': 0.0, 'end': 2.0, 'text': '这是一条动态安装的模板字幕', 'original': 'Dynamic template caption'}],
    )
    assert caption_line_limit('geek_note') == (1080 - 2 * 64) // 48
    fill = build_fill(pkg, 2.5, template='geek_note')
    assert fill['moments']
    graph, label = composite_tail('v0', 1, 1080, 1920, loaded.spec.base.grade, template='geek_note', offset=0.0, total=2.5)
    assert '[scrim]' in graph and '[bar]' in graph and label == 'paced'

    # 4. Local preview asset resolves from installed folder.
    poster = catalog.resolve_preview_asset('geek_note', 'poster.webp')
    assert poster is not None and poster.is_file()

    # 5. Uninstall removes user template cleanly while keeping built-ins intact.
    assert catalog.uninstall_template('geek_note') is True
    assert not registry.is_html_template('geek_note')
    assert registry.is_html_template('editorial')


def test_security_gates_reject_network_clock_zipslip_and_bad_sha256(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    folder = _scaffold_template(tmp_path / 'src', 'bad_tpl')

    # External URL in CSS is rejected.
    (folder / 'style.css').write_text('body { background: url(https://evil.example/bg.png); }\n', encoding='utf-8')
    with pytest.raises(TemplateRegistryError, match='外部网络资源'):
        load_folder(folder)

    # Restore CSS, inject fetch() in JS -> rejected.
    folder = _scaffold_template(tmp_path / 'src2', 'bad_js')
    (folder / 'template.js').write_text(
        (folder / 'template.js').read_text(encoding='utf-8') + '\nfetch("https://evil.example");\n',
        encoding='utf-8',
    )
    with pytest.raises(TemplateRegistryError, match='禁止的调用'):
        load_folder(folder)

    # SHA-256 mismatch is rejected before extraction.
    good_folder = _scaffold_template(tmp_path / 'src3', 'good_tpl')
    good_zip = _zip_dir(good_folder)
    wrong_sha = hashlib.sha256(b'not-the-archive').hexdigest()
    with pytest.raises(catalog.TemplateCatalogError, match='SHA-256'):
        catalog.install_from_archive(good_zip, expected_sha256=wrong_sha)

    # Zip-slip path traversal is rejected.
    slip_buf = io.BytesIO()
    with zipfile.ZipFile(slip_buf, 'w') as zf:
        zf.writestr('../escape.txt', 'pwned')
    with pytest.raises(catalog.TemplateCatalogError, match='非法路径'):
        catalog.install_from_archive(slip_buf.getvalue())


def test_sync_catalog_treats_http_404_as_empty_remote_list(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    manifest = catalog.sync_catalog(
        force=True,
        url='https://github.com/zhouxiaoka/autoclip-templates/releases/latest/download/catalog.json',
        fetcher=lambda _url, **_kw: (404, b'', {}),
    )
    assert manifest.templates == []
    listed = catalog.list_template_items(include_remote=True)
    assert any(item['id'] == 'editorial' for item in listed['templates'])


def test_sync_catalog_falls_back_across_mirrors(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    tried = []

    def mirror_fetcher(url: str, **_kw):
        tried.append(url)
        if 'primary.example' in url:
            raise catalog.TemplateCatalogError('timeout')
        payload = json.dumps({'schema_version': 1, 'updated_at': '2026-11-24T00:00:00Z', 'templates': []}).encode()
        return 200, payload, {'etag': '"mirror-ok"'}

    manifest = catalog.sync_catalog(
        force=True,
        urls=['https://primary.example/catalog.json', 'https://mirror.example/catalog.json'],
        fetcher=mirror_fetcher,
    )
    assert manifest.updated_at == '2026-11-24T00:00:00Z'
    assert tried == ['https://primary.example/catalog.json', 'https://mirror.example/catalog.json']


def test_all_shipping_catalog_templates_pass_factory_verify():
    catalog_root = Path(__file__).resolve().parents[2] / 'templates-catalog'
    found = sorted(p.name for p in catalog_root.iterdir() if p.is_dir() and (p / 'template.yaml').is_file())
    assert {
        'interview_card', 'xhs_note', 'podcast_dark',
        'streamer_split', 'gta_wasted', 'streamer_pip',
        'highlight_note', 'meme_setup', 'clean_pill',
    } <= set(found)
    for name in found:
        spec, info = template_factory.verify_folder(catalog_root / name)
        assert spec.id == name
        assert set(info['previews']) == {'poster.webp', 'preview.mp4', 'preview.webm'}


def test_concurrent_catalog_cache_writes_do_not_race(tmp_path):
    """Concurrent background sync + manual /templates/sync must not race on a shared .tmp file."""
    import threading
    from backend.services.studio.templates import catalog

    manifest = catalog.CatalogManifest(version=1, templates=[])
    errors: list[Exception] = []

    def worker(idx: int) -> None:
        try:
            for step in range(25):
                catalog._write_cached_catalog(manifest, etag=f'W/"{idx}-{step}"', user_root=tmp_path)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    loaded, meta = catalog.read_cached_catalog(user_root=tmp_path)
    assert loaded is not None
    assert meta['etag'].startswith('W/"')
    assert list(tmp_path.glob('*.tmp')) == []


def test_catalog_admin_filters_locale_min_version_badge_and_removed_ids(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    folder = _scaffold_template(tmp_path / 'src', 'installed_soft_hidden')
    catalog.install_from_archive(_zip_dir(folder), source_url='test')
    assert registry.is_html_template('installed_soft_hidden')

    sha = 'a' * 64
    base_url = 'https://github.com/zhouxiaoka/autoclip/releases/download/templates-catalog'
    payload = {
        'schema_version': 1,
        'catalog_revision': 7,
        'updated_at': '2026-11-25T12:00:00Z',
        'removed_ids': ['installed_soft_hidden', 'remote_removed'],
        'templates': [
            {
                'id': 'global_new',
                'version': '1.0.0',
                'name': {'zh': '全球新模版', 'en': 'Global New'},
                'sha256': sha,
                'download_url': f'{base_url}/global_new-1.0.0.zip',
                'badge': 'new',
                'target_locales': [],
                'min_app_version': '1.6.1',
            },
            {
                'id': 'zh_only',
                'version': '1.0.0',
                'name': {'zh': '中文专属', 'en': 'ZH Only'},
                'sha256': sha,
                'download_url': f'{base_url}/zh_only-1.0.0.zip',
                'target_locales': ['zh'],
                'min_app_version': '1.6.1',
            },
            {
                'id': 'future_app_only',
                'version': '1.0.0',
                'name': {'zh': '未来版本', 'en': 'Future App'},
                'sha256': sha,
                'download_url': f'{base_url}/future_app_only-1.0.0.zip',
                'min_app_version': '2.0.0',
            },
            {
                'id': 'unlisted_tpl',
                'version': '1.0.0',
                'name': {'zh': '已下架', 'en': 'Unlisted'},
                'sha256': sha,
                'download_url': f'{base_url}/unlisted_tpl-1.0.0.zip',
                'status': 'unlisted',
            },
            {
                'id': 'remote_removed',
                'version': '1.0.0',
                'name': {'zh': '软隐藏远端', 'en': 'Removed Remote'},
                'sha256': sha,
                'download_url': f'{base_url}/remote_removed-1.0.0.zip',
            },
        ],
    }
    catalog.sync_catalog(
        force=True,
        url=f'{base_url}/catalog.json',
        fetcher=lambda _u, **_kw: (200, json.dumps(payload).encode('utf-8'), {}),
    )

    en_items = catalog.list_template_items(include_remote=True, locale='en-US', app_version='1.6.2')['templates']
    en_ids = {item['id'] for item in en_items}
    assert 'global_new' in en_ids
    assert 'zh_only' not in en_ids
    assert 'future_app_only' not in en_ids
    assert 'unlisted_tpl' not in en_ids
    assert 'remote_removed' not in en_ids
    assert 'installed_soft_hidden' not in en_ids
    # Installed template files remain intact for existing drafts!
    assert registry.is_html_template('installed_soft_hidden')
    global_item = next(item for item in en_items if item['id'] == 'global_new')
    assert global_item['badge'] == 'new'

    zh_items = catalog.list_template_items(include_remote=True, locale='zh-CN', app_version='1.6.2')['templates']
    assert 'zh_only' in {item['id'] for item in zh_items}


def test_template_factory_build_ingest_payload():
    entry = {
        'id': 'highlight_note',
        'version': '1.0.0',
        'name': {'en': 'Highlight Note', 'zh': '干货高光纸条'},
        'desc': {'en': 'Highlighter tape', 'zh': '荧光黄胶带'},
        'category': 'knowledge',
        'tags': ['knowledge', 'highlight'],
        'min_app_version': '1.6.1',
        'sha256': 'b' * 64,
        'size_bytes': 175855,
        'download_url': 'https://github.com/zhouxiaoka/autoclip/releases/download/templates-catalog/highlight_note-1.0.0.zip',
        'poster_url': 'https://github.com/zhouxiaoka/autoclip/releases/download/templates-catalog/highlight_note-1.0.0.poster.webp',
        'preview_mp4_url': 'https://github.com/zhouxiaoka/autoclip/releases/download/templates-catalog/highlight_note-1.0.0.preview.mp4',
        'preview_webm_url': 'https://github.com/zhouxiaoka/autoclip/releases/download/templates-catalog/highlight_note-1.0.0.preview.webm',
    }
    body = template_factory.build_ingest_payload(entry, target_region='global', auto_publish=True, badge='new')
    assert body['id'] == 'highlight_note'
    assert body['target_region'] == 'global'
    assert body['badge'] == 'new'
    assert body['auto_publish'] is True
    assert body['sha256'] == 'b' * 64


def test_catalog_overrides_builtin_order_featured_locale_and_unlisted(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    sha = 'c' * 64
    base_url = 'https://github.com/zhouxiaoka/autoclip/releases/download/templates-catalog'
    payload = {
        'schema_version': 1,
        'catalog_revision': 8,
        'updated_at': '2026-11-25T13:00:00Z',
        'templates': [
            {
                'id': 'cloud_top',
                'version': '1.0.0',
                'name': {'zh': '云端置顶', 'en': 'Cloud Top'},
                'sha256': sha,
                'download_url': f'{base_url}/cloud_top-1.0.0.zip',
                'order': 5,
                'featured': True,
                'badge': 'new',
            },
        ],
        'overrides': {
            'editorial': {'order': 10, 'featured': True, 'badge': 'hot', 'target_locales': [], 'status': 'published'},
            'street': {'order': 20, 'target_locales': ['zh'], 'status': 'published'},
            'news': {'order': 90, 'status': 'unlisted'},
            'classic': {'order': 950, 'status': 'unlisted'},
        },
        'removed_ids': ['news'],
    }
    catalog.sync_catalog(
        force=True,
        url=f'{base_url}/catalog.json',
        fetcher=lambda _u, **_kw: (200, json.dumps(payload).encode('utf-8'), {}),
    )

    en_items = catalog.list_template_items(include_remote=True, locale='en-US', app_version='1.6.2')['templates']
    en_ids = [item['id'] for item in en_items]
    # Cloud featured (order 5) comes BEFORE built-in featured editorial (order 10) -> true interleaved equality!
    assert en_ids[:2] == ['cloud_top', 'editorial']
    assert 'street' not in en_ids  # zh-only override hides street for en-US
    assert 'news' not in en_ids  # unlisted + removed_ids hides news from picker
    assert 'classic' not in en_ids  # unlisted hides classic from picker
    # Built-in news files remain renderable for existing drafts!
    assert registry.is_html_template('news')
    editorial_item = next(item for item in en_items if item['id'] == 'editorial')
    assert editorial_item['featured'] is True and editorial_item['badge'] == 'hot' and editorial_item['order'] == 10

    zh_items = catalog.list_template_items(include_remote=True, locale='zh-CN', app_version='1.6.2')['templates']
    assert 'street' in [item['id'] for item in zh_items]


def test_install_remote_template_falls_back_to_cos_mirror_and_system_proxy_direct_retry(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    monkeypatch.delenv('AUTOCLIP_TEMPLATE_CATALOG_URL', raising=False)
    monkeypatch.delenv('AUTOCLIP_TEMPLATE_CATALOG_MIRRORS', raising=False)

    # 1. Archive download falls back from GitHub Release URL to Shanghai COS mirror when GitHub times out
    folder = _scaffold_template(tmp_path / 'src_mirror', 'mirror_demo')
    zip_bytes = _zip_dir(folder)
    sha = hashlib.sha256(zip_bytes).hexdigest()
    gh_url = 'https://github.com/zhouxiaoka/autoclip/releases/download/templates-catalog/mirror_demo-1.0.0.zip'
    cos_url = 'https://autoclip-config-1311545920.cos.ap-shanghai.myqcloud.com/templates-catalog/mirror_demo-1.0.0.zip'
    manifest = catalog.CatalogManifest(
        schema_version=1,
        templates=[
            catalog.CatalogEntry(
                id='mirror_demo',
                version='1.0.0',
                name={'zh': '镜像测试', 'en': 'Mirror Demo'},
                sha256=sha,
                download_url=gh_url,
                size_bytes=len(zip_bytes),
            )
        ],
    )
    tried: list[str] = []

    def archive_fetcher(url: str, **_kw):
        tried.append(url)
        if 'github.com' in url:
            raise catalog.TemplateCatalogError('timeout')
        return 200, zip_bytes, {}

    loaded = catalog.install_remote_template('mirror_demo', catalog=manifest, fetcher=archive_fetcher)
    assert loaded.spec.id == 'mirror_demo'
    assert tried == [gh_url, cos_url]

    # 2. _open_with_proxy_fallback retries direct when OS/registry proxy is set (urllib.request.getproxies()) even if env vars are empty
    for key in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(catalog.urllib.request, 'getproxies', lambda: {'https': 'http://127.0.0.1:7890'})
    monkeypatch.setattr(catalog.urllib.request, 'urlopen', lambda *_a, **_kw: (_ for _ in ()).throw(TimeoutError('proxy dead')))

    direct_calls: list[str] = []

    class FakeDirectOpener:
        def open(self, req, *, timeout):
            direct_calls.append(req.full_url)
            return 'direct-ok'

    monkeypatch.setattr(catalog.urllib.request, 'build_opener', lambda *_a, **_kw: FakeDirectOpener())
    req = catalog.urllib.request.Request(cos_url)
    assert catalog._open_with_proxy_fallback(req, timeout=6.0) == 'direct-ok'
    assert direct_calls == [cos_url]
