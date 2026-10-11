"""pip 子进程不能比后端活得久（1.5.7 Windows S3）。

后端不是桌面壳拉起的（没有 Tauri 的 Job Object）时，后端退出后 pip 还活了约 5 分钟。
这里用一个“像后端的”父进程跑假 pip，然后杀掉父进程，断言 pip 几秒内消失。
也在 Windows CI 上跑（test_framing_concurrency.py 导入）。
"""
import os
import signal
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import psutil
import pytest

from backend.services import child_guard, pip_install

ROOT = Path(__file__).resolve().parents[2]
FAKE_PIP = "import os, sys, time; print('PIP_PID=%d' % os.getpid(), flush=True); time.sleep(120)"

PARENT = textwrap.dedent(f"""
    import sys
    sys.path.insert(0, {str(ROOT)!r})
    from backend.services import child_guard, pip_install
    child_guard.install_hooks()
    def on_line(line, lines):
        print(line, flush=True)
    pip_install.stream([sys.executable, '-c', {FAKE_PIP!r}], 300, 300, on_line, owner='framing')
""")


def _start_parent():
    parent = subprocess.Popen([sys.executable, "-c", PARENT], stdout=subprocess.PIPE, text=True,
                              stdin=subprocess.DEVNULL)
    deadline = time.monotonic() + 30
    pid = None
    while time.monotonic() < deadline:
        line = parent.stdout.readline()
        if line.startswith("PIP_PID="):
            pid = int(line.split("=", 1)[1])
            break
        if not line and parent.poll() is not None:
            break
    assert pid, "fake pip never started"
    assert psutil.pid_exists(pid)
    return parent, pid


def _gone(pid: int, seconds: float = 8.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                return True
        except psutil.NoSuchProcess:
            return True
        time.sleep(0.1)
    return False


def _cleanup(pid: int) -> None:
    try:
        psutil.Process(pid).kill()
    except psutil.Error:
        pass


@pytest.mark.skipif(sys.platform == "darwin", reason="macOS has no Job Object / PDEATHSIG for kill -9")
def test_pip_dies_when_backend_is_killed_hard():
    """Windows: TerminateProcess -> job handle closes. Linux: SIGKILL -> PDEATHSIG."""
    parent, pid = _start_parent()
    try:
        parent.kill()
        parent.wait(10)
        assert _gone(pid), "pip outlived the killed backend"
    finally:
        _cleanup(pid)


@pytest.mark.skipif(os.name == "nt", reason="SIGTERM is POSIX; Windows is covered by the hard-kill test")
def test_pip_dies_when_backend_gets_sigterm():
    parent, pid = _start_parent()
    try:
        parent.send_signal(signal.SIGTERM)
        parent.wait(10)
        assert _gone(pid), "pip outlived the terminated backend"
    finally:
        _cleanup(pid)


def _run_in_thread(owner):
    result = {}
    lines_seen = threading.Event()

    def on_line(line, _lines):
        if line.startswith("PIP_PID="):
            result["pid"] = int(line.split("=", 1)[1])
            lines_seen.set()

    def work():
        result["out"] = pip_install.stream([sys.executable, "-c", FAKE_PIP], 300, 300, on_line, owner=owner)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    assert lines_seen.wait(30)
    return thread, result


def test_cancel_kills_pip_and_reports_cancel():
    thread, result = _run_in_thread("framing")
    assert child_guard.live("framing")
    assert pip_install.cancel("framing") == 1
    thread.join(10)
    assert not thread.is_alive()
    assert result["out"][0] == pip_install.CANCEL_EXIT
    assert _gone(result["pid"])
    assert child_guard.live("framing") == []


def test_cancel_only_hits_its_owner_and_does_not_leak_into_next_run():
    thread, result = _run_in_thread("whisper")
    try:
        assert pip_install.cancel("framing") == 0
        assert child_guard.live("whisper")
    finally:
        pip_install.cancel("whisper")
        thread.join(10)
    # A cancel with nothing running must not cancel the next install.
    pip_install.cancel("framing")
    code, lines = pip_install.stream([sys.executable, "-c", "print('ok')"], 30, 30, owner="framing")
    assert code == 0 and lines == ["ok"]


def test_shutdown_kills_every_live_pip():
    thread, result = _run_in_thread("whisper")
    assert child_guard.kill_all() >= 1
    thread.join(10)
    assert _gone(result["pid"])


def test_framing_cancel_does_not_start_a_cooldown(tmp_path, monkeypatch):
    from backend.services.studio import framing
    monkeypatch.setattr(framing, "_data_dir", lambda: tmp_path)
    monkeypatch.setattr(pip_install, "run_plan", lambda *a, **k: (pip_install.CANCEL_EXIT, ["pypi: 已取消"]))
    monkeypatch.setattr(framing, "is_installed", lambda: False)
    framing._do_install(None)
    assert framing.get_status()["status"] == "not_installed"
    assert framing.cooldown_remaining() == 0
    framing._set_state(status="unknown", progress=0, message="")
