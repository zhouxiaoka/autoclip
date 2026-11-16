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
   validated against eligible endings; audio only aligns inside that chosen ending.
   Anything implausible keeps pass 1, with a review flag when no ending was found.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from backend.core.job_budget import JobDurationExceeded
from backend.core.project_cancellation import JobStopped, ProjectDeleted, ServiceRestarted

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
MAX_LEAD_SEC = 20      # how far a start may move back to reach its sentence start (a question's opening)
MAX_TAIL_SEC = 25      # how far an end may move forward to finish its sentence
CONTEXT_BEFORE, CONTEXT_AFTER = 40, 75
MODEL_MAX_EXTEND = 25  # finish this sentence; a long new answer needs editorial review


Row = tuple[float, float, str]


class ClipBounds(tuple):
    """Keep the existing (start, end) API while carrying an unresolved-ending warning."""
    def __new__(cls, start, end, *, needs_review=False):
        value = super().__new__(cls, (start, end))
        value.needs_review = needs_review
        return value


_DANGLING = re.compile(
    r'\b(?:because|although|unless|whether|which|who|whose|and|or|but|if|when|while|'
    r'the|a|an|of|to|for|with|without|from|in|at|than|such as|seems like|which is like|'
    r'um|uh)\s*[,.!?…]*$', re.I)


def unfinished(text: str) -> bool:
    """A breath or ASR punctuation cannot complete an explicit connective/half-clause."""
    text = text.strip()
    copula = re.search(r'\b(?:is|are|was|were|be|being|been)\s*[,;:]?$', text, re.I)
    return bool(_DANGLING.search(text) or copula or re.fullmatch(r'(?:I|we|you|they)[,.!?…]*', text, re.I))


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
    if unfinished(text):
        return False
    if index + 1 < len(rows) and rows[index + 1][2].lstrip().startswith('>>'):
        return True  # an explicit speaker turn ends even an unpunctuated ASR answer
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


def _end_cut(rows: list[Row], last: int, end: float, has_punct: bool) -> tuple[int, int] | None:
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
        # Search exhaustion is not evidence that the last visited row finished a sentence.
        # Prefer a known earlier ending; the caller rejects a retreat that would gut the clip.
        for j in range(last, -1, -1):
            if end - rows[j][1] > MAX_TAIL_SEC:
                break
            inner = _inner_ends(rows[j][2])
            if inner:
                return j, inner[-1]
            if ends_sentence(rows, j, has_punct):
                return j, len(rows[j][2])
        return None


def _drop_trailing_question(rows: list[Row], i: int, offset: int, first: int, has_punct: bool, end_time: float) -> tuple[int, int]:
    """End before the next topic: a question near the end followed by only the opening of its answer."""
    # A host often introduces the next question with declarative sentences. Looking only
    # for a question mark near the selected end leaves that unfinished introduction behind.
    for j in range(i, first, -1):
        if rows[j][0] < end_time - TRAILING_QUESTION_SEC:
            break
        if not rows[j][2].lstrip().startswith('>>'):
            continue
        turn = []
        for k in range(j, len(rows)):
            if rows[k][0] > end_time + MAX_TAIL_SEC or (k > j and rows[k][2].lstrip().startswith('>>')):
                break
            turn.append(rows[k])
        questions = [r for r in turn if QUESTION.search(r[2]) or re.search(r'[?？]', r[2])]
        if questions and end_time - questions[-1][1] <= ANSWER_STUB_SEC:
            return j - 1, len(rows[j - 1][2])
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
    while i > 0 and start - rows[i - 1][1] <= MAX_LEAD_SEC:
        i -= 1
        inner = _inner_ends(rows[i][2])
        if not inner and (i == 0 or ends_sentence(rows, i - 1, has_punct)):
            return (i, 0) if start - rows[i][0] <= MAX_LEAD_SEC else (first, 0)
        if inner:
            offset = inner[-1] + (1 if rows[i][2][inner[-1]:inner[-1] + 1] == ' ' else 0)
            return (i, offset) if start - _time_at(rows[i], offset) <= MAX_LEAD_SEC else (first, 0)
    return first, 0


def sentence_bounds(rows: list[Row], start: float, end: float, silences: 'SilenceFinder | None' = None) -> tuple[float, float]:
    """(start, end) on complete sentences, within MAX_LEAD_SEC / MAX_TAIL_SEC.

    With `silences`, both cuts snap to real pauses in the audio: subtitle rows carry no word
    timing, so a cut estimated inside a row can be a few hundred ms into the next sentence.
    """
    if not rows:
        return ClipBounds(start, end, needs_review=True)
    first = _index_at(rows, start + 0.05)
    if first is None:
        first = next((i for i, r in enumerate(rows) if r[0] >= start), None)
    last = _index_at(rows, end - 0.05)
    if first is None or last is None or last < first:
        return ClipBounds(start, end, needs_review=True)
    has_punct = punctuated(rows)
    s_row, s_off = _start_cut(rows, first, start, has_punct)
    ending = _end_cut(rows, last, end, has_punct)
    if ending is None:
        return ClipBounds(start, end, needs_review=True)
    e_row, e_off = ending
    cut_end = rows[e_row][1] if e_off >= len(rows[e_row][2]) else _time_at(rows[e_row], e_off)
    if cut_end - rows[s_row][0] < max(1, (end - start) * .6):
        return ClipBounds(start, end, needs_review=True)
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
        return ClipBounds(start, end, needs_review=True)
    if silences is not None:
        min_end = new_start + (end - start) * 0.6
        estimate = rows[e_row][1] if e_off >= len(rows[e_row][2]) else _time_at(rows[e_row], e_off)
        new_end = _snap_end(rows, e_row, e_off, estimate, min_end, silences) or new_end
        new_start = _snap_start(new_start, silences, inner=s_off > 0)
    return ClipBounds(round(new_start, 3), round(new_end, 3))


SilenceFinder = Callable[[float, float], list[tuple[float, float]]]
MATCH_SEC = 1.3          # a sentence end estimated inside a row may be off by this much either way
MIN_CHAR_SEC = 0.03      # speech takes at least this long per character (bounds an estimate's drift)
BREATH_SEC = 0.5         # a pause this long is a clear breath between statements


def _cut_window(rows: list[Row], row: int, offset: int, estimate: float) -> tuple[float, float]:
    """Where the pause after this cut can really be: text before the cut is spoken before it, text after after it."""
    s, e, text = rows[row]
    if offset >= len(text):
        nxt = rows[row + 1][0] if row + 1 < len(rows) else e + 0.9
        return e - 0.4, max(e, nxt)
    before, after = len(text[:offset].replace(' ', '')), len(text[offset:].replace(' ', ''))
    return max(s + before * MIN_CHAR_SEC, estimate - MATCH_SEC), min(e - after * MIN_CHAR_SEC, estimate + MATCH_SEC)


def _pause_in(gaps, lo: float, hi: float, near: float, min_sec: float = 0.0):
    fit = [(s, e) for s, e in gaps if lo <= s <= hi and e - s >= min_sec]
    return min(fit, key=lambda g: (g[1] - g[0] < BREATH_SEC, abs(g[0] - near))) if fit else None


def _snap_end(rows: list[Row], row: int, offset: int, estimate: float, min_end: float, silences: SilenceFinder) -> float | None:
    """Align within the chosen semantic ending. A later breath cannot select another sentence."""
    lo, hi = _cut_window(rows, row, offset, estimate)
    gaps = [g for g in silences(lo, hi + .5) if g[0] >= min_end]
    pause = _pause_in(gaps, lo, hi, estimate)
    if pause is None:
        return None
    return min(hi, pause[0] + min(0.3, (pause[1] - pause[0]) / 2))


def _snap_start(estimate: float, silences: SilenceFinder, *, inner: bool) -> float:
    """Start at the end of the pause just before the first word, so no tail of the previous line leaks in.

    A row start is close (ASR may include a little leading silence): never move it into the first words.
    """
    ahead = 0.8 if inner else 0.35
    gaps = [g for g in silences(estimate - 1.5, estimate + 1.0) if estimate - 1.2 <= g[1] <= estimate + ahead]
    if not gaps:
        return estimate
    s, e = min(gaps, key=lambda g: abs(g[1] - estimate))
    return max(s, e - min(0.12, (e - s) / 2))


def audio_silences(video, noise_db: int = -32, min_sec: float = 0.2) -> SilenceFinder:
    """Silence intervals (absolute seconds) in a window of the source audio, via ffmpeg silencedetect."""
    import subprocess
    from backend.services import render_limits
    from backend.utils.ffmpeg_utils import get_ffmpeg_path

    def find(lo: float, hi: float) -> list[tuple[float, float]]:
        lo = max(0.0, lo)
        cmd = [get_ffmpeg_path(), '-hide_banner', '-nostats', *render_limits.input_args(), '-ss', f'{lo:.3f}', '-t', f'{max(0.5, hi - lo):.3f}',
               '-i', str(video), '-vn', '-af', f'silencedetect=noise={noise_db}dB:d={min_sec}', '-f', 'null', '-']
        cmd, priority = render_limits.low_priority(cmd)
        try:
            log = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                                 errors='replace', timeout=60, check=False, **priority).stderr
        except (OSError, subprocess.SubprocessError):
            return []
        # Pause detection is optional. Reader failures must keep text-based cuts usable.
        # Explicit UTF-8 also avoids Windows locale decoding failures in pipe readers.
        if isinstance(log, (bytes, bytearray)):
            log = log.decode('utf-8', errors='replace')
        if not isinstance(log, str):
            return []
        out, begin = [], None
        for line in log.splitlines():
            if 'silence_start:' in line:
                begin = lo + float(line.split('silence_start:')[1].split()[0])
            elif 'silence_end:' in line and begin is not None:
                out.append((begin, lo + float(line.split('silence_end:')[1].split('|')[0])))
                begin = None
        return out

    return find


BOUNDARY_PROMPT = (
    '你是访谈剪辑师。lines 是当前片尾附近的原字幕，end_line 是当前结尾。只调整结尾。'
    '先找当前观点最后讲完的位置：若当前末尾已进入新话题或主持人插话，必须退回上一个完整回答的末尾；'
    '只有原回答的最后一句尚未讲完时才向后延长，不能为了追求较晚的结束位置吞入下一话题。'
    'end_candidates 是允许选择的行号。不能停在半句话、回答刚开始、下一个问题或其引入语之后。'
    '字幕没有句号也要根据前后语义判断；because/who 等引导词后的停顿不是说完。'
    '如果没有合适的候选，返回 {"needs_review":true}，不要强选。'
    '只返回 JSON：{"end_line":允许结束的行号}。'
)


def refine_with_model(rows: list[Row], start: float, end: float, call: Callable[[str, dict], dict], silences: SilenceFinder | None = None) -> tuple[float, float] | None:
    window = [(i, r) for i, r in enumerate(rows) if end - MAX_TAIL_SEC - 20 <= r[0] <= end + CONTEXT_AFTER]
    if len(window) < 3:
        return None
    ids = {i: n for n, (i, _) in enumerate(window)}
    first, last = _index_at(rows, start + 0.05), _index_at(rows, end - 0.05)
    if first is None or last not in ids:
        return None
    candidates = [n for n, (_, r) in enumerate(window)
                  if end - MAX_TAIL_SEC <= r[1] <= end + MODEL_MAX_EXTEND
                  and not unfinished(r[2]) and not QUESTION.search(r[2])]
    if not candidates:
        return None
    result = call(BOUNDARY_PROMPT, {'lines': [{'id': n, 'text': r[2]} for n, (_, r) in enumerate(window)],
                                    'end_line': ids[last], 'end_candidates': candidates})
    if not isinstance(result, dict) or result.get('needs_review'):
        return None
    s_id, e_id = (result or {}).get('start_line'), (result or {}).get('end_line')
    if not (type(e_id) is int and e_id in candidates):
        return None
    if 'start_line' in result and not (type(s_id) is int and 0 <= s_id <= e_id):
        return None
    start_row = first if s_id is None else window[s_id][0]
    new_start, new_end = rows[start_row][0], window[e_id][1][1]
    length, original = new_end - new_start, end - start
    # Reject drastic rewrites: the model should adjust edges, not pick a different clip.
    if new_end > end + MODEL_MAX_EXTEND or new_start < start - CONTEXT_BEFORE or length < original * 0.6 or length > original + MODEL_MAX_EXTEND + 15:
        return None
    # The model chose the completed thought. Do not run forward sentence search over it again.
    s_row, s_off = _start_cut(rows, start_row, new_start, punctuated(rows))
    new_start = rows[s_row][0] if s_off == 0 else _time_at(rows[s_row], s_off)
    e_row = window[e_id][0]
    nxt = rows[e_row + 1][0] if e_row + 1 < len(rows) else new_end + .4
    aligned_end = max(new_end, min(new_end + .4, nxt))
    if silences is not None:
        aligned_end = _snap_end(rows, e_row, len(rows[e_row][2]), new_end,
                                new_start + original * .6, silences) or aligned_end
        new_start = _snap_start(new_start, silences, inner=s_off > 0)
    if new_start < start - CONTEXT_BEFORE or not original * .6 <= aligned_end - new_start <= original + MODEL_MAX_EXTEND + 15:
        return None
    return ClipBounds(round(new_start, 3), round(aligned_end, 3))


def neighbor_limits(clips: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """How far each clip's model refinement may reach: not past its neighbours' original edges.

    Clips are refined one by one in parallel, so each model call only sees its own clip. Without
    this limit two adjacent clips were both "finished" into the same span (RC156 Win QA #7: two
    drafts with an identical 0.0-57.8s scene). A clip may still keep its own original range.
    """
    order = sorted(range(len(clips)), key=lambda i: clips[i])
    limits = [(float('-inf'), float('inf'))] * len(clips)
    for n, i in enumerate(order):
        start, end = clips[i]
        lo = min(clips[order[n - 1]][1], start) if n > 0 else float('-inf')
        hi = max(clips[order[n + 1]][0], end) if n + 1 < len(order) else float('inf')
        limits[i] = (lo, hi)
    return limits


def refine_clips(rows: list[Row], clips: list[tuple[float, float]], call: Callable[[str, dict], dict] | None = None,
                 silences: SilenceFinder | None = None) -> list[tuple[float, float]]:
    """Sentence-snapped bounds for every clip; model-refined where the model gives a valid answer.

    A model answer that reaches into a neighbouring clip keeps pass 1 instead.
    """
    snapped = [sentence_bounds(rows, s, e, silences) for s, e in clips]
    if call is None or not rows:
        return snapped

    def one(item):
        (s, e), fallback, (lo, hi) = item
        try:
            refined = refine_with_model(rows, s, e, call, silences)
        except (JobDurationExceeded, JobStopped, ProjectDeleted, ServiceRestarted):
            raise
        except Exception as error:  # noqa: BLE001 - boundary polish never blocks output
            logger.warning('Boundary refinement fell back: %s', type(error).__name__)
            return ClipBounds(*fallback, needs_review=True)
        if refined is None:
            return ClipBounds(*fallback, needs_review=True)
        if refined[0] < lo or refined[1] > hi:
            logger.info('Boundary refinement crossed a neighbouring clip; keeping sentence bounds')
            return fallback
        return refined

    from backend.core.llm_usage import run_in_context
    with ThreadPoolExecutor(max_workers=4, thread_name_prefix='studio-bounds') as pool:
        return list(pool.map(run_in_context(one), zip(clips, snapped, neighbor_limits(clips))))
