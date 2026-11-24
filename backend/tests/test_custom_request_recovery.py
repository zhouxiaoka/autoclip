"""Request regressions reproduced by independent review, using a loopback gateway.
All authentication strings are deliberately synthetic.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    from backend.core import llm_telemetry, model_recovery
    from backend.services import ai_model_settings as ai
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setenv('DATABASE_URL', 'sqlite:///:memory:')
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    monkeypatch.setattr(llm_telemetry, 'observe_provider_call',
                        lambda provider, impl, *args, **kwargs: impl(provider, *args, **kwargs))
    model_recovery.clear_remembered_models()
    yield
    model_recovery.clear_remembered_models()


@pytest.fixture
def gateway():
    records = []
    config = {'require_workspace': False, 'retired': False}

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
            records.append({'method': 'GET', 'headers': dict(self.headers),
                            'authorization_count': len(self.headers.get_all('Authorization') or [])})
            if config['require_workspace'] and self.headers.get('X-Workspace') != 'fixture-workspace':
                self.reply(401, {'error': {'code': 'invalid_api_key', 'message': 'Missing fixture workspace'}})
                return
            self.reply(200, {'data': [{'id': 'gpt-4o-mini', 'capability': 'multimodal'}]})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))))
            records.append({'method': 'POST', 'body': body,
                            'headers': dict(self.headers),
                            'authorization_count': len(self.headers.get_all('Authorization') or [])})
            if config['require_workspace'] and self.headers.get('X-Workspace') != 'fixture-workspace':
                self.reply(401, {'error': {'code': 'invalid_api_key', 'message': 'Missing fixture workspace'}})
                return
            if config['retired'] and body.get('model') == 'gpt-4o-retired':
                self.reply(404, {'error': {'code': 'model_not_found', 'message': 'The model does not exist'}})
                return
            answer = '{"color":"red"}'
            if body.get('stream'):
                chunk = {'id': 'fixture', 'object': 'chat.completion.chunk', 'created': 1,
                         'model': body['model'], 'choices': [{'index': 0, 'delta': {'content': answer}, 'finish_reason': 'stop'}]}
                self.reply(200, 'data: ' + json.dumps(chunk) + '\n\ndata: [DONE]\n\n', 'text/event-stream')
            else:
                self.reply(200, {'id': 'fixture', 'object': 'chat.completion', 'created': 1,
                                 'model': body['model'], 'choices': [{'index': 0,
                                 'message': {'role': 'assistant', 'content': answer}, 'finish_reason': 'stop'}]})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1', records, config
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize('api_key', ['', 'fixture-api-key'])
@pytest.mark.parametrize('name', ['Authorization', 'authorization', 'AUTHORIZATION'])
def test_sdk_custom_authorization_is_one_case_insensitive_override(gateway, name, api_key):
    from backend.core.llm_providers import OpenAIProvider
    from backend.services import ai_model_settings as ai
    from backend.services import provider_validation as validation
    base, records, _ = gateway
    connection = ai.Connection(id='custom', name='Custom', provider='compatible', base_url=base,
                               api_key=api_key, http_headers={name: 'Bearer fixture-override'})
    # The actual quick-test request already handles case-insensitive overrides.
    assert validation.validate_connection(connection, 'gpt-4o-mini').ok
    probe_record = next(row for row in records if row['method'] == 'POST')
    assert probe_record['authorization_count'] == 1
    provider = OpenAIProvider(api_key=api_key, model_name='gpt-4o-mini', base_url=base,
                              http_headers=connection.http_headers)
    try:
        assert json.loads(provider.call('fixture', max_tokens=16).content)['color'] == 'red'
    finally:
        provider.client.close()
    sdk_record = records[-1]
    assert sdk_record['authorization_count'] == 1, 'SDK sends duplicate case-variant Authorization fields'
    assert {key.lower(): value for key, value in sdk_record['headers'].items()}['authorization'] == 'Bearer fixture-override'


def test_sdk_explicit_call_temperature_wins_over_connection_extra_body(gateway):
    from backend.core.llm_providers import OpenAIProvider, http_chat_body
    from backend.core.custom_request_options import apply_chat_options
    base, records, _ = gateway
    options = {'extra_body': {'temperature': 1.0}}
    # Raw HTTP/probe serialization follows the documented call-argument precedence.
    assert http_chat_body(apply_chat_options({'temperature': 0.0}, options))['temperature'] == 0.0
    provider = OpenAIProvider(api_key='', model_name='gpt-4o-mini', base_url=base, **options)
    try:
        provider.call('fixture', temperature=0.0, max_tokens=16)
    finally:
        provider.client.close()
    assert records[-1]['body']['temperature'] == 0.0, 'SDK extra_body replaces explicit runtime temperature'


@pytest.mark.parametrize('kind', ['text', 'vision'])
def test_model_not_found_recovery_keeps_custom_header_auth(gateway, kind):
    from backend.services import ai_model_settings as ai
    from backend.services import provider_validation as validation
    from backend.core.llm_manager import LLMManager
    from backend.services.studio.intelligence import vision_call
    base, records, config = gateway
    config.update(require_workspace=True, retired=True)
    connection = ai.Connection(id='custom', name='Custom', provider='compatible', base_url=base,
                               api_key='', http_headers={'X-Workspace': 'fixture-workspace'})
    settings = ai.ModelSettings(connections=[connection],
                               analysis=ai.Assignment(connection_id='custom', model='gpt-4o-retired', capability='multimodal', model_source='preset'))
    ai.save(settings)
    assert validation.fetch_list_for_connection(connection).models == ['gpt-4o-mini']
    records.clear()
    error = None
    try:
        if kind == 'text':
            manager = LLMManager()
            try:
                result = json.loads(manager.call('fixture', max_tokens=16))
            finally:
                manager.current_provider.client.close()
        else:
            result = vision_call([{'type': 'text', 'text': 'fixture'}],
                                 config=ai.chat_endpoint(connection, 'gpt-4o-retired'))
    except Exception as exc:
        error = type(exc).__name__
    lookups = [row for row in records if row['method'] == 'GET']
    assert lookups and all(row['headers'].get('X-Workspace') == 'fixture-workspace' for row in lookups), (
        f'{kind} recovery loses custom-header authentication; error_type={error}; list_request_count={len(lookups)}')
    assert error is None
    assert all(not any(key.lower() == 'authorization' for key in row['headers']) for row in records)
    assert result['color'] == 'red'


def test_recovery_caches_are_scoped_to_endpoint_and_case_insensitive_headers(monkeypatch):
    from types import SimpleNamespace
    from backend.core import model_recovery as recovery, provider_model_fetch
    seen = []
    def listed(**kwargs):
        seen.append(kwargs)
        model = 'gpt-4o-mini' if kwargs['extra_headers'].get('X-Workspace') == 'fixture-first' else 'gpt-4.1-mini'
        return SimpleNamespace(ok=True, models=[model], capabilities={model: 'text'})
    monkeypatch.setattr(provider_model_fetch, 'list_account_models', listed)
    first, second = {'X-Workspace': 'fixture-first'}, {'X-Workspace': 'fixture-second'}
    def resolve(headers, base='http://127.0.0.1:12345/v1'):
        return recovery.resolve_available_analysis_model(base_url=base, api_key='', provider='compatible',
                                                         failed_model='gpt-4o-retired', extra_headers=headers)
    assert resolve(first) == 'gpt-4o-mini'
    assert resolve({'x-workspace': 'fixture-first'}) == 'gpt-4o-mini'
    assert len(seen) == 1
    assert resolve(second) == 'gpt-4.1-mini'
    assert len(seen) == 2
    assert resolve(first, 'http://127.0.0.1:12346/v1') == 'gpt-4o-mini'
    assert len(seen) == 3
    recovery.remember_model('compatible', 'http://127.0.0.1:12345/v1', '', 'retired', 'gpt-4o-mini', extra_headers=first)
    assert recovery.remembered_model('compatible', 'http://127.0.0.1:12345/v1', '', 'retired', extra_headers={'x-workspace': 'fixture-first'}) == 'gpt-4o-mini'
    assert recovery.remembered_model('compatible', 'http://127.0.0.1:12345/v1', '', 'retired', extra_headers=second) is None
    assert recovery.remembered_model('compatible', 'http://127.0.0.1:12346/v1', '', 'retired', extra_headers=first) is None
    assert 'fixture-first' not in repr(recovery._lists) + repr(recovery._remembered)


def test_header_only_auth_with_official_url_never_contacts_public_provider(monkeypatch):
    import httpx
    from backend.core.llm_providers import OpenAIProvider
    requests = []
    def send(self, request):
        requests.append(request)
        body = json.loads(request.content)
        chunk = {'id': 'fixture', 'object': 'chat.completion.chunk', 'created': 1,
                 'model': body['model'], 'choices': [{'index': 0, 'delta': {'content': 'fixture-ok'}, 'finish_reason': 'stop'}]}
        return httpx.Response(200, request=request, headers={'Content-Type': 'text/event-stream'},
                              content=('data: ' + json.dumps(chunk) + '\n\ndata: [DONE]\n\n').encode())
    # Intercept beneath Client.send so real request hooks still run, but no socket can open.
    monkeypatch.setattr(httpx.Client, '_send_single_request', send)
    provider = OpenAIProvider(api_key='', model_name='gpt-4o-mini', base_url='https://api.openai.com/v1',
                              http_headers={'authorization': 'Bearer fixture-official-header'})
    try:
        assert provider.call('fixture', max_tokens=16).content == 'fixture-ok'
    finally:
        provider.client.close()
    assert len(requests) == 1
    assert requests[0].headers.get_list('authorization') == ['Bearer fixture-official-header']


def test_substitution_notices_preserve_purpose_and_header_account_isolation():
    from backend.core import model_recovery as recovery
    from backend.services import ai_model_settings as ai
    base = 'http://127.0.0.1:12345/v1'
    first, second = {'X-Workspace': 'fixture-first'}, {'X-Workspace': 'fixture-second'}
    recovery.remember_model('compatible', base, '', 'retired', 'gpt-4o-mini',
                            purpose='analysis', extra_headers=first)
    assert recovery.remembered_model('compatible', base, '', 'retired', purpose='analysis',
                                     extra_headers=first) == 'gpt-4o-mini'
    assert recovery.remembered_model('compatible', base, '', 'retired', purpose='vision',
                                     extra_headers=first) is None
    connection = ai.Connection(id='custom', name='Custom', provider='compatible', base_url=base,
                               api_key='', http_headers=first)
    settings = ai.ModelSettings(connections=[connection], analysis=ai.Assignment(
        connection_id='custom', model='retired', model_source='preset'))
    assert ai.public(settings)['model_substitutions'] == [
        {'purpose': 'analysis', 'saved_model': 'retired', 'replacement': 'gpt-4o-mini', 'connection_id': 'custom'}]
    settings.connections[0] = connection.model_copy(update={'http_headers': second})
    assert 'model_substitutions' not in ai.public(settings)
    assert 'fixture-first' not in repr(recovery._notices)
