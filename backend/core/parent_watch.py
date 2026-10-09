"""Exit the desktop backend when the app that launched it is gone (RC156 #20).

On Windows the Tauri shell puts the backend in a Job Object that kills the whole tree when the
app dies. macOS has no equivalent: after `kill -9` of the app (or a crash) the bundled backend
kept running as an orphan, holding the port, the database and any ffmpeg/Whisper children.

The shell passes its own PID in `AUTOCLIP_PARENT_PID`. `start()` polls it and, once that
process is gone, runs the shutdown callback. Without the variable (CLI, MCP, Docker, dev runs,
`python -m backend.desktop_main` by hand) nothing is watched. The variable is removed from
`os.environ` so the backend's own children never inherit it.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

ENV = 'AUTOCLIP_PARENT_PID'
DEFAULT_INTERVAL = 2.0


def parent_pid_from_env(environ=None) -> Optional[int]:
    """The PID to watch, or None when not launched by the desktop shell. Consumes the variable."""
    environ = os.environ if environ is None else environ
    raw = environ.pop(ENV, None)
    if raw is None:
        return None
    try:
        pid = int(str(raw).strip())
    except ValueError:
        logger.warning('Ignoring invalid %s', ENV)
        return None
    if pid <= 1 or pid == os.getpid():
        logger.warning('Ignoring %s that is not a parent process', ENV)
        return None
    return pid


class ParentProbe:
    """Is the launching process still alive? PID reuse safe (psutil compares the start time)."""

    def __init__(self, pid: int):
        import psutil
        self.pid = pid
        # Launched directly by the shell: on POSIX a reparent (ppid changes) is the fastest signal.
        self.direct_child = os.name == 'posix' and os.getppid() == pid
        try:
            self._process = psutil.Process(pid)
        except psutil.Error:
            self._process = None  # already gone before we started watching

    def alive(self) -> bool:
        import psutil
        if self._process is None:
            return False
        if self.direct_child and os.getppid() != self.pid:
            return False
        try:
            return self._process.is_running() and self._process.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False
        except psutil.Error:
            return True  # access denied etc.: never shut down on an unclear answer


def start(on_parent_gone: Callable[[int], None], *, pid: Optional[int] = None, interval: float = DEFAULT_INTERVAL,
          environ=None) -> Optional[threading.Thread]:
    """Watch `pid` (default: AUTOCLIP_PARENT_PID) and call `on_parent_gone(pid)` once it exits."""
    pid = parent_pid_from_env(environ) if pid is None else pid
    if pid is None:
        return None
    try:
        probe = ParentProbe(pid)
    except Exception as error:  # noqa: BLE001 - psutil missing/broken: behave like before
        logger.warning('Parent watch unavailable: %s', type(error).__name__)
        return None
    stop = threading.Event()

    def loop():
        while probe.alive():
            if stop.wait(interval):
                return  # watch ended by the normal shutdown
        logger.warning('Desktop app (pid %s) is gone; shutting the backend down', pid)
        stop.set()
        on_parent_gone(pid)

    thread = threading.Thread(target=loop, name='autoclip-parent-watch', daemon=True)
    thread.stop = stop  # type: ignore[attr-defined] - tests and shutdown can end the watch
    thread.start()
    logger.info('Watching desktop app pid %s', pid)
    return thread


def terminate_children(timeout: float = 3.0) -> int:
    """Terminate every child of this process (ffmpeg, Whisper/SenseVoice runtimes, yt-dlp). Returns the count."""
    import psutil
    try:
        children = psutil.Process().children(recursive=True)
    except psutil.Error:
        return 0
    for child in children:
        try:
            child.terminate()
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs(children, timeout=timeout)
    for child in alive:
        try:
            child.kill()
        except psutil.Error:
            pass
    if alive:
        psutil.wait_procs(alive, timeout=timeout)
    return len(children)
