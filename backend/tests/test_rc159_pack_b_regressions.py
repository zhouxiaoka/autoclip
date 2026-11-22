"""1.5.9 Pack B regressions: DPAPI CookieLoadError, Whisper blob progress, platform subtitles, UTF-8 ffmpeg cut."""
from __future__ import annotations

import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import yt_dlp

from backend.pipeline.failures import PipelineFailure
from backend.services import simple_pipeline_adapter as spa
from backend.services import whisper_model_manager as wmm
from backend.services import whisper_runtime
from backend.services.studio import jobs
from backend.utils import download_recovery as dr


def test_cookie_load_error_without_permission_error_triggers_cookie_recovery(monkeypatch):
    calls = []

    class FakeYDL:
        def __init__(self, opts):
            self.opts = dict(opts)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def download(self, urls):
            calls.append(dict(self.opts))
            if self.opts.get('cookiesfrombrowser'):
                # Simulate Windows Chrome 127+ DPAPI / App-Bound Encryption CookieLoadError with NO PermissionError
                raise yt_dlp.cookies.CookieLoadError('Failed to decrypt with DPAPI (v20)')
            return 0

    monkeypatch.setattr(yt_dlp, 'YoutubeDL', FakeYDL)

    # Public YouTube URL should recover automatically by retrying without cookies
    result = dr.download_with_recovery(
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
        {'cookiesfrombrowser': ('chrome',)},
    )
    assert result == 0
    assert len(calls) == 2
    assert 'cookiesfrombrowser' in calls[0]
    assert 'cookiesfrombrowser' not in calls[1]

    # When cookie-less retry also fails with bot-check, must raise actionable COOKIE_ACCESS_HINT (not raw CookieLoadError)
    class AlwaysBlockedYDL(FakeYDL):
        def download(self, urls):
            if self.opts.get('cookiesfrombrowser'):
                raise yt_dlp.cookies.CookieLoadError('Failed to decrypt with DPAPI (v20)')
            raise yt_dlp.utils.DownloadError('Sign in to confirm you are not a bot')

    monkeypatch.setattr(yt_dlp, 'YoutubeDL', AlwaysBlockedYDL)
    with pytest.raises(PipelineFailure) as exc_info:
        dr.download_with_recovery(
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            {'cookiesfrombrowser': ('chrome',)},
        )
    assert exc_info.value.code == dr.SOURCE_BLOCKED_CODE
    assert exc_info.value.user_message() == dr.COOKIE_ACCESS_HINT


def test_whisper_download_updates_progress_from_blob_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(whisper_runtime, 'get_models_dir', lambda: tmp_path)
    monkeypatch.setattr(whisper_runtime, 'is_installed', lambda: True)

    manager = wmm.WhisperModelManager()
    cache_dir = manager._model_cache_dir('base')
    blobs = cache_dir / 'blobs'
    blobs.mkdir(parents=True)
    with manager._lock:
        manager._download_state['base'] = {'status': 'downloading', 'progress': 0, 'error': None}
    assert manager.get_model_info('base').download_progress == 0

    # Write ~30 MB into .incomplete blob (~20% of 145 MB base model)
    (blobs / 'abc123.incomplete').write_bytes(b'\0' * (30 * 1024 * 1024))
    info = manager.get_model_info('base')
    assert info is not None
    assert info.download_progress is not None
    assert 15 <= info.download_progress <= 25


def test_platform_subtitle_code_excludes_danmaku_and_live_chat():
    assert jobs._platform_subtitle_code({
        'language': 'zh',
        'subtitles': {'danmaku': [{'ext': 'xml'}], 'zh-CN': [{'ext': 'srt'}]},
    }) == 'zh-CN'
    assert jobs._platform_subtitle_code({
        'language': 'danmaku',
        'subtitles': {'danmaku': [{'ext': 'xml'}], 'live_chat': [{'ext': 'json'}]},
    }) is None


def test_cut_audio_window_passes_utf8_encoding_for_windows_gbk(tmp_path, monkeypatch):
    captured = {}

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        out = Path(cmd[-1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b'RIFF')
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    monkeypatch.setattr('subprocess.run', fake_run)
    monkeypatch.setattr('backend.utils.ffmpeg_utils.get_ffmpeg_path', lambda: 'ffmpeg')

    out_wav = tmp_path / 'cut.wav'
    spa._cut_audio_window(tmp_path / 'video.mp4', 0.0, 1800.0, out_wav)
    assert captured.get('encoding') == 'utf-8'
    assert captured.get('errors') in ('ignore', 'replace')
