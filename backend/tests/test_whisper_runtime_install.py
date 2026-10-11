"""Whisper 运行时安装：只装 wheel，Windows 钉版本，源码编译立刻停，官方源失败换镜像。"""
import sys

import pytest

from backend.services import whisper_runtime as wr


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    for name in ("AUTOCLIP_PIP_INDEX", "PIP_INDEX_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(wr, "_data_dir", lambda: tmp_path)
    wr._set_state(status="unknown", progress=0, message="", log_tail="")


def test_command_installs_wheels_only_with_windows_pins():
    cmd = wr.pip_command("https://pypi.org/simple")
    assert "--only-binary=:all:" in cmd
    assert cmd[cmd.index("--timeout") + 1] == "30"
    assert cmd[-2:] == ["--index-url", "https://pypi.org/simple"]
    packages = [c for c in cmd if "==" in c or "<" in c]
    assert "faster-whisper==1.2.1" in packages
    for pin in ("av==18.1.0", "ctranslate2==4.8.2", "onnxruntime==1.31.0", "tokenizers==0.23.3"):
        assert f'{pin}; sys_platform == "win32"' in packages
    # PyAV 19 dropped av.open(metadata_errors=...)
    assert "av>=11,<19" in packages


def test_index_plan_tries_pypi_then_mirror_and_respects_pip_index_url(monkeypatch):
    assert [label for label, _ in wr.index_plan(None)] == ["pypi", "mirror"]
    monkeypatch.setenv("PIP_INDEX_URL", "https://example.invalid/simple")
    assert wr.index_plan(None) == [("custom", "https://example.invalid/simple")]


def _script(lines, code=0):
    body = ";".join(f"print({line!r}, flush=True)" for line in lines)
    return [sys.executable, "-c", f"{body};import sys;sys.exit({code})"]


def test_source_build_stops_immediately():
    code, lines = wr._stream(_script(["Collecting av<19", "Building wheel for av (pyproject.toml): started", "never"], 0), 30, 30)
    assert code == wr.SOURCE_BUILD_EXIT
    assert "never" not in lines


def test_missing_wheel_is_reported_as_such():
    code, _ = wr._stream(_script(["ERROR: Could not find a version that satisfies the requirement av==18.1.0"], 1), 30, 30)
    assert code == wr.NO_WHEEL_EXIT
    assert "预编译包" in wr._failure_message(code, ["pypi: 没有可用 wheel"])


def test_silent_pip_times_out():
    code, _ = wr._stream([sys.executable, "-c", "import time;time.sleep(5)"], 30, 0.5)
    assert code == wr.TIMEOUT_EXIT


def test_falls_back_to_mirror_and_reports_clear_errors(monkeypatch):
    calls = []

    def fake(cmd, timeout, stall, **_):
        calls.append((cmd[cmd.index("--index-url") + 1], timeout))
        return wr.SOURCE_BUILD_EXIT, []

    monkeypatch.setattr(wr, "_stream", fake)
    monkeypatch.setattr(wr, "is_installed", lambda: False)
    wr._do_install(None)
    assert [url for url, _ in calls] == ["https://pypi.org/simple", "https://pypi.tuna.tsinghua.edu.cn/simple"]
    assert calls[0][1] < calls[1][1]
    status = wr._state
    assert status["status"] == "error"
    assert "源码编译" in status["message"]
    assert "源码编译" in wr._read_install_error()


def test_success_on_mirror_clears_error(monkeypatch):
    results = iter([wr.TIMEOUT_EXIT, 0])
    monkeypatch.setattr(wr, "_stream", lambda cmd, timeout, stall, **_: (next(results), []))
    monkeypatch.setattr(wr, "is_installed", lambda: True)
    wr._write_install_error("old")
    wr._do_install(None)
    assert wr._state["status"] == "installed"
    assert wr._read_install_error() == ""
