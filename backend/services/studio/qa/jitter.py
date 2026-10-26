"""Framing-path flashes and sampled background motion.

A flash is a reversal of at least the framing jump (12% of the width) inside
0.8 s, more than once a minute. On a shot that is not panning, RMS motion above
0.30 px also fails. The live frame sample is 96 px wide, so one sample pixel is
about 11 px on a 1080-wide frame: shifts under 0.12 sample px are phase-correlation
noise and are zeroed before that comparison. A pan is motion of at least 8 output
px per frame; visible wobble below that still fails RMS.
Shifts come from phase correlation, not a pixel search.
"""
from __future__ import annotations

import math

from backend.services.studio.qa.media import ProbeError, run

FLASHES_PER_MIN = 1.0
RMS_PX = 0.30
REVERSAL_S = 0.8
MIN_JUMP = 0.12
# Output px/frame. Below this, motion is not a pan. 8 px is under 1% of 1080
# and above the noise that survives SAMPLE_NOISE_PX.
STATIC_MEAN_PX = 8.0
# Sample-pixel reversals. One sample pixel is coarser than compression noise.
SAMPLE_FLASH_PX = 3.0
# Phase correlation on a 96px sample jitters below this. It is not camera motion.
SAMPLE_NOISE_PX = 0.12
_SAMPLE_W, _SAMPLE_H = 96, 54


def flashes(points: list[tuple[float, float]], width: int, modes: list[str] | None = None) -> int:
    """Direction reversals, and a fit blip that is undone within REVERSAL_S.

    A fit point is a layout, not a crop at 0.5. Crop-to-crop jumps still use MIN_JUMP.
    Two layout changes inside the reversal window are one visible flash.
    """
    modes = list(modes or [])
    states = []
    for index, (time, crop_x) in enumerate(points):
        mode = modes[index] if index < len(modes) and modes[index] in ('crop', 'fit') else 'crop'
        states.append((time, mode, crop_x))
    moves = []
    layouts = []
    for previous, current in zip(states, states[1:]):
        if previous[1] != current[1]:
            layouts.append(current[0])
        elif previous[1] == 'crop':
            delta = (current[2] - previous[2]) * width
            if abs(delta) >= MIN_JUMP * width:
                moves.append((current[0], 1 if delta > 0 else -1))
    count = 0
    for (t1, d1), (t2, d2) in zip(moves, moves[1:]):
        if d1 * d2 < 0 and (t2 - t1) <= REVERSAL_S:
            count += 1
    for t1, t2 in zip(layouts, layouts[1:]):
        if t2 - t1 <= REVERSAL_S:
            count += 1
    return count


def flashes_from_shifts(shifts: list[tuple[float, float]], min_px: float = SAMPLE_FLASH_PX) -> int:
    count = 0
    previous = None
    for dx, dy in shifts:
        mag = math.hypot(dx, dy)
        if mag < min_px:
            previous = None
            continue
        sign = 1 if dx > 0 or (dx == 0 and dy > 0) else -1
        if previous is not None and previous * sign < 0:
            count += 1
        previous = sign
    return count


def quiet_sample_noise(shifts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Zero sub-resolution sample shifts. A real wobble stays."""
    quiet = []
    for dx, dy in shifts:
        if math.hypot(dx, dy) < SAMPLE_NOISE_PX:
            quiet.append((0.0, 0.0))
        else:
            quiet.append((dx, dy))
    return quiet


def motion_stats(shifts: list[tuple[float, float]]) -> tuple[float, float]:
    if not shifts:
        return 0.0, 0.0
    mags = [math.hypot(dx, dy) for dx, dy in shifts]
    mean = sum(mags) / len(mags)
    rms = math.sqrt(sum(v * v for v in mags) / len(mags))
    return rms, mean


def judge_motion(flash_count: int, duration_s: float, rms_px: float, mean_abs_px: float) -> tuple[str, str]:
    per_min = flash_count / max(duration_s, 1e-3) * 60
    flash_fail = per_min > FLASHES_PER_MIN
    rms_fail = mean_abs_px < STATIC_MEAN_PX and rms_px > RMS_PX
    if flash_fail and rms_fail:
        return 'fail', 'flash_and_rms'
    if flash_fail:
        return 'fail', 'flash'
    if rms_fail:
        return 'fail', 'rms'
    return 'pass', 'calm'


def estimate_shift(prev: bytes, curr: bytes, width: int, height: int) -> tuple[float, float]:
    """Sub-pixel shift of curr relative to prev, via phase correlation.

    A pure Python search cannot be killed mid-loop. This returns as soon as
    the FFT finishes. Missing numpy or OpenCV is a skip, not a slow fallback.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        raise ProbeError('unreadable') from None
    if len(prev) != width * height or len(curr) != width * height or width < 8 or height < 8:
        raise ProbeError('unreadable')
    previous = np.frombuffer(prev, dtype=np.uint8).reshape(height, width).astype(np.float32)
    current = np.frombuffer(curr, dtype=np.uint8).reshape(height, width).astype(np.float32)
    try:
        window = cv2.createHanningWindow((width, height), cv2.CV_32F)
        (shift_x, shift_y), _response = cv2.phaseCorrelate(previous, current, window)
    except cv2.error:
        (shift_x, shift_y), _response = cv2.phaseCorrelate(previous, current)
    return float(shift_x), float(shift_y)


def _sample_shifts(path, at: float, timeout: float) -> list[tuple[float, float]]:
    """Consecutive-frame shifts in sample pixels, not output pixels."""
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    proc = run([
        get_ffmpeg_path(), '-v', 'error', '-ss', f'{max(0.0, at):.3f}', '-i', str(path),
        '-frames:v', '6', '-vf', f'scale={_SAMPLE_W}:{_SAMPLE_H}',
        '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1',
    ], timeout)
    raw = proc.stdout or b''
    size = _SAMPLE_W * _SAMPLE_H
    count = len(raw) // size
    if proc.returncode != 0 or count < 2:
        raise ProbeError('unreadable')
    frames = [raw[i * size:(i + 1) * size] for i in range(count)]
    return [estimate_shift(frames[i], frames[i + 1], _SAMPLE_W, _SAMPLE_H) for i in range(count - 1)]


def check(ctx, timeout: float) -> tuple[str, str]:
    width = ctx.width or 1080
    duration = sum(max(0.0, scene.end - scene.start) for scene in ctx.scenes) or 1.0
    track_flashes = sum(flashes(scene.points, width, scene.modes) for scene in ctx.scenes)
    has_track = any(scene.points for scene in ctx.scenes)
    raw: list[tuple[float, float]] = []
    if ctx.output is not None and getattr(ctx.output, 'is_file', lambda: False)():
        try:
            raw = _sample_shifts(ctx.output, duration / 2, timeout)
        except ProbeError as error:
            if not has_track:
                return 'skip', error.reason
    elif not has_track:
        return 'skip', 'unreadable'
    scale = width / _SAMPLE_W
    raw = quiet_sample_noise(raw)
    rms, mean = motion_stats([(dx * scale, dy * scale) for dx, dy in raw])
    flash_count = max(track_flashes, flashes_from_shifts(raw))
    return judge_motion(flash_count, duration, rms, mean)
