"""Disk-backed status for CLI and MCP jobs.

A missing record is unknown. A record whose worker process is gone is
interrupted. Project files alone never mean the job completed.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

SAFE_ID = re.compile(r'^[A-Za-z0-9_-]{1,100}$')
RUNNING = frozenset({'queued', 'running'})
TERMINAL = frozenset({'completed', 'partial', 'failed', 'interrupted', 'cancelled', 'unknown'})
_FIELDS = ('status', 'progress', 'stage', 'started_at', 'pid', 'pid_created_at', 'error_code', 'kind', 'result')


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
    """Mark a known job cancelled. Does not delete project files."""
    if not valid_id(project_id):
        return _view(project_id, status='unknown', error_code='invalid_input')
    record = read_job(project_id)
    if record is None:
        return _view(project_id, status='unknown', error_code='unknown')
    status = record.get('status')
    if status not in RUNNING:
        return lookup(project_id)
    write_job(project_id, status='cancelled', stage='cancelled', error_code='cancelled',
              progress=record.get('progress'), kind=record.get('kind'), result=record.get('result'),
              started_at=record.get('started_at'))
    return lookup(project_id)


def write_job(project_id: str, **fields: Any) -> dict[str, Any] | None:
    if not valid_id(project_id):
        return None
    current = read_job(project_id) or {
        'project_id': project_id,
        'started_at': time.time(),
        'pid': os.getpid(),
        'pid_created_at': _own_create_time(),
    }
    if current.get('status') == 'cancelled':
        fields['status'] = 'cancelled'
        fields['stage'] = 'cancelled'
        fields['error_code'] = 'cancelled'
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
    folder = _directory()
    path = folder / f'{project_id}.json'
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
