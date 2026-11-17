"""Issue #591 — a thinking-only chat completion is not valid outline JSON.

The in-app report said "Kimi K3 thinking-only" and did not include the vendor
model id. This fixture uses the catalog id ``kimi-k3`` only as the request
label. It does not call Moonshot. The body matches the OpenAI-compatible
shape where ``reasoning_content`` (and ``reasoning``) can hold text while
``content`` is empty. That reasoning text is never parsed as the answer,
even when it happens to be JSON.
"""
import json

import httpx
import pytest

from backend.services import ai_model_settings as ai
from backend.services.provider_validation import NO_FINAL_ANSWER_HINT, validate_connection_with_probe


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


def _kimi():
    return ai.Connection(
        id='kimi', name='Kimi', provider='kimi',
        base_url='https://api.moonshot.cn/v1', api_key='sk-test-key',
    )


def _reasoning_body(field):
    return {'choices': [{
        'finish_reason': 'length',
        'message': {
            'role': 'assistant',
            'content': '',
            field: json.dumps({'topics': [{'title': 'must-not-count'}]}, ensure_ascii=False),
        },
    }]}


@pytest.mark.parametrize('field', ['reasoning_content', 'reasoning'])
def test_reasoning_only_trial_is_not_json_and_not_a_context_error(monkeypatch, field):
    bodies = []

    def handler(method, url, headers, payload):
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'kimi-k3'}]})
        bodies.append(payload)
        content = (payload.get('messages') or [{}])[0].get('content') or ''
        if content == 'ok':
            return _FakeResponse(200, {'choices': [{'message': {'content': 'ok'}, 'finish_reason': 'stop'}]})
        assert 'thinking' not in payload
        assert payload.get('enable_thinking') is None
        return _FakeResponse(200, _reasoning_body(field))

    monkeypatch.setattr('httpx.Client', lambda *args, **kwargs: _FakeClient(handler))
    result = validate_connection_with_probe(_kimi(), 'kimi-k3', probe_kind='trial')
    assert result.ok is True  # the short probe answered; the trial does not flip the connection
    assert result.trial_passed is False
    assert result.trial_answer == 'no_answer'
    assert result.trial_context_ok is True
    assert result.trial_json_ok is None
    assert 'must-not-count' not in json.dumps(result.as_api())
    assert any(item.get('max_tokens') == 2048 for item in bodies if item.get('messages') and item['messages'][0]['content'] != 'ok')


def test_quick_probe_empty_reasoning_fails_closed_with_an_actionable_hint(monkeypatch):
    def handler(method, url, headers, payload):
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'kimi-k3'}]})
        return _FakeResponse(200, _reasoning_body('reasoning_content'))

    monkeypatch.setattr('httpx.Client', lambda *args, **kwargs: _FakeClient(handler))
    result = validate_connection_with_probe(_kimi(), 'kimi-k3', probe_kind='quick')
    assert result.ok is False
    assert result.hint_key == NO_FINAL_ANSWER_HINT
    assert result.error_type == 'unknown'
    # Quick probe does not invent trial lights.
    assert result.trial_context_ok is None
    assert result.trial_json_ok is None
    assert result.trial_passed is None
    api = result.as_api()
    assert 'must-not-count' not in json.dumps(api)

    saved = _kimi()
    saved.validation_status = 'failed'
    saved.validation_error_type = result.error_type
    saved.validation_hint_key = result.hint_key
    settings = ai.ModelSettings(
        connections=[saved],
        analysis=ai.Assignment(connection_id='kimi', model='kimi-k3', capability='auto', model_source='user'),
    )
    ai.save(settings)
    loaded = ai.load()
    assert loaded.connections[0].validation_hint_key == NO_FINAL_ANSWER_HINT
    assert loaded.connections[0].api_key == 'sk-test-key'
    assert loaded.connections[0].base_url == 'https://api.moonshot.cn/v1'


def test_trial_timeout_is_transport_not_context_or_format(monkeypatch):
    def handler(method, url, headers, payload):
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'kimi-k3'}]})
        content = (payload.get('messages') or [{}])[0].get('content') or ''
        if content == 'ok':
            return _FakeResponse(200, {'choices': [{'message': {'content': 'ok'}}]})
        raise httpx.TimeoutException('timed out')

    monkeypatch.setattr('httpx.Client', lambda *args, **kwargs: _FakeClient(handler))
    result = validate_connection_with_probe(_kimi(), 'kimi-k3', probe_kind='trial')
    assert result.ok is True
    assert result.trial_answer == 'transport'
    assert result.trial_context_ok is True
    assert result.trial_json_ok is None
    assert result.trial_passed is False


def test_no_answer_sentence_is_in_the_trial_panel_and_every_locale():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    panel = (root / 'frontend/src/features/settings/trialRunResult.ts').read_text(encoding='utf-8')
    assert NO_FINAL_ANSWER_HINT in panel
    for name in ('zh', 'en', 'ja', 'ko', 'es', 'fr', 'pt', 'ru'):
        text = (root / 'frontend/src/i18n/locales' / f'{name}.json').read_text(encoding='utf-8')
        assert NO_FINAL_ANSWER_HINT in text


def test_visible_non_json_is_still_a_format_failure(monkeypatch):
    def handler(method, url, headers, payload):
        if method == 'GET':
            return _FakeResponse(200, {'data': [{'id': 'kimi-k3'}]})
        content = (payload.get('messages') or [{}])[0].get('content') or ''
        if content == 'ok':
            return _FakeResponse(200, {'choices': [{'message': {'content': 'ok'}}]})
        return _FakeResponse(200, {'choices': [{'message': {'content': 'not json', 'reasoning_content': '{"topics":[{"title":"hidden"}]}'}}]})

    monkeypatch.setattr('httpx.Client', lambda *args, **kwargs: _FakeClient(handler))
    result = validate_connection_with_probe(_kimi(), 'kimi-k3', probe_kind='trial')
    assert result.trial_answer == 'format'
    assert result.trial_json_ok is False
    assert result.trial_context_ok is True
    assert result.trial_passed is False
