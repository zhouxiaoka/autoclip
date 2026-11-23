"""Gemini requests errors keep their provider identity across the redaction boundary."""
import json

import pytest
import requests

from backend.core.failure_attribution import FailureKind, classify_failure, frozen_error_code, http_status_of
from backend.core.llm_providers import GeminiProvider
from backend.core.llm_retry import classify_for_retry
from backend.core.llm_telemetry import log_safe_exception
from backend.core.upstream_errors import http_error_parts


@pytest.mark.parametrize('case,status,upstream,code,retryable', [
    ('timeout', None, 'timeout', 'timeout', True),
    ('connection', None, 'connection', 'connection', True),
    ('rate', 429, 'rate_limited', 'rate_limited', True),
    ('invalid_key', 400, 'invalid_key', 'llm_auth_invalid', False),
    ('quota', 429, 'insufficient_quota', 'provider_error', False),
])
def test_gemini_requests_error_attribution(case, status, upstream, code, retryable, monkeypatch, caplog):
    body = None
    if status is None:
        error_type = requests.Timeout if case == 'timeout' else requests.ConnectionError
        original = error_type('fixture AQ.test-key')
    else:
        details = []
        if case == 'invalid_key':
            details = [{'reason': 'API_KEY_INVALID'}]
        elif case == 'quota':
            details = [{'violations': [{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}]
        body = {'error': {'code': status, 'status': 'INVALID_ARGUMENT' if status == 400 else 'RESOURCE_EXHAUSTED',
                          'message': 'fixture failure', 'details': details}}
        response = requests.Response()
        response.status_code = status
        response._content = json.dumps(body).encode()
        response.headers['Retry-After'] = '7'
        original = requests.HTTPError('fixture AQ.test-key', response=response)

    assert not classify_failure(original).decided
    direct = log_safe_exception(original)
    assert direct.attribution is None and frozen_error_code(direct) is None

    def fail(*args, **kwargs):
        raise original

    monkeypatch.setattr(requests, 'post', fail)
    with pytest.raises(RuntimeError) as caught:
        GeminiProvider('AQ.test-key', 'gemini-2.5-flash').call('sample')
    error = caught.value
    info, actual_status, delay = classify_for_retry(error)
    print(case, {'kind': classify_failure(error).kind.value, 'upstream': info.error_type.value,
                 'status': actual_status, 'retryable': info.retryable,
                 'frozen_error_code': frozen_error_code(error)})
    assert info.error_type.value == upstream
    assert info.retryable is retryable
    assert actual_status == status and http_status_of(error) == status
    assert delay == (7 if status is not None else None)
    if body is not None:
        assert http_error_parts(error)[1] == body
    assert classify_failure(error).kind is FailureKind.MODEL
    assert error.attribution is not None
    assert error.attribution.provider == 'gemini'
    assert error.attribution.upstream_error_type == (upstream if status is not None else None)
    assert error.attribution.http_status == status
    assert frozen_error_code(error) == code
    assert error.__cause__ is None and error.__suppress_context__
    assert 'AQ.test-key' not in str(error)
    assert 'AQ.test-key' not in caplog.text


@pytest.mark.parametrize('error_type', [ValueError, requests.exceptions.InvalidURL, requests.exceptions.InvalidHeader])
def test_gemini_local_errors_do_not_gain_model_attribution(error_type, monkeypatch):
    def fail(*args, **kwargs):
        raise error_type('fixture invalid input')

    monkeypatch.setattr(requests, 'post', fail)
    with pytest.raises(RuntimeError) as caught:
        GeminiProvider('AQ.test-key', 'gemini-2.5-flash').call('sample')
    assert not classify_failure(caught.value).decided
    assert caught.value.attribution is None
    assert frozen_error_code(caught.value) is None
