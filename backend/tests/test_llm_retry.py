"""call_with_retry honors Kris's cap: two retries max, none for non-retryable."""
from types import SimpleNamespace

import pytest

from backend.core.llm_manager import LLMManager
from backend.core.upstream_errors import RETRYABLE_TYPES, UpstreamErrorType
from backend.pipeline import concurrency


def _manager(calls):
    manager = LLMManager.__new__(LLMManager)
    manager._reload_if_settings_changed = lambda: None
    manager.call = lambda *a, **k: calls['fn']()
    return manager


def _http(status, message, retry_after=None):
    error = Exception(message)
    error.status_code = status
    if retry_after is not None:
        error.response = SimpleNamespace(headers={'Retry-After': str(retry_after)}, status_code=status)
    return error


def test_retries_429_using_retry_after(monkeypatch):
    concurrency.reset_limiter()
    monkeypatch.setenv('AUTOCLIP_LLM_CONCURRENCY', '4')
    sleeps = []
    monkeypatch.setattr('time.sleep', sleeps.append)
    n = {'i': 0}

    def flaky():
        n['i'] += 1
        if n['i'] < 3:
            raise _http(429, 'rate limit', retry_after=7)
        return 'ok'

    assert _manager({'fn': flaky}).call_with_retry('p') == 'ok'
    assert n['i'] == 3
    assert sleeps == [7.0, 7.0]
    assert concurrency.effective_workers() == 1
    concurrency.reset_limiter()


def test_401_and_403_are_not_retried(monkeypatch):
    sleeps = []
    monkeypatch.setattr('time.sleep', lambda seconds: sleeps.append(seconds))
    for status, text, kind in (
        (401, 'invalid api key', 'invalid_key'),
        (403, 'insufficient_user_quota', 'insufficient_quota'),
        (402, 'Payment Required', 'insufficient_quota'),
        (404, 'does not exist', 'model_not_found'),
    ):
        sleeps.clear()
        n = {'i': 0}

        def boom(status=status, text=text):
            n['i'] += 1
            raise _http(status, text)

        manager = _manager({'fn': boom})
        with pytest.raises(Exception, match=text.split()[0]):
            manager.call_with_retry('p')
        assert n['i'] == 1
        assert sleeps == []
        from backend.core.upstream_errors import classify_exception
        assert classify_exception(_http(status, text)).error_type.value == kind
        assert classify_exception(_http(status, text)).retryable is False


@pytest.mark.parametrize(
    'factory,match',
    [
        (lambda: _http(429, 'rate limit', retry_after=1), 'rate limit'),
        (lambda: _http(500, 'internal server error'), 'internal'),
        (lambda: _http(503, 'service unavailable'), 'unavailable'),
        (lambda: TimeoutError('timed out'), 'timed out'),
        (lambda: ConnectionError('connection error'), 'connection error'),
    ],
    ids=('429', '500', '503', 'timeout', 'connection'),
)
def test_retryable_errors_retry_at_most_twice(monkeypatch, factory, match):
    sleeps = []
    monkeypatch.setattr('time.sleep', sleeps.append)
    n = {'i': 0}

    def always():
        n['i'] += 1
        raise factory()

    with pytest.raises(Exception, match=match):
        _manager({'fn': always}).call_with_retry('p')
    assert n['i'] == 3
    assert len(sleeps) == 2


def test_caller_cannot_raise_retry_ceiling(monkeypatch):
    sleeps = []
    monkeypatch.setattr('time.sleep', sleeps.append)
    n = {'i': 0}

    def always():
        n['i'] += 1
        raise _http(429, 'rate limit', retry_after=1)

    with pytest.raises(Exception, match='rate limit'):
        _manager({'fn': always}).call_with_retry('p', max_retries=10)
    assert n['i'] == 3
    assert sleeps == [1.0, 1.0]


def test_caller_can_request_fewer_attempts(monkeypatch):
    sleeps = []
    monkeypatch.setattr('time.sleep', sleeps.append)
    n = {'i': 0}

    def always():
        n['i'] += 1
        raise _http(500, 'internal server error')

    with pytest.raises(Exception, match='internal'):
        _manager({'fn': always}).call_with_retry('p', max_retries=1)
    assert n['i'] == 1
    assert sleeps == []


def test_retry_policy_uses_shared_classifier_and_retry_after():
    from backend.core.llm_retry import (
        MAX_RETRIES,
        RETRYABLE_ATTEMPTS,
        backoff_seconds,
        max_attempts_for,
        parse_retry_after,
    )
    from backend.core.upstream_errors import classify_upstream_error

    assert MAX_RETRIES == 2
    assert RETRYABLE_ATTEMPTS == 3
    assert parse_retry_after('7') == 7.0
    assert parse_retry_after('9999') == 120.0
    assert backoff_seconds(None, 0, rng=lambda: 0) == 1.0
    assert backoff_seconds(None, 0, rng=lambda: 1) == 2.0
    assert backoff_seconds(9.0, 0, rng=lambda: 1) == 9.0
    for kind in RETRYABLE_TYPES:
        assert max_attempts_for(kind) == 3
        assert max_attempts_for(kind, 10) == 3
        assert max_attempts_for(kind, 1) == 1
    for kind in (
        UpstreamErrorType.INVALID_KEY,
        UpstreamErrorType.INSUFFICIENT_QUOTA,
        UpstreamErrorType.PERMISSION_DENIED,
        UpstreamErrorType.MODEL_NOT_FOUND,
        UpstreamErrorType.BAD_ENDPOINT,
        UpstreamErrorType.OUTPUT_TRUNCATED,
        UpstreamErrorType.UNKNOWN,
    ):
        assert max_attempts_for(kind) == 1
        assert max_attempts_for(kind, 10) == 1
    limited = classify_upstream_error(429, {'error': {'code': 'rate_limit_exceeded'}})
    assert limited.retryable is True and limited.error_type in RETRYABLE_TYPES
    denied = classify_upstream_error(403, {'error': {'code': 'insufficient_user_quota'}})
    assert denied.retryable is False
    assert set(RETRYABLE_TYPES) == {
        UpstreamErrorType.RATE_LIMITED,
        UpstreamErrorType.UPSTREAM_UNAVAILABLE,
        UpstreamErrorType.TIMEOUT,
        UpstreamErrorType.CONNECTION,
    }
