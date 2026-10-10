"""Lightweight editing-style recommendation.

Answers from a file header and ffprobe. A URL is accepted but not downloaded.
Unknown input and anything that exceeds the budget stay on editorial. The
body is enums only: no titles, names, paths, or durations.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import time

TEMPLATES = ('editorial', 'street', 'classic')
REASONS = ('seated_interview', 'street_quick', 'speech', 'default', 'timeout')
SCENES = ('seated_interview', 'street', 'speech', 'unknown')
PEOPLE = ('solo', 'duo', 'group', 'unknown')
PACES = ('calm', 'fast', 'unknown')
CAPTIONS = ('bilingual', 'zh', 'en', 'none', 'unknown')
BUCKETS = ('short', 'medium', 'long', 'unknown')
_SIGNAL_KEYS = {
    'scene': SCENES,
    'people': PEOPLE,
    'pace': PACES,
    'captions': CAPTIONS,
    'duration_bucket': BUCKETS,
}
BUDGET_SEC = 1.8


def signals_from_media(width: int | None, height: int | None, duration: float | None) -> dict:
    """Map picture shape and length onto enums. Faces and words are not read."""
    scene = 'unknown'
    pace = 'unknown'
    bucket = 'unknown'
    if isinstance(duration, (int, float)) and not isinstance(duration, bool) and duration > 0:
        if duration <= 180:
            bucket = 'short'
        elif duration >= 600:
            bucket = 'long'
        else:
            bucket = 'medium'
    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0 and bucket != 'unknown':
        portrait = height > width * 1.05
        if portrait and duration is not None and duration <= 180:
            scene, pace = 'street', 'fast'
        elif not portrait and duration is not None and duration >= 600:
            scene, pace = 'seated_interview', 'calm'
        else:
            scene, pace = 'speech', 'calm'
    return {
        'scene': scene,
        'people': 'unknown',
        'pace': pace,
        'captions': 'unknown',
        'duration_bucket': bucket,
    }


def decide(signals: dict) -> tuple[str, str]:
    """Street when the picture is a short vertical or the pace is fast."""
    scene = signals.get('scene')
    pace = signals.get('pace')
    if scene == 'street' or pace == 'fast':
        return 'street', 'street_quick'
    if scene == 'seated_interview':
        return 'editorial', 'seated_interview'
    if scene == 'speech':
        return 'editorial', 'speech'
    return 'editorial', 'default'


def pack(template: str, reason: str, signals: dict | None) -> dict:
    raw = signals or {}
    return {
        'template': template if template in TEMPLATES else 'editorial',
        'reason_code': reason if reason in REASONS else 'default',
        'signals': {
            key: raw.get(key) if raw.get(key) in allowed else 'unknown'
            for key, allowed in _SIGNAL_KEYS.items()
        },
    }


def fallback(reason: str = 'default') -> dict:
    return pack('editorial', reason, signals_from_media(None, None, None))


def probe_header(header: bytes, budget: float) -> dict:
    """ffprobe the first megabyte. A partial file that will not probe stays unknown."""
    if not header:
        return signals_from_media(None, None, None)
    from backend.utils.ffmpeg_utils import get_ffprobe_path
    with tempfile.NamedTemporaryFile(suffix='.mp4') as tmp:
        tmp.write(header[: 1024 * 1024])
        tmp.flush()
        try:
            completed = subprocess.run(
                [get_ffprobe_path(), '-v', 'error', '-show_entries', 'format=duration:stream=width,height,codec_type', '-of', 'json', tmp.name],
                capture_output=True, timeout=max(0.05, min(budget, BUDGET_SEC)), check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise TimeoutError('probe timed out') from error
    if completed.returncode != 0 or not completed.stdout:
        return signals_from_media(None, None, None)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return signals_from_media(None, None, None)
    width = height = None
    for stream in payload.get('streams') or []:
        if not isinstance(stream, dict):
            continue
        if stream.get('codec_type') in (None, 'video') and isinstance(stream.get('width'), int):
            width = stream.get('width')
            height = stream.get('height') if isinstance(stream.get('height'), int) else None
            break
    duration = None
    raw_duration = (payload.get('format') or {}).get('duration') if isinstance(payload.get('format'), dict) else None
    try:
        duration = float(raw_duration)
    except (TypeError, ValueError):
        duration = None
    return signals_from_media(width, height, duration)


def recommend_template(*, url: str | None = None, header: bytes | None = None, budget: float = BUDGET_SEC, probe=None, clock=None) -> dict:
    """Return before `budget` seconds. `url` is not fetched."""
    del url  # accepted so the route can validate it; the probe never opens it
    clock = time.monotonic if clock is None else clock
    probe = probe_header if probe is None else probe
    started = clock()
    if not header:
        return fallback('default')
    remaining = budget - (clock() - started)
    if remaining <= 0:
        return fallback('timeout')
    try:
        signals = probe(header, remaining)
    except TimeoutError:
        return fallback('timeout')
    if clock() - started > budget:
        return fallback('timeout')
    template, reason = decide(signals if isinstance(signals, dict) else {})
    return pack(template, reason, signals if isinstance(signals, dict) else {})
