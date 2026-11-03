"""Wrong API key (real SDK 401/403) -> llm_auth_invalid all the way to Studio + success-rate SQL (373e0b8a)."""
import re
from pathlib import Path

import httpx
import openai
import pytest

from backend.core import event_catalog, sentry_setup
from backend.core.llm_retry import classify_for_retry, studio_code_for
from backend.pipeline.failures import PipelineFailure, model_call_error_code
from backend.tests.test_pipeline_failures import SRT, _extractor, prompt_files  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]


def _sdk_error(status):
    request = httpx.Request('POST', 'https://api.example.invalid/v1/chat/completions')
    response = httpx.Response(status, request=request, json={
        'error': {'message': 'Incorrect API key provided', 'type': 'invalid_request_error', 'code': 'invalid_api_key'}})
    cls = openai.AuthenticationError if status == 401 else openai.PermissionDeniedError
    return cls('Incorrect API key provided', response=response, body=response.json()['error'])


@pytest.mark.parametrize('status', [401, 403])
def test_real_sdk_wrong_key_is_llm_auth_invalid(status):
    error = _sdk_error(status)
    info, got_status, _ = classify_for_retry(error)
    assert got_status == status
    assert studio_code_for(info.error_type, got_status) == 'llm_auth_invalid'
    assert model_call_error_code(error) == 'llm_auth_invalid'


@pytest.mark.parametrize('status', [401, 403])
def test_real_sdk_wrong_key_through_step1_to_studio(tmp_path, prompt_files, monkeypatch, status):  # noqa: F811
    srt = tmp_path / 'input.srt'
    srt.write_text(SRT, encoding='utf-8')
    extractor = _extractor(tmp_path, prompt_files, monkeypatch, [_sdk_error(status)])
    with pytest.raises(PipelineFailure) as caught:
        extractor.extract_outline(srt)
    assert caught.value.code == 'llm_auth_invalid'
    assert sentry_setup.studio_error_code(caught.value) == 'llm_auth_invalid'
    assert event_catalog.validate_event('studio_generation_finished', {
        'outcome': 'error', 'error_code': 'llm_auth_invalid', 'failure_stage': 'analyze'}) == []


def _excluded_per_query(sql):
    """v4: one (error_code, upstream_error_type) user_hard exclusion pair per statement in success_rate.sql."""
    pattern = r"OR ec IN \(([^)]*)\)\s*OR ue IN \(([^)]*)\)\) AS user_hard"
    return [(set(re.findall(r"'(\w+)'", code)), set(re.findall(r"'(\w+)'", up))) for code, up in re.findall(pattern, sql)]


def test_success_rate_sql_excludes_llm_auth_invalid_and_every_user_caused_code():
    sql = (ROOT / 'docs/analytics/success_rate.sql').read_text(encoding='utf-8')
    queries = _excluded_per_query(sql)
    assert len(queries) >= 2
    v4 = event_catalog.load_catalog()['attribution']['success_rate_v4']
    for codes, upstream in queries:
        assert 'llm_auth_invalid' in codes
        assert set(v4['overall_excluded_error_codes']) == codes
        assert set(v4['overall_excluded_upstream_types']) == upstream
        # legacy rows (<=1.5.7) carried invalid_key / insufficient_quota in error_code itself
        assert {'invalid_key', 'insufficient_quota'} <= codes
    assert len({frozenset(c) for c, _ in queries}) == 1, 'qualifying queries disagree on excluded codes'
