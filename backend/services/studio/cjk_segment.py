"""Word tokens for caption breaks and fallback emphasis.

Numbers stay with their unit (15小时, 8倍) and a Latin token stays with a following
里/中 (DNA里). The remaining Chinese is cut with jieba, which is already a runtime
dependency. A missing install falls back to keeping those protected tokens whole
and cutting the rest on characters.
"""
from __future__ import annotations

import logging
import re

_LOG = logging.getLogger(__name__)
_JIEBA = None
_UNITS = ('小时', '分钟', '秒钟', '毫秒', '纳米', '公里', '千克', '公斤', '个月', '倍', '个', '元', '块', '年', '天', '秒', '点')
_PARTICLE = set('的了着过地得们吗呢吧啊呀嘛')
# A one-character tail that is its own word, not the end of the phrase we want.
_TAIL = set('来去到过')


def _segmenter():
    global _JIEBA
    if _JIEBA is False:
        return None
    if _JIEBA is None:
        try:
            import jieba
            jieba.setLogLevel(logging.WARNING)
            _JIEBA = jieba
        except ImportError:
            _LOG.warning('jieba is not installed; Chinese breaks fall back to characters')
            _JIEBA = False
            return None
    return _JIEBA


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


def _cut_cjk(text: str) -> list[str]:
    if not text:
        return []
    jieba = _segmenter()
    if jieba is None:
        return [ch for ch in text if not ch.isspace()] or ([text] if text.strip() else [])
    return [token for token in jieba.lcut(text) if token != '']


def tokenize(text: str) -> list[str]:
    """Atomic tokens. Callers wrap and pick phrases from these, never from a character slice."""
    tokens: list[str] = []
    chunk: list[str] = []
    index = 0
    while index < len(text):
        number = _number_token(text, index)
        latin = None if number else _latin_token(text, index)
        taken = number or latin
        if taken:
            if chunk:
                tokens.extend(_cut_cjk(''.join(chunk)))
                chunk = []
            tokens.append(taken)
            index += len(taken)
            continue
        chunk.append(text[index])
        index += 1
    if chunk:
        tokens.extend(_cut_cjk(''.join(chunk)))
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
    """The last whole content word, or the last two when the last is a one-character compound.

    件衬衫来 → 衬衫, 的美国梦 → 美国梦, 怪的东西 → 东西, 公司上班 → 上班.
    """
    words = content_words(text)
    if not words:
        return ''
    chosen = words[-1]
    if len(chosen) == 1 and len(words) >= 2:
        if chosen in _TAIL:
            chosen = words[-2]
        else:
            joined = words[-2] + chosen
            chosen = joined if joined in text else words[-2]
    return chosen if len(chosen) >= 2 else ''
