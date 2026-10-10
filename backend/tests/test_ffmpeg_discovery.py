"""应用外查找 ffmpeg：环境变量，然后安装包 resources，然后 PATH。"""
from pathlib import Path

from backend.utils import ffmpeg_utils


def _clear(monkeypatch):
    for name in ("AUTOCLIP_FFMPEG_PATH", "FFMPEG_PATH", "AUTOCLIP_FFPROBE_PATH", "FFPROBE_PATH"):
        monkeypatch.delenv(name, raising=False)
    ffmpeg_utils._reported_missing.clear()


def test_env_wins_over_bundled_resources_and_path(tmp_path, monkeypatch):
    _clear(monkeypatch)
    binary = tmp_path / "from-env"
    binary.write_bytes(b"")
    monkeypatch.setenv("AUTOCLIP_FFMPEG_PATH", str(binary))
    monkeypatch.setattr(ffmpeg_utils, "bundled_candidates", lambda *_args, **_kwargs: [tmp_path / "bundled"])
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda _name: str(tmp_path / "from-path"))
    assert ffmpeg_utils.get_ffmpeg_path() == str(binary)


def test_bundled_resources_win_over_path(tmp_path, monkeypatch):
    _clear(monkeypatch)
    bundled = tmp_path / "ffmpeg"
    bundled.write_bytes(b"")
    monkeypatch.setattr(ffmpeg_utils, "bundled_candidates", lambda *_args, **_kwargs: [bundled])
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda _name: "/usr/bin/ffmpeg")
    assert ffmpeg_utils.get_ffmpeg_path() == str(bundled)


def test_path_is_used_when_the_bundle_is_absent(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setattr(ffmpeg_utils, "bundled_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    assert ffmpeg_utils.get_ffmpeg_path() == "/usr/bin/ffmpeg"


def test_missing_ffmpeg_prints_the_lookup_order_once(monkeypatch, capsys):
    _clear(monkeypatch)
    monkeypatch.setattr(ffmpeg_utils, "bundled_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda _name: None)
    assert ffmpeg_utils.get_ffmpeg_path() == "ffmpeg"
    err = capsys.readouterr().err
    assert "AUTOCLIP_FFMPEG_PATH" in err
    assert "resources/ffmpeg" in err
    assert "PATH" in err
    assert "AUTOCLIP_FFPROBE_PATH" in err
    assert ffmpeg_utils.get_ffmpeg_path() == "ffmpeg"
    assert capsys.readouterr().err == ""


def test_windows_portable_python_points_at_resources_ffmpeg(tmp_path):
    exe = tmp_path / "resources" / "python" / "python.exe"
    binary = tmp_path / "resources" / "ffmpeg" / "ffmpeg.exe"
    probe = tmp_path / "resources" / "ffmpeg" / "ffprobe.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    ffmpeg_hits = {item.resolve() for item in ffmpeg_utils.bundled_candidates("ffmpeg", executable=str(exe), platform_name="nt")}
    probe_hits = {item.resolve() for item in ffmpeg_utils.bundled_candidates("ffprobe", executable=str(exe), platform_name="nt")}
    assert binary.resolve() in ffmpeg_hits
    assert probe.resolve() in probe_hits


def test_unix_portable_python_points_at_resources_ffmpeg(tmp_path):
    exe = tmp_path / "resources" / "python" / "bin" / "python3"
    binary = tmp_path / "resources" / "ffmpeg" / "ffmpeg"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    hits = {item.resolve() for item in ffmpeg_utils.bundled_candidates("ffmpeg", executable=str(exe), platform_name="posix")}
    assert binary.resolve() in hits


def test_a_real_bundle_next_to_python_beats_path(tmp_path, monkeypatch):
    _clear(monkeypatch)
    exe = tmp_path / "resources" / "python" / "bin" / "python3"
    binary = tmp_path / "resources" / "ffmpeg" / ffmpeg_utils.tool_filename("ffmpeg")
    exe.parent.mkdir(parents=True)
    binary.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    binary.write_bytes(b"")
    monkeypatch.setattr(ffmpeg_utils.sys, "executable", str(exe))
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda _name: "/usr/bin/ffmpeg")
    assert Path(ffmpeg_utils.get_ffmpeg_path()).resolve() == binary.resolve()


def test_ffprobe_uses_the_same_lookup(tmp_path, monkeypatch):
    _clear(monkeypatch)
    probe = tmp_path / "ffprobe"
    probe.write_bytes(b"")
    monkeypatch.setattr(
        ffmpeg_utils, "bundled_candidates",
        lambda base, *_args, **_kwargs: [probe] if base == "ffprobe" else [],
    )
    monkeypatch.setattr(ffmpeg_utils.shutil, "which", lambda _name: None)
    assert ffmpeg_utils.get_ffprobe_path() == str(probe)
