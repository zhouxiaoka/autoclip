"""链接导入：yt-dlp 要拿到打包的 ffmpeg，下载期间要有真实进度。"""
from pathlib import Path

from backend.utils import ffmpeg_utils


def test_ytdlp_ffmpeg_options_uses_bundled_binary(tmp_path, monkeypatch):
    binary = tmp_path / "ffmpeg.exe"
    binary.write_bytes(b"")
    monkeypatch.setenv("AUTOCLIP_FFMPEG_PATH", str(binary))
    assert ffmpeg_utils.ytdlp_ffmpeg_options()["ffmpeg_location"] == str(binary)


def test_ytdlp_options_enable_every_js_runtime_found(monkeypatch):
    monkeypatch.delenv("AUTOCLIP_FFMPEG_PATH", raising=False)
    monkeypatch.delenv("FFMPEG_PATH", raising=False)
    monkeypatch.setattr(ffmpeg_utils, "bundled_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(ffmpeg_utils, "_report_missing", lambda _name: None)
    found = {"node": "/usr/local/bin/node", "bun": "/opt/bun"}
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda name: found.get(name))
    assert ffmpeg_utils.ytdlp_ffmpeg_options() == {
        "js_runtimes": {"node": {"path": "/usr/local/bin/node"}, "bun": {"path": "/opt/bun"}},
    }


def test_ytdlp_js_runtimes_are_valid_for_yt_dlp(monkeypatch):
    import yt_dlp
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda name: f"/bin/{name}" if name == "node" else None)
    with yt_dlp.YoutubeDL({"quiet": True, **ffmpeg_utils.ytdlp_js_runtimes()}) as ydl:
        assert "node" in ydl.params["js_runtimes"]


def test_ytdlp_ffmpeg_options_empty_when_unresolved(monkeypatch):
    monkeypatch.delenv("AUTOCLIP_FFMPEG_PATH", raising=False)
    monkeypatch.delenv("FFMPEG_PATH", raising=False)
    monkeypatch.setattr(ffmpeg_utils, "bundled_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(ffmpeg_utils, "_report_missing", lambda _name: None)
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
    hook({"status": "finished"})  # 单个文件下完，还没进入合并
    assert state["analysis"]["percent"] == 99
    assert state["analysis"]["message"] == "准备素材"


def test_studio_merge_hook_clears_capped_download_percent(monkeypatch):
    from backend.services.studio import jobs

    state = {"analysis": {"status": "running", "message": "准备素材", "percent": 99}}
    monkeypatch.setattr(jobs.store, "change", lambda _pid, mutate: mutate(state))
    hook = jobs.download_progress_hook("p1", min_interval=0)

    hook({"status": "started", "postprocessor": "SubtitlesConvertor"})
    assert state["analysis"]["message"] == "准备素材"
    assert state["analysis"]["percent"] == 99

    hook({"status": "started", "postprocessor": "Merger"})
    assert state["analysis"]["message"] == jobs.MERGE_MESSAGE == "正在合并音视频"
    assert "percent" not in state["analysis"]
    # 合并期间再来的下载百分比不能把 99 写回去
    hook({"status": "downloading", "downloaded_bytes": 100, "total_bytes": 100})
    hook({"status": "finished", "postprocessor": "Merger"})
    hook({"status": "started", "postprocessor": "VideoRemuxer"})
    assert state["analysis"]["message"] == "正在合并音视频"
    assert "percent" not in state["analysis"]


def test_studio_download_registers_the_same_hook_for_postprocess(monkeypatch, tmp_path):
    from backend.services.studio import jobs

    captured = {}

    def capture(_url, options):
        captured["progress"] = options.get("progress_hooks")
        captured["post"] = options.get("postprocessor_hooks")
        raise RuntimeError("stop-after-options")

    monkeypatch.setattr(jobs.store, "directory", lambda _pid: tmp_path)
    monkeypatch.setattr("backend.utils.ffmpeg_utils.get_ffmpeg_path", lambda: "ffmpeg")
    monkeypatch.setattr("backend.utils.ffmpeg_utils.ytdlp_js_runtimes", lambda: {})
    monkeypatch.setattr("backend.utils.download_recovery.download_with_recovery", capture)
    try:
        jobs.download("p1", "https://example.com/v", None)
    except RuntimeError as error:
        assert str(error) == "stop-after-options"
    else:
        raise AssertionError("download continued past option capture")
    assert captured["progress"] and captured["progress"] == captured["post"]


def test_legacy_downloaders_pass_ffmpeg_and_mp4_merge():
    root = Path(__file__).resolve().parents[1]
    for rel in ("api/v1/youtube.py", "utils/bilibili_downloader.py"):
        text = (root / rel).read_text(encoding="utf-8")
        assert "ytdlp_ffmpeg_options()" in text, rel
        assert "'merge_output_format': 'mp4'" in text, rel
