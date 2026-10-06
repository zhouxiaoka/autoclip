"""Connection isolation, migration, atomic persistence and dynamic capability data."""
import asyncio
import json
import os
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.services import ai_model_settings as ai
from backend.core import model_registry as registry

legacy_migrate = ai.migrate_legacy


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())


def example():
    return ai.ModelSettings(
        connections=[
            ai.Connection(id='one', name='Analysis account', provider='openai', base_url='https://one.example/v1', api_key='sk-first-secret'),
            ai.Connection(id='two', name='Cover account', provider='openai', base_url='https://two.example/v1', api_key='sk-second-secret'),
        ],
        analysis=ai.Assignment(connection_id='one', model='custom-vision', capability='multimodal'),
        cover=ai.Assignment(connection_id='two', model='my-image'), cover_enabled=True,
    )


def test_independent_connections_and_key_references_survive_analysis_change():
    from backend.services import cover
    from backend.services.studio import vision_settings
    ai.save(example())
    assert vision_settings.effective()['api_key'] == 'sk-first-secret'
    assert cover.load_config().api_key == 'sk-second-secret'
    config = ai.load()
    config.analysis.model = 'another-model'
    config.connections[0].api_key = 'rotated-key'
    ai.save(config)
    assert vision_settings.effective()['model'] == 'another-model'
    assert vision_settings.effective()['api_key'] == 'rotated-key'
    assert cover.load_config().model == 'my-image'
    assert cover.load_config().api_key == 'sk-second-secret'


def test_same_provider_multiple_accounts_and_separate_vision():
    config = example()
    config.vision = ai.Assignment(connection_id='two', model='vision-b', capability='multimodal')
    config.analysis.capability = 'text'
    ai.save(config)
    assert ai.vision_endpoint(ai.load()) == {'base_url': 'https://two.example/v1', 'api_key': 'sk-second-secret', 'model': 'vision-b'}


def test_secrets_are_masked_preserved_and_can_be_cleared():
    response = ai.save(example())
    assert 'sk-first-secret' not in json.dumps(response)
    assert all('api_key' not in c for c in response['connections'])
    ai.save(ai.ModelSettings.model_validate(response))
    assert ai.load().connections[0].api_key == 'sk-first-secret'
    response['connections'][0]['api_key'] = ''
    ai.save(ai.ModelSettings.model_validate(response))
    assert ai.load().connections[0].api_key == ''
    assert os.stat(ai.path()).st_mode & 0o777 == 0o600


def test_changed_endpoint_cannot_reuse_hidden_key():
    response = ai.save(example())
    response['connections'][0]['base_url'] = 'https://new.example/v1'
    before = ai.path().read_bytes()
    with pytest.raises(ValueError, match='重新填写'):
        ai.save(ai.ModelSettings.model_validate(response))
    assert ai.path().read_bytes() == before


def test_invalid_binding_and_visual_choice_do_not_partially_save():
    ai.save(example())
    before = ai.path().read_bytes()
    config = example()
    config.analysis.capability = 'text'
    config.analysis_mode = 'visual'
    with pytest.raises(ValueError, match='多模态'):
        ai.save(config)
    assert ai.path().read_bytes() == before
    raw = example().model_dump()
    raw['connections'].pop()
    with pytest.raises(ValidationError, match='引用的服务'):
        ai.ModelSettings.model_validate(raw)


def test_atomic_write_failure_leaves_old_config(monkeypatch):
    ai.save(example())
    before = ai.path().read_bytes()
    def fail(*args):
        raise OSError('disk full')
    monkeypatch.setattr(ai.os, 'replace', fail)
    with pytest.raises(OSError):
        ai.save(example())
    assert ai.path().read_bytes() == before
    assert not list(ai.path().parent.glob('*.tmp'))


def test_local_analysis_does_not_disable_cloud_cover():
    from backend.services import cover
    config = example()
    config.connections[0] = ai.Connection(id='one', name='Local', provider='ollama', api_key='')
    ai.save(config)
    assert ai.vision_endpoint(ai.load())['base_url'] == 'http://localhost:11434/v1'
    assert cover.load_config().enabled and cover.load_config().api_key == 'sk-second-secret'


def test_runtime_manager_reloads_connection_document(tmp_path, monkeypatch):
    from backend.core.llm_manager import LLMManager
    monkeypatch.setattr(LLMManager, '_sync_config_if_needed', lambda self: None)
    monkeypatch.setattr(LLMManager, '_initialize_provider', lambda self: None)
    ai.save(example())
    manager = LLMManager(settings_file=tmp_path / 'settings.json')
    assert manager.settings['openai_api_key'] == 'sk-first-secret'
    config = example()
    config.analysis = ai.Assignment(connection_id='two', model='new-analysis')
    ai.save(config)
    manager._reload_if_settings_changed()
    assert manager.settings['openai_api_key'] == 'sk-second-secret'
    assert manager.settings['model_name'] == 'new-analysis'


def test_qwen_verified_and_unknown_is_not_text_only():
    c = ai.Connection(id='q', name='Qwen', provider='dashscope')
    assert registry.lookup_capability(c, 'qwen3.8-max') == 'multimodal'
    assert registry.lookup_capability(c, 'qwen3.8-flash') == 'multimodal'
    assert registry.lookup_capability(c, 'qwen-future-unknown') is None
    unknown = registry._records(c, [{'id': 'future-model'}], {})[0]
    assert unknown['capability'] is None and unknown['analysis']


def test_http_config_and_discovery_use_saved_secrets_without_returning_them(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router
    app = FastAPI()
    app.include_router(router)
    async def discover(connection, refresh):
        assert connection.api_key == 'sk-first-secret'
        return {'models': [{'id': 'new-model', 'capability': 'multimodal', 'analysis': True, 'image': False}], 'source': 'live'}
    monkeypatch.setattr(registry, 'discover', discover)
    with TestClient(app) as client:
        response = client.put('/settings/ai-models', json=example().model_dump())
        assert response.status_code == 200
        assert 'sk-first-secret' not in response.text
        connection = response.json()['connections'][0]
        listing = client.post('/settings/ai-models/discover', json={'connection': connection})
        assert listing.status_code == 200 and listing.json()['models'][0]['id'] == 'new-model'
        assert client.get('/settings/ai-models').json()['cover']['connection_id'] == 'two'


def test_no_unselected_ocr_model_is_called():
    from backend.services import cover
    config = example()
    config.analysis.capability = 'text'
    ai.save(config)
    with pytest.raises(cover.ImageError, match='跳过校对'):
        cover.verify_endpoint(cover.load_config())


def test_live_metadata_overrides_catalog_and_keeps_new_models(monkeypatch):
    c = example().connections[0]
    async def metadata():
        return None
    async def fetch(*args, **kwargs):
        return {'data': [{'id': 'brand-new', 'architecture': {'input_modalities': ['text', 'image'], 'output_modalities': ['text']}},
                         {'id': 'image-new', 'architecture': {'input_modalities': ['text'], 'output_modalities': ['image']}}]}
    monkeypatch.setattr(registry, '_ensure_metadata', metadata)
    monkeypatch.setattr(registry.model_catalog, '_http_get_json', fetch)
    result = asyncio.run(registry.discover(c))
    assert [m['id'] for m in result['models']] == ['brand-new', 'image-new']
    assert registry.lookup_capability(c, 'brand-new') == 'multimodal'
    assert result['models'][1]['image'] and not result['models'][1]['analysis']
    assert 'sk-first-secret' not in registry._path().read_text()


def test_failed_refresh_preserves_last_live_list(monkeypatch):
    c = example().connections[0]
    registry._update(registry._scope(c), {'models': [{'id': 'saved-model'}], 'updated_at': 1, 'source': 'live'})
    async def metadata():
        return None
    async def fail(*args, **kwargs):
        raise RuntimeError('network unavailable')
    monkeypatch.setattr(registry, '_ensure_metadata', metadata)
    monkeypatch.setattr(registry.model_catalog, '_http_get_json', fail)
    result = asyncio.run(registry.discover(c, refresh=True))
    assert result['models'] == [{'id': 'saved-model'}]
    assert result['source'] == 'cache' and result['warning']


@pytest.mark.parametrize('cover_provider', ['openai', 'gemini', 'grok', 'glm'])
def test_migration_keeps_legacy_endpoints_without_writing(monkeypatch, cover_provider):
    # Retrieve the real function, replaced in the fixture only to isolate saves.
    from backend.services import cover
    from backend.services.studio import vision_settings, analysis_preferences
    from backend.core import llm_manager
    manager = SimpleNamespace(settings={'llm_provider': 'openai', 'model_name': 'main-model'},
                              _reload_if_settings_changed=lambda: None,
                              openai_compatible_endpoint=lambda: {'base_url': 'https://main.example/v1', 'api_key': 'main-key'})
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: manager)
    monkeypatch.setattr(vision_settings, 'effective', lambda: {'mode': 'custom', 'base_url': 'https://vision.example/v1', 'api_key': 'vision-key', 'model': 'vision-model'})
    monkeypatch.setattr(cover, 'load_config', lambda: cover.CoverConfig(provider=cover_provider, enabled=True, model='image-model', api_key='image-key', base_url='https://image.example/v1'))
    monkeypatch.setattr(analysis_preferences, 'load', lambda: analysis_preferences.AnalysisPreferences(analysis_mode='subtitle'))
    config = legacy_migrate()
    assert len(config.connections) == 3
    assert ai.connection_for(config, config.vision).api_key == 'vision-key'
    assert ai.connection_for(config, config.cover).api_key == 'image-key'
    assert ai.image_endpoint(ai.connection_for(config, config.cover)) == {
        'provider': cover_provider, 'api_key': 'image-key', 'base_url': 'https://image.example/v1'}
    assert config.analysis_mode == 'subtitle'
    assert not ai.path().exists()


@pytest.mark.parametrize('invalid', [
    {'base_url': 'https://image.example/v1?api_key=synthetic-secret'},
    {'base_url': 'not-an-endpoint'},
    {'api_key': 'x' * 2001},
    {'model': 'm' * 201},
])
def test_invalid_legacy_cover_does_not_block_settings_or_overwrite_files(monkeypatch, invalid):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router
    from backend.services import cover
    from backend.services.studio import vision_settings, analysis_preferences
    from backend.core import llm_manager
    manager = SimpleNamespace(settings={'llm_provider': 'openai', 'model_name': 'main-model'},
                              _reload_if_settings_changed=lambda: None,
                              openai_compatible_endpoint=lambda: {'base_url': 'https://main.example/v1', 'api_key': 'main-key'})
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: manager)
    monkeypatch.setattr(vision_settings, 'effective', lambda: {})
    monkeypatch.setattr(cover, 'load_config', lambda: cover.CoverConfig(**{'enabled': True, 'model': 'image-model', **invalid}))
    monkeypatch.setattr(analysis_preferences, 'load', lambda: analysis_preferences.AnalysisPreferences(analysis_mode='subtitle'))
    monkeypatch.setattr(ai, 'migrate_legacy', legacy_migrate)
    legacy_path = cover.config_path()
    legacy_path.write_text('{"legacy": "preserved"}')
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get('/settings/ai-models')
        assert response.status_code == 200
        value = response.json()
        assert value['analysis']['model'] == 'main-model'
        assert value['connections'][0]['has_key']
        assert value['cover'] is None and not value['cover_enabled']
        assert value['migration_warnings'] == ['cover_configuration_invalid']
        assert 'synthetic-secret' not in response.text and 'main-key' not in response.text
    assert legacy_path.read_text() == '{"legacy": "preserved"}'
    assert not ai.path().exists()


@pytest.mark.parametrize('role', ['analysis', 'vision'])
def test_invalid_legacy_role_preserves_other_connections(monkeypatch, role):
    from backend.core import llm_manager
    from backend.services import cover
    from backend.services.studio import vision_settings, analysis_preferences
    endpoint = {'base_url': 'https://main.example/v1', 'api_key': 'main-key'}
    vision = {'mode': 'custom', 'base_url': 'https://vision.example/v1', 'api_key': 'vision-key', 'model': 'vision-model'}
    (endpoint if role == 'analysis' else vision)['base_url'] = 'https://invalid.example/v1?key=synthetic-secret'
    manager = SimpleNamespace(settings={'llm_provider': 'openai', 'model_name': 'main-model'},
                              _reload_if_settings_changed=lambda: None,
                              openai_compatible_endpoint=lambda: endpoint)
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: manager)
    monkeypatch.setattr(vision_settings, 'effective', lambda: vision)
    monkeypatch.setattr(cover, 'load_config', lambda: cover.CoverConfig(model='image-model', api_key='image-key', base_url='https://image.example/v1'))
    monkeypatch.setattr(analysis_preferences, 'load', lambda: analysis_preferences.AnalysisPreferences())
    config = legacy_migrate()
    assert getattr(config, role) is None
    assert config.cover.model == 'image-model'
    assert config._migration_warnings == [role + '_configuration_invalid']
    assert 'synthetic-secret' not in json.dumps(ai.public(config))
    assert not ai.path().exists()


@pytest.mark.parametrize('raw', ['{"version":', '{"version":99}', '[]'])
def test_corrupt_saved_settings_can_be_repaired_without_reusing_keys(raw):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router
    target = ai.path()
    target.write_text(raw)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get('/settings/ai-models')
        assert response.status_code == 200
        assert response.json()['connections'] == []
        assert response.json()['migration_warnings'] == ['settings_configuration_invalid']
        assert response.json()['saved'] is False, 'a damaged file must not hide first-run repair or claim saved settings'
        assert target.read_text() == raw
        # Runtime readers still reject invalid files; only the editor offers recovery.
        with pytest.raises(ValidationError):
            ai.load()
        result = client.put('/settings/ai-models', json=example().model_dump())
        assert result.status_code == 200
        assert ai.load().analysis.model == 'custom-vision'
    backups = list(target.parent.glob('ai-model-settings.invalid.*.json'))
    assert len(backups) == 1 and backups[0].read_text() == raw


def test_unrecognized_legacy_transcription_model_does_not_break_settings(monkeypatch):
    from backend.core import desktop_config
    previous = SimpleNamespace(speech_recognition=SimpleNamespace(whisper_config=SimpleNamespace(model_name='invalid-model')))
    monkeypatch.setattr(desktop_config, 'get_desktop_config', lambda: previous)
    value = ai.public(ai.ModelSettings())
    assert value['transcription']['model'] == 'base'
    assert value['migration_warnings'] == ['transcription_configuration_invalid']


def test_infistar_public_preview_and_exact_account_intersection(monkeypatch):
    calls = []
    async def fetch(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith('/api/pricing'):
            assert not kwargs.get('headers')
            return {'success': True, 'data': [
                {'model_name': 'new-image', 'supported_endpoint_types': ['image-generation']},
                {'model_name': 'edit-only', 'supported_endpoint_types': ['image-edit']},
                {'model_name': 'new-chat', 'supported_endpoint_types': ['openai'], 'tags': '图像理解,工具调用'},
                {'model_name': 'public-only', 'supported_endpoint_types': ['image-generation']},
            ]}
        return {'data': [{'id': 'new-image'}, {'id': 'new-chat'}, {'id': 'edit-only'}]}
    async def metadata():
        return None
    monkeypatch.setattr(registry.model_catalog, '_http_get_json', fetch)
    monkeypatch.setattr(registry, '_ensure_metadata', metadata)
    connection = ai.Connection(id='preview', name='Infistar', provider='infistar')
    preview = asyncio.run(registry.discover(connection))
    assert preview['preview'] is True
    assert len(calls) == 1 and calls[0][0].endswith('/api/pricing')
    assert [m['id'] for m in preview['models'] if m['image']] == ['new-image', 'public-only']
    connection.api_key = 'test-secret'
    account = asyncio.run(registry.discover(connection))
    assert not account.get('preview')
    assert [m['id'] for m in account['models'] if m['image']] == ['new-image']
    assert [m['id'] for m in account['models'] if m['analysis']] == ['new-chat']
    assert registry.lookup_capability(connection, 'new-chat') == 'multimodal'
    assert 'test-secret' not in registry._path().read_text()


def test_public_catalog_outage_preserves_preview(monkeypatch):
    async def fail(*args, **kwargs):
        raise RuntimeError('offline')
    monkeypatch.setattr(registry.model_catalog, '_http_get_json', fail)
    connection = ai.Connection(id='preview', name='Infistar', provider='infistar')
    result = asyncio.run(registry.discover(connection))
    assert result['preview']
    assert len([m for m in result['models'] if m['image']]) > 1
    assert '缓存' in result['warning']


def test_official_preview_does_not_call_authenticated_models_endpoint(monkeypatch):
    async def metadata():
        return None
    async def unexpected(*args, **kwargs):
        raise AssertionError('preview must not call authenticated endpoint')
    monkeypatch.setattr(registry, '_ensure_metadata', metadata)
    monkeypatch.setattr(registry.model_catalog, '_http_get_json', unexpected)
    result = asyncio.run(registry.discover(ai.Connection(id='preview', name='OpenAI', provider='openai')))
    assert result['preview'] and result['models']


@pytest.mark.parametrize('provider,expected', [
    ('seed', {'doubao-seedream-5-0-flash-260915', 'doubao-seedream-5-0-pro-260628'}),
    ('dashscope', {'qwen-image-3.0', 'wan2.7-image', 'z-image-turbo'}),
    ('gemini', {'gemini-3.1-flash-image', 'gemini-3-pro-image'}),
    ('openai', {'gpt-image-2.5-flare', 'gpt-image-2'}),
    ('glm', {'glm-image', 'cogview-4'}),
    ('grok', {'grok-imagine-image-2.0', 'grok-imagine-image'}),
])
def test_official_image_previews_include_verified_models(monkeypatch, provider, expected):
    async def metadata():
        return None
    monkeypatch.setattr(registry, '_ensure_metadata', metadata)
    result = asyncio.run(registry.discover(ai.Connection(id='preview', name=provider, provider=provider)))
    assert expected <= {m['id'] for m in result['models'] if m['image']}
    assert result['preview']
    if provider == 'seed':
        assert 'doubao-seedream-5-0-260128' not in {m['id'] for m in result['models']}


def test_official_image_and_gateway_protocols_stay_independent():
    for provider in ['gemini', 'grok', 'glm']:
        endpoint = ai.image_endpoint(ai.Connection(id='one', name='test', provider=provider))
        assert endpoint['provider'] == provider
        assert not endpoint['base_url'].endswith('/openai')
    assert ai.image_endpoint(ai.Connection(id='one', name='test', provider='infistar'))['provider'] == 'openai'


def test_research_agent_image_output_is_not_a_native_cover_model():
    connection = ai.Connection(id='preview', name='Gemini', provider='gemini')
    data = {'metadata': {'providers': {'google': {'deep-research-preview-04-2026': {'image_output': True}}}}}
    records = registry._records(connection, ['deep-research-preview-04-2026'], data)
    assert not records[0]['image'] and not records[0]['analysis']


def test_transcription_model_is_saved_and_used_without_overriding_explicit_call(monkeypatch, tmp_path):
    from backend.utils import speech_recognizer as speech
    config = example()
    config.transcription = ai.Transcription(model='large-v3')
    saved = ai.save(config)
    assert saved['transcription'] == {'provider': 'whisper_local', 'model': 'large-v3', 'connection_id': None}
    calls = []
    class FakeRecognizer:
        def __init__(self, config=None):
            self.config = config
        def generate_subtitle(self, video, output, config):
            calls.append(config.model)
            assert config.enable_fallback is False
            return output
    monkeypatch.setattr(speech, 'SpeechRecognizer', FakeRecognizer)
    speech.generate_subtitle_for_video(tmp_path / 'video.mp4', tmp_path / 'out.srt', method='whisper_local')
    speech.generate_subtitle_for_video(tmp_path / 'video.mp4', tmp_path / 'out.srt', method='whisper_local', model='tiny')
    speech.generate_subtitle_for_video(tmp_path / 'video.mp4', tmp_path / 'out.srt')
    assert calls == ['large-v3', 'tiny', 'large-v3']


def test_cloud_transcription_binding_is_validated():
    from pydantic import ValidationError
    from backend.services.ai_model_settings import ModelSettings, Connection, Transcription
    connection = Connection(id='asr', name='ASR', provider='openai')
    value = ModelSettings(connections=[connection], transcription=Transcription(provider='cloud', model='whisper-1', connection_id='asr'))
    assert value.transcription.connection_id == 'asr'
    with pytest.raises(ValidationError):
        ModelSettings(transcription=Transcription(provider='cloud', model='whisper-1', connection_id='gone'))
    with pytest.raises(ValidationError):
        ModelSettings(connections=[connection], transcription=Transcription(provider='cloud', model='gpt-4o-transcribe', connection_id='asr'))


def test_cloud_selection_routes_auto_without_loading_whisper(monkeypatch, tmp_path):
    from backend.services import ai_model_settings as settings, cloud_transcription
    from backend.utils.speech_recognizer import generate_subtitle_for_video, configured_whisper_model
    value = settings.ModelSettings(connections=[settings.Connection(id='asr', name='ASR', provider='openai')],
        transcription=settings.Transcription(provider='cloud', connection_id='asr', model='whisper-1'))
    monkeypatch.setattr(settings, 'load', lambda: value)
    calls = []
    monkeypatch.setattr(cloud_transcription, 'transcribe', lambda *args: calls.append(args) or tmp_path / 'result.srt')
    assert generate_subtitle_for_video(tmp_path / 'video.mp4') == tmp_path / 'result.srt'
    assert calls[0][2] is value
    assert configured_whisper_model('small') == 'small'


def test_api88_gateway_catalog_routes_account_models_and_isolates_keys(monkeypatch):
    async def no_metadata():
        pass

    async def account_models(url, **kwargs):
        assert url == 'https://88api.ai/v1/models'
        assert kwargs['headers']['Authorization'] == 'Bearer sk-88-only'
        return {'data': [{'id': 'gpt-image-1'}, {'id': 'whisper-1'},
                         {'id': 'gpt-5-mini'}, {'id': 'tts-1'}, {'id': 'sora-2'}]}

    monkeypatch.setattr(registry, '_ensure_metadata', no_metadata)
    monkeypatch.setattr(registry.model_catalog, '_http_get_json', account_models)
    c = ai.Connection(id='88', name='88API', provider='api88', api_key='sk-88-only')
    result = asyncio.run(registry.discover(c, refresh=True))
    by_id = {m['id']: m for m in result['models']}
    assert by_id['gpt-image-1']['image'] and not by_id['gpt-image-1']['analysis']
    assert by_id['whisper-1']['asr_supported'] and not by_id['whisper-1']['analysis']
    assert by_id['gpt-5-mini']['analysis']
    assert not by_id['tts-1']['analysis'] and not by_id['sora-2']['analysis']
    assert ai.image_endpoint(c)['base_url'] == 'https://88api.ai/v1'
    assert ai.image_endpoint(c)['api_key'] == 'sk-88-only'

    config = ai.ModelSettings(connections=[c], analysis=ai.Assignment(connection_id='88', model='gpt-5-mini'),
                              transcription=ai.Transcription(provider='cloud', connection_id='88', model='whisper-1'))
    response = ai.save(config)
    assert 'sk-88-only' not in json.dumps(response)
    assert ai.load().connections[0].api_key == 'sk-88-only'


def test_a_dedicated_bailian_endpoint_serves_text_models_on_its_compatible_path():
    host = 'https://llm-x.cn-beijing.maas.aliyuncs.com'
    for pasted in (host, host + '/api/v1', host + '/api/v1/', host + '/compatible-mode/v1'):
        connection = ai.Connection(id='b', name='百炼', provider='dashscope', base_url=pasted)
        assert ai.chat_endpoint(connection, 'qwen-plus')['base_url'] == host + '/compatible-mode/v1'
    assert ai.chat_endpoint(ai.Connection(id='d', name='d', provider='dashscope'), 'm')['base_url'] == 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    relay = ai.Connection(id='r', name='relay', provider='dashscope', base_url='https://proxy.example.com/v1')
    assert ai.chat_endpoint(relay, 'm')['base_url'] == 'https://proxy.example.com/v1', 'a 1.4 relay address is used as entered'


def test_fal_image_connections_and_unknown_image_apis_from_newer_versions():
    fal = ai.Connection(id='f', name='fal', provider='compatible', base_url='https://fal.run', api_key='k', image_api='fal')
    assert ai.image_endpoint(fal) == {'provider': 'fal', 'base_url': 'https://fal.run', 'api_key': 'k'}
    future = ai.Connection(id='n', name='n', provider='openai', image_api='some-future-api')
    assert future.image_api == 'auto'  # an unknown value never invalidates the whole settings file


def test_ai_covers_switched_on_by_1_4_are_off_after_upgrade_until_chosen_again():
    from backend.services import cover
    written_by_1_4 = example().model_dump()
    written_by_1_4.pop('cover_choice_version')
    ai.path().parent.mkdir(parents=True, exist_ok=True)
    ai.path().write_text(json.dumps(written_by_1_4), encoding='utf-8')
    loaded = ai.load()
    assert loaded.cover_enabled is False and loaded.cover.model == 'my-image', 'the chosen model stays for one click'
    assert cover.load_config().enabled is False, 'no billed AI cover in the background'
    loaded.cover_enabled = True  # the user picks AI generation in 1.5
    ai.save(loaded)
    assert ai.load().cover_enabled is True and cover.load_config().enabled is True


@pytest.mark.parametrize('model', ['qwen3-vl-flash', 'qwen3-vl-flash-2026-01-22'])
def test_official_qwen_vision_route_survives_unavailable_capability_catalog(monkeypatch, model):
    monkeypatch.setattr(registry, '_read', lambda: {})
    config = ai.ModelSettings(
        connections=[ai.Connection(id='dashscope', name='DashScope', provider='dashscope', api_key='test-key')],
        analysis=ai.Assignment(connection_id='dashscope', model=model),
        analysis_mode='auto', allow_visual_screening=True,
    )
    ai.save(config)
    from backend.services.studio import intelligence, vision_settings
    assert intelligence.ready(), 'enabled frame analysis silently fell back to subtitles'
    assert vision_settings.effective()['model'] == model
    # Do not infer an arbitrary gateway alias or a future model by its prefix.
    config.connections[0].provider = 'compatible'
    config.connections[0].base_url = 'https://gateway.example/v1'
    assert ai.vision_endpoint(config) is None
