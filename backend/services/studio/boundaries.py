"""Snap clip boundaries so a clip never starts or ends in the middle of a sentence or a thought.

ASR subtitle rows are often half sentences, and the content pipeline picks clips on row edges,
so clips ended on "It seems like" or "having this". Two passes:

1. `sentence_bounds` (always, no model): cut inside a row at its sentence end when the row holds
   one ("...responsible. It seems like" ends after "responsible."), otherwise extend to the row
   that finishes the sentence; start at the first full sentence the same way. Pauses count as
   sentence ends only when the transcript has no punctuation (e.g. Japanese ASR). A trailing
   question is dropped: it is the next topic, not this answer.
2. `refine_with_model` (when a text model is available): show the rows around both cuts and let
   the model pick where the question starts and where the answer is finished. Every choice is
   validated and snapped by pass 1; anything implausible keeps pass 1.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

TERMINAL = re.compile(r'[.?!。？！…」』"”]\s*$')
INNER_END = re.compile(r'[.?!。？！…]+["”」』]?(?=\s|$)|[。？！]')
PUNCT = re.compile(r'[.,?!。，？！、]')
QUESTION = re.compile(r'(\?|？|ですか|ますか|でしょうか|吗|呢)["”」』]?\s*$')
# Japanese ASR has no punctuation: polite sentence-final forms still mark a finished sentence.
JA_END = re.compile(r'(です|ます|ました|でした|ございます|ません|でしょう|ですね|ますね|ですよ|ますよ)\s*$')
TRAILING_QUESTION_SEC = 20  # look this far back from the end for the next topic's question
ANSWER_STUB_SEC = 12        # an answer shorter than this after the question is the next topic's opening
PAUSE_SEC = 0.6
MAX_LEAD_SEC = 12      # how far a start may move back to reach its sentence start
MAX_TAIL_SEC = 25      # how far an end may move forward to finish its sentence
CONTEXT_BEFORE, CONTEXT_AFTER = 40, 75
MODEL_MAX_EXTEND = 60  # the model may extend the end by at most this much


Row = tuple[float, float, str]


def rows_from_entries(entries) -> list[Row]:
    from backend.pipeline.quality import to_seconds
    rows = []
    for entry in entries:
        try:
            rows.append((to_seconds(entry['start_time']), to_seconds(entry['end_time']), str(entry.get('text') or '').strip()))
        except (KeyError, ValueError):
            continue
    return sorted(r for r in rows if r[2])


def punctuated(rows: list[Row]) -> bool:
    return bool(rows) and sum(bool(PUNCT.search(r[2])) for r in rows) >= len(rows) * 0.3


def ends_sentence(rows: list[Row], index: int, has_punct: bool | None = None) -> bool:
    text = rows[index][2]
    if TERMINAL.search(text) or (JA_END.search(text) and not QUESTION.search(text)):
        return True
    if has_punct is None:
        has_punct = punctuated(rows)
    if has_punct:
        return index + 1 >= len(rows)
    return index + 1 >= len(rows) or rows[index + 1][0] - rows[index][1] >= PAUSE_SEC


def _inner_ends(text: str) -> list[int]:
    """Character offsets just after each sentence end inside `text` (not at its very end)."""
    return [m.end() for m in INNER_END.finditer(text) if text[m.end():].strip()]


def _time_at(row: Row, offset: int) -> float:
    s, e, text = row
    return s + (e - s) * offset / max(len(text), 1)


def _index_at(rows: list[Row], t: float) -> int | None:
    for i, (s, e, _) in enumerate(rows):
        if s <= t < e or (i + 1 < len(rows) and e <= t < rows[i + 1][0]):
            return i
    return None


def _end_cut(rows: list[Row], last: int, end: float, has_punct: bool) -> tuple[int, int]:
    """(row index, char offset) where the sentence running through `end` finishes."""
    i = last
    while True:
        text = rows[i][2]
        if ends_sentence(rows, i, has_punct):
            return i, len(text)
        inner = _inner_ends(text)
        if inner:
            return i, inner[-1]
        if i + 1 < len(rows) and rows[i + 1][1] - end <= MAX_TAIL_SEC:
            i += 1
            continue
        return i, len(text)


def _drop_trailing_question(rows: list[Row], i: int, offset: int, first: int, has_punct: bool, end_time: float) -> tuple[int, int]:
    """End before the next topic: a question near the end followed by only the opening of its answer."""
    for j in range(i, first, -1):
        if rows[j][1] < end_time - TRAILING_QUESTION_SEC:
            break
        text = rows[j][2][:offset] if j == i else rows[j][2]
        if QUESTION.search(text.rstrip()):
            q_off = len(text.rstrip())
        else:
            marks = [m.end() for m in re.finditer(r'[?？]', text)]
            if not marks:
                continue
            q_off = marks[-1]
        if end_time - _time_at(rows[j], q_off) > ANSWER_STUB_SEC:
            break  # a real answer follows the question: keep it
        inner = _inner_ends(text[:q_off])
        if inner:
            return j, inner[-1]
        k = j - 1
        while k > first:
            if ends_sentence(rows, k, has_punct):
                return k, len(rows[k][2])
            inner = _inner_ends(rows[k][2])
            if inner:
                return k, inner[-1]
            k -= 1
        break
    return i, offset


def _start_cut(rows: list[Row], first: int, start: float, has_punct: bool) -> tuple[int, int]:
    """(row index, char offset) of the first full sentence at or before `start`."""
    if first == 0 or ends_sentence(rows, first - 1, has_punct):
        return first, 0
    inner = _inner_ends(rows[first][2])
    if inner:  # the row starts with the tail of the previous sentence: begin at the next one
        text = rows[first][2]
        offset = inner[0]
        while offset < len(text) and text[offset] == ' ':
            offset += 1
        return first, offset
    i = first
    while i > 0 and start - rows[i - 1][0] <= MAX_LEAD_SEC:
        i -= 1
        if i == 0 or ends_sentence(rows, i - 1, has_punct):
            return i, 0
        inner = _inner_ends(rows[i][2])
        if inner:
            return i, inner[-1] + (1 if rows[i][2][inner[-1]:inner[-1] + 1] == ' ' else 0)
    return first, 0


def sentence_bounds(rows: list[Row], start: float, end: float) -> tuple[float, float]:
    """(start, end) on complete sentences, within MAX_LEAD_SEC / MAX_TAIL_SEC."""
    if not rows:
        return start, end
    first = _index_at(rows, start + 0.05)
    if first is None:
        first = next((i for i, r in enumerate(rows) if r[0] >= start), None)
    last = _index_at(rows, end - 0.05)
    if first is None or last is None or last < first:
        return start, end
    has_punct = punctuated(rows)
    s_row, s_off = _start_cut(rows, first, start, has_punct)
    e_row, e_off = _end_cut(rows, last, end, has_punct)
    cut_end = rows[e_row][1] if e_off >= len(rows[e_row][2]) else _time_at(rows[e_row], e_off)
    q_row, q_off = _drop_trailing_question(rows, e_row, e_off, s_row, has_punct, cut_end)
    q_end = rows[q_row][1] if q_off >= len(rows[q_row][2]) else _time_at(rows[q_row], q_off)
    if q_end - (rows[s_row][0]) >= (end - start) * 0.6:  # never gut the clip to drop a question
        e_row, e_off = q_row, q_off
    new_start = rows[s_row][0] if s_off == 0 else _time_at(rows[s_row], s_off)
    if e_off >= len(rows[e_row][2]):
        # A short tail keeps the last word from being clipped, without running into the next row.
        nxt = rows[e_row + 1][0] if e_row + 1 < len(rows) else rows[e_row][1] + 0.4
        new_end = max(rows[e_row][1], min(rows[e_row][1] + 0.4, nxt))
    else:
        new_end = _time_at(rows[e_row], e_off) + 0.25
    if new_end - new_start < 1:
        return start, end
    return round(new_start, 3), round(new_end, 3)


BOUNDARY_PROMPT = (
    '你是访谈剪辑师。lines 是一段访谈的原字幕（已按时间排序，常被切成半句），start_line 与 end_line 是当前片段的首尾行。'
    '请调整首尾，让片段从一个完整问题或观点的开头开始，到这个回答或观点真正讲完才结束：'
    '不能停在半句话，不能在对方刚开始回答时结束，也不能以主持人抛出的下一个问题结尾。'
    '可以向前或向后移动，但不要合并下一个话题。返回 JSON：{"start_line":0,"end_line":0,"reason":"..."}。'
)


def refine_with_model(rows: list[Row], start: float, end: float, call: Callable[[str, dict], dict]) -> tuple[float, float] | None:
    window = [(i, r) for i, r in enumerate(rows) if start - CONTEXT_BEFORE <= r[0] <= end + CONTEXT_AFTER]
    if len(window) < 3:
        return None
    ids = {i: n for n, (i, _) in enumerate(window)}
    first, last = _index_at(rows, start + 0.05), _index_at(rows, end - 0.05)
    if first not in ids or last not in ids:
        return None
    result = call(BOUNDARY_PROMPT, {'lines': [{'id': n, 'text': r[2]} for n, (_, r) in enumerate(window)],
                                    'start_line': ids[first], 'end_line': ids[last]})
    s_id, e_id = (result or {}).get('start_line'), (result or {}).get('end_line')
    if not (isinstance(s_id, int) and isinstance(e_id, int) and 0 <= s_id <= e_id < len(window)):
        return None
    new_start, new_end = window[s_id][1][0], window[e_id][1][1]
    length, original = new_end - new_start, end - start
    # Reject drastic rewrites: the model should adjust edges, not pick a different clip.
    if new_end > end + MODEL_MAX_EXTEND or new_start < start - CONTEXT_BEFORE or length < original * 0.6 or length > original + MODEL_MAX_EXTEND + 15:
        return None
    return sentence_bounds(rows, new_start, new_end)


def refine_clips(rows: list[Row], clips: list[tuple[float, float]], call: Callable[[str, dict], dict] | None = None) -> list[tuple[float, float]]:
    """Sentence-snapped bounds for every clip; model-refined where the model gives a valid answer."""
    snapped = [sentence_bounds(rows, s, e) for s, e in clips]
    if call is None or not rows:
        return snapped

    def one(pair):
        (s, e), fallback = pair
        try:
            return refine_with_model(rows, s, e, call) or fallback
        except Exception as error:  # noqa: BLE001 - boundary polish never blocks output
            logger.warning('Boundary refinement fell back: %s', type(error).__name__)
            return fallback

    with ThreadPoolExecutor(max_workers=4, thread_name_prefix='studio-bounds') as pool:
        return list(pool.map(one, zip(clips, snapped)))
