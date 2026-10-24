"""Retry budget and backoff. Classification stays in ``upstream_errors``.

Only ``rate_limited`` / ``upstream_unavailable`` / ``timeout`` / ``connection``
are retried — that set is ``RETRYABLE_TYPES`` from the shared classifier.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

from backend.core.upstream_errors import (
    UpstreamErrorType,
    classify_exception,
    http_error_parts,
    is_retryable,
)

# Product cap: each retryable type may retry at most twice (excluding the first request).
MAX_RETRIES = 2
RETRYABLE_ATTEMPTS = MAX_RETRIES + 1
DEFAULT_ATTEMPTS = RETRYABLE_ATTEMPTS
RETRY_AFTER_CAP = 120.0
BACKOFF_BASES = (2, 4, 8, 16, 32)


def parse_retry_after(value: object) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value < 0:
            return None
        return min(RETRY_AFTER_CAP, float(value))
    text = str(value).strip()
    if not text:
        return None
    try:
        return min(RETRY_AFTER_CAP, max(0.0, float(text)))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(text)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = (when - datetime.now(timezone.utc)).total_seconds()
        return min(RETRY_AFTER_CAP, max(0.0, seconds))
    except (TypeError, ValueError, OverflowError):
        return None


def retry_after_from_error(error: BaseException) -> float | None:
    """The provider's Retry-After on the error or its EXPLICIT ``__cause__`` links (#3,
    the rule): an exception that was merely being handled (an earlier, unrelated 429) never lends
    its Retry-After to this one."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen and len(seen) < 32:
        seen.add(id(current))
        delay = parse_retry_after(getattr(current, "retry_after", None))
        if delay is not None:
            return delay
        delay = _retry_after_from_headers(_headers_of(current))
        if delay is not None:
            return delay
        current = current.__cause__
    return None


def backoff_seconds(retry_after: float | None, attempt: int, *, rng: Any = None) -> float:
    """Equal jitter on 2/4/8/16/32. A provider Retry-After wins (capped) and is not jittered."""
    if retry_after is not None:
        return retry_after
    base = BACKOFF_BASES[min(max(0, attempt), len(BACKOFF_BASES) - 1)]
    roll = float(rng()) if rng is not None else __import__("random").random()
    return (base / 2.0) + (base / 2.0) * max(0.0, min(1.0, roll))


def max_attempts_for(error_type: UpstreamErrorType | str, default: int = DEFAULT_ATTEMPTS) -> int:
    """Non-retryable: first request only. Retryable: first + at most ``MAX_RETRIES``."""
    if not is_retryable(error_type):
        return 1
    return min(RETRYABLE_ATTEMPTS, max(1, default))


def studio_code_for(error_type: UpstreamErrorType | str, status: int | None = None) -> str:
    """Keep Studio ``error_code`` coarse; fine type lives on ``upstream_error_type``."""
    value = error_type.value if isinstance(error_type, UpstreamErrorType) else error_type
    if value == UpstreamErrorType.RATE_LIMITED.value:
        return "rate_limited"
    if value == UpstreamErrorType.TIMEOUT.value:
        return "timeout"
    if value == UpstreamErrorType.CONNECTION.value:
        return "connection"
    if value in {UpstreamErrorType.INVALID_KEY.value, UpstreamErrorType.PERMISSION_DENIED.value}:
        return "llm_auth_invalid"
    if value == UpstreamErrorType.INSUFFICIENT_QUOTA.value:
        return "llm_auth_invalid" if status in (401, 403) else "provider_error"
    return "provider_error"


def classify_for_retry(error: BaseException):
    """Shared classifier plus Retry-After and the coarse Studio code."""
    info = classify_exception(error)
    status, _body = http_error_parts(error)
    return info, status, retry_after_from_error(error)


def _headers_of(error: BaseException) -> Any:
    headers = getattr(error, "headers", None)
    if headers:
        return headers
    response = getattr(error, "response", None)
    return getattr(response, "headers", None) if response is not None else None


def _retry_after_from_headers(headers: Any) -> float | None:
    if not headers:
        return None
    getter = getattr(headers, "get", None)
    raw = None
    if callable(getter):
        try:
            raw = getter("retry-after") or getter("Retry-After")
        except Exception:  # noqa: BLE001
            raw = None
    if raw is None and isinstance(headers, dict):
        lowered = {str(key).lower(): value for key, value in headers.items()}
        raw = lowered.get("retry-after")
    return parse_retry_after(raw)
