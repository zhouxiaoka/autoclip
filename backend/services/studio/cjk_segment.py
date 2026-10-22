"""Word tokens for caption breaks and fallback emphasis.

Numbers stay with their unit (15小时, 8倍) and a Latin token stays with a following
里/中 (DNA里). Chinese lines break on those atoms, on a highlight, and on characters.
No dictionary package: a general word list is not required, and jieba was about 37MB
in the installer.
"""
from __future__ import annotations

import re

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
