"""Official Gemini completions use native key authentication, including AQ keys."""
import io
import json
from types import SimpleNamespace
from urllib.parse import urlsplit, parse_qs

import httpx
import pytest
import requests
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.v1 import settings as settings_api
from backend.core import image_providers, llm_retry
from backend.core.llm_manager import LLMManager
from backend.core.llm_providers import GeminiProvider
from backend.core.upstream_errors import classify_upstream_error, http_error_parts
from backend.pipeline import concurrency
from backend.services import ai_model_settings as ai, provider_validation as pv
from backend.services.studio import intelligence, vision_settings
from backend.services.studio.failure_identity import connection_identity

BASE = 'https://generativelanguage.googleapis.com/v1beta/openai'
KEY = 'AQ.test-key'
MODEL = 'gemini-2.5-flash'
TEXT = '{"title":"Opening","color":"red","events":[]}'


def answer(text=TEXT, **extra):
    return {'candidates': [{'content': {'parts': [{'text': text}]}, 'finishReason': 'STOP'}], **extra}


@pytest.fixture
def wire(monkeypatch):
    calls = []
    state = {'status': 200, 'body': answer()}

    def record(url, headers, body):
        calls.append((urlsplit(str(url)), {k.lower(): v for k, v in headers.items()}, body))

    def httpx_send(request):
        payload = json.loads(request.content)
        record(request.url, request.headers, payload)
        if payload.get('stream') and 'choices' in state['body']:
            chunk = {'choices': [{'delta': {'content': TEXT}, 'finish_reason': 'stop'}]}
            return httpx.Response(200, text=f'data: {json.dumps(chunk)}\n\ndata: [DONE]\n\n',
                                  headers={'content-type': 'text/event-stream'})
        return httpx.Response(state['status'], json=state['body'], headers=state.get('headers'))

    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', lambda self, request: httpx_send(request))
    monkeypatch.setattr('backend.core.llm_providers.make_openai_http_client',
                        lambda base: httpx.Client(transport=httpx.MockTransport(httpx_send)))

    def requests_send(session, request, **kw):
        record(request.url, request.headers, json.loads(request.body))
        response = requests.Response()
        response.status_code = state['status']
        response.headers.update(state.get('headers', {}))
        response.raw = io.BytesIO(json.dumps(state['body']).encode())
        response.url = request.url
        response.request = request
        return response

    monkeypatch.setattr(requests.Session, 'send', requests_send)

    def urlopen(request, **kw):
        record(request.full_url, dict(request.header_items()), json.loads(request.data))
        if state['status'] >= 400:
            import urllib.error
            raise urllib.error.HTTPError(request.full_url, state['status'], 'fixture', {},
                                         io.BytesIO(json.dumps(state['body']).encode()))
        return io.BytesIO(json.dumps(state['body']).encode())

    monkeypatch.setattr(intelligence.urllib.request, 'urlopen', urlopen)
    return calls, state


@pytest.fixture
def configured(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    connection = ai.Connection(id='google', name='Google', provider='gemini', base_url=BASE, api_key=KEY)
    settings = ai.ModelSettings(connections=[connection], analysis=ai.Assignment(
        connection_id='google', model=MODEL, model_source='user'), analysis_mode='visual')
    monkeypatch.setattr(ai, 'load', lambda: settings)
    monkeypatch.setattr(LLMManager, '_sync_config_if_needed', lambda self: None)
    return settings


def assert_native(calls, *, json_mode=False):
    assert calls
    for url, headers, body in calls:
        assert url.path == f'/v1beta/models/{MODEL}:generateContent'
        assert 'key' not in parse_qs(url.query)
        assert not url.query
        assert headers['x-goog-api-key'] == KEY
        assert 'authorization' not in headers
        assert body['contents']
        assert 'messages' not in body
        if json_mode:
            assert body['generationConfig']['responseMimeType'] == 'application/json'


@pytest.mark.parametrize('route', ['probe', 'trial', 'text', 'vision', 'ocr'])
def test_official_gemini_routes_use_one_native_credential(route, wire, configured, monkeypatch, tmp_path):
    calls, state = wire
    connection = configured.connections[0]
    if route in ('probe', 'trial'):
        monkeypatch.setattr(pv, '_get_models', lambda *a: ([MODEL], None, SimpleNamespace(
            recommended={}, truncated=False, message_key='')))
    if route == 'probe':
        assert pv.validate_connection(connection, MODEL).ok
    elif route == 'trial':
        monkeypatch.setattr(pv, 'TRIAL_GAP_SEC', 0)
        result = pv.validate_connection_with_probe(connection, MODEL, probe_kind='trial')
        assert result.ok and result.trial_passed
    elif route == 'text':
        manager = LLMManager(tmp_path / 'settings.json')
        assert manager.call('sample', temperature=0.2, max_tokens=123) == TEXT
        assert calls[0][2]['generationConfig'] == {'temperature': 0.2, 'maxOutputTokens': 123}
    elif route == 'vision':
        assert intelligence.vision_call([{'type': 'text', 'text': 'color'}, {
            'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,aW1hZ2U='}}]) == json.loads(TEXT)
        assert calls[0][2]['contents'][0]['parts'][1]['inlineData']['mimeType'] == 'image/png'
    else:
        from backend.services.cover import verify_endpoint
        cfg = SimpleNamespace(ocr_model='', source='connections')
        assert image_providers.read_image_text(**verify_endpoint(cfg), image=b'image') == TEXT
    assert_native(calls)
    if route == 'trial':
        assert len(calls) == 4
        assert_native(calls[1:], json_mode=True)
    assert connection.base_url == BASE


@pytest.mark.parametrize('provider,base', [('compatible', BASE), ('gemini', 'https://relay.example/v1')])
def test_nonofficial_endpoint_keeps_bearer_chat(provider, base, wire):
    calls, state = wire
    state['body'] = {'choices': [{'message': {'content': TEXT}}]}
    result = pv._trial_once(base, KEY, MODEL, 'sample', provider=provider)
    assert result['json_ok']
    url, headers, body = calls[0]
    assert url.path.endswith('/chat/completions')
    assert headers['authorization'] == f'Bearer {KEY}'
    assert 'x-goog-api-key' not in headers


def test_settings_vision_uses_tested_connection_provider(wire, configured):
    connection = configured.connections[0]
    identity = connection_identity(connection, MODEL)
    assert identity['provider'] == 'gemini'
    body = vision_settings.VisionSettingsInput(mode='custom', base_url=BASE, api_key=KEY, model=MODEL)
    with vision_settings.testing_identity(identity):
        assert vision_settings.test(body)['ok']
    assert_native(wire[0])


@pytest.mark.parametrize('token_key', ['max_tokens', 'max_completion_tokens'])
def test_native_manager_honors_json_mode_and_token_limit(token_key, wire, configured, tmp_path):
    manager = LLMManager(tmp_path / 'settings.json')
    assert manager.call_with_retry('sample', **{token_key: 123},
                                   response_format={'type': 'json_object'}) == TEXT
    assert_native(wire[0], json_mode=True)
    assert wire[0][0][2]['generationConfig']['maxOutputTokens'] == 123


def test_native_provider_ignores_unrelated_payload_options(wire):
    provider = GeminiProvider(api_key=KEY, model_name=MODEL, base_url=BASE)
    assert provider.call('sample', model='injected-model',
                         messages=[{'role': 'user', 'content': 'injected-message'}],
                         api_key='injected-key', headers={'Authorization': 'Bearer injected'},
                         extra_body={'model': 'injected-model'}, stream=True,
                         temperature=0.2, top_p=0.9, max_tokens=123).content == TEXT
    assert_native(wire[0])
    body = wire[0][0][2]
    assert body == {
        'contents': [{'role': 'user', 'parts': [{'text': 'sample'}]}],
        'generationConfig': {'temperature': 0.2, 'topP': 0.9, 'maxOutputTokens': 123},
    }


@pytest.mark.parametrize('status', [200, 400])
def test_legacy_gemini_test_api_uses_default_native_root(status, wire):
    if status == 400:
        wire[1].update(status=status, body={'error': {'status': 'INVALID_ARGUMENT',
            'details': [{'reason': 'API_KEY_INVALID'}]}})
    app = FastAPI()
    app.include_router(settings_api.router)
    with TestClient(app) as client:
        response = client.post('/settings/test-api', json={
            'provider': 'gemini', 'api_key': KEY, 'model': MODEL})
    assert response.status_code == 200
    assert response.json()['success'] == (status == 200)
    assert KEY not in response.text
    assert_native(wire[0])


@pytest.mark.parametrize('provider', ['gemini', 'compatible'])
@pytest.mark.parametrize('status,code,detail,expected,attempts', [
    (400, 'INVALID_ARGUMENT', {'reason': 'API_KEY_INVALID'}, 'invalid_key', 1),
    (429, 'RESOURCE_EXHAUSTED', {}, 'rate_limited', 3),
    (429, 'RESOURCE_EXHAUSTED', {'violations': [{
        'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}, 'insufficient_quota', 1),
    (503, 'UNAVAILABLE', {}, 'upstream_unavailable', 3),
])
def test_manager_native_and_openai_retry_policy(provider, status, code, detail, expected, attempts,
                                               wire, configured, tmp_path, monkeypatch):
    calls, state = wire
    body = {'error': {'code': status, 'status': code, 'message': 'fixture failure',
                      'details': [detail] if detail else []}}
    state.update(status=status, body=body, headers={'Retry-After': '7'})
    if provider == 'compatible':
        configured.connections[0] = configured.connections[0].model_copy(update={'provider': provider})
    manager = LLMManager(tmp_path / 'settings.json')
    if provider == 'compatible':
        # Isolate the manager's retries from SDK-internal resends.
        manager.current_provider.client = manager.current_provider.client.with_options(max_retries=0)
    sleeps = []
    monkeypatch.setattr('time.sleep', sleeps.append)
    concurrency.reset_limiter()
    try:
        with pytest.raises(RuntimeError) as caught:
            manager.call_with_retry('sample')
    finally:
        concurrency.reset_limiter()
    actual_status, actual_body = http_error_parts(caught.value)
    assert actual_status == status
    assert actual_body.get('error', actual_body) == body['error']
    info, retry_status, retry_after = llm_retry.classify_for_retry(caught.value)
    assert info.error_type.value == expected
    assert info.retryable == (attempts > 1)
    assert retry_status == status and retry_after == 7
    assert len(calls) == attempts
    assert sleeps == [7.0] * (attempts - 1)
    if provider == 'gemini':
        assert_native(calls)
    else:
        assert all(url.path.endswith('/chat/completions') and
                   headers['authorization'] == f'Bearer {KEY}' for url, headers, _ in calls)


@pytest.mark.parametrize('route', ['text', 'vision', 'ocr'])
def test_custom_gemini_runtime_keeps_compatible_transport(route, wire, configured, tmp_path, monkeypatch):
    """Protocol selection depends on the resolved host, not just the provider label."""
    calls, state = wire
    base = 'https://relay.example/v1'
    configured.connections[0] = configured.connections[0].model_copy(update={
        'base_url': base, 'base_url_source': 'user'})
    monkeypatch.setattr(ai, 'chat_endpoint', lambda connection, model: {
        'base_url': base, 'api_key': connection.api_key, 'model': model})
    state['body'] = {'choices': [{'message': {'content': TEXT}, 'finish_reason': 'stop'}]}
    if route == 'text':
        assert LLMManager(tmp_path / 'settings.json').call('sample') == TEXT
    elif route == 'vision':
        assert intelligence.vision_call([{'type': 'text', 'text': 'sample'}]) == json.loads(TEXT)
    else:
        assert image_providers.read_image_text(provider='gemini', api_key=KEY, base_url=base,
                                               model=MODEL, image=b'image') == TEXT
    assert calls
    for url, headers, body in calls:
        assert url.path == '/v1/chat/completions'
        assert headers['authorization'] == f'Bearer {KEY}'
        assert 'x-goog-api-key' not in headers


@pytest.mark.parametrize('status,code,reason,expected', [
    (401, 'UNAUTHENTICATED', None, 'invalid_key'),
    (400, 'INVALID_ARGUMENT', 'API_KEY_INVALID', 'invalid_key'),
    (400, 'RESOURCE_EXHAUSTED', None, 'rate_limited'),
    (403, 'PERMISSION_DENIED', None, 'permission_denied'),
])
def test_native_error_bodies_keep_classification(status, code, reason, expected, wire):
    calls, state = wire
    body = {'error': {'code': status, 'status': code, 'message': 'fixture failure',
                      'details': [{'reason': reason}] if reason else []}}
    state.update(status=status, body=body)
    assert pv._probe(BASE, KEY, MODEL, provider='gemini').error_type.value == expected
    assert classify_upstream_error(status, body).error_type.value == expected
    assert_native(calls)


def test_message_and_response_translation():
    from backend.core import gemini_transport as gt
    url, headers, body = gt.request(BASE + '?key=must-not-survive', KEY, {
        'model': MODEL, 'messages': [{'role': 'system', 'content': 'rules'},
                                   {'role': 'user', 'content': 'question'},
                                   {'role': 'assistant', 'content': 'answer'}],
        'temperature': 0, 'max_completion_tokens': 45, 'response_format': {'type': 'json_object'}})
    assert '?' not in url
    assert headers == {'x-goog-api-key': KEY, 'Content-Type': 'application/json'}
    assert body['systemInstruction']['parts'] == [{'text': 'rules'}]
    assert [item['role'] for item in body['contents']] == ['user', 'model']
    assert body['generationConfig'] == {'temperature': 0, 'maxOutputTokens': 45, 'responseMimeType': 'application/json'}
    data = answer('one')
    data['candidates'][0]['content']['parts'] += [{'text': 'hidden', 'thought': True}, {'text': 'two'}]
    data['candidates'][0]['finishReason'] = 'MAX_TOKENS'
    result = gt.completion(data)
    assert result['choices'][0] == {'message': {'content': 'onetwo'}, 'finish_reason': 'length'}


@pytest.mark.parametrize('data,message', [
    ({}, 'no candidates'), (answer(''), 'empty text'),
    ({'promptFeedback': {'blockReason': 'SAFETY'}}, 'blocked'),
    ({'candidates': [{'finishReason': 'SAFETY'}]}, 'SAFETY'),
])
def test_empty_or_blocked_response_is_explicit(data, message):
    from backend.core.gemini_transport import completion
    with pytest.raises(ValueError, match=message):
        completion(data)


@pytest.mark.parametrize('body', [{}, answer(''), {'promptFeedback': {'blockReason': 'SAFETY'}}])
def test_invalid_native_ocr_stays_inside_cover_recovery_boundary(wire, body):
    wire[1]['body'] = body
    with pytest.raises(image_providers.ImageError) as caught:
        image_providers.read_image_text(provider='gemini', api_key=KEY, base_url=BASE,
                                        model=MODEL, image=b'image')
    assert caught.value.error_code == 'invalid_response'
    assert_native(wire[0])


@pytest.mark.parametrize('content', ['', [{'type': 'image_url', 'image_url': {'url': 'https://private.example/image'}}],
                                  [{'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,invalid!'}}]])
def test_empty_and_remote_or_invalid_images_are_rejected(content):
    from backend.core.gemini_transport import request
    with pytest.raises(ValueError):
        request(BASE, KEY, {'model': MODEL, 'messages': [{'role': 'user', 'content': content}]})


def test_aq_key_is_redacted_from_upstream_messages():
    from backend.core.log_redaction import redact_text
    from backend.core.llm_telemetry import sanitize_exception_text
    for redact in (redact_text, sanitize_exception_text):
        assert KEY not in redact(f'Invalid credential {KEY}')


def test_native_requests_suppress_session_and_netrc_auth(wire, monkeypatch, configured, tmp_path):
    from backend.core.gemini_transport import native_auth
    monkeypatch.setattr(requests.sessions, 'get_netrc_auth', lambda url: ('ambient', 'password'))
    manager = LLMManager(tmp_path / 'settings.json')
    assert manager.call('sample') == TEXT
    session = requests.Session()
    session.headers['Authorization'] = 'Bearer ambient'
    session.auth = ('ambient', 'password')
    assert image_providers.read_image_text(provider='gemini', api_key=KEY, base_url=BASE,
                                          model=MODEL, image=b'image', session=session) == TEXT
    assert_native(wire[0])
    assert native_auth(requests.Request('POST', BASE, headers={'Authorization': 'Basic ambient'}).prepare()).headers.get('Authorization') is None


@pytest.mark.parametrize('route', ['text', 'vision', 'ocr', 'trial'])
@pytest.mark.parametrize('status,code,reason,expected', [
    (400, 'INVALID_ARGUMENT', 'API_KEY_INVALID', 'invalid_key'),
    (400, 'RESOURCE_EXHAUSTED', None, 'rate_limited'),
])
def test_native_runtime_error_metadata(route, status, code, reason, expected, wire, configured, tmp_path):
    from backend.core.upstream_errors import classify_exception
    calls, state = wire
    state.update(status=status, body={'error': {'status': code, 'message': 'fixture failure',
                                               'details': [{'reason': reason}] if reason else []}})
    if route == 'trial':
        result = pv._trial_once(BASE, KEY, MODEL, 'sample', provider='gemini')
        assert not result['ok_http'] and not result['json_ok']
        assert result['rate_limited'] == (expected == 'rate_limited')
    elif route == 'text':
        with pytest.raises(RuntimeError) as caught:
            LLMManager(tmp_path / 'settings.json').call('sample')
        assert classify_exception(caught.value).error_type.value == expected
    elif route == 'vision':
        with pytest.raises(intelligence.VisionRequestError) as caught:
            intelligence.vision_call([{'type': 'text', 'text': 'sample'}])
        assert caught.value.http_status == status
        assert caught.value.code == ('llm_auth_invalid' if expected == 'invalid_key' else 'rate_limited')
    else:
        with pytest.raises(image_providers.ImageError) as caught:
            image_providers.read_image_text(provider='gemini', api_key=KEY, base_url=BASE,
                                            model=MODEL, image=b'image')
        assert caught.value.attribution.upstream_error_type == expected
        assert caught.value.http_status == status
    assert_native(calls)
