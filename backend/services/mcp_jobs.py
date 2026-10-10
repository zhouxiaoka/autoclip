"""Disk-backed status for CLI and MCP jobs.

A missing record is unknown. A record whose worker process is gone is
interrupted. Project files alone never mean the job completed.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SAFE_ID = re.compile(r'^[A-Za-z0-9_-]{1,100}$')
RUNNING = frozenset({'queued', 'running'})
TERMINAL = frozenset({'completed', 'partial', 'failed', 'interrupted', 'cancelled', 'unknown'})
_FIELDS = ('status', 'progress', 'stage', 'started_at', 'pid', 'pid_created_at', 'error_code', 'kind', 'result')
_guards_lock = threading.Lock()
_guards: dict[str, threading.Lock] = {}


def valid_id(project_id: str | None) -> bool:
    return bool(project_id) and SAFE_ID.fullmatch(project_id) is not None


def progress_fields(*, status: str, progress: Any = None, stage: Any = None, started_at: Any = None) -> dict[str, Any]:
    """The status fields every job query returns."""
    if status in ('completed', 'partial') and progress is None:
        progress = 100
    if status in RUNNING and progress is None:
        progress = 0
    number = _progress(progress)
    return {
        'status': status,
        'progress': number,
        'stage': stage if isinstance(stage, str) and stage else None,
        'eta': _eta(number, started_at, status),
        'poll_after_sec': 10 if status in RUNNING else 0,
    }


def lookup(project_id: str) -> dict[str, Any]:
    """Read the job record. Never promotes a bare project directory to completed."""
    if not valid_id(project_id):
        return _view(project_id, status='unknown', error_code='invalid_input')
    record = read_job(project_id)
    if record is None:
        return _view(project_id, status='unknown', error_code='unknown')
    status = record.get('status') if isinstance(record.get('status'), str) else 'unknown'
    if status in RUNNING and not _process_alive(record):
        status = 'interrupted'
        write_job(project_id, status='interrupted', stage='interrupted', error_code='interrupted',
                  progress=record.get('progress'), kind=record.get('kind'), result=record.get('result'),
                  started_at=record.get('started_at'))
        record = read_job(project_id) or record
        record['status'] = 'interrupted'
    return _view(project_id, status=status, progress=record.get('progress'), stage=record.get('stage'),
                 started_at=record.get('started_at'), error_code=_error_code(status, record.get('error_code')),
                 result=record.get('result') if status == 'completed' else None)


def cancel(project_id: str) -> dict[str, Any]:
    """Stop a running render, keep finished videos, and record cancelled."""
    if not valid_id(project_id):
        return _view(project_id, status='unknown', error_code='invalid_input')
    from backend.core import project_cancellation

    record = read_job(project_id)
    busy = project_cancellation.has_running(project_id) or _studio_busy(project_id)
    if record is None and not busy:
        return _view(project_id, status='unknown', error_code='unknown')
    status = record.get('status') if record else None
    if not busy and status not in RUNNING:
        return lookup(project_id)
    project_cancellation.stop(project_id)
    _settle_studio(project_id)
    write_job(project_id, status='cancelled', stage='cancelled', error_code='cancelled',
              progress=(record or {}).get('progress'), kind=(record or {}).get('kind'),
              result=(record or {}).get('result'), started_at=(record or {}).get('started_at'))
    return lookup(project_id)


def _studio_busy(project_id: str) -> bool:
    from backend.core.project_cancellation import project_directory
    path = project_directory(project_id) / 'metadata' / 'studio.json'
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    generation = data.get('generation') or {}
    if isinstance(generation, dict) and generation.get('status') in ('screening', 'rendering', 'running', 'queued'):
        return True
    return any(isinstance(job, dict) and job.get('status') in ('queued', 'running', 'preparing') for job in data.get('jobs') or [])


def _settle_studio(project_id: str) -> None:
    """Mark in-progress desktop jobs cancelled. Finished videos stay completed."""
    from backend.core.project_cancellation import record_stop
    from backend.services.studio import store
    try:
        with record_stop():
            def mutate(data):
                generation = data.get('generation')
                if isinstance(generation, dict) and generation.get('status') in ('screening', 'rendering', 'running', 'queued'):
                    generation['status'] = 'cancelled'
                for job in data.get('jobs') or []:
                    if isinstance(job, dict) and job.get('status') in ('queued', 'running', 'preparing'):
                        job['status'] = 'cancelled'
                        job['error_code'] = 'cancelled'
                for variant in data.get('output_variants') or []:
                    if isinstance(variant, dict) and variant.get('status') in ('queued', 'running', 'preparing'):
                        variant['status'] = 'cancelled'
            store.change(project_id, mutate)
    except (OSError, FileNotFoundError, LookupError, ValueError):
        return


def _guard(project_id: str) -> threading.Lock:
    with _guards_lock:
        return _guards.setdefault(project_id, threading.Lock())


@contextmanager
def _exclusive(path: Path):
    """Cross-process lock. Callers also hold the per-id thread lock; flock does not."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + '.lock')
    handle = open(lock_path, 'a+b')
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


def write_job(project_id: str, **fields: Any) -> dict[str, Any] | None:
    if not valid_id(project_id):
        return None
    path = _directory() / f'{project_id}.json'
    with _guard(project_id), _exclusive(path):
        current = read_job(project_id) or {
            'project_id': project_id,
            'started_at': time.time(),
            'pid': os.getpid(),
            'pid_created_at': _own_create_time(),
        }
        status = current.get('status')
        incoming = fields.get('status')
        if status == 'cancelled':
            fields['status'] = 'cancelled'
            fields['stage'] = 'cancelled'
            fields['error_code'] = 'cancelled'
        elif status == 'completed' and incoming == 'cancelled':
            return current
        for key in _FIELDS:
            if key in fields and fields[key] is not None:
                current[key] = fields[key]
        current['project_id'] = project_id
        current.pop('api_key', None)
        current.pop('video', None)
        current.pop('error', None)
        result = current.get('result')
        if isinstance(result, dict):
            result.pop('api_key', None)
            result.pop('apiKey', None)
        temporary = path.with_suffix(f'.{os.getpid()}.tmp')
        temporary.write_text(json.dumps(current, ensure_ascii=False), encoding='utf-8')
        temporary.replace(path)
        return current


def read_job(project_id: str) -> dict[str, Any] | None:
    if not valid_id(project_id):
        return None
    path = _directory() / f'{project_id}.json'
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _directory():
    from backend.core.path_utils import get_data_directory
    path = get_data_directory() / 'mcp-jobs'
    path.mkdir(parents=True, exist_ok=True)
    return path


def _progress(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return max(0, min(100, int(value)))


def _eta(progress: int | None, started_at: Any, status: str) -> int | None:
    if status not in RUNNING:
        return 0
    if progress is None or progress < 5 or progress >= 100:
        return None
    if isinstance(started_at, bool) or not isinstance(started_at, (int, float)):
        return None
    elapsed = time.time() - float(started_at)
    if elapsed < 1:
        return None
    return int(min(86_400, elapsed * (100 - progress) / progress))


def _error_code(status: str, stored: Any) -> str:
    if status in ('completed', 'partial', 'queued', 'running'):
        return 'none'
    if isinstance(stored, str) and stored in ('unknown', 'interrupted', 'failed', 'cancelled', 'invalid_input', 'disabled'):
        return stored
    if status in ('unknown', 'interrupted', 'failed', 'cancelled'):
        return status
    return 'failed'


def _view(project_id: str, *, status: str, error_code: str, progress: Any = None, stage: Any = None,
          started_at: Any = None, result: Any = None) -> dict[str, Any]:
    body = {
        'ok': status in ('completed', 'partial', 'queued', 'running'),
        'project_id': project_id,
        'error_code': error_code,
        **progress_fields(status=status, progress=progress, stage=stage, started_at=started_at),
    }
    if status == 'completed' and isinstance(result, dict):
        body['result'] = result
    return body


def _process_alive(record: dict[str, Any]) -> bool:
    pid = record.get('pid')
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        import psutil
        proc = psutil.Process(pid)
    except Exception:  # noqa: BLE001 - a missing process is not alive
        return False
    created = record.get('pid_created_at')
    if isinstance(created, bool) or not isinstance(created, (int, float)):
        return True
    try:
        return abs(proc.create_time() - float(created)) <= 0.05
    except Exception:  # noqa: BLE001
        return False


def _own_create_time() -> float | None:
    try:
        import psutil
        return float(psutil.Process().create_time())
    except Exception:  # noqa: BLE001
        return None
