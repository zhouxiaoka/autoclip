"""Behavior tests for connection-test error codes."""
import json
import socket

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.connection_test_codes import (
    CONNECTION_TEST_ERROR_CODES,
    connection_test_error_code,
)
from backend.services import ai_model_settings as ai
from backend.services.provider_validation import validate_connection
"""1.5.7 success-rate must-have: every connection-test failure carries a closed-set error_code
and an integer upstream status; never the URL, key, path or upstream body."""

SECRET = 'sk-test-only-secret'
UPSTREAM_TEXT = 'upstream says private-detail'


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())


class _Resp:
    def __init__(self, status, payload, headers=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {'content-type': 'application/json'}
        self.text = payload if isinstance(payload, str) else json.dumps(payload)

    def json(self):
        return json.loads(self.text)


class _Client:
    def __init__(self, handler):
        self.handler = handler

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, headers=None):
        return self.handler('GET', url)

    def post(self, url, json=None, headers=None):
        return self.handler('POST', url)


def _patch(monkeypatch, handler):
    monkeypatch.setattr('httpx.Client', lambda *a, **k: _Client(handler))


def _conn(provider='compatible', **kw):
    values = {'id': 'c1', 'name': 'custom', 'provider': provider, 'base_url': 'https://gw.example/v1', 'api_key': SECRET}
    if provider == 'gemini':
        values.update(base_url='https://generativelanguage.googleapis.com/v1beta', base_url_source='user', preset_version=1)
    values.update(kw)
    return ai.Connection(**values)


def _models_ok(provider):
    if provider == 'gemini':
        return _Resp(200, {'models': [{'name': 'models/m1'}]})
    return _Resp(200, {'data': [{'id': 'm1'}]})


def _chat_fails(status, body):
    def handler(provider):
        def inner(method, url):
            if method == 'GET':
                return _models_ok(provider)
            return _Resp(status, body)
        return inner
    return handler


CHAT_CASES = [
    ('invalid_key', 401, {'error': {'message': UPSTREAM_TEXT, 'code': 'invalid_api_key'}}),
    ('model_not_found', 404, {'error': {'message': 'The model does not exist', 'code': 'model_not_found'}}),
    ('rate_limited', 429, {'error': {'message': UPSTREAM_TEXT}}),
    ('http_5xx', 503, {'error': {'message': UPSTREAM_TEXT}}),
]


def _assert_safe(result_or_text):
    text = result_or_text if isinstance(result_or_text, str) else json.dumps(result_or_text.as_api())
    assert SECRET not in text and UPSTREAM_TEXT not in text and 'private-detail' not in text


@pytest.mark.parametrize('provider', ['compatible', 'gemini'])
@pytest.mark.parametrize('code,status,body', CHAT_CASES)
def test_chat_probe_failure_carries_code_and_status(monkeypatch, provider, code, status, body):
    _patch(monkeypatch, _chat_fails(status, body)(provider))
    result = validate_connection(_conn(provider), 'm1')
    payload = result.as_api()
    assert payload['error_code'] == code
    assert payload['http_status'] == status
    assert payload['error_code'] in CONNECTION_TEST_ERROR_CODES
    _assert_safe(result)


@pytest.mark.parametrize('provider', ['compatible', 'gemini'])
def test_models_listing_failure_carries_code_and_status(monkeypatch, provider):
    # Gemini lists models natively: a rejected key fails here, before the chat probe.
    _patch(monkeypatch, lambda method, url: _Resp(401, {'error': {'message': UPSTREAM_TEXT}}))
    result = validate_connection(_conn(provider), 'm1')
    assert result.as_api()['error_code'] == 'invalid_key'
    assert result.as_api()['http_status'] == 401
    _assert_safe(result)


@pytest.mark.parametrize('provider', ['compatible', 'gemini'])
def test_timeout_dns_and_network(monkeypatch, provider):
    for exc, code in [
        (httpx.ReadTimeout('slow'), 'timeout'),
        (httpx.ConnectError('[Errno -2] Name or service not known'), 'dns'),
        (httpx.ConnectError('[Errno 111] Connection refused'), 'network'),
    ]:
        def handler(method, url, exc=exc):
            if method == 'GET':
                return _models_ok(provider)
            raise exc
        _patch(monkeypatch, handler)
        result = validate_connection(_conn(provider), 'm1')
        assert result.as_api()['error_code'] == code, (provider, code)
        assert result.as_api()['http_status'] is None


def test_dns_detected_through_gaierror_cause():
    from backend.core.upstream_errors import network_kind_of
    try:
        try:
            raise socket.gaierror(-2, 'x')
        except socket.gaierror as inner:
            raise httpx.ConnectError('connect failed') from inner
    except httpx.ConnectError as outer:
        assert network_kind_of(outer) == 'dns'


def test_empty_key_and_bad_base_url(monkeypatch):
    _patch(monkeypatch, lambda method, url: _Resp(401, {'error': {'message': UPSTREAM_TEXT}}))
    empty = validate_connection(_conn(api_key=''), 'm1')
    assert empty.as_api()['error_code'] == 'empty_key'
    # A persisted console address (bypassing constructor checks) and an HTML page both mean
    # the address is not a model API.
    legacy = _conn().model_copy(update={'base_url': 'https://platform.openai.com/v1'})
    assert validate_connection(legacy, 'm1').as_api()['error_code'] == 'bad_base_url'
    _patch(monkeypatch, lambda method, url: _Resp(200, '<html><body>console</body></html>', {'content-type': 'text/html'}))
    html = validate_connection(_conn(), 'm1')
    assert html.as_api()['error_code'] == 'bad_base_url'


def test_classification_stays_within_provider(monkeypatch):
    calls = []

    def handler(method, url):
        calls.append(url)
        return _Resp(401, {'error': {'message': UPSTREAM_TEXT}})
    _patch(monkeypatch, handler)
    validate_connection(_conn('gemini'), 'm1')
    assert calls and all('generativelanguage.googleapis.com' in url for url in calls)


def test_every_error_type_maps_into_the_closed_set():
    from backend.core.upstream_errors import UPSTREAM_ERROR_TYPES
    for kind in [*UPSTREAM_ERROR_TYPES, 'vision_unsupported', '', 'something_new']:
        assert connection_test_error_code(kind) in CONNECTION_TEST_ERROR_CODES


def test_http_endpoint_exception_branch_carries_code(monkeypatch):
    from backend.services import provider_validation

    def boom(*a, **k):
        raise httpx.ConnectError('Name or service not known')
    monkeypatch.setattr(provider_validation, 'validate_connection', boom)
    app = FastAPI()
    from backend.api.v1.settings import router
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post('/settings/ai-models/test', json={'connection': _conn().model_dump(), 'model': 'm1'})
    assert response.status_code == 200
    assert response.json()['error_code'] in ('dns', 'network')
    _assert_safe(response.text)


def test_http_endpoint_success_payload_has_status_and_code(monkeypatch):
    _patch(monkeypatch, _chat_fails(503, {'error': {'message': UPSTREAM_TEXT}})('compatible'))
    app = FastAPI()
    from backend.api.v1.settings import router
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post('/settings/ai-models/test', json={'connection': _conn().model_dump(), 'model': 'm1'})
    body = response.json()
    assert body['error_code'] == 'http_5xx' and body['http_status'] == 503
    _assert_safe(response.text)


# --- 1.5.7 (B): config_source enum + terminal identity ---------------------------------------

def test_config_source_enum_never_carries_strings():
    from backend.core.provider_presets import get_provider
    from backend.services.studio.failure_identity import config_source
    preset = get_provider('gemini')
    assert config_source('gemini', preset.base_url, preset.default_model) == 'preset'
    assert config_source('gemini', '', preset.default_model) == 'preset'
    saved = ai.Connection(id='c', name='g', provider='gemini', base_url=preset.base_url, api_key=SECRET)
    assert config_source('gemini', saved.base_url, preset.default_model) == 'preset'
    assert config_source('gemini', 'https://proxy.example/v1', preset.default_model) == 'customized'
    assert config_source('gemini', preset.base_url, 'my-private-finetune') == 'customized'
    assert config_source('compatible', 'https://gw.example/v1', 'm1') == 'customized'
    apimart = get_provider('apimart')
    assert config_source('apimart', apimart.base_url, 'qwen3.8-flash') == 'preset'
    assert config_source('apimart', apimart.base_url, 'account-only-model') == 'preset'
    assert config_source('apimart', 'https://proxy.example/v1', 'qwen3.8-flash') == 'customized'
    api88 = get_provider('api88')
    assert config_source('api88', api88.base_url, 'account-only-model') == 'preset'


def test_connection_test_endpoint_reports_config_source(monkeypatch):
    from backend.core.provider_presets import get_provider
    _patch(monkeypatch, _chat_fails(503, {'error': {'message': UPSTREAM_TEXT}})('gemini'))
    app = FastAPI()
    from backend.api.v1.settings import router
    app.include_router(router)
    preset = get_provider('gemini')
    with TestClient(app) as client:
        custom = client.post('/settings/ai-models/test', json={'connection': _conn().model_dump(), 'model': 'm1'}).json()
        stock = client.post('/settings/ai-models/test', json={'connection': _conn('gemini', base_url=preset.base_url).model_dump(), 'model': preset.default_model}).json()
    assert custom['config_source'] == 'customized' and stock['config_source'] == 'preset'
    assert stock['error_code'] == 'http_5xx' and stock['http_status'] == 503


def test_provider_identity_is_slug_plus_enum(monkeypatch):
    from backend.services.studio import failure_identity
    settings = ai.ModelSettings(connections=[_conn('gemini')], analysis=ai.Assignment(connection_id='c1', model='private-model'))
    monkeypatch.setattr(ai, 'load', lambda **k: settings)
    assert failure_identity.provider_identity() == {'provider': 'gemini', 'config_source': 'customized'}
    monkeypatch.setattr(ai, 'load', lambda **k: None)
    assert failure_identity.provider_identity() == {}


@pytest.mark.parametrize('phase,stage', [('screening', 'screening'), ('production', 'production'), (None, 'other')])
def test_restarted_analysis_without_instance_records_code_and_stage(phase, stage):
    from backend.services.studio import store
    analysis = {'status': 'running', 'run_id': 'r1'}
    if phase:
        analysis['phase'] = phase
    store.directory('p158').mkdir(parents=True, exist_ok=True)
    store.write('p158', {'id': 'p158', 'analysis': analysis})
    data = store.recover('p158')
    assert data['analysis']['status'] == 'failed'
    assert data['analysis']['error_code'] == store.RESTART_CODE
    assert data['analysis']['failure_stage'] == stage


@pytest.mark.parametrize('phase,stage', [('screening', 'screening'), ('production', 'production'), ('rendering', 'render'), (None, 'other')])
def test_expired_analysis_restart_branch_records_failure_stage(phase, stage):
    from backend.services.studio import store
    analysis = {'status': 'running', 'run_id': 'r1', 'instance': 'previous-process'}
    if phase:
        analysis['phase'] = phase
    data = {'id': 'p158', 'analysis': analysis}
    assert store._recover_interrupted_run(data) is True
    assert data['analysis']['error_code'] == store.RESTART_CODE
    assert data['analysis']['failure_stage'] == stage


def _stale(instance):
    return {'id': 'p158', 'analysis': {'status': 'running', 'run_id': 'r1', 'phase': 'screening', 'instance': instance}}


def test_restart_after_clean_shutdown_reports_clean():
    from backend.core import project_cancellation
    from backend.services.studio import store
    from backend.services.studio.shutdown_marker import mark
    old = 'a' * 32
    mark('user_quit', old)
    data = _stale(old)
    assert store._recover_interrupted_run(data)
    assert data['analysis']['shutdown_kind'] == 'clean'
    # begin_shutdown also runs on parent loss, so it must not claim a clean quit.
    project_cancellation.begin_shutdown()
    try:
        from backend.services.studio.shutdown_marker import shutdown_kind
        assert shutdown_kind(store.INSTANCE) != 'clean'
    finally:
        project_cancellation._shutting_down = False


def test_restart_without_marker_reports_crash_or_unknown():
    from backend.services.studio import store
    data = _stale('b' * 32)
    assert store._recover_interrupted_run(data)
    assert data['analysis']['shutdown_kind'] == 'crash'  # missing marker = crash
    data = _stale('legacy-instance')
    assert store._recover_interrupted_run(data)
    assert data['analysis']['shutdown_kind'] == 'unknown'  # not a valid instance id


def test_generation_restart_carries_shutdown_kind():
    from backend.services.studio import store
    from backend.services.studio.shutdown_marker import mark
    mark('update', 'd' * 32)
    data = _stale('d' * 32)
    data['generation'] = {'status': 'production', 'auto_start': True}
    assert store._recover_interrupted_run(data)
    assert data['generation']['shutdown_kind'] == 'clean'
    assert data['analysis']['shutdown_kind'] == 'clean'


@pytest.mark.parametrize('status,code', [(401, 'invalid_key'), (429, 'rate_limited'), (503, 'http_5xx')])
def test_visual_probe_http_status_is_kept(monkeypatch, status, code):
    from backend.services.studio import intelligence, vision_settings
    from backend.services import provider_validation

    class _Ok:
        ok = True

        def as_api(self):
            return {'success': True, 'ok': True, 'result': 'ok'}
    monkeypatch.setattr(provider_validation, 'validate_connection', lambda *a, **k: _Ok())
    monkeypatch.setattr(ai, 'chat_endpoint', lambda *a, **k: {'base_url': 'https://gw.example/v1', 'api_key': SECRET, 'model': 'm1'})

    def fail(_body):
        raise intelligence.VisionRequestError('http_error', '视觉接口请求失败', http_status=status)
    monkeypatch.setattr(vision_settings, 'test', fail)
    app = FastAPI()
    from backend.api.v1.settings import router
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post('/settings/ai-models/test', json={'connection': _conn().model_dump(), 'model': 'm1', 'vision': True, 'purpose': 'analysis'})
    body = response.json()
    assert body['http_status'] == status and body['error_code'] == code, body
    _assert_safe(response.text)
