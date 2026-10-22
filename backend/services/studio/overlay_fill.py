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
# Phrase budget on the 1080px canvas. One line, no wrap: street 84px inside 30px
# insets (ink about 92px, inside the 90–96 cap), editorial 52px inside 60px insets.
# A longer sentence is split into phrases.
_CANVAS = 1080
_EDITORIAL_FONT = 52
_EDITORIAL_INSET = 60
_STREET_FONT = 84
_MIN_PHRASE_SEC = 0.6
_LEAD = set('的了着过地得吗呢吧啊呀')
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


def _transcript_rows(transcript) -> list[tuple]:
    rows = []
    for item in transcript or []:
        speaker = ''
        if isinstance(item, dict):
            try:
                start = float(item.get('start', item.get('start_time', 0)) or 0)
                end = float(item.get('end', item.get('end_time', 0)) or 0)
            except (TypeError, ValueError):
                continue
            text = str(item.get('text') or '')
            speaker = str(item.get('speaker') or '').strip()
        else:
            try:
                start, end, text = float(item[0]), float(item[1]), str(item[2])
            except (TypeError, ValueError, IndexError):
                continue
            if len(item) > 3 and item[3]:
                speaker = str(item[3]).strip()
        if end > start and text.strip():
            rows.append((start, end, text, speaker))
    rows.sort(key=lambda row: (row[0], row[1]))
    return rows


def _turns(rows: list[tuple]) -> list[tuple]:
    """``(start, end, parity, text, explicit name)``. Each ``>>`` starts the next speaker.

    A file that opens without ``>>`` is parity 0. The first ``>>`` is the next speaker.
    """
    parity = -1
    turns = []
    for start, end, text, explicit in rows:
        if explicit:
            turns.append((start, end, None, text, explicit))
            continue
        if text.lstrip().startswith('>>') or parity < 0:
            parity += 1
        turns.append((start, end, parity, text, ''))
    return turns


def _host_parity(turns: list[tuple]) -> int:
    """The side with more questions. With none, the shorter side: the guest talks more."""
    questions = {0: 0, 1: 0}
    durations = {0: 0.0, 1: 0.0}
    for start, end, parity, text, _explicit in turns:
        if parity is None:
            continue
        side = int(parity) % 2
        questions[side] += text.count('?') + text.count('？')
        durations[side] += max(0.0, end - start)
    if questions[0] != questions[1]:
        return 0 if questions[0] > questions[1] else 1
    if durations[0] != durations[1]:
        return 0 if durations[0] < durations[1] else 1
    return 0


def _diarized_name(cue_start: float, cue_end: float, word_timing, speakers: list[dict]) -> str:
    """A word or segment ``speaker`` that is already a roster name. Empty when there is none."""
    if not word_timing:
        return ''
    from backend.services.studio.packaging import _HOST_NAMES
    roster = {str(person.get('name') or '').strip() for person in speakers}
    roster.discard('')
    totals: dict[str, float] = {}
    for segment in word_timing:
        if not isinstance(segment, dict):
            continue
        words = segment.get('words')
        if not isinstance(words, list):
            words = [segment] if 'start' in segment else []
        segment_name = str(segment.get('speaker') or '').strip()
        for word in words:
            if not isinstance(word, dict):
                continue
            name = str(word.get('speaker') or segment_name).strip()
            if name not in roster and name not in _HOST_NAMES and name.lower() not in {item.lower() for item in _HOST_NAMES}:
                continue
            try:
                start, end = float(word['start']), float(word['end'])
            except (KeyError, TypeError, ValueError):
                continue
            overlap = min(cue_end, end) - max(cue_start, start)
            if overlap > 0:
                totals[name] = totals.get(name, 0.0) + overlap
    if not totals:
        return ''
    return max(totals, key=totals.get)


def _names_agree(model_name: str, evidence: str, speakers: list[dict]) -> str:
    """Show a name only when the model and the transcript name the same person.

    A blank model does not contradict a guest turn, so the single guest is shown.
    A guest name on a host turn is dropped: a wrong label is worse than none.
    """
    from backend.services.studio.packaging import _HOST_NAMES
    evidence = str(evidence or '').strip()
    model_name = str(model_name or '').strip()
    if not evidence:
        return ''

    def hostish(name: str) -> bool:
        return bool(name) and (name in _HOST_NAMES or name.lower() in {item.lower() for item in _HOST_NAMES})

    if hostish(evidence):
        return model_name if hostish(model_name) else ''
    guests = _guest_names(speakers)
    if evidence not in guests and evidence not in {person.get('name') for person in speakers}:
        return ''
    if not model_name or model_name == evidence:
        return evidence
    return ''


def _agree_speaker(model_name: str, cue_start: float, cue_end: float, transcript, speakers: list[dict], word_timing) -> str:
    """The label is the name the model and the transcript both support. Otherwise none.

    Transcript turns come from ``>>`` or from a diarized ``speaker`` on the words.
    Without either, the model's name is not shown.
    """
    from backend.services.studio.packaging import _HOST_NAMES
    diarized = _diarized_name(cue_start, cue_end, word_timing, speakers)
    if diarized:
        return _names_agree(model_name, diarized, speakers)
    turns = _turns(_transcript_rows(transcript))
    if not turns:
        return ''
    best = None
    best_len = 0.0
    for turn in turns:
        overlap = min(cue_end, turn[1]) - max(cue_start, turn[0])
        if overlap > best_len:
            best_len = overlap
            best = turn
    if best is None or best_len <= 0:
        return ''
    if best[4]:
        return _names_agree(model_name, best[4], speakers)
    host_side = _host_parity(turns)
    role_host = best[2] is not None and int(best[2]) % 2 == host_side
    if role_host:
        if model_name in _HOST_NAMES or (model_name and model_name.lower() in {item.lower() for item in _HOST_NAMES}):
            return model_name
        return ''
    guests = _guest_names(speakers)
    if len(guests) == 1 and (not model_name or model_name == guests[0]):
        return guests[0]
    if model_name in guests:
        return model_name
    return ''


def _deck_line(packaging) -> str:
    """The model's deck only. A clipped first sentence is not a deck."""
    deck = str(_get(packaging, 'deck', '') or '').strip()
    return deck[:80] if deck else ''


_CREDIT_STOP = {'on', 'the', 'a', 'an', 'of', 'about', 'and'}


def _guest_names(speakers: list[dict]) -> list[str]:
    from backend.services.studio.packaging import _HOST_NAMES
    names = []
    for person in speakers:
        name = str(person.get('name') or '').strip()
        if name and name not in _HOST_NAMES and name.lower() not in {item.lower() for item in _HOST_NAMES}:
            names.append(name)
    return names


def _title_caps(speakers: list[dict], title_lines: list[str] | None) -> str:
    """Caps from the packaging title and the guest, never from a clipped spoken sentence."""
    title = ' '.join(str(line).strip() for line in (title_lines or []) if str(line).strip())
    title = ' '.join(title.split())
    if not title:
        return ''
    guests = _guest_names(speakers)
    named = next((name for name in guests if name in title), '')
    name = named or (guests[0] if len(guests) == 1 else '')
    if name and name not in title:
        return f'{title} · {name}'
    return title


def _caps_credit(deck: str, speakers: list[dict], title_lines: list[str] | None = None) -> str:
    """TOPIC · SPEAKER under the magazine headline.

    "Jensen Huang on the five-layer cake" becomes FIVE-LAYER CAKE · JENSEN HUANG.
    A long spoken sentence is shortened to its last few words. With no deck, the line is the
    title and the guest, not that spoken sentence.
    """
    if not deck:
        return _title_caps(speakers, title_lines)
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


def _protected_token(token: str, emphasis: str) -> bool:
    """A highlight, a number or a Latin token stays whole even when it is wider than the line."""
    if emphasis and token.strip() == emphasis:
        return True
    if any(ch.isdigit() for ch in token):
        return True
    return any(ch.isascii() and ch.isalnum() for ch in token)


def _wrap_units(text: str, limit: float, emphasis: str = '') -> list[str]:
    """One line per chunk, broken between words: never 增长八|倍, 生|产力 or 每周工|作80小时.

    Fewest lines first; then no line under three characters (一项|预测 left 预测 alone for
    0.5s), no line opening with 的/了, and lines of similar length.
    """
    if width(text) <= limit + 1e-6:
        return [text]
    from backend.services.studio.cjk_segment import break_units, crosses_word
    # A highlight wider than the line cannot be one atom; a short one such as 机会 can.
    guard = emphasis if emphasis and width(emphasis) <= limit + 1e-6 else ''
    units: list[str] = []
    for unit in break_units(text, guard):
        if width(unit.strip()) > limit + 1e-6 and not _protected_token(unit, emphasis):
            units.extend(_hard_slices(unit.strip(), limit))
        elif unit.strip():
            units.append(unit)
    n = len(units)
    best: list[tuple | None] = [(0, 0.0)] + [None] * n
    back = [0] * (n + 1)
    for end in range(1, n + 1):
        for begin in range(end - 1, -1, -1):
            chunk = ''.join(units[begin:end]).strip()
            size = width(chunk)
            if size > limit + 1e-6 and end - begin > 1:
                break
            if best[begin] is None:
                continue
            penalty = (limit - size) ** 2 * 0.2
            if size < 3:
                penalty += 40
            if chunk[:1] in _LEAD:
                penalty += 30
            if begin and crosses_word(''.join(units[:begin]), ''.join(units[begin:])):
                penalty += 25
            lines, cost = best[begin]
            candidate = (lines + 1, cost + penalty)
            if best[end] is None or candidate < best[end]:
                best[end], back[end] = candidate, begin
    chunks: list[str] = []
    end = n
    while end > 0:
        chunks.append(''.join(units[back[end]:end]).strip())
        end = back[end]
    return [chunk for chunk in chunks[::-1] if chunk]


def _attach_emphasis(previous: str, piece: str, limit: float) -> list[str]:
    """Keep a highlight off its own line without blowing the line budget.

    If the previous line has room, the highlight joins it. Otherwise a few characters
    move down with it, so 「机会」 is not a phrase by itself and neither line overflows.
    """
    if width(previous + piece) <= limit + 1e-6:
        return [previous + piece]
    for take in range(1, len(previous)):
        left, right = previous[:-take], previous[-take:] + piece
        if left and width(left) <= limit + 1e-6 and width(right) <= limit + 1e-6:
            return [left, right]
    return [previous + piece]


def _merge_isolated_emphasis(pieces: list[str], emphasis: str, limit: float) -> list[str]:
    """A highlight is not its own phrase. 「机会」 stays with the words around it."""
    emphasis = str(emphasis or '').strip().strip(_PUNCT)
    if not emphasis:
        return pieces
    merged: list[str] = []
    for piece in pieces:
        if merged and piece.strip().strip(_PUNCT) == emphasis:
            merged[-1:] = _attach_emphasis(merged[-1], piece, limit)
        else:
            merged.append(piece)
    return merged


def _no_leading_particle(pieces: list[str]) -> list[str]:
    """Don't start a line with 的/了/吗. The particle stays on the previous line."""
    fixed: list[str] = []
    for piece in pieces:
        if fixed and piece and piece[0] in _LEAD:
            take = 0
            while take < len(piece) and piece[take] in _LEAD:
                take += 1
            fixed[-1] += piece[:take]
            rest = piece[take:]
            if rest:
                fixed.append(rest)
            continue
        fixed.append(piece)
    return [piece for piece in fixed if piece]


def _phrases(text: str, limit: float, emphasis: str = '') -> list[str]:
    """Short single-line pieces. Trailing punctuation is dropped, the same way the preview does."""
    cleaned = str(text or '').strip().strip(_PUNCT).strip()
    if not cleaned:
        return []
    parts = [part.strip() for part in re.split(r'[，。、！？：；,.!?]+', cleaned) if part.strip()]
    pieces: list[str] = []
    for part in parts:
        pieces.extend(_wrap_units(part, limit, emphasis))
    pieces = _no_leading_particle(_merge_isolated_emphasis(pieces, emphasis, limit))
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


def _hold_phrases(placed: list[tuple], line_limit: float | None = None) -> list[tuple]:
    """A phrase under about 0.6s joins a neighbour on the same side of a cut.

    80小时 and 15小时 were on screen for 0.37s. Join only when the combined line still
    fits; otherwise the phrase borrows time from a touching neighbour. Merging across a
    removed gap would replay the line on the next shot.
    """
    def fits(left: str, right: str) -> bool:
        if not line_limit:
            return True
        return width(left + right) <= float(line_limit) + 1e-6

    items = list(placed)
    skipped: set[int] = set()
    guard = 0
    while guard < 32:
        guard += 1
        short = next((index for index, item in enumerate(items)
                      if index not in skipped and item[2] - item[1] < _MIN_PHRASE_SEC - 1e-3), None)
        if short is None:
            break
        item = items[short]
        prev = items[short - 1] if short else None
        nxt = items[short + 1] if short + 1 < len(items) else None
        if prev is not None and prev[2] >= item[1] - 0.05 and fits(prev[0], item[0]):
            items[short - 1] = (prev[0] + item[0], prev[1], max(prev[2], item[2]), prev[3], max(prev[4], item[4]))
            del items[short]
            skipped.clear()
            continue
        if nxt is not None and item[2] >= nxt[1] - 0.05 and fits(item[0], nxt[0]):
            items[short + 1] = (item[0] + nxt[0], item[1], max(item[2], nxt[2]), item[3], max(item[4], nxt[4]))
            del items[short]
            skipped.clear()
            continue
        if not _borrow_time(items, short):
            skipped.add(short)
    return items


def _borrow_time(items: list[tuple], short: int) -> bool:
    """A short phrase that cannot share a line takes time from a touching neighbour.

    Both keep at least 0.6s; time never crosses a cut, because only touching phrases trade.
    """
    item = items[short]
    fps = next((it[3] / it[1] for it in items if it[1] > 0 and it[3] > 0), 30.0)
    need = max(1, round(_MIN_PHRASE_SEC * fps)) - (item[4] - item[3])
    keep = round(_MIN_PHRASE_SEC * fps)
    for side in (1, -1):
        index = short + side
        if not 0 <= index < len(items):
            continue
        other = items[index]
        touching = other[3] == item[4] if side == 1 else other[4] == item[3]
        spare = (other[4] - other[3]) - keep
        if not touching or spare <= 0:
            continue
        take = min(need, spare)
        if side == 1:
            cut = item[4] + take
            items[short] = (item[0], item[1], cut / fps, item[3], cut)
            items[index] = (other[0], cut / fps, other[2], cut, other[4])
        else:
            cut = item[3] - take
            items[short] = (item[0], cut / fps, item[2], cut, item[4])
            items[index] = (other[0], other[1], cut / fps, other[3], cut)
        need -= take
        if need <= 0:
            return True
    return False


def cue_lines(cue_start: float, cue_end: float, rows: list[tuple], scenes) -> list[tuple] | None:
    """The subtitle lines a packaged cue was built from, as (src lo, src hi, out lo, out hi, text).

    Packaging groups consecutive draft lines (``packaging.draft_lines``: rows clipped to each
    scene, in timeline order) and stamps the cue with the first line's start and the last
    line's end. A cue across a cold open can therefore run backwards in source time
    (1245.78 -> 1236.22). Rebuilding the lines the same way recovers the real spoken parts.
    None when the rows do not reproduce the cue's bounds.
    """
    if not rows or not scenes:
        return None
    from backend.services.studio.audio import scene_duration
    from backend.services.studio.packaging_render import timeline
    lines = []
    for scene, (src_start, src_end, offset) in zip(scenes, timeline(scenes)):
        src_start, src_end = float(src_start), float(src_end)
        length = scene_duration(scene)
        for start, end, text, _speaker in rows:
            if end <= src_start or start >= src_end:
                continue
            lo, hi = max(start, src_start), min(end, src_end)
            if hi - lo < min(.15, (end - start) * .2):
                continue
            out_lo = offset + lo - src_start
            out_hi = min(offset + length, offset + hi - src_start)
            if out_hi > out_lo:
                lines.append((lo, hi, out_lo, out_hi, text))
    cue_start, cue_end = float(cue_start or 0), float(cue_end or 0)
    for first, line in enumerate(lines):
        if abs(line[0] - cue_start) > .05:
            continue
        for last in range(first, min(len(lines), first + 40)):
            if abs(lines[last][1] - cue_end) <= .05:
                return lines[first:last + 1]
    return None


def _clock_rough(pieces: list[str], lines: list[tuple]) -> list[tuple]:
    """Split the pieces over the lines by text length, then map each into its line's kept time.

    The translation follows the source line by line, so a piece's share of the Chinese text
    lands on the same share of the source text: 我完全不同意 stays on "I completely disagree."
    Lines get their own length of the clock, so silence and cuts between lines take no text.
    A piece that straddles two lines goes to the line holding most of it.
    """
    weights = [max(1, len(' '.join(str(line[4] or '').split()))) for line in lines]
    clock = []
    cursor = 0.0
    for line, weight in zip(lines, weights):
        clock.append((cursor, cursor + weight, line[2], line[3]))
        cursor += weight
    rough = []
    for piece, c0, c1 in _length_bounds(pieces, 0.0, cursor):
        best = None
        best_len = 0.0
        for k0, k1, out_lo, out_hi in clock:
            ov0, ov1 = max(c0, k0), min(c1, k1)
            if ov1 - ov0 > best_len + 1e-6:
                best_len = ov1 - ov0
                scale = (out_hi - out_lo) / (k1 - k0)
                best = (piece, out_lo + (ov0 - k0) * scale, out_lo + (ov1 - k0) * scale)
        if best is None:
            _k0, _k1, out_lo, out_hi = clock[-1]
            best = (piece, max(out_lo, out_hi - .05), out_hi)
        rough.append(best)
    return rough


def _place_on_lines(pieces: list[str], lines: list[tuple], total: int, fps: int, source_words, line_limit: float | None) -> list[tuple]:
    """Every piece once, on the kept footage where its line is spoken."""
    rough = None
    aligned = _align_phrase_times(pieces, source_words, min(l[0] for l in lines), max(l[1] for l in lines)) if source_words else None
    if aligned:
        mapped = []
        for piece, t0, t1 in aligned:
            best = None
            best_len = 0.0
            for lo, hi, out_lo, out_hi, _text in lines:
                ov0, ov1 = max(t0, lo), min(t1, hi)
                if ov1 - ov0 > best_len + 1e-6:
                    best_len = ov1 - ov0
                    scale = (out_hi - out_lo) / max(hi - lo, 1e-6)
                    best = (piece, out_lo + (ov0 - lo) * scale, out_lo + (ov1 - lo) * scale)
            if best is None:
                mapped = None
                break
            mapped.append(best)
        if mapped and all(b[1] >= a[1] for a, b in zip(mapped, mapped[1:])):
            rough = mapped
    if rough is None:
        rough = _clock_rough(pieces, lines)
    placed = _place_rough(rough, total, fps, None)
    if len(placed) < len(rough):
        # Frame rounding pushed a piece past its end. Retile the run so none is lost.
        first, last = _frames(rough[0][1], fps), min(total, max(_frames(rough[-1][2], fps), _frames(rough[0][1], fps) + len(rough)))
        counts = _frame_counts(max(1, last - first), [max(width(piece), 1) for piece, _a, _b in rough])
        placed, cursor = [], first
        for (piece, _a, _b), count in zip(rough, counts):
            if count <= 0 or cursor >= total:
                continue
            placed.append((piece, cursor / fps, (cursor + count) / fps, cursor, cursor + count))
            cursor += count
    return _hold_phrases(placed, line_limit)


def _once_per_clip(pieces: list[str], cue_start: float, cue_end: float, scenes, total: int, fps: int, source_words, line_limit: float | None = None, lines: list[tuple] | None = None) -> list[tuple]:
    """Place each phrase on the output clock once, at the moment it is spoken.

    A cue that crosses a cut used to restart its whole phrase list inside every shot.
    Phrases are timed across the cue, then mapped through the shots. A phrase the cut
    removes entirely is dropped. A phrase the cut splits is kept on the shot that holds
    most of it, so a sliver at the end of the first shot does not eat the line.
    One shot that contains the whole cue keeps the old frame tiling, so a single scene
    still meets the caption page exactly.
    """
    spans = _kept_spans(cue_start, cue_end, scenes)
    whole = bool(spans) and len(spans) == 1 and abs(spans[0][0] - cue_start) <= 1e-3 and abs(spans[0][1] - cue_end) <= 1e-3
    if lines and not whole:
        # The cue's own subtitle lines, in timeline order and on kept footage only. The span
        # [cue_start, cue_end] also covers removed source time and other shots (a cold open),
        # and a length split over it dropped phrases that were spoken in a kept shot.
        return _place_on_lines(pieces, lines, total, fps, source_words, line_limit)
    if not spans:
        return []
    src_lo, src_hi, out_lo, out_hi = spans[0]
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
        return _hold_phrases(placed, line_limit)
    bounds = aligned or _length_bounds(pieces, cue_start, cue_end)
    rough = []
    for piece, t0, t1 in bounds:
        best = None
        best_len = 0.0
        for span_lo, span_hi, span_out, span_end in spans:
            ov0, ov1 = max(t0, span_lo), min(t1, span_hi)
            if ov1 <= ov0 + 1e-4:
                continue
            length = ov1 - ov0
            if length <= best_len:
                continue
            best_len = length
            scale = (span_end - span_out) / max(span_hi - span_lo, 1e-6)
            best = (piece, span_out + (ov0 - span_lo) * scale, span_out + (ov1 - span_lo) * scale)
        if best:
            rough.append(best)
    return _place_rough(rough, total, fps, line_limit)


def _place_rough(rough: list[tuple], total: int, fps: int, line_limit: float | None) -> list[tuple]:
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
    return _hold_phrases(placed, line_limit)


def build_fill(packaging, duration: float, fps: int = 30, safe_area: str = 'xiaohongshu', scenes=None, template: str | None = None, word_timing=None, transcript=None) -> dict:
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
    rows = _transcript_rows(transcript)
    for cue in cues:
        text = str(_get(cue, 'text', '')).strip()
        if not text:
            continue
        phrase = _cue_phrase(cue, text, emphasis)
        raw_original = str(_get(cue, 'original', '') or '')
        # The preview keeps the whole English sentence on one line and shrinks it. The template trims what still overflows.
        original = ' '.join(raw_original.split()) if (template or '') in {'editorial', 'street'} else _source_line(raw_original, source_limit)
        speaker = _agree_speaker(
            _cue_speaker_name(cue, roster, packaging),
            float(_get(cue, 'start', 0) or 0), float(_get(cue, 'end', 0) or 0),
            transcript, roster, word_timing,
        )
        pieces = _phrases(text, phrase_limit, phrase)
        if not pieces:
            continue
        timed = _timed_in_cue(cue, word_timing, scenes)
        cue_start, cue_end = float(_get(cue, 'start', 0) or 0), float(_get(cue, 'end', 0) or 0)
        spoken = _once_per_clip(
            pieces, cue_start, cue_end,
            scenes, total, fps, _source_words(cue, word_timing), phrase_limit,
            lines=cue_lines(cue_start, cue_end, rows, scenes) if rows else None,
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
            ]
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

    `build_fill` always keeps `title_lines` and the hook text. Street and editorial paint that
    title in their own safe zone (the black lower band, or the magazine headline under the face).
    The classic top title is not burned on top of either. Captions-on returns the same dict.
    A caller that does not name an HTML template still clears the painted hook.
    """
    if _get(packaging, 'captions_enabled', True) is not False:
        return fill
    if template in {'street', 'editorial'}:
        return fill
    hook = dict(fill.get('hook') or {})
    hook['text'] = ''
    return {**fill, 'hook': hook, 'hook_lines': [], 'title_lines': [], 'kicker': '', 'deck': '', 'hook_trk': '', 'credit': ''}
