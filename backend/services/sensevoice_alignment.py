"""SenseVoice CTC alignment, in milliseconds; never invent subtitle timing.

Adapted from LauraGPT's MIT-licensed timestamp fix for 123mlly/autoclip PR #1.
We require complete CTC alignment instead of its coarse/proportional fallbacks.
"""
import math
import re


def clean(text):
    return re.sub(r"<\|[^|]*\|>", "", text).replace("▁", " ").strip()


def aligned_cues(result, duration_ms, max_chars=42, max_duration_ms=8000):
    """Preserve all source text and real word times, across VAD segments."""
    if not isinstance(result, list) or not result or duration_ms <= 0:
        raise ValueError('SenseVoice 未返回可用的词级时间戳')
    cues, current = [], []
    previous_end = 0

    def flush():
        if current:
            cues.append({'start': current[0]['start'], 'end': current[-1]['end'],
                         'text': ''.join(w['text'] for w in current).strip(),
                         'words': list(current)})
            current.clear()

    for item in result:
        if not isinstance(item, dict) or not isinstance(item.get('text'), str):
            raise ValueError('SenseVoice 返回了无效的转写结果')
        source = clean(item['text'])
        if not source:
            continue
        words, times = item.get('words'), item.get('timestamp')
        if not isinstance(words, list) or not isinstance(times, list) or not words or len(words) != len(times):
            raise ValueError('SenseVoice 词与时间戳未完整配对，请重新准备模型或改用 Whisper')
        cursor, aligned = 0, []
        for word, time in zip(words, times):
            if not isinstance(word, str) or not clean(word) or not isinstance(time, (list, tuple)) or len(time) != 2:
                raise ValueError('SenseVoice 返回了无效的词级时间戳')
            if not all(isinstance(t, (int, float)) and not isinstance(t, bool) and math.isfinite(t) for t in time):
                raise ValueError('SenseVoice 返回了无效的词级时间戳')
            start, end = (int(t) for t in time)  # FunASR lists are always milliseconds.
            # CTC has a 60ms frame step; only tolerate final-frame rounding.
            if not 0 <= previous_end <= start < end <= duration_ms + 60:
                raise ValueError('SenseVoice 时间戳倒退、重叠或超出音频范围')
            end = min(end, duration_ms)
            if end <= start:
                raise ValueError('SenseVoice 时间戳超出音频范围')
            token = clean(word)
            position = source.find(token, cursor)
            if position < 0 or any(c.isalnum() for c in source[cursor:position]):
                raise ValueError('SenseVoice 原文与词级时间戳无法完整对齐')
            stop = position + len(token)
            aligned.append({'text': source[cursor:stop], 'start': start / 1000, 'end': end / 1000})
            cursor, previous_end = stop, end
        if any(c.isalnum() for c in source[cursor:]):
            raise ValueError('SenseVoice 原文与词级时间戳无法完整对齐')
        aligned[-1]['text'] += source[cursor:]
        for word in aligned:
            if current and (len(''.join(w['text'] for w in current) + word['text']) > max_chars
                            or (word['end'] - current[0]['start']) * 1000 > max_duration_ms
                            or word['start'] - current[-1]['end'] > 1.2):
                flush()
            if len(word['text'].strip()) > max_chars or (word['end'] - word['start']) * 1000 > max_duration_ms:
                raise ValueError('SenseVoice 单词时间戳异常，无法生成可读字幕')
            current.append(word)
            if re.search(r'[。！？；!?.;]$', word['text'].strip()):
                flush()
        flush()
    if not cues:
        raise ValueError('SenseVoice 未识别出可用人声')
    return cues
