"""Turn packaging fields into the setData payload an HTML template reads.

Sentence cues become one word each. Optional kicker, emphasis, numbers and
gloss are included when packaging already has them. Stickers are not generated
in this version.
"""
from __future__ import annotations

SAFE_AREAS = ('xiaohongshu', 'douyin', 'tiktok', 'instagram_reels', 'youtube_shorts')


def _get(packaging, name, default):
    if packaging is None:
        return default
    if isinstance(packaging, dict):
        return packaging.get(name, default)
    return getattr(packaging, name, default)


def _frames(seconds: float, fps: int) -> int:
    return max(0, int(round(float(seconds) * fps)))


def _cue_output_spans(start: float, end: float, scenes) -> list[tuple[float, float]]:
    """Map a source-time cue onto the concatenated clip, the same way classic ASS does.

    Without scenes the cue is already on the output clock. With scenes, subtract each
    scene start and place the overlap at that scene's output offset.
    """
    start, end = float(start or 0), float(end or 0)
    if not scenes:
        return [(start, end)] if end > start else []
    from backend.services.studio.audio import scene_duration
    from backend.services.studio.packaging_render import timeline
    spans = []
    for scene, (src_start, src_end, offset) in zip(scenes, timeline(scenes)):
        lo, hi = max(start, float(src_start)), min(end, float(src_end))
        if hi <= lo:
            continue
        length = scene_duration(scene)
        out_start = max(offset, offset + lo - float(src_start))
        out_end = min(offset + length, offset + hi - float(src_start))
        if out_end > out_start:
            spans.append((out_start, out_end))
    return spans


def _clip_frames(out_start: float, out_end: float, total: int, fps: int) -> tuple[int, int] | None:
    start = _frames(out_start, fps)
    end = _frames(out_end, fps)
    if end <= start:
        end = start + 1
    if start >= total:
        return None
    end = min(end, total)
    if end <= start:
        return None
    return start, end


def build_fill(packaging, duration: float, fps: int = 30, safe_area: str = 'xiaohongshu', scenes=None) -> dict:
    """A JSON-safe fill. Word times are frame indexes on the clip, not source timestamps."""
    duration = max(0.0, float(duration))
    total = max(1, _frames(duration, fps))
    lines = [str(line).strip() for line in (_get(packaging, 'title_lines', []) or []) if str(line).strip()]
    # #367 / P2: HTML templates must honor the same captions switch as ASS packaging_render.
    captions_on = _get(packaging, 'captions_enabled', True)
    cues = list(_get(packaging, 'cues', []) or []) if captions_on is not False else []
    emphasis = [str(_get(mark, 'text', '')).strip() for mark in (_get(packaging, 'emphasis', []) or [])]
    emphasis = [phrase for phrase in emphasis if phrase]
    words = []
    for cue in cues:
        text = str(_get(cue, 'text', '')).strip()
        if not text:
            continue
        phrase = next((item for item in emphasis if item in text), '')
        for out_start, out_end in _cue_output_spans(_get(cue, 'start', 0), _get(cue, 'end', 0), scenes):
            frames = _clip_frames(out_start, out_end, total, fps)
            if frames is None:
                continue
            words.append({'text': text, 'start_frame': frames[0], 'end_frame': frames[1], 'emphasis': phrase})
    cards = []
    glosses = list(_get(packaging, 'gloss', []) or [])
    for index, card in enumerate(glosses):
        title = str(_get(card, 'title', '')).strip()
        if not title:
            continue
        start = min(total, _frames(_get(card, 'at', 0) or 0, fps))
        nxt = glosses[index + 1] if index + 1 < len(glosses) else None
        end = min(total, _frames(_get(nxt, 'at', 0) or 0, fps)) if nxt is not None else min(total, start + _frames(2.4, fps))
        if end <= start:
            end = min(total, start + _frames(2.4, fps))
        cards.append({'id': f'g{index}', 'title': title, 'body': str(_get(card, 'body', '') or ''), 'start_frame': start, 'end_frame': max(start + 1, end)})
    number = None
    for item in _get(packaging, 'numbers', []) or []:
        start = min(total, _frames(_get(item, 'at', 0) or 0, fps))
        end = min(total, start + _frames(1.2, fps))
        try:
            value = float(_get(item, 'value', 0))
        except (TypeError, ValueError):
            continue
        number = {
            'value': value,
            'unit': str(_get(item, 'unit', '') or ''),
            'start_frame': start,
            'end_frame': max(start + 1, end),
            'hold_frame': min(total, max(start + 1, end) + _frames(0.6, fps)),
            'steps': 8,
        }
        break
    area = safe_area if safe_area in SAFE_AREAS else 'xiaohongshu'
    hook = '\n'.join(lines) if lines else str(_get(packaging, 'kicker', '') or '')
    return {
        'fps': fps,
        'kicker': str(_get(packaging, 'kicker', '') or ''),
        'hook': {'text': hook, 'until_frame': min(total, _frames(2.4, fps))},
        'title_lines': lines[:2],
        'words': words,
        'gloss': cards,
        'number': number,
        'stickers': [],
        'safe_area': area,
    }
