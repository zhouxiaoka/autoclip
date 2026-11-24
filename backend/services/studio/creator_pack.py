"""Creator Pack compiler: Theme x Layout x Effect -> deterministic RenderPlan & FFmpeg graph.

Implements the GTA VI Creator Pack architecture (and any future game Creator Pack):
  - Deterministic event arbitration (manual > priority > confidence > earlier frame > id)
  - 12-frame same-type dedup, active-interval mutex, per-effect cooldown
  - 3 Themes x 4 Layouts (coast / split / desk / full) with automatic no-camera fallback
  - Dual-plane FFmpeg filtergraph (game window + embedded cameraROI or separate camera)
  - Game-only impact-hold freeze + B&W desaturation without altering audio or camera timing
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Default GTA VI Creator Pack registry (matches config/pack.json v1.0.0).
GTA_PACK_ID = 'autoclip.gta-vi-creator'
GTA_PACK_VERSION = '1.0.0'
CANVAS_W, CANVAS_H, FPS = 1080, 1920, 30
SAFE_RECT = (72, 132, 828, 1464)

DEFAULT_PACK: dict[str, Any] = {
    'id': GTA_PACK_ID,
    'version': GTA_PACK_VERSION,
    'canvas': [CANVAS_W, CANVAS_H],
    'fps': FPS,
    'safeRect': list(SAFE_RECT),
    'themes': {
        'vice-city-sunset': {
            'name': 'Vice City Sunset', 'key': 'sunset',
            'ink': '#26162F', 'paper': '#FFF1D4', 'accent': '#FF978E', 'secondary': '#FFD38E',
            'defaultLayout': 'coast',
        },
        'wasted': {
            'name': 'Wasted', 'key': 'wasted',
            'ink': '#171717', 'paper': '#F2EFE8', 'accent': '#FF5145', 'secondary': '#ADAAA3',
            'defaultLayout': 'split',
        },
        'leonida-news': {
            'name': 'Leonida News', 'key': 'news',
            'ink': '#0D2944', 'paper': '#F3F1DE', 'accent': '#FFD454', 'secondary': '#86BAC2',
            'defaultLayout': 'desk',
        },
    },
    'layouts': {
        'coast': {
            'game': [0, 0, 1080, 1500],
            'brand': [72, 132, 828, 280],
            'title': [72, 1200, 828, 130],
            'camera': [72, 1354, 215, 215],
            'caption': [318, 1354, 582, 215],
            'event': [72, 1080, 710, 98],
            'ticker': [72, 1572, 828, 24],
        },
        'split': {
            'game': [0, 440, 1080, 735],
            'brand': [72, 132, 828, 88],
            'title': [72, 243, 828, 164],
            'camera': [72, 1234, 286, 312],
            'caption': [388, 1234, 512, 312],
            'event': [72, 977, 828, 170],
            'ticker': [72, 1552, 828, 44],
        },
        'desk': {
            'game': [0, 414, 1080, 780],
            'brand': [72, 132, 828, 254],
            'title': [72, 1235, 828, 128],
            'camera': [682, 456, 218, 218],
            'caption': [72, 1374, 828, 124],
            'event': [72, 1110, 680, 90],
            'ticker': [72, 1520, 828, 76],
        },
        'full': {
            'game': [0, 0, 1080, 1920],
            'brand': [72, 132, 650, 126],
            'title': [72, 1146, 828, 134],
            'camera': None,
            'caption': [72, 1350, 828, 170],
            'event': [72, 1000, 720, 104],
            'ticker': [72, 1526, 828, 70],
        },
    },
    'effects': {
        'coast-pass': {'enter': 6, 'hold': 42, 'exit': 12, 'cooldown': 90},
        'impact-hold': {'enter': 3, 'hold': 15, 'exit': 12, 'cooldown': 90},
        'news-flash': {'enter': 6, 'hold': 66, 'exit': 12, 'cooldown': 120},
    },
    'eventMap': {
        'exploration': ['vice-city-sunset', 'coast-pass', 10],
        'stunt': ['vice-city-sunset', 'coast-pass', 20],
        'crash': ['wasted', 'impact-hold', 50],
        'fail': ['wasted', 'impact-hold', 40],
        'npc_oddity': ['leonida-news', 'news-flash', 30],
        'glitch': ['leonida-news', 'news-flash', 35],
    },
}

DEDUP_WINDOW_FRAMES = 12
AI_ACCEPT_CONFIDENCE = 0.80
AI_PENDING_CONFIDENCE = 0.60


@dataclass(frozen=True)
class AcceptedEvent:
    id: str
    type: str
    frame: int
    effect: str
    theme: str
    priority: int
    confidence: float
    source: str
    label: str
    enter: int
    hold: int
    exit: int

    @property
    def end_frame(self) -> int:
        return self.frame + self.enter + self.hold + self.exit

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'type': self.type,
            'frame': self.frame,
            'effect': self.effect,
            'theme': self.theme,
            'priority': self.priority,
            'confidence': self.confidence,
            'source': self.source,
            'label': self.label,
            'enter': self.enter,
            'hold': self.hold,
            'exit': self.exit,
            'end_frame': self.end_frame,
        }


@dataclass(frozen=True)
class RenderPlan:
    pack_id: str
    pack_version: str
    theme_id: str
    theme: dict[str, Any]
    layout_id: str
    slots: dict[str, list[int] | None]
    camera_active: bool
    camera_mode: str
    camera_roi: tuple[float, float, float, float] | None
    events: list[AcceptedEvent] = field(default_factory=list)
    pending_events: list[dict[str, Any]] = field(default_factory=list)
    reduced_motion: bool = False
    strength: float = 1.0
    host: str = ''
    location: str = ''
    ticker: str = ''
    fallback_reason: str = ''

    def to_overlay_dict(self) -> dict[str, Any]:
        return {
            'pack_id': self.pack_id,
            'pack_version': self.pack_version,
            'theme_id': self.theme_id,
            'theme': self.theme,
            'layout_id': self.layout_id,
            'slots': self.slots,
            'camera_active': self.camera_active,
            'events': [ev.to_dict() for ev in self.events],
            'reduced_motion': self.reduced_motion,
            'strength': self.strength,
            'host': self.host,
            'location': self.location,
            'ticker': self.ticker,
        }


def load_pack(folder: Path | None = None) -> dict[str, Any]:
    """Load pack.json from a template folder if present, else the built-in GTA pack."""
    if folder is not None:
        pack_path = folder / 'pack.json'
        if pack_path.is_file():
            try:
                loaded = json.loads(pack_path.read_text(encoding='utf-8'))
                if isinstance(loaded, dict) and 'themes' in loaded and 'layouts' in loaded:
                    return loaded
            except (OSError, json.JSONDecodeError):
                pass
    return DEFAULT_PACK


def _valid_roi(roi: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(roi, (list, tuple)) or len(roi) != 4:
        return None
    try:
        x, y, w, h = (float(roi[0]), float(roi[1]), float(roi[2]), float(roi[3]))
    except (TypeError, ValueError):
        return None
    if not (0.0 <= x < 1.0 and 0.0 <= y < 1.0 and w > 0.0 and h > 0.0 and x + w <= 1.0001 and y + h <= 1.0001):
        return None
    return (x, y, min(w, 1.0 - x), min(h, 1.0 - y))


def arbitrate_events(
    raw_events: list[dict[str, Any]] | None,
    duration_frames: int,
    pack: dict[str, Any] = DEFAULT_PACK,
) -> tuple[list[AcceptedEvent], list[dict[str, Any]]]:
    """Arbitrate raw event candidates according to implementation.md rules:

    - manual always eligible; AI needs confidence >= 0.80 (0.60..0.79 -> pending; <0.60 ignored)
    - ASR-only candidates stay pending (never auto-trigger full effects)
    - 12-frame same-type dedup (manual > confidence > earlier frame > id)
    - Global active-interval mutex + per-effect cooldown
    """
    event_map = pack.get('eventMap') or {}
    effects = pack.get('effects') or {}
    eligible: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []

    for idx, raw in enumerate(raw_events or []):
        if not isinstance(raw, dict):
            continue
        etype = str(raw.get('type') or '').strip()
        if etype not in event_map:
            continue
        frame = int(raw.get('frame', -1))
        if frame < 0 or frame >= max(1, int(duration_frames)):
            continue
        source = str(raw.get('source') or 'vision').strip().lower()
        try:
            conf = float(raw.get('confidence', 1.0 if source == 'manual' else 0.0))
        except (TypeError, ValueError):
            conf = 0.0
        eid = str(raw.get('id') or f'ev-{idx}')
        label = str(raw.get('label') or '')[:24]
        theme_id, fx_id, priority = event_map[etype]
        timing = effects.get(fx_id)
        if not timing:
            continue

        if source == 'asr':
            if conf >= AI_PENDING_CONFIDENCE:
                pending.append({**raw, 'id': eid, 'reason': 'asr_only'})
            continue
        if source != 'manual':
            if conf < AI_PENDING_CONFIDENCE:
                continue
            if conf < AI_ACCEPT_CONFIDENCE:
                pending.append({**raw, 'id': eid, 'reason': 'low_confidence'})
                continue

        eligible.append({
            'id': eid, 'type': etype, 'frame': frame, 'effect': fx_id,
            'theme': theme_id, 'priority': int(priority), 'confidence': conf,
            'source': source, 'label': label,
            'enter': int(timing['enter']), 'hold': int(timing['hold']),
            'exit': int(timing['exit']), 'cooldown': int(timing['cooldown']),
        })

    # 1. Deduplicate same-type candidates within 12 frames.
    eligible.sort(key=lambda c: (0 if c['source'] == 'manual' else 1, -c['confidence'], c['frame'], c['id']))
    deduped: list[dict[str, Any]] = []
    for cand in eligible:
        if any(
            kept['type'] == cand['type'] and abs(kept['frame'] - cand['frame']) <= DEDUP_WINDOW_FRAMES
            for kept in deduped
        ):
            continue
        deduped.append(cand)

    # 2. Global arbitration: manual > priority > confidence > earlier frame > id.
    deduped.sort(key=lambda c: (
        0 if c['source'] == 'manual' else 1,
        -c['priority'],
        -c['confidence'],
        c['frame'],
        c['id'],
    ))

    accepted: list[AcceptedEvent] = []
    last_fx_frame: dict[str, list[int]] = {}
    for cand in deduped:
        c_start = cand['frame']
        c_end = c_start + cand['enter'] + cand['hold'] + cand['exit']
        # Active-interval mutex
        if any(not (c_end <= prev.frame or c_start >= prev.end_frame) for prev in accepted):
            continue
        # Per-effect cooldown
        if any(abs(c_start - prev_f) < cand['cooldown'] for prev_f in last_fx_frame.get(cand['effect'], [])):
            continue
        ev = AcceptedEvent(
            id=cand['id'], type=cand['type'], frame=c_start, effect=cand['effect'],
            theme=cand['theme'], priority=cand['priority'], confidence=cand['confidence'],
            source=cand['source'], label=cand['label'],
            enter=cand['enter'], hold=cand['hold'], exit=cand['exit'],
        )
        accepted.append(ev)
        last_fx_frame.setdefault(cand['effect'], []).append(c_start)

    accepted.sort(key=lambda e: (e.frame, e.id))
    return accepted, pending


def resolve_render_plan(
    *,
    theme_id: str = 'auto',
    layout_id: str = 'auto',
    duration_frames: int = 360,
    events: list[dict[str, Any]] | None = None,
    camera_mode: str = 'none',
    camera_roi: Any = None,
    camera_enabled: bool = True,
    events_enabled: bool = True,
    reduced_motion: bool = False,
    strength: float = 1.0,
    host: str = '',
    location: str = '',
    ticker: str = '',
    pack: dict[str, Any] = DEFAULT_PACK,
) -> RenderPlan:
    """Compile theme, layout, camera, and event arbitration into one deterministic RenderPlan."""
    accepted, pending = arbitrate_events(events if events_enabled else [], duration_frames, pack)

    themes = pack['themes']
    layouts = pack['layouts']
    resolved_theme_id = theme_id
    if resolved_theme_id == 'auto' or resolved_theme_id not in themes:
        if accepted:
            best = sorted(accepted, key=lambda e: (-e.priority, -e.confidence, e.frame, e.id))[0]
            resolved_theme_id = best.theme
        else:
            resolved_theme_id = 'vice-city-sunset'
    theme = themes[resolved_theme_id]

    resolved_layout_id = layout_id
    if resolved_layout_id == 'auto' or resolved_layout_id not in layouts:
        resolved_layout_id = theme['defaultLayout']
    raw_slots = layouts[resolved_layout_id]
    slots: dict[str, list[int] | None] = {
        k: (list(v) if isinstance(v, list) else None)
        for k, v in raw_slots.items()
    }

    roi = _valid_roi(camera_roi)
    has_cam_slot = slots.get('camera') is not None
    cam_active = bool(camera_enabled and has_cam_slot and (
        (camera_mode == 'embedded' and roi is not None) or camera_mode == 'separate'
    ))
    fallback_reason = ''
    if not cam_active:
        slots['camera'] = None
        if resolved_layout_id in ('coast', 'split') and slots.get('caption'):
            # Widen caption to full safe width when camera is absent (implementation.md §5).
            cap = slots['caption']
            slots['caption'] = [72, cap[1], 828, cap[3]]
        if camera_enabled and has_cam_slot and camera_mode != 'none':
            fallback_reason = 'camera_unavailable'

    clamped_strength = max(0.0, min(1.0, float(strength)))
    if reduced_motion:
        clamped_strength = 0.0

    return RenderPlan(
        pack_id=str(pack.get('id') or GTA_PACK_ID),
        pack_version=str(pack.get('version') or GTA_PACK_VERSION),
        theme_id=resolved_theme_id,
        theme=theme,
        layout_id=resolved_layout_id,
        slots=slots,
        camera_active=cam_active,
        camera_mode=camera_mode if cam_active else 'none',
        camera_roi=roi if cam_active and camera_mode == 'embedded' else None,
        events=accepted,
        pending_events=pending,
        reduced_motion=bool(reduced_motion),
        strength=clamped_strength,
        host=str(host or '')[:24],
        location=str(location or '')[:32],
        ticker=str(ticker or '')[:120],
        fallback_reason=fallback_reason,
    )


def _hex_to_ffmpeg(color: str) -> str:
    cleaned = color.strip().lstrip('#')
    return f'0x{cleaned}' if len(cleaned) == 6 else '0x171717'


def _even(n: int) -> int:
    return max(2, int(n) - (int(n) % 2))


def build_base_video_graph(
    plan: RenderPlan,
    source_w: int,
    source_h: int,
    *,
    scene_start: float,
    scene_end: float,
    scene_offset: float = 0.0,
    fps: int = FPS,
    camera_input_index: int | None = None,
) -> tuple[str, str]:
    """Build the FFmpeg base video filtergraph for a Creator Pack layout.

    Layers produced here (below the transparent HTML/SVG overlay):
      00 matte (theme ink canvas 1080x1920)
      10 game (placed in plan.slots['game'], with impact-hold B&W desaturation when active)
      40 camera (optional embedded cameraROI cropped from input 0 or separate camera stream, placed in plan.slots['camera'])
    """
    game_rect = plan.slots.get('game') or [0, 0, CANVAS_W, CANVAS_H]
    gx, gy, gw, gh = int(game_rect[0]), int(game_rect[1]), _even(game_rect[2]), _even(game_rect[3])
    matte_hex = _hex_to_ffmpeg(plan.theme.get('ink', '#171717'))
    dur = max(0.04, float(scene_end) - float(scene_start))

    # Input 0 is already seeked to scene_start with -t duration by render.py.
    src_prep = f"[0:v]setpts=PTS-STARTPTS,fps={fps},setsar=1"

    # Build optional impact-hold B&W desaturation expression on the game plane ONLY.
    desat_terms: list[str] = []
    if not plan.reduced_motion and plan.strength > 0:
        for ev in plan.events:
            if ev.effect != 'impact-hold':
                continue
            t0 = (ev.frame / fps) - scene_offset
            t1 = ((ev.frame + ev.enter + ev.hold) / fps) - scene_offset
            if t1 > 0 and t0 < dur:
                desat_terms.append(f"between(t,{max(0.0, t0):.3f},{min(dur, t1):.3f})")
    game_fx = f",hue=s='if({'+'.join(desat_terms)},0,1)'" if desat_terms else ''

    # Cover-fit source into the game slot (or contain for wide sources in short split slots).
    src_ratio = (source_w / source_h) if (source_w > 0 and source_h > 0) else (16 / 9)
    slot_ratio = gw / gh
    if plan.layout_id in ('split', 'desk') and src_ratio > slot_ratio * 1.15:
        game_scale = f"scale={gw}:{gh}:force_original_aspect_ratio=decrease,pad={gw}:{gh}:(ow-iw)/2:(oh-ih)/2:color={matte_hex}"
    else:
        game_scale = f"scale={gw}:{gh}:force_original_aspect_ratio=increase,crop={gw}:{gh}"

    matte = f"color=c={matte_hex}:s={CANVAS_W}x{CANVAS_H}:r={fps}:d={dur:.3f},format=yuv420p[matte]"

    if plan.camera_active and plan.slots.get('camera'):
        cx, cy, cw, ch = (int(v) for v in plan.slots['camera'])
        cw, ch = _even(cw), _even(ch)
        if plan.camera_mode == 'separate' and camera_input_index is not None:
            parts = [
                matte,
                f"{src_prep},{game_scale}{game_fx}[game]",
                f"[{camera_input_index}:v]setpts=PTS-STARTPTS,fps={fps},setsar=1,scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch}[cam]",
                f"[matte][game]overlay={gx}:{gy}:shortest=1[with_game]",
                f"[with_game][cam]overlay={cx}:{cy}:shortest=1[base]",
            ]
            return ';'.join(parts), 'base'
        if plan.camera_roi:
            rx, ry, rw, rh = plan.camera_roi
            parts = [
                matte,
                f"{src_prep},split=2[src_g][src_c]",
                f"[src_g]{game_scale}{game_fx}[game]",
                f"[src_c]crop=w='max(2,trunc(iw*{rw:.4f}/2)*2)':h='max(2,trunc(ih*{rh:.4f}/2)*2)':x='trunc(iw*{rx:.4f}/2)*2':y='trunc(ih*{ry:.4f}/2)*2',scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch}[cam]",
                f"[matte][game]overlay={gx}:{gy}:shortest=1[with_game]",
                f"[with_game][cam]overlay={cx}:{cy}:shortest=1[base]",
            ]
            return ';'.join(parts), 'base'

    parts = [
        matte,
        f"{src_prep},{game_scale}{game_fx}[game]",
        f"[matte][game]overlay={gx}:{gy}:shortest=1[base]",
    ]
    return ';'.join(parts), 'base'


def event_phase(frame_index: int, ev: dict[str, Any]) -> float:
    """Exact frame-level opacity curve from implementation.md §7."""
    d = int(frame_index) - int(ev['frame'])
    enter = max(1, int(ev['enter']))
    hold = max(0, int(ev['hold']))
    exit_f = max(1, int(ev['exit']))
    total = enter + hold + exit_f
    if d < 0 or d >= total:
        return 0.0
    return max(0.0, min(1.0, (d + 1) / enter, (total - d) / exit_f))
