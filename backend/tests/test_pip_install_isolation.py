"""pip 安装不能拖住或带倒后端（1.5.7 Windows 桌面冒烟 S1 排查）。

- 事件循环在 pip 慢慢刷大量输出时仍然及时响应；
- pip 不继承后端的 stdin；Windows 上无窗口、独立进程组，POSIX 上独立会话。
在 Windows CI（windows-asyncio.yml）里也跑。
"""
import asyncio
import os
import subprocess
import sys
import threading
import time

from backend.services import pip_install
from backend.services.studio import framing

# conftest stubs start_install for every test; keep the real one.
REAL_START_INSTALL = framing.start_install

# A fake pip: lots of output (well past a pipe buffer), slowly, on stdout and stderr.
FAKE_PIP = r"""
import sys, time
for i in range(400):
    line = 'Downloading pkg%03d-1.0-cp313-cp313-win_amd64.whl (1.0 MB) ' % i + 'x' * 200
    (sys.stderr if i % 3 == 0 else sys.stdout).write(line + '\n')
    if i % 20 == 0:
        sys.stdout.flush(); sys.stderr.flush(); time.sleep(0.02)
sys.stdout.write('Successfully installed pkg\n')
"""


def test_event_loop_stays_responsive_while_pip_streams(tmp_path, monkeypatch):
    monkeypatch.setattr(framing, "_data_dir", lambda: tmp_path)
    seen = []

    async def main():
        loop = asyncio.get_running_loop()
        worker = threading.Thread(target=lambda: seen.append(pip_install.stream(
            [sys.executable, "-c", FAKE_PIP], 60, 30, lambda line, lines: None)), daemon=True)
        worker.start()
        worst = 0.0
        while worker.is_alive():
            start = loop.time()
            await asyncio.sleep(0.01)
            worst = max(worst, loop.time() - start)
        return worst

    worst = asyncio.run(main())
    code, lines = seen[0]
    assert code == 0
    assert lines[-1] == "Successfully installed pkg"
    # The loop never stalls behind the pip reader (generous bound for slow CI runners).
    assert worst < 0.5, worst


def test_framing_install_runs_off_the_event_loop(monkeypatch):
    """start_install from a coroutine returns at once; pip runs on its own thread."""
    started = threading.Event()
    release = threading.Event()
    monkeypatch.setattr(framing, "is_installed", lambda: False)
    monkeypatch.setattr(framing, "cooldown_remaining", lambda now=None: 0.0)
    monkeypatch.setattr(framing, "_do_install", lambda url: (started.set(), release.wait(5)))
    framing._set_state(status="unknown", progress=0, message="")

    async def main():
        t0 = time.monotonic()
        result = REAL_START_INSTALL()
        return result, time.monotonic() - t0

    try:
        result, took = asyncio.run(main())
        assert result["started"] is True and took < 0.5
        assert started.wait(2)
    finally:
        release.set()
        framing._set_state(status="unknown", progress=0, message="")



def test_pip_does_not_share_stdin_console_or_process_group(monkeypatch):
    kwargs = pip_install.spawn_kwargs()
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["stdout"] is subprocess.PIPE and kwargs["stderr"] is subprocess.STDOUT
    if os.name == "nt":
        flags = kwargs["creationflags"]
        assert flags & 0x08000000  # CREATE_NO_WINDOW
        assert flags & 0x00000200  # CREATE_NEW_PROCESS_GROUP
    else:
        assert kwargs["start_new_session"] is True


def test_pip_child_reads_eof_from_stdin():
    code, lines = pip_install.stream(
        [sys.executable, "-c", "import sys; print('stdin=%r' % sys.stdin.read())"], 30, 30)
    assert code == 0 and lines == ["stdin=''"]
