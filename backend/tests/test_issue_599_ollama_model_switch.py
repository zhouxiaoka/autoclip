"""Issue #599 — Ollama model switch must not mark the whole endpoint disconnected.

The fixture speaks the OpenAI-compatible Ollama protocol (GET /v1/models,
POST /v1/chat/completions, Bearer EMPTY). It is not a running Ollama and it
does not download a model. Two probes run at the same time: one listed model
answers, one times out the way a cold local model does.
"""
import json
import threading

import httpx
import pytest

from backend.services import ai_model_settings as ai
from backend.services.provider_validation import (
    LOCAL_MODEL_NOT_READY_HINT,
    validate_connection,
    validate_connection_with_probe,
)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())


class _FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.headers = {'content-type': 'application/json'}
        self.text = json.dumps(payload)

    def json(self):
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


def _ollama():
    return ai.Connection(
        id='ollama', name='Ollama', provider='ollama',
        base_url='http://localhost:11434/v1', api_key='',
    )


def test_listed_local_timeout_keeps_the_endpoint_connected_and_generation_open(monkeypatch):
    from backend.services.studio import readiness

    seen = {'post_auth': []}

    def handler(method, url, headers, payload):
        if method == 'GET':
            assert url.rstrip('/').endswith('/models')
            assert (headers or {}).get('Authorization') is None
            return _FakeResponse(200, {'object': 'list', 'data': [
                {'id': 'qwen2.5:7b', 'object': 'model', 'owned_by': 'library'},
                {'id': 'qwen2.5-coder:14b', 'object': 'model', 'owned_by': 'library'},
            ]})
        assert payload.get('stream') is False
        assert 'response_format' not in payload
        seen['post_auth'].append((headers or {}).get('Authorization'))
        if payload.get('model') == 'qwen2.5-coder:14b':
            raise httpx.TimeoutException('cold model load')
        return _FakeResponse(200, {'choices': [{'message': {'role': 'assistant', 'content': 'ok'}, 'finish_reason': 'stop'}]})

    monkeypatch.setattr('httpx.Client', lambda *args, **kwargs: _FakeClient(handler))
    previous = validate_connection(_ollama(), 'qwen2.5:7b')
    switched = validate_connection(_ollama(), 'qwen2.5-coder:14b')

    assert previous.ok is True
    assert previous.warning == ''
    assert switched.ok is True
    assert switched.result == 'ok'
    assert switched.warning == LOCAL_MODEL_NOT_READY_HINT
    assert switched.error_type == ''
    assert seen['post_auth'] == ['Bearer EMPTY', 'Bearer EMPTY']

    connection = _ollama()
    connection.validation_status = 'ok' if switched.ok else 'failed'
    settings = ai.ModelSettings(
        connections=[connection],
        analysis=ai.Assignment(connection_id='ollama', model='qwen2.5-coder:14b', capability='auto', model_source='user'),
        transcription=ai.Transcription(),
    )
    ai.save(settings)
    loaded = ai.load()
    assert loaded.connections[0].validation_status == 'ok'
    assert loaded.analysis.model == 'qwen2.5-coder:14b'
    readiness.ensure_analysis_usable()
    report = readiness.report()
    assert report['checks']['analysis']['code'] == 'configured'
    assert report['checks']['analysis']['ok'] is True


def test_sibling_probes_overlap_and_a_timeout_does_not_fail_the_answering_model(monkeypatch):
    started = threading.Barrier(2)
    release = threading.Event()
    inflight = {'n': 0, 'max': 0}
    lock = threading.Lock()

    def handler(method, url, headers, payload):
        if method == 'GET':
            return _FakeResponse(200, {'data': [
                {'id': 'qwen2.5:7b'}, {'id': 'qwen2.5-coder:14b'},
            ]})
        model = (payload or {}).get('model')
        with lock:
            inflight['n'] += 1
            inflight['max'] = max(inflight['max'], inflight['n'])
        try:
            started.wait(timeout=3)
            if model == 'qwen2.5-coder:14b':
                assert release.wait(timeout=3)
                raise httpx.TimeoutException('still loading')
            release.set()
            return _FakeResponse(200, {'choices': [{'message': {'content': 'ok'}}]})
        finally:
            with lock:
                inflight['n'] -= 1

    monkeypatch.setattr('httpx.Client', lambda *args, **kwargs: _FakeClient(handler))
    results = {}

    def run(model):
        results[model] = validate_connection(_ollama(), model)

    threads = [threading.Thread(target=run, args=(model,)) for model in ('qwen2.5:7b', 'qwen2.5-coder:14b')]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert not any(thread.is_alive() for thread in threads)
    assert inflight['max'] >= 2
    assert results['qwen2.5:7b'].ok is True
    assert results['qwen2.5:7b'].warning == ''
    assert results['qwen2.5-coder:14b'].ok is True
    assert results['qwen2.5-coder:14b'].warning == LOCAL_MODEL_NOT_READY_HINT


def test_ollama_reasoning_only_completion_is_not_a_dead_connection(monkeypatch):
    """A 200 whose only text is in the reasoning channel must not fail the endpoint."""
    def handler(method, url, headers, payload):
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'qwen2.5:7b'}]})
        return _FakeResponse(200, {'choices': [{
            'finish_reason': 'length',
            'message': {
                'role': 'assistant',
                'content': '',
                'reasoning': '{"topics":[{"title":"should-not-count"}]}',
            },
        }]})

    monkeypatch.setattr('httpx.Client', lambda *args, **kwargs: _FakeClient(handler))
    result = validate_connection(_ollama(), 'qwen2.5:7b')
    assert result.ok is True
    assert result.warning == LOCAL_MODEL_NOT_READY_HINT
    assert 'should-not-count' not in result.warning


def test_ollama_trial_retries_without_response_format_and_does_not_paint_context(monkeypatch):
    trial_posts = []

    def handler(method, url, headers, payload):
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'qwen2.5:7b'}]})
        content = (payload.get('messages') or [{}])[0].get('content') or ''
        if content == 'ok':
            return _FakeResponse(200, {'choices': [{'message': {'content': 'ok'}}]})
        trial_posts.append(dict(payload))
        if 'response_format' in payload:
            return _FakeResponse(400, {'error': {'message': 'response_format is not supported'}})
        raise httpx.TimeoutException('trial still loading')

    monkeypatch.setattr('httpx.Client', lambda *args, **kwargs: _FakeClient(handler))
    result = validate_connection_with_probe(_ollama(), 'qwen2.5:7b', probe_kind='trial')
    assert result.ok is True
    assert result.trial_passed is False
    assert result.trial_answer == 'transport'
    assert result.trial_context_ok is True
    assert result.trial_json_ok is None
    assert trial_posts[0].get('response_format') == {'type': 'json_object'}
    assert 'response_format' not in trial_posts[1]


def test_local_not_ready_sentence_matches_the_settings_hook_and_every_locale():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    hook = (root / 'frontend/src/features/settings/useModelSettings.ts').read_text(encoding='utf-8')
    assert LOCAL_MODEL_NOT_READY_HINT in hook
    for name in ('zh', 'en', 'ja', 'ko', 'es', 'fr', 'pt', 'ru'):
        text = (root / 'frontend/src/i18n/locales' / f'{name}.json').read_text(encoding='utf-8')
        assert LOCAL_MODEL_NOT_READY_HINT in text


def test_connection_refused_is_still_a_failed_local_service(monkeypatch):
    import socket
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    sock.close()
    conn = ai.Connection(id='o1', name='Ollama', provider='ollama', base_url=f'http://127.0.0.1:{port}/v1')
    result = validate_connection(conn, 'qwen2.5:7b')
    assert result.ok is False
    assert result.error_type == 'connection'
    assert result.warning == ''
