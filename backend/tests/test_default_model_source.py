"""U2: persist model_source on purpose slots; old files without the field are user."""
import json

import pytest

from backend.services import ai_model_settings as ai

pytestmark = pytest.mark.stdlib_only


def example(source='preset'):
    return ai.ModelSettings(
        connections=[
            ai.Connection(id='one', name='Analysis', provider='openai', base_url='https://one.example/v1', api_key='sk-first-secret'),
        ],
        analysis=ai.Assignment(connection_id='one', model='gpt-4o-mini', model_source=source),
        transcription=ai.Transcription(provider='whisper_local', model='base', model_source='user'),
        cover_enabled=False,
    )


def test_old_assignment_without_source_is_user(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    path = tmp_path / 'ai-model-settings.json'
    path.write_text(json.dumps({
        'version': 1,
        'connections': [{'id': 'one', 'name': 'Analysis', 'provider': 'openai', 'base_url': 'https://one.example/v1', 'api_key': 'sk-old'}],
        'analysis': {'connection_id': 'one', 'model': 'gpt-4o-mini'},
        'cover_enabled': False,
    }), encoding='utf-8')
    loaded = ai.load()
    assert loaded.analysis.model_source == 'user'
    assert loaded.analysis.model == 'gpt-4o-mini'


def test_preset_source_round_trips_and_cover_stays_optional(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    dumped = example('preset').model_dump()
    assert dumped['analysis']['model_source'] == 'preset'
    assert dumped['cover_enabled'] is False
    assert dumped['analysis']['model'] == 'gpt-4o-mini'
    path = tmp_path / 'ai-model-settings.json'
    path.write_text(json.dumps(dumped), encoding='utf-8')
    loaded = ai.load()
    assert loaded.analysis.model_source == 'preset'
    assert loaded.cover_enabled is False


def test_public_payload_does_not_include_api_key():
    public = ai.public(example('user'))
    dumped = json.dumps(public)
    assert 'sk-first-secret' not in dumped
    assert public['analysis']['model_source'] == 'user'
    assert public['connections'][0]['has_key'] is True
