"""Anonymous mcp_tool_called and mcp_job_finished events.

Uses the same switch as studio QA: no project key, or privacy.json analytics
false, means no request. Properties are tool, client, version, duration, ok
and error_code. Paths, secrets and free text are not properties.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request

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


def reset_seen() -> None:
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
    """Record one tool call. A terminal job also records mcp_job_finished once."""
    try:
        duration_ms = max(0, min(3_600_000, int((time.perf_counter() - started) * 1000)))
        properties = _properties(tool, client, duration_ms, ok, error_code)
        _emit('mcp_tool_called', properties)
        if not terminal or not isinstance(job_id, str) or _JOB_ID.fullmatch(job_id) is None:
            return
        key = (job_id, properties['error_code'], properties['ok'])
        if key in _seen:
            return
        _emit('mcp_job_finished', properties, dedup=key)
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


def _emit(event: str, properties: dict, dedup: tuple[str, str, bool] | None = None) -> None:
    key = qa_telemetry._key()
    if not key or not qa_telemetry._analytics_allowed():
        return
    if dedup is not None:
        _seen.add(dedup)
    try:
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
            return
    except (OSError, TypeError, ValueError, urllib.error.URLError):
        logger.warning('MCP event was not delivered')
