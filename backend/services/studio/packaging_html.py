"""HTML overlay capture and the ffv1 movie that follows it.

The page contract is ``setData`` / ``renderFrame`` / ``occupiedRects``. ``renderFrame``
returns a state hash. A frame whose hash matches the previous one is not captured
again. Two pages run at once, each owning a contiguous range of frames.

The overlay is ffv1 with alpha. The picture encode is ``video_encoder.run_with_fallback``:
it probes NVENC, QSV, AMF or VideoToolbox and retries libx264 veryfast. This module
does not choose that encoder. A failed overlay encode removes its partial file and
raises ``OverlayEncodeError``. The caller downgrades to classic.
"""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
from pathlib import Path

from backend.services.studio.features import flag_enabled
from backend.services.studio.template_telemetry import host_facts, render_event
from backend.services.video_encoder import SOFTWARE

logger = logging.getLogger(__name__)

PAGES = 2


class OverlayEncodeError(RuntimeError):
    """Encoder or capture failure. ``reason`` is an enum. The message is that enum."""

    def __init__(self, reason: str):
        self.reason = reason if reason in {'capture', 'encode', 'runtime', 'timeout', 'unknown'} else 'unknown'
        super().__init__(self.reason)


class HtmlRetry(Exception):
    """The overlay picture failed. Retry the clip once as classic packaging."""


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


def concat_quote(path: Path | str) -> str:
    """Concat-demuxer path. Quotes, spaces and backslashes are backslash-escaped."""
    escaped: list[str] = []
    for char in Path(path).as_posix():
        if char in "\\' \t\"#":
            escaped.append('\\')
        escaped.append(char)
    return ''.join(escaped)


def _concat_listing(holds: list[tuple[Path, int]], fps: int, listing: Path) -> None:
    lines: list[str] = []
    for path, count in holds:
        lines.append(f"file {concat_quote(path)}\n")
        lines.append(f"duration {count / fps:.6f}\n")
    if holds:
        lines.append(f"file {concat_quote(holds[-1][0])}\n")
    listing.write_text(''.join(lines), encoding='utf-8')


def _run(cmd: list[str], timeout: float):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def encode_ffv1(holds: list[tuple[Path, int]], dest: Path, fps: int = 30, *, timeout: float, run=None) -> None:
    """Write an ffv1 movie with alpha. ``holds`` is ``(png, frame count)`` in order.

    ``timeout`` is the seconds left in the clip budget. The listing lives in a
    temporary directory. Bytes land in a sibling partial file and replace ``dest``
    only after ffmpeg exits 0. A failure deletes the partial and leaves ``dest`` alone.
    """
    if not holds or fps <= 0:
        raise OverlayEncodeError('capture')
    if timeout <= 0:
        raise OverlayEncodeError('timeout')
    partial = dest.with_name(dest.name + '.partial')
    partial.unlink(missing_ok=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    replaced = False
    try:
        with tempfile.TemporaryDirectory(prefix='ac-ffconcat-') as temp:
            listing = Path(temp) / 'list.ffconcat'
            _concat_listing(holds, fps, listing)
            from backend.utils.ffmpeg_utils import get_ffmpeg_path
            cmd = [get_ffmpeg_path(), '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing), *ffv1_args(), '-f', 'matroska', '-y', str(partial)]
            try:
                proc = _run(cmd, timeout) if run is None else run(cmd)
            except subprocess.TimeoutExpired as error:
                report_overlay_failure(error)
                raise OverlayEncodeError('timeout') from None
            except OSError as error:
                report_overlay_failure(error)
                raise OverlayEncodeError('runtime') from None
            if proc.returncode:
                report_overlay_failure(RuntimeError('encode'))
                raise OverlayEncodeError('encode')
        os.replace(partial, dest)
        replaced = True
    finally:
        if not replaced:
            partial.unlink(missing_ok=True)


def _grade_prefix(grade: str) -> str:
    if not grade or any(token in grade for token in (';', '[', ']', '\\', '\n')):
        return ''
    return grade if grade.endswith(',') else grade + ','
