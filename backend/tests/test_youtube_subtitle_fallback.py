"""YouTube 备用字幕策略：视频已下载，重试时只取字幕，不再重复下载视频"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.api.v1 import youtube


class _RecordingYDL:
    calls = []

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def download(self, urls):
        _RecordingYDL.calls.append(self.opts)
        return 0


def test_subtitle_fallbacks_do_not_download_the_video(tmp_path, monkeypatch):
    _RecordingYDL.calls = []
    monkeypatch.setattr(youtube.yt_dlp, "YoutubeDL", _RecordingYDL)
    url = "https://www.youtube.com/watch?v=x"

    assert asyncio.run(youtube._try_download_with_different_formats(url, tmp_path)) == ""
    assert asyncio.run(youtube._try_download_with_different_langs(url, tmp_path)) == ""

    # 3 种格式 + 5 组语言，每次都只应下载字幕
    assert len(_RecordingYDL.calls) == 8
    for opts in _RecordingYDL.calls:
        assert opts.get("skip_download") is True
        assert "format" not in opts
