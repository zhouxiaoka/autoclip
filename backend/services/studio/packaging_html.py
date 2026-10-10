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
import hashlib
import json
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
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


@dataclass
class OverlayJob:
    """A captured overlay, or a classic downgrade. ``path`` is local and never logged."""

    path: Path | None
    template: str
    downgraded: bool
    downgrade_reason: str
    failure_reason: str
    outcome: str


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


def _downgrade(reason: str, *, failure: str = 'none') -> OverlayJob:
    if reason == 'none' and failure in {'capture', 'encode'}:
        reason = failure
    downgraded = reason not in {'none', 'flag_off'}
    if reason == 'flag_off':
        outcome = 'completed'
    elif downgraded:
        outcome = 'downgraded'
    else:
        outcome = 'failed' if failure != 'none' else 'completed'
    return OverlayJob(None, 'classic', downgraded, reason, failure, outcome)


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


async def _playwright_frames(template: str, fill: dict, frame_count: int, fps: int, stop) -> list[dict]:
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
                if stop():
                    raise OverlayEncodeError('timeout')
                digest = await pages[ordinal].evaluate('(t) => window.renderFrame(t)', seconds)
                return digest

            async def shoot(ordinal, index):
                return await pages[ordinal].screenshot(omit_background=True, type='png')

            return await capture_changed(frame_count, fps, render, shoot)
        finally:
            await browser.close()


def prepare_overlay(project_id: str, template: str, packaging, duration: float, *, features: dict | None, safe_area: str = 'xiaohongshu', capture=None, clock=None) -> OverlayJob:
    """Capture the overlay, or return a classic downgrade. This does not raise.

    ``capture(frame_count, fps)`` is the test seam. Without it, Playwright runs
    only when the packaging runtime is installed.
    """
    from backend.services.studio.overlay_fill import build_fill
    from backend.services.studio.template_choice import blocking_reason

    reason = blocking_reason(features, runtime_ready=True if capture else None)
    if reason:
        return _downgrade(reason)
    if template not in {'editorial', 'street'}:
        return _downgrade('flag_off')
    fps = 30
    frames = max(1, int(round(max(0.1, float(duration)) * fps)))
    fill = build_fill(packaging, duration, fps=fps, safe_area=safe_area)
    dest = overlay_cache_path(project_id, template, fill)
    if dest.is_file() and dest.stat().st_size > 0:
        return OverlayJob(dest, template, False, 'none', 'none', 'completed')
    now = clock or time.monotonic
    started = now()
    budget = budget_seconds()

    def stop() -> bool:
        return now() - started > budget

    try:
        if capture is not None:
            produced = capture(frames, fps)
            if asyncio.iscoroutine(produced):
                produced = asyncio.run(produced)
        else:
            produced = asyncio.run(_playwright_frames(template, fill, frames, fps, stop))
        if stop():
            return _downgrade('over_budget')
        with tempfile.TemporaryDirectory(prefix='ac-overlay-') as temp:
            holds = _write_holds(produced, Path(temp))
            encode_ffv1(holds, dest, fps=fps)
    except OverlayEncodeError as error:
        if error.reason == 'timeout' or stop():
            return _downgrade('over_budget')
        report_overlay_failure(error)
        return _downgrade('missing_runtime' if error.reason == 'runtime' else 'none', failure=error.reason)
    except Exception as error:  # noqa: BLE001 - a capture failure must not fail the export
        report_overlay_failure(error)
        return _downgrade('none', failure='capture')
    if not dest.is_file():
        return _downgrade('none', failure='capture')
    return OverlayJob(dest, template, False, 'none', 'none', 'completed')
