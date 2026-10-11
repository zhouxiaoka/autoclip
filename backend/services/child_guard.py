"""Children that must not outlive the backend (pip installs; 1.5.7 Windows S3).

Under the desktop app the Tauri shell's Job Object already kills the whole tree. Started any other
way (`python -m backend.desktop_main`, CLI, MCP, dev) nothing did: a pip child kept running for
minutes after the backend exited.

- Windows: every guarded child is assigned to one backend-owned Job Object with
  JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE. The handle is never inherited, so when the backend process
  goes away for any reason (exit, crash, TerminateProcess) the kernel closes it and kills the
  children. Nested jobs (inside the Tauri job) work on Windows 8+.
- Linux: PR_SET_PDEATHSIG(SIGKILL) in the child, so it dies with the backend even after kill -9.
- POSIX: the child leads its own session; atexit and SIGTERM/SIGINT kill those process groups.
- Everywhere: a registry of live children; `kill_all()` on shutdown and `kill(owner)` on cancel.
"""
from __future__ import annotations

import atexit
import logging
import os
import signal
import subprocess
import sys
import threading
from typing import Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_live: dict[subprocess.Popen, str] = {}
_job = None
_hooks_installed = False


# ---------------------------------------------------------------- Windows Job Object
def _windows_job():
    """The backend's kill-on-close job (created once). None when unavailable."""
    global _job
    if _job is not None:
        return _job or None
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class BASIC(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                        ("SchedulingClass", wintypes.DWORD)]

        class EXTENDED(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        handle = kernel32.CreateJobObjectW(None, None)  # default security: not inheritable
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = EXTENDED()
        info.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        _job = (kernel32, handle)
    except Exception as error:  # noqa: BLE001 - fall back to the registry + atexit
        logger.warning("Job Object unavailable, pip children rely on shutdown cleanup: %s", error)
        _job = False
        return None
    return _job


def _assign_to_job(proc: subprocess.Popen) -> bool:
    job = _windows_job()
    if not job:
        return False
    kernel32, handle = job
    if not kernel32.AssignProcessToJobObject(handle, int(proc._handle)):  # type: ignore[attr-defined]
        logger.warning("Could not assign pid %s to the backend job", proc.pid)
        return False
    return True


# ---------------------------------------------------------------- POSIX
def _linux_pdeathsig() -> None:  # runs in the child between fork and exec
    try:
        import ctypes
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        libc.prctl(1, int(signal.SIGKILL), 0, 0, 0)  # PR_SET_PDEATHSIG
        if os.getppid() == 1:  # parent already gone before prctl took effect
            os._exit(1)
    except Exception:
        pass


def popen_kwargs() -> dict:
    """Extra Popen kwargs for a guarded child (session / pdeathsig). Windows needs none here."""
    if os.name == "nt":
        return {}
    kwargs: dict = {"start_new_session": True}
    if sys.platform.startswith("linux"):
        kwargs["preexec_fn"] = _linux_pdeathsig
    return kwargs


# ---------------------------------------------------------------- registry
def _kill(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            proc.kill()
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def _install_hooks() -> None:
    global _hooks_installed
    if _hooks_installed:
        return
    _hooks_installed = True
    atexit.register(kill_all)
    if threading.current_thread() is not threading.main_thread():
        return  # signal handlers can only be set from the main thread; atexit still covers exit
    for signum in (signal.SIGTERM, signal.SIGINT):
        try:
            previous = signal.getsignal(signum)
        except (ValueError, OSError):
            continue

        def handler(sig, frame, _previous=previous):
            kill_all()
            if callable(_previous):
                _previous(sig, frame)
            elif _previous == signal.SIG_DFL:
                signal.signal(sig, signal.SIG_DFL)
                os.kill(os.getpid(), sig)
        try:
            signal.signal(signum, handler)
        except (ValueError, OSError):
            pass


def install_hooks() -> None:
    """Call once from the main thread at startup so SIGTERM/SIGINT also clean up."""
    _install_hooks()


def track(proc: subprocess.Popen, owner: str) -> subprocess.Popen:
    """Guard a freshly started child: job (Windows), registry, exit hooks."""
    if os.name == "nt":
        _assign_to_job(proc)
    with _lock:
        _live[proc] = owner
    _install_hooks()
    return proc


def untrack(proc: subprocess.Popen) -> None:
    with _lock:
        _live.pop(proc, None)


def live(owner: Optional[str] = None) -> list[subprocess.Popen]:
    with _lock:
        return [p for p, o in _live.items() if (owner is None or o == owner) and p.poll() is None]


def kill(owner: str) -> int:
    procs = live(owner)
    for proc in procs:
        _kill(proc)
    return len(procs)


def kill_all() -> int:
    procs = live()
    for proc in procs:
        _kill(proc)
    if procs:
        logger.info("Stopped %d install child process(es) on shutdown", len(procs))
    return len(procs)
