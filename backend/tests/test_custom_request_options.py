"""Custom gateway options cross the settings, discovery and runtime boundaries."""
import json

import pytest

from backend.services import ai_model_settings as ai


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())


def configured(**patch):
    return ai.Connection(**{
        'id': 'custom', 'name': 'Custom', 'provider': 'compatible',
        'base_url': 'http://127.0.0.1:12345/v1', 'api_key': '',
        'http_headers': {'X-Workspace': 'fixture-private-value'},
        'reasoning_effort': 'high', 'extra_body': {'provider_options': {'thinking': True}}, **patch,
    })


def test_custom_options_survive_persistence_without_exposing_headers():
    connection = configured()
    settings = ai.ModelSettings(connections=[connection], analysis=ai.Assignment(connection_id='custom', model='fixture-model'))
    public = ai.save(settings)
    disk = json.loads(ai.path().read_text())
    assert disk['connections'][0]['http_headers'] == {'X-Workspace': 'fixture-private-value'}
    assert public['connections'][0]['has_http_headers'] is True
    assert 'fixture-private-value' not in json.dumps(public)
    assert 'http_headers' not in public['connections'][0]
    assert public['connections'][0]['reasoning_effort'] == 'high'
    ai.save(ai.ModelSettings.model_validate(public))
    assert ai.load().connections[0].http_headers == connection.http_headers


def test_custom_options_reach_chat_endpoint_and_are_isolated():
    endpoint = ai.chat_endpoint(configured(), 'fixture-model')
    assert endpoint['http_headers'] == {'X-Workspace': 'fixture-private-value'}
    assert endpoint['reasoning_effort'] == 'high'
    assert endpoint['extra_body'] == {'provider_options': {'thinking': True}}
    old = ai.Connection(id='old', name='Old', provider='compatible', base_url='http://127.0.0.1:12345/v1')
    assert ai.chat_endpoint(old, 'old-model') == {'base_url': old.base_url, 'api_key': '', 'model': 'old-model'}


@pytest.mark.parametrize('headers', [
    {'X-Workspace': 'value\r\nInjected: bad'}, {'X-Workspace': 'value\x00'},
    {'Bad Name': 'value'}, {'X-Workspace': 'value', 'x-workspace': 'other'},
    {'Host': 'elsewhere.example'}, {'Content-Length': '1'}, {'Transfer-Encoding': 'chunked'},
    {'X-Workspace': '非 ASCII'}, {'X-Workspace': 12}, {'X-Workspace': 'x' * 4097},
])
def test_unsafe_headers_are_rejected_without_printing_values(headers):
    from pydantic import ValidationError
    with pytest.raises(ValidationError) as error:
        configured(http_headers=headers)
    assert 'fixture-private-value' not in str(error.value)
    assert 'input_value=' not in str(error.value)


@pytest.mark.parametrize('body', [
    {'model': 'other'}, {'messages': []}, {'stream': False}, {'max_tokens': 999999},
    {'max_completion_tokens': 999999}, {'timeout': 999}, {'extra_headers': {'Auth': 'x'}},
    {'extra_body': {}}, {'reasoning_effort': 'high'}, {'response_format': {}},
    {'value': float('nan')}, {'value': float('inf')}, {'value': 'x' * 16385},
])
def test_provider_parameters_cannot_replace_app_fields_or_budget(body):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        configured(extra_body=body)


def test_secret_preservation_clear_and_endpoint_change():
    original = configured()
    ai.save(ai.ModelSettings(connections=[original], analysis=ai.Assignment(connection_id='custom', model='fixture-model')))
    public = ai.public(ai.load())
    kept = ai.resolve_secret(ai.Connection.model_validate(public['connections'][0]), ai.load())
    assert kept.http_headers == original.http_headers
    assert 'fixture-private-value' not in repr(kept)
    cleared = ai.resolve_secret(kept.model_copy(update={'http_headers': {}}), ai.load())
    assert cleared.http_headers == {}
    changed = ai.Connection.model_validate({**public['connections'][0], 'base_url': 'https://another.example/v1'})
    with pytest.raises(ValueError, match='HTTP Headers'):
        ai.resolve_secret(changed, ai.load())
    explicit = ai.resolve_secret(changed.model_copy(update={'http_headers': {}}), ai.load())
    assert explicit.http_headers == {}


@pytest.fixture
def gateway():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    records = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body, content_type='application/json'):
            raw = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            records.append(('GET', self.path, dict(self.headers), None))
            if self.headers.get('X-Workspace') != 'fixture-private-value':
                self.reply(401, {'error': {'message': 'missing fixture header'}})
                return
            self.reply(200, {'data': [{'id': 'fixture-model'}]})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
            records.append(('POST', self.path, dict(self.headers), body))
            if self.headers.get('X-Workspace') != 'fixture-private-value':
                self.reply(401, {'error': {'message': 'missing fixture header'}})
                return
            if body.get('reasoning_effort') != 'high' or body.get('provider_options') != {'thinking': True}:
                self.reply(400, {'error': {'message': 'missing fixture options'}})
                return
            answer = json.dumps({'color': 'red', 'topics': [{'title': 'Fixture'}]})
            if body.get('stream'):
                chunks = [
                    {'id': 'fixture', 'object': 'chat.completion.chunk', 'created': 1, 'model': 'fixture-model', 'choices': [{'index': 0, 'delta': {'content': answer}, 'finish_reason': None}]},
                    {'id': 'fixture', 'object': 'chat.completion.chunk', 'created': 1, 'model': 'fixture-model', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]},
                ]
                self.reply(200, ''.join('data: ' + json.dumps(row) + '\n\n' for row in chunks) + 'data: [DONE]\n\n', 'text/event-stream')
            else:
                self.reply(200, {'id': 'fixture', 'object': 'chat.completion', 'created': 1, 'model': 'fixture-model',
                                 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': answer}, 'finish_reason': 'stop'}]})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:' + str(server.server_port) + '/v1', records
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_header_only_gateway_discovery_quick_trial_sdk_and_vision(gateway, monkeypatch):
    import asyncio
    from backend.services import provider_validation as validation
    from backend.core import model_registry
    from backend.core.llm_manager import LLMManager
    from backend.services.studio.vision_settings import VisionSettingsInput, test as test_vision
    base, records = gateway
    connection = configured(base_url=base)
    settings = ai.ModelSettings(connections=[connection], analysis=ai.Assignment(connection_id='custom', model='fixture-model', capability='multimodal'))
    ai.save(settings)
    assert validation.fetch_list_for_connection(connection).models == ['fixture-model']
    discovered = asyncio.run(model_registry.discover(connection, refresh=True))
    assert discovered['source'] == 'live'
    assert any(row['id'] == 'fixture-model' for row in discovered['models'])
    monkeypatch.setattr(validation, 'TRIAL_GAP_SEC', 0)
    checked = validation.validate_connection_with_probe(connection, 'fixture-model', probe_kind='trial')
    assert checked.ok and checked.trial_passed
    manager = LLMManager()
    result = manager.call('Return the fixture object.', max_tokens=20)
    assert json.loads(result)['color'] == 'red'
    assert test_vision(VisionSettingsInput(mode='custom', **ai.chat_endpoint(connection, 'fixture-model')))['ok']
    posts = [row for row in records if row[0] == 'POST']
    assert len(posts) >= 6
    for _, _, headers, body in posts:
        assert {key.lower(): value for key, value in headers.items()}.get('x-workspace') == 'fixture-private-value'
        assert not any(key.lower() == 'authorization' for key in headers)
        assert body['model'] == 'fixture-model'
        assert body['reasoning_effort'] == 'high'
        assert body['provider_options'] == {'thinking': True}
        assert 'extra_body' not in body
        assert body.get('max_tokens', body.get('max_completion_tokens', 0)) <= 4000


def test_remote_header_only_fetch_is_not_rejected_as_missing_api_key():
    from types import SimpleNamespace
    from backend.core.provider_model_fetch import fetch_provider_models
    seen = []
    def get(url, **kwargs):
        seen.append(kwargs['headers'])
        return SimpleNamespace(status_code=200, headers={'Content-Type': 'application/json'}, text='{"data":[{"id":"fixture-model"}]}', json=lambda: {'data': [{'id': 'fixture-model'}]})
    result = fetch_provider_models(base_url='https://gateway.example/v1', api_key='', provider='compatible',
                                   extra_headers={'X-Workspace': 'fixture-private-value'}, http=get)
    assert result.ok and result.models == ['fixture-model']
    assert seen[0]['X-Workspace'] == 'fixture-private-value'


def test_header_cache_scope_and_payload_defaults_are_isolated():
    from backend.core.model_registry import _scope
    from backend.core.custom_request_options import apply_chat_options, merge_headers
    a, b = configured(), configured(http_headers={'X-Workspace': 'other-fixture-value'})
    assert _scope(a) != _scope(b)
    payload = {'model': 'fixture-model', 'messages': [], 'extra_body': {'provider_options': {'thinking': False}}, 'reasoning_effort': 'low'}
    merged = apply_chat_options(payload, a)
    assert merged['reasoning_effort'] == 'low'
    assert merged['extra_body']['provider_options'] == {'thinking': False}
    assert a.extra_body == {'provider_options': {'thinking': True}}
    assert merge_headers({'Authorization': 'Bearer old'}, {'authorization': 'Bearer fixture'}) == {'authorization': 'Bearer fixture'}


def test_http_validation_never_echoes_header_values(tmp_path):
    from backend.app_factory import create_app
    from fastapi.testclient import TestClient
    connection = configured().model_dump()
    connection['http_headers']['X-Workspace'] += '\r\nInjected: bad'
    body = {'connections': [connection], 'analysis': {'connection_id': 'custom', 'model': 'fixture-model'}}
    with TestClient(create_app(mode='web'), raise_server_exceptions=False) as client:
        for path, verb, payload in [
            ('/api/v1/settings/ai-models', 'put', body),
            ('/api/v1/settings/ai-models/test', 'post', {'connection': connection, 'model': 'fixture-model'}),
            ('/api/v1/settings/ai-models/discover', 'post', {'connection': connection}),
            ('/api/v1/settings/ai-models/fetch-list', 'post', {'connection': connection}),
        ]:
            response = getattr(client, verb)(path, json=payload)
            assert response.status_code == 422
            assert 'fixture-private-value' not in response.text


def test_custom_header_and_provider_parameter_logs_are_redacted():
    from backend.core.log_redaction import redact_text
    from backend.core.llm_telemetry import sanitize_exception_text
    raw = 'payload=' + json.dumps({'http_headers': {'X-Workspace': 'fixture-private-}value'}, 'extra_body': {'provider_options': {'private': 'fixture-private-value'}}})
    safe = redact_text(raw)
    assert 'fixture-private' not in safe
    assert 'fixture-private' not in sanitize_exception_text(RuntimeError(raw))
    assert 'http_headers' in safe


def test_sdk_and_vision_do_not_follow_redirects_with_custom_headers(gateway):
    import urllib.error
    import urllib.request
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    from backend.core.llm_providers import OpenAIProvider
    from backend.core.custom_request_options import no_redirect_open
    target, records = gateway

    class Redirect(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            self.send_response(307)
            self.send_header('Location', target + '/chat/completions')
            self.send_header('Content-Length', '0')
            self.end_headers()

    server = ThreadingHTTPServer(('127.0.0.1', 0), Redirect)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    source = 'http://127.0.0.1:' + str(server.server_port) + '/v1'
    try:
        provider = OpenAIProvider(api_key='', model_name='fixture-model', base_url=source,
                                  http_headers={'X-Workspace': 'fixture-private-value'})
        with pytest.raises(Exception):
            provider.call('fixture')
        req = urllib.request.Request(source + '/chat/completions', data=b'{}', headers={'X-Workspace': 'fixture-private-value'})
        with pytest.raises(urllib.error.HTTPError):
            no_redirect_open(req, timeout=2)
        assert records == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_runtime_reload_and_connection_switch_do_not_reuse_options(monkeypatch):
    from types import SimpleNamespace
    from backend.core.llm_manager import LLMManager
    from backend.core.llm_providers import LLMProviderFactory
    seen = []
    def create(provider, api_key, model_name, **kwargs):
        seen.append((model_name, kwargs))
        return SimpleNamespace(model_name=model_name, _build_full_input=lambda prompt, data: prompt, call=lambda *args, **kw: SimpleNamespace(content='{}', usage=None, model=model_name, finish_reason='stop'))
    monkeypatch.setattr(LLMProviderFactory, 'create_provider', create)
    settings = ai.ModelSettings(connections=[configured()], analysis=ai.Assignment(connection_id='custom', model='fixture-model'))
    ai.save(settings)
    manager = LLMManager()
    manager.call('fixture')
    assert seen[-1][1]['http_headers']['X-Workspace'] == 'fixture-private-value'
    updated = ai.load()
    updated.connections[0].http_headers = {'X-Workspace': 'new-fixture-value'}
    updated.connections[0].reasoning_effort = 'low'
    ai.save(updated)
    manager.call('fixture')
    assert seen[-1][1]['http_headers']['X-Workspace'] == 'new-fixture-value'
    assert seen[-1][1]['reasoning_effort'] == 'low'
    other = ai.Connection(id='other', name='Other', provider='compatible', base_url='http://127.0.0.1:12345/v1')
    updated.connections.append(other)
    updated.analysis = ai.Assignment(connection_id='other', model='other-model')
    ai.save(updated)
    manager.call('fixture')
    assert seen[-1] == ('other-model', {'base_url': other.base_url})
