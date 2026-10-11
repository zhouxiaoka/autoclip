"""人物识别组件按需安装：并发只装一次，超时/锁文件只记 warning（1.5.7 Windows 验收 S4）。"""
import logging
import subprocess
import threading

import pytest

from backend.services.studio import framing

# conftest stubs start_install for every test so nothing runs pip; this test needs the real one.
REAL_START_INSTALL = framing.start_install


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setattr(framing, "get_install_dir", lambda: tmp_path / "framing-runtime")
    monkeypatch.setattr(framing, "is_installed", lambda: False)
    framing._set_state(status="unknown", progress=0, message="")
    yield
    framing._set_state(status="unknown", progress=0, message="")


def test_concurrent_starts_install_once(monkeypatch):
    started = []
    gate = threading.Event()

    def slow(index_url):
        started.append(index_url)
        gate.wait(2)

    monkeypatch.setattr(framing, "_do_install", slow)
    results = [REAL_START_INSTALL() for _ in range(5)]
    gate.set()
    assert [r["started"] for r in results] == [True, False, False, False, False]
    assert len(started) == 1


def test_timeout_is_a_warning_without_traceback(monkeypatch, caplog):
    def timeout(*a, **k):
        raise subprocess.TimeoutExpired(cmd="pip", timeout=framing.INSTALL_TIMEOUT)

    monkeypatch.setattr(framing.subprocess, "run", timeout)
    monkeypatch.setattr(framing.shutil, "rmtree", lambda *_: None)
    with caplog.at_level(logging.WARNING, logger=framing.logger.name):
        framing._do_install(None)
    assert framing._state["status"] == "error" and "超时" in framing._state["message"]
    records = [r for r in caplog.records if r.name == framing.logger.name]
    assert records and all(r.levelno == logging.WARNING and r.exc_info is None for r in records)


def test_locked_old_files_stop_cleanly(monkeypatch, caplog):
    def locked(*_):
        raise PermissionError(32, "The process cannot access the file because it is being used by another process")

    monkeypatch.setattr(framing.shutil, "rmtree", locked)
    called = []
    monkeypatch.setattr(framing.subprocess, "run", lambda *a, **k: called.append(1))
    with caplog.at_level(logging.WARNING, logger=framing.logger.name):
        framing._do_install(None)
    assert not called
    assert framing._state["status"] == "error" and "重启" in framing._state["message"]
    assert all(r.exc_info is None for r in caplog.records)


def test_pip_installs_wheels_only(monkeypatch):
    seen = {}

    def run(cmd, **kwargs):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 1, stdout="ERROR: no wheel", stderr="")

    monkeypatch.setattr(framing.subprocess, "run", run)
    monkeypatch.setattr(framing.shutil, "rmtree", lambda *_: None)
    framing._do_install("https://pypi.org/simple")
    assert "--only-binary=:all:" in seen["cmd"]
    assert seen["cmd"][-2:] == ["--index-url", "https://pypi.org/simple"]
