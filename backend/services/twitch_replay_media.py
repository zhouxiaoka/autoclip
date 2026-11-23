"""Opt-in desktop experiment for acquiring an owned, public, ended Twitch replay."""
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

from fastapi import HTTPException

from backend.services.studio.preflight import probe_material
from backend.utils.ffmpeg_utils import get_ffmpeg_path

_active = threading.Lock()


def enabled():
    return os.getenv('AUTOCLIP_TWITCH_REPLAY_PILOT', '1') != '0'


def duration_seconds(raw):
    match = re.fullmatch(r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?', raw or '')
    if not match:
        raise ValueError('Platform duration unavailable.')
    h, m, s = (int(v or 0) for v in match.groups())
    result = h * 3600 + m * 60 + s
    if not result:
        raise ValueError('Platform duration unavailable.')
    return result


def download_archive(video_id, directory, *, progress_hooks=None):
    if not re.fullmatch(r'[0-9]{1,20}', video_id):
        raise ValueError('Invalid Twitch video ID.')
    path = directory / 'replay.mp4'
    logger = logging.Logger('replay-download')
    logger.addHandler(logging.NullHandler())

    def check_space(_):
        if shutil.disk_usage(directory).free < 512 * 1024 * 1024:
            raise ValueError('Insufficient disk space.')

    def match_archive(info, *, incomplete=False):
        if not incomplete and info.get('id') != 'v' + video_id:
            return 'Unexpected archive identity.'
        if info.get('is_live') or info.get('has_drm'):
            return 'Unavailable archive.'
        return None

    hooks = [check_space, *(progress_hooks or ())]
    from yt_dlp import YoutubeDL
    with YoutubeDL({'format': 'best[ext=mp4][vcodec!=none][acodec!=none]', 'outtmpl': str(path),
                    'logger': logger, 'quiet': True, 'noprogress': True, 'cachedir': False,
                    'noplaylist': True, 'skip_unavailable_fragments': False, 'hls_prefer_native': True,
                    'socket_timeout': 15, 'fragment_retries': 2, 'retries': 2,
                    'ffmpeg_location': get_ffmpeg_path(), 'progress_hooks': hooks,
                    'match_filter': match_archive}) as downloader:
        info = downloader.extract_info('https://www.twitch.tv/videos/' + video_id, download=True)
    if not info or info.get('id') != 'v' + video_id or not path.is_file():
        raise ValueError('Selected archive was not downloaded.')
    return path


def check_recording(path, expected):
    media = probe_material(path)
    tolerance = max(5.0, expected * 0.015)
    if (not media.width or not media.height or not media.audio or not media.duration
            or not math.isfinite(media.duration) or abs(media.duration - expected) > tolerance):
        raise ValueError('Incomplete recording or missing video/audio.')
    for start in (0, max(0, media.duration - 1)):
        subprocess.run([get_ffmpeg_path(), '-nostdin', '-v', 'error', '-xerror', '-ss', str(start),
                        '-i', str(path), '-t', '1', '-map', '0:v:0', '-map', '0:a:0',
                        '-f', 'null', '-'], check=True, capture_output=True, timeout=45)
    return media


def download_for_project(video_id, duration, destination_dir, *, progress_hook=None, checkpoint=None):
    """Download and verify a Twitch replay directly into a project's raw dir with progress & cancellation."""
    expected = duration_seconds(duration)
    destination_dir = Path(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    hooks = []
    if checkpoint is not None:
        hooks.append(lambda _data: checkpoint())
    if progress_hook is not None:
        hooks.append(progress_hook)
    with tempfile.TemporaryDirectory(dir=destination_dir, prefix='twitch-') as temporary:
        if checkpoint is not None:
            checkpoint()
        path = download_archive(video_id, Path(temporary), progress_hooks=hooks)
        if checkpoint is not None:
            checkpoint()
        check_recording(path, expected)
        target = destination_dir / 'input.mp4'
        path.replace(target)
        return target


def stage(video_id, duration, staging):
    """Return only a completed, checked file. Failed and partial transfers stay temporary."""
    if not _active.acquire(blocking=False):
        raise HTTPException(409, 'replay_download_busy')
    try:
        expected = duration_seconds(duration)
        staging.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=staging) as temporary:
            path = download_archive(video_id, Path(temporary))
            check_recording(path, expected)
            staged = staging / (uuid.uuid4().hex + '.mp4')
            path.replace(staged)
            return staged
    except Exception:
        raise HTTPException(422, 'replay_download_failed') from None
    finally:
        _active.release()
