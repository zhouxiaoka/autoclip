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
import json
import logging
import os
import shutil
import signal
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_cancelled: set[str] = set()
_stopped: set[str] = set()
_processes: dict[str, set[subprocess.Popen]] = {}
_leaders: set[int] = set()
_temporary: dict[str, set[Path]] = {}
_binds: dict[str, int] = {}
_round_ignored: dict[str, int] = {}
_current: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('autoclip_project', default=None)
_recording_stop: contextvars.ContextVar[bool] = contextvars.ContextVar('autoclip_recording_stop', default=False)
MESSAGE = '项目已删除，已停止生成'
STOP_MESSAGE = '任务已取消'
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000


class ProjectDeleted(FileNotFoundError):
    """The project was deleted while this worker was running; stop without recording anything."""

    def __init__(self, project_id: str = ''):
        super().__init__(MESSAGE)
        self.project_id = project_id


class JobStopped(Exception):
    """The user cancelled this generation. Finished videos stay on disk."""

    def __init__(self, project_id: str = ''):
        super().__init__(STOP_MESSAGE)
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


def stop(project_id: str) -> None:
    """Stop this project's render. Kills the ffmpeg process group and temporary files.

    Finished videos are left in place. Deleting the project still goes through `cancel`.
    The on-disk marker is what a render in another process sees at its next checkpoint.
    """
    write_stop_marker(project_id)
    with _lock:
        _stopped.add(project_id)
        running = list(_processes.get(project_id, ()))
    for proc in running:
        _kill(proc)
    clean_temporary(project_id)


def is_stopped(project_id: Optional[str]) -> bool:
    """True only for the worker currently bound to this project.

    `stop()` keeps the id so that worker can exit. MCP can cancel a desktop job
    without entering `bind`; the leftover record must not fail a later edit,
    export, or publish in this process.
    """
    return bool(project_id) and project_id in _stopped and _current.get() == project_id


def has_running(project_id: str) -> bool:
    with _lock:
        return bool(_processes.get(project_id))


def note_temporary(path: Path, project_id: Optional[str] = None) -> None:
    project_id = project_id or _current.get()
    if not project_id:
        return
    with _lock:
        _temporary.setdefault(project_id, set()).add(Path(path))


def clean_temporary(project_id: str) -> None:
    """Remove scratch files for a cancelled render. A finished `.mp4` stays."""
    with _lock:
        noted = list(_temporary.pop(project_id, ()))
    extras: list[Path] = []
    studio = project_directory(project_id) / 'output' / 'studio'
    if studio.is_dir():
        extras.extend(studio.glob('*.part.mp4'))
    for path in [*noted, *extras]:
        if _finished_video(path):
            continue
        try:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        except OSError as error:
            logger.warning('Could not remove temporary render file: %s', type(error).__name__)


def is_cancelled(project_id: Optional[str]) -> bool:
    return bool(project_id) and project_id in _cancelled


def current() -> Optional[str]:
    return _current.get()


def current_cancelled() -> bool:
    return is_cancelled(_current.get())


@contextmanager
def record_stop():
    """Let the worker write `cancelled` after a stop without raising again."""
    token = _recording_stop.set(True)
    try:
        yield
    finally:
        _recording_stop.reset(token)


def checkpoint(project_id: Optional[str] = None) -> None:
    project_id = project_id or _current.get()
    if is_cancelled(project_id):
        raise ProjectDeleted(project_id or '')
    if _recording_stop.get():
        return
    if is_stopped(project_id) or _marker_requests_stop(project_id):
        raise JobStopped(project_id or '')


def project_directory(project_id: str) -> Path:
    # Never get_project_directory(): it creates the directory it returns.
    from backend.core.path_utils import get_data_directory
    return get_data_directory() / 'projects' / project_id


def _marker_path(project_id: str) -> Path:
    return project_directory(project_id) / 'metadata' / 'cancel.marker'


def _seq_path(project_id: str) -> Path:
    """High-water seq. Survives deletion of the marker so the next cancel still increments."""
    return project_directory(project_id) / 'metadata' / 'cancel.seq'


def _marker_seq(project_id: Optional[str]) -> int:
    if not project_id:
        return 0
    try:
        data = json.loads(_marker_path(project_id).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, TypeError):
        return 0
    seq = data.get('seq') if isinstance(data, dict) else None
    if isinstance(seq, bool) or not isinstance(seq, int) or seq <= 0:
        return 0
    return seq


def _stored_high(project_id: str) -> int:
    try:
        value = int(_seq_path(project_id).read_text(encoding='utf-8').strip())
    except (OSError, ValueError):
        return 0
    if value <= 0:
        return 0
    return value


def _high_water(project_id: str) -> int:
    return max(_marker_seq(project_id), _stored_high(project_id))


@contextmanager
def _marker_exclusive(project_id: str):
    """Cross-process lock for the cancel marker. Does not create a missing project."""
    folder = project_directory(project_id)
    if not folder.is_dir():
        yield
        return
    meta = folder / 'metadata'
    try:
        meta.mkdir(exist_ok=True)
        handle = open(meta / 'cancel.lock', 'a+b')
    except OSError:
        yield
        return
    locked = False
    try:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b'\0')
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        locked = True
        yield
    finally:
        if locked:
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
        handle.close()


def _write_high(project_id: str, seq: int) -> None:
    if seq <= 0:
        return
    _seq_path(project_id).write_text(str(seq), encoding='utf-8')


def write_stop_marker(project_id: str) -> None:
    """Tell every process working on this project to stop at its next checkpoint."""
    folder = project_directory(project_id)
    if not folder.is_dir():
        return
    try:
        with _marker_exclusive(project_id):
            if not folder.is_dir():
                return
            nxt = _high_water(project_id) + 1
            meta = folder / 'metadata'
            meta.mkdir(exist_ok=True)
            _marker_path(project_id).write_text(json.dumps({'seq': nxt}), encoding='utf-8')
            _write_high(project_id, nxt)
    except OSError as error:
        logger.warning('Could not record the cancel marker: %s', type(error).__name__)


def _retire_marker(project_id: str, expected: int) -> None:
    """Drop a marker this round already observed. A newer seq is a live cancel and stays."""
    if expected <= 0 or not project_directory(project_id).is_dir():
        return
    try:
        with _marker_exclusive(project_id):
            if _marker_seq(project_id) != expected:
                return
            _marker_path(project_id).unlink(missing_ok=True)
            _write_high(project_id, max(expected, _stored_high(project_id)))
    except OSError as error:
        logger.warning('Could not remove the cancel marker: %s', type(error).__name__)


def _marker_requests_stop(project_id: Optional[str]) -> bool:
    """A marker stops only the worker bound to this project.

    `store.write` / `store.change` checkpoint on the desktop and in other MCP
    processes that never entered `bind`. A leftover marker must not fail those.
    """
    if not project_id or _current.get() != project_id:
        return False
    seq = _marker_seq(project_id)
    if seq <= 0:
        return False
    ignored = _round_ignored.get(project_id)
    if ignored is None:
        return True
    return seq > ignored


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
    """Run a worker for `project_id`: checkpoints see it, and its leftovers go if it was deleted.

    The first bind of a round clears a previous stop and retires that round's marker,
    so the same project can be edited and produced again. A stop that lands after this
    snapshot still wins. When the round ends, that marker is removed too.
    """
    with _lock:
        depth = _binds.get(project_id, 0)
        starting = depth == 0
    if starting:
        observed = _high_water(project_id)
        live = _marker_seq(project_id)
    else:
        observed = 0
        live = 0
    with _lock:
        depth = _binds.get(project_id, 0)
        if depth == 0:
            _round_ignored[project_id] = observed
            _stopped.discard(project_id)
        else:
            live = 0
        _binds[project_id] = depth + 1
    if live:
        _retire_marker(project_id, live)
    token = _current.set(project_id)
    try:
        yield
    finally:
        _current.reset(token)
        with _lock:
            depth = _binds.get(project_id, 1) - 1
            if depth <= 0:
                _binds.pop(project_id, None)
                _stopped.discard(project_id)
                finished = _marker_seq(project_id)
            else:
                _binds[project_id] = depth
                finished = 0
            busy = bool(_processes.get(project_id))
        if finished:
            _retire_marker(project_id, finished)
        if is_cancelled(project_id) and not busy:
            remove_files(project_id)


def _finished_video(path: Path) -> bool:
    return path.suffix.lower() == '.mp4' and not path.name.endswith('.part.mp4')


def _spawn_kwargs(kwargs: dict) -> dict:
    """Run the child in its own process group so a cancel reaches ffmpeg and its children."""
    kwargs = dict(kwargs)
    if os.name == 'nt':
        flags = int(kwargs.get('creationflags') or 0)
        flags |= int(getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', _CREATE_NEW_PROCESS_GROUP))
        flags |= int(getattr(subprocess, 'CREATE_NO_WINDOW', _CREATE_NO_WINDOW))
        kwargs['creationflags'] = flags
    else:
        kwargs['start_new_session'] = True
    return kwargs


def _group_owned(pid: int, leader_reaped: bool) -> bool:
    """Whether `killpg` still names the group `run()` started.

    `poll`/`communicate` already reap the leader. The pid can be recycled before
    the `finally` block signals it. A live `getpgid` after the reap belongs to
    someone else. A dead pid is signaled only when group members remain
    (grandchildren whose leader has exited).
    """
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        if not leader_reaped:
            return False
        try:
            os.killpg(pid, 0)
        except OSError:
            return False
        return True
    except OSError:
        return False
    if pgid != pid or leader_reaped:
        return False
    return True


def _kill(proc: subprocess.Popen) -> None:
    pid = proc.pid
    leader = pid in _leaders
    exited = proc.poll() is not None
    # A dead session leader must still take its grandchildren with it.
    if exited and not leader:
        return
    try:
        if os.name == 'nt':
            if not exited:
                subprocess.run(
                    ['taskkill', '/F', '/T', '/PID', str(pid)],
                    capture_output=True, timeout=5, check=False,
                    creationflags=int(getattr(subprocess, 'CREATE_NO_WINDOW', _CREATE_NO_WINDOW)),
                )
        elif leader:
            if _group_owned(pid, exited):
                os.killpg(pid, signal.SIGKILL)
        elif not exited:
            proc.kill()
    except (OSError, subprocess.TimeoutExpired):
        if not exited:
            try:
                proc.kill()
            except OSError:
                pass
    if proc.poll() is not None:
        return
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except OSError:
            pass


def _stop_requested(project_id: Optional[str]) -> bool:
    return is_cancelled(project_id) or is_stopped(project_id) or _marker_requests_stop(project_id)


def _wait_child(proc: subprocess.Popen, timeout: Optional[float], project_id: str):
    """Poll the child so a cancel marker written by another process stops this render."""
    deadline = None if timeout is None else time.monotonic() + float(timeout)
    while True:
        slice_timeout = 0.5
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(proc.args, timeout)
            slice_timeout = min(0.5, remaining)
        try:
            return proc.communicate(timeout=slice_timeout)
        except subprocess.TimeoutExpired:
            checkpoint(project_id)


def run(cmd, *, check: bool = False, timeout: Optional[float] = None, capture_output: bool = False, **kwargs):
    """subprocess.run for long children (ffmpeg) of the bound project: deleting the project kills them."""
    project_id = _current.get()
    if project_id is None:
        return subprocess.run(cmd, check=check, timeout=timeout, capture_output=capture_output, **kwargs)
    checkpoint(project_id)
    if capture_output:
        kwargs['stdout'] = subprocess.PIPE
        kwargs['stderr'] = subprocess.PIPE
    kwargs = _spawn_kwargs(kwargs)
    with subprocess.Popen(cmd, **kwargs) as proc:
        with _lock:
            _processes.setdefault(project_id, set()).add(proc)
            if os.name != 'nt':
                _leaders.add(proc.pid)
        try:
            if _stop_requested(project_id):
                _kill(proc)  # cancelled between the checkpoint and the registration
            try:
                stdout, stderr = _wait_child(proc, timeout, project_id)
            except subprocess.TimeoutExpired:
                _kill(proc)
                stdout, stderr = proc.communicate()
                raise subprocess.TimeoutExpired(proc.args, timeout, output=stdout, stderr=stderr) from None
            except BaseException:
                _kill(proc)
                raise
        finally:
            if _stop_requested(project_id):
                _kill(proc)  # the leader may already have exited; the group is still in _leaders
            with _lock:
                _leaders.discard(proc.pid)
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
