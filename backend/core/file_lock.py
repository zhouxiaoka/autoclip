"""one cross-process exclusive lock with a timeout (POSIX flock / Windows msvcrt).

Known limits: flock is per open file description (callers also hold a thread lock); on network or
cloud-synced folders the OS may not enforce it."""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

from backend.core.failure_codes import sentence

LOCK_TIMEOUT_CODE = 'store_lock_timeout'
# what the user sees. A local busy store, never phrased as a provider/model timeout.
LOCK_TIMEOUT_MESSAGE = sentence('store_lock_timeout')
DEFAULT_TIMEOUT = 10.0
_POLL = 0.05
logger = logging.getLogger(__name__)


class LockTimeout(TimeoutError):
    """The lock was not acquired in time. ``code`` is the content-free error code."""
    code = LOCK_TIMEOUT_CODE

    def __init__(self, message: str = LOCK_TIMEOUT_MESSAGE):
        super().__init__(message)


def _try_lock(handle) -> bool:
    try:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (BlockingIOError, PermissionError):
        return False
    except OSError as error:
        # Windows reports a held byte range as EACCES/EDEADLK; anything else is a real failure.
        if os.name == 'nt' and getattr(error, 'errno', None) in (13, 36):
            return False
        raise


def _unlock(handle) -> None:
    try:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


def acquire(path: Path, timeout: float = DEFAULT_TIMEOUT):
    """Open ``path`` and lock its first byte; returns the handle (pass it to ``release``)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, 'a+b')
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b'\0')
            handle.flush()
        deadline = time.monotonic() + max(0.0, timeout)
        while not _try_lock(handle):
            if time.monotonic() >= deadline:
                logger.warning('Exclusive lock not acquired in time (%s)', LOCK_TIMEOUT_CODE)
                raise LockTimeout()
            time.sleep(_POLL)
        return handle
    except BaseException:
        handle.close()
        raise


def release(handle) -> None:
    try:
        _unlock(handle)
    finally:
        handle.close()


class ProcessLock:
    """Re-entrant in-process lock plus a cross-process file lock taken by the OUTERMOST holder.
    Used as ``with lock:`` exactly like the ``threading.RLock`` it replaces."""

    def __init__(self, path_fn, timeout: float = DEFAULT_TIMEOUT):
        self._path_fn = path_fn
        self.timeout = timeout
        self._thread = threading.RLock()
        self._depth = 0
        self._handle = None
        self.after_release = None  # runs only after the outermost holder has dropped both locks

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        # ONE deadline for both stages, computed on entry; the file lock only gets what the
        # in-process wait left. Default timeout: either stage raises LockTimeout. Explicit timeout: either
        # stage returns False (RLock semantics). Non-blocking never waits.
        explicit = blocking and timeout >= 0
        budget = (timeout if explicit else self.timeout) if blocking else 0.0
        deadline = time.monotonic() + max(0.0, budget)
        if not self._thread.acquire(blocking, max(0.0, budget) if blocking else -1):
            if blocking and not explicit:
                logger.warning('In-process lock not acquired in time (%s)', LOCK_TIMEOUT_CODE)
                raise LockTimeout()
            return False
        if self._depth == 0:
            try:
                self._handle = acquire(Path(self._path_fn()), max(0.0, deadline - time.monotonic()))
            except LockTimeout:
                self._thread.release()
                if not blocking or explicit:
                    return False
                raise
            except BaseException:
                self._thread.release()
                raise
        self._depth += 1
        return True

    def release(self) -> None:
        self._depth -= 1
        finished = self._depth == 0
        if finished and self._handle is not None:
            handle, self._handle = self._handle, None
            release(handle)
        hook = self.after_release if finished else None
        self._thread.release()
        if hook is not None:
            try:
                hook()
            except Exception:
                logger.warning('Lock release hook failed')

    def _is_owned(self) -> bool:
        return self._thread._is_owned()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *_exc):
        self.release()
        return False
