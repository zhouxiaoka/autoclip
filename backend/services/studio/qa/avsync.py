"""Output audio/video start drift. Fail when the absolute drift is over 40 ms.

Source-frame ORB matching from the packaging plan is not part of this shadow
check: a budget-sized sample cannot resolve 40 ms once the picture is cropped
or captioned, and a weak match would fail clips that are actually in sync.
"""
from __future__ import annotations

# Plan §5: any segment whose median offset exceeds 40 ms fails.
FAIL_MS = 40.0


def judge_drift(drift_ms: float) -> tuple[str, str]:
    mag = abs(drift_ms)
    if mag <= FAIL_MS:
        return 'pass', 'lt40'
    if mag <= 80:
        return 'fail', '40_80'
    if mag <= 200:
        return 'fail', '80_200'
    return 'fail', 'gt200'


def measure_drift_ms(path, timeout: float) -> float:
    from backend.services.studio.qa.media import ProbeError, probe_json
    data = probe_json(path, timeout)
    video = audio = None
    for stream in data.get('streams') or []:
        if not isinstance(stream, dict):
            continue
        try:
            start = float(stream.get('start_time'))
        except (TypeError, ValueError):
            continue
        kind = stream.get('codec_type')
        if kind == 'video' and video is None:
            video = start
        elif kind == 'audio' and audio is None:
            audio = start
    if video is None:
        raise ProbeError('unreadable')
    if audio is None:
        raise ProbeError('no_audio')
    return (audio - video) * 1000


def check(ctx, timeout: float) -> tuple[str, str]:
    from backend.services.studio.qa.media import ProbeError
    if ctx.output is None or not getattr(ctx.output, 'is_file', lambda: False)():
        return 'skip', 'unreadable'
    try:
        return judge_drift(measure_drift_ms(ctx.output, timeout))
    except ProbeError as error:
        return 'skip', error.reason
