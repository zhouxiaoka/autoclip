"""Credential-free coverage for the MiniMax ordinary-text preset."""
from types import SimpleNamespace

import pytest

from backend.core.cloud_presets import resolve_cloud_preset
from backend.core.llm_providers import OpenAIProvider
from backend.core.model_catalog import curated_models, default_model_for, supports_vision, IMAGE_MODELS
from backend.core.provider_url import normalize_provider_base_url


@pytest.mark.parametrize('model', ['MiniMax-M3.1-Flash', 'MiniMax-M3', 'MiniMax-M2.7', 'custom-model'])
@pytest.mark.parametrize('base_url', [None, 'https://api.minimaxi.com/v1', 'https://relay.example/v1'])
def test_sdk_text_boundary_preserves_explicit_model_and_endpoint(monkeypatch, model, base_url):
    import openai
    calls = []
    clients = []

    def create(**payload):
        calls.append(payload)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='result'), finish_reason='stop')], usage=None)

    def client(**kwargs):
        clients.append(kwargs)
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    monkeypatch.setattr(openai, 'OpenAI', client)
    provider, endpoint, preset = resolve_cloud_preset('minimax', base_url)
    assert provider == 'openai'
    instance = OpenAIProvider('fixture-only', model, base_url=endpoint)
    result = instance.call('Summarize', 'subtitle text', temperature=0.2, max_tokens=128)
    assert clients[0]['api_key'] == 'fixture-only'
    assert clients[0]['base_url'] == (base_url or 'https://api.minimax.io/v1')
    assert result.content == 'result'
    assert len(calls) == 1
    assert calls[0]['model'] == model
    assert calls[0]['max_tokens'] == 128
    assert calls[0]['temperature'] == 0.2
    assert len(calls[0]['messages']) == 1
    assert calls[0]['messages'][0]['role'] == 'user'
    assert 'subtitle text' in calls[0]['messages'][0]['content']
    assert 'extra_body' not in calls[0]


def test_mocked_http_catalog_keeps_order_and_legacy_models(monkeypatch):
    import asyncio
    from backend.core import model_catalog
    calls = []

    async def get(url, **kwargs):
        calls.append((url, kwargs))
        return {'data': [{'id': 'MiniMax-M2.7'}, {'id': 'custom-model'}, {'id': 'MiniMax-M3'}]}

    monkeypatch.setattr(model_catalog, '_http_get_json', get)
    model_catalog.clear_model_list_cache()
    offline = asyncio.run(model_catalog.list_available_models('minimax'))
    assert offline.models == ['MiniMax-M3.1-Flash', 'MiniMax-M3']
    assert not calls
    live = asyncio.run(model_catalog.list_available_models('minimax', api_key='fixture-only', refresh=True))
    assert live.models == ['MiniMax-M3.1-Flash', 'MiniMax-M3', 'MiniMax-M2.7', 'custom-model']
    assert live.image_models == []
    assert calls[0][0] == 'https://api.minimax.io/v1/models'
    assert calls[0][1]['headers'] == {'Authorization': 'Bearer fixture-only'}
    model_catalog.clear_model_list_cache()


def test_catalog_is_flash_first_without_enabling_media():
    assert curated_models('minimax') == ['MiniMax-M3.1-Flash', 'MiniMax-M3']
    assert default_model_for('minimax') == 'MiniMax-M3.1-Flash'
    assert resolve_cloud_preset('minimax')[2].default_model == 'MiniMax-M3.1-Flash'
    assert 'minimax' not in IMAGE_MODELS
    for model in curated_models('minimax'):
        assert not supports_vision(model)
    assert normalize_provider_base_url('https://api.minimaxi.com', 'minimax') == 'https://api.minimaxi.com/v1'
