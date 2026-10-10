"""HTML overlay capture and the one encode that follows it.

The page contract is ``setData`` / ``renderFrame`` / ``occupiedRects``. ``renderFrame``
returns a state hash. A frame whose hash matches the previous one is not captured
again. Two pages run at once, each owning a contiguous range of frames.

The overlay is ffv1 with alpha. The picture encode probes NVENC, QSV, AMF and
VideoToolbox. A failed probe or a failed hardware encode retries libx264 veryfast.
This module does not fail an export because the encoder was unavailable: the
caller receives ``ok: false`` and a ``failure_reason`` enum, with no path and no
caption in the message.
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time
from pathlib import Path

from backend.services.studio.features import flag_enabled
from backend.services.studio.template_telemetry import host_facts, render_event
from backend.services.video_encoder import SOFTWARE, h264_args

logger = logging.getLogger(__name__)

PAGES = 2
PROBE_ORDER = ('h264_nvenc', 'h264_qsv', 'h264_amf', 'h264_videotoolbox')
_lock = __import__('threading').Lock()
_chosen: str | None = None
_broken: set[str] = set()


class OverlayEncodeError(RuntimeError):
    """Encoder or capture failure. ``reason`` is an enum. The message is that enum."""

    def __init__(self, reason: str):
        self.reason = reason if reason in {'capture', 'encode', 'runtime', 'timeout', 'unknown'} else 'unknown'
        super().__init__(self.reason)


def reset_encoder_cache() -> None:
    """Tests start from an unprobed process."""
    global _chosen
    with _lock:
        _chosen = None
        _broken.clear()


def templates_requested(features: dict | None) -> bool:
    return flag_enabled(features, 'pkg_templates_v1')


def skipped_event(reason: str, *, template: str = 'classic', flow_id: str | None = None, strategy_id: str | None = None) -> dict:
    """Flag off or a non-HTML template. This is not a failed export."""
    return render_event({
        'template': template,
        'encoder': SOFTWARE,
        'downgraded': reason not in {'none', 'flag_off'},
        'downgrade_reason': reason,
        'failure_reason': 'none',
        'outcome': 'downgraded' if reason not in {'none', 'flag_off'} else 'completed',
        'flow_id': flow_id,
        'strategy_id': strategy_id,
        **host_facts(),
    })


def split_indices(count: int, pages: int = PAGES) -> list[list[int]]:
    """Contiguous ranges for ``pages`` parallel captures. Empty input yields nothing."""
    if count <= 0:
        return []
    pages = max(1, min(pages, count))
    size = (count + pages - 1) // pages
    return [list(range(start, min(count, start + size))) for start in range(0, count, size)]


def collapse_hashes(hashes: list[str]) -> list[dict]:
    """One record per run of identical hashes. ``count`` is how many frames that PNG covers."""
    runs: list[dict] = []
    for index, digest in enumerate(hashes):
        if runs and runs[-1]['hash'] == digest:
            runs[-1]['count'] += 1
            continue
        runs.append({'index': index, 'hash': digest, 'count': 1})
    return runs


async def capture_changed(frame_count: int, fps: int, render, shoot, pages: int = PAGES) -> list[dict]:
    """Capture only frames whose hash differs from the previous frame on that page.

    ``render(page, time_seconds)`` returns the hash. ``shoot(page, index)`` returns PNG bytes.
    """
    if fps <= 0:
        raise OverlayEncodeError('capture')

    async def one(ordinal: int, indices: list[int]) -> list[dict]:
        frames: list[dict] = []
        last = None
        for index in indices:
            digest = await render(ordinal, index / fps)
            if not isinstance(digest, str) or not digest:
                raise OverlayEncodeError('capture')
            if frames and digest == last:
                frames[-1]['count'] += 1
                continue
            png = await shoot(ordinal, index)
            frames.append({'index': index, 'hash': digest, 'count': 1, 'png': png})
            last = digest
        return frames

    groups = await asyncio.gather(*(one(ordinal, chunk) for ordinal, chunk in enumerate(split_indices(frame_count, pages))))
    return [frame for group in groups for frame in group]


def report_overlay_failure(error: BaseException) -> None:
    """Sentry phase ``packaging_html``. The public log line is the exception type only."""
    logger.warning('HTML overlay failed: %s', type(error).__name__)
    try:
        from backend.core.sentry_setup import capture_studio_exception
        if isinstance(error, Exception):
            capture_studio_exception(error, 'packaging_html')
    except Exception:
        logger.warning('HTML overlay sentry report failed')


def ffv1_args() -> list[str]:
    return ['-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'yuva444p']


def _concat_listing(holds: list[tuple[Path, int]], fps: int, listing: Path) -> None:
    lines: list[str] = []
    for path, count in holds:
        lines.append(f"file '{path.as_posix()}'\n")
        lines.append(f"duration {count / fps:.6f}\n")
    if holds:
        lines.append(f"file '{holds[-1][0].as_posix()}'\n")
    listing.write_text(''.join(lines), encoding='utf-8')


def encode_ffv1(holds: list[tuple[Path, int]], dest: Path, fps: int = 30, run=None) -> None:
    """Write an ffv1 movie with alpha. ``holds`` is ``(png, frame count)`` in order."""
    if not holds or fps <= 0:
        raise OverlayEncodeError('capture')
    listing = dest.with_suffix('.ffconcat')
    _concat_listing(holds, fps, listing)
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    cmd = [get_ffmpeg_path(), '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing), *ffv1_args(), '-y', str(dest)]
    try:
        proc = (run or _run)(cmd)
    except subprocess.TimeoutExpired as error:
        report_overlay_failure(error)
        raise OverlayEncodeError('timeout') from None
    except OSError as error:
        report_overlay_failure(error)
        raise OverlayEncodeError('runtime') from None
    if proc.returncode:
        report_overlay_failure(RuntimeError('encode'))
        raise OverlayEncodeError('encode')


def _grade_prefix(grade: str) -> str:
    if not grade or any(token in grade for token in (';', '[', ']', '\\', '\n')):
        return ''
    return grade if grade.endswith(',') else grade + ','


def composite_command(base: Path, overlay: Path, dest: Path, width: int, height: int, grade: str, encoder_name: str) -> list[str]:
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    graph = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},setsar=1,"
        f"{_grade_prefix(grade)}format=yuv420p[base];"
        f"[1:v]scale={width}:{height}:flags=lanczos,format=yuva444p[ov];"
        f"[base][ov]overlay=0:0:format=auto:shortest=1[out]"
    )
    return [
        get_ffmpeg_path(), '-v', 'error', '-i', str(base), '-i', str(overlay),
        '-filter_complex', graph, '-map', '[out]', *h264_args(width, height, encoder_name),
        '-an', '-y', str(dest),
    ]


def choose_encoder() -> str:
    """Probe NVENC, QSV, AMF and VideoToolbox once. Any probe failure falls through to libx264."""
    global _chosen
    forced = os.getenv('AUTOCLIP_VIDEO_ENCODER', '').strip().lower()
    if forced in {'x264', 'libx264', 'software'}:
        return SOFTWARE
    with _lock:
        if _chosen and _chosen not in _broken:
            return _chosen
        from backend.services.video_encoder import _works
        from backend.utils.ffmpeg_utils import get_ffmpeg_path
        ffmpeg = get_ffmpeg_path()
        picked = SOFTWARE
        for name in PROBE_ORDER:
            if name in _broken:
                continue
            try:
                works = _works(ffmpeg, name)
            except Exception as error:  # noqa: BLE001 - a probe must not fail the export
                logger.warning('Hardware encoder probe failed: %s', type(error).__name__)
                works = False
            if works:
                picked = name
                break
        _chosen = picked
        logger.info('Overlay encoder: %s', picked)
        return picked


def _run(cmd: list[str]):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def encode_picture(base: Path, overlay: Path, dest: Path, width: int, height: int, grade: str = '', run=None) -> dict:
    """Encode the composited picture. Hardware failure retries libx264 and still returns ok.

    When libx264 also fails, ``ok`` is false and ``failure_reason`` is ``encode``.
    The return value never contains a path or a caption.
    """
    runner = run or _run
    started = time.perf_counter()
    first = choose_encoder()

    def attempt(name: str):
        try:
            return runner(composite_command(base, overlay, dest, width, height, grade, name))
        except subprocess.TimeoutExpired:
            return None
        except OSError:
            return None

    proc = attempt(first)
    encoder = first
    if first != SOFTWARE and (proc is None or proc.returncode):
        with _lock:
            _broken.add(first)
            global _chosen
            _chosen = SOFTWARE
        proc = attempt(SOFTWARE)
        encoder = SOFTWARE
    ok = proc is not None and proc.returncode == 0
    if not ok:
        report_overlay_failure(OverlayEncodeError('encode'))
    return render_event({
        'encoder': encoder,
        'downgraded': False,
        'downgrade_reason': 'none',
        'failure_reason': 'none' if ok else 'encode',
        'outcome': 'completed' if ok else 'failed',
        'duration_ms': int((time.perf_counter() - started) * 1000),
        **host_facts(),
    }) | {'ok': ok, 'encoder': encoder}
