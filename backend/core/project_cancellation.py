"""Stop a project's background work when the project is deleted (RC156 Win QA #12).

Deleting a project is the only way to abort a Studio generation in the UI. Before this
module the delete returned 200 while rendering, cover design and state writes carried on
and re-created files in the deleted project's directory.

- `cancel(project_id)` marks the project (process-wide) and kills the ffmpeg children that
  were started through `run()` for it.
- Workers `bind(project_id)` for their whole run (studio jobs, the content pipeline). Every
  `checkpoint()` - step boundaries, before model calls, before state writes, around ffmpeg -
  raises `ProjectDeleted` once the project is cancelled.
- `ProjectDeleted` is a FileNotFoundError: existing "the project is gone, nothing to record"
  handlers already treat it that way, and it is never reported to Sentry.
- When a bound worker stops, `bind` removes whatever the cancelled job wrote after the delete.
"""
from __future__ import annotations

import contextvars
import logging
import shutil
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cancelled: set[str] = set()
_processes: dict[str, set[subprocess.Popen]] = {}
_current: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('autoclip_project', default=None)
MESSAGE = '项目已删除，已停止生成'


class ProjectDeleted(FileNotFoundError):
    """The project was deleted while this worker was running; stop without recording anything."""

    def __init__(self, project_id: str = ''):
        super().__init__(MESSAGE)
        self.project_id = project_id


def cancel(project_id: str) -> None:
    with _lock:
        _cancelled.add(project_id)
        running = list(_processes.get(project_id, ()))
    for proc in running:
        _kill(proc)


def restore(project_id: str) -> None:
    """Undo `cancel` when the delete itself failed and the project still exists."""
    with _lock:
        _cancelled.discard(project_id)


def is_cancelled(project_id: Optional[str]) -> bool:
    return bool(project_id) and project_id in _cancelled


def current() -> Optional[str]:
    return _current.get()


def current_cancelled() -> bool:
    return is_cancelled(_current.get())


def checkpoint(project_id: Optional[str] = None) -> None:
    project_id = project_id or _current.get()
    if is_cancelled(project_id):
        raise ProjectDeleted(project_id)


def project_directory(project_id: str) -> Path:
    # Never get_project_directory(): it creates the directory it returns.
    from backend.core.path_utils import get_data_directory
    return get_data_directory() / 'projects' / project_id


def remove_files(project_id: str, attempts: int = 5) -> bool:
    """Remove the project directory; retry briefly for files a just-killed child still held."""
    folder = project_directory(project_id)
    for attempt in range(attempts):
        if not folder.exists():
            return True
        try:
            shutil.rmtree(folder)
        except FileNotFoundError:
            pass
        except OSError as error:
            if attempt + 1 == attempts:
                logger.warning('Could not remove deleted project files yet: %s', type(error).__name__)
                return False
            time.sleep(0.2 * (attempt + 1))
    return not folder.exists()


@contextmanager
def bind(project_id: str):
    """Run a worker for `project_id`: checkpoints see it, and its leftovers go if it was deleted."""
    token = _current.set(project_id)
    try:
        yield
    finally:
        _current.reset(token)
        if is_cancelled(project_id):
            with _lock:
                busy = bool(_processes.get(project_id))
            if not busy:
                remove_files(project_id)


def _kill(proc: subprocess.Popen) -> None:
    try:
        if proc.poll() is None:
            proc.kill()
    except OSError:
        pass


def run(cmd, *, check: bool = False, timeout: Optional[float] = None, capture_output: bool = False, **kwargs):
    """subprocess.run for long children (ffmpeg) of the bound project: deleting the project kills them."""
    project_id = _current.get()
    if project_id is None:
        return subprocess.run(cmd, check=check, timeout=timeout, capture_output=capture_output, **kwargs)
    checkpoint(project_id)
    if capture_output:
        kwargs['stdout'] = subprocess.PIPE
        kwargs['stderr'] = subprocess.PIPE
    with subprocess.Popen(cmd, **kwargs) as proc:
        with _lock:
            _processes.setdefault(project_id, set()).add(proc)
        try:
            if is_cancelled(project_id):
                _kill(proc)  # cancelled between the checkpoint and the registration
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                _kill(proc)
                stdout, stderr = proc.communicate()
                raise subprocess.TimeoutExpired(proc.args, timeout, output=stdout, stderr=stderr) from None
            except BaseException:
                _kill(proc)
                raise
        finally:
            with _lock:
                running = _processes.get(project_id)
                if running is not None:
                    running.discard(proc)
                    if not running:
                        _processes.pop(project_id, None)
    checkpoint(project_id)  # killed by the delete: stop, do not report an encoder failure
    result = subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
    if check:
        result.check_returncode()
    return result
