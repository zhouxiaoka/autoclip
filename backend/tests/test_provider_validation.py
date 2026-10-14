"""Settings validation: missing /v1, console host, wrong provider, spaced key, zero balance."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services import ai_model_settings as ai
from backend.services.provider_validation import validate_connection


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())


class _FakeResponse:
    def __init__(self, status, payload, headers=None, text=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {'content-type': 'application/json'}
        self.text = text if text is not None else (payload if isinstance(payload, str) else json.dumps(payload))

    def json(self):
        if isinstance(self._payload, str):
            return json.loads(self._payload)
        return self._payload


class _FakeClient:
    def __init__(self, handler):
        self.handler = handler

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, headers=None):
        return self.handler('GET', url, headers, None)

    def post(self, url, json=None, headers=None):
        return self.handler('POST', url, headers, json)


def _patch_httpx(monkeypatch, handler):
    monkeypatch.setattr(
        'httpx.Client',
        lambda *args, **kwargs: _FakeClient(handler),
    )


def _connection(**overrides):
    values = dict(
        id='c1', name='custom', provider='compatible',
        base_url='https://gw.example/v1', api_key='sk-test-key',
    )
    values.update(overrides)
    return ai.Connection(**values)


def test_key_spaces_are_stripped_on_the_connection():
    connection = ai.Connection(id='c', name='k', provider='openai', api_key='  sk-live-secret  \n')
    assert connection.api_key == 'sk-live-secret'


def test_url_internal_spaces_are_stripped_and_v1_added():
    connection = ai.Connection(id='c', name='c', provider='compatible', base_url='https://gw.example /v1')
    assert connection.base_url == 'https://gw.example/v1'


def test_compatible_url_gains_v1_and_drops_chat_completions():
    connection = ai.Connection(id='c', name='c', provider='compatible', base_url='https://gw.example/chat/completions')
    assert connection.base_url == 'https://gw.example/v1'


def test_missing_v1_is_normalized_then_models_404_is_bad_endpoint(monkeypatch):
    calls = []

    def handler(method, url, headers, body):
        calls.append(url)
        if method == 'GET':
            assert url == 'https://gw.example/v1/models'
            return _FakeResponse(404, {'error': {'message': 'not found'}})
        raise AssertionError('must not probe after /models 404')

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(_connection(base_url='https://gw.example'), 'gpt-4o-mini')
    assert result.ok is False
    assert result.error_type == 'bad_endpoint'
    assert result.normalized_base_url == 'https://gw.example/v1'
    assert result.base_url_host == 'gw.example'
    assert calls == ['https://gw.example/v1/models']


def test_console_host_is_rejected_without_a_network_call(monkeypatch):
    monkeypatch.setattr('httpx.Client', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('network')))
    result = validate_connection(
        _connection(base_url='https://platform.openai.com'),
        'gpt-4o-mini',
    )
    assert result.ok is False
    assert result.error_type == 'bad_endpoint'
    assert result.base_url_host in {'platform.openai.com', 'unknown'}


def test_html_console_response_is_flagged(monkeypatch):
    def handler(method, url, headers, body):
        return _FakeResponse(200, '<!DOCTYPE html><html>控制台</html>', headers={'content-type': 'text/html'},
                             text='<!DOCTYPE html><html>控制台</html>')

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(_connection(), 'gpt-4o-mini')
    assert result.error_type == 'bad_endpoint'
    assert result.ok is False


def test_wrong_provider_key_is_hinted_not_switched(monkeypatch):
    def handler(method, url, headers, body):
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'gpt-4o-mini'}]})
        return _FakeResponse(401, {'error': {'message': 'Incorrect API key provided'}})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(
        ai.Connection(id='c', name='OpenAI', provider='openai', api_key='AIzaSyLooksLikeGemini'),
        'gpt-4o-mini',
    )
    assert result.ok is False
    assert result.error_type == 'invalid_key'
    assert result.key_hint == 'gemini'


def test_group_forbidden_is_permission_denied(monkeypatch):
    def handler(method, url, headers, body):
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'gpt-4o-mini'}]})
        return _FakeResponse(403, {'error': {'message': '无权访问 default 分组'}})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(_connection(), 'gpt-4o-mini')
    assert result.ok is False
    assert result.error_type == 'permission_denied'


def test_zero_balance_is_insufficient_quota(monkeypatch):
    def handler(method, url, headers, body):
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'gpt-4o-mini'}]})
        return _FakeResponse(403, {'error': {'code': 'insufficient_user_quota', 'message': '余额不足'}})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(_connection(), 'gpt-4o-mini')
    assert result.ok is False
    assert result.error_type == 'insufficient_quota'


def test_success_probes_with_about_sixteen_tokens_and_returns_models(monkeypatch):
    posted = []

    def handler(method, url, headers, body):
        if method == 'GET':
            assert 'sk-test-key' in (headers or {}).get('Authorization', '')
            return _FakeResponse(200, {'data': [{'id': 'gpt-4o-mini'}, {'id': 'gpt-4o'}]})
        posted.append(body)
        return _FakeResponse(200, {'choices': [{'message': {'content': 'ok'}}]})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(_connection(), 'gpt-4o-mini')
    assert result.ok is True
    assert result.result == 'ok'
    assert result.model_ids == ['gpt-4o-mini', 'gpt-4o']
    assert posted[0]['max_tokens'] == 16
    assert posted[0]['model'] == 'gpt-4o-mini'


def test_http_test_endpoint_returns_classified_payload(monkeypatch):
    def handler(method, url, headers, body):
        return _FakeResponse(401, {'error': {'message': '无效的令牌'}})

    _patch_httpx(monkeypatch, handler)
    app = FastAPI()
    from backend.api.v1.settings import router
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post('/settings/ai-models/test', json={
            'connection': _connection().model_dump(),
            'model': 'gpt-4o-mini',
        })
    assert response.status_code == 200
    body = response.json()
    assert body['success'] is False
    assert body['error_type'] == 'invalid_key'
    assert body['base_url_host'] == 'gw.example'
    assert 'sk-test-key' not in response.text
    assert '无效的令牌' not in response.text


def test_failed_validation_saves_but_blocks_readiness_and_generation(monkeypatch):
    from backend.services.studio import readiness
    settings = ai.ModelSettings(
        connections=[_connection(validation_status='failed', validation_error_type='insufficient_quota')],
        analysis=ai.Assignment(connection_id='c1', model='gpt-4o-mini'),
    )
    ai.save(settings)
    loaded = ai.load()
    assert loaded.connections[0].api_key == 'sk-test-key'
    assert loaded.connections[0].validation_status == 'failed'
    monkeypatch.setattr(ai, 'for_editing', lambda: loaded)
    report = readiness.report()
    assert report['checks']['analysis'] == {'ok': False, 'code': 'validation_failed', 'repair': 'settings_ai'}
    with pytest.raises(ValueError, match='未通过校验'):
        readiness.ensure_analysis_usable()


def test_unchecked_legacy_connections_still_ready(monkeypatch):
    from backend.services.studio import readiness
    settings = ai.ModelSettings(
        connections=[_connection()],
        analysis=ai.Assignment(connection_id='c1', model='gpt-4o-mini'),
    )
    monkeypatch.setattr(ai, 'for_editing', lambda: settings)
    assert readiness.report()['checks']['analysis']['ok'] is True
    readiness.ensure_analysis_usable()


def test_inspect_without_a_saved_document_is_not_blocked():
    from backend.services.studio import readiness
    assert ai.load() is None
    readiness.ensure_analysis_usable()


def test_api88_wrong_stored_url_is_forced_to_the_preset(monkeypatch):
    seen = []

    def handler(method, url, headers, body):
        seen.append(url)
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'gpt-4o-mini'}]})
        return _FakeResponse(200, {'choices': [{'message': {'content': 'ok'}}]})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(
        ai.Connection(id='c', name='88', provider='api88', api_key='sk-88', base_url='https://api.openai.com/v1'),
        'gpt-4o-mini',
    )
    assert result.ok is True
    assert seen[0].startswith('https://88api.ai/v1/')
    assert result.base_url_host == '88api.ai'
