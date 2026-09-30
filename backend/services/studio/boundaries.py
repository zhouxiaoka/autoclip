"""Snap clip boundaries so a clip never starts or ends in the middle of a sentence or a thought.

ASR subtitle rows are often half sentences, and the content pipeline picks clips on row edges,
so clips ended on "It seems like" or "having this". Two passes:

1. `sentence_bounds` (always, no model): move the start back to the beginning of its sentence and
   the end forward until the sentence is finished. A row ends a sentence when it ends with
   terminal punctuation or is followed by a clear pause (languages whose ASR has no punctuation).
2. `refine_with_model` (when a text model is available): show the rows around both cuts and let
   the model pick where the question starts and where the answer is finished. Every choice is
   validated; anything implausible keeps pass 1.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

TERMINAL = re.compile(r'[.?!。？！…」』"”]\s*$')
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


def ends_sentence(rows: list[Row], index: int) -> bool:
    if TERMINAL.search(rows[index][2]):
        return True
    return index + 1 >= len(rows) or rows[index + 1][0] - rows[index][1] >= PAUSE_SEC


def _index_at(rows: list[Row], t: float) -> int | None:
    for i, (s, e, _) in enumerate(rows):
        if s <= t < e or (i + 1 < len(rows) and e <= t < rows[i + 1][0]):
            return i
    return None


def sentence_bounds(rows: list[Row], start: float, end: float) -> tuple[float, float]:
    """(start, end) moved to sentence edges, within MAX_LEAD_SEC / MAX_TAIL_SEC."""
    if not rows:
        return start, end
    first = _index_at(rows, start + 0.05)
    if first is None:
        first = next((i for i, r in enumerate(rows) if r[0] >= start), None)
    last = _index_at(rows, end - 0.05)
    if first is None or last is None or last < first:
        return start, end
    while first > 0 and not ends_sentence(rows, first - 1) and start - rows[first - 1][0] <= MAX_LEAD_SEC:
        first -= 1
    while not ends_sentence(rows, last) and last + 1 < len(rows) and rows[last + 1][1] - end <= MAX_TAIL_SEC:
        last += 1
    new_start = min(start, rows[first][0])
    # A short tail keeps the last word from being clipped, without running into the next row.
    tail = rows[last + 1][0] if last + 1 < len(rows) else rows[last][1] + 0.4
    new_end = max(rows[last][1], min(rows[last][1] + 0.4, tail))
    return round(new_start, 3), round(new_end, 3)


BOUNDARY_PROMPT = (
    '你是访谈剪辑师。lines 是一段访谈的原字幕（已按时间排序，常被切成半句），start_line 与 end_line 是当前片段的首尾行。'
    '请调整首尾，让片段从一个完整问题或观点的开头开始，到这个回答或观点真正讲完才结束：'
    '不能停在半句话，也不能在对方刚开始回答、或刚抛出新问题时结束。'
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
