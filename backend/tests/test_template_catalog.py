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
    } <= set(found)
    for name in found:
        spec, info = template_factory.verify_folder(catalog_root / name)
        assert spec.id == name
        assert set(info['previews']) == {'poster.webp', 'preview.mp4', 'preview.webm'}
