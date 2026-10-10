"""Anonymous mcp_tool_called and mcp_job_finished events.

Uses the same switch as studio QA: no project key, or privacy.json analytics
false, means no request. Properties are tool, client, version, duration, ok
and error_code. Paths, secrets and free text are not properties.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
import queue
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from backend import __version__
from backend.services.studio.features import flag_enabled, resolve_features
from backend.services.studio.qa import telemetry as qa_telemetry

logger = logging.getLogger(__name__)

TOOLS = frozenset({
    'get_version', 'start_quick_output', 'get_quick_output_status', 'clip_video', 'start_clip_job',
    'get_job_status', 'get_project', 'list_projects', 'list_providers', 'check_environment',
    'export_clip', 'publish_clip', 'get_publish_status', 'list_publish_profiles',
    'cancel_job', 'list_styles', 'produce', 'outputs', 'run',
})
ERROR_CODES = frozenset({
    'none', 'unknown', 'interrupted', 'failed', 'cancelled', 'invalid_input', 'disabled', 'timeout',
})
TERMINAL = frozenset({'completed', 'partial', 'failed', 'interrupted', 'cancelled'})
_CLIENT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')
_JOB_ID = re.compile(r'^[A-Za-z0-9_-]{1,100}$')
_seen: set[tuple[str, str, bool]] = set()
_pending: set[tuple[str, str, bool]] = set()
_seen_lock = threading.Lock()
_posts: queue.Queue = queue.Queue()
_worker: threading.Thread | None = None
_worker_lock = threading.Lock()
_EXIT_FLUSH_SECONDS = 2.0


def reset_seen() -> None:
    """Clear the in-memory dedup set. A marker written after a successful send stays on disk."""
    _seen.clear()


def client_label(raw: str | None) -> str:
    """A short client token. Paths and free text become unknown."""
    if not isinstance(raw, str) or not raw.strip():
        raw = os.environ.get('AUTOCLIP_MCP_CLIENT', '')
    if not isinstance(raw, str) or any(mark in raw for mark in ('/', '\\', ':')):
        return 'unknown'
    parts = raw.strip().split()
    if not parts or _CLIENT.fullmatch(parts[0]) is None:
        return 'unknown'
    return parts[0]


def normalize_error(value: object, *, ok: bool) -> str:
    if value == 'partial':
        return 'none'
    if isinstance(value, str) and value in ERROR_CODES:
        return value
    return 'none' if ok else 'failed'


def normalize_tool(name: object) -> str:
    return name if isinstance(name, str) and name in TOOLS else 'other'


def record(tool: str, client: str | None, started: float, *, ok: bool, error_code: str,
           job_id: str | None = None, terminal: bool = False) -> None:
    """Record one tool call. A terminal job also records mcp_job_finished once.

    The post is queued and this returns without waiting. mcp_tool_called uses the
    call duration. mcp_job_finished uses the task's start-to-end time.
    """
    try:
        duration_ms = _cap_ms((time.perf_counter() - started) * 1000)
        properties = _properties(tool, client, duration_ms, ok, error_code)
        _emit('mcp_tool_called', properties)
        if not terminal or not isinstance(job_id, str) or _JOB_ID.fullmatch(job_id) is None:
            return
        key = (job_id, properties['error_code'], properties['ok'])
        job_properties = {**properties, 'duration_ms': _job_duration_ms(job_id, duration_ms)}
        _emit('mcp_job_finished', job_properties, dedup=key)
    except Exception:  # noqa: BLE001 - telemetry must not break the tool
        logger.warning('MCP event was not recorded')


def outcome_from_result(result: object) -> tuple[bool, str, str | None, bool]:
    """ok, error_code, job id, terminal. Ignores paths, secrets and message text."""
    payload = result if isinstance(result, dict) else getattr(result, 'structured_content', None)
    is_error = bool(getattr(result, 'is_error', False))
    if not isinstance(payload, dict):
        return (not is_error), ('failed' if is_error else 'none'), None, False
    ok = payload['ok'] if isinstance(payload.get('ok'), bool) else not is_error
    status = payload.get('status') if isinstance(payload.get('status'), str) else None
    error_code = normalize_error(payload.get('error_code') or status, ok=ok)
    job_id = payload.get('project_id')
    if not isinstance(job_id, str) or _JOB_ID.fullmatch(job_id) is None:
        job_id = None
    return ok, error_code, job_id, status in TERMINAL


def client_from_context(context: object) -> str:
    name = None
    try:
        info = context.session.client_params.client_info  # type: ignore[attr-defined]
        name = getattr(info, 'name', None)
    except Exception:  # noqa: BLE001 - a missing handshake is just an unknown client
        name = None
    return client_label(name if isinstance(name, str) else None)


def _properties(tool: str, client: str | None, duration_ms: int, ok: bool, error_code: str) -> dict:
    code = normalize_error(error_code, ok=ok)
    return {
        'tool': normalize_tool(tool),
        'client': client_label(client),
        'version': __version__,
        'duration_ms': duration_ms,
        'ok': ok,
        'error_code': code,
        '$feature/mcp_v2_tools': flag_enabled(resolve_features(), 'mcp_v2_tools'),
    }


def flush(timeout: float = 5) -> None:
    """Wait until queued posts have been attempted, but no longer than `timeout` seconds.

    Callers that emit do not wait. The process exit hook uses two seconds.
    """
    if timeout <= 0:
        return
    deadline = time.monotonic() + float(timeout)
    while True:
        if _posts.unfinished_tasks <= 0:
            return
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.02, remaining))


def _flush_on_exit() -> None:
    flush(_EXIT_FLUSH_SECONDS)


atexit.register(_flush_on_exit)


def _cap_ms(value: float) -> int:
    return max(0, min(3_600_000, int(value)))


def _job_duration_ms(job_id: str, fallback: int) -> int:
    """Milliseconds from the task's started_at to now. The tool-call timer is only a fallback."""
    try:
        from backend.services import mcp_jobs
        stored = mcp_jobs.read_job(job_id)
    except Exception:  # noqa: BLE001 - a missing ledger still reports the call
        return fallback
    started_at = stored.get('started_at') if isinstance(stored, dict) else None
    if isinstance(started_at, bool) or not isinstance(started_at, (int, float)):
        return fallback
    return _cap_ms((time.time() - float(started_at)) * 1000)


def _seen_path() -> Path | None:
    try:
        from backend.core.sentry_setup import _privacy_path
        path = _privacy_path()
    except Exception:  # noqa: BLE001
        return None
    if path is None:
        return None
    return path.with_name('mcp-events-seen.json')


def _digest(key: tuple[str, str, bool]) -> str:
    raw = f'{key[0]}|{key[1]}|{int(bool(key[2]))}'
    return hashlib.sha256(raw.encode()).hexdigest()


def _load_seen() -> list[str]:
    path = _seen_path()
    if path is None or not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, str)]


def _reserve(key: tuple[str, str, bool]) -> bool:
    """True when this process should send. Does not mark the event as sent."""
    digest = _digest(key)
    with _seen_lock:
        if key in _seen or key in _pending:
            return False
        if digest in _load_seen():
            _seen.add(key)
            return False
        _pending.add(key)
        return True


def _release(key: tuple[str, str, bool]) -> None:
    with _seen_lock:
        _pending.discard(key)


def _remember(key: tuple[str, str, bool]) -> None:
    """Record a successful send. A failed post never reaches this, so a later try can send."""
    digest = _digest(key)
    with _seen_lock:
        _seen.add(key)
        path = _seen_path()
        if path is None:
            return
        current = _load_seen()
        if digest in current:
            return
        current.append(digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(current[-2000:]), encoding='utf-8')
        temporary.replace(path)


def _ensure_worker() -> None:
    global _worker
    with _worker_lock:
        if _worker is not None and _worker.is_alive():
            return
        _worker = threading.Thread(target=_drain, name='mcp-telemetry', daemon=True)
        _worker.start()


def _drain() -> None:
    while True:
        item = _posts.get()
        dedup = item.get('dedup')
        try:
            if _post(item['event'], item['properties']) and dedup is not None:
                try:
                    _remember(dedup)
                except OSError:
                    logger.warning('MCP event was sent but not marked')
        finally:
            if dedup is not None:
                _release(dedup)
            _posts.task_done()


def _emit(event: str, properties: dict, dedup: tuple[str, str, bool] | None = None) -> None:
    key = qa_telemetry._key()
    if not key or not qa_telemetry._analytics_allowed():
        return
    if dedup is not None and not _reserve(dedup):
        return
    _ensure_worker()
    _posts.put({'event': event, 'properties': properties, 'dedup': dedup})


def _post(event: str, properties: dict) -> bool:
    try:
        key = qa_telemetry._key()
        if not key or not qa_telemetry._analytics_allowed():
            return False
        body = json.dumps({
            'api_key': key,
            'event': event,
            'distinct_id': qa_telemetry.anonymous_distinct_id(),
            'properties': properties,
        }).encode()
        request = urllib.request.Request(
            f'{qa_telemetry._HOST}/capture/', data=body, headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(request, timeout=1.5):
            return True
    except (OSError, TypeError, ValueError, urllib.error.URLError):
        logger.warning('MCP event was not delivered')
        return False
