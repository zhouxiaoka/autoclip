"""New clips must be H.264/AAC so the in-app player is not a black frame."""

from pathlib import Path

from backend.utils.video_processor import VideoProcessor


def test_extract_clip_command_is_browser_safe_h264():
    cmd = VideoProcessor.build_extract_clip_command(
        "ffmpeg",
        Path("in.mp4"),
        Path("out.mp4"),
        "00:01:02.000",
        12.5,
    )
    assert cmd[0] == "ffmpeg"
    assert cmd[cmd.index("-ss") + 1] == "00:01:02.000"
    assert cmd[cmd.index("-t") + 1] == "12.500"
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv420p"
    assert cmd[cmd.index("-c:a") + 1] == "aac"
    assert "+faststart" in cmd[cmd.index("-movflags") + 1]
    assert "copy" not in cmd
    # Optional audio map: a video-only source should not fail the whole clip.
    assert "0:a:0?" in cmd


def test_extract_clip_invokes_browser_safe_command(monkeypatch, tmp_path: Path):
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)

        class Result:
            returncode = 0
            stderr = ""

        return Result()

    monkeypatch.setattr("backend.utils.video_processor.subprocess.run", fake_run)
    monkeypatch.setattr("backend.utils.video_processor.get_ffmpeg_path", lambda: "/usr/bin/ffmpeg")
    source = tmp_path / "source.mp4"
    source.write_bytes(b"not-a-real-video")
    output = tmp_path / "clips" / "clip.mp4"

    assert VideoProcessor.extract_clip(source, output, "00:00:01,000", "00:00:04,500") is True
    assert len(calls) == 1
    cmd = calls[0]
    assert cmd[0] == "/usr/bin/ffmpeg"
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "copy" not in cmd
    assert output.parent.is_dir()
