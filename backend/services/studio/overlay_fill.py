"""Turn packaging fields into the setData payload an HTML template reads.

Sentence cues become one word each. A long editorial or street cue is paged into
two-line screens that share its clip interval. Each screen keeps the cue's original
source line (two lines, then an ellipsis) so the template can paint it underneath.
Optional kicker, emphasis, numbers, gloss and speakers are included when packaging
already has them. Stickers are not generated in this version.
"""
from __future__ import annotations

from backend.services.studio.caption_layout import lines_for, page_screens, width

SAFE_AREAS = ('xiaohongshu', 'douyin', 'tiktok', 'instagram_reels', 'youtube_shorts')
# Caption box on the 720px canvas. Editorial insets are the fixed #sub rule in
# style.css. Street insets are the SAFE map paint() applies over that template.
_CANVAS = 720
_EDITORIAL_FONT = 32
_EDITORIAL_INSET = 48
_STREET_FONT = 52
# CJK-width units for the small source line under a caption. Two lines, then an ellipsis.
_SOURCE_LIMIT = 34
_STREET_INSET = {
    'xiaohongshu': 48,
    'douyin': 36,
    'tiktok': 36,
    'instagram_reels': 40,
    'youtube_shorts': 36,
}


def caption_line_limit(template: str, safe_area: str = 'xiaohongshu') -> int | None:
    """CJK-width capacity of one caption line, or None when the cue is not paged."""
    if template == 'editorial':
        return (_CANVAS - 2 * _EDITORIAL_INSET) // _EDITORIAL_FONT
    if template == 'street':
        inset = _STREET_INSET.get(safe_area, _STREET_INSET['xiaohongshu'])
        return (_CANVAS - 2 * inset) // _STREET_FONT
    return None


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


def _frame_counts(span: int, weights: list[float]) -> list[int]:
    """Integer lengths that sum to `span`. Each screen gets at least one frame."""
    count = len(weights)
    extra_budget = span - count
    total = sum(weights) or float(count)
    raw = [extra_budget * weight / total for weight in weights]
    extra = [int(part) for part in raw]
    left = extra_budget - sum(extra)
    order = sorted(range(count), key=lambda i: (raw[i] - extra[i], weights[i], -i), reverse=True)
    for index in order[:left]:
        extra[index] += 1
    return [1 + part for part in extra]


def _emphasis_on_screen(text: str, phrase: str, start: int, end: int) -> str:
    """The part of the first matching phrase that lands on text[start:end]."""
    if not phrase:
        return ''
    at = text.find(phrase)
    if at < 0:
        return ''
    phrase_end = at + len(phrase)
    if end <= at or start >= phrase_end:
        return ''
    return text[max(start, at):min(end, phrase_end)]


def _source_line(text: str) -> str:
    """The cue's original, fitted to two source lines. The same line sits under every page of that cue."""
    cleaned = ' '.join(str(text or '').split())
    if not cleaned:
        return ''
    lines = lines_for(cleaned, _SOURCE_LIMIT)
    if len(lines) <= 2:
        return '\n'.join(lines)
    budget = _SOURCE_LIMIT - width('…')
    second = ''
    for word in ' '.join(lines[1:]).split(' '):
        candidate = f'{second} {word}'.strip()
        if width(candidate) > budget:
            break
        second = candidate
    return f'{lines[0]}\n{second}…' if second else f'{lines[0]}…'


def _speakers(packaging) -> list[dict]:
    found = []
    for item in _get(packaging, 'speakers', []) or []:
        name = str(_get(item, 'name', '')).strip()
        if not name:
            continue
        found.append({'name': name, 'role': str(_get(item, 'role', '') or '').strip()})
        if len(found) >= 4:
            break
    return found


def _append_cue(words: list, text: str, frames: tuple[int, int], phrase: str, limit: int | None, original: str = '') -> None:
    start, end = frames
    if not limit:
        words.append({'text': text, 'start_frame': start, 'end_frame': end, 'emphasis': phrase, 'original': original})
        return
    screens = page_screens(text, limit)
    if ''.join(screen.replace('\n', '') for screen in screens) != text:
        screens = []
    if len(screens) <= 1 or end - start < len(screens):
        # One screen still fits the box, so the template keeps today's CSS wrap.
        # A cue shorter than one frame per page cannot be split without overlap.
        words.append({'text': text, 'start_frame': start, 'end_frame': end, 'emphasis': phrase, 'original': original})
        return
    cursor = 0
    pieces = []
    for screen in screens:
        length = len(screen.replace('\n', ''))
        pieces.append((cursor, cursor + length, screen))
        cursor += length
    counts = _frame_counts(end - start, [max(width(screen.replace('\n', '')), 1) for screen in screens])
    frame = start
    for (lo, hi, screen), count in zip(pieces, counts):
        words.append({
            'text': screen,
            'start_frame': frame,
            'end_frame': frame + count,
            'emphasis': _emphasis_on_screen(text, phrase, lo, hi),
            'original': original,
        })
        frame += count


def build_fill(packaging, duration: float, fps: int = 30, safe_area: str = 'xiaohongshu', scenes=None, template: str | None = None) -> dict:
    """A JSON-safe fill. Word times are frame indexes on the clip, not source timestamps."""
    duration = max(0.0, float(duration))
    total = max(1, _frames(duration, fps))
    lines = [str(line).strip() for line in (_get(packaging, 'title_lines', []) or []) if str(line).strip()]
    # #367 / P2: HTML templates must honor the same captions switch as ASS packaging_render.
    captions_on = _get(packaging, 'captions_enabled', True)
    cues = list(_get(packaging, 'cues', []) or []) if captions_on is not False else []
    emphasis = [str(_get(mark, 'text', '')).strip() for mark in (_get(packaging, 'emphasis', []) or [])]
    emphasis = [phrase for phrase in emphasis if phrase]
    area = safe_area if safe_area in SAFE_AREAS else 'xiaohongshu'
    limit = caption_line_limit(template or '', area)
    words = []
    for cue in cues:
        text = str(_get(cue, 'text', '')).strip()
        if not text:
            continue
        phrase = next((item for item in emphasis if item in text), '')
        original = _source_line(_get(cue, 'original', ''))
        for out_start, out_end in _cue_output_spans(_get(cue, 'start', 0), _get(cue, 'end', 0), scenes):
            frames = _clip_frames(out_start, out_end, total, fps)
            if frames is None:
                continue
            _append_cue(words, text, frames, phrase, limit, original)
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
    hook = '\n'.join(lines) if lines else str(_get(packaging, 'kicker', '') or '')
    return {
        'fps': fps,
        'kicker': str(_get(packaging, 'kicker', '') or ''),
        'hook': {'text': hook, 'until_frame': min(total, _frames(2.4, fps))},
        'title_lines': lines[:2],
        'words': words,
        'gloss': cards,
        'number': number,
        'speakers': _speakers(packaging),
        'stickers': [],
        'safe_area': area,
    }


def paint_fill(fill: dict, packaging) -> dict:
    """The fill the HTML template actually paints.

    `build_fill` always keeps `title_lines` and the hook text. With captions off, painting
    them draws the editorial left hook (about 2.4s) or the street 34px boxes instead of the
    classic title. Drop only those painted fields; the classic title is burned beside the overlay.
    Captions-on returns the same dict, so that overlay payload does not change.
    """
    if _get(packaging, 'captions_enabled', True) is not False:
        return fill
    hook = dict(fill.get('hook') or {})
    hook['text'] = ''
    return {**fill, 'hook': hook, 'title_lines': []}
