"""HTML overlay capture and the ffv1 movie that follows it.

The page contract is ``setData`` / ``renderFrame`` / ``occupiedRects``. ``renderFrame``
returns a state hash. A frame whose hash matches the previous one is not captured
again. Two pages run at once, each owning a contiguous range of frames.

The overlay is ffv1 with alpha. The picture encode is ``video_encoder.run_with_fallback``:
it probes NVENC, QSV, AMF or VideoToolbox and retries libx264 veryfast. This module
does not choose that encoder. Capture and the ffv1 encode share one clip budget.
A failed encode deletes its partial file. The caller downgrades to classic.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from backend.core.project_cancellation import ProjectDeleted
from backend.services.studio.features import flag_enabled
from backend.services.studio.template_telemetry import host_facts, render_event
from backend.services.video_encoder import SOFTWARE

logger = logging.getLogger(__name__)

PAGES = 2
OVERLAY_CACHE_BYTES = 512 * 1024 * 1024


@dataclass
class OverlayJob:
    """A captured overlay, or a classic result. ``path`` is local and never logged."""

    path: Path | None
    template: str
    downgraded: bool
    downgrade_reason: str
    failure_reason: str
    outcome: str
    requested_template: str = 'classic'
    duration_ms: int = 0


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


def budget_seconds() -> float:
    """Per-clip overlay budget. ``AUTOCLIP_TEMPLATE_BUDGET_SEC`` overrides the 90s default."""
    raw = os.getenv('AUTOCLIP_TEMPLATE_BUDGET_SEC', '90').strip()
    try:
        value = float(raw)
    except ValueError:
        return 90.0
    if value < 1 or value > 600:
        return 90.0
    return value


def overlay_cache_limit() -> int:
    """Bytes kept under one project's overlay folder. The file just written stays."""
    raw = os.getenv('AUTOCLIP_OVERLAY_CACHE_BYTES', '').strip()
    if not raw:
        return OVERLAY_CACHE_BYTES
    try:
        value = int(raw)
    except ValueError:
        return OVERLAY_CACHE_BYTES
    if value < 1:
        return OVERLAY_CACHE_BYTES
    return value


def composite_tail(base_label: str, overlay_index: int, width: int, height: int, grade: str) -> tuple[str, str]:
    """Grade the base, then place the transparent overlay on top. Label is ``html``."""
    graph = (
        f"[{base_label}]{_grade_prefix(grade)}format=yuv420p[graded];"
        f"[{overlay_index}:v]scale={width}:{height}:flags=lanczos,format=yuva444p[ov];"
        f"[graded][ov]overlay=0:0:format=auto:shortest=1[html]"
    )
    return graph, 'html'


def overlay_cache_path(project_id: str, template: str, fill: dict) -> Path:
    """One file per template and fill. The name is a hash, not the caption."""
    from backend.services.studio.store import directory
    blob = json.dumps(fill, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    digest = hashlib.sha256(f'{template}|{blob}'.encode()).hexdigest()[:20]
    folder = directory(project_id) / 'output' / 'studio' / 'overlays'
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f'{digest}.mkv'


def _stamp(job: OverlayJob, started: float) -> OverlayJob:
    job.duration_ms = max(0, int((time.monotonic() - started) * 1000))
    return job


def _downgrade(reason: str, *, failure: str = 'none', requested: str = 'classic') -> OverlayJob:
    if reason == 'none' and failure in {'capture', 'encode'}:
        reason = failure
    if reason == 'rank':
        return OverlayJob(None, 'classic', False, 'rank', 'none', 'skipped', requested_template=requested)
    downgraded = reason not in {'none', 'flag_off'}
    if reason == 'flag_off':
        outcome = 'completed'
    elif downgraded:
        outcome = 'downgraded'
    else:
        outcome = 'failed' if failure != 'none' else 'completed'
    return OverlayJob(None, 'classic', downgraded, reason, failure, outcome, requested_template=requested)


def _enforce_overlay_cap(folder: Path, keep: Path | None = None) -> None:
    """Drop concat leftovers and the oldest movies until the folder is under the cap."""
    if not folder.is_dir():
        return
    keep_resolved = None
    if keep is not None:
        try:
            keep_resolved = keep.resolve()
        except OSError:
            keep_resolved = None
    for path in list(folder.iterdir()):
        if not path.is_file():
            continue
        if path.suffix == '.ffconcat' or path.name.endswith('.partial'):
            if keep_resolved is None or path.resolve() != keep_resolved:
                path.unlink(missing_ok=True)
    sized: list[tuple[Path, int]] = []
    total = 0
    for path in folder.glob('*.mkv'):
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        sized.append((path, size))
        total += size
    limit = overlay_cache_limit()
    if total <= limit:
        return
    for path, size in sorted(sized, key=lambda item: item[0].stat().st_mtime):
        try:
            if keep_resolved is not None and path.resolve() == keep_resolved:
                continue
        except OSError:
            continue
        path.unlink(missing_ok=True)
        total -= size
        if total <= limit:
            break


def _cache_usable(path: Path) -> bool:
    """A reusable overlay is a finished ffv1 movie with alpha, not a partial write."""
    if not path.is_file():
        return False
    try:
        if path.stat().st_size <= 0:
            return False
        from backend.utils.ffmpeg_utils import get_ffprobe_path
        probe = subprocess.run(
            [get_ffprobe_path(), '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=codec_name,pix_fmt', '-of', 'csv=p=0', str(path)],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0 and probe.stdout.strip() == 'ffv1,yuva444p'


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
    from backend.core import project_cancellation
    # A bound studio render must be able to kill this ffmpeg with the rest of the task.
    if project_cancellation.current():
        return project_cancellation.run(cmd, capture_output=True, text=True, timeout=timeout)
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


def _write_holds(frames: list[dict], folder: Path) -> list[tuple[Path, int]]:
    holds: list[tuple[Path, int]] = []
    for frame in frames:
        path = folder / f"{int(frame['index']):05d}.png"
        png = frame.get('png')
        if isinstance(png, (bytes, bytearray)):
            path.write_bytes(png)
        elif isinstance(png, Path):
            path.write_bytes(png.read_bytes())
        else:
            raise OverlayEncodeError('capture')
        holds.append((path, int(frame['count'])))
    return holds


async def _playwright_frames(template: str, fill: dict, frame_count: int, fps: int) -> list[dict]:
    from playwright.async_api import async_playwright

    from backend.services.packaging_runtime import launch_kwargs
    from backend.services.studio.templates.registry import ASSET_ROOT, get

    width, height = get(template).canvas.overlay_px
    page_url = (ASSET_ROOT / template / 'index.html').as_uri()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(**launch_kwargs())
        try:
            pages = []
            for _ordinal in range(min(PAGES, max(1, frame_count))):
                page = await browser.new_page(viewport={'width': width, 'height': height}, device_scale_factor=1)
                await page.goto(page_url)
                await page.evaluate('(fill) => window.setData(fill)', fill)
                pages.append(page)

            async def render(ordinal, seconds):
                digest = await pages[ordinal].evaluate('(t) => window.renderFrame(t)', seconds)
                return digest

            async def shoot(ordinal, index):
                return await pages[ordinal].screenshot(omit_background=True, type='png')

            return await capture_changed(frame_count, fps, render, shoot)
        finally:
            await browser.close()


async def _bounded_capture(template: str, fill: dict, frames: int, fps: int, capture):
    if capture is not None:
        produced = capture(frames, fps)
        if asyncio.iscoroutine(produced):
            produced = await produced
        return produced
    return await _playwright_frames(template, fill, frames, fps)


def prepare_overlay(project_id: str, template: str, packaging, duration: float, *, features: dict | None, safe_area: str = 'xiaohongshu', capture=None, clock=None) -> OverlayJob:
    """Capture the overlay, or return a classic result. This does not raise.

    ``capture(frame_count, fps)`` is the test seam. Without it, Playwright runs
    only when the packaging runtime is installed. The whole capture, including
    browser startup, and the ffv1 encode share ``budget_seconds()``. ``duration_ms``
    is that overlay work, not the rest of the render.
    """
    from backend.services.studio.overlay_fill import build_fill
    from backend.services.studio.template_choice import blocking_reason

    started_wall = time.monotonic()
    requested = template if template in {'editorial', 'street'} else 'classic'

    def finish(job: OverlayJob) -> OverlayJob:
        return _stamp(job, started_wall)

    reason = blocking_reason(features, runtime_ready=True if capture else None)
    if reason:
        return finish(_downgrade(reason, requested=requested))
    if template not in {'editorial', 'street'}:
        return finish(_downgrade('flag_off', requested=requested))
    fps = 30
    frames = max(1, int(round(max(0.1, float(duration)) * fps)))
    fill = build_fill(packaging, duration, fps=fps, safe_area=safe_area)
    dest = overlay_cache_path(project_id, template, fill)
    _enforce_overlay_cap(dest.parent)
    if _cache_usable(dest):
        return finish(OverlayJob(dest, template, False, 'none', 'none', 'completed', requested_template=template))
    dest.unlink(missing_ok=True)
    now = clock or time.monotonic
    budget_started = now()
    budget = budget_seconds()

    def remaining() -> float:
        return budget - (now() - budget_started)

    try:
        if remaining() <= 0:
            return finish(_downgrade('over_budget', requested=template))
        produced = asyncio.run(asyncio.wait_for(
            _bounded_capture(template, fill, frames, fps, capture),
            timeout=remaining(),
        ))
        left = remaining()
        if left <= 0:
            return finish(_downgrade('over_budget', requested=template))
        with tempfile.TemporaryDirectory(prefix='ac-overlay-') as temp:
            holds = _write_holds(produced, Path(temp))
            encode_ffv1(holds, dest, fps=fps, timeout=left)
    except ProjectDeleted:
        raise
    except (TimeoutError, asyncio.TimeoutError):
        return finish(_downgrade('over_budget', requested=template))
    except OverlayEncodeError as error:
        if error.reason == 'timeout' or remaining() <= 0:
            return finish(_downgrade('over_budget', requested=template))
        report_overlay_failure(error)
        return finish(_downgrade('missing_runtime' if error.reason == 'runtime' else 'none', failure=error.reason, requested=template))
    except Exception as error:  # noqa: BLE001 - a capture failure must not fail the export
        report_overlay_failure(error)
        return finish(_downgrade('none', failure='capture', requested=template))
    if not _cache_usable(dest):
        dest.unlink(missing_ok=True)
        return finish(_downgrade('none', failure='encode', requested=template))
    _enforce_overlay_cap(dest.parent, keep=dest)
    return finish(OverlayJob(dest, template, False, 'none', 'none', 'completed', requested_template=template))
