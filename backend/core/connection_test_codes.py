"""Closed error_code set for provider connection tests (1.5.7 success-rate must-have).

Telemetry carries only this code plus an integer upstream HTTP status. Never the URL, key,
path, upstream body or message. Classification stays within the tested provider.
"""
from __future__ import annotations

import json
from pathlib import Path

from backend.core.event_catalog import load_catalog


def connection_test_error_codes() -> tuple[str, ...]:
    """The catalog enum. Callers do not keep a second copy of the list."""
    values = (load_catalog().get('enums') or {}).get('connection_test_error_code')
    if not isinstance(values, list) or not values:
        values = json.loads(Path(__file__).resolve().with_name('event_catalog.json').read_text(encoding='utf-8'))['enums']['connection_test_error_code']
    return tuple(value for value in values if isinstance(value, str))


CONNECTION_TEST_ERROR_CODES: tuple[str, ...] = connection_test_error_codes()

_BY_TYPE = {
    'invalid_key': 'invalid_key',
    'insufficient_quota': 'insufficient_quota',
    'permission_denied': 'permission_denied',
    'model_not_found': 'model_not_found',
    'bad_endpoint': 'bad_base_url',
    'rate_limited': 'rate_limited',
    'upstream_unavailable': 'http_5xx',
    'timeout': 'timeout',
    'connection': 'network',
    'output_truncated': 'output_truncated',
    'vision_unsupported': 'vision_unsupported',
}


def safe_http_status(status) -> int | None:
    try:
        value = int(status)
    except (TypeError, ValueError):
        return None
    return value if 100 <= value <= 599 else None


# Upstream tokens that stay ``unknown`` after the shared classifier, but already have a
# stable connection-test code. Matched on the normalized code/type only, never the message.
_INVALID_REQUEST_CODES = frozenset({
    'invalid_request_error', 'invalid_request', 'invalid_parameter', 'invalidparameter',
    'context_length_exceeded', 'content_filter', 'content_policy_violation', 'content_filter_error',
})


def _request_token(upstream_code: str) -> str:
    return (upstream_code or '').strip().lower().replace(' ', '_')


def connection_test_error_code(error_type: str | None, *, http_status=None, network_kind: str = '',
                               empty_key: bool = False, upstream_code: str = '') -> str:
    kind = (error_type or '').strip()
    status = safe_http_status(http_status)
    if kind == 'invalid_key' and empty_key:
        return 'empty_key'
    if kind == 'connection' and network_kind == 'dns':
        return 'dns'
    if kind in _BY_TYPE:
        return _BY_TYPE[kind]
    token = _request_token(upstream_code)
    compact = token.replace('.', '')
    if token in _INVALID_REQUEST_CODES or compact in _INVALID_REQUEST_CODES or token.startswith('invalidparameter.'):
        return 'invalid_request'
    if status is not None and 500 <= status <= 599:
        return 'http_5xx'
    if status == 429:
        return 'rate_limited'
    return 'unknown'


def vision_error_code(_vision_result=None) -> str:
    """The text probe passed but the image probe did not: a capability miss of the same model."""
    return 'vision_unsupported'
