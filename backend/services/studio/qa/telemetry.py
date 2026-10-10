"""One studio_qa_checked event from the process that ran the checkers.

The desktop window, Docker, CLI and MCP all finish renders without the UI
observer. This post is a no-op unless a project key is configured and
privacy.json has not set analytics to false. Payloads are enums and counts.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
import uuid

from backend.services.studio.qa.loudness import TARGETS
from backend.services.studio.qa.report import BUCKETS, CHECKERS

logger = logging.getLogger(__name__)

_HOST = os.environ.get('AUTOCLIP_POSTHOG_HOST', 'https://us.i.posthog.com').rstrip('/')
_OUTCOMES = frozenset({'pass', 'fail', 'skip'})


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


def emit_checked(report: dict, strategy_id: str) -> None:
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
            'distinct_id': uuid.uuid4().hex,
            'properties': properties,
        }).encode()
        request = urllib.request.Request(
            f'{_HOST}/capture/', data=body, headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(request, timeout=1.5):
            return
    except (OSError, TypeError, ValueError, urllib.error.URLError):
        logger.warning('QA event was not delivered')
