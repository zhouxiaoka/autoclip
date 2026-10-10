"""Segment offset between the export's audio and the source audio it came from.

A container start_time match is not a sync pass: most files report 0 and would
always pass. When the source and the scene list are available, each sampled
window is cross-correlated with the source audio at the mapped time. The
median offset and the spread across windows both have to stay within 40 ms.
Without a source, a start_time gap above 40 ms still fails; a small gap is
`skip` / `start_only`.
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


RATE = 16000
WINDOW_S = 1.0
MARGIN_S = 0.25
MIN_RHO = 0.35


def _map_source_time(scenes, t_out: float) -> float | None:
    """Output time walks the concatenated scenes back to a source time."""
    cursor = 0.0
    for scene in scenes:
        dur = max(0.0, scene.end - scene.start)
        if dur <= 0:
            continue
        if t_out <= cursor + dur + 1e-3:
            return scene.start + max(0.0, t_out - cursor)
        cursor += dur
    return None


def _pcm(path, start: float, duration: float, timeout: float) -> bytes:
    from backend.services.render_limits import input_args
    from backend.services.studio.qa.media import ProbeError, run
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    proc = run([
        get_ffmpeg_path(), '-v', 'error', *input_args(),
        '-ss', f'{max(0.0, start):.3f}', '-t', f'{duration:.3f}', '-i', str(path),
        '-map', '0:a:0', '-vn', '-sn', '-dn', '-ac', '1', '-ar', str(RATE), '-f', 'f32le', 'pipe:1',
    ], timeout)
    raw = proc.stdout or b''
    if proc.returncode != 0 or len(raw) < (RATE * 4) // 2:
        raise ProbeError('unreadable')
    return raw


def _lag_ms(output_pcm: bytes, source_pcm: bytes, margin_s: float) -> float | None:
    """Milliseconds the output window is late relative to the mapped source time.

    None means the signal is silent or the correlation is too weak to trust.
    """
    import numpy as np
    out = np.frombuffer(output_pcm, dtype='<f4').astype(np.float64)
    src = np.frombuffer(source_pcm, dtype='<f4').astype(np.float64)
    if out.size < RATE // 2 or src.size <= out.size:
        return None
    if float(np.std(out)) < 1e-4 or float(np.std(src)) < 1e-4:
        return None
    out = out - float(out.mean())
    src = src - float(src.mean())
    corr = np.correlate(src, out, mode='valid')
    peak = int(np.argmax(np.abs(corr)))
    aligned = src[peak:peak + out.size]
    denom = float(np.linalg.norm(out) * np.linalg.norm(aligned))
    if denom <= 0 or abs(float(corr[peak]) / denom) < MIN_RHO:
        return None
    expected = int(round(margin_s * RATE))
    return (peak - expected) / RATE * 1000.0


def measure_offsets_ms(ctx, timeout: float) -> list[float]:
    from backend.services.studio.qa.media import ProbeError
    duration = sum(max(0.0, scene.end - scene.start) for scene in ctx.scenes)
    if duration < WINDOW_S + 0.2:
        raise ProbeError('unreadable')
    points = []
    for frac in (0.15, 0.5, 0.8):
        at = duration * frac
        if 0.2 < at < duration - 0.3:
            points.append(at)
    if not points:
        raise ProbeError('unreadable')
    share = max(0.2, timeout / (len(points) * 2))
    lags = []
    for at in points:
        mapped = _map_source_time(ctx.scenes, at)
        if mapped is None:
            continue
        src_start = max(0.0, mapped - MARGIN_S)
        margin = mapped - src_start
        out_pcm = _pcm(ctx.output, at, WINDOW_S, share)
        src_pcm = _pcm(ctx.source, src_start, WINDOW_S + margin + MARGIN_S, share)
        lag = _lag_ms(out_pcm, src_pcm, margin)
        if lag is not None:
            lags.append(lag)
    if not lags:
        raise ProbeError('start_only')
    return lags


def judge_offsets(lags: list[float]) -> tuple[str, str]:
    ordered = sorted(lags)
    median = ordered[len(ordered) // 2]
    drift = (max(lags) - min(lags)) if len(lags) > 1 else 0.0
    return judge_drift(max(abs(median), drift))


def _source_ready(ctx) -> bool:
    source = getattr(ctx, 'source', None)
    return bool(ctx.scenes) and source is not None and getattr(source, 'is_file', lambda: False)()


def check(ctx, timeout: float) -> tuple[str, str]:
    from backend.services.studio.qa.media import ProbeError
    if ctx.output is None or not getattr(ctx.output, 'is_file', lambda: False)():
        return 'skip', 'unreadable'
    if _source_ready(ctx):
        try:
            return judge_offsets(measure_offsets_ms(ctx, timeout))
        except ProbeError as error:
            if error.reason == 'no_audio':
                return 'skip', 'no_audio'
    try:
        drift = measure_drift_ms(ctx.output, min(1.0, timeout))
    except ProbeError as error:
        return 'skip', error.reason
    outcome, bucket = judge_drift(drift)
    # A container that already starts together is not evidence the pictures match the words.
    if outcome == 'pass':
        return 'skip', 'start_only'
    return outcome, bucket
