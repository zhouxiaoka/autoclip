#!/usr/bin/env python3
"""Automated Template Factory: scaffold, verify, pack, and publish catalog.json.

Usage:
  python scripts/template_factory.py scaffold my_style --name-zh "极客笔记" --name-en "Geek Note" --out ./templates
  python scripts/template_factory.py verify ./templates/my_style
  python scripts/template_factory.py pack ./templates/my_style --out ./dist-templates
  python scripts/template_factory.py build-catalog ./dist-templates \\
      --base-url https://github.com/zhouxiaoka/autoclip-templates/releases/latest/download \\
      --out ./dist-templates/catalog.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.studio.templates.catalog import (
    MAX_ARCHIVE_BYTES,
    MAX_EXTRACTED_BYTES,
    PREVIEW_ASSET_NAMES,
    CatalogEntry,
    CatalogManifest,
)
from backend.services.studio.templates.registry import TemplateRegistryError, load_folder
from backend.services.studio.templates.spec import is_valid_template_slug

POSTER_MAX = 30 * 1024
VIDEO_MAX = 120 * 1024
SHARED_SDK = ROOT / 'templates-catalog' / '_shared' / 'ac-template-sdk.js'


def _scaffold_yaml(slug: str, name_zh: str, name_en: str, desc_zh: str, desc_en: str) -> str:
    return f"""id: {slug}
version: 2
name: {{zh: "{name_zh}", en: "{name_en}"}}
fit:
  formats: {{sit_down_interview: 0.9, keynote_stage: 0.8, podcast_studio: 0.7}}
  needs_face: true
canvas: {{aspects: [portrait], overlay_px: [1080, 1920], fps: 30}}
base:
  framing: full_face
  face_y: 0.38
  head_zone: [260, 860]
  zoom:
    mode: creep
    creep: 0.04
    intro: {{from: 1.06, dur: 0.8}}
  transitions: {{broll: cut, max: 1}}
  grade: "eq=contrast=1.04:saturation=1.02"
  scrim: {{enabled: true, height: 840, color: "0x0E1014", mid_stop: 0.4, mid_alpha: 0.32, bottom_alpha: 0.76}}
  progress_bar: {{enabled: true, height: 4, inset_x: 48, y_from_bottom: 72, color: "0x5A8BFF@0.9"}}
overlay:
  entry: index.html
  slots:
    hook: {{top: 180, alt_top: 180}}
    subtitle: {{top: 1500, max_rows: 2}}
  safe_area: xiaohongshu
  limits: {{emphasis_gap_s: 3.0}}
fields:
  required: [title_lines, cues]
  optional: [kicker, emphasis, speakers]
audio: {{bgm: none}}
cover: {{layout: {slug}_3x4, from_overlay: true}}
caption_layout:
  font_px: 48
  inset_px: 64
  source_limit: 34
  paging_mode: phrase
  bilingual_align: per_cue
  strip_speaker_prefix: false
  en_key_propagates: true
meta:
  desc: {{zh: "{desc_zh}", en: "{desc_en}"}}
  tags: [custom, portrait]
  category: general
  order: 100
  package_version: "1.0.0"
  preview_layout: blur
qa: {{}}
"""


_SCAFFOLD_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet" href="./style.css" />
</head>
<body>
  <main id="stage" class="stage">
    <header id="kicker" class="kicker" hidden></header>
    <section id="subtitle" class="subtitle" aria-live="off">
      <div id="zh" class="zh"></div>
      <div id="en" class="en"></div>
    </section>
  </main>
  <script src="./ac-template-sdk.js"></script>
  <script src="./template.js"></script>
</body>
</html>
"""

_SCAFFOLD_CSS = """* { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
  width: 1080px;
  height: 1920px;
  overflow: hidden;
  background: transparent;
  font-family: "Noto Sans CJK SC", "PingFang SC", sans-serif;
}
.stage {
  position: relative;
  width: 1080px;
  height: 1920px;
}
.kicker {
  position: absolute;
  top: 120px;
  left: 64px;
  padding: 8px 18px;
  border-radius: 999px;
  background: rgba(14, 16, 20, 0.72);
  color: #f4efe6;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.subtitle {
  position: absolute;
  top: 1500px;
  left: 64px;
  right: 64px;
  text-align: center;
}
.zh {
  color: #ffffff;
  font-size: 48px;
  font-weight: 700;
  line-height: 1.32;
  text-shadow: 0 3px 16px rgba(0, 0, 0, 0.75);
}
.zh .hl {
  color: #5a8bff;
}
.en {
  margin-top: 12px;
  color: rgba(244, 239, 230, 0.86);
  font-size: 28px;
  font-weight: 500;
  line-height: 1.3;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.7);
}
"""

_SCAFFOLD_JS = """(function () {
  var state = { moments: [], kicker: '' };
  var kickerEl = document.getElementById('kicker');
  var zhEl = document.getElementById('zh');
  var enEl = document.getElementById('en');

  window.setData = function (fill) {
    state = fill || { moments: [] };
    var kicker = (state.kicker || '').trim();
    kickerEl.textContent = kicker;
    kickerEl.hidden = !kicker;
  };

  window.renderFrame = function (seconds) {
    var active = ACTemplate.momentAt(state, seconds);
    var zhHtml = ACTemplate.zhHtml(state, active, { highlightClass: 'hl', maxLines: 2, joinWith: '' });
    var enText = ACTemplate.enText(state, active, { onlyTranslated: false });
    zhEl.innerHTML = zhHtml;
    enEl.textContent = enText;
    return zhHtml + '|' + enText + '|' + (state.kicker || '');
  };

  window.occupiedRects = function () {
    return ACTemplate.occupiedRects(['kicker', 'subtitle']);
  };
})();
"""


def cmd_scaffold(args: argparse.Namespace) -> int:
    slug = args.id.strip()
    if not is_valid_template_slug(slug):
        raise SystemExit(f'Invalid template slug: {slug}')
    target = Path(args.out).resolve() / slug
    if target.exists() and not args.force:
        raise SystemExit(f'Target already exists: {target} (use --force to overwrite)')
    target.mkdir(parents=True, exist_ok=True)
    desc_zh = args.desc_zh or f'{args.name_zh} 竖屏切片包装模板'
    desc_en = args.desc_en or f'{args.name_en} portrait clip packaging template'
    (target / 'template.yaml').write_text(_scaffold_yaml(slug, args.name_zh, args.name_en, desc_zh, desc_en), encoding='utf-8')
    (target / 'index.html').write_text(_SCAFFOLD_HTML, encoding='utf-8')
    (target / 'style.css').write_text(_SCAFFOLD_CSS, encoding='utf-8')
    (target / 'template.js').write_text(_SCAFFOLD_JS, encoding='utf-8')
    if SHARED_SDK.is_file():
        shutil.copy2(SHARED_SDK, target / 'ac-template-sdk.js')
    spec = load_folder(target)
    print(f'Scaffolded valid template "{spec.id}" at {target}')
    return 0


def verify_folder(folder: Path) -> tuple[object, dict]:
    """Run static schema, security/determinism, and size budget checks."""
    folder = folder.resolve()
    try:
        spec = load_folder(folder)
    except TemplateRegistryError as error:
        raise SystemExit(f'Verification failed: {error}') from None

    total_bytes = 0
    for path in folder.rglob('*'):
        if path.is_symlink():
            raise SystemExit(f'Verification failed: symlink not allowed: {path}')
        if path.is_file():
            total_bytes += path.stat().st_size
    if total_bytes > MAX_EXTRACTED_BYTES:
        raise SystemExit(f'Verification failed: folder exceeds {MAX_EXTRACTED_BYTES} bytes ({total_bytes})')

    preview_info: dict[str, Path] = {}
    for asset_name in PREVIEW_ASSET_NAMES:
        for candidate in (folder / 'preview' / asset_name, folder / asset_name):
            if candidate.is_file():
                limit = POSTER_MAX if asset_name.endswith('.webp') else VIDEO_MAX
                size = candidate.stat().st_size
                if size == 0 or size > limit:
                    raise SystemExit(f'Verification failed: {candidate.name} size {size} outside (0, {limit}]')
                preview_info[asset_name] = candidate
                break

    return spec, {'total_bytes': total_bytes, 'previews': preview_info}


def cmd_verify(args: argparse.Namespace) -> int:
    spec, info = verify_folder(Path(args.folder))
    print(f'PASS {spec.id} v{spec.effective_meta().package_version} ({info["total_bytes"]} bytes, previews={sorted(info["previews"])})')
    return 0


def _pack_zip(folder: Path, dest_zip: Path) -> tuple[str, int]:
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(
        p for p in folder.rglob('*')
        if p.is_file() and not any(part.startswith('.') or part == '__MACOSX' for part in p.relative_to(folder).parts)
    )
    with zipfile.ZipFile(dest_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            arcname = f'{folder.name}/{path.relative_to(folder).as_posix()}'
            zi = zipfile.ZipInfo(arcname, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(zi, path.read_bytes())
    raw = dest_zip.read_bytes()
    if len(raw) > MAX_ARCHIVE_BYTES:
        dest_zip.unlink(missing_ok=True)
        raise SystemExit(f'Packed archive exceeds {MAX_ARCHIVE_BYTES} bytes ({len(raw)})')
    return hashlib.sha256(raw).hexdigest(), len(raw)


def cmd_pack(args: argparse.Namespace) -> int:
    folder = Path(args.folder).resolve()
    spec, info = verify_folder(folder)
    meta = spec.effective_meta()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    zip_name = f'{spec.id}-{meta.package_version}.zip'
    zip_path = out_dir / zip_name
    sha256, size_bytes = _pack_zip(folder, zip_path)

    exported_previews: dict[str, str] = {}
    for asset_name, src_path in info['previews'].items():
        pub_name = f'{spec.id}-{meta.package_version}.{asset_name}'
        shutil.copy2(src_path, out_dir / pub_name)
        exported_previews[asset_name] = pub_name

    entry_payload = {
        'id': spec.id,
        'version': meta.package_version,
        'name': spec.name.model_dump(mode='json'),
        'desc': meta.desc.model_dump(mode='json') if meta.desc else None,
        'tags': meta.tags,
        'category': meta.category,
        'order': meta.order,
        'sha256': sha256,
        'archive_file': zip_name,
        'size_bytes': size_bytes,
        'min_app_version': meta.min_app_version,
        'author': meta.author,
        'preview_files': exported_previews,
    }
    entry_path = out_dir / f'{spec.id}-{meta.package_version}.entry.json'
    entry_path.write_text(json.dumps(entry_payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'PACKED {zip_name} ({size_bytes} bytes, sha256={sha256[:12]}...)')
    return 0


def cmd_build_catalog(args: argparse.Namespace) -> int:
    dist_dir = Path(args.dist_dir).resolve()
    base_url = args.base_url.rstrip('/')
    entries: list[CatalogEntry] = []
    for entry_file in sorted(dist_dir.glob('*.entry.json')):
        raw = json.loads(entry_file.read_text(encoding='utf-8'))
        previews = raw.get('preview_files') or {}
        entry = CatalogEntry(
            id=raw['id'],
            version=raw['version'],
            name=raw['name'],
            desc=raw.get('desc'),
            tags=raw.get('tags') or [],
            category=raw.get('category') or 'general',
            order=int(raw.get('order', 100)),
            sha256=raw['sha256'],
            download_url=f'{base_url}/{raw["archive_file"]}',
            size_bytes=int(raw.get('size_bytes', 0)),
            min_app_version=raw.get('min_app_version'),
            author=raw.get('author') or 'AutoClip',
            poster_url=f'{base_url}/{previews["poster.webp"]}' if 'poster.webp' in previews else None,
            preview_mp4_url=f'{base_url}/{previews["preview.mp4"]}' if 'preview.mp4' in previews else None,
            preview_webm_url=f'{base_url}/{previews["preview.webm"]}' if 'preview.webm' in previews else None,
        )
        entries.append(entry)

    manifest = CatalogManifest(
        schema_version=1,
        updated_at=datetime.now(timezone.utc).isoformat(),
        templates=sorted(entries, key=lambda e: (e.order, e.id)),
    )
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest.model_dump(mode='json'), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'WROTE {out_path} ({len(entries)} templates)')
    return 0


def build_ingest_payload(
    entry: dict,
    *,
    target_region: str = 'global',
    auto_publish: bool = False,
    badge: str | None = None,
) -> dict:
    """Build an AutoClip Admin ``POST /templates/ingest`` request body from a catalog entry."""
    name_raw = entry.get('name') or {}
    desc_raw = entry.get('desc') or {}
    payload: dict = {
        'id': entry['id'],
        'version': entry['version'],
        'name': {
            'en': name_raw.get('en') or entry['id'],
            'zh': name_raw.get('zh') or name_raw.get('en') or entry['id'],
        },
        'desc': {
            'en': desc_raw.get('en') or '',
            'zh': desc_raw.get('zh') or desc_raw.get('en') or '',
        },
        'category': entry.get('category') or 'general',
        'badge': badge if badge is not None else entry.get('badge'),
        'target_region': target_region,
        'tags': entry.get('tags') or [],
        'min_app_version': entry.get('min_app_version') or '1.6.1',
        'sha256': entry['sha256'],
        'size_bytes': int(entry.get('size_bytes') or 0),
        'download_url': entry['download_url'],
        'poster_url': entry.get('poster_url'),
        'preview_mp4_url': entry.get('preview_mp4_url'),
        'preview_webm_url': entry.get('preview_webm_url'),
        'auto_publish': bool(auto_publish),
    }
    return payload


def cmd_ingest(args: argparse.Namespace) -> int:
    catalog_path = Path(args.catalog).resolve()
    raw = json.loads(catalog_path.read_text(encoding='utf-8'))
    templates = raw.get('templates') if isinstance(raw, dict) else None
    if not isinstance(templates, list):
        raise SystemExit(f'Invalid catalog.json (missing templates list): {catalog_path}')

    only_ids = {s.strip() for s in (args.only or '').split(',') if s.strip()}
    selected = [entry for entry in templates if not only_ids or entry.get('id') in only_ids]
    if not selected:
        raise SystemExit('No matching templates to ingest')

    admin_url = (args.admin_url or os.getenv('AUTOCLIP_ADMIN_URL') or 'http://127.0.0.1:8765').rstrip('/')
    endpoint = f'{admin_url}/templates/ingest'
    token = (args.token or os.getenv('AUTOCLIP_ADMIN_BOT_TOKEN') or '').strip()
    if not args.dry_run and not token:
        raise SystemExit('Missing AUTOCLIP_ADMIN_BOT_TOKEN (pass --token or set env var)')

    for entry in selected:
        payload = build_ingest_payload(
            entry,
            target_region=args.target_region,
            auto_publish=args.auto_publish,
            badge=args.badge or None,
        )
        if args.dry_run:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            continue
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(
            endpoint,
            data=body,
            method='POST',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {token}',
                'User-Agent': 'AutoClip-TemplateFactory/1.0',
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_text = resp.read().decode('utf-8', errors='replace')[:200]
                print(f'INGESTED {payload["id"]} v{payload["version"]} -> HTTP {resp.status} ({resp_text})')
        except urllib.error.HTTPError as err:
            detail = err.read().decode('utf-8', errors='replace')[:300]
            raise SystemExit(f'Ingest failed for {payload["id"]}: HTTP {err.code} {detail}') from None
        except urllib.error.URLError as err:
            raise SystemExit(f'Ingest connection failed ({endpoint}): {err.reason}') from None
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='AutoClip automated template factory')
    sub = parser.add_subparsers(dest='command', required=True)

    s = sub.add_parser('scaffold', help='Create a starter compliant template directory')
    s.add_argument('id', help='Template slug (e.g. xhs_tech_card)')
    s.add_argument('--name-zh', required=True)
    s.add_argument('--name-en', required=True)
    s.add_argument('--desc-zh', default='')
    s.add_argument('--desc-en', default='')
    s.add_argument('--out', default=str(ROOT / 'backend' / 'assets' / 'templates'))
    s.add_argument('--force', action='store_true')
    s.set_defaults(func=cmd_scaffold)

    v = sub.add_parser('verify', help='Validate schema, security contract, and preview budgets')
    v.add_argument('folder', help='Template directory path')
    v.set_defaults(func=cmd_verify)

    p = sub.add_parser('pack', help='Verify and package one template into a versioned zip + entry JSON')
    p.add_argument('folder', help='Template directory path')
    p.add_argument('--out', required=True, help='Output directory for zip and entry JSON')
    p.set_defaults(func=cmd_pack)

    c = sub.add_parser('build-catalog', help='Aggregate *.entry.json into a GitHub Releases catalog.json')
    c.add_argument('dist_dir', help='Directory containing packed *.entry.json files')
    c.add_argument('--base-url', required=True, help='Release download base URL')
    c.add_argument('--out', required=True, help='Output catalog.json path')
    c.set_defaults(func=cmd_build_catalog)

    ig = sub.add_parser('ingest', help='Push built catalog.json entries into AutoClip Admin (/templates/ingest)')
    ig.add_argument('catalog', help='Path to built catalog.json')
    ig.add_argument('--admin-url', default='', help='Admin base URL (default: AUTOCLIP_ADMIN_URL or http://127.0.0.1:8765)')
    ig.add_argument('--token', default='', help='Admin bot bearer token (default: AUTOCLIP_ADMIN_BOT_TOKEN)')
    ig.add_argument('--target-region', choices=['global', 'zh', 'overseas'], default='global')
    ig.add_argument('--badge', default='', help='Optional badge override (e.g. new, hot, beta)')
    ig.add_argument('--auto-publish', action='store_true', help='Publish immediately instead of creating a draft')
    ig.add_argument('--only', default='', help='Comma-separated template IDs to ingest (default: all)')
    ig.add_argument('--dry-run', action='store_true', help='Print ingest JSON payloads without sending HTTP requests')
    ig.set_defaults(func=cmd_ingest)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == '__main__':
    raise SystemExit(main())
