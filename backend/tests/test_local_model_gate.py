"""T3: local model params_b / context_tokens from Ollama /api/show and name inference."""
import asyncio
import json

import pytest

from backend.core import model_registry as registry
from backend.services import ai_model_settings as ai


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())


def test_parse_parameter_size_units():
    assert registry.parse_parameter_size('7B') == 7.0
    assert registry.parse_parameter_size('3.8B') == 3.8
    assert registry.parse_parameter_size('700M') == pytest.approx(0.7)
    assert registry.parse_parameter_size(None) is None


def test_infer_params_from_name_regex():
    assert registry.infer_params_b_from_name('qwen2.5:7b') == 7.0
    assert registry.infer_params_b_from_name('llama3.1:8b-instruct-q4_K_M') == 8.0
    assert registry.infer_params_b_from_name('phi3') is None


def test_extract_context_tokens_from_model_info():
    assert registry.extract_context_tokens({'llama.context_length': 8192}) == 8192
    assert registry.extract_context_tokens({'qwen2.context_length': '32768'}) == 32768
    assert registry.extract_context_tokens({'other': 1}) is None


def test_below_gate_thresholds():
    assert registry.below_local_analysis_gate(3.0, 8192) is True
    assert registry.below_local_analysis_gate(7.0, 4096) is True
    assert registry.below_local_analysis_gate(7.0, 8192) is False
    assert registry.below_local_analysis_gate(None, None) is False


def test_records_include_params_from_show_fields():
    raw = [{
        'id': 'tinyllama:1.1b',
        'params_b': 1.1,
        'context_tokens': 2048,
        'capabilities': ['completion'],
    }]
    rows = registry._records(ai.Connection(id='o', name='o', provider='ollama', base_url='http://127.0.0.1:11434/v1'), raw, {})
    assert rows[0]['params_b'] == 1.1
    assert rows[0]['context_tokens'] == 2048


def test_lmstudio_infers_from_name_when_no_params():
    raw = [{'id': 'Qwen2.5-3B-Instruct'}]
    rows = registry._records(
        ai.Connection(id='l', name='l', provider='lmstudio', base_url='http://127.0.0.1:1234/v1'),
        raw, {},
    )
    assert rows[0]['params_b'] == 3.0
    assert 'context_tokens' not in rows[0] or rows[0].get('context_tokens') is None


def test_ollama_discover_merges_api_show(monkeypatch):
    class _Resp:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return self._payload

    class _Client:
        def __init__(self, *a, **k):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *a):
            return False
        async def post(self, url, json=None, headers=None):
            assert url.endswith('/api/show')
            assert json['model'] == 'phi3:3.8b'
            return _Resp({
                'capabilities': ['completion'],
                'details': {'parameter_size': '3.8B'},
                'model_info': {'phi3.context_length': 4096},
            })

    async def fake_get_json(url, headers=None, params=None, trust_env=True):
        return {'data': [{'id': 'phi3:3.8b'}]}

    monkeypatch.setattr(registry.model_catalog, '_http_get_json', fake_get_json)
    monkeypatch.setattr('httpx.AsyncClient', _Client)
    monkeypatch.setattr(registry, '_ensure_metadata', lambda: asyncio.sleep(0))

    connection = ai.Connection(id='o', name='o', provider='ollama', base_url='http://127.0.0.1:11434/v1')
    result = asyncio.run(registry.discover(connection, refresh=True))
    row = next(m for m in result['models'] if m['id'] == 'phi3:3.8b')
    assert row['params_b'] == 3.8
    assert row['context_tokens'] == 4096


def test_sanitize_infers_model_params_b():
    from backend.core.llm_telemetry import sanitize_llm_request_properties
    props = sanitize_llm_request_properties({
        'provider': 'ollama', 'model': 'qwen2.5:7b', 'kind': 'chat',
        'outcome': 'success', 'base_url_host': 'local',
    })
    assert props.get('model_params_b') == 7.0
