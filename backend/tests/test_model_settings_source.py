"""source=preset/user inference, legacy document migration, and catalog freeze."""
import json

from backend.services import ai_model_settings as ai
from backend.services import model_settings_source as source


def test_filled_legacy_model_is_user_and_empty_official_url_is_preset():
    connection = ai.Connection(id='one', name='百炼', provider='dashscope')
    assignment = ai.Assignment(connection_id='one', model='qwen-plus')
    assert connection.base_url_source == 'preset'
    assert assignment.model_source == 'user'
    custom = ai.Connection(id='two', name='custom', provider='compatible', base_url='https://gw.example/v1')
    assert custom.base_url_source == 'user'
    official = ai.Connection(
        id='three', name='OpenAI', provider='openai', base_url='https://api.openai.com/v1')
    assert official.base_url_source == 'preset'
    relay = ai.Connection(
        id='four', name='relay', provider='dashscope', base_url='https://proxy.example.com/v1')
    assert relay.base_url_source == 'user'


def test_legacy_document_without_source_fields_keeps_filled_models_as_user(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    raw = {
        'version': 1,
        'connections': [
            {'id': 'one', 'name': 'Analysis', 'provider': 'dashscope', 'api_key': 'sk-legacy-secret'},
        ],
        'analysis': {'connection_id': 'one', 'model': 'qwen-plus', 'capability': 'auto'},
        'cover_enabled': False,
    }
    ai.path().parent.mkdir(parents=True, exist_ok=True)
    ai.path().write_text(json.dumps(raw), encoding='utf-8')
    loaded = ai.load()
    assert loaded.analysis.model == 'qwen-plus'
    assert loaded.analysis.model_source == 'user'
    assert loaded.connections[0].base_url_source == 'preset'
    assert loaded.connections[0].api_key == 'sk-legacy-secret'
    assert loaded.acked_catalog_version == source.current_catalog_version()
    dumped = json.loads(ai.path().read_text(encoding='utf-8'))
    assert 'base_url_source' not in dumped['connections'][0]
    assert 'model_source' not in dumped['analysis']


def test_unmigratable_purpose_in_saved_file_resets_to_recommended_and_keeps_key(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    raw = {
        'version': 1,
        'connections': [
            {'id': 'one', 'name': 'Analysis', 'provider': 'openai', 'api_key': 'sk-keep-me',
             'base_url': 'https://api.openai.com/v1'},
        ],
        'analysis': {'connection_id': 'one', 'model': 'm' * 201, 'capability': 'auto'},
        'cover_enabled': False,
    }
    ai.path().parent.mkdir(parents=True, exist_ok=True)
    ai.path().write_text(json.dumps(raw), encoding='utf-8')
    loaded = ai.load()
    assert loaded.connections[0].api_key == 'sk-keep-me'
    assert loaded.analysis.model == source.recommended_model('openai', 'analysis')
    assert loaded.analysis.model_source == 'preset'
    assert source.NOTICE_PURPOSE_RESET in loaded._migration_warnings
    public = ai.public(loaded)
    assert 'sk-keep-me' not in json.dumps(public)
    assert 'm' * 20 not in json.dumps(public)
    assert source.NOTICE_PURPOSE_RESET in public['migration_warnings']


def test_save_freezes_preset_url_and_later_catalog_updates_do_not_rewrite(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    settings = ai.ModelSettings(
        connections=[ai.Connection(id='one', name='百炼', provider='dashscope', api_key='sk-live-secret')],
        analysis=ai.Assignment(connection_id='one', model='qwen-plus', model_source='user'),
    )
    ai.save(settings)
    saved = ai.load()
    frozen_url = saved.connections[0].base_url
    assert frozen_url
    assert saved.connections[0].base_url_source == 'preset'
    assert saved.analysis.model == 'qwen-plus'
    assert saved.analysis.model_source == 'user'
    stamped = saved.connections[0].preset_version
    assert stamped == source.current_catalog_version()

    monkeypatch.setattr(source, 'current_catalog_version', lambda: stamped + 1)
    monkeypatch.setattr(source, 'preset_base_url', lambda provider: 'https://new-official.example/v1')
    monkeypatch.setattr(ai, 'current_catalog_version', source.current_catalog_version)
    monkeypatch.setattr(ai, 'preset_update_available', source.preset_update_available)
    again = ai.load()
    assert again.connections[0].base_url == frozen_url
    assert again.analysis.model == 'qwen-plus'
    public = ai.public(again)
    assert public['preset_update_available'] is True
    assert source.NOTICE_PRESET_UPDATED in public['migration_warnings']
    assert 'new-official.example' not in json.dumps(public)
    assert 'sk-live-secret' not in json.dumps(public)


def test_new_connection_uses_current_catalog_url_and_notice_acks_on_save(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    raw = {
        'version': 1,
        'connections': [
            {'id': 'one', 'name': 'Analysis', 'provider': 'openai', 'api_key': 'sk-keep-me',
             'base_url': 'https://api.openai.com/v1'},
        ],
        'analysis': {'connection_id': 'one', 'model': 'm' * 201, 'capability': 'auto'},
        'cover_enabled': False,
    }
    ai.path().parent.mkdir(parents=True, exist_ok=True)
    ai.path().write_text(json.dumps(raw), encoding='utf-8')
    loaded = ai.for_editing()
    assert source.NOTICE_PURPOSE_RESET in loaded._migration_warnings
    saved = ai.save(loaded)
    assert source.NOTICE_PURPOSE_RESET not in (saved.get('migration_warnings') or [])
    persisted = json.loads(ai.path().read_text(encoding='utf-8'))
    assert persisted['analysis']['model_source'] == 'preset'
    assert persisted['connections'][0]['api_key'] == 'sk-keep-me'
    assert source.NOTICE_PURPOSE_RESET in persisted['seen_notices']


def test_annotate_legacy_empty_model_slot_is_preset_not_a_reset_notice():
    data, warnings = source.annotate_document({
        'connections': [{'id': 'one', 'name': 'n', 'provider': 'dashscope', 'api_key': 'k'}],
        'analysis': {'connection_id': 'one', 'model': 'qwen-plus'},
    })
    assert data['analysis']['model_source'] == 'user'
    assert data['connections'][0]['base_url_source'] == 'preset'
    assert source.NOTICE_PURPOSE_RESET not in warnings


def test_migration_never_switches_binding_to_another_provider(tmp_path, monkeypatch):
    """A missing connection is needs-repair. Do not reuse connections[0] (that changes provider)."""
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    raw = {
        'version': 1,
        'connections': [
            {'id': 'openai-1', 'name': 'OpenAI', 'provider': 'openai', 'api_key': 'sk-openai-keep',
             'base_url': 'https://api.openai.com/v1'},
            {'id': 'dashscope-1', 'name': '百炼', 'provider': 'dashscope', 'api_key': 'sk-dashscope-keep'},
        ],
        'analysis': {'connection_id': 'gone', 'model': 'gpt-4o-mini', 'capability': 'auto'},
        'cover_enabled': False,
    }
    data, warnings = source.annotate_document(raw)
    assert data['analysis'] is None
    assert [item['provider'] for item in data['connections']] == ['openai', 'dashscope']
    assert [item['id'] for item in data['connections']] == ['openai-1', 'dashscope-1']
    assert 'analysis_configuration_invalid' in warnings
    assert source.NOTICE_PURPOSE_RESET not in warnings

    ai.path().parent.mkdir(parents=True, exist_ok=True)
    ai.path().write_text(json.dumps(raw), encoding='utf-8')
    loaded = ai.load()
    assert loaded.analysis is None
    assert [item.provider for item in loaded.connections] == ['openai', 'dashscope']
    assert 'analysis_configuration_invalid' in loaded._migration_warnings
    public = ai.public(loaded)
    assert public['analysis'] is None
    assert [item['provider'] for item in public['connections']] == ['openai', 'dashscope']
    assert 'sk-openai-keep' not in json.dumps(public)


def test_unmigratable_model_resets_on_the_same_provider():
    data, warnings = source.annotate_document({
        'connections': [
            {'id': 'gemini-1', 'name': 'Gemini', 'provider': 'gemini', 'api_key': 'AIza-keep'},
            {'id': 'openai-1', 'name': 'OpenAI', 'provider': 'openai', 'api_key': 'sk-other',
             'base_url': 'https://api.openai.com/v1'},
        ],
        'analysis': {'connection_id': 'gemini-1', 'model': 'm' * 201, 'capability': 'auto'},
    })
    assert data['analysis']['connection_id'] == 'gemini-1'
    assert data['analysis']['model'] == source.recommended_model('gemini', 'analysis')
    assert data['analysis']['model_source'] == 'preset'
    assert next(item['provider'] for item in data['connections'] if item['id'] == 'gemini-1') == 'gemini'
    assert source.NOTICE_PURPOSE_RESET in warnings
