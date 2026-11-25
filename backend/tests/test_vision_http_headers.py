"""Exercise settings and vision requests against a gateway that rejects urllib's default agent."""
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend import __version__
from backend.services import ai_model_settings as ai
from backend.services.studio import intelligence


@pytest.fixture
def gateway(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body):
            raw = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'text/plain' if isinstance(body, str) else 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            self.reply(200, {'data': [{'id': 'fixture-vision'}]})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append((dict(self.headers), body))
            if self.headers.get('User-Agent', '').startswith('Python-urllib/'):
                self.reply(403, 'error code: 1010\n')
                return
            self.reply(200, {'choices': [{'message': {'content': '{"color":"red"}'}}]})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1', requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize('custom_headers', [None, {'X-Workspace': 'fixture-workspace'},
                                           {'user-agent': 'fixture-client/1.0'}])
def test_multimodal_quick_test_reaches_a_gateway_that_blocks_urllib(gateway, custom_headers):
    from backend.api.v1.settings import router

    base, requests = gateway
    connection = ai.Connection(id='fixture', name='Fixture', provider='compatible',
                               base_url=base, api_key='fixture-key', http_headers=custom_headers)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.post('/settings/ai-models/test', json={
            'connection': connection.model_dump(), 'model': 'fixture-vision',
            'purpose': 'analysis', 'vision': True,
        })

    assert response.status_code == 200
    assert response.json()['ok'] is True
    assert len(requests) == 2
    headers, body = requests[-1]
    headers = {key.lower(): value for key, value in headers.items()}
    expected = (custom_headers or {}).get('user-agent', f'autoclip/{__version__} (+https://github.com/zhouxiaoka/autoclip)')
    assert headers['user-agent'] == expected
    assert headers['authorization'] == 'Bearer fixture-key'
    assert headers['content-type'] == 'application/json'
    if custom_headers and 'X-Workspace' in custom_headers:
        assert headers['x-workspace'] == custom_headers['X-Workspace']
    assert body['model'] == 'fixture-vision'
    assert body['stream'] is True
    assert body['messages'][0]['content'][1]['type'] == 'image_url'


def test_native_gemini_vision_retains_its_authentication_and_client_identity(monkeypatch):
    requests = []

    def send(request, **kwargs):
        requests.append(request)
        return io.BytesIO(json.dumps({'candidates': [{'content': {'parts': [
            {'text': '{"color":"red"}'},
        ]}, 'finishReason': 'STOP'}]}).encode())

    monkeypatch.setattr(intelligence.urllib.request, 'urlopen', send)
    result = intelligence.vision_call([{'type': 'text', 'text': 'Return the color as JSON.'}], config={
        'provider': 'gemini', 'base_url': 'https://generativelanguage.googleapis.com/v1beta',
        'api_key': 'fixture-key', 'model': 'gemini-fixture', 'timeout': 10,
    })
    assert result == {'color': 'red'}
    assert len(requests) == 1
    request = requests[0]
    assert request.get_header('User-agent') == f'autoclip/{__version__} (+https://github.com/zhouxiaoka/autoclip)'
    assert request.get_header('X-goog-api-key') == 'fixture-key'
    assert request.get_header('Authorization') is None
    assert request.full_url.endswith('/models/gemini-fixture:generateContent')


def test_stream_fallback_preserves_the_vision_client_identity(monkeypatch):
    import urllib.error

    requests = []

    def send(request, **kwargs):
        requests.append(request)
        if len(requests) == 1:
            raise urllib.error.HTTPError(request.full_url, 400, 'Bad Request', {},
                                         io.BytesIO(b'{"error":{"message":"stream is not supported"}}'))
        return io.BytesIO(b'{"choices":[{"message":{"content":"{\\"color\\":\\"red\\"}"}}]}')

    monkeypatch.setattr(intelligence.urllib.request, 'urlopen', send)
    assert intelligence.vision_call([], config={
        'base_url': 'https://gateway.example/v1', 'model': 'fixture-vision',
        'api_key': 'fixture-key', 'timeout': 10,
    }) == {'color': 'red'}
    assert [json.loads(request.data)['stream'] for request in requests] == [True, False]
    assert all(request.get_header('User-agent') ==
               f'autoclip/{__version__} (+https://github.com/zhouxiaoka/autoclip)' for request in requests)
