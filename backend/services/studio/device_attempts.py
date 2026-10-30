"""Device-local generation attempt ledger for M1 success-rate dimensions.

Lives next to privacy.json / terminal-outbox.json (same app data dir). Keyed by
attempt_id so a replay of the same receipt returns the same index. Counts only
``studio_generation_finished`` attempts. ``is_first_success_device`` is true when
this device had no prior generation success before the attempt being recorded
(emitted on failure as well as success).
"""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_FILE = 'generation-device-attempts.json'
_KEEP = 500
_lock = threading.Lock()
_memory: dict[str, Any] = {'attempts': {}}


def _path() -> Path | None:
    try:
        from backend.core.sentry_setup import _privacy_path
        privacy = _privacy_path()
    except Exception:  # noqa: BLE001 - missing data dir must not fail settle
        return None
    if privacy is None:
        return None
    return privacy.with_name(_FILE)


def _empty() -> dict[str, Any]:
    return {'attempts': {}}


def _read() -> dict[str, Any]:
    path = _path()
    if path is None:
        return _memory
    if not path.is_file():
        return _empty()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, TypeError, ValueError):
        logger.warning('generation device attempt ledger could not be read')
        return _empty()
    if not isinstance(data, dict):
        return _empty()
    attempts = data.get('attempts')
    if not isinstance(attempts, dict):
        return _empty()
    cleaned = {}
    for key, value in attempts.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        outcome = value.get('outcome')
        if outcome not in ('success', 'partial', 'error'):
            continue
        row = {'outcome': outcome}
        index = value.get('index')
        if isinstance(index, int) and not isinstance(index, bool) and index >= 1:
            row['index'] = index
        if 'first_success_device' in value:
            row['first_success_device'] = bool(value.get('first_success_device'))
        cleaned[key] = row
    return {'attempts': cleaned}


def _write(data: dict[str, Any]) -> None:
    path = _path()
    if path is None:
        _memory.clear()
        _memory.update(data)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp')
    try:
        with temporary.open('wb') as handle:
            handle.write(json.dumps(data, ensure_ascii=False).encode())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def record(attempt_id: str | None, outcome: str) -> dict[str, Any]:
    """Record a generation terminal and return M1 device dimensions.

    Idempotent on ``attempt_id``: a second call with the same id returns the
    same ``attempt_index_on_device`` and the ``is_first_success_device`` that was
    true at first record time (frozen on the stored row when present).
    """
    if not isinstance(attempt_id, str) or not attempt_id:
        return {}
    mapped = {'success': 'success', 'completed': 'success', 'partial': 'partial',
              'error': 'error', 'failed': 'error'}.get(outcome)
    if mapped is None:
        return {}
    with _lock:
        data = _read()
        attempts = data['attempts']
        existing = attempts.get(attempt_id)
        if isinstance(existing, dict) and isinstance(existing.get('index'), int):
            return {
                'attempt_index_on_device': existing['index'],
                'is_first_success_device': bool(existing.get('first_success_device', False)),
            }
        # Order is insertion order of attempt_id keys (JSON object preserves it).
        prior_success = any(row.get('outcome') == 'success' for row in attempts.values())
        index = len(attempts) + 1
        first = not prior_success
        attempts[attempt_id] = {
            'outcome': mapped,
            'index': index,
            'first_success_device': first,
        }
        # Cap growth: drop oldest entries but keep indices stable on survivors.
        overflow = len(attempts) - _KEEP
        if overflow > 0:
            for key in list(attempts.keys())[:overflow]:
                attempts.pop(key, None)
        try:
            _write(data)
        except OSError:
            logger.warning('generation device attempt ledger could not be written')
            attempts.pop(attempt_id, None)
            return {}
        return {
            'attempt_index_on_device': index,
            'is_first_success_device': first,
        }
