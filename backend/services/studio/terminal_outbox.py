"""Durable queue for studio terminal events.

The settle path writes the payload here before it returns. A background thread
posts it. A successful post or a permanent HTTP 4xx rejection removes it.
408, 429, 5xx and network errors are retried in this process, then left for
the next start. The same
``$insert_id`` is kept, and the settle time is sent as the capture timestamp.
Nothing is written when there is no project key. Telemetry switched off drops
the queue and does not post.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_QUEUE_LIMIT = 64
# Integer usage counts. A privacy scan must not treat prompt_tokens as a prompt.
_COUNT_KEYS = frozenset({'prompt_tokens', 'completion_tokens', 'reasoning_tokens', 'llm_calls'})
_RETRY_DELAYS = (1.0, 2.0, 4.0)
_file = threading.Lock()
_state = threading.Lock()
_running = False
_again = False
_attempted: set[str] = set()
_tries: dict[str, int] = {}
_memory: list[dict] = []


def _allowed() -> bool:
    from backend.services.studio.qa import telemetry
    return bool(telemetry._key()) and telemetry._analytics_allowed()


def _suppressed() -> bool:
    from backend.services.studio.qa import telemetry
    return not telemetry._analytics_allowed()


def _path() -> Path | None:
    try:
        from backend.core.sentry_setup import _privacy_path
        privacy = _privacy_path()
    except Exception:  # noqa: BLE001 - a missing data dir must not fail the settle
        return None
    if privacy is None:
        return None
    return privacy.with_name('terminal-outbox.json')


def _read() -> list[dict]:
    path = _path()
    if path is None:
        return list(_memory)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, TypeError, ValueError):
        logger.warning('Studio terminal queue could not be read')
        return []
    pending = data.get('pending') if isinstance(data, dict) else None
    if not isinstance(pending, list):
        return []
    return [item for item in pending if isinstance(item, dict) and isinstance(item.get('insert_id'), str)]


def _write(pending: list[dict]) -> None:
    path = _path()
    if path is None:
        _memory[:] = pending
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp')
    try:
        with temporary.open('wb') as handle:
            handle.write(json.dumps({'pending': pending}, ensure_ascii=False).encode())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _clear() -> None:
    with _file:
        path = _path()
        if not _memory and (path is None or not path.exists()):
            return
        _write([])


def pending_ids() -> list[str]:
    with _file:
        return [item['insert_id'] for item in _read()]


def _prepare(pending) -> list[dict]:
    from backend.core.event_catalog import analytics_environment, app_version, detect_arch, detect_os, validate_event
    envelope = {
        'schema_version': 2,
        'runtime': 'desktop' if os.environ.get('AUTOCLIP_MODE') == 'desktop' else 'web',
        'app_version': app_version(),
        'os': detect_os(),
        'arch': detect_arch(),
        'analytics_environment': analytics_environment(),
    }
    stamped = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    prepared = []
    for item in pending:
        name, props = item.get('event'), dict(item.get('properties') or {})
        if name not in ('studio_generation_finished', 'studio_production_finished'):
            continue
        for _ in range(6):
            bad = [p.split('.', 1)[-1].split('=', 1)[0].split(' ', 1)[0]
                   for p in validate_event(name, {**props, **envelope, 'studio_schema_version': 2}, envelope=True)
                   if any(s in p for s in (' not in ', 'secret', 'URL'))]
            # Integer token counts are not prompts. Never strip them as secrets.
            if not [props.pop(key, None) for key in bad if key not in ('outcome', 'error_code', 'failure_stage') and key not in _COUNT_KEYS]:
                break
        if validate_event(name, {**props, **envelope, 'studio_schema_version': 2}, envelope=True):
            logger.warning('%s failed catalog checks', name)
            continue
        insert_id = props.get('$insert_id')
        if not isinstance(insert_id, str) or not insert_id:
            continue
        prepared.append({
            'insert_id': insert_id, 'event': name, 'properties': props,
            'envelope': envelope, 'timestamp': stamped,
        })
    return prepared


def _append(items: list[dict]) -> None:
    if not items:
        return
    with _file:
        current = _read()
        seen = {item['insert_id'] for item in current}
        for item in items:
            if item['insert_id'] in seen:
                continue
            current.append(item)
            seen.add(item['insert_id'])
        overflow = len(current) - _QUEUE_LIMIT
        if overflow > 0:
            del current[:overflow]
            logger.warning('terminal outbox dropped %s oldest item(s)', overflow)
        _write(current)


def accept(pending) -> None:
    """Persist terminal payloads, then return. The network post runs on another thread."""
    if not pending:
        return
    try:
        if _suppressed():
            _clear()
            return
        from backend.services.studio.qa import telemetry
        if not telemetry._key():
            return
        _append(_prepare(pending))
        if _allowed():
            _kick()
    except Exception:  # noqa: BLE001 - the project state is already durable
        logger.warning('Studio terminal event was not queued')


def replay_unsent() -> None:
    """Send payloads left by an earlier process. The caller does not wait."""
    global _attempted, _tries
    try:
        if _suppressed():
            _clear()
            return
        with _state:
            _attempted = set()
            _tries = {}
        if _allowed() and _read():
            _kick()
    except Exception:  # noqa: BLE001
        logger.warning('Studio terminal event was not replayed')


def wait_until_idle(timeout: float = 3.0) -> bool:
    """Test helper: block until the background sender has finished this wave."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with _state:
            running = _running
        if not running:
            return True
        time.sleep(0.01)
    return False


def _kick() -> None:
    global _running, _again
    with _state:
        if _running:
            _again = True
            return
        _running = True

    def run():
        global _running, _again
        try:
            while True:
                _send_pending()
                with _state:
                    if not _again:
                        _running = False
                        return
                    _again = False
        except Exception:  # noqa: BLE001
            logger.warning('Studio terminal event was not delivered')
            with _state:
                _running = False
                _again = False

    threading.Thread(target=run, name='studio-terminal-event', daemon=True).start()


def _send_pending() -> None:
    global _again
    from backend.core.llm_emit import Rejected, _post_event
    if _suppressed() or not _allowed():
        if _suppressed():
            _clear()
        return
    with _file:
        batch = _read()
    delay = None
    for item in batch:
        if _suppressed():
            _clear()
            return
        insert_id = item['insert_id']
        with _state:
            if insert_id in _attempted:
                continue
        properties = item.get('properties') if isinstance(item.get('properties'), dict) else {}
        blob = json.dumps(properties, ensure_ascii=False)
        if 'sk-' in blob.lower() or 'authorization' in blob.lower():
            _drop(insert_id)
            continue
        envelope = item.get('envelope') if isinstance(item.get('envelope'), dict) else None
        stamp = item.get('timestamp') if isinstance(item.get('timestamp'), str) and item.get('timestamp') else None
        try:
            sent = _post_event(item['event'], properties, envelope=envelope, timestamp=stamp)
        except Rejected:
            _forget(insert_id)
            _drop(insert_id)
            continue
        if sent:
            _forget(insert_id)
            _drop(insert_id)
            continue
        with _state:
            count = _tries.get(insert_id, 0)
            if count < len(_RETRY_DELAYS):
                wait = _RETRY_DELAYS[count]
                _tries[insert_id] = count + 1
                delay = wait if delay is None else min(delay, wait)
            else:
                _attempted.add(insert_id)
                _tries.pop(insert_id, None)
    if delay is not None:
        time.sleep(delay)
        with _state:
            _again = True


def _forget(insert_id: str) -> None:
    with _state:
        _tries.pop(insert_id, None)


def _drop(insert_id: str) -> None:
    with _file:
        _write([item for item in _read() if item.get('insert_id') != insert_id])
