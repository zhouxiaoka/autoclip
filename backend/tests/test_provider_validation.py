"""Settings validation: missing /v1, console host, wrong provider, spaced key, zero balance."""
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.upstream_errors import HINT_KEYS, UpstreamErrorType
from backend.core.provider_model_fetch import GEMINI_PAGE_SIZE
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


@pytest.mark.parametrize('path,expected', [
    ('/v1beta', '/v1beta/openai'),
    ('/v1beta/openai', '/v1beta/openai'),
    ('/v1', '/v1'),
])
@pytest.mark.parametrize('provider', ['gemini', 'compatible'])
def test_gemini_validation_requests_use_the_shared_chat_root(monkeypatch, path, expected, provider):
    root = 'https://generativelanguage.googleapis.com'
    calls = []

    def handler(method, url, headers, body):
        calls.append(url)
        if method == 'GET':
            if provider == 'gemini':
                assert 'x-goog-api-key' in headers
                return _FakeResponse(200, {'models': [{'name': 'models/gemini-test'}]})
            return _FakeResponse(200, {'data': [{'id': 'gemini-test'}]})
        return _FakeResponse(200, {'choices': [{'message': {'content': 'ok'}}]})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(ai.Connection(
        id='g', name='Gemini', provider=provider, base_url=root + path,
        base_url_source='user', preset_version=1, api_key='test-only-key',
    ), 'gemini-test')
    assert result.ok
    # P4 lists Gemini models natively; the chat probe uses the shared OpenAI root.
    models_url = root + expected.removesuffix('/openai') + '/models' + f'?pageSize={GEMINI_PAGE_SIZE}' if provider == 'gemini' else root + expected + '/models'
    assert calls == [models_url, root + expected + '/chat/completions']
    assert root + '/v1beta/chat/completions' not in calls


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
    assert result.hint_key == HINT_KEYS[UpstreamErrorType.BAD_ENDPOINT]
    assert result.normalized_base_url == 'https://gw.example/v1'
    assert result.base_url_host == 'gw.example'
    assert calls == ['https://gw.example/v1/models']


def test_console_host_is_rejected_without_a_network_call(monkeypatch):
    from pydantic import ValidationError
    monkeypatch.setattr('httpx.Client', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('network')))
    with pytest.raises(ValidationError, match='控制台或官网'):
        _connection(base_url='https://platform.openai.com')
    # A stored row that skipped the constructor still must not hit the network.
    result = validate_connection(
        ai.Connection.model_construct(
            id='c1', name='custom', provider='compatible',
            base_url='https://platform.openai.com', api_key='sk-test-key',
        ),
        'gpt-4o-mini',
    )
    assert result.ok is False
    assert result.error_type == 'bad_endpoint'
    assert result.hint_key == HINT_KEYS[UpstreamErrorType.BAD_ENDPOINT]
    assert result.base_url_host in {'platform.openai.com', 'unknown'}


def test_infistar_api_host_reaches_validation_probes(monkeypatch):
    calls = []

    def handler(method, url, headers, body):
        calls.append((method, url))
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'fixture-model'}]})
        return _FakeResponse(200, {'choices': [{'message': {'content': 'ok'}}]})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(_connection(base_url='https://infistar.ai/v1'), 'fixture-model')
    assert result.ok is True
    assert calls == [
        ('GET', 'https://infistar.ai/v1/models'),
        ('POST', 'https://infistar.ai/v1/chat/completions'),
    ]


def test_html_console_response_is_flagged(monkeypatch):
    def handler(method, url, headers, body):
        return _FakeResponse(200, '<!DOCTYPE html><html>控制台</html>', headers={'content-type': 'text/html'},
                             text='<!DOCTYPE html><html>控制台</html>')

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(_connection(), 'gpt-4o-mini')
    assert result.error_type == 'bad_endpoint'
    assert result.hint_key == HINT_KEYS[UpstreamErrorType.BAD_ENDPOINT]
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
    assert result.hint_key == HINT_KEYS[UpstreamErrorType.INVALID_KEY]
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
    assert result.hint_key == HINT_KEYS[UpstreamErrorType.PERMISSION_DENIED]


def test_zero_balance_is_insufficient_quota(monkeypatch):
    def handler(method, url, headers, body):
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'gpt-4o-mini'}]})
        return _FakeResponse(403, {'error': {'code': 'insufficient_user_quota', 'message': '余额不足'}})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(_connection(), 'gpt-4o-mini')
    assert result.ok is False
    assert result.error_type == 'insufficient_quota'
    assert result.hint_key == HINT_KEYS[UpstreamErrorType.INSUFFICIENT_QUOTA]


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
    assert posted[0]['stream'] is False


@pytest.mark.parametrize('provider', ['gemini', 'compatible'])
def test_gemini_native_models_and_shared_openai_chat_root(monkeypatch, provider):
    calls = []
    root = 'https://generativelanguage.googleapis.com/v1beta/openai'

    def handler(method, url, headers, body):
        calls.append((method, url))
        if method == 'GET':
            if provider == 'gemini':
                assert 'x-goog-api-key' in headers
                return _FakeResponse(200, {'models': [{'name': 'models/gemini-test'}]})
            return _FakeResponse(200, {'data': [{'id': 'gemini-test'}]})
        return _FakeResponse(200, {'choices': [{'message': {'content': 'ok'}}]})

    _patch_httpx(monkeypatch, handler)
    # Also cover legacy persisted connections that bypass constructor cleanup.
    connection = _connection(provider=provider).model_copy(update={
        'base_url': 'https://generativelanguage.googleapis.com/v1beta',
    })
    result = validate_connection(connection, 'gemini-test')
    assert result.ok is True
    assert result.normalized_base_url == root
    models_url = root.removesuffix('/openai') + f'/models?pageSize={GEMINI_PAGE_SIZE}' if provider == 'gemini' else root + '/models'
    assert calls == [('GET', models_url), ('POST', root + '/chat/completions')]


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
    assert body['hint_key'] == HINT_KEYS[UpstreamErrorType.INVALID_KEY]
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


@pytest.mark.parametrize('catalog_provider_id', ['', 'azure-openai'])
@pytest.mark.parametrize('stage', ['GET', 'POST'])
@pytest.mark.parametrize('failure', ['timeout', 'connection', 429, 500, 502, 503, 504, 529, 'html_503', 401])
def test_transient_validation_does_not_block_generation(monkeypatch, catalog_provider_id, stage, failure):
    import httpx
    from backend.services.studio import readiness

    def handler(method, url, headers, body):
        if method != stage:
            return _FakeResponse(200, {'data': [{'id': 'gpt-4o-mini'}]})
        if failure == 'timeout':
            raise httpx.ReadTimeout('fixture')
        if failure == 'connection':
            raise httpx.ConnectError('fixture')
        if failure == 'html_503':
            return _FakeResponse(503, '<html>Unavailable</html>', {'content-type': 'text/html'})
        return _FakeResponse(failure, {'error': {'message': 'fixture'}})

    _patch_httpx(monkeypatch, handler)
    connection = _connection(catalog_provider_id=catalog_provider_id)
    result = validate_connection(connection, 'gpt-4o-mini').as_api()
    expected = 'failed' if failure == 401 else 'transient'
    assert result['ok'] is False
    assert result['result'] == expected
    if failure == 401:
        assert result['error_type'] == 'invalid_key'
    elif failure == 'timeout':
        assert result['error_type'] == 'timeout'
    checked = ai.Connection.model_validate({
        **connection.model_dump(), 'validation_status': result['result'],
        'validation_error_type': result['error_type'],
    })
    ai.save(ai.ModelSettings(
        connections=[checked], analysis=ai.Assignment(connection_id='c1', model='gpt-4o-mini'),
        analysis_mode='subtitle', allow_visual_screening=False,
    ))
    loaded = ai.load()
    assert loaded.connections[0].validation_status == expected
    monkeypatch.setattr(ai, 'for_editing', lambda: loaded)
    check = readiness.report()['checks']['analysis']
    assert check['ok'] is (failure != 401)
    if failure == 401:
        assert check['code'] == 'validation_failed'
        with pytest.raises(ValueError):
            readiness.ensure_analysis_usable()
    else:
        readiness.ensure_analysis_usable()
        ai.require_analysis(loaded)


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


def test_text_only_vision_follow_saves_but_blocks_generation(monkeypatch):
    from backend.services.provider_validation import VISION_BLOCK_MESSAGE
    from backend.services.studio import readiness
    settings = ai.ModelSettings(
        connections=[_connection()],
        analysis=ai.Assignment(connection_id='c1', model='deepseek-flash', capability='text'),
        analysis_mode='auto',
    )
    # D7: auto + text-only is not a readiness block (subtitle fallback).
    assert ai.vision_follow_lacks_capability(settings) is False
    ai.save(settings)
    loaded = ai.load()
    assert loaded.analysis.capability == 'text'
    assert loaded.connections[0].validation_status == 'unchecked'
    monkeypatch.setattr(ai, 'for_editing', lambda: loaded)
    report = readiness.report()
    assert report['checks']['visual'] == {'ok': True, 'code': 'optional', 'repair': 'none'}
    assert report['ready'] is True
    readiness.ensure_analysis_usable()  # must not raise
    # Explicit visual mode still blocks:
    visual = settings.model_copy(update={'analysis_mode': 'visual'})
    assert ai.vision_follow_lacks_capability(visual) is True
    assert VISION_BLOCK_MESSAGE.startswith('画面理解')


def test_visual_mode_without_vision_saves_but_blocks_generation(monkeypatch):
    from backend.services.studio import readiness
    settings = ai.ModelSettings(
        connections=[_connection()],
        analysis=ai.Assignment(connection_id='c1', model='gpt-4o-mini', capability='text'),
        analysis_mode='visual',
    )
    ai.save(settings)
    loaded = ai.load()
    monkeypatch.setattr(ai, 'for_editing', lambda: loaded)
    assert readiness.report()['checks']['visual']['code'] == 'vision_unsupported'
    with pytest.raises(ValueError, match='设置 → 服务商与模型'):
        readiness.ensure_analysis_usable()


def test_subtitle_mode_text_model_does_not_block(monkeypatch):
    from backend.services.studio import readiness
    settings = ai.ModelSettings(
        connections=[_connection()],
        analysis=ai.Assignment(connection_id='c1', model='deepseek-flash', capability='text'),
        analysis_mode='subtitle',
        allow_visual_screening=False,
    )
    assert ai.vision_follow_lacks_capability(settings) is False
    ai.save(settings)
    monkeypatch.setattr(ai, 'for_editing', lambda: ai.load())
    assert readiness.report()['checks']['visual'] == {'ok': True, 'code': 'not_required', 'repair': 'none'}
    readiness.ensure_analysis_usable()


def test_multimodal_follow_and_unresolved_auto_do_not_flag():
    vision_ok = ai.ModelSettings(
        connections=[_connection(provider='openai', base_url='')],
        analysis=ai.Assignment(connection_id='c1', model='gpt-4o-mini', capability='auto'),
        analysis_mode='auto',
    )
    assert ai.vision_follow_lacks_capability(vision_ok) is False
    unresolved = ai.ModelSettings(
        connections=[_connection(provider='openai', base_url='')],
        analysis=ai.Assignment(connection_id='c1', model='o3-mini', capability='auto'),
        analysis_mode='auto',
    )
    assert ai.vision_follow_lacks_capability(unresolved) is False
    visual_unresolved = unresolved.model_copy(update={'analysis_mode': 'visual'})
    assert ai.vision_follow_lacks_capability(visual_unresolved) is True


def test_vision_unsupported_is_not_an_upstream_type():
    from backend.core.upstream_errors import UPSTREAM_ERROR_TYPES
    assert 'vision_unsupported' not in UPSTREAM_ERROR_TYPES


def test_dedicated_text_vision_assignment_is_flagged():
    settings = ai.ModelSettings(
        connections=[_connection()],
        analysis=ai.Assignment(connection_id='c1', model='gpt-4o', capability='multimodal'),
        vision=ai.Assignment(connection_id='c1', model='deepseek-flash', capability='text'),
        analysis_mode='auto',
    )
    # D7: auto does not flag; explicit visual does.
    assert ai.vision_follow_lacks_capability(settings) is False
    visual = settings.model_copy(update={'analysis_mode': 'visual'})
    assert ai.vision_follow_lacks_capability(visual) is True


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
    from backend.core.provider_presets import get_provider
    official = get_provider('api88').base_url.rstrip('/') + '/'
    assert seen[0].startswith(official)
    assert result.base_url_host == 'api.88api.ai'


@pytest.mark.parametrize('purpose,model', [('cover', 'image-only'), ('transcription', 'whisper-1')])
def test_non_chat_connection_checks_account_access_without_chat_probe(monkeypatch, purpose, model):
    calls = []

    def handler(method, url, headers, body):
        calls.append((method, url))
        assert method == 'GET', 'image and ASR models must never be sent to chat/completions'
        return _FakeResponse(200, {'data': [{'id': model}]})

    _patch_httpx(monkeypatch, handler)
    app = FastAPI()
    from backend.api.v1.settings import router
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post('/settings/ai-models/test', json={
            'connection': _connection().model_dump(), 'model': model, 'purpose': purpose,
        })
    assert response.status_code == 200
    assert response.json()['ok'] is True
    assert calls == [('GET', 'https://gw.example/v1/models')]


@pytest.mark.parametrize('model', [
    'qwen-audio-3.1-asr-flash', 'qwen-audio-3.0-asr-flash', 'fun-asr-flash-2026-06-15',
])
def test_dashscope_sync_asr_passes_when_absent_from_the_account_list(monkeypatch, model):
    calls = []

    def handler(method, url, headers, body):
        calls.append((method, url))
        assert method == 'GET'
        return _FakeResponse(200, {'data': [{'id': 'qwen-plus'}]})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(
        _connection(provider='dashscope', base_url='', name='百炼'),
        model, purpose='transcription',
    )
    assert result.ok is True
    assert calls == [('GET', 'https://dashscope.aliyuncs.com/compatible-mode/v1/models')]


def test_dashscope_sync_asr_still_rejects_a_bad_key(monkeypatch):
    def handler(method, url, headers, body):
        assert method == 'GET'
        return _FakeResponse(401, {'error': {'message': 'Incorrect API key provided'}})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(
        _connection(provider='dashscope', base_url='', name='百炼'),
        'qwen-audio-3.1-asr-flash', purpose='transcription',
    )
    assert result.ok is False
    assert result.error_type == 'invalid_key'


def test_unadapted_or_non_bailian_asr_still_requires_the_account_list(monkeypatch):
    def handler(method, url, headers, body):
        return _FakeResponse(200, {'data': [{'id': 'qwen-plus'}]})

    _patch_httpx(monkeypatch, handler)
    missing = validate_connection(
        _connection(provider='dashscope', base_url='', name='百炼'),
        'paraformer-v2', purpose='transcription',
    )
    assert missing.ok is False and missing.error_type == 'model_not_found'
    other = validate_connection(_connection(), 'qwen-audio-3.1-asr-flash', purpose='transcription')
    assert other.ok is False and other.error_type == 'model_not_found'


@pytest.mark.parametrize('purpose', ['cover', 'transcription'])
@pytest.mark.parametrize('status,expected', [(401, 'invalid_key'), (200, 'model_not_found')])
def test_non_chat_access_never_accepts_unauthorized_or_unlisted_models(monkeypatch, purpose, status, expected):
    def handler(method, url, headers, body):
        assert method == 'GET'
        return _FakeResponse(status, {'data': [{'id': 'another-model'}]} if status == 200
                             else {'error': {'message': 'Incorrect API key provided'}})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(_connection(), 'selected-model', purpose=purpose)
    assert result.ok is False
    assert result.error_type == expected
    assert result.base_url_host == 'gw.example'


def test_cover_access_uses_image_address_without_replacing_chat_address(monkeypatch):
    def handler(method, url, headers, body):
        assert (method, url) == ('GET', 'https://images.example/v1/models')
        return _FakeResponse(200, {'data': [{'id': 'image-only'}]})

    _patch_httpx(monkeypatch, handler)
    app = FastAPI()
    from backend.api.v1.settings import router
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post('/settings/ai-models/test', json={
            'connection': _connection(image_base_url='https://images.example/v1').model_dump(),
            'model': 'image-only', 'purpose': 'cover',
        })
    assert response.status_code == 200
    assert response.json()['ok'] is True
    assert response.json()['base_url_host'] == 'images.example'
    assert response.json()['normalized_base_url'] == 'https://gw.example/v1'


def test_explicit_vision_purpose_runs_vision_validation(monkeypatch):
    from backend.services import provider_validation
    from backend.services.studio import vision_settings
    monkeypatch.setattr(provider_validation, 'validate_connection', lambda *args: provider_validation._ok('https://gw.example/v1', None, ['gpt-4o']))
    probes = []

    def vision_probe(value):
        probes.append(value)
        return {'success': True}

    monkeypatch.setattr(vision_settings, 'test', vision_probe)
    app = FastAPI()
    from backend.api.v1.settings import router
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post('/settings/ai-models/test', json={
            'connection': _connection().model_dump(), 'model': 'gpt-4o', 'purpose': 'vision',
        })
    assert response.status_code == 200
    assert response.json()['ok'] is True
    assert len(probes) == 1
    assert probes[0].model == 'gpt-4o'


def _closed_local_port():
    import socket
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()  # nothing listens here now -> connection refused
    return port


def test_e6_ollama_not_running_gets_inline_start_hint():
    from backend.services.provider_validation import LOCAL_SERVICE_DOWN_HINT_KEY
    port = _closed_local_port()
    conn = ai.Connection(id='o1', name='Ollama', provider='ollama', base_url=f'http://127.0.0.1:{port}/v1')
    result = validate_connection(conn, 'qwen2.5:7b')
    assert result.ok is False
    assert result.error_type == 'connection'
    assert result.hint_key == LOCAL_SERVICE_DOWN_HINT_KEY
    assert 'Ollama' in result.hint_key
    assert result.as_api()['hint_key'] == LOCAL_SERVICE_DOWN_HINT_KEY


def test_e6_remote_connection_error_keeps_generic_hint(monkeypatch):
    from types import SimpleNamespace
    from backend.services import provider_validation as pv
    fetched = SimpleNamespace(recommended={}, truncated=False, message_key='')
    monkeypatch.setattr(pv, '_get_models', lambda *a, **k: ([], pv._classify(None, '', error_name='ConnectError'), fetched))
    result = validate_connection(_connection(base_url='https://api.example.com/v1'), 'm')
    assert result.error_type == 'connection'
    assert result.hint_key == HINT_KEYS[UpstreamErrorType.CONNECTION]


def test_e6_local_service_down_hint_exists_in_all_eight_locales():
    from pathlib import Path
    from backend.services.provider_validation import LOCAL_SERVICE_DOWN_HINT_KEY

    root = Path(__file__).resolve().parents[2] / 'frontend' / 'src' / 'i18n' / 'locales'
    langs = ('zh', 'en', 'es', 'fr', 'ja', 'ko', 'pt', 'ru')
    catalogs = {lang: json.loads((root / f'{lang}.json').read_text(encoding='utf-8')) for lang in langs}
    assert catalogs['zh'][LOCAL_SERVICE_DOWN_HINT_KEY] == LOCAL_SERVICE_DOWN_HINT_KEY
    for lang in langs:
        text = catalogs[lang].get(LOCAL_SERVICE_DOWN_HINT_KEY)
        assert text and str(text).strip(), f'{lang} missing E6 local-service-down hint'
        if lang != 'zh':
            assert text != LOCAL_SERVICE_DOWN_HINT_KEY, f'{lang} still uses Chinese source string'
            assert 'Ollama' in text, f'{lang} should name Ollama'


# only loopback counts as "this machine"; LAN / .local gateways keep the generic hint.
@pytest.mark.parametrize('base,local', [
    ('http://127.0.0.1:11434/v1', True),
    ('http://127.8.0.1:11434/v1', True),
    ('http://localhost:1234/v1', True),
    ('http://ollama.localhost:11434/v1', True),
    ('http://[::1]:11434/v1', True),
    ('http://192.168.1.20:11434/v1', False),
    ('http://10.0.0.5:11434/v1', False),
    ('http://172.16.3.4:8000/v1', False),
    ('http://gpu-box.local:11434/v1', False),
    ('http://169.254.10.10:11434/v1', False),
    ('http://host.docker.internal:11434/v1', False),
    ('https://api.example.com/v1', False),
])
def test_r10_local_service_down_hint_only_for_loopback(monkeypatch, base, local):
    from types import SimpleNamespace
    from backend.services import provider_validation as pv
    fetched = SimpleNamespace(recommended={}, truncated=False, message_key='')
    monkeypatch.setattr(pv, '_get_models', lambda *a, **k: ([], pv._classify(None, '', error_name='ConnectError'), fetched))
    result = validate_connection(_connection(base_url=base), 'm')
    assert result.error_type == 'connection'
    expected = pv.LOCAL_SERVICE_DOWN_HINT_KEY if local else HINT_KEYS[UpstreamErrorType.CONNECTION]
    assert result.hint_key == expected


@pytest.mark.parametrize('content', ['', '   ', None])
def test_probe_rejects_an_empty_or_blank_answer(monkeypatch, content):
    def handler(method, url, headers, body):
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'gpt-4o-mini'}]})
        return _FakeResponse(200, {'choices': [{'message': {'content': content}}]})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(_connection(), 'gpt-4o-mini')
    assert result.ok is False
    assert result.as_api()['error_code'] == 'unknown'


def test_probe_rejects_a_body_that_is_not_a_completion(monkeypatch):
    def handler(method, url, headers, body):
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'gpt-4o-mini'}]})
        return _FakeResponse(200, {'ok': True, 'message': 'pong'})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(_connection(), 'gpt-4o-mini')
    assert result.ok is False
    assert result.as_api()['error_code'] == 'unknown'


@pytest.mark.parametrize('status,body,code', [
    (400, {'error': {'code': 'context_length_exceeded', 'message': 'too long'}}, 'invalid_request'),
    (400, {'code': 'InvalidParameter', 'message': 'range out of bounds'}, 'invalid_request'),
    (400, {'error': {'code': 'content_filter', 'message': 'blocked'}}, 'invalid_request'),
    (200, {'error': {'code': 'invalid_api_key', 'message': 'bad'}}, 'invalid_key'),
])
def test_probe_maps_upstream_error_code(monkeypatch, status, body, code):
    def handler(method, url, headers, payload):
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'gpt-4o-mini'}]})
        return _FakeResponse(status, body)

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(_connection(), 'gpt-4o-mini')
    assert result.ok is False
    assert result.as_api()['error_code'] == code
    assert result.as_api()['error_code'] != 'unknown' or code == 'unknown'


def test_dashscope_probe_sends_enable_thinking_false(monkeypatch):
    posted = []

    def handler(method, url, headers, body):
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'qwen3.8-flash'}]})
        posted.append(body)
        return _FakeResponse(200, {'choices': [{'message': {'content': 'ok'}}]})

    _patch_httpx(monkeypatch, handler)
    result = validate_connection(
        _connection(base_url='https://dashscope.aliyuncs.com/compatible-mode/v1'),
        'qwen3.8-flash',
    )
    assert result.ok is True
    assert posted[0]['enable_thinking'] is False
    assert 'extra_body' not in posted[0]
    assert posted[0]['stream'] is False
