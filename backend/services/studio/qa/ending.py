"""The clip ends inside a word or a sentence. Word timings are the only source.

A word that still has more than 80 ms left is cut mid-word. A following word
that starts within 0.6 s, when the last spoken word is not sentence-final, is
cut mid-sentence. The word text is not stored on the report.
"""
from __future__ import annotations

import re

SLACK_S = 0.08
GAP_S = 0.6
_FINAL = re.compile(r'[。！？!?…]$|\.$')


def _sentence_final(text: str) -> bool:
    token = text.strip().strip('\"\'“”‘’')
    return bool(token) and bool(_FINAL.search(token))


def judge_ending(words: list[dict] | None, clip_end: float, clip_start: float = 0.0) -> tuple[str, str]:
    if not words:
        return 'skip', 'no_words'
    inside = [
        word for word in words
        if word['start'] < clip_end < word['end'] - SLACK_S and word['end'] > clip_start
    ]
    if inside:
        return 'fail', 'mid_word'
    spoken = [
        word for word in words
        if clip_start - SLACK_S <= word['start'] and word['end'] <= clip_end + SLACK_S
    ]
    if not spoken:
        return 'pass', 'complete'
    last = max(spoken, key=lambda word: word['end'])
    if _sentence_final(last['text']):
        return 'pass', 'complete'
    nxt = next((word for word in words if word['start'] >= clip_end - 1e-6), None)
    if nxt is not None and nxt['start'] - clip_end <= GAP_S:
        return 'fail', 'mid_sentence'
    return 'pass', 'complete'


def check(ctx, timeout: float) -> tuple[str, str]:
    del timeout
    if not ctx.scenes:
        return judge_ending(ctx.words, 0.0, 0.0) if ctx.words else ('skip', 'no_words')
    last = ctx.scenes[-1]
    return judge_ending(ctx.words, last.end, ctx.scenes[0].start)
