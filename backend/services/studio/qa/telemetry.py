"""One studio_qa_checked event from the process that ran the checkers.

The desktop window, Docker, CLI and MCP all finish renders without the UI
observer. This post is a no-op unless a project key is configured and
privacy.json has not set analytics to false. Payloads are enums and counts.
"""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from backend.services.studio.features import DEFAULTS, VARIANTS
from backend.services.studio.qa.loudness import TARGETS
from backend.services.studio.qa.report import BUCKETS, CHECKERS

logger = logging.getLogger(__name__)

_HOST = os.environ.get('AUTOCLIP_POSTHOG_HOST', 'https://us.i.posthog.com').rstrip('/')
_OUTCOMES = frozenset({'pass', 'fail', 'skip'})
_QA_VARIANTS = VARIANTS['qa_gate_blocking']
# Anonymous device ids only. Paths, emails and free text never qualify.
_ANONYMOUS_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:-]{7,199}$')


def _key() -> str:
    for name in ('AUTOCLIP_POSTHOG_KEY', 'VITE_PUBLIC_POSTHOG_KEY'):
        value = os.environ.get(name, '').strip()
        if value:
            return value
    return ''


def _analytics_allowed() -> bool:
    """Product default is on. privacy.json analytics:false is the opt-out the tests write."""
    try:
        from backend.core.sentry_setup import _privacy_path
        path = _privacy_path()
        if path is None or not path.is_file():
            return True
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, TypeError, ValueError):
        return True
    if isinstance(data, dict) and data.get('analytics') is False:
        return False
    return True


def _identity_path() -> Path | None:
    try:
        from backend.core.sentry_setup import _privacy_path
        path = _privacy_path()
    except Exception:  # noqa: BLE001 - identity lookup must not break the event
        return None
    if path is None:
        return None
    return path.with_name('analytics.json')


def _read_id(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    value = data.get('distinct_id')
    if isinstance(value, str) and _ANONYMOUS_ID.fullmatch(value):
        return value
    return None


def remember_distinct_id(value: str) -> bool:
    """Store the UI's anonymous id so later backend events join the same person."""
    if not isinstance(value, str) or _ANONYMOUS_ID.fullmatch(value) is None:
        return False
    path = _identity_path()
    if path is None:
        return False
    try:
        if _read_id(path) == value:
            return True
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f'{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp')
        try:
            temporary.write_text(json.dumps({'distinct_id': value}), encoding='utf-8')
            temporary.replace(path)
        except OSError:
            temporary.unlink(missing_ok=True)
            return False
    except OSError:
        return False
    return _read_id(path) == value


def anonymous_distinct_id() -> str:
    """The id already on this machine. A fresh uuid is written only when none exists."""
    path = _identity_path()
    found = _read_id(path)
    if found:
        return found
    minted = uuid.uuid4().hex
    if path is not None and remember_distinct_id(minted):
        return _read_id(path) or minted
    return minted


def _qa_variant(value: str | None) -> str:
    if value == 'blocking':
        value = 'block'
    if value in _QA_VARIANTS:
        return value
    return str(DEFAULTS['qa_gate_blocking'])


def emit_checked(report: dict, strategy_id: str, *, variant: str | None = None) -> None:
    """POST one event with an outcome (and bucket) for each checker. Never raises."""
    key = _key()
    if not key or not _analytics_allowed():
        return
    try:
        properties = {
            'qa_mode': 'shadow',
            'duration_ms': max(0, min(60_000, int(report.get('duration_ms') or 0))),
            'studio_schema_version': 2,
            'runtime': 'python',
            '$feature/qa_gate_blocking': _qa_variant(variant),
        }
        if strategy_id in TARGETS:
            properties['strategy_id'] = strategy_id
        for check in report.get('checks') or []:
            if not isinstance(check, dict):
                continue
            name = check.get('checker')
            if name not in CHECKERS:
                continue
            outcome = check.get('outcome')
            bucket = check.get('bucket')
            if outcome in _OUTCOMES:
                properties[f'qa_{name}'] = outcome
            if isinstance(bucket, str) and bucket in BUCKETS:
                properties[f'qa_{name}_bucket'] = bucket
        body = json.dumps({
            'api_key': key,
            'event': 'studio_qa_checked',
            'distinct_id': anonymous_distinct_id(),
            'properties': properties,
        }).encode()
        request = urllib.request.Request(
            f'{_HOST}/capture/', data=body, headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(request, timeout=1.5):
            return
    except (OSError, TypeError, ValueError, urllib.error.URLError):
        logger.warning('QA event was not delivered')
