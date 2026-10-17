"""Closed error_code set for provider connection tests (1.5.8 success-rate must-have).

Telemetry carries only this code plus an integer upstream HTTP status. Never the URL, key,
path, upstream body or message. Classification stays within the tested provider.
"""
from __future__ import annotations

CONNECTION_TEST_ERROR_CODES: tuple[str, ...] = (
    'empty_key', 'invalid_key', 'insufficient_quota', 'permission_denied',
    'bad_base_url', 'model_not_found', 'rate_limited', 'http_5xx', 'timeout',
    'dns', 'cors', 'network', 'vision_unsupported', 'output_truncated',
    'invalid_request', 'unknown',
)

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


def connection_test_error_code(error_type: str | None, *, http_status=None, network_kind: str = '',
                               empty_key: bool = False) -> str:
    kind = (error_type or '').strip()
    status = safe_http_status(http_status)
    if kind == 'invalid_key' and empty_key:
        return 'empty_key'
    if kind == 'connection' and network_kind == 'dns':
        return 'dns'
    if kind in _BY_TYPE:
        return _BY_TYPE[kind]
    if status is not None and 500 <= status <= 599:
        return 'http_5xx'
    if status == 429:
        return 'rate_limited'
    return 'unknown'


def vision_error_code(_vision_result=None) -> str:
    """The text probe passed but the image probe did not: a capability miss of the same model."""
    return 'vision_unsupported'
