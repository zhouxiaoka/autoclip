"""In-app AI Style Cloner: turn any reference short video or prompt into a reusable local template.

Pipeline:
  1. Ingest reference (local video path, URL via yt-dlp capped <=60s/50MB, or text-only prompt)
  2. Extract up to 6 evenly-spaced JPEG keyframes via FFmpeg
  3. Infer structured ``StyleBlueprint`` JSON via configured Vision LLM (or text LLM fallback)
  4. Synthesize deterministic, offline-safe template bundle using ``ac-motion-kit`` + declarative ``variables``
  5. Validate via ``registry.load_folder`` and render a 3s preview on bundled ``example/source.mp4``
  6. Support instant variable overrides (0-token), 1-line natural-language refinement, undo, atomic save & zip export
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re
import shutil
import subprocess
import threading
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any, Callable, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from backend.core.failure_codes import UserFacingError
from backend.core.path_utils import get_data_directory, get_project_root
from backend.services.studio.templates import registry
from backend.services.studio.templates.spec import is_valid_template_slug

logger = logging.getLogger(__name__)

_HEX_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
_SLUG_CLEAN_RE = re.compile(r'[^a-z0-9_]+')


class StyleBlueprint(BaseModel):
    """Structured visual & motion DNA extracted from a reference clip or prompt."""
    model_config = ConfigDict(extra='ignore')
    name_zh: str = Field(default='灵感风格', min_length=1, max_length=24)
    name_en: str = Field(default='Custom Vibe', min_length=1, max_length=28)
    desc_zh: str = Field(default='从参考视频克隆的自定义模板', max_length=120)
    desc_en: str = Field(default='Custom style cloned from reference video', max_length=120)
    accent_color: str = '#FFE548'
    text_color: str = '#FFFFFF'
    caption_motion: Literal['karaoke_pill', 'spring_pop', 'blur_in', 'kinetic_slam', 'serif_focus'] = 'karaoke_pill'
    header_style: Literal['none', 'pill_hook', 'issue_line', 'kpi_pill'] = 'pill_hook'
    font_style: Literal['sans', 'serif', 'condensed'] = 'sans'
    font_scale: Literal['S', 'M', 'L'] = 'M'
    depth_enabled: bool = False
    grain_enabled: bool = False
    vignette_strength: float = Field(default=0.45, ge=0.0, le=0.85)
    category: Literal['general', 'knowledge', 'interview', 'gaming'] = 'general'

    def normalized(self) -> 'StyleBlueprint':
        acc = self.accent_color.strip() if isinstance(self.accent_color, str) else '#FFE548'
        if not _HEX_RE.match(acc):
            acc = '#FFE548'
        txt = self.text_color.strip() if isinstance(self.text_color, str) else '#FFFFFF'
        if not _HEX_RE.match(txt):
            txt = '#FFFFFF'
        return self.model_copy(update={'accent_color': acc.upper(), 'text_color': txt.upper()})


def clone_jobs_root() -> Path:
    root = get_data_directory() / 'tmp' / 'template_clone'
    root.mkdir(parents=True, exist_ok=True)
    return root


def _shared_sdk_path() -> Path:
    root = get_project_root()
    candidates = [
        root / 'templates-catalog' / '_shared' / 'ac-template-sdk.js',
        root / 'backend' / 'assets' / 'templates' / '_shared' / 'ac-template-sdk.js',
    ]
    for p in candidates:
        if p.is_file():
            return p
    # Fallback: copy from any installed/shipping template that bundles ac-template-sdk.js
    for p in (root / 'templates-catalog').glob('*/ac-template-sdk.js'):
        return p
    raise UserFacingError('缺少内置模板 SDK（ac-template-sdk.js）')


def _example_source_video() -> Path:
    p = get_project_root() / 'backend' / 'assets' / 'example' / 'source.mp4'
    if not p.is_file():
        raise UserFacingError('缺少内置示例试看视频')
    return p


def _ffmpeg_bin() -> str:
    found = shutil.which('ffmpeg')
    if not found:
        raise UserFacingError('未找到 ffmpeg，无法抽取参考画面')
    return found


def extract_reference_frames(video_path: Path, out_dir: Path, *, count: int = 6) -> list[Path]:
    """Extract up to ``count`` evenly-spaced JPEG keyframes from the first 15s of a video."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ff = _ffmpeg_bin()
    # Probe duration (best-effort)
    dur = 10.0
    ffprobe = shutil.which('ffprobe')
    if ffprobe:
        try:
            raw = subprocess.check_output(
                [ffprobe, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)],
                text=True, timeout=10,
            ).strip()
            val = float(raw)
            if val > 0.4:
                dur = min(val, 15.0)
        except Exception:
            pass
    frames: list[Path] = []
    step = dur / max(1, count + 1)
    for i in range(count):
        ts = max(0.1, round((i + 1) * step, 2))
        dest = out_dir / f'frame_{i + 1:02d}.jpg'
        proc = subprocess.run(
            [ff, '-y', '-hide_banner', '-loglevel', 'error', '-ss', str(ts), '-i', str(video_path),
             '-vframes', '1', '-vf', 'scale=360:-2', '-q:v', '4', str(dest)],
            capture_output=True, text=True, timeout=20,
        )
        if proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 0:
            frames.append(dest)
    return frames


def download_reference_url(url: str, out_dir: Path) -> Path:
    """Download a short reference clip (<=60s, <=50MB) via yt-dlp."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ytdlp = shutil.which('yt-dlp')
    if not ytdlp:
        raise UserFacingError('当前环境缺少 yt-dlp，请直接拖入本地 MP4 视频')
    target = out_dir / 'reference.mp4'
    cmd = [
        ytdlp, '--no-playlist', '--max-filesize', '50M',
        '--download-sections', '*0:00-0:20',
        '-f', 'bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/b[ext=mp4]/b',
        '--merge-output-format', 'mp4',
        '-o', str(target), url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if proc.returncode != 0 or not target.is_file():
        raise UserFacingError('参考视频链接下载失败，建议先保存到本地后直接拖入 MP4')
    return target


def vision_readiness() -> dict[str, Any]:
    """Check whether the user's configured model supports image/frame understanding."""
    try:
        from backend.services.studio import vision_settings
        eff = vision_settings.effective()
        pub = vision_settings.public(eff)
        model = (eff.get('model') or '').strip()
        ready = bool(pub.get('available') or (eff.get('base_url') and model))
        return {'vision_capable': ready, 'model': model}
    except Exception:
        return {'vision_capable': False, 'model': ''}


_BLUEPRINT_PROMPT = """You are an elite short-form video art director for AutoClip.
Analyze the reference frames (or user description) and return ONLY a compact JSON object matching this exact schema:
{
  "name_zh": "2-5 Chinese chars evocative style name (e.g. 霓虹穿影, 猩红急停)",
  "name_en": "1-2 word iconic English name (e.g. Neon Depth, Crimson Drop)",
  "desc_zh": "1 concise Chinese sentence describing the look",
  "desc_en": "1 concise English sentence describing the look",
  "accent_color": "#RRGGBB primary highlight hex",
  "text_color": "#FFFFFF or #RRGGBB caption text hex",
  "caption_motion": "karaoke_pill | spring_pop | blur_in | kinetic_slam | serif_focus",
  "header_style": "none | pill_hook | issue_line | kpi_pill",
  "font_style": "sans | serif | condensed",
  "font_scale": "S | M | L",
  "depth_enabled": true or false (true if giant typography passes behind the speaker's head/shoulders),
  "grain_enabled": true or false,
  "vignette_strength": 0.0 to 0.75,
  "category": "general | knowledge | interview | gaming"
}
Return valid JSON only, no markdown fences."""


def infer_blueprint(
    *,
    frames: list[Path],
    prompt_hint: str = '',
    depth_mode: Literal['auto', 'on', 'off'] = 'auto',
    vision_caller: Callable[..., dict] | None = None,
) -> StyleBlueprint:
    """Call Vision LLM (or text fallback) to extract a structured StyleBlueprint."""
    caller = vision_caller
    if caller is None:
        from backend.services.studio.intelligence import vision_call
        caller = vision_call

    content: list[dict[str, Any]] = [{'type': 'text', 'text': _BLUEPRINT_PROMPT}]
    if prompt_hint.strip():
        content.append({'type': 'text', 'text': f'User preference: {prompt_hint.strip()}'})
    if depth_mode == 'on':
        content.append({'type': 'text', 'text': 'Set depth_enabled=true (3D text behind speaker).'})
    elif depth_mode == 'off':
        content.append({'type': 'text', 'text': 'Set depth_enabled=false.'})
    for fp in frames[:6]:
        b64 = base64.b64encode(fp.read_bytes()).decode('ascii')
        content.append({'type': 'image_url', 'image_url': {'url': f'data:image/jpeg;base64,{b64}'}})

    raw: dict[str, Any] = {}
    try:
        res = caller(content)
        if isinstance(res, dict):
            raw = res
    except Exception as exc:
        logger.warning('Style cloner vision_call failed, falling back to heuristic blueprint: %s', exc)
        if not frames and not prompt_hint.strip():
            raise UserFacingError('模型调用失败，请检查 AI 模型配置后重试') from exc

    bp = StyleBlueprint.model_validate(raw or {}).normalized()
    if depth_mode == 'on':
        bp = bp.model_copy(update={'depth_enabled': True})
    elif depth_mode == 'off':
        bp = bp.model_copy(update={'depth_enabled': False})
    return bp


def refine_blueprint_with_instruction(
    current: StyleBlueprint,
    instruction: str,
    *,
    vision_caller: Callable[..., dict] | None = None,
) -> StyleBlueprint:
    """Apply a 1-line natural-language refinement to an existing StyleBlueprint."""
    text = (instruction or '').strip()
    if not text:
        return current
    caller = vision_caller
    if caller is None:
        from backend.services.studio.intelligence import vision_call
        caller = vision_call

    prompt = (
        f'{_BLUEPRINT_PROMPT}\n\n'
        f'Current blueprint JSON:\n{current.model_dump_json()}\n\n'
        f'User refinement request: {text}\n'
        'Return the updated full JSON object only.'
    )
    try:
        res = caller([{'type': 'text', 'text': prompt}])
        if isinstance(res, dict) and res:
            merged = {**current.model_dump(), **res}
            return StyleBlueprint.model_validate(merged).normalized()
    except Exception as exc:
        logger.warning('Style refinement LLM failed, applying local heuristic fallback: %s', exc)

    # Lightweight deterministic fallback for common tweaks if LLM is offline
    low = text.lower()
    upd: dict[str, Any] = {}
    hex_m = re.search(r'#[0-9a-fA-F]{6}', text)
    if hex_m:
        upd['accent_color'] = hex_m.group(0).upper()
    elif any(k in low for k in ('蓝', 'blue')):
        upd['accent_color'] = '#2D6BFF'
    elif any(k in low for k in ('绿', '薄荷', 'green', 'mint')):
        upd['accent_color'] = '#34D399'
    elif any(k in low for k in ('红', 'red', 'crimson')):
        upd['accent_color'] = '#FF4D4F'
    elif any(k in low for k in ('黄', 'yellow', 'gold')):
        upd['accent_color'] = '#FFE548'
    if any(k in low for k in ('大一', '放大', 'bigger', 'larger')):
        upd['font_scale'] = 'L'
    elif any(k in low for k in ('小一', '缩小', 'smaller')):
        upd['font_scale'] = 'S'
    if any(k in low for k in ('景深', '穿背', 'depth', '3d')):
        upd['depth_enabled'] = not any(k in low for k in ('关', '取消', '不要', 'disable', 'off'))
    if any(k in low for k in ('颗粒', 'grain')):
        upd['grain_enabled'] = not any(k in low for k in ('关', '取消', '不要', 'disable', 'off'))
    return current.model_copy(update=upd).normalized()


def make_unique_slug(name_en: str, *, user_root: Path | None = None) -> str:
    base = _SLUG_CLEAN_RE.sub('_', (name_en or 'custom_style').strip().lower()).strip('_')
    if not base or not base[0].isalpha():
        base = 'style_' + (base or 'custom')
    base = base[:24]
    existing = {item.spec.id for item in registry.list_loaded(user_root=user_root)}
    cand = base
    idx = 2
    while cand in existing or not is_valid_template_slug(cand):
        cand = f'{base[:20]}_{idx}'
        idx += 1
    return cand


def synthesize_template_dir(template_id: str, bp: StyleBlueprint, dest_dir: Path) -> Path:
    """Deterministically generate a security-compliant, ACMotion-powered template directory."""
    bp = bp.normalized()
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_shared_sdk_path(), dest_dir / 'ac-template-sdk.js')

    scale_map = {'S': 0.88, 'M': 1.0, 'L': 1.15}
    spec_dict: dict[str, Any] = {
        'id': template_id,
        'version': 2,
        'name': {'zh': bp.name_zh, 'en': bp.name_en},
        'fit': {'formats': {'vlog': 1.0, 'sit_down_interview': 0.95, 'podcast_studio': 0.9}, 'needs_face': True},
        'canvas': {'aspects': ['portrait'], 'overlay_px': [1080, 1920], 'fps': 30},
        'base': {
            'framing': 'full_face',
            'face_y': 0.38,
            'head_zone': [240, 1140],
            'zoom': {'mode': 'creep', 'creep': 0.02},
            'transitions': {'broll': 'none', 'max': 0},
            'grade': 'eq=contrast=1.05',
            'picture_layout': 'crop',
            'subject_layer': bp.depth_enabled,
        },
        'overlay': {
            'entry': 'index.html',
            **({'back_entry': 'back.html'} if bp.depth_enabled else {}),
            'slots': {'hook': {'top': 180, 'alt_top': 180}, 'subtitle': {'top': 1440, 'max_rows': 2}},
            'safe_area': 'tiktok',
            'limits': {'emphasis_gap_s': 2.0},
        },
        'fields': {'required': ['title_lines', 'cues'], 'optional': ['kicker', 'emphasis', 'speakers']},
        'audio': {'bgm': 'none'},
        'cover': {'layout': 'street_9x16', 'from_overlay': True},
        'caption_layout': {
            'font_px': 48,
            'inset_px': 84,
            'source_limit': 36,
            'paging_mode': 'phrase',
            'bilingual_align': 'per_cue',
            'strip_speaker_prefix': True,
            'en_key_propagates': False,
            'burn_cover_title': True,
            'keep_punctuation': True,
        },
        'meta': {
            'desc': {'zh': bp.desc_zh, 'en': bp.desc_en},
            'tags': ['custom', 'cloned', *(['depth', '3d'] if bp.depth_enabled else [])],
            'category': bp.category,
            'order': 10,
            'package_version': '1.0.0',
            **({'min_app_version': '1.6.3'} if bp.depth_enabled else {}),
            'author': 'My Clone',
            'preview_layout': 'crop',
        },
        'variables': [
            {'key': 'accent_color', 'kind': 'color', 'label': {'zh': '强调色', 'en': 'Accent'}, 'default': bp.accent_color},
            {'key': 'font_scale', 'kind': 'select', 'label': {'zh': '字号', 'en': 'Size'}, 'default': bp.font_scale, 'options': ['S', 'M', 'L']},
            {'key': 'depth_enabled', 'kind': 'boolean', 'label': {'zh': '3D 景深', 'en': '3D Depth'}, 'default': bp.depth_enabled},
            {'key': 'grain_enabled', 'kind': 'boolean', 'label': {'zh': '胶片颗粒', 'en': 'Film Grain'}, 'default': bp.grain_enabled},
        ],
        'qa': {},
    }
    (dest_dir / 'template.yaml').write_text(
        yaml.safe_dump(spec_dict, allow_unicode=True, sort_keys=False),
        encoding='utf-8',
    )

    font_css = {
        'sans': "'PingFang SC', 'Noto Sans SC', 'Helvetica Neue', Arial, sans-serif",
        'serif': "'Songti SC', 'Noto Serif CJK SC', Georgia, serif",
        'condensed': "'Impact', 'PingFang SC', 'Noto Sans SC', sans-serif",
    }[bp.font_style]

    (dest_dir / 'style.css').write_text(
        '* { box-sizing: border-box; margin: 0; padding: 0; }\n'
        'html, body { width: 1080px; height: 1920px; overflow: hidden; background: transparent; }\n'
        '#stage { width: 1080px; height: 1920px; position: relative; }\n',
        encoding='utf-8',
    )
    (dest_dir / 'index.html').write_text(
        '<!doctype html><html lang="zh"><head><meta charset="utf-8"><link rel="stylesheet" href="./style.css"></head>\n'
        '<body><div id="stage"></div><script src="./ac-template-sdk.js"></script><script src="./template.js"></script></body></html>\n',
        encoding='utf-8',
    )

    cfg_json = json.dumps({
        'fontFamily': font_css,
        'textColor': bp.text_color,
        'accentColor': bp.accent_color,
        'captionMotion': bp.caption_motion,
        'headerStyle': bp.header_style,
        'vignette': bp.vignette_strength,
        'scaleMap': scale_map,
    }, ensure_ascii=False)

    template_js = f'''(function () {{
  'use strict';
  var CFG = {cfg_json};
  var state = {{}};
  var root = document.getElementById('stage');
  var mctx = document.createElement('canvas').getContext('2d');
  var esc = window.ACTemplate.esc;
  var M = window.ACMotion;

  function measureW(text, sz, weight) {{
    mctx.font = (weight || 800) + ' ' + sz + 'px ' + CFG.fontFamily;
    return Math.max(1, mctx.measureText(text).width);
  }}

  window.setData = function (fill) {{ state = fill || {{}}; }};

  window.renderFrame = function (tSeconds) {{
    var t = Number(tSeconds) || 0;
    var lang = state.audience_language || 'zh';
    var accent = M.getVar(state, 'accent_color', CFG.accentColor);
    var scaleKey = M.getVar(state, 'font_scale', 'M');
    var fScale = CFG.scaleMap[scaleKey] || 1.0;
    var grainOn = M.getVar(state, 'grain_enabled', false);

    var parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">'];
    if (CFG.vignette > 0.02) parts.push(M.renderVignette(CFG.vignette));
    if (grainOn) parts.push(M.renderGrain(0.06));

    // Optional top header in face-safe zone (y=150..240)
    var lines = (state.title_lines || []).filter(Boolean);
    var topText = (state.kicker || lines[0] || '').trim();
    if (topText && CFG.headerStyle !== 'none') {{
      var hp = M.easeOutCubic(t / 0.25);
      if (CFG.headerStyle === 'pill_hook') {{
        var pw = Math.min(820, measureW(topText, 30, 800) + 48);
        parts.push('<g opacity="' + hp.toFixed(3) + '">');
        parts.push('<rect x="' + ((1080 - pw) / 2).toFixed(1) + '" y="146" width="' + pw.toFixed(1) + '" height="50" rx="25" fill="' + accent + '"/>');
        parts.push('<text x="540" y="180" text-anchor="middle" font-family="' + CFG.fontFamily + '" font-size="28" font-weight="800" fill="#14151A">' + esc(topText.slice(0, 22)) + '</text>');
        parts.push('</g>');
      }} else if (CFG.headerStyle === 'issue_line') {{
        parts.push('<g opacity="' + hp.toFixed(3) + '">');
        parts.push('<line x1="84" y1="176" x2="996" y2="176" stroke="#FFFFFF" stroke-opacity="0.45" stroke-width="2"/>');
        parts.push('<text x="540" y="162" text-anchor="middle" font-family="' + CFG.fontFamily + '" font-size="24" letter-spacing="4" fill="#FFFFFF">' + esc(topText.slice(0, 26).toUpperCase()) + '</text>');
        parts.push('</g>');
      }} else if (CFG.headerStyle === 'kpi_pill') {{
        parts.push('<g opacity="' + hp.toFixed(3) + '">');
        parts.push('<rect x="190" y="142" width="700" height="68" rx="18" fill="#14151A" fill-opacity="0.78" stroke="#FFFFFF" stroke-opacity="0.18" stroke-width="2"/>');
        parts.push('<text x="540" y="186" text-anchor="middle" font-family="' + CFG.fontFamily + '" font-size="32" font-weight="800" fill="' + accent + '">' + esc(topText.slice(0, 24)) + '</text>');
        parts.push('</g>');
      }}
    }}

    // Lower face-safe kinetic caption (y=1470)
    var moment = window.ACTemplate.momentAt(state, t);
    var chunks = M.chunkCaption(moment, lang, 4);
    var capDigest = 'IDLE';
    if (chunks.length) {{
      var mStart = (moment.t0 != null ? moment.t0 : moment.start) || 0;
      var mEnd = (moment.t1 != null ? moment.t1 : moment.end) || (mStart + 2.0);
      var age = Math.max(0, t - mStart);
      var prog = M.clamp01(age / Math.max(0.2, mEnd - mStart));
      var activeIdx = M.staggerIndex(chunks.length, prog);
      var sep = lang === 'en' ? ' ' : '';
      var full = chunks.join(sep);
      capDigest = full + '_' + activeIdx + '_' + accent + '_' + scaleKey;

      var baseFz = Math.round((full.length > 22 ? 42 : 50) * fScale);
      var sc = CFG.captionMotion === 'spring_pop' ? (0.86 + 0.14 * M.springPop(age, 0.24))
             : CFG.captionMotion === 'kinetic_slam' ? M.kineticSlam(age, 0.2).scale : 1.0;
      var op = CFG.captionMotion === 'blur_in' ? M.blurIn(age, 0.24).opacity : M.clamp01(age / 0.12);
      var totalW = measureW(full, baseFz, 800);
      var xCur = Math.max(64, (1080 - totalW) / 2);

      parts.push('<g opacity="' + op.toFixed(3) + '" transform="translate(540,1470) scale(' + sc.toFixed(3) + ') translate(-540,-1470)">');
      for (var i = 0; i < chunks.length; i++) {{
        var tok = chunks[i];
        var ww = measureW(tok, baseFz, 800);
        var isAct = i === activeIdx;
        if (isAct && CFG.captionMotion === 'karaoke_pill') {{
          parts.push('<rect x="' + (xCur - 5).toFixed(1) + '" y="' + (1470 - baseFz + 4).toFixed(1) + '" width="' + (ww + 10).toFixed(1) + '" height="' + (baseFz + 14).toFixed(1) + '" rx="10" fill="' + accent + '"/>');
          parts.push('<text x="' + xCur.toFixed(1) + '" y="1476" font-family="' + CFG.fontFamily + '" font-size="' + baseFz + '" font-weight="800" fill="#14151A">' + esc(tok) + '</text>');
        }} else {{
          var fillCol = isAct ? accent : CFG.textColor;
          parts.push('<text x="' + xCur.toFixed(1) + '" y="1476" font-family="' + CFG.fontFamily + '" font-size="' + baseFz + '" font-weight="800" fill="' + fillCol + '" stroke="#0B0C10" stroke-width="10" paint-order="stroke" stroke-linejoin="round">' + esc(tok) + '</text>');
        }}
        xCur += ww + (sep ? measureW(sep, baseFz, 800) : 6);
      }}
      parts.push('</g>');
    }}

    parts.push('</svg>');
    root.innerHTML = parts.join('');
    return 'CLONE_' + capDigest;
  }};

  window.occupiedRects = function () {{ return []; }};
}})();
'''
    (dest_dir / 'template.js').write_text(template_js, encoding='utf-8')

    if bp.depth_enabled:
        (dest_dir / 'back.html').write_text(
            '<!doctype html><html lang="zh"><head><meta charset="utf-8"><link rel="stylesheet" href="./style.css"></head>\n'
            '<body><div id="stage"></div><script src="./ac-template-sdk.js"></script><script src="./back.js"></script></body></html>\n',
            encoding='utf-8',
        )
        back_js = f'''(function () {{
  'use strict';
  var CFG = {cfg_json};
  var state = {{}};
  var root = document.getElementById('stage');
  var esc = window.ACTemplate.esc;
  var M = window.ACMotion;

  window.setData = function (fill) {{ state = fill || {{}}; }};
  window.renderFrame = function (tSeconds) {{
    var t = Number(tSeconds) || 0;
    if (!M.getVar(state, 'depth_enabled', true)) {{
      root.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920"></svg>';
      return 'BACK_OFF';
    }}
    var accent = M.getVar(state, 'accent_color', CFG.accentColor);
    var moment = window.ACTemplate.momentAt(state, t);
    var lang = state.audience_language || 'zh';
    var chunks = M.chunkCaption(moment, lang, 4);
    var word = (chunks[0] || (state.title_lines && state.title_lines[0]) || 'FOCUS').replace(/[，。！？.,!?]/g, '').slice(0, 9).toUpperCase();
    var mStart = (moment && (moment.t0 != null ? moment.t0 : moment.start)) || 0;
    var p = M.easeOutQuint(Math.max(0, t - mStart) / 0.36);
    var y = 515 + (1 - p) * 28;
    var fz = word.length <= 4 ? 196 : (word.length <= 7 ? 156 : 124);
    root.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1920" viewBox="0 0 1080 1920">' +
      '<g opacity="' + (0.25 + 0.72 * p).toFixed(3) + '">' +
      '<text x="540" y="' + y.toFixed(1) + '" text-anchor="middle" font-family="' + CFG.fontFamily + '" font-size="' + fz + '" font-weight="900" fill="' + accent + '" fill-opacity="0.92">' + esc(word) + '</text>' +
      '</g></svg>';
    return 'BACK_' + word + '_' + accent + '_' + Math.round(p * 10);
  }};
  window.occupiedRects = function () {{ return []; }};
}})();
'''
        (dest_dir / 'back.js').write_text(back_js, encoding='utf-8')

    return dest_dir


def _probe_duration(video_path: Path) -> float:
    ffprobe = shutil.which('ffprobe') or 'ffprobe'
    try:
        out = subprocess.check_output(
            [ffprobe, '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)],
            text=True, timeout=10,
        ).strip()
        val = float(out)
        return val if val > 0 else 10.0
    except Exception:
        return 10.0


def render_clone_preview(
    template_dir: Path,
    template_id: str,
    *,
    lang: Literal['zh', 'en'] = 'zh',
    source_video: Path | None = None,
    user_root: Path | None = None,
) -> dict[str, Path]:
    """Validate synthesized template via load_folder and render 3s real-case preview assets."""
    template_dir = template_dir.resolve()
    registry.load_folder(template_dir)

    # Temporarily stage under isolated preview user_root so render_draft resolves it cleanly
    stage_root = template_dir.parent / '_preview_stage'
    tpl_root = stage_root / 'templates'
    tpl_dst = tpl_root / template_id
    if tpl_dst.exists():
        shutil.rmtree(tpl_dst)
    shutil.copytree(template_dir, tpl_dst)

    from backend.services.studio.models import Draft, Packaging, PackagingCue, Scene
    from backend.services.studio.render import render_draft
    from backend.services.studio.store import directory

    use_custom = bool(source_video and source_video.is_file())
    vid_src = source_video if use_custom else _example_source_video()
    assert vid_src is not None
    if use_custom:
        dur = _probe_duration(vid_src)
        s0 = 0.0 if dur <= 3.5 else min(2.0, max(0.0, dur - 3.0))
        s1 = min(dur, s0 + 3.0) if dur > 0.5 else 3.0
    else:
        s0, s1 = 40.0, 43.0
    mid = round(s0 + (s1 - s0) * 0.48, 2)

    orig_root_fn = registry.user_templates_root
    registry.user_templates_root = lambda: tpl_root  # type: ignore[assignment]
    try:
        proj = f'clone_prev_{template_id}_{lang}'
        pdir = directory(proj)
        pdir.mkdir(parents=True, exist_ok=True)
        cues = (
            [
                PackagingCue(start=round(s0 + 0.1, 2), end=mid, text='走过低谷之后，'),
                PackagingCue(start=mid, end=round(s1, 2), text='回升才更有意思。'),
            ]
            if lang == 'zh'
            else [
                PackagingCue(start=round(s0 + 0.1, 2), end=mid, text='After every tough downswing,'),
                PackagingCue(start=mid, end=round(s1, 2), text='the upswing feels effortless.'),
            ]
        )
        draft = Draft(
            id=f'{template_id}_{lang}',
            title='好产品让复杂消失' if lang == 'zh' else 'Effortless Craft',
            scenes=[Scene(id='s1', start=round(s0, 2), end=round(s1, 2))],
            aspect='portrait',
            original_audio=False,
            layout='crop',
            crop_x=0.34,
            packaging=Packaging(version=2, template='editorial', audience_language=lang, source_language='en', cues=cues),
        )
        res = render_draft(
            proj, vid_src, draft, f'{template_id}_{lang}', lambda _: None,
            html_template=template_id, features={'pkg_templates_v1': True},
        )
        if res.get('template') != template_id:
            raise UserFacingError(f'试渲染未命中目标模板（{res.get("template_render")}）')
        rendered = pdir / 'output' / 'studio' / f'{template_id}_{lang}.mp4'
    finally:
        registry.user_templates_root = orig_root_fn

    prev_dir = template_dir / 'preview'
    prev_dir.mkdir(parents=True, exist_ok=True)
    ff = _ffmpeg_bin()
    suffix = '' if lang == 'zh' else '_en'
    mp4 = prev_dir / f'preview{suffix}.mp4'
    webm = prev_dir / f'preview{suffix}.webm'
    poster = prev_dir / f'poster{suffix}.webp'
    vf = 'scale=270:480:force_original_aspect_ratio=increase,crop=270:480,fps=24,format=yuv420p'
    subprocess.run([ff, '-y', '-hide_banner', '-loglevel', 'error', '-i', str(rendered), '-an', '-vf', vf,
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '28', '-movflags', '+faststart', str(mp4)], check=True)
    subprocess.run([ff, '-y', '-hide_banner', '-loglevel', 'error', '-i', str(rendered), '-an', '-vf', vf,
                    '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '40', '-deadline', 'realtime', '-cpu-used', '6', str(webm)], check=True)
    subprocess.run([ff, '-y', '-hide_banner', '-loglevel', 'error', '-ss', '1.8', '-i', str(rendered), '-vframes', '1',
                    '-vf', 'scale=270:480', '-c:v', 'libwebp', '-quality', '80', str(poster)], check=True)
    return {'mp4': mp4, 'webm': webm, 'poster': poster}


def export_template_zip(template_id: str, *, user_root: Path | None = None) -> tuple[str, bytes]:
    """Package an installed template directory as a shareable standard .zip archive."""
    loaded = registry.get_loaded(template_id, user_root=user_root)
    if loaded is None:
        raise UserFacingError(f'未找到模板: {template_id}')
    ver = loaded.spec.effective_meta().package_version
    buf = io.BytesIO()
    seen: set[str] = set()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(loaded.root.rglob('*')):
            if not f.is_file():
                continue
            rel = f.relative_to(loaded.root)
            if any(part.startswith('.') or part == '__pycache__' for part in rel.parts):
                continue
            # Skip secondary preview_en files when exporting canonical pack
            if rel.name.endswith('_en.mp4') or rel.name.endswith('_en.webm') or rel.name.endswith('_en.webp'):
                continue
            arc = f'{template_id}/{rel.as_posix()}'
            if arc not in seen:
                zf.write(f, arcname=arc)
                seen.add(arc)
    return f'{template_id}-{ver}.zip', buf.getvalue()


# ---------------------------------------------------------------------------
# In-memory async clone job registry (backed by <data_dir>/tmp/template_clone)
# ---------------------------------------------------------------------------

_jobs_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}


def _job_dir(job_id: str) -> Path:
    return clone_jobs_root() / job_id


def start_clone_job(
    *,
    reference_url: str = '',
    reference_file: Path | None = None,
    preview_file: Path | None = None,
    prompt_hint: str = '',
    depth_mode: Literal['auto', 'on', 'off'] = 'auto',
    render_preview: bool = True,
    vision_caller: Callable[..., dict] | None = None,
    sync_run: bool = False,
) -> dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    jdir = _job_dir(job_id)
    jdir.mkdir(parents=True, exist_ok=True)
    state: dict[str, Any] = {
        'job_id': job_id,
        'status': 'running',
        'step': 'extract',
        'error': None,
        'frames': [],
        'blueprint': None,
        'revisions': [],
        'revision': 0,
        'template_id': None,
        'preview_source': str(preview_file) if (preview_file and preview_file.is_file()) else None,
        'preview_zh_url': None,
        'preview_en_url': None,
        'poster_url': None,
        'created_at': time.time(),
    }
    with _jobs_lock:
        _jobs[job_id] = state

    def _run():
        try:
            frames: list[Path] = []
            vid_path = reference_file
            if not vid_path and reference_url.strip():
                vid_path = download_reference_url(reference_url.strip(), jdir / 'ref')
            if vid_path and vid_path.is_file():
                frames = extract_reference_frames(vid_path, jdir / 'frames', count=6)
                with _jobs_lock:
                    state['frames'] = [f'/api/v1/studio/templates/clone/{job_id}/assets/frames/{p.name}' for p in frames]

            with _jobs_lock:
                state['step'] = 'analyze'
            bp = infer_blueprint(frames=frames, prompt_hint=prompt_hint, depth_mode=depth_mode, vision_caller=vision_caller)
            tid = make_unique_slug(bp.name_en)

            with _jobs_lock:
                state['step'] = 'render'
                state['template_id'] = tid
                state['blueprint'] = bp.model_dump(mode='json')
                state['revisions'] = [bp.model_dump(mode='json')]
                state['revision'] = 1

            tpl_dir = synthesize_template_dir(tid, bp, jdir / 'tpl' / tid)
            registry.load_folder(tpl_dir)
            if render_preview:
                src_vid = Path(state['preview_source']) if state.get('preview_source') else None
                render_clone_preview(tpl_dir, tid, lang='zh', source_video=src_vid)
                render_clone_preview(tpl_dir, tid, lang='en', source_video=src_vid)

            with _jobs_lock:
                state['status'] = 'ready'
                state['step'] = 'ready'
                state['preview_zh_url'] = f'/api/v1/studio/templates/clone/{job_id}/assets/tpl/{tid}/preview/preview.mp4?r=1'
                state['preview_en_url'] = f'/api/v1/studio/templates/clone/{job_id}/assets/tpl/{tid}/preview/preview_en.mp4?r=1'
                state['poster_url'] = f'/api/v1/studio/templates/clone/{job_id}/assets/tpl/{tid}/preview/poster.webp?r=1'
        except Exception as exc:
            logger.exception('Template clone job %s failed', job_id)
            with _jobs_lock:
                state['status'] = 'failed'
                state['error'] = str(exc)

    if sync_run:
        _run()
    else:
        threading.Thread(target=_run, daemon=True, name=f'tpl-clone-{job_id}').start()
    return get_clone_job(job_id)


def get_clone_job(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        st = _jobs.get(job_id)
        if not st:
            raise UserFacingError('未找到该克隆任务，可能已过期')
        return {k: v for k, v in st.items() if k != 'revisions'} | {'can_undo': len(st.get('revisions') or []) > 1}


def refine_clone_job(
    job_id: str,
    *,
    variable_overrides: dict[str, Any] | None = None,
    instruction: str = '',
    render_preview: bool = True,
    vision_caller: Callable[..., dict] | None = None,
) -> dict[str, Any]:
    with _jobs_lock:
        st = _jobs.get(job_id)
        if not st or not st.get('blueprint'):
            raise UserFacingError('克隆任务尚未就绪')
        current = StyleBlueprint.model_validate(st['blueprint'])
        tid = st['template_id']

    updated = current
    if variable_overrides:
        patch: dict[str, Any] = {}
        for k in ('accent_color', 'font_scale', 'depth_enabled', 'grain_enabled', 'name_zh', 'name_en'):
            if k in variable_overrides and variable_overrides[k] is not None:
                patch[k] = variable_overrides[k]
        if patch:
            updated = updated.model_copy(update=patch).normalized()
    if instruction.strip():
        updated = refine_blueprint_with_instruction(updated, instruction, vision_caller=vision_caller)

    jdir = _job_dir(job_id)
    tpl_dir = synthesize_template_dir(tid, updated, jdir / 'tpl' / tid)
    registry.load_folder(tpl_dir)
    if render_preview:
        src_vid = Path(st['preview_source']) if st.get('preview_source') else None
        render_clone_preview(tpl_dir, tid, lang='zh', source_video=src_vid)
        render_clone_preview(tpl_dir, tid, lang='en', source_video=src_vid)

    with _jobs_lock:
        st['revisions'].append(updated.model_dump(mode='json'))
        st['revision'] = len(st['revisions'])
        st['blueprint'] = updated.model_dump(mode='json')
        rev = st['revision']
        st['preview_zh_url'] = f'/api/v1/studio/templates/clone/{job_id}/assets/tpl/{tid}/preview/preview.mp4?r={rev}'
        st['preview_en_url'] = f'/api/v1/studio/templates/clone/{job_id}/assets/tpl/{tid}/preview/preview_en.mp4?r={rev}'
        st['poster_url'] = f'/api/v1/studio/templates/clone/{job_id}/assets/tpl/{tid}/preview/poster.webp?r={rev}'
    return get_clone_job(job_id)


def revert_clone_job(job_id: str, *, render_preview: bool = True) -> dict[str, Any]:
    with _jobs_lock:
        st = _jobs.get(job_id)
        if not st or len(st.get('revisions') or []) <= 1:
            raise UserFacingError('没有可撤销的上一版本')
        st['revisions'].pop()
        prev = StyleBlueprint.model_validate(st['revisions'][-1])
        tid = st['template_id']

    jdir = _job_dir(job_id)
    tpl_dir = synthesize_template_dir(tid, prev, jdir / 'tpl' / tid)
    registry.load_folder(tpl_dir)
    if render_preview:
        render_clone_preview(tpl_dir, tid, lang='zh')
        render_clone_preview(tpl_dir, tid, lang='en')

    with _jobs_lock:
        st['revision'] = len(st['revisions'])
        st['blueprint'] = prev.model_dump(mode='json')
        rev = st['revision']
        st['preview_zh_url'] = f'/api/v1/studio/templates/clone/{job_id}/assets/tpl/{tid}/preview/preview.mp4?r={rev}'
        st['preview_en_url'] = f'/api/v1/studio/templates/clone/{job_id}/assets/tpl/{tid}/preview/preview_en.mp4?r={rev}'
        st['poster_url'] = f'/api/v1/studio/templates/clone/{job_id}/assets/tpl/{tid}/preview/poster.webp?r={rev}'
    return get_clone_job(job_id)


def save_clone_job(
    job_id: str,
    *,
    name_zh: str | None = None,
    name_en: str | None = None,
    user_root: Path | None = None,
) -> dict[str, Any]:
    with _jobs_lock:
        st = _jobs.get(job_id)
        if not st or st.get('status') != 'ready' or not st.get('blueprint'):
            raise UserFacingError('克隆任务尚未就绪，无法保存')
        bp = StyleBlueprint.model_validate(st['blueprint'])
        tid = st['template_id']

    if name_zh and name_zh.strip():
        bp = bp.model_copy(update={'name_zh': name_zh.strip()[:24]})
    if name_en and name_en.strip():
        bp = bp.model_copy(update={'name_en': name_en.strip()[:28]})

    jdir = _job_dir(job_id)
    src_tpl = jdir / 'tpl' / tid
    # Preserve existing previews while refreshing template.yaml with final bilingual name
    prev_backup = jdir / '_prev_backup'
    if (src_tpl / 'preview').is_dir():
        if prev_backup.exists():
            shutil.rmtree(prev_backup)
        shutil.copytree(src_tpl / 'preview', prev_backup)

    synthesize_template_dir(tid, bp, src_tpl)
    if prev_backup.is_dir():
        shutil.copytree(prev_backup, src_tpl / 'preview', dirs_exist_ok=True)
        shutil.rmtree(prev_backup, ignore_errors=True)

    spec = registry.load_folder(src_tpl)
    target_root = user_root if user_root is not None else registry.user_templates_root()
    target_root.mkdir(parents=True, exist_ok=True)
    final_dir = target_root / tid
    if final_dir.exists():
        shutil.rmtree(final_dir)
    shutil.copytree(src_tpl, final_dir)
    # Remove secondary _en previews from final installed folder
    for extra in ('preview_en.mp4', 'preview_en.webm', 'poster_en.webp'):
        (final_dir / 'preview' / extra).unlink(missing_ok=True)

    shutil.rmtree(jdir, ignore_errors=True)
    with _jobs_lock:
        _jobs.pop(job_id, None)
    return {'installed': spec.id, 'version': spec.effective_meta().package_version}


def resolve_clone_asset(job_id: str, rel_path: str) -> Path:
    base = _job_dir(job_id).resolve()
    target = (base / rel_path).resolve()
    if not target.is_relative_to(base) or not target.is_file():
        raise UserFacingError('预览文件不存在')
    return target
