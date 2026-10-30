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


def test_quota_on_401_or_403_is_not_an_invalid_key():
    from backend.core.llm_retry import studio_code_for
    from backend.core.upstream_errors import UpstreamErrorType, classify_upstream_error

    for status in (401, 403, 402, 429, None):
        assert studio_code_for(UpstreamErrorType.INSUFFICIENT_QUOTA, status) == 'provider_error'
    assert studio_code_for(UpstreamErrorType.INVALID_KEY, 401) == 'llm_auth_invalid'
    assert studio_code_for(UpstreamErrorType.PERMISSION_DENIED, 403) == 'llm_auth_invalid'
    body = {'error': {'message': '用户余额不足', 'type': 'new_api_error', 'code': 'insufficient_user_quota'}}
    info = classify_upstream_error(403, body)
    assert info.error_type is UpstreamErrorType.INSUFFICIENT_QUOTA
    assert studio_code_for(info.error_type, 403) == 'provider_error'


def test_gemini_retry_delay_seconds_are_retry_after():
    from backend.core.llm_retry import parse_retry_after, retry_after_from_error

    assert parse_retry_after("17s") == 17.0
    assert parse_retry_after("17.234s") == 17.234
    assert parse_retry_after("86400s") == 120.0
    assert parse_retry_after({"seconds": 17, "nanos": 500_000_000}) == 17.5
    error = Exception("429 RESOURCE_EXHAUSTED")
    error.code = 429
    error.details = {
        "error": {
            "status": "RESOURCE_EXHAUSTED",
            "message": "You exceeded your current quota",
            "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "17s"}],
        }
    }
    assert retry_after_from_error(error) == 17.0
    # An explicit header still wins over the body delay.
    error.response = SimpleNamespace(headers={"Retry-After": "3"}, status_code=429)
    assert retry_after_from_error(error) == 3.0


def test_gemini_per_minute_429_is_retried(monkeypatch):
    concurrency.reset_limiter()
    sleeps = []
    monkeypatch.setattr("time.sleep", sleeps.append)
    n = {"i": 0}

    def flaky():
        n["i"] += 1
        if n["i"] < 2:
            error = Exception("429 RESOURCE_EXHAUSTED")
            error.code = 429
            error.details = {
                "error": {
                    "code": 429,
                    "status": "RESOURCE_EXHAUSTED",
                    "message": "You exceeded your current quota, please check your plan and billing details.",
                    "details": [
                        {"violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]},
                        {"retryDelay": "17s"},
                    ],
                }
            }
            raise error
        return "ok"

    assert _manager({"fn": flaky}).call_with_retry("p") == "ok"
    assert n["i"] == 2
    assert sleeps == [17.0]
    concurrency.reset_limiter()


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


def test_x3_insufficient_quota_is_not_llm_auth_invalid():
    """A2/X3: quota must stay provider_error so the frontend can offer recharge."""
    from backend.core.llm_retry import studio_code_for
    from backend.core.upstream_errors import UpstreamErrorType
    assert studio_code_for(UpstreamErrorType.INSUFFICIENT_QUOTA, 403) == 'provider_error'
    assert studio_code_for(UpstreamErrorType.INSUFFICIENT_QUOTA, 402) == 'provider_error'
    assert studio_code_for(UpstreamErrorType.INSUFFICIENT_QUOTA, 429) == 'provider_error'
    assert studio_code_for(UpstreamErrorType.INSUFFICIENT_QUOTA) != 'llm_auth_invalid'


def test_x3_sponsor_topup_url_prefers_topup_over_register():
    from backend.core import cloud_presets
    for key in ('api88', 'infistar', 'apimart'):
        url = cloud_presets.sponsor_topup_url(key)
        assert url and url.startswith('http'), key
    assert cloud_presets.sponsor_topup_url('openai') is None
    assert cloud_presets.sponsor_topup_url(None) is None
