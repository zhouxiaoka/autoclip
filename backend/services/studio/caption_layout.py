"""Caption screens that never exceed two lines on any output frame.

Rows are cut into clauses at punctuation, each clause gets its own line when it fits, and lines
are paired into screens; so line breaks land on punctuation whenever the text allows. A clause
wider than one line is cut at a natural joint (after 的/了/着…, before 和/在/但…, or a space),
never through the middle when a better joint exists. Screen time is shared by displayed width.
Widths count a CJK character as 1 and Latin as 0.55.
"""
from __future__ import annotations

import re
from itertools import pairwise

CJK = re.compile(r'[　-〿㐀-鿿＀-￯]')
CLAUSE = re.compile(r'[^，。！？!?；;、,：:]+[，。！？!?；;、,：:]*')
AFTER = set('的了着过地得们吗呢吧啊')
BEFORE = set('和与及在把被就而但又还也都让对从向为')
# 避头尾: a line does not open on a closer, or end on an opener.
NO_LINE_START = frozenset('，。！？、；：,.!?;:」』）)]}〉》】')
NO_LINE_END = frozenset('「『（([〈《【')
# English breaks avoid leaving a function word alone at the end of a line.
_FUNCTION = frozenset({'a', 'an', 'the', 'of', 'to', 'and', 'or', 'in', 'on', 'for', 'at', 'by', 'as', 'from'})
_SPEAKER_MARK = re.compile(r'^(?:>>\s*)+')
_FILLER = re.compile(r'(?i)(?<![A-Za-z])(?:uh+|um+|erm)(?![A-Za-z])')


def display_text(text: str) -> str:
    """Caption text as burned. Speaker turns stay in the transcript; fillers are not words."""
    cleaned = _SPEAKER_MARK.sub('', text or '')
    cleaned = _FILLER.sub(' ', cleaned)
    cleaned = re.sub(r'[ \t]+', ' ', cleaned)
    cleaned = re.sub(r'\s+([，。！？、；：,.!?;:])', r'\1', cleaned)
    return cleaned.strip(' ,')


def _word_before(text: str, index: int) -> str:
    end = index
    while end > 0 and text[end - 1] == ' ':
        end -= 1
    start = end
    while start > 0 and text[start - 1].isascii() and (text[start - 1].isalnum() or text[start - 1] == "'"):
        start -= 1
    return text[start:end].lower()


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
        if nxt in NO_LINE_START or ch in NO_LINE_END:
            continue
        if ch == ' ':
            rank = 5 if _word_before(text, i) in _FUNCTION else 0
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
    return _avoid_orphan(_kinsoku([line for line in lines if line], line_limit), line_limit)


def split_screens(text: str, line_limit: float) -> list[str]:
    """Consecutive screens, each at most two lines joined by an ASS hard break."""
    lines = lines_for(text, line_limit)
    return ['\\N'.join(lines[i:i + 2]) for i in range(0, len(lines), 2)]


def _clause_spans(text: str) -> list[tuple[int, int]]:
    """Clause ranges that cover `text` exactly, punctuation kept with the clause before it."""
    spans = []
    cursor = 0
    for match in CLAUSE.finditer(text):
        if match.start() > cursor:
            spans.append((cursor, match.start()))
        if match.end() > match.start():
            spans.append((match.start(), match.end()))
        cursor = match.end()
    if cursor < len(text):
        spans.append((cursor, len(text)))
    return spans


def _cut_span(text: str, start: int, end: int, limit: float) -> int:
    """Exclusive end of the next piece inside text[start:end]. The cut keeps every character."""
    piece = text[start:end]
    cut = _cut(piece, limit)
    if cut <= 0:
        cut = 1
    if cut < len(piece):
        return start + cut
    acc = 0.0
    for index, ch in enumerate(piece):
        acc += width(ch)
        if acc > limit:
            return start + max(1, index)
    return end


def page_lines(text: str, line_limit: float) -> list[str]:
    """Lines that join back to `text`. Breaks prefer punctuation, then the same joints as `_cut`."""
    if not text:
        return []
    pieces: list[tuple[int, int]] = []
    for start, end in _clause_spans(text):
        while start < end and width(text[start:end]) > line_limit:
            cut = _cut_span(text, start, end, line_limit)
            if cut <= start:
                cut = min(end, start + 1)
            pieces.append((start, cut))
            start = cut
        if start < end:
            pieces.append((start, end))
    if not pieces:
        return [text]
    lines: list[tuple[int, int]] = []
    for start, end in pieces:
        if lines and lines[-1][1] == start and width(text[lines[-1][0]:end]) <= line_limit:
            lines[-1] = (lines[-1][0], end)
        else:
            lines.append((start, end))
    covered = lines[0][0] == 0 and lines[-1][1] == len(text)
    covered = covered and all(left[1] == right[0] for left, right in pairwise(lines))
    if not covered:
        return _hard_lines(text, line_limit)
    rendered = [text[start:end] for start, end in lines]
    return _kinsoku(_attach_break_spaces(rendered, line_limit), line_limit)


def _hard_lines(text: str, line_limit: float) -> list[str]:
    lines = []
    start = 0
    while start < len(text):
        acc = 0.0
        index = start
        while index < len(text):
            step = width(text[index])
            if index > start and acc + step > line_limit:
                break
            acc += step
            index += 1
        if index == start:
            index = start + 1
        lines.append(text[start:index])
        start = index
    return lines


def _attach_break_spaces(lines: list[str], line_limit: float) -> list[str]:
    """Keep a break-point space on the previous line when that line still fits."""
    out = list(lines)
    for index in range(1, len(out)):
        spaces = len(out[index]) - len(out[index].lstrip(' '))
        if spaces <= 0:
            continue
        moved = out[index][:spaces]
        if width(out[index - 1] + moved) <= line_limit:
            out[index - 1] += moved
            out[index] = out[index][spaces:]
    return [line for line in out if line]


def _kinsoku(lines: list[str], line_limit: float) -> list[str]:
    """Move a closer onto the previous line, and an opener onto the next, when it still fits."""
    out = [line for line in lines if line]
    index = 1
    while index < len(out):
        line = out[index]
        if line and line[0] in NO_LINE_START:
            take = 0
            while take < len(line) and line[take] in NO_LINE_START:
                take += 1
            chunk = line[:take]
            if width(out[index - 1] + chunk) <= line_limit + 1e-6:
                out[index - 1] += chunk
                out[index] = line[take:]
                if not out[index]:
                    out.pop(index)
                    continue
                continue
        if out[index - 1] and out[index - 1][-1] in NO_LINE_END:
            opener = out[index - 1][-1]
            if width(opener + out[index]) <= line_limit + 1e-6:
                out[index - 1] = out[index - 1][:-1]
                out[index] = opener + out[index]
                if not out[index - 1]:
                    out.pop(index - 1)
                    continue
                continue
        index += 1
    return [line for line in out if line]


def _avoid_orphan(lines: list[str], line_limit: float) -> list[str]:
    """A one-word English tail joins a word from the line above when both still fit."""
    if len(lines) < 2:
        return lines
    out = list(lines)
    last_words = out[-1].split()
    prev_words = out[-2].split()
    if len(last_words) != 1 or not last_words[0].isascii() or len(prev_words) < 2:
        return out
    new_prev = ' '.join(prev_words[:-1])
    new_last = f'{prev_words[-1]} {out[-1].strip()}'.strip()
    if width(new_prev) <= line_limit + 1e-6 and width(new_last) <= line_limit + 1e-6:
        out[-2] = new_prev
        out[-1] = new_last
    return out


def page_screens(text: str, line_limit: float) -> list[str]:
    """Two-line screens joined by a newline. Dropping the newlines restores `text`."""
    lines = page_lines(text, line_limit)
    return ['\n'.join(lines[i:i + 2]) for i in range(0, len(lines), 2)]


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
