"""Caption screens that never exceed two lines on any output frame.

Rows are cut into clauses at punctuation, each clause gets its own line when it fits, and lines
are paired into screens; so line breaks land on punctuation whenever the text allows. A clause
wider than one line is cut at a natural joint (after 的/了/着…, before 和/在/但…, or a space),
never through the middle when a better joint exists. Screen time is shared by displayed width.
Widths count a CJK character as 1 and Latin as 0.55.
"""
from __future__ import annotations

import re

CJK = re.compile(r'[　-〿㐀-鿿＀-￯]')
CLAUSE = re.compile(r'[^，。！？!?；;、,：:]+[，。！？!?；;、,：:]*')
AFTER = set('的了着过地得们吗呢吧啊')
BEFORE = set('和与及在把被就而但又还也都让对从向为')


def width(text: str) -> float:
    return sum(1 if CJK.match(ch) else 0.55 for ch in text)


def _cut(text: str, limit: float) -> int:
    """Where to cut a clause wider than `limit`: the latest natural joint that still fits."""
    best, best_rank, acc = None, None, 0.0
    for i, ch in enumerate(text[:-1]):
        acc += width(ch)
        if acc > limit:
            break
        nxt = text[i + 1]
        if ch == ' ':
            rank = 0
        elif ch in AFTER or nxt in BEFORE:
            rank = 1
        elif CJK.match(ch) and CJK.match(nxt):
            rank = 3
        else:
            continue
        # Prefer better joints; among equals, the one that fills the line most.
        if best_rank is None or rank < best_rank or (rank == best_rank and acc >= limit * 0.5):
            best, best_rank = i + 1, rank
    if best is not None:
        return best
    acc = 0.0
    for i, ch in enumerate(text):
        acc += width(ch)
        if acc > limit:
            return max(1, i)
    return len(text)


def lines_for(text: str, line_limit: float) -> list[str]:
    pieces = []
    for clause in CLAUSE.findall(text.strip()) or [text.strip()]:
        clause = clause.strip()
        while clause and width(clause) > line_limit:
            cut = _cut(clause, line_limit)
            pieces.append(clause[:cut].strip())
            clause = clause[cut:].strip()
        if clause:
            pieces.append(clause)
    lines = []
    for piece in pieces:
        joiner = ' ' if lines and not CJK.match(lines[-1][-1:] or ' ') and not CJK.match(piece[:1]) else ''
        if lines and width(lines[-1] + joiner + piece) <= line_limit:
            lines[-1] = lines[-1] + joiner + piece
        else:
            lines.append(piece)
    return [line for line in lines if line]


def split_screens(text: str, line_limit: float) -> list[str]:
    """Consecutive screens, each at most two lines joined by an ASS hard break."""
    lines = lines_for(text, line_limit)
    return ['\\N'.join(lines[i:i + 2]) for i in range(0, len(lines), 2)]


def wrap_two(text: str, line_limit: float) -> str:
    """Fit `text` in at most two lines; extra lines are merged into the second line."""
    lines = lines_for(text, line_limit)
    if len(lines) <= 2:
        return '\\N'.join(lines)
    return lines[0] + '\\N' + ' '.join(lines[1:])


def _split_words(text: str, parts: int) -> list[str]:
    words = text.split()
    if parts <= 1 or len(words) <= 1:
        return [text.strip()] + [''] * (parts - 1)
    size = len(words) / parts
    return [' '.join(words[round(i * size):round((i + 1) * size)]) for i in range(parts)]


def _fit_two(text: str, line_limit: float) -> str:
    """Two lines at most; if the text needs more, cut the second line with an ellipsis."""
    lines = lines_for(text, line_limit)
    if len(lines) <= 2:
        return '\\N'.join(lines)
    second, budget = '', line_limit - width('…')
    for word in ' '.join(lines[1:]).split(' '):
        candidate = f'{second} {word}'.strip()
        if width(candidate) > budget:
            break
        second = candidate
    return f'{lines[0]}\\N{second}…'


def timed_screens(text: str, start: float, end: float, line_limit: float, original: str = '',
                  original_limit: float = 0) -> list[tuple[float, float, str, str]]:
    """(start, end, screen text, original text) screens covering [start, end).

    A long original (e.g. English under a short Chinese line) gets more screens: the caption then
    shows one line per screen so both stay within two lines; beyond that the original is cut.
    """
    screens = split_screens(text, line_limit)
    if not screens:
        return []
    if original and original_limit:
        needed = -(-width(original) // (2 * original_limit * 0.9))
        if needed > len(screens):
            screens = lines_for(text, line_limit)
    originals = _split_words(original, len(screens)) if original else [''] * len(screens)
    weights = [max(width(s.replace('\\N', '')), 1) for s in screens]
    out, cursor = [], start
    for screen, orig, weight in zip(screens, originals, weights):
        span = (end - start) * weight / sum(weights)
        out.append((cursor, cursor + span, screen, _fit_two(orig, original_limit) if orig and original_limit else orig))
        cursor += span
    return out


def line_count(text: str) -> int:
    return text.count('\\N') + 1 if text else 0
