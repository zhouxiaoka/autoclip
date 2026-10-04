"""Optional model-list caching must not turn a successful provider reply into 500."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core import model_registry as registry
from backend.services import ai_model_settings as ai


@pytest.fixture
def catalog(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    cache = tmp_path / 'model-catalog-cache.json'
    monkeypatch.setattr(registry, '_path', lambda: cache)
    monkeypatch.setattr(ai, 'for_editing', lambda: ai.ModelSettings())

    async def metadata():
        return None

    # Capability metadata is external; this regression calls only the local provider.
    monkeypatch.setattr(registry, '_ensure_metadata', metadata)
    state = SimpleNamespace(status=200, requests=0)
    key = 'synthetic-model-cache-test-key'

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state.requests += 1
            authorized = self.headers.get('Authorization') == 'Bearer ' + key
            status = state.status if authorized and self.path == '/v1/models' else 401
            body = json.dumps({'data': [{'id': 'live-model', 'capability': 'multimodal'}]}
                              if status == 200 else {'error': {'message': 'fixture failure'}}).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = ai.Connection(id='local-fixture', name='Local fixture', provider='openai',
                               base_url=f'http://127.0.0.1:{server.server_port}/v1', api_key=key)
    from backend.api.v1.settings import router
    app = FastAPI()
    app.include_router(router)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield SimpleNamespace(cache=cache, connection=connection, client=client, state=state, key=key)
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def seed(catalog):
    value = {'models': [{'id': 'cached-model'}], 'source': 'live', 'updated_at': 1}
    data = {'unrelated': {'keep': True}, registry._scope(catalog.connection): value}
    catalog.cache.write_text(json.dumps(data), encoding='utf-8')
    return catalog.cache.read_bytes()


def discover(catalog, refresh=True):
    return catalog.client.post('/settings/ai-models/discover',
                               json={'connection': catalog.connection.model_dump(), 'refresh': refresh})


def cache_fault(monkeypatch, cache, operation, message='optional cache unavailable'):
    if operation == 'replace':
        original = registry.os.replace

        def replace(source, target):
            if Path(target) == cache:
                raise OSError(message)
            return original(source, target)

        monkeypatch.setattr(registry.os, 'replace', replace)
        return
    method = {'mkdir': 'mkdir', 'write': 'write_text', 'cleanup': 'unlink'}[operation]
    original = getattr(Path, method)

    def fail(path, *args, **kwargs):
        selected = path == cache.parent if operation == 'mkdir' else (
            path.parent == cache.parent and path.name.startswith(cache.stem + '.') and path.suffix == '.tmp')
        if selected:
            raise OSError(message)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, method, fail)


@pytest.mark.parametrize('operation', ['mkdir', 'write', 'replace', 'cleanup'])
def test_live_endpoint_keeps_provider_list_when_optional_cache_fails(catalog, monkeypatch, caplog, operation):
    before = seed(catalog)
    cache_fault(monkeypatch, catalog.cache, operation,
                message=f'fixture private {catalog.cache} {catalog.key}')
    response = discover(catalog)
    assert response.status_code == 200
    assert response.json()['source'] == 'live'
    assert response.json()['models'][0]['id'] == 'live-model'
    assert catalog.state.requests == 1
    assert catalog.key not in response.text + caplog.text
    assert str(catalog.cache) not in response.text + caplog.text
    if operation == 'cleanup':
        saved = json.loads(catalog.cache.read_text())
        assert saved[registry._scope(catalog.connection)]['models'][0]['id'] == 'live-model'
        assert saved['unrelated'] == {'keep': True}
    else:
        assert catalog.cache.read_bytes() == before
        assert not list(catalog.cache.parent.glob('*.tmp'))


def test_failed_write_and_cleanup_preserve_existing_cache(catalog, monkeypatch):
    before = seed(catalog)
    cache_fault(monkeypatch, catalog.cache, 'write')
    cache_fault(monkeypatch, catalog.cache, 'cleanup')
    response = discover(catalog)
    assert response.status_code == 200 and response.json()['source'] == 'live'
    assert catalog.cache.read_bytes() == before


def test_cleanup_error_does_not_mask_non_io_programming_error(catalog, monkeypatch):
    before = seed(catalog)
    original = Path.write_text

    def invalid(path, *args, **kwargs):
        if path.parent == catalog.cache.parent and path.suffix == '.tmp':
            raise TypeError('invalid cache value')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'write_text', invalid)
    cache_fault(monkeypatch, catalog.cache, 'cleanup')
    with pytest.raises(TypeError, match='invalid cache value'):
        registry._update('new', {})
    assert catalog.cache.read_bytes() == before


def test_cache_can_be_written_and_reused_after_io_recovers(catalog, monkeypatch):
    before = seed(catalog)
    with monkeypatch.context() as fault:
        cache_fault(fault, catalog.cache, 'replace')
        assert discover(catalog).status_code == 200
        assert catalog.cache.read_bytes() == before
    recovered = discover(catalog)
    assert recovered.status_code == 200 and recovered.json()['source'] == 'live'
    cached = discover(catalog, refresh=False)
    assert cached.status_code == 200 and cached.json()['source'] == 'cache'
    assert cached.json()['models'] == recovered.json()['models']
    assert catalog.state.requests == 2


@pytest.mark.parametrize('status', [401, 503])
@pytest.mark.parametrize('cached', [False, True])
def test_real_provider_failure_keeps_existing_fallback_semantics(catalog, status, cached):
    before = seed(catalog) if cached else None
    catalog.state.status = status
    response = discover(catalog)
    assert response.status_code == 200
    result = response.json()
    assert result['source'] == ('cache' if cached else 'catalog')
    assert result['warning']
    if cached:
        assert result['models'] == [{'id': 'cached-model'}]
        assert catalog.cache.read_bytes() == before
    else:
        assert result['preview'] and not catalog.cache.exists()
    assert catalog.state.requests == 1
