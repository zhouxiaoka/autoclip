"""Final output branding shared by Studio and legacy exports.

The outro is a designed 1.8 s animation (logo, wordmark, chime; source in design/outro-v5),
shipped pre-rendered in vertical and horizontal. It is conformed once per output spec (size,
frame rate, time base, audio layout) and cached, then joined to the content by stream copy.
"""
from __future__ import annotations

import hashlib
import json
import math
import logging
import os
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path
from pydantic import BaseModel, ConfigDict, StrictBool

from backend.services.publish_export import resolve_cjk_font
from backend.utils.ffmpeg_utils import get_ffmpeg_path, get_ffprobe_path

logger = logging.getLogger(__name__)
_unreadable_logged = False

OUTRO_SECONDS = 1.8
OUTRO_VERSION = "v5"
OUTRO_DIR = Path(__file__).resolve().parents[1] / 'assets' / 'outro'
OUTRO_BACKGROUND = '0x080809'  # the animation's own background, for padding other aspect ratios
_cache_lock = threading.Lock()


class BrandingSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: StrictBool = True


def settings_path() -> Path:
    from backend.core.path_utils import get_data_directory
    return get_data_directory() / 'output-branding.json'


def load_settings() -> BrandingSettings:
    path = settings_path()
    if not path.exists():
        return BrandingSettings()
    try:
        return BrandingSettings.model_validate_json(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        _warn_unreadable()
        return BrandingSettings()


def _warn_unreadable() -> None:
    global _unreadable_logged
    if _unreadable_logged:
        return
    _unreadable_logged = True
    logger.warning('output-branding.json is unreadable; outro stays on')


def save_settings(settings: BrandingSettings) -> BrandingSettings:
    settings = BrandingSettings.model_validate(settings.model_dump())
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f'.{uuid.uuid4().hex}.tmp')
    try:
        temporary.write_text(settings.model_dump_json(), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return settings


def _font_arg() -> str:
    font = resolve_cjk_font()
    if not font:
        return "font='Sans'"
    # Forward slashes: drawtext's option parser eats Windows backslashes (C:\\Windows\\Fonts\\...).
    path = str(font).replace('\\', '/').replace(':', r'\:').replace("'", r"\'")
    return f"fontfile='{path}'"


def _stream_params(source: Path) -> dict:
    """Video time base / fps and audio layout of the content, so the outro concatenates by copy."""
    raw = _ffmpeg([
        get_ffprobe_path(), '-v', 'error', '-show_entries', 'stream=codec_type,time_base,r_frame_rate,sample_rate,channels',
        '-of', 'json', str(source),
    ], timeout=30, text=True).stdout
    streams = json.loads(raw).get('streams', [])
    video = next((s for s in streams if s.get('codec_type') == 'video'), {})
    audio = next((s for s in streams if s.get('codec_type') == 'audio'), {})
    timescale = str(video.get('time_base', '1/15360')).split('/')[-1]
    return {
        'timescale': timescale if timescale.isdigit() else '15360',
        'fps': video.get('r_frame_rate') or '30',
        'sample_rate': str(audio.get('sample_rate') or 48000),
        'channels': int(audio.get('channels') or 2),
    }


def _cache_dir() -> Path:
    from backend.core.path_utils import get_data_directory
    path = get_data_directory() / 'cache' / 'outro'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _designed_outro(width: int, height: int, params: dict) -> Path | None:
    """The animation conformed to this output, from the cache when it was made before."""
    asset = OUTRO_DIR / ('outro-vertical.mp4' if height > width else 'outro-horizontal.mp4')
    if not asset.is_file():
        return None
    key = hashlib.sha1(json.dumps([OUTRO_VERSION, asset.stat().st_size, width, height, params], sort_keys=True).encode()).hexdigest()[:16]
    target = _cache_dir() / f'{key}.mp4'
    with _cache_lock:
        if target.is_file() and target.stat().st_size:
            return target
        layout = 'mono' if params['channels'] == 1 else 'stereo'
        partial = target.with_suffix('.part.mp4')
        _ffmpeg([
            get_ffmpeg_path(), '-v', 'error', '-i', str(asset),
            '-vf', f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={OUTRO_BACKGROUND},fps={params['fps']},format=yuv420p",
            '-af', f"aresample={params['sample_rate']},aformat=channel_layouts={layout}",
            '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-r', params['fps'], '-video_track_timescale', params['timescale'],
            '-c:a', 'aac', '-b:a', '160k', '-ar', params['sample_rate'], '-ac', str(params['channels']),
            '-movflags', '+faststart', '-y', str(partial),
        ], timeout=120)
        os.replace(partial, target)
        return target


def append_outro(source: Path, destination: Path, *, width: int, height: int, enabled: bool = True, report: dict | None = None) -> bool:
    """Append the branded outro atomically. If branding fails, the video is delivered without it:
    a finished render must never be lost to the end card. ``report['outro_seconds']`` receives the
    duration of the outro actually used, so the caller can verify body + outro."""
    partial = destination.with_name(f'{destination.stem}.branding.part.mp4')
    partial.unlink(missing_ok=True)
    if not enabled:
        os.replace(source, destination)
        return False
    try:
        seconds = _append(source, partial, width, height)
        if not (isinstance(seconds, float) and math.isfinite(seconds) and seconds > 0):
            raise OutroDurationUnavailable('invalid_duration')
        os.replace(partial, destination)
        if report is not None:
            report['outro_seconds'] = seconds
        return True
    except (OSError, subprocess.SubprocessError, ValueError, KeyError) as error:
        # no paths or command lines in the log, only the error class and a fixed reason.
        reason = error.reason if isinstance(error, OutroDurationUnavailable) else type(error).__name__
        logging.getLogger(__name__).warning('Outro skipped: %s', reason)
        partial.unlink(missing_ok=True)
        os.replace(source, destination)
        return False


class OutroDurationUnavailable(ValueError):
    """the outro's own duration could not be proven, so it is treated as not added."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _ffmpeg(cmd: list[str], timeout: float, **kwargs) -> subprocess.CompletedProcess:
    """Every branding child (ffprobe, outro conform, text outro, concat) starts here.

    Bound renders use the project process group so cancel reaches the child. Once the
    desktop shell exits (``begin_shutdown``) no new child may start, bound or not —
    check and spawn share ``project_cancellation``'s lock with ``begin_shutdown``.
    """
    from backend.core import project_cancellation
    return project_cancellation.run(cmd, check=True, capture_output=True, timeout=timeout, **kwargs)


def _media_seconds(path: Path) -> float | None:
    """Video stream duration of the outro actually concatenated (format duration as fallback)."""
    raw = _ffmpeg([
        get_ffprobe_path(), '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=duration:format=duration',
        '-of', 'json', str(path),
    ], timeout=30, text=True).stdout
    data = json.loads(raw or '{}')
    for value in [*(s.get('duration') for s in data.get('streams', [])), (data.get('format') or {}).get('duration')]:
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            continue
        if seconds > 0:
            return seconds
    return None


def _append(source: Path, partial: Path, width: int, height: int) -> float:
    with tempfile.TemporaryDirectory(prefix='ac-outro-') as tmp:
        concat = Path(tmp) / 'concat.txt'
        ffmpeg = get_ffmpeg_path()
        params = _stream_params(source)
        # Stream copy concat keeps packet timestamps in each file's own time base; the outro
        # must share the content's video timescale and frame rate or its frames collapse.
        try:
            outro = _designed_outro(width, height, params)
        except (OSError, subprocess.SubprocessError):
            outro = None
        if outro is None:
            outro = Path(tmp) / 'outro.mp4'
            _text_outro(outro, width, height, params)
        # prove the outro duration before concatenating. A probe timeout, garbage
        # output or empty duration means the outro is not added (the validated body ships).
        try:
            seconds = _media_seconds(outro)
        except subprocess.TimeoutExpired as error:
            raise OutroDurationUnavailable('probe_timeout') from error
        except (OSError, subprocess.SubprocessError) as error:
            raise OutroDurationUnavailable('probe_failed') from error
        except ValueError as error:
            raise OutroDurationUnavailable('probe_unreadable') from error
        if seconds is None or not math.isfinite(seconds) or seconds <= 0:
            raise OutroDurationUnavailable('probe_empty_duration')
        quote = lambda path: str(path).replace("'", "'\\''")  # noqa: E731 - concat list syntax for an apostrophe in a path
        concat.write_text(f"file '{quote(source)}'\nfile '{quote(outro)}'\n", encoding='utf-8')
        _ffmpeg([
            ffmpeg, '-v', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat), '-map', '0:v:0', '-map', '0:a:0?',
            '-c', 'copy', '-movflags', '+faststart', '-y', str(partial),
        ], timeout=120)
        return float(seconds)


def _text_outro(outro: Path, width: int, height: int, params: dict) -> None:
    """Fallback when the designed animation is missing: one dark second with the credit line."""
    ffmpeg = get_ffmpeg_path()
    layout = 'mono' if params['channels'] == 1 else 'stereo'
    drawtext = f"drawtext={_font_arg()}:text='Made with AutoClip':x=(w-text_w)/2:y=(h-text_h)/2:fontsize={max(22, round(width * .035))}:fontcolor=white"
    _ffmpeg([
        ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', f"color=c=0x1A1A19:s={width}x{height}:d=1:r={params['fps']}",
        '-f', 'lavfi', '-i', f"anullsrc=channel_layout={layout}:sample_rate={params['sample_rate']}", '-t', '1',
        '-vf', drawtext, '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', params['fps'],
        '-video_track_timescale', params['timescale'],
        '-c:a', 'aac', '-b:a', '160k', '-ar', params['sample_rate'], '-ac', str(params['channels']),
        '-movflags', '+faststart', '-y', str(outro),
    ], timeout=60)
