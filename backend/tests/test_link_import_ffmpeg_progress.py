"""链接导入：yt-dlp 要拿到打包的 ffmpeg，下载期间要有真实进度。"""
from pathlib import Path

from backend.utils import ffmpeg_utils


def test_ytdlp_ffmpeg_options_uses_bundled_binary(tmp_path, monkeypatch):
    binary = tmp_path / "ffmpeg.exe"
    binary.write_bytes(b"")
    monkeypatch.setenv("AUTOCLIP_FFMPEG_PATH", str(binary))
    assert ffmpeg_utils.ytdlp_ffmpeg_options() == {"ffmpeg_location": str(binary)}


def test_ytdlp_ffmpeg_options_empty_when_unresolved(monkeypatch):
    monkeypatch.delenv("AUTOCLIP_FFMPEG_PATH", raising=False)
    monkeypatch.delenv("FFMPEG_PATH", raising=False)
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda _name: None)
    assert ffmpeg_utils.ytdlp_ffmpeg_options() == {}


def test_legacy_download_hook_maps_progress_monotonically(monkeypatch):
    from backend.api.v1 import youtube

    writes = []
    monkeypatch.setattr(youtube, "save_project_download_progress", lambda pid, value, msg: writes.append(value))
    hook = youtube.make_download_progress_hook("p1", "missing-task", min_interval=0)

    hook({"status": "downloading", "downloaded_bytes": 0, "total_bytes": 100})
    hook({"status": "downloading", "downloaded_bytes": 50, "total_bytes": 100})
    # 视频下完换音频，百分比回落，不能倒退
    hook({"status": "downloading", "downloaded_bytes": 10, "total_bytes": 100})
    hook({"status": "downloading", "downloaded_bytes": 100, "total_bytes_estimate": 100})
    hook({"status": "finished"})
    hook({"status": "downloading", "downloaded_bytes": 5})  # 没有总大小

    assert writes == sorted(writes)
    assert writes[0] > youtube.DOWNLOAD_PROGRESS_START
    assert writes[-1] < youtube.DOWNLOAD_PROGRESS_END


def test_studio_download_hook_writes_percent(monkeypatch):
    from backend.services.studio import jobs

    state = {"analysis": {"status": "running", "message": "准备素材"}}
    monkeypatch.setattr(jobs.store, "change", lambda _pid, mutate: mutate(state))
    hook = jobs.download_progress_hook("p1", min_interval=0)

    hook({"status": "downloading", "downloaded_bytes": 30, "total_bytes": 100})
    assert state["analysis"]["percent"] == 30
    hook({"status": "downloading", "downloaded_bytes": 10, "total_bytes": 100})
    assert state["analysis"]["percent"] == 30
    hook({"status": "downloading", "downloaded_bytes": 100, "total_bytes": 100})
    assert state["analysis"]["percent"] == 99  # 下完还要合并，不显示 100


def test_legacy_downloaders_pass_ffmpeg_and_mp4_merge():
    root = Path(__file__).resolve().parents[1]
    for rel in ("api/v1/youtube.py", "utils/bilibili_downloader.py"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "ytdlp_ffmpeg_options()" in text, rel
        assert "'merge_output_format': 'mp4'" in text, rel
