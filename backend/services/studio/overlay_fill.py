"""Turn packaging fields into the setData payload an HTML template reads.

Editorial and street cues become one-line phrases. A phrase is a punctuation
clause, wrapped only when it is wider than the 1080px line. Phrases share the
cue's clip interval by length, or by ASR word times when a sidecar is passed in.
The English line keeps the cue's original sentence. Optional deck, issue, emphasis,
numbers, gloss and speakers are included when packaging already has them.
Stickers are not generated in this version.
"""
from __future__ import annotations

import re

from backend.services.studio.caption_layout import lines_for, page_screens, width

SAFE_AREAS = ('xiaohongshu', 'douyin', 'tiktok', 'instagram_reels', 'youtube_shorts')
# Phrase budget on the 1080px canvas. One line, no wrap: street 100px inside 30px
# insets, editorial 52px inside 60px insets. A longer sentence is split into phrases.
_CANVAS = 1080
_EDITORIAL_FONT = 52
_EDITORIAL_INSET = 60
_STREET_FONT = 100
_SOURCE_LIMIT = 34
_STREET_SOURCE_LIMIT = 42
_STREET_INSET = {
    'xiaohongshu': 30,
    'douyin': 30,
    'tiktok': 30,
    'instagram_reels': 30,
    'youtube_shorts': 30,
}
_PUNCT = '，。、！？：；,.!?'


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


def _source_line(text: str, limit: int = _SOURCE_LIMIT) -> str:
    """The cue's original, fitted to two source lines. The same line sits under every page of that cue."""
    cleaned = ' '.join(str(text or '').split())
    if not cleaned:
        return ''
    lines = lines_for(cleaned, limit)
    if len(lines) <= 2:
        return '\n'.join(lines)
    budget = limit - width('…')
    second = ''
    for word in ' '.join(lines[1:]).split(' '):
        candidate = f'{second} {word}'.strip()
        if width(candidate) > budget:
            break
        second = candidate
    return f'{lines[0]}\n{second}…' if second else f'{lines[0]}…'


def _speaker_with_at(item) -> dict:
    return {
        'name': str(_get(item, 'name', '') or '').strip(),
        'role': str(_get(item, 'role', '') or '').strip(),
        'at': _get(item, 'at', 0) or 0,
    }


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


def _append_cue(words: list, text: str, frames: tuple[int, int], phrase: str, limit: int | None, original: str = '', speaker: str = '') -> None:
    start, end = frames
    if not limit:
        words.append({'text': text, 'start_frame': start, 'end_frame': end, 'emphasis': phrase, 'original': original, 'speaker': speaker})
        return
    screens = page_screens(text, limit)
    if ''.join(screen.replace('\n', '') for screen in screens) != text:
        screens = []
    if len(screens) <= 1 or end - start < len(screens):
        # One screen still fits the box, so the template keeps today's CSS wrap.
        # A cue shorter than one frame per page cannot be split without overlap.
        words.append({'text': text, 'start_frame': start, 'end_frame': end, 'emphasis': phrase, 'original': original, 'speaker': speaker})
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
            'speaker': speaker,
        })
        frame += count


def _cue_phrase(cue, text: str, listed: list[str]) -> str:
    """The cue's own phrase, else the first listed phrase inside the cue, else a stable fallback."""
    from backend.services.studio.packaging import _accept_phrase, key_phrase
    own = _accept_phrase(str(_get(cue, 'emphasis', '') or ''), text)
    if own:
        return own
    listed_hit = next((item for item in listed if item in text), '')
    if listed_hit:
        return listed_hit
    return key_phrase(text, str(_get(cue, 'original', '') or ''))


def _cue_speaker_name(cue, speakers: list[dict], packaging=None) -> str:
    """The cue's own speaker, in the audience's writing. An unnamed line stays unnamed.

    A Latin name on a Chinese video becomes the one CJK guest on the roster, or nothing.
    It is not replaced with whoever happens to be the only person in the roster when the
    cue never named them.
    """
    from backend.services.studio.packaging import CJK, LATIN, _localize_zh_name, _speaker_name
    claimed = _speaker_name(
        str(_get(cue, 'text', '') or ''),
        _get(cue, 'start', 0) or 0,
        str(_get(cue, 'speaker', '') or ''),
        [{'name': item['name'], 'at': _get(item, 'at', 0) or 0, 'role': item.get('role', '')} for item in speakers],
    )
    if not claimed:
        return ''
    audience = str(_get(packaging, 'audience_language', '') or '')
    roster = ' '.join(item.get('name', '') for item in speakers if item.get('name'))
    localized = _localize_zh_name(claimed, audience, roster)
    if audience == 'zh' and not localized and LATIN.search(claimed) and not CJK.search(claimed):
        return ''
    return localized or claimed


def _deck_line(packaging) -> str:
    """The model's deck only. A clipped first sentence is not a deck."""
    deck = str(_get(packaging, 'deck', '') or '').strip()
    return deck[:80] if deck else ''


_CREDIT_STOP = {'on', 'the', 'a', 'an', 'of', 'about', 'and'}


def _caps_credit(deck: str, speakers: list[dict], title_lines: list[str] | None = None) -> str:
    """TOPIC · SPEAKER under the magazine headline.

    "Jensen Huang on the five-layer cake" becomes FIVE-LAYER CAKE · JENSEN HUANG.
    A long spoken sentence is shortened to its last few words.
    """
    if not deck:
        return ''
    text = ' '.join(deck.split())
    named = re.match(r'^(.+?)\s+on\s+(.+)$', text, flags=re.IGNORECASE)
    if named and re.search(r'[A-Za-z]', named.group(1)):
        who = named.group(1).strip()
        topic_words = [word for word in named.group(2).split() if word]
        while topic_words and topic_words[0].lower().strip('.,') in _CREDIT_STOP:
            topic_words = topic_words[1:]
        topic = ' '.join(topic_words[-4:] if len(topic_words) > 4 else topic_words).upper()
        return f'{topic} · {who.upper()}' if topic else who.upper()
    titled = ' '.join(title_lines or [])
    name = ''
    for person in speakers:
        if person['name'] and person['name'] in titled:
            name = person['name']
            break
    if not name and speakers:
        name = speakers[0]['name']
    words = [word for word in text.replace('·', ' ').split() if word]
    if name:
        dropped = {part.lower() for part in name.split()}
        words = [word for word in words if word.lower() not in dropped]
    while words and words[0].lower().strip('.,') in _CREDIT_STOP:
        words = words[1:]
    topic = ' '.join(words[-4:] if len(words) > 4 else words).upper()
    if name and any('A' <= ch <= 'z' for ch in name):
        shown = name.upper()
    else:
        shown = name
    if not topic:
        return shown
    if not shown or shown.lower() in topic.lower():
        return topic
    return f'{topic} · {shown}'


def _clip_units(text: str, limit: float) -> str:
    out = ''
    for ch in text:
        if width(out + ch) > limit:
            break
        out += ch
    return out.strip().strip(_PUNCT).strip()


def _hard_slices(token: str, limit: float) -> list[str]:
    """A single token wider than the line. Cut by character only then."""
    slices: list[str] = []
    buf = ''
    for ch in token:
        if buf and width(buf + ch) > limit + 1e-6:
            slices.append(buf)
            buf = ch
        else:
            buf += ch
    if buf:
        slices.append(buf)
    return slices


def _wrap_units(text: str, limit: float) -> list[str]:
    """One line per chunk. Breaks land on word boundaries, not inside 15小时 / 生产力 / DNA里."""
    if width(text) <= limit + 1e-6:
        return [text]
    from backend.services.studio.cjk_segment import tokenize
    chunks: list[str] = []
    buf = ''
    for token in tokenize(text):
        if not token.strip():
            if buf and width(buf + token) <= limit + 1e-6:
                buf += token
            continue
        if width(token) > limit + 1e-6:
            if buf.strip():
                chunks.append(buf.strip())
                buf = ''
            chunks.extend(_hard_slices(token, limit))
            continue
        if buf and width(buf + token) > limit + 1e-6:
            chunks.append(buf.strip())
            buf = token
        else:
            buf += token
    if buf.strip():
        chunks.append(buf.strip())
    return [chunk for chunk in chunks if chunk]


def _phrases(text: str, limit: float) -> list[str]:
    """Short single-line pieces. Trailing punctuation is dropped, the same way the preview does."""
    cleaned = str(text or '').strip().strip(_PUNCT).strip()
    if not cleaned:
        return []
    parts = [part.strip() for part in re.split(r'[，。、！？：；,.!?]+', cleaned) if part.strip()]
    pieces: list[str] = []
    for part in parts:
        pieces.extend(_wrap_units(part, limit))
    return pieces or [cleaned]


def _en_key(token: str, emphasis: str) -> bool:
    """Lime only when this English token, or a digit run, actually occurs in the emphasis.

    一半 does not paint HALF. A shared number such as 8 does.
    """
    if not emphasis:
        return False
    leaf = re.sub(r'[^A-Za-z0-9]+', '', token).lower()
    folded = re.sub(r'[^A-Za-z0-9]+', '', emphasis).lower()
    if leaf and folded and (leaf == folded or (len(leaf) >= 3 and leaf in folded) or (len(folded) >= 3 and folded in leaf)):
        return True
    return any(digit and digit in token for digit in re.findall(r'\d+', emphasis))


def _map_time(t: float, scenes) -> float | None:
    if not scenes:
        return t
    from backend.services.studio.packaging_render import timeline
    for _scene, (src_start, src_end, offset) in zip(scenes, timeline(scenes)):
        if float(src_start) - 1e-3 <= t <= float(src_end) + 1e-3:
            return offset + (t - float(src_start))
    return None


def _en_words(original: str, t0: float, t1: float, emphasis: str, timed: list | None) -> list[dict]:
    original = ' '.join(str(original or '').split())
    if not original:
        return []
    if timed:
        rows = []
        for word in timed:
            token = str(word.get('text') or '').strip()
            if not token:
                continue
            try:
                start, end = float(word['start']), float(word['end'])
            except (KeyError, TypeError, ValueError):
                continue
            if end > start:
                rows.append((token, start, end))
        if rows:
            return [{'w': token, 't0': start, 't1': end, 'key': _en_key(token, emphasis)} for token, start, end in rows]
    tokens = original.split(' ')
    weights = [max(len(token), 1) for token in tokens]
    total = sum(weights) or 1
    span = max(t1 - t0, 0.05)
    cursor = t0
    words = []
    for token, weight in zip(tokens, weights):
        dur = span * weight / total
        words.append({'w': token, 't0': cursor, 't1': cursor + dur, 'key': _en_key(token, emphasis)})
        cursor += dur
    return words


def _fit_pieces(pieces: list[str], span: int) -> list[str]:
    """Never ask for more phrases than frames. Extra pieces join the previous one."""
    merged = list(pieces)
    while len(merged) > max(1, span):
        merged[-2] = f'{merged[-2]}{merged[-1]}'
        merged.pop()
    return merged


def _timed_in_cue(cue, word_timing, scenes) -> list | None:
    """ASR words that overlap this cue, on the output clock. None when there is no sidecar."""
    if not word_timing:
        return None
    start = float(_get(cue, 'start', 0) or 0)
    end = float(_get(cue, 'end', 0) or 0)
    rows = []
    for segment in word_timing:
        if not isinstance(segment, dict):
            continue
        words = segment.get('words')
        if not isinstance(words, list):
            words = [segment] if 'start' in segment and 'text' in segment else []
        for word in words:
            if not isinstance(word, dict):
                continue
            token = str(word.get('text') or '').strip()
            try:
                word_start, word_end = float(word['start']), float(word['end'])
            except (KeyError, TypeError, ValueError):
                continue
            if not token or word_end <= start or word_start >= end:
                continue
            mapped_start = _map_time(max(word_start, start), scenes)
            mapped_end = _map_time(min(word_end, end), scenes)
            if mapped_start is None or mapped_end is None or mapped_end <= mapped_start:
                continue
            rows.append({'text': token, 'start': mapped_start, 'end': mapped_end})
    return rows or None


def _groups(spoken: list, group_limit: float) -> list[list]:
    """Phrases that share a line and a contiguous stretch of the output clock.

    A cut that removes the middle of a sentence leaves a gap. Those two sides are
    different moments, so the first phrase does not stay up through the other shot.
    """
    groups: list[list] = []
    current: list = []
    used = 0.0
    for item in spoken:
        piece_width = width(item[0])
        gap = current and item[3] > current[-1][4]
        if current and (gap or used + piece_width > group_limit + 1e-6):
            groups.append(current)
            current = []
            used = 0.0
        current.append(item)
        used += piece_width
    if current:
        groups.append(current)
    return groups


def _mark_accents(moments: list[dict]) -> None:
    """One gold serif phrase per moment, and not again for 3 seconds."""
    last = -9.0
    for moment in moments:
        chosen = None
        for phrase in moment['zh']:
            if phrase['key'] and len(phrase['s']) >= 2 and phrase['t0'] - last >= 3.0:
                chosen = phrase
                break
        for phrase in moment['zh']:
            phrase['acc'] = phrase is chosen
        if chosen is not None:
            last = chosen['t0']


def _short_topic(lines: list[str], speakers: list[dict]) -> str:
    raw = (lines[0] if lines else '').strip()
    names = [item['name'] for item in speakers if item.get('name')]
    for _ in range(4):
        changed = False
        for name in names:
            for mark in (f'{name}：', f'{name}:'):
                if mark in raw:
                    raw = raw.replace(mark, '')
                    changed = True
        if not changed:
            break
    return _clip_units(raw.strip().strip(_PUNCT), 12)


def _timecode(seconds: float) -> str:
    whole = int(max(0, round(seconds)))
    hours, rem = divmod(whole, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f'{hours}:{minutes:02d}:{secs:02d}'
    return f'{minutes}:{secs:02d}'


def _kept_spans(start: float, end: float, scenes) -> list[tuple[float, float, float, float]]:
    """Each kept overlap as (source start, source end, output start, output end)."""
    start, end = float(start or 0), float(end or 0)
    if end <= start:
        return []
    if not scenes:
        return [(start, end, start, end)]
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
            spans.append((lo, hi, out_start, out_end))
    return spans


def _source_words(cue, word_timing) -> list | None:
    """ASR words overlapping this cue, still on the source clock."""
    if not word_timing:
        return None
    start = float(_get(cue, 'start', 0) or 0)
    end = float(_get(cue, 'end', 0) or 0)
    rows = []
    for segment in word_timing:
        if not isinstance(segment, dict):
            continue
        words = segment.get('words')
        if not isinstance(words, list):
            words = [segment] if 'start' in segment and 'text' in segment else []
        for word in words:
            if not isinstance(word, dict):
                continue
            token = str(word.get('text') or '').strip()
            try:
                word_start, word_end = float(word['start']), float(word['end'])
            except (KeyError, TypeError, ValueError):
                continue
            if not token or word_end <= start or word_start >= end:
                continue
            rows.append({'text': token, 'start': max(word_start, start), 'end': min(word_end, end)})
    rows.sort(key=lambda item: (item['start'], item['end']))
    return rows or None


def _align_phrase_times(pieces: list[str], words: list, start: float, end: float) -> list[tuple[str, float, float]] | None:
    """Give each phrase the source interval of the words it covers. None when the text does not line up."""
    def norm(value: str) -> str:
        return re.sub(r'[\s，。、！？：；,.!?]+', '', value)

    cursor = 0
    rows = []
    for piece in pieces:
        target = norm(piece)
        if not target:
            continue
        if cursor >= len(words):
            return None
        acc = ''
        t0 = t1 = None
        while cursor < len(words) and target not in acc:
            acc += norm(words[cursor]['text'])
            if t0 is None:
                t0 = float(words[cursor]['start'])
            t1 = float(words[cursor]['end'])
            cursor += 1
            if len(acc) > len(target) + 12 and target not in acc:
                return None
        if t0 is None or t1 is None or t1 <= t0:
            return None
        rows.append((piece, max(start, t0), min(end, t1)))
    return rows or None


def _length_bounds(pieces: list[str], start: float, end: float) -> list[tuple[str, float, float]]:
    weights = [max(width(piece), 1) for piece in pieces]
    total_weight = sum(weights) or 1
    span = max(end - start, 0.05)
    cursor = start
    rows = []
    for piece, weight in zip(pieces, weights):
        dur = span * weight / total_weight
        rows.append((piece, cursor, cursor + dur))
        cursor += dur
    if rows:
        piece, t0, _t1 = rows[-1]
        rows[-1] = (piece, t0, end)
    return rows


def _once_per_clip(pieces: list[str], cue_start: float, cue_end: float, scenes, total: int, fps: int, source_words) -> list[tuple]:
    """Place each phrase on the output clock once, at the moment it is spoken.

    A cue that crosses a cut used to restart its whole phrase list inside every shot.
    Phrases are timed across the cue, then mapped through the shots. A phrase the cut
    removes is dropped. A phrase the cut splits is kept on the first overlap only.
    One shot that contains the whole cue keeps the old frame tiling, so a single scene
    still meets the caption page exactly.
    """
    spans = _kept_spans(cue_start, cue_end, scenes)
    if not spans:
        return []
    src_lo, src_hi, out_lo, out_hi = spans[0]
    whole = len(spans) == 1 and abs(src_lo - cue_start) <= 1e-3 and abs(src_hi - cue_end) <= 1e-3
    aligned = _align_phrase_times(pieces, source_words, cue_start, cue_end) if source_words else None
    if whole and not aligned:
        frames = _clip_frames(out_lo, out_hi, total, fps)
        if frames is None:
            return []
        shown = _fit_pieces(pieces, frames[1] - frames[0])
        counts = _frame_counts(frames[1] - frames[0], [max(width(piece), 1) for piece in shown])
        cursor = frames[0]
        placed = []
        for piece, count in zip(shown, counts):
            placed.append((piece, cursor / fps, (cursor + count) / fps, cursor, cursor + count))
            cursor += count
        return placed
    bounds = aligned or _length_bounds(pieces, cue_start, cue_end)
    rough = []
    for piece, t0, t1 in bounds:
        for span_lo, span_hi, span_out, span_end in spans:
            ov0, ov1 = max(t0, span_lo), min(t1, span_hi)
            if ov1 <= ov0 + 1e-4:
                continue
            scale = (span_end - span_out) / max(span_hi - span_lo, 1e-6)
            rough.append((piece, span_out + (ov0 - span_lo) * scale, span_out + (ov1 - span_lo) * scale))
            break
    placed = []
    for piece, ot0, ot1 in rough:
        start = _frames(ot0, fps)
        end = _frames(ot1, fps)
        if end <= start:
            end = start + 1
        if placed and start < placed[-1][4]:
            start = placed[-1][4]
        if start >= total:
            continue
        end = min(end, total)
        if end <= start:
            continue
        placed.append((piece, start / fps, end / fps, start, end))
    return placed


def build_fill(packaging, duration: float, fps: int = 30, safe_area: str = 'xiaohongshu', scenes=None, template: str | None = None, word_timing=None) -> dict:
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
    source_limit = _STREET_SOURCE_LIMIT if (template or '') == 'street' else _SOURCE_LIMIT
    people = _speakers(packaging)
    words = []
    moments = []
    phrase_limit = float(limit or 10)
    # One caption line. Two full phrases used to share a moment and overflow the box.
    group_limit = phrase_limit if (template or '') == 'editorial' else phrase_limit * 10**6
    roster = [_speaker_with_at(item) for item in (_get(packaging, 'speakers', []) or [])]
    for cue in cues:
        text = str(_get(cue, 'text', '')).strip()
        if not text:
            continue
        phrase = _cue_phrase(cue, text, emphasis)
        raw_original = str(_get(cue, 'original', '') or '')
        # The preview keeps the whole English sentence on one line and shrinks it. The template trims what still overflows.
        original = ' '.join(raw_original.split()) if (template or '') in {'editorial', 'street'} else _source_line(raw_original, source_limit)
        speaker = _cue_speaker_name(cue, roster, packaging)
        pieces = _phrases(text, phrase_limit)
        if not pieces:
            continue
        timed = _timed_in_cue(cue, word_timing, scenes)
        spoken = _once_per_clip(
            pieces, float(_get(cue, 'start', 0) or 0), float(_get(cue, 'end', 0) or 0),
            scenes, total, fps, _source_words(cue, word_timing),
        )
        if not spoken:
            continue
        english = _en_words(original, spoken[0][1], spoken[-1][2], phrase, timed)
        groups = _groups(spoken, group_limit)
        for group in groups:
            zh = []
            group_en = [
                word for word in english
                if word['t1'] > group[0][1] - 1e-6 and word['t0'] < group[-1][2] + 1e-6
            ] or english
            for piece, t0, t1, start_frame, end_frame in group:
                key = bool(phrase and (phrase in piece or piece in phrase)) or any(
                    word['key'] and word['t1'] > t0 and word['t0'] < t1 for word in group_en
                )
                zh.append({'s': piece, 't0': t0, 't1': t1, 'key': key, 'acc': False})
                words.append({
                    'text': piece,
                    'start_frame': start_frame,
                    'end_frame': end_frame,
                    'emphasis': phrase if key and phrase and (phrase in piece or piece in phrase) else '',
                    'original': original,
                    'speaker': speaker,
                })
            moments.append({
                't0': group[0][1], 't1': group[-1][2], 'speaker': speaker,
                'zh': zh, 'en': group_en,
            })
    _mark_accents(moments)
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
    deck = _deck_line(packaging)
    credit = _caps_credit(deck, people, lines)
    accent = _get(packaging, 'title_accent_line', len(lines) - 1 if lines else 0)
    try:
        accent = int(accent)
    except (TypeError, ValueError):
        accent = len(lines) - 1 if lines else 0
    hook_lines = [[line, index == accent] for index, line in enumerate(lines[:2])]
    issue = str(_get(packaging, 'issue', '') or '').strip()
    src_start = 0.0
    if scenes:
        src_start = float(_get(scenes[0], 'start', 0) or 0)
    return {
        'fps': fps,
        'T': duration,
        'kicker': str(_get(packaging, 'kicker', '') or '')[:16],
        'hook': {'text': hook, 'until_frame': total},
        'hook_lines': hook_lines,
        'hook_trk': credit,
        'title_lines': lines[:2],
        'topic': _short_topic(lines, people),
        'words': words,
        'moments': moments,
        'gloss': cards,
        'number': number,
        'speakers': people,
        'deck': deck,
        'credit': credit,
        'issue': issue,
        'src_start_tc': _timecode(src_start),
        'stickers': [],
        'safe_area': area,
        'audience_language': str(_get(packaging, 'audience_language', '') or ''),
    }


def paint_fill(fill: dict, packaging, template: str | None = None) -> dict:
    """The fill the HTML template actually paints.

    `build_fill` always keeps `title_lines` and the hook text. With captions off, editorial
    drops those painted fields so the classic title can be burned beside the overlay.
    Street keeps them: the lower band paints the title, and the classic top title is not burned.
    Captions-on returns the same dict, so that overlay payload does not change.
    """
    if _get(packaging, 'captions_enabled', True) is not False:
        return fill
    if (template or _get(packaging, 'template', '')) == 'street':
        return fill
    hook = dict(fill.get('hook') or {})
    hook['text'] = ''
    return {**fill, 'hook': hook, 'hook_lines': [], 'title_lines': [], 'kicker': '', 'deck': '', 'hook_trk': '', 'credit': ''}
