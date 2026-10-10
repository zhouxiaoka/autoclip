"""Integrated LUFS and true peak against the platform target.

Every current strategy uses the plan's social target: −14 LUFS ± 1 LU, true
peak at or below −1 dBTP. The table is per strategy so a later target can differ.
"""
from __future__ import annotations

import re

from backend.services.studio.qa.media import ProbeError, run

# (integrated LUFS, tolerance LU, true-peak ceiling dBTP)
TARGETS = {
    'douyin': (-14.0, 1.0, -1.0),
    'tiktok': (-14.0, 1.0, -1.0),
    'instagram_reels': (-14.0, 1.0, -1.0),
    'youtube_shorts': (-14.0, 1.0, -1.0),
    'youtube_long': (-14.0, 1.0, -1.0),
    'bilibili': (-14.0, 1.0, -1.0),
    'xiaohongshu': (-14.0, 1.0, -1.0),
    'original': (-14.0, 1.0, -1.0),
}
DEFAULT_TARGET = (-14.0, 1.0, -1.0)

_I = re.compile(r'I:\s*(-?\d+(?:\.\d+)?)\s*LUFS')
_PEAK = re.compile(r'Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS')


def target_for(strategy_id: str) -> tuple[float, float, float]:
    return TARGETS.get(strategy_id, DEFAULT_TARGET)


def judge_levels(lufs: float, peak: float, strategy_id: str = 'original') -> tuple[str, str]:
    center, tolerance, peak_max = target_for(strategy_id)
    offset = lufs - center
    level_bad = abs(offset) > tolerance
    peak_bad = peak > peak_max
    if not level_bad and not peak_bad:
        return 'pass', 'in_target'
    if level_bad and peak_bad:
        return 'fail', 'peak_and_level'
    if peak_bad:
        return 'fail', 'peak'
    band = '1_3' if abs(offset) <= 3 else 'gt3'
    side = 'loud' if offset > 0 else 'quiet'
    return 'fail', f'{side}_{band}'


def parse_summary(text: str) -> tuple[float, float]:
    integrated, peaks = _I.findall(text), _PEAK.findall(text)
    if not integrated or not peaks:
        raise ProbeError('unreadable')
    return float(integrated[-1]), float(peaks[-1])


def measure(path, timeout: float) -> tuple[float, float]:
    """Audio only. Video, subtitles and data streams are not decoded."""
    from backend.services.render_limits import input_args
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    proc = run([
        get_ffmpeg_path(), '-hide_banner', *input_args(), '-i', str(path),
        '-map', '0:a:0', '-vn', '-sn', '-dn', '-af', 'ebur128=peak=true', '-f', 'null', '-',
    ], timeout, text=True)
    text = f'{proc.stderr or ""}\n{proc.stdout or ""}'
    if proc.returncode != 0 and 'LUFS' not in text:
        raise ProbeError('unreadable')
    return parse_summary(text)


def check(ctx, timeout: float) -> tuple[str, str]:
    if ctx.output is None or not getattr(ctx.output, 'is_file', lambda: False)():
        return 'skip', 'unreadable'
    try:
        from backend.services.studio.qa.media import probe_json
        # A 0.3 s probe expired on ordinary files and skipped the measurement.
        probe_s = min(1.5, max(0.4, timeout * 0.3))
        streams = probe_json(ctx.output, probe_s).get('streams') or []
        if not any(isinstance(row, dict) and row.get('codec_type') == 'audio' for row in streams):
            return 'skip', 'no_audio'
        lufs, peak = measure(ctx.output, max(0.5, timeout - probe_s))
    except ProbeError as error:
        return 'skip', error.reason
    return judge_levels(lufs, peak, ctx.strategy_id)
