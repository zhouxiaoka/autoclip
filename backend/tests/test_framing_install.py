"""人物识别组件按需安装：并发只装一次；和 Whisper 同一套 PyPI→镜像回退；失败后冷却；警告不打堆栈。"""
import logging
import threading

import pytest

from backend.services import pip_install
from backend.services.studio import framing

# conftest stubs start_install for every test so nothing runs pip; these tests need the real one.
REAL_START_INSTALL = framing.start_install


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setattr(framing, "get_install_dir", lambda: tmp_path / "framing-runtime")
    monkeypatch.setattr(framing, "_data_dir", lambda: tmp_path)
    monkeypatch.setattr(framing, "is_installed", lambda: False)
    for name in ("AUTOCLIP_PIP_INDEX", "PIP_INDEX_URL"):
        monkeypatch.delenv(name, raising=False)
    framing._set_state(status="unknown", progress=0, message="")
    yield
    framing._set_state(status="unknown", progress=0, message="")


def _fake_pip(monkeypatch, codes):
    calls = []
    results = iter(codes)

    def stream(cmd, timeout, stall, on_line=None, env=None, **_):
        calls.append({"url": cmd[cmd.index("--index-url") + 1] if "--index-url" in cmd else None,
                      "timeout": timeout, "stall": stall, "cmd": cmd})
        return next(results), []

    monkeypatch.setattr(pip_install, "stream", stream)
    monkeypatch.setattr(framing.shutil, "rmtree", lambda *_: None)
    return calls


def test_concurrent_starts_install_once(monkeypatch):
    started = []
    gate = threading.Event()
    monkeypatch.setattr(framing, "_do_install", lambda url: (started.append(url), gate.wait(2)))
    results = [REAL_START_INSTALL() for _ in range(5)]
    gate.set()
    assert [r["started"] for r in results] == [True, False, False, False, False]
    assert len(started) == 1


def test_falls_back_from_pypi_to_mirror_with_whisper_budgets(monkeypatch):
    calls = _fake_pip(monkeypatch, [pip_install.TIMEOUT_EXIT, 0])
    monkeypatch.setattr(framing, "is_installed", lambda: True)
    framing._do_install(None)
    assert [c["url"] for c in calls] == ["https://pypi.org/simple", "https://pypi.tuna.tsinghua.edu.cn/simple"]
    assert [c["timeout"] for c in calls] == [pip_install.PIP_OFFICIAL_TIMEOUT_SECONDS, pip_install.PIP_MIRROR_TIMEOUT_SECONDS]
    assert all(c["stall"] == pip_install.PIP_STALL_SECONDS for c in calls)
    assert "--only-binary=:all:" in calls[0]["cmd"]
    assert framing._state["status"] == "installed"
    assert framing.cooldown_remaining() == 0


def test_pip_index_url_pins_one_index(monkeypatch):
    monkeypatch.setenv("PIP_INDEX_URL", "https://example.invalid/simple")
    calls = _fake_pip(monkeypatch, [pip_install.TIMEOUT_EXIT])
    framing._do_install(None)
    assert [c["url"] for c in calls] == ["https://example.invalid/simple"]
    assert calls[0]["timeout"] == pip_install.PIP_MIRROR_TIMEOUT_SECONDS


def test_failure_is_a_warning_and_starts_a_cooldown(monkeypatch, caplog):
    _fake_pip(monkeypatch, [pip_install.TIMEOUT_EXIT, pip_install.TIMEOUT_EXIT])
    with caplog.at_level(logging.INFO, logger=framing.logger.name):
        framing._do_install(None)
    assert framing._state["status"] == "error" and "镜像" in framing._state["message"]
    assert all(r.exc_info is None and r.levelno <= logging.WARNING for r in caplog.records)
    assert 29 * 60 < framing.cooldown_remaining() <= 30 * 60
    assert framing.get_status()["cooldown_seconds"] > 0


def test_auto_install_skips_during_cooldown_but_manual_reinstall_runs(monkeypatch, caplog):
    framing._remember_failure("安装失败：下载超时。")
    started = []
    monkeypatch.setattr(framing, "_do_install", lambda url: started.append(url))
    with caplog.at_level(logging.INFO, logger=framing.logger.name):
        auto = REAL_START_INSTALL()
    assert auto["started"] is False and auto["cooldown_seconds"] > 0
    assert not started
    assert [r.levelno for r in caplog.records if "不再自动重试" in r.getMessage()] == [logging.INFO]
    manual = REAL_START_INSTALL(manual=True)
    assert manual["started"] is True
    assert framing.cooldown_remaining() == 0


def test_cooldown_expires(monkeypatch):
    framing._remember_failure("x")
    import time
    assert framing.cooldown_remaining(now=time.time() + framing.AUTO_RETRY_COOLDOWN_SECONDS + 1) == 0


def test_locked_old_files_stop_cleanly(monkeypatch, caplog):
    def locked(*_):
        raise PermissionError(32, "The process cannot access the file because it is being used by another process")

    monkeypatch.setattr(framing.shutil, "rmtree", locked)
    called = []
    monkeypatch.setattr(pip_install, "stream", lambda *a, **k: called.append(1))
    with caplog.at_level(logging.WARNING, logger=framing.logger.name):
        framing._do_install(None)
    assert not called
    assert framing._state["status"] == "error" and "重启" in framing._state["message"]
    assert all(r.exc_info is None for r in caplog.records)
