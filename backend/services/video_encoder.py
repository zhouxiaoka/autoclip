"""H.264 encoder choice: the machine's hardware encoder when it works, else libx264.

A Studio render used to be one libx264 encode per clip on the CPU; with 30+ clips per video that
was most of the run and all of the fan noise. VideoToolbox (macOS) and NVENC / QSV / AMF (Windows,
Linux) encode the same 1080×1920 clip several times faster with almost no CPU. Each candidate is
proven once with a tiny test encode; a failed real encode marks it broken and the caller retries
with libx264. `AUTOCLIP_VIDEO_ENCODER=x264` forces software encoding.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading

logger = logging.getLogger(__name__)

SOFTWARE = 'libx264'
_lock = threading.Lock()
_chosen: str | None = None
_broken: set[str] = set()


def _candidates() -> list[str]:
    if sys.platform == 'darwin':
        return ['h264_videotoolbox']
    return ['h264_nvenc', 'h264_qsv', 'h264_amf']


def _works(ffmpeg: str, encoder: str) -> bool:
    cmd = [ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=320x568:r=30:d=0.3',
           *_args(encoder, 320, 568), '-f', 'null', '-']
    try:
        return subprocess.run(cmd, capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def encoder() -> str:
    """The encoder to use now (probed once per process)."""
    global _chosen
    if os.getenv('AUTOCLIP_VIDEO_ENCODER', '').strip().lower() in ('x264', 'libx264', 'software'):
        return SOFTWARE
    with _lock:
        if _chosen is None or _chosen in _broken:
            from backend.utils.ffmpeg_utils import get_ffmpeg_path
            ffmpeg = get_ffmpeg_path()
            _chosen = next((name for name in _candidates() if name not in _broken and _works(ffmpeg, name)), SOFTWARE)
            logger.info('Video encoder: %s', _chosen)
        return _chosen


def mark_broken(name: str) -> None:
    if name != SOFTWARE:
        with _lock:
            _broken.add(name)
        logger.warning('Hardware encoder %s failed; using libx264 from now on', name)


def _bitrate(width: int, height: int, fps: int = 30) -> int:
    # ~0.13 bits per pixel per frame matches libx264 crf 20 on talking-head footage (8 Mbps at 1080×1920@30).
    return max(1_500_000, int(width * height * fps * 0.13))


def _args(name: str, width: int, height: int) -> list[str]:
    rate = _bitrate(width, height)
    vbr = ['-b:v', str(rate), '-maxrate', str(int(rate * 1.5)), '-bufsize', str(rate * 2)]
    if name == 'h264_videotoolbox':
        return ['-c:v', name, *vbr, '-profile:v', 'high', '-pix_fmt', 'yuv420p']
    if name == 'h264_nvenc':
        return ['-c:v', name, '-preset', 'p4', '-rc', 'vbr', '-cq', '21', *vbr, '-pix_fmt', 'yuv420p']
    if name == 'h264_qsv':
        return ['-c:v', name, '-preset', 'medium', '-global_quality', '21', *vbr, '-pix_fmt', 'nv12']
    if name == 'h264_amf':
        return ['-c:v', name, '-quality', 'balanced', '-rc', 'vbr_peak', *vbr, '-pix_fmt', 'yuv420p']
    return ['-c:v', SOFTWARE, '-preset', 'veryfast', '-crf', '20', '-pix_fmt', 'yuv420p']


def h264_args(width: int, height: int, name: str | None = None) -> list[str]:
    """Video codec arguments (codec, rate control, pixel format) for one encode."""
    return _args(name or encoder(), width, height)


def run_with_fallback(build, run):
    """Run `run(build(name))`; if a hardware encode fails, mark it broken and retry with libx264.

    `build(name)` returns the ffmpeg command for that encoder; `run(cmd)` returns a completed process.
    """
    name = encoder()
    if name == SOFTWARE:
        return run(build(name))
    try:
        proc = run(build(name))
    except (subprocess.TimeoutExpired, OSError):
        proc = None  # a stalled hardware encoder: software encoding still gets its chance
    if proc is None or proc.returncode:
        retry = run(build(SOFTWARE))
        # Only blame the hardware encoder when software succeeds on the same input; a bad source
        # or filter graph fails both and must not disable hardware encoding for the session.
        if not retry.returncode:
            mark_broken(name)
        return retry
    return proc
