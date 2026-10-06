"""Import readiness reads saved settings and local runtimes. It must not call a model."""
import json

import pytest
from backend.services.ai_model_settings import Assignment, Connection, ModelSettings, Transcription


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    binary = tmp_path / 'ffmpeg'
    binary.write_bytes(b'ffmpeg')
    monkeypatch.setattr('backend.utils.ffmpeg_utils.get_ffmpeg_path', lambda: str(binary))
    monkeypatch.setattr('backend.services.whisper_runtime.get_status', lambda: {'status': 'installed'})
    monkeypatch.setattr('backend.services.sensevoice_runtime.status', lambda: {'status': 'not_installed', 'message': ''})
    return tmp_path


def document(**overrides):
    connection = Connection(id='ai', name='OpenAI', provider='openai', api_key='sk-test-key')
    values = dict(
        connections=[connection],
        analysis=Assignment(connection_id='ai', model='gpt-4o', capability='text'),
        transcription=Transcription(),
        analysis_mode='auto',
    )
    values.update(overrides)
    return ModelSettings(**values)


def report_for(monkeypatch, settings):
    from backend.services import ai_model_settings as ai
    from backend.services.studio import readiness
    monkeypatch.setattr(ai, 'for_editing', lambda: settings)
    return readiness.report()


def test_saved_document_is_ready_without_a_provider_call(monkeypatch):
    from backend.services import ai_model_settings as ai
    from backend.services.studio import readiness
    connection = Connection(id='local', name='Ollama', provider='ollama')
    settings = document(
        connections=[connection],
        analysis=Assignment(connection_id='local', model='qwen2.5:7b', capability='text'),
    )
    ai.path().write_text(settings.model_dump_json(), encoding='utf-8')
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: (_ for _ in ()).throw(AssertionError('legacy migration')))
    monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('network')))
    result = readiness.report()
    assert result['analysis_mode'] == 'auto'
    assert result['ready'] is True
    assert result['checks']['analysis'] == {'ok': True, 'code': 'configured', 'repair': 'none'}
    assert result['checks']['transcription'] == {'ok': True, 'code': 'whisper_installed', 'repair': 'none'}
    assert result['checks']['visual'] == {'ok': True, 'code': 'optional', 'repair': 'none'}
    assert result['checks']['ffmpeg'] == {'ok': True, 'code': 'available', 'repair': 'none'}
    assert 'sk-test-key' not in json.dumps(result)


def test_nothing_saved_asks_for_an_ai_connection(monkeypatch):
    from backend.services import ai_model_settings as ai
    from backend.services.studio import readiness
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ModelSettings())
    result = readiness.report()
    assert result['checks']['analysis'] == {'ok': False, 'code': 'not_configured', 'repair': 'settings_ai'}


def test_invalid_document_is_repairable_in_ai_settings(monkeypatch):
    from backend.services import ai_model_settings as ai
    from backend.services.studio import readiness
    ai.path().write_text('{', encoding='utf-8')
    result = readiness.report()
    assert result['checks']['analysis'] == {'ok': False, 'code': 'settings_invalid', 'repair': 'settings_ai'}


def test_cloud_connection_without_a_key_is_not_ready(monkeypatch):
    analysis = Connection(id='ai', name='OpenAI', provider='openai', api_key='sk-test-key')
    speech = Connection(id='asr', name='OpenAI', provider='openai', api_key='')
    result = report_for(monkeypatch, document(
        connections=[analysis, speech],
        transcription=Transcription(provider='cloud', model='whisper-1', connection_id='asr'),
    ))
    assert result['checks']['analysis']['ok'] is True
    assert result['checks']['transcription'] == {'ok': False, 'code': 'cloud_not_configured', 'repair': 'settings_transcription'}


def test_configured_cloud_asr_skips_local_whisper(monkeypatch):
    monkeypatch.setattr('backend.services.whisper_runtime.get_status', lambda: (_ for _ in ()).throw(AssertionError('whisper')))
    analysis = Connection(id='ai', name='OpenAI', provider='openai', api_key='sk-test-key')
    speech = Connection(id='asr', name='OpenAI', provider='openai', api_key='sk-asr')
    result = report_for(monkeypatch, document(
        connections=[analysis, speech],
        transcription=Transcription(provider='cloud', model='whisper-1', connection_id='asr'),
    ))
    assert result['checks']['transcription'] == {'ok': True, 'code': 'cloud_configured', 'repair': 'none'}


def test_sensevoice_ready_skips_whisper_install(monkeypatch):
    monkeypatch.setattr('backend.services.whisper_runtime.get_status', lambda: (_ for _ in ()).throw(AssertionError('whisper')))
    monkeypatch.setattr('backend.services.sensevoice_runtime.status', lambda: {'status': 'ready', 'message': ''})
    result = report_for(monkeypatch, document(
        transcription=Transcription(provider='sensevoice_local', model='SenseVoiceSmall'),
    ))
    assert result['checks']['transcription'] == {'ok': True, 'code': 'sensevoice_ready', 'repair': 'none'}


def test_missing_whisper_offers_install(monkeypatch):
    monkeypatch.setattr('backend.services.whisper_runtime.get_status', lambda: {'status': 'not_installed'})
    result = report_for(monkeypatch, document())
    assert result['checks']['transcription'] == {'ok': False, 'code': 'whisper_not_installed', 'repair': 'install_whisper'}
    monkeypatch.setattr('backend.services.whisper_runtime.get_status', lambda: {'status': 'installing'})
    assert report_for(monkeypatch, document())['checks']['transcription'] == {'ok': False, 'code': 'whisper_installing', 'repair': 'none'}


def test_visual_mode_requires_a_multimodal_model_and_auto_does_not(monkeypatch):
    text = document(analysis_mode='visual')
    blocked = report_for(monkeypatch, text)
    assert blocked['checks']['visual'] == {'ok': False, 'code': 'not_configured', 'repair': 'settings_vision'}
    assert blocked['ready'] is False
    allowed = report_for(monkeypatch, document(
        analysis=Assignment(connection_id='ai', model='gpt-4o', capability='multimodal'),
        analysis_mode='visual',
    ))
    assert allowed['checks']['visual'] == {'ok': True, 'code': 'configured', 'repair': 'none'}
    auto = report_for(monkeypatch, document(analysis_mode='auto'))
    assert auto['checks']['visual'] == {'ok': True, 'code': 'optional', 'repair': 'none'}
    subtitles = report_for(monkeypatch, document(analysis_mode='subtitle', allow_visual_screening=False))
    assert subtitles['checks']['visual'] == {'ok': True, 'code': 'not_required', 'repair': 'none'}


def test_missing_ffmpeg_has_no_repair_action(monkeypatch):
    monkeypatch.setattr('backend.utils.ffmpeg_utils.get_ffmpeg_path', lambda: 'ffmpeg')
    result = report_for(monkeypatch, document())
    assert result['checks']['ffmpeg'] == {'ok': False, 'code': 'missing', 'repair': 'none'}


def test_http_readiness_is_registered_before_project_routes(isolated, monkeypatch):
    from backend.services import ai_model_settings as ai
    ai.path().write_text(document().model_dump_json(), encoding='utf-8')
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.studio import router
    paths = [getattr(route, 'path', '') for route in router.routes]
    assert paths.index('/readiness') < paths.index('/{project_id}')
    app = FastAPI()
    app.include_router(router, prefix='/api/v1/studio')
    response = TestClient(app).get('/api/v1/studio/readiness')
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {'analysis_mode', 'ready', 'checks'}
    assert set(body['checks']) == {'analysis', 'transcription', 'visual', 'ffmpeg'}
    for check in body['checks'].values():
        assert set(check) == {'ok', 'code', 'repair'}
        assert check['repair'] in {'settings_ai', 'install_whisper', 'settings_transcription', 'settings_vision', 'none'}
    assert 'sk-test-key' not in response.text
