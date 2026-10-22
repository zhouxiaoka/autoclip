"""Word tokens for caption breaks and fallback emphasis.

Numbers stay with their unit (15小时, 8倍) and a Latin token stays with a following
里/中 (DNA里). Chinese lines break on those atoms, on a highlight, and on characters.
No dictionary package (jieba was about 37MB in the installer): caption breaks use a
compact word list, see break_units.
"""
from __future__ import annotations

import gzip
import math
import re
from functools import lru_cache
from pathlib import Path

_UNITS = ('小时', '分钟', '秒钟', '毫秒', '纳米', '公里', '千克', '公斤', '个月', '倍', '个', '元', '块', '年', '天', '秒', '点')
_PARTICLE = set('的了着过地得们吗呢吧啊呀嘛')
# A one-character tail that is its own word, not the end of the phrase we want.
_TAIL = set('来去到过')
_SPLIT = re.compile(r'[的了着]')


def _number_token(text: str, index: int) -> str | None:
    if not text[index].isdigit():
        return None
    end = index + 1
    while end < len(text) and (text[end].isdigit() or (text[end] == '.' and end + 1 < len(text) and text[end + 1].isdigit())):
        end += 1
    if end < len(text) and text[end] in '十百千万亿':
        end += 1
    probe = end
    if probe < len(text) and text[probe] == ' ':
        probe += 1
    for unit in _UNITS:
        if text.startswith(unit, probe):
            return text[index:probe + len(unit)]
    if probe < len(text) and text[probe] in '%％':
        return text[index:probe + 1]
    return text[index:end]


def _latin_token(text: str, index: int) -> str | None:
    if not ('A' <= text[index] <= 'z'):
        return None
    end = index + 1
    while end < len(text) and text[end].isascii() and (text[end].isalnum() or text[end] in "+._-'"):
        end += 1
    if end < len(text) and text[end] in '里中':
        end += 1
    return text[index:end]


def tokenize(text: str, protected: str = '') -> list[str]:
    """Atomic tokens. A highlight, a number+unit and a Latin token are never cut.

    Other Chinese is one character, so a line can break between characters. The caller
    still refuses a line that starts with 的/了/吗.
    """
    protected = str(protected or '').strip()
    tokens: list[str] = []
    index = 0
    while index < len(text):
        if protected and text.startswith(protected, index):
            tokens.append(protected)
            index += len(protected)
            continue
        number = _number_token(text, index)
        latin = None if number else _latin_token(text, index)
        taken = number or latin
        if taken:
            tokens.append(taken)
            index += len(taken)
            continue
        if text[index] == ' ':
            if tokens and not tokens[-1].endswith(' '):
                tokens[-1] += ' '
            index += 1
            continue
        tokens.append(text[index])
        index += 1
    return [token for token in tokens if token.strip()]


def content_words(text: str) -> list[str]:
    """Tokens a highlight can sit on. Particles and punctuation are not a phrase."""
    words = []
    for token in tokenize(text):
        token = token.strip().strip('，。、！？：；,.!?')
        if not token or all(ch in _PARTICLE for ch in token):
            continue
        words.append(token)
    return words


def whole_phrase(text: str) -> str:
    """The last content word of a Chinese clause, without a dictionary.

    Split on 的/了/着, drop a trailing 来/去/到/过, and keep the last two characters
    when the tail is still a long compound.

    件衬衫来 → 衬衫, 的美国梦 → 美国梦, 怪的东西 → 东西, 公司上班 → 上班.
    """
    cleaned = str(text or '').strip().strip('，。、！？：；,.!?').strip()
    if not cleaned:
        return ''
    parts = [part for part in _SPLIT.split(cleaned) if part]
    tail = parts[-1] if parts else cleaned
    if len(tail) >= 2 and tail[-1] in _TAIL:
        tail = tail[:-1]
    if len(tail) > 3:
        tail = tail[-2:]
    if len(tail) < 2 or tail not in cleaned:
        return ''
    return tail


# Words for caption breaks: a compact list derived from jieba's dictionary (MIT, see
# assets/lexicon/zh_words-LICENSE.txt), about 1.8MB gzipped. Missing file: character breaks.
_LEXICON = Path(__file__).resolve().parents[2] / 'assets' / 'lexicon' / 'zh_words.txt.gz'
_NUMERAL = set('零一二两三四五六七八九十百千万亿几半')
_MEASURE = set('倍项个位种次年天件条家段步层份批台部周月岁成点名轮代张句')


@lru_cache(maxsize=1)
def _lexicon() -> tuple[dict[str, float], float]:
    try:
        with gzip.open(_LEXICON, 'rt', encoding='utf-8') as handle:
            counts = {}
            for line in handle:
                word, _, freq = line.rstrip('\n').partition(' ')
                if word and freq.isdigit():
                    counts[word] = int(freq)
    except OSError:
        return {}, 0.0
    total = float(sum(counts.values()) or 1)
    return {word: math.log(freq / total) for word, freq in counts.items()}, math.log(1 / total)


def _is_cjk(token: str) -> bool:
    return len(token) == 1 and '\u4e00' <= token <= '\u9fff'


def _segment_run(run: str) -> list[str]:
    """Fewest-words split of a Chinese run, ties broken by word frequency.

    The dictionary's unigram split prefers 更|多 and 解|锁 (their own entries are rare);
    for line breaks a known word must win over its characters.
    """
    words, floor = _lexicon()
    if not words:
        return list(run)
    n = len(run)
    best = [(0, 0.0)] + [(10 ** 6, 0.0)] * n
    back = [0] * (n + 1)
    for end in range(1, n + 1):
        for size in range(1, min(4, end) + 1):
            piece = run[end - size:end]
            score = words.get(piece)
            if score is None:
                if size > 1:
                    continue
                score = floor
            count, logp = best[end - size]
            candidate = (count + 1, logp - score)
            if candidate < best[end]:
                best[end], back[end] = candidate, end - size
    out, end = [], n
    while end > 0:
        out.append(run[back[end]:end])
        end = back[end]
    return out[::-1]


def break_units(text: str, protected: str = '') -> list[str]:
    """Pieces a caption line never breaks inside: words, numbers with units, Latin, the highlight.

    生产力 / 每周 / 工作 / 80小时 / 增长 / 八倍 / 一项预测 are kept whole, so a line is never
    「增长八|倍」 or 「每周工|作80小时」. A numeral and its measure word stay with the next word.
    """
    units: list[str] = []
    run = ''
    for token in tokenize(text, protected) + ['']:
        if token and _is_cjk(token) and token != protected:
            run += token
            continue
        if run:
            units.extend(_segment_run(run))
            run = ''
        if token:
            units.append(token)
    merged: list[str] = []
    for unit in units:
        if merged and unit and unit[0] in _MEASURE and merged[-1] and all(ch in _NUMERAL for ch in merged[-1]):
            merged[-1] += unit  # 八 + 倍, 一 + 项
        else:
            merged.append(unit)
    # 一项 / 两种 / 八倍 lead into the word they count: 一项预测, not 一项|预测.
    joined: list[str] = []
    glue = False
    for unit in merged:
        if glue and joined and unit != protected and _is_cjk(unit[0]) and len(joined[-1] + unit) <= 6:
            joined[-1] += unit
        else:
            joined.append(unit)
        glue = (len(unit) >= 2 and unit[-1] in _MEASURE and all(ch in _NUMERAL for ch in unit[:-1])
                and not unit.endswith('倍'))
    return joined


def crosses_word(left: str, right: str, min_freq: int = 100) -> bool:
    """True when a common word runs across the break: 越发|现 cuts 发现 even if 越发 is a word too."""
    words, floor = _lexicon()
    if not words or not left or not right:
        return False
    common = floor + math.log(min_freq)
    for take in range(1, 4):
        for give in range(1, 5 - take):
            piece = left[-take:] + right[:give]
            if len(piece) == take + give and all(_is_cjk(ch) for ch in piece) and words.get(piece, -math.inf) > common:
                return True
    return False
