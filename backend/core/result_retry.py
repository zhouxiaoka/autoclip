"""Retry only ``invalid_response`` and ``timeline_empty``.

HTTP / transport failures are classified with ``classify_upstream_error`` and
are not retried here. 429 backoff and ASR preflight stay out of this change.
Each retryable type may retry at most twice (excluding the first request).
"""
from __future__ import annotations

from typing import Any

from backend.core.upstream_errors import classify_exception, classify_upstream_error

RETRYABLE_RESULT_TYPES = frozenset({"invalid_response", "timeline_empty"})
MAX_RETRIES = 2
MAX_ATTEMPTS = MAX_RETRIES + 1


def classify_for_retry(
    error: BaseException | None = None,
    *,
    status: int | None = None,
    body: Any = None,
    result_code: str | None = None,
) -> tuple[str, bool]:
    """Return ``(type, retryable)``. Only the two result codes are retryable."""
    code = result_code or getattr(error, "code", None)
    if isinstance(code, str) and code in RETRYABLE_RESULT_TYPES:
        return code, True
    if error is not None:
        info = classify_exception(error)
        return info.error_type.value, info.error_type.value in RETRYABLE_RESULT_TYPES
    if status is not None or body is not None:
        info = classify_upstream_error(status, body)
        return info.error_type.value, info.error_type.value in RETRYABLE_RESULT_TYPES
    return "unknown", False


def is_retryable_result(
    error_or_type: BaseException | str | None,
    *,
    status: int | None = None,
    body: Any = None,
) -> bool:
    if isinstance(error_or_type, str):
        kind, retryable = classify_for_retry(result_code=error_or_type, status=status, body=body)
        return retryable and kind in RETRYABLE_RESULT_TYPES
    kind, retryable = classify_for_retry(error_or_type, status=status, body=body)
    return retryable


def max_attempts_for(error_or_type: BaseException | str | None) -> int:
    return MAX_ATTEMPTS if is_retryable_result(error_or_type) else 1
