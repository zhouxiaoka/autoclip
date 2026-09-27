"""Validated ASR word timing tied to the exact subtitle file.

SRT has only sentence timing. Keep ASR words in a sidecar; edits invalidate it
rather than silently using old timings for different or translated text.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile


def sidecar_path(srt: Path) -> Path:
    return srt.with_suffix('.words.json')


def _normalized(text):
    return ''.join(text.split())


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def valid_words(segment):
    """Reject partial text, missing times, reversed/overlapping words and NaNs."""
    try:
        start, end = segment['start'], segment['end']
        words = segment['words']
        if not (_number(start) and _number(end) and 0 <= start < end and words):
            return False
        last = start
        for word in words:
            a, b = word['start'], word['end']
            if not (_number(a) and _number(b) and start <= a < b <= end and a >= last):
                return False
            if not isinstance(word['text'], str) or not word['text'].strip():
                return False
            last = b
        return _normalized(''.join(w['text'] for w in words)) == _normalized(segment['text'])
    except (KeyError, TypeError, AttributeError):
        return False


def write_word_timing(srt: Path, segments, language=None):
    payload = {'schema_version': 1, 'source': 'faster-whisper', 'language': language,
               'srt_sha256': hashlib.sha256(srt.read_bytes()).hexdigest(),
               'segments': [s for s in segments if s.get('text', '').strip()]}
    # A bad segment keeps sentence captions usable, but must not become karaoke.
    for segment in payload['segments']:
        if not valid_words(segment):
            raise ValueError('Invalid ASR word timing')
    target = sidecar_path(srt)
    fd, temporary = tempfile.mkstemp(prefix=target.name+'.', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(payload, stream, ensure_ascii=False, allow_nan=False)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_word_timing(srt: Path):
    """Return only complete, unchanged source captions; otherwise safe fallback."""
    try:
        payload = json.loads(sidecar_path(srt).read_text(encoding='utf-8'))
        if payload.get('schema_version') != 1 or payload.get('source') != 'faster-whisper':
            return None
        if payload.get('srt_sha256') != hashlib.sha256(srt.read_bytes()).hexdigest():
            return None
        segments = payload['segments']
        if not isinstance(segments, list) or not segments or not all(valid_words(s) for s in segments):
            return None
        return segments
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return None
