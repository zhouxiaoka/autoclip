"""Connection isolation, migration, atomic persistence and dynamic capability data."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
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


@pytest.mark.parametrize('binding_id', ['old', 'independent', None])
@pytest.mark.parametrize('cover_enabled', [True, False])
def test_b2_analysis_switch_and_visual_toggle_http_save_round_trip(binding_id, cover_enabled):
    """Persist the frontend's switch/toggle contract through HTTP, disk and runtime routing."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router

    config = ai.ModelSettings(
        connections=[ai.Connection(id=id_, name=id_, provider=provider, api_key='')
                     for id_, provider in [('old', 'ollama'), ('new', 'lmstudio'), ('independent', 'ollama')]],
        analysis=ai.Assignment(connection_id='old', model='old-analysis', capability='multimodal'),
        vision=ai.Assignment(connection_id=binding_id, model='my-vision', capability='multimodal', model_source='user') if binding_id else None,
        cover=ai.Assignment(connection_id=binding_id or 'old', model='my-cover', model_source='user'),
        cover_enabled=cover_enabled,
        cover_follows_analysis=False,  # explicit independent cover, even on the analysis connection
    )
    switched = config.model_copy(update={
        'analysis': ai.Assignment(connection_id='new', model='new-analysis'),
    })
    off = switched.model_copy(update={'analysis_mode': 'subtitle', 'allow_visual_screening': False})
    on = off.model_copy(update={'analysis_mode': 'auto', 'allow_visual_screening': True})
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        for index, document in enumerate([config, switched, off, on]):
            payload = document.model_dump()
            payload['revision'] = client.get('/settings/ai-models').json()['revision']
            response = client.put('/settings/ai-models', json=payload)
            assert response.status_code == 200
            public = response.json()
            loaded = ai.load()
            assert loaded.vision == config.vision
            assert loaded.cover == config.cover
            assert loaded.cover_enabled == cover_enabled
            assert loaded.analysis.connection_id == ('old' if index == 0 else 'new')
            assert loaded.analysis_mode == ('subtitle' if index == 2 else 'auto')
            assert loaded.allow_visual_screening == (index != 2)
            assert public['vision'] == config.model_dump()['vision']
            assert public['cover'] == config.model_dump()['cover']
            assert client.get('/settings/ai-models').json()['vision'] == public['vision']
            assert client.get('/settings/ai-models').json()['cover'] == public['cover']
            routed = ai.vision_follow_binding(loaded)
            assert routed.connection_id == (binding_id or loaded.analysis.connection_id)
            assert routed.model == ('my-vision' if binding_id else loaded.analysis.model)
            assert ai.connection_for(loaded, loaded.cover).id == (binding_id or 'old')
            # Re-save the public editing document, just as reopening settings does.
            assert client.put('/settings/ai-models', json=public).status_code == 200
            assert ai.load().vision == config.vision
            assert ai.load().cover == config.cover


@pytest.mark.parametrize('entry', ['legacy', 'catalog', 'slots'])
@pytest.mark.parametrize('binding_id', ['old', 'independent'])
@pytest.mark.parametrize('cover_enabled', [True, False])
def test_x1_smart_own_provider_survives_analysis_switch_round_trip(entry, binding_id, cover_enabled):
    """Run the real frontend switch, then save/reopen through HTTP, disk and runtime."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router

    config = ai.ModelSettings(
        connections=[ai.Connection(id=id_, name=id_, provider=provider, api_key='')
                     for id_, provider in [('old', 'ollama'), ('new', 'lmstudio'), ('independent', 'ollama')]],
        analysis=ai.Assignment(connection_id='old', model='old-analysis'),
        vision=ai.Assignment(connection_id=binding_id, model='own-vision', capability='multimodal', model_source='preset'),
        cover=ai.Assignment(connection_id=binding_id, model='own-cover', model_source='preset'),
        cover_enabled=cover_enabled,
        cover_follows_analysis=False,  # explicit independent cover, even on the analysis connection
    )
    script = """
const fs = require('node:fs')
const { loadTs } = require('./tests/load-ts.cjs')
const mocks = { '../../i18n': { t: text => text } }
const logic = loadTs('modelSettingsLogic.ts', mocks)
const defaults = loadTs('modelDefaults.ts', mocks)
const view = loadTs('providerCatalogView.ts', mocks)
const slots = loadTs('defaultModelSlots.ts', mocks)
const state = logic.prepareLoaded(JSON.parse(fs.readFileSync(0, 'utf8')))
const connection = state.connections.find(c => c.id === 'new')
const models = [{ id: 'new-analysis', analysis: true }, { id: 'new-cover', image: true }]
const lists = { new: { models, source: 'live', preview: false } }
const entry = process.argv[1]
let switched = entry === 'legacy'
  ? logic.chooseProvider(state, 'analysis', 'lmstudio', lists, false).settings
  : entry === 'catalog' ? view.assignAnalysis(state, connection)
  : slots.applySmartSelection(state, 'analysis', 'new-analysis', 'new')
switched = defaults.applyModelDefaults(switched, connection, models, false)
process.stdout.write(JSON.stringify(logic.forSave(switched)))
"""
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.put('/settings/ai-models', json=config.model_dump()).status_code == 200
        result = subprocess.run(
            ['node', '-e', script, entry], cwd=Path(__file__).resolve().parents[2] / 'frontend',
            input=json.dumps(client.get('/settings/ai-models').json()),
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
        response = client.put('/settings/ai-models', json=json.loads(result.stdout))
        assert response.status_code == 200
        reopened = client.get('/settings/ai-models').json()
        loaded = ai.load()
        assert reopened['analysis']['connection_id'] == 'new'
        for role in ('vision', 'cover'):
            assert reopened[role] == getattr(config, role).model_dump()
            assert getattr(loaded, role) == getattr(config, role)
        assert reopened['cover_enabled'] == cover_enabled
        assert ai.connection_for(loaded, ai.vision_follow_binding(loaded)).id == binding_id
        assert ai.connection_for(loaded, loaded.cover).id == binding_id
        # Reopening and saving the public editing document keeps the same routing.
        assert client.put('/settings/ai-models', json=reopened).status_code == 200
        assert ai.load().vision == config.vision
        assert ai.load().cover == config.cover


def test_api_key_strips_surrounding_whitespace_on_construct_and_save():
    connection = ai.Connection(id='c', name='k', provider='openai', api_key='  sk-live-secret  \n')
    assert connection.api_key == 'sk-live-secret'
    assert ai.Connection(id='c', name='k', provider='openai', api_key=None).api_key is None
    assert ai.Connection(id='c', name='k', provider='openai', api_key='   ').api_key == ''
    settings = ai.ModelSettings(connections=[connection], analysis=ai.Assignment(connection_id='c', model='gpt-4o-mini'))
    ai.save(settings)
    assert ai.load().connections[0].api_key == 'sk-live-secret'


def test_http_put_strips_key_spaces():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router
    app = FastAPI()
    app.include_router(router)
    payload = example().model_dump()
    payload['connections'][0]['api_key'] = '  sk-first-secret  \n'
    with TestClient(app) as client:
        response = client.put('/settings/ai-models', json=payload)
    assert response.status_code == 200
    assert 'sk-first-secret' not in response.text
    assert ai.load().connections[0].api_key == 'sk-first-secret'


def test_secrets_are_masked_preserved_and_can_be_cleared():
    response = ai.save(example())
    assert 'sk-first-secret' not in json.dumps(response)
    assert all('api_key' not in c for c in response['connections'])
    response = ai.save(ai.ModelSettings.model_validate(response))
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


def test_invalid_binding_does_not_partially_save():
    ai.save(example())
    before = ai.path().read_bytes()
    raw = example().model_dump()
    raw['connections'].pop()
    with pytest.raises(ValidationError, match='引用的服务'):
        ai.ModelSettings.model_validate(raw)
    assert ai.path().read_bytes() == before


def test_visual_mode_without_vision_saves():
    config = example()
    config.analysis.capability = 'text'
    config.analysis_mode = 'visual'
    ai.save(config)
    loaded = ai.load()
    assert loaded.analysis_mode == 'visual'
    assert loaded.analysis.capability == 'text'
    assert ai.vision_follow_lacks_capability(loaded) is True


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
    # Back-to-back writes can share one mtime on coarse-timestamp filesystems (overlayfs/ext4
    # tick): make the second save observable, as it is for a real settings save seconds later.
    import os
    before = manager._settings_mtime[1] or 0
    os.utime(ai.path(), ns=(before + 1_000_000_000, before + 1_000_000_000))
    manager._reload_if_settings_changed()
    assert manager.settings['openai_api_key'] == 'sk-second-secret'
    assert manager.settings['model_name'] == 'new-analysis'


def test_qwen_verified_and_unknown_is_not_text_only():
    c = ai.Connection(id='q', name='Qwen', provider='dashscope')
    assert registry.lookup_capability(c, 'qwen3.8-max') == 'multimodal'
    assert registry.lookup_capability(c, 'qwen3.8-flash') == 'multimodal'
    assert registry.lookup_capability(c, 'qwen-future-unknown') is None
    unknown = registry._records(c, [{'id': 'future-model'}], {})[0]
    assert unknown['capability'] is None and not unknown['analysis']


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
    assert [row['id'] for row in result['models']] == ['saved-model']
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
    assert config.analysis.model_source == 'user'
    assert config.vision.model_source == 'user'
    assert config.cover.model_source == 'user'
    assert config.connections[0].base_url_source == 'user'
    assert config.connections[1].base_url_source == 'user'
    assert config.connections[2].base_url_source == 'user'
    assert not ai.path().exists()


def _legacy_cover_client(monkeypatch, invalid):
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
    return TestClient(app), legacy_path


def test_unmigratable_legacy_cover_keeps_key_and_resets_to_recommended(monkeypatch):
    from backend.services.model_settings_source import NOTICE_PURPOSE_RESET, recommended_model
    client, legacy_path = _legacy_cover_client(monkeypatch, {'base_url': 'https://image.example/v1?api_key=synthetic-secret'})
    with client:
        response = client.get('/settings/ai-models')
        assert response.status_code == 200
        value = response.json()
        assert value['analysis']['model'] == 'main-model'
        assert value['analysis']['model_source'] == 'user'
        assert any(c['has_key'] for c in value['connections'])
        assert value['cover']['model'] == recommended_model('openai', 'cover')
        assert value['cover']['model_source'] == 'preset'
        assert value['cover_enabled'] is True
        assert NOTICE_PURPOSE_RESET in value['migration_warnings']
        assert 'synthetic-secret' not in response.text and 'main-key' not in response.text
    assert legacy_path.read_text() == '{"legacy": "preserved"}'
    assert not ai.path().exists()


def test_oversized_legacy_cover_key_does_not_block_settings(monkeypatch):
    client, legacy_path = _legacy_cover_client(monkeypatch, {'api_key': 'x' * 2001})
    with client:
        response = client.get('/settings/ai-models')
        assert response.status_code == 200
        value = response.json()
        assert value['analysis']['model'] == 'main-model'
        assert value['cover'] is None and not value['cover_enabled']
        assert value['migration_warnings'] == ['cover_configuration_invalid']
        assert 'main-key' not in response.text
    assert legacy_path.read_text() == '{"legacy": "preserved"}'
    assert not ai.path().exists()


def test_oversized_legacy_cover_model_resets_to_recommended(monkeypatch):
    from backend.services.model_settings_source import NOTICE_PURPOSE_RESET, recommended_model
    client, legacy_path = _legacy_cover_client(monkeypatch, {'model': 'm' * 201, 'api_key': 'image-key', 'base_url': 'https://image.example/v1'})
    with client:
        response = client.get('/settings/ai-models')
        assert response.status_code == 200
        value = response.json()
        assert value['cover']['model'] == recommended_model('openai', 'cover')
        assert value['cover']['model_source'] == 'preset'
        assert NOTICE_PURPOSE_RESET in value['migration_warnings']
        assert value['connections'][-1]['has_key']
        assert 'image-key' not in response.text and 'm' * 20 not in response.text
    assert legacy_path.read_text() == '{"legacy": "preserved"}'


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
    from backend.services.model_settings_source import NOTICE_PURPOSE_RESET, recommended_model
    assert getattr(config, role) is not None
    assert getattr(config, role).model_source == 'preset'
    assert getattr(config, role).model == recommended_model(
        'openai' if role == 'analysis' else 'openai', role)
    assert config.cover.model == 'image-model'
    assert NOTICE_PURPOSE_RESET in config._migration_warnings
    assert next(c for c in config.connections if c.id == ('legacy-analysis' if role == 'analysis' else 'legacy-vision')).api_key
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


def test_dashscope_sync_asr_missing_from_models_stays_selectable(monkeypatch):
    async def fetch(url, **kwargs):
        assert url.endswith('/models')
        return {'data': [{'id': 'qwen-plus'}]}

    async def metadata():
        return None

    monkeypatch.setattr(registry.model_catalog, '_http_get_json', fetch)
    monkeypatch.setattr(registry, '_ensure_metadata', metadata)
    connection = ai.Connection(id='ds-asr', name='百炼', provider='dashscope', api_key='sk-test')
    result = asyncio.run(registry.discover(connection, refresh=True))
    by_id = {item['id']: item for item in result['models']}
    for name in ('qwen-audio-3.1-asr-flash', 'qwen-audio-3.0-asr-flash', 'fun-asr-flash-2026-06-15'):
        assert by_id[name]['asr'] is True
        assert by_id[name]['asr_supported'] is True
        assert by_id[name]['asr_preview'] is False
    assert by_id['qwen-audio-3.1-asr-flash-filetrans']['asr_preview'] is True
    assert not result.get('preview')


def test_dashscope_new_model_discovery_and_cached_runtime(monkeypatch):
    fixture = json.loads((Path(__file__).parent / 'fixtures/dashscope_model_settings.json').read_text())
    async def fetch(url, **kwargs):
        assert url == 'https://dashscope.aliyuncs.com/compatible-mode/v1/models'
        return {'data': fixture['account']['data'] + fixture['synthetic']}

    async def offline():
        pass

    monkeypatch.setattr(registry.model_catalog, '_http_get_json', fetch)
    monkeypatch.setattr(registry, '_ensure_metadata', offline)
    connection = ai.Connection(id='legacy-analysis', name='DashScope', provider='dashscope', api_key='fixture')
    live = asyncio.run(registry.discover(connection))
    cached = asyncio.run(registry.discover(connection))
    assert live['source'] == 'live' and cached['source'] == 'cache'
    records = {row['id']: row for row in cached['models']}
    for expected in fixture['expected']:
        assert {key: records[expected['id']][key] for key in expected} == expected
    # Exact verified official allowlist (qwen4-max) resists boilerplate text-only input metadata,
    # while unverified IDs still follow explicit provider input metadata.
    [verified_mm, explicit_text] = registry._records(connection, [
        {'id': 'qwen4-max', 'input_modalities': ['text']},
        {'id': 'fixture-alpha', 'input_modalities': ['text']},
    ], {})
    assert verified_mm['capability'] == 'multimodal'
    assert explicit_text['capability'] == 'text'
    assert registry.lookup_capability(connection, 'fixture-alpha') == 'multimodal'
    assert registry.lookup_capability(connection, 'fixture-max-new') is None


@pytest.mark.parametrize('cover_model', [None, '', 'qwen-image-2.1-pro'])
def test_dashscope_optional_cover_save_and_reopen(cover_model):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router
    from backend.services import cover

    previous = example()
    previous.connections.append(ai.Connection(id='legacy-analysis', name='DashScope', provider='dashscope', api_key='synthetic'))
    ai.save(previous)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        url = '/settings/ai-models'
        draft = client.get(url).json()
        binding = {'connection_id': 'legacy-analysis', 'model': 'qwen4-max', 'capability': 'auto', 'model_source': 'user'}
        draft.update(analysis=binding, vision=binding,
                     transcription={**binding, 'provider': 'cloud', 'model': 'qwen-audio-3.1-asr-flash'},
                     cover=None if cover_model is None else {**binding, 'model': cover_model},
                     cover_enabled=True)
        response = client.put(url, json=draft)
        assert response.status_code == 200, response.text
        reopened = client.get(url).json()
    for role in ('analysis', 'vision', 'transcription'):
        assert reopened[role]['connection_id'] == 'legacy-analysis'
        assert reopened[role]['model'] == draft[role]['model']
        assert reopened[role]['model_source'] == 'user'
    assert reopened['allow_send_frame'] is True and not reopened['prefer_local_cover']
    assert [c.api_key for c in ai.load().connections] == [c.api_key for c in previous.connections]
    assert reopened['cover'] == (draft['cover'] if cover_model else None)
    cfg = cover.load_config()
    assert cfg.enabled == bool(cover_model)
    assert cfg.model == (cover_model or '')
    assert cfg.api_key == ('synthetic' if cover_model else '')


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
    assert saved['transcription'] == {'provider': 'whisper_local', 'model': 'large-v3', 'connection_id': None, 'model_source': 'user'}
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
    with pytest.raises(ValueError, match='转写'):
        ai.save(ModelSettings(connections=[connection], transcription=Transcription(provider='cloud', model='gpt-4o-transcribe', connection_id='asr')))


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
        assert url == 'https://api.88api.ai/v1/models'
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
    assert ai.image_endpoint(c)['base_url'] == 'https://api.88api.ai/v1'
    assert ai.image_endpoint(c)['api_key'] == 'sk-88-only'

    config = ai.ModelSettings(connections=[c], analysis=ai.Assignment(connection_id='88', model='gpt-5-mini'),
                              transcription=ai.Transcription(provider='cloud', connection_id='88', model='whisper-1'))
    response = ai.save(config)
    assert 'sk-88-only' not in json.dumps(response)
    assert ai.load().connections[0].api_key == 'sk-88-only'


def test_api88_saved_legacy_base_url_is_not_rewritten():
    saved = ai.Connection(
        id='88', name='88API', provider='api88', api_key='sk-88-only',
        base_url='https://88api.ai/v1',
    )
    assert saved.base_url == 'https://88api.ai/v1'
    assert ai.chat_endpoint(saved, 'gpt-5-mini')['base_url'] == 'https://88api.ai/v1'
    assert ai.image_endpoint(saved)['base_url'] == 'https://88api.ai/v1'


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


@pytest.mark.parametrize('prefer_local', [True, False])
def test_image_binding_without_explicit_switch_follows_automatic_cover_preference(prefer_local):
    from backend.services import cover
    saved = example().model_dump()
    saved.pop('cover_enabled')
    saved.update(cover_choice_version=ai.COVER_CHOICE_VERSION, prefer_local_cover=prefer_local)
    ai.path().parent.mkdir(parents=True, exist_ok=True)
    ai.path().write_text(json.dumps(saved), encoding='utf-8')
    assert cover.load_config().enabled is (not prefer_local)


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


@pytest.mark.parametrize('model', ['qwen3-vl-flash', 'qwen3-vl-flash-2026-01-22', 'qwen4-max'])
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
    assert vision_settings.effective()['model_source'] == 'user'
    # Do not infer an arbitrary gateway alias or a future model by its prefix.
    config.connections[0].provider = 'compatible'
    config.connections[0].base_url = 'https://gateway.example/v1'
    assert ai.vision_endpoint(config) is None


def test_custom_base_url_rejects_console_host_and_embedded_credentials():
    with pytest.raises(ValidationError):
        ai.Connection(id='c', name='x', provider='compatible', base_url='https://user:pass@gw.example/v1')
    with pytest.raises(ValidationError):
        ai.Connection(id='c', name='x', provider='compatible', base_url='https://user@gw.example/v1')
    with pytest.raises(ValidationError, match='控制台或官网'):
        ai.Connection(id='c', name='x', provider='compatible', base_url='https://platform.openai.com/v1')
    with pytest.raises(ValidationError, match='控制台或官网'):
        ai.Connection(id='c', name='x', provider='compatible', base_url='https://bailian.console.aliyun.com')
    ok = ai.Connection(id='c', name='x', provider='compatible', base_url='https://gw.example/v1', api_key='k')
    assert ok.base_url == 'https://gw.example/v1'


def test_custom_models_survive_save_reopen_and_are_not_overwritten_by_discover(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router

    settings = ai.ModelSettings(
        connections=[ai.Connection(
            id='gw', name='Office gateway', provider='compatible',
            base_url='https://gw.example/v1', api_key='sk-custom-secret',
            custom_models=[ai.CustomModelOffer(
                id='office-llm', display_name='Office LLM', types=['language'],
                vision=True, scenarios=['analysis', 'vision'], enabled=True,
            )],
        )],
        analysis=ai.Assignment(connection_id='gw', model='office-llm', capability='multimodal'),
    )
    public = ai.save(settings)
    assert public['connections'][0]['custom_models'][0]['display_name'] == 'Office LLM'
    assert public['connections'][0]['custom_models'][0]['vision'] is True

    loaded = ai.load()
    offer = loaded.connections[0].custom_models[0]
    assert offer.id == 'office-llm'
    assert offer.display_name == 'Office LLM'
    assert offer.vision is True
    assert registry.lookup_capability(loaded.connections[0], 'office-llm') == 'multimodal'

    async def metadata():
        return None

    async def fetch(*args, **kwargs):
        return {'data': [{'id': 'other-live', 'architecture': {
            'input_modalities': ['text'], 'output_modalities': ['text'],
        }}]}

    monkeypatch.setattr(registry, '_ensure_metadata', metadata)
    monkeypatch.setattr(registry.model_catalog, '_http_get_json', fetch)
    result = asyncio.run(registry.discover(loaded.connections[0], refresh=True))
    listed = {item['id']: item for item in result['models']}
    assert 'office-llm' in listed
    assert 'other-live' in listed
    assert listed['office-llm']['capability'] == 'multimodal'
    assert listed['office-llm']['analysis'] is True
    reopened = ai.load()
    assert reopened.connections[0].custom_models[0].display_name == 'Office LLM'
    assert reopened.connections[0].custom_models[0].vision is True

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        body = client.get('/settings/ai-models').json()
        assert body['connections'][0]['custom_models'][0]['id'] == 'office-llm'
        assert body['connections'][0]['custom_models'][0]['display_name'] == 'Office LLM'
        listing = client.post('/settings/ai-models/discover', json={
            'connection': body['connections'][0], 'refresh': True,
        })
        assert listing.status_code == 200
        http_listed = {item['id']: item for item in listing.json()['models']}
        assert http_listed['office-llm']['capability'] == 'multimodal'
        again = client.get('/settings/ai-models').json()['connections'][0]['custom_models']
        assert again[0]['id'] == 'office-llm'
        assert again[0]['display_name'] == 'Office LLM'
        assert again[0]['vision'] is True


def test_fetch_list_returns_ids_without_secrets(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router

    assert len([route for route in router.routes
                if route.path == '/settings/ai-models/fetch-list' and 'POST' in route.methods]) == 1

    from backend.core import provider_model_fetch

    def fetch(url, *, headers, **kwargs):
        assert headers['Authorization'] == 'Bearer sk-custom-secret'
        assert url == 'https://gw.example/v1/models'
        return SimpleNamespace(status_code=200, text='', headers={},
            json=lambda: {'data': [{'id': 'relay-a'}, {'id': 'office-llm'}]})

    monkeypatch.setattr(provider_model_fetch, '_default_http_get', fetch)
    settings = ai.ModelSettings(
        connections=[ai.Connection(
            id='gw', name='Office', provider='compatible',
            base_url='https://gw.example/v1', api_key='sk-custom-secret',
        )],
        analysis=ai.Assignment(connection_id='gw', model='office-llm'),
    )
    ai.save(settings)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        public = client.get('/settings/ai-models').json()['connections'][0]
        response = client.post('/settings/ai-models/fetch-list', json={'connection': public})
    assert response.status_code == 200
    body = response.json()
    assert body['ok'] is True
    assert body['models'] == ['relay-a', 'office-llm']
    assert body['base_url_host'] == 'gw.example'
    assert 'sk-custom-secret' not in response.text
    assert 'https://gw.example' not in response.text


def test_custom_models_persist_without_exposing_keys():
    settings = ai.ModelSettings(
        connections=[ai.Connection(
            id='gw', name='Office gateway', provider='compatible',
            base_url='https://gw.example/v1', api_key='sk-custom-secret',
            custom_models=[ai.CustomModelOffer(
                id='office-llm', display_name='Office', types=['language'],
                vision=True, scenarios=['analysis', 'vision'], enabled=True,
            )],
        )],
        analysis=ai.Assignment(connection_id='gw', model='office-llm', capability='multimodal'),
    )
    public = ai.save(settings)
    dumped = json.dumps(public)
    assert 'sk-custom-secret' not in dumped
    assert public['connections'][0]['custom_models'][0]['id'] == 'office-llm'
    loaded = ai.load()
    offer = loaded.connections[0].custom_models[0]
    assert offer.id == 'office-llm'
    assert offer.vision is True
    assert offer.scenarios == ['analysis', 'vision']
    illegal = ai.CustomModelOffer(id='img', types=['image'], vision=True, scenarios=['analysis', 'cover', 'vision'])
    assert illegal.vision is False
    assert illegal.scenarios == ['cover']
    blank = ai.CustomModelOffer(id='x', types=[], scenarios=['analysis'])
    assert blank.types == ['language']
    assert blank.scenarios == ['analysis']


@pytest.mark.parametrize('provider,model,supported', [
    ('openai', 'gpt-4o-transcribe', False),
    ('compatible', 'gpt-4o-mini-transcribe', False),
    ('openai', 'whisper-1', True),
    ('compatible', 'whisper-1', True),
    ('dashscope', 'paraformer-v2', False),
])
def test_custom_asr_support_requires_timestamp_adapter(provider, model, supported):
    from backend.core.asr_model_catalog import adapter
    connection = ai.Connection(id='asr', name='ASR', provider=provider,
        base_url='https://gw.example/v1', custom_models=[ai.CustomModelOffer(id=model, types=['asr'])])
    record = registry._merge_custom_models(connection, {'models': []})['models'][0]
    assert record['asr'] is True
    assert record['asr_supported'] is bool(adapter(provider, model)) is supported


_X1_SWITCH_SCRIPT = """
const fs = require('node:fs')
const { loadTs } = require('./tests/load-ts.cjs')
const mocks = { '../../i18n': { t: text => text } }
const logic = loadTs('modelSettingsLogic.ts', mocks)
const defaults = loadTs('modelDefaults.ts', mocks)
const view = loadTs('providerCatalogView.ts', mocks)
const slots = loadTs('defaultModelSlots.ts', mocks)
let state = logic.prepareLoaded(JSON.parse(fs.readFileSync(0, 'utf8')))
const [entry, target] = process.argv.slice(1)
const connection = state.connections.find(c => c.id === target)
const models = [{ id: 'new-analysis', analysis: true, capability: 'multimodal' }, { id: 'new-cover', image: true }]
const lists = { [target]: { models, source: 'live', preview: false } }
let switched = entry === 'legacy'
  ? logic.chooseProvider(state, 'analysis', connection.provider, lists, false).settings
  : entry === 'catalog' ? view.assignAnalysis(state, connection)
  : slots.applySmartSelection(state, 'analysis', 'new-analysis', target)
switched = defaults.applyModelDefaults(switched, connection, models, false)
process.stdout.write(JSON.stringify(logic.forSave(switched)))
"""


def _x1_switch(client, entry, target):
    result = subprocess.run(
        ['node', '-e', _X1_SWITCH_SCRIPT, entry, target], cwd=Path(__file__).resolve().parents[2] / 'frontend',
        input=json.dumps(client.get('/settings/ai-models').json()), capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert client.put('/settings/ai-models', json=json.loads(result.stdout)).status_code == 200
    return client.get('/settings/ai-models').json()


@pytest.mark.parametrize('entry', ['legacy', 'catalog', 'slots'])
def test_x1_only_explicit_follow_migrates_vision(entry):
    """Explicit follow (vision=None) moves with analysis; nothing else is rewritten."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router

    config = ai.ModelSettings(
        connections=[ai.Connection(id=id_, name=id_, provider=provider, api_key='')
                     for id_, provider in [('old', 'ollama'), ('new', 'lmstudio')]],
        analysis=ai.Assignment(connection_id='old', model='old-analysis'),
        vision=None,
    )
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.put('/settings/ai-models', json=config.model_dump()).status_code == 200
        reopened = _x1_switch(client, entry, 'new')
        assert reopened['vision'] is None, 'follow must stay follow, not be frozen to a connection'
        loaded = ai.load()
        assert ai.connection_for(loaded, ai.vision_follow_binding(loaded)).id == 'new'


@pytest.mark.parametrize('entry', ['legacy', 'catalog', 'slots'])
@pytest.mark.parametrize('source', ['preset', 'user'])
def test_x1_independent_binding_survives_two_switches_and_switch_back(entry, source):
    """independent(+preset) keeps its connection through A->B->A analysis switches and reopen."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router

    config = ai.ModelSettings(
        connections=[ai.Connection(id=id_, name=id_, provider=provider, api_key='')
                     for id_, provider in [('old', 'ollama'), ('new', 'lmstudio'), ('own', 'ollama')]],
        analysis=ai.Assignment(connection_id='old', model='old-analysis'),
        vision=ai.Assignment(connection_id='own', model='own-vision', capability='multimodal', model_source=source),
        cover=ai.Assignment(connection_id='own', model='own-cover', model_source=source),
        cover_enabled=True,
    )
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.put('/settings/ai-models', json=config.model_dump()).status_code == 200
        before = client.get('/settings/ai-models').json()
        for target in ('new', 'old'):
            reopened = _x1_switch(client, entry, target)
            assert reopened['analysis']['connection_id'] == target
            for role in ('vision', 'cover'):
                assert reopened[role]['connection_id'] == 'own'
                assert reopened[role]['model_source'] == before[role]['model_source']
        loaded = ai.load()
        assert ai.connection_for(loaded, ai.vision_follow_binding(loaded)).id == 'own'
        assert ai.connection_for(loaded, loaded.cover).id == 'own'


# ---- cover follow flag (Kris round 6): explicit cover_follows_analysis ----

def _cover_doc(cover_conn, flag='absent'):
    doc = {
        'version': 1,
        'connections': [{'id': i, 'name': i, 'provider': p, 'api_key': ''}
                        for i, p in [('old', 'ollama'), ('new', 'lmstudio'), ('own', 'ollama')]],
        'analysis': {'connection_id': 'old', 'model': 'old-analysis'},
        'cover': {'connection_id': cover_conn, 'model': 'own-cover', 'model_source': 'preset'},
        'cover_enabled': True, 'cover_choice_version': 1,
    }
    if flag != 'absent':
        doc['cover_follows_analysis'] = flag
    return doc


@pytest.mark.parametrize('cover_conn,expected', [('old', True), ('own', False)])
def test_cover_follow_legacy_inference_written_back_once(cover_conn, expected):
    target = ai.path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(_cover_doc(cover_conn)), encoding='utf-8')
    original = target.read_bytes()
    loaded = ai.load()
    assert loaded.cover_follows_analysis is expected
    assert target.read_bytes() == original, 'runtime reads never rewrite the settings file'
    ai.for_editing()  # opening settings migrates once
    assert json.loads(target.read_text(encoding='utf-8'))['cover_follows_analysis'] is expected
    migrated = target.read_bytes()
    ai.for_editing()
    assert target.read_bytes() == migrated
    assert ai.public(loaded)['cover_follows_analysis'] is expected


def test_cover_follow_flag_beats_inference_and_must_match_analysis():
    assert ai.ModelSettings.model_validate(_cover_doc('old', False)).cover_follows_analysis is False
    with pytest.raises(ValidationError):
        ai.ModelSettings.model_validate(_cover_doc('own', True))


@pytest.mark.parametrize('entry', ['legacy', 'catalog', 'slots'])
@pytest.mark.parametrize('follow', [True, False])
def test_cover_follow_flag_drives_analysis_switch_round_trip(entry, follow):
    """Following cover moves to the new analysis connection; independent cover on the same connection stays."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router
    from backend.services import cover

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.put('/settings/ai-models', json=_cover_doc('old', follow)).status_code == 200
        reopened = _x1_switch(client, entry, 'new')
        assert reopened['analysis']['connection_id'] == 'new'
        assert reopened['cover_follows_analysis'] is follow
        if follow:
            assert reopened['cover']['connection_id'] == 'new'
            assert reopened['cover']['model'] == 'new-cover'
        else:
            assert reopened['cover']['connection_id'] == 'old'
            assert reopened['cover']['model'] == 'own-cover'
        # Reopen and save again: unchanged.
        assert client.put('/settings/ai-models', json=reopened).status_code == 200
        loaded = ai.load()
        assert loaded.cover_follows_analysis is follow
        assert ai.connection_for(loaded, loaded.cover).id == ('new' if follow else 'old')
        assert cover.load_config().model == ('new-cover' if follow else 'own-cover')


def test_save_rejects_image_model_in_analysis(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    settings = ai.ModelSettings(
        connections=[ai.Connection(id='c1', name='seed', provider='seed', api_key='sk-x')],
        analysis=ai.Assignment(connection_id='c1', model='doubao-seedream-5-0-flash-260915'),
        transcription=ai.Transcription(provider='whisper_local', model='base'),
    )
    with pytest.raises(ValueError, match='生图模型'):
        ai.save(settings)


def test_save_allows_same_image_model_on_cover(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    seedream = 'doubao-seedream-5-0-flash-260915'
    settings = ai.ModelSettings(
        connections=[ai.Connection(id='c1', name='seed', provider='seed', api_key='sk-x')],
        analysis=ai.Assignment(connection_id='c1', model='doubao-seed-2-1-lite-260915'),
        cover=ai.Assignment(connection_id='c1', model=seedream),
        cover_enabled=True,
        cover_follows_analysis=False,
        transcription=ai.Transcription(provider='whisper_local', model='base'),
    )
    public = ai.save(settings)
    assert public['cover']['model'] == seedream
    assert public['analysis']['model'] == 'doubao-seed-2-1-lite-260915'


@pytest.mark.parametrize('nested', [True, False], ids=['desktop', 'flat'])
def test_other_saved_legacy_cloud_account_can_be_selected_without_reentering_keys(tmp_path, monkeypatch, nested):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router
    from backend.core import llm_manager
    from backend.services import cover
    from backend.services.studio import vision_settings, analysis_preferences

    active, other = ('dashscope', 'deepseek') if nested else ('deepseek', 'dashscope')
    active_model = 'qwen-plus' if nested else 'deepseek-flash'
    base = 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1'
    keys = {'dashscope': 'test-ali-only', 'deepseek': 'test-deep-only'}
    legacy = {'api': {'api_provider': active, 'api_model': active_model, 'api_keys': keys}} if nested else {
        'llm_provider': active, 'model_name': active_model, 'dashscope_base_url': base,
        **{f'{p}_api_key': key for p, key in keys.items()},
    }
    legacy_path = tmp_path / 'settings.json'
    original = json.dumps(legacy)
    legacy_path.write_text(original, encoding='utf-8')
    monkeypatch.setenv('API_KIMI_API_KEY', 'test-env-only')
    monkeypatch.setattr(llm_manager.LLMManager, '_sync_config_if_needed', lambda self: None)
    monkeypatch.setattr(llm_manager.LLMManager, '_initialize_provider', lambda self: None)
    manager = llm_manager.LLMManager(legacy_path)
    monkeypatch.setattr(llm_manager, 'get_llm_manager', lambda: manager)
    monkeypatch.setattr(vision_settings, 'effective', lambda: {})
    monkeypatch.setattr(cover, 'load_config', lambda: cover.CoverConfig())
    monkeypatch.setattr(analysis_preferences, 'load', lambda: analysis_preferences.AnalysisPreferences())
    monkeypatch.setattr(ai, 'migrate_legacy', legacy_migrate)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get('/settings/ai-models')
        response.raise_for_status()
        doc = response.json()
        rows = {row['provider']: row for row in doc['connections']}
        assert set(rows) == set(keys)
        assert all(row['has_key'] and row['validation_status'] == 'unchecked' for row in rows.values())
        assert not any(key in response.text for key in keys.values())
        assert doc['analysis']['connection_id'] == rows[active]['id']
        assert not ai.path().exists()
        doc['analysis'] = {'connection_id': rows[other]['id'], 'model': 'deepseek-flash' if nested else 'qwen-plus',
                           'capability': 'text', 'model_source': 'user'}
        client.put('/settings/ai-models', json=doc).raise_for_status()
        assert client.get('/settings/ai-models').json()['analysis'] == doc['analysis']
        persisted = ai.load()
        endpoint = ai.chat_endpoint(ai.connection_for(persisted, persisted.analysis), persisted.analysis.model)
        assert endpoint['api_key'] == keys[other]
        assert endpoint['base_url'] == ('https://api.deepseek.com/v1' if nested else base)
        assert legacy_path.read_text(encoding='utf-8') == original


def test_two_open_windows_preserve_disjoint_edits_and_reject_same_purpose():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router

    app = FastAPI()
    app.include_router(router)
    ai.save(example())
    url = '/settings/ai-models'
    with TestClient(app) as client:
        a, b, c = (client.get(url).json() for _ in range(3))
        a['analysis']['model'] = 'chosen-by-a'
        b['chunk_size'] = 6000
        c['analysis']['model'] = 'chosen-by-c'
        assert client.put(url, json={**a, 'edited_fields': ['analysis']}).status_code == 200
        assert client.put(url, json={**b, 'edited_fields': ['chunk_size']}).status_code == 200
        assert client.put(url, json={**c, 'edited_fields': ['analysis']}).status_code == 409
        reopened = client.get(url).json()
        assert (reopened['analysis']['model'], reopened['chunk_size']) == ('chosen-by-a', 6000)
        assert reopened['revision'] == a['revision'] + 2
        assert all('api_key' not in row for row in reopened['connections'])
    loaded = ai.load()
    assert ai.require_analysis(loaded).model == 'chosen-by-a'
    assert [row.api_key for row in loaded.connections] == [row.api_key for row in example().connections]


def test_retired_transcription_only_blocks_transcription_and_supports_repair():
    from backend.services.studio import readiness

    data = example()
    ai.save(data)
    raw = json.loads(ai.path().read_text())
    raw['transcription'] = {'provider': 'cloud', 'connection_id': 'one', 'model': 'retired-asr'}
    ai.path().write_text(json.dumps(raw))
    before = ai.path().read_bytes()
    reopened = ai.public(ai.for_editing())
    assert reopened['transcription_needs_repair'] and reopened['saved']
    assert len(reopened['connections']) == 2 and ai.path().read_bytes() == before
    assert readiness._analysis(ai.load())['ok']
    assert readiness._transcription(ai.load())['repair'] == 'settings_transcription'
    reopened['chunk_size'] = 6000
    after = ai.save(ai.ModelSettings.model_validate(reopened), edited_fields={'chunk_size'})
    assert after['transcription_needs_repair']
    after['transcription']['model'] = 'whisper-1'
    after = ai.save(ai.ModelSettings.model_validate(after), edited_fields={'transcription'})
    assert not after['transcription_needs_repair']
    assert ai.load().transcription.model == 'whisper-1' and readiness._transcription(ai.load())['ok']
    assert ai.require_analysis(ai.load()) == data.analysis
    assert [row.api_key for row in ai.load().connections] == [row.api_key for row in data.connections]


def test_account_only_scoped_failure_and_hidden_fixed_model_in_production_request(tmp_path, monkeypatch):
    import httpx
    from openai import OpenAI
    from backend.core.llm_manager import LLMManager
    from backend.core.llm_providers import LLMProviderFactory
    from backend.services.studio import readiness
    from backend.tests.test_chunk_retry_budget import _response

    account = ai.Connection(id='bailian', name='Bailian', provider='dashscope', api_key='fixture',
                            failed_model_checks=[{'purpose': 'analysis', 'model': 'fixture-alpha'}])
    saved = ai.save(ai.ModelSettings(connections=[account]))
    assert saved['analysis'] is None and saved['connections'][0]['has_key']
    assert readiness._analysis(ai.load())['code'] == 'no_model'
    with pytest.raises(ValueError):
        ai.require_analysis(ai.load())
    saved['analysis'] = {'connection_id': account.id, 'model': 'fixture-alpha', 'model_source': 'user'}
    ai.save(ai.ModelSettings.model_validate(saved))
    assert readiness._analysis(ai.load())['code'] == 'model_validation_failed'
    with pytest.raises(ValueError):
        ai.require_analysis(ai.load())
    working = ai.load()
    working.analysis.model = 'qwen4-max'
    working.connections[0].enabled_model_ids = []
    ai.save(working)
    assert readiness._analysis(ai.load())['ok']
    hits = []
    create_provider = LLMProviderFactory.create_provider

    def receive(request):
        hits.append((request.url.host, json.loads(request.content)['model']))
        return _response(request, 'ok')

    def offline_provider(*args, **kwargs):
        provider = create_provider(*args, **kwargs)
        provider.client = OpenAI(api_key='fixture', base_url=kwargs['base_url'],
                                 http_client=httpx.Client(transport=httpx.MockTransport(receive)))
        return provider

    monkeypatch.setattr(LLMProviderFactory, 'create_provider', offline_provider)
    monkeypatch.setattr(LLMManager, '_sync_config_if_needed', lambda self: None)
    manager = LLMManager(tmp_path / 'settings.json')
    assert manager.settings['model_source'] == 'user'
    assert manager.call_with_retry('test', max_retries=1) == 'ok'
    assert hits == [('dashscope.aliyuncs.com', 'qwen4-max')]


def test_windows_upgrade_first_refresh_timeout_reclassifies_only_the_saved_account(tmp_path, monkeypatch):
    profile = tmp_path / 'AppData' / 'Roaming' / 'AutoClip'
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(profile))
    account = ai.Connection(id='legacy-analysis', name='Bailian', provider='dashscope', api_key='fixture-bailian')
    other = account.model_copy(update={'id': 'other', 'api_key': 'fixture-other'})
    ai.save(ai.ModelSettings(connections=[account, other], analysis=ai.Assignment(connection_id=account.id, model='qwen4-max')))
    registry._update(registry._scope(account), {'source': 'live', 'updated_at': 1, 'models': [
        {'id': 'qwen4-max', 'analysis': True, 'capability': None, 'kind': 'language'},
        {'id': 'qwen-image-2.1-pro', 'image': False, 'kind': 'other'},
        {'id': 'private-text', 'capability': 'text', 'capability_source': 'provider', 'analysis': True},
    ]})
    registry._update(registry._scope(other), {'models': [{'id': 'other-account-only'}]})
    async def timeout(url, **kwargs):
        assert kwargs['headers']['Authorization'] == 'Bearer fixture-bailian'
        raise TimeoutError('fixture deadline')
    async def offline():
        pass
    monkeypatch.setattr(registry, '_ensure_metadata', offline)
    monkeypatch.setattr(registry.model_catalog, '_http_get_json', timeout)
    listed = asyncio.run(registry.discover(ai.load().connections[0]))
    by_id = {row['id']: row for row in listed['models']}
    assert listed['source'] == 'cache' and listed['warning'] and listed['updated_at'] == 1
    assert by_id['qwen4-max']['capability'] == 'multimodal'
    assert by_id['qwen-image-2.1-pro']['kind'] == 'image'
    assert by_id['private-text']['capability_source'] == 'provider'
    assert 'other-account-only' not in by_id


def test_unknown_ids_require_a_declaration_and_empty_metadata_defers_to_evidence():
    from backend.core.model_recovery import pick_available_vision_model
    from backend.core.provider_model_fetch import _page_models
    c = ai.Connection(id='bailian', name='Bailian', provider='dashscope', api_key='fixture')
    raw = [{'id': name} for name in ('custom-vision-widget', 'fixture-max-new', 'qwen-image-9.9-ultra')]
    raw += [{'id': 'qwen-image-2.1-pro', 'output_modalities': [], 'supported_endpoint_types': ['multimodal-generation']},
            {'id': 'qwen4-max', 'input_modalities': [], 'architecture': {'input_modalities': ['text']}},
            {'id': 'fixture-text-only', 'architecture': {'input_modalities': ['text']}}]
    rows = {row['id']: row for row in registry._records(c, raw, {})}
    for row in raw[:3]:
        assert rows[row['id']]['kind'] == 'other'
        assert rows[row['id']]['capability'] is None
    assert rows['qwen-image-2.1-pro']['image']
    assert rows['qwen4-max']['capability'] == 'multimodal'
    assert rows['fixture-text-only']['capability'] == 'text'
    assert pick_available_vision_model('dashscope', ['qwen4-max']) == 'qwen4-max'
    ids, caps = _page_models({'data': raw}, 'openai-completions', 'dashscope')
    assert pick_available_vision_model('dashscope', ids, capabilities=caps) == 'qwen4-max'
    assert pick_available_vision_model('dashscope', ['fixture-text-only'], capabilities=caps) is None
