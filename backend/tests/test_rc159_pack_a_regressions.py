"""1.5.9 Pack A regressions: provider probe, vision 422, quota cache, JSON parsing."""
from __future__ import annotations

import json
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1 import settings as settings_api
from backend.core import quota_precheck
from backend.services import ai_model_settings as ai
from backend.services import provider_validation as pv
from backend.services.studio import intelligence, vision_settings
from backend.utils.llm_client import LLMClient


class _FakeResponse:
    def __init__(self, status_code: int, body, headers: dict | None = None):
        self.status_code = status_code
        self.headers = headers or {'content-type': 'application/json'}
        if isinstance(body, (dict, list)):
            self._json = body
            self.text = json.dumps(body, ensure_ascii=False)
        else:
            self._json = None
            self.text = str(body)

    def json(self):
        if self._json is not None:
            return self._json
        return json.loads(self.text)


class _SequenceClient:
    def __init__(self, responses, calls):
        self._responses = list(responses)
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, json=None, headers=None, **kwargs):
        self._calls.append({'url': url, 'json': dict(json or {})})
        return self._responses.pop(0)


def test_probe_retries_reasoning_model_with_larger_budget(monkeypatch):
    calls = []
    responses = [
        _FakeResponse(200, {
            'choices': [{
                'message': {'content': '', 'reasoning_content': 'thinking about ok...'},
                'finish_reason': 'length',
            }]
        }),
        _FakeResponse(200, {
            'choices': [{
                'message': {'content': 'ok', 'reasoning_content': 'short thought'},
                'finish_reason': 'stop',
            }]
        }),
    ]
    monkeypatch.setattr(httpx, 'Client', lambda **kw: _SequenceClient(responses, calls))

    err = pv._probe('https://api.apimart.ai/v1', 'sk-test', 'qwen3.8-flash')
    assert err is None
    assert len(calls) == 2
    assert calls[0]['json']['max_tokens'] == pv.PROBE_MAX_TOKENS
    assert calls[1]['json']['max_tokens'] >= pv.PROBE_REASONING_MAX_TOKENS


def test_probe_retries_max_completion_tokens_on_relay_400(monkeypatch):
    calls = []
    responses = [
        _FakeResponse(400, {
            'error': {'message': "Unsupported parameter: 'max_tokens' is not supported with this model. Use 'max_completion_tokens' instead."}
        }),
        _FakeResponse(200, {
            'choices': [{'message': {'content': 'ok'}, 'finish_reason': 'stop'}]
        }),
    ]
    monkeypatch.setattr(httpx, 'Client', lambda **kw: _SequenceClient(responses, calls))

    err = pv._probe('https://api.apimart.ai/v1', 'sk-test', 'gpt-5-mini')
    assert err is None
    assert len(calls) == 2
    assert 'max_tokens' in calls[0]['json']
    assert 'max_tokens' not in calls[1]['json']
    assert calls[1]['json']['max_completion_tokens'] >= pv.PROBE_REASONING_MAX_TOKENS


def test_probe_retries_stream_only_thinking_model(monkeypatch):
    calls = []
    sse_body = (
        'data: {"choices":[{"delta":{"reasoning_content":"hmm"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
        'data: [DONE]\n\n'
    )
    responses = [
        _FakeResponse(400, {'error': {'message': 'This model only support stream mode, please enable the stream parameter.'}}),
        _FakeResponse(200, sse_body, headers={'content-type': 'text/event-stream'}),
    ]
    monkeypatch.setattr(httpx, 'Client', lambda **kw: _SequenceClient(responses, calls))

    err = pv._probe('https://dashscope.aliyuncs.com/compatible-mode/v1', 'sk-test', 'qwq-plus')
    assert err is None
    assert len(calls) == 2
    assert calls[0]['json']['stream'] is False
    assert calls[1]['json']['stream'] is True


def test_trial_once_retries_json_object_and_max_completion_tokens_and_parses_think(monkeypatch):
    calls = []
    responses = [
        _FakeResponse(400, {'error': {'message': "Unsupported parameter: 'max_tokens'. Use 'max_completion_tokens'."}}),
        _FakeResponse(400, {'error': {'message': 'json_object is not supported in thinking mode'}}),
        _FakeResponse(200, {
            'choices': [{'message': {'content': '<think>plan</think>\n[{"title":"t","subtopics":["a"]}]'}}]
        }),
    ]
    monkeypatch.setattr(httpx, 'Client', lambda **kw: _SequenceClient(responses, calls))

    result = pv._trial_once('https://api.apimart.ai/v1', 'sk-test', 'gpt-5-mini', 'prompt')
    assert result['ok_http'] is True
    assert result['json_ok'] is True
    assert len(calls) == 3
    assert 'max_completion_tokens' in calls[1]['json']
    assert 'response_format' not in calls[2]['json']


def test_settings_test_vision_user_facing_error_returns_200_vision_unsupported(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    app = FastAPI()
    app.include_router(settings_api.router)
    client = TestClient(app)

    monkeypatch.setattr(
        pv,
        'validate_connection_with_probe',
        lambda *a, **k: pv.ValidationResult(ok=True, result='ok', model_ids=['kimi-k3']),
    )

    def fail_vision(*_a, **_k):
        raise intelligence.UserFacingError('接口已响应，但图像识别测试未通过；请确认所选模型支持图片输入')

    monkeypatch.setattr(vision_settings, 'test', fail_vision)

    resp = client.post('/settings/ai-models/test', json={
        'connection': {
            'id': 'c1',
            'name': 'Kimi',
            'provider': 'kimi',
            'base_url': 'https://api.moonshot.cn/v1',
            'api_key': 'sk-test-valid',
        },
        'model': 'kimi-k3',
        'vision': True,
        'purpose': 'analysis',
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body['ok'] is False
    assert body['error_type'] == 'vision_unsupported'
    assert body['error_code'] == 'vision_unsupported'


def test_quota_precheck_cache_clears_on_settings_save_and_resolves_empty_base_url(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    quota_precheck.clear_cache()

    probe_results = iter(['exhausted', 'ok'])
    monkeypatch.setattr(quota_precheck, '_probe_new_api', lambda base, key: next(probe_results))

    first = quota_precheck.check_quota(provider='api88', base_url='https://api.88api.ai/v1', api_key='sk-88-key')
    assert first == 'exhausted'
    # Still cached before save
    assert quota_precheck.check_quota(provider='api88', base_url='https://api.88api.ai/v1', api_key='sk-88-key') == 'exhausted'

    app = FastAPI()
    app.include_router(settings_api.router)
    client = TestClient(app)

    save_resp = client.put('/settings/ai-models', json={
        'connections': [{
            'id': 'c88',
            'name': '88API',
            'provider': 'api88',
            'base_url': '',
            'api_key': 'sk-88-key',
            'validation_status': 'ok',
        }],
        'analysis': {'connection_id': 'c88', 'model': 'qwen3.8-flash', 'capability': 'auto'},
    })
    assert save_resp.status_code == 200

    # After save, cache must be cleared AND empty base_url must resolve via preset endpoint -> 'ok'
    status, extras = quota_precheck.check_for_analysis_settings()
    assert status == 'ok'
    assert extras.get('provider') == 'api88'


def test_intelligence_decode_json_handles_think_prose_and_single_line_fence():
    assert intelligence.decode_json('<think>reasoning step</think>\n{"a": 1}') == {'a': 1}
    assert intelligence.decode_json('Here is the JSON result:\n```json\n{"a": 2}\n```') == {'a': 2}
    assert intelligence.decode_json('```{"a": 3}```') == {'a': 3}
    assert intelligence.decode_json('Result: {"a": 4} Hope this helps!') == {'a': 4}
    with pytest.raises(ValueError):
        intelligence.decode_json('```not json```')


def test_llm_client_fix_common_json_errors_preserves_quoted_keys_and_value_colons():
    client = object.__new__(LLMClient)
    # Trailing comma forces parse_json_response into fix_common_json_errors
    raw = '{"start_time": "00:01:23", "title": "Note: important clip",}'
    parsed = client.parse_json_response(raw)
    assert parsed == {'start_time': '00:01:23', 'title': 'Note: important clip'}
