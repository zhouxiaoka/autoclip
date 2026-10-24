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
    from backend.services import whisper_model_manager
    monkeypatch.setattr(whisper_model_manager, '_model_manager', whisper_model_manager.WhisperModelManager())
    monkeypatch.setattr('backend.services.whisper_runtime.get_models_dir', lambda: tmp_path / 'whisper-models')
    model_snapshot(tmp_path, 'base')
    return tmp_path


def model_snapshot(root, name):
    snapshot = root / 'whisper-models' / 'hub' / f'models--Systran--faster-whisper-{name}' / 'snapshots' / 'complete'
    snapshot.mkdir(parents=True, exist_ok=True)
    for file in ('model.bin', 'config.json', 'tokenizer.json', 'vocabulary.json'):
        (snapshot / file).write_bytes(b'fixture')
    return snapshot


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
    # the report's analysis mode is the one planning reads; with a saved document that is its own mode.
    from backend.services.studio import analysis_preferences
    monkeypatch.setattr(analysis_preferences, 'load', lambda: analysis_preferences.AnalysisPreferences(analysis_mode=settings.analysis_mode))
    return readiness.report()


@pytest.mark.own_whisper_status  # simulates its own Whisper runtime / model state
def test_saved_document_is_ready_without_a_provider_call(monkeypatch):
    from backend.services import ai_model_settings as ai
    from backend.services.studio import readiness
    connection = Connection(id='local', name='Ollama', provider='ollama')
    settings = document(
        connections=[connection],
        analysis=Assignment(connection_id='local', model='qwen2.5:7b', capability='auto'),
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


@pytest.mark.own_whisper_status  # simulates its own Whisper runtime / model state
def test_runtime_without_the_selected_model_is_not_ready(monkeypatch, isolated):
    # RC156 Win QA #5: an installed runtime alone cannot transcribe.
    from backend.services.whisper_model_manager import get_model_manager
    small = document(transcription=Transcription(model='small'))
    assert report_for(monkeypatch, small)['checks']['transcription'] == {
        'ok': False, 'code': 'whisper_model_missing', 'repair': 'install_whisper', 'model': 'small'}
    manager = get_model_manager()
    manager._download_state['small'] = {'status': 'downloading', 'progress': 0, 'error': None}
    assert report_for(monkeypatch, small)['checks']['transcription'] == {
        'ok': False, 'code': 'whisper_model_downloading', 'repair': 'none', 'model': 'small'}
    manager._download_state['small'] = {'status': 'error', 'progress': 0, 'error': 'timeout'}
    assert report_for(monkeypatch, small)['checks']['transcription'] == {
        'ok': False, 'code': 'whisper_model_failed', 'repair': 'install_whisper', 'model': 'small'}
    model_snapshot(isolated, 'small')
    assert report_for(monkeypatch, small)['checks']['transcription'] == {'ok': True, 'code': 'whisper_installed', 'repair': 'none'}


@pytest.mark.own_whisper_status  # simulates its own Whisper runtime / model state
def test_large_alias_uses_the_large_v3_model(monkeypatch, isolated):
    large = document(transcription=Transcription(model='large'))
    assert report_for(monkeypatch, large)['checks']['transcription']['model'] == 'large-v3'
    model_snapshot(isolated, 'large-v3')
    assert report_for(monkeypatch, large)['checks']['transcription']['ok'] is True


def test_visual_mode_requires_a_multimodal_model_and_auto_does_not(monkeypatch):
    text = document(analysis_mode='visual')
    blocked = report_for(monkeypatch, text)
    assert blocked['checks']['visual'] == {'ok': False, 'code': 'vision_unsupported', 'repair': 'settings_vision'}
    assert blocked['ready'] is False
    allowed = report_for(monkeypatch, document(
        analysis=Assignment(connection_id='ai', model='gpt-4o', capability='multimodal'),
        analysis_mode='visual',
    ))
    assert allowed['checks']['visual'] == {'ok': True, 'code': 'configured', 'repair': 'none'}
    auto_text = report_for(monkeypatch, document(analysis_mode='auto'))
    # D7: auto + known text must stay optional so S5 can fall back to subtitles
    assert auto_text['checks']['visual'] == {'ok': True, 'code': 'optional', 'repair': 'none'}
    assert auto_text['ready'] is True
    auto_unresolved = report_for(monkeypatch, document(
        analysis=Assignment(connection_id='ai', model='o3-mini', capability='auto'),
        analysis_mode='auto',
    ))
    assert auto_unresolved['checks']['visual'] == {'ok': True, 'code': 'optional', 'repair': 'none'}
    subtitles = report_for(monkeypatch, document(analysis_mode='subtitle', allow_visual_screening=False))
    assert subtitles['checks']['visual'] == {'ok': True, 'code': 'not_required', 'repair': 'none'}


def test_missing_ffmpeg_has_no_repair_action(monkeypatch):
    monkeypatch.setattr('backend.utils.ffmpeg_utils.get_ffmpeg_path', lambda: 'ffmpeg')
    result = report_for(monkeypatch, document())
    assert result['checks']['ffmpeg'] == {'ok': False, 'code': 'missing', 'repair': 'none'}


@pytest.mark.own_whisper_status  # simulates its own Whisper runtime / model state
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


# 1.5.7 Windows acceptance (b4) S3: capability=auto must resolve like the pipeline.
@pytest.mark.parametrize('model, capability, ok', [
    ('gpt-6.1-sol', 'auto', True),
    ('gpt-4o-mini', 'auto', True),
    ('o3-mini', 'auto', False),
    ('gpt-6.1-sol', 'text', False),
    ('o3-mini', 'multimodal', True),
])
def test_visual_check_uses_the_pipeline_capability(monkeypatch, model, capability, ok):
    from backend.services import ai_model_settings as ai
    gateway = Connection(id='ai', name='88API', provider='api88', api_key='sk-test-key', base_url='https://api.88api.ai/v1')
    settings = document(connections=[gateway], analysis_mode='visual',
                        analysis=Assignment(connection_id='ai', model=model, capability=capability))
    visual = report_for(monkeypatch, settings)['checks']['visual']
    assert visual['ok'] is ok
    assert visual['code'] == ('configured' if ok else 'vision_unsupported')
    # The pipeline gives the same answer: a vision endpoint exists exactly when readiness is ok.
    assert (ai.vision_endpoint(settings) is not None) is ok
    assert ai.sees_images(settings, settings.analysis) is ok


def test_auto_capability_resolution(monkeypatch):
    from backend.services import ai_model_settings as ai
    settings = document()
    pick = lambda model, cap='auto': ai.capability(settings, Assignment(connection_id='ai', model=model, capability=cap))
    assert pick('gpt-6.1-sol') == 'multimodal'
    assert pick('gpt-4o-mini') == 'multimodal'
    assert pick('o3-mini') is None  # not confirmed to see images; never guessed as text
    assert pick('gpt-6.1-sol', 'text') == 'text'


def test_catalog_image_flag_cannot_make_a_text_only_model_ready_for_visual(monkeypatch):
    """models.dev lists deepseek-flash as image input. Visual mode must still say it cannot see images."""
    from backend.core import model_registry as registry
    from backend.services import ai_model_settings as ai
    connection = Connection(id='ai', name='DeepSeek', provider='deepseek', api_key='sk-test-key', base_url='https://api.deepseek.com')
    registry._update('metadata', {'updated_at': 10**10, 'providers': {
        'deepseek': {'deepseek-flash': {'capability': 'multimodal', 'source': 'https://models.dev/api.json'}},
    }})
    registry._update(registry._scope(connection), {
        'models': [{'id': 'deepseek-flash', 'capability': 'multimodal', 'capability_source': 'provider'}],
        'source': 'live',
    })
    settings = document(
        connections=[connection], analysis_mode='visual',
        analysis=Assignment(connection_id='ai', model='deepseek-flash', capability='auto'),
    )
    assert registry.lookup_capability(connection, 'deepseek-flash') == 'multimodal'
    assert ai.capability(settings, settings.analysis) == 'text'
    assert ai.vision_endpoint(settings) is None
    visual = report_for(monkeypatch, settings)['checks']['visual']
    assert visual == {'ok': False, 'code': 'vision_unsupported', 'repair': 'settings_vision'}
    # An explicit multimodal flag on this name does not override the text-only classification.
    forced = document(
        connections=[connection], analysis_mode='visual',
        analysis=Assignment(connection_id='ai', model='deepseek-flash', capability='multimodal'),
    )
    assert report_for(monkeypatch, forced)['checks']['visual']['code'] == 'vision_unsupported'


def test_generic_compatible_gateway_still_needs_an_explicit_choice(monkeypatch):
    gateway = Connection(id='ai', name='Gateway', provider='compatible', api_key='k', base_url='https://gateway.example/v1')
    settings = document(connections=[gateway], analysis_mode='visual',
                        analysis=Assignment(connection_id='ai', model='gpt-6.1-sol', capability='auto'))
    assert report_for(monkeypatch, settings)['checks']['visual']['code'] == 'vision_unsupported'


def test_require_transcription_raises_before_caller_spends(monkeypatch):
    from backend.pipeline.failures import PipelineFailure
    from backend.services.studio import readiness
    monkeypatch.setattr(readiness, 'transcription_check', lambda: {'ok': False, 'code': 'whisper_not_installed', 'repair': 'install_whisper'})
    with pytest.raises(PipelineFailure) as caught:
        readiness.require_transcription(srt_available=False, analysis_mode='auto')
    assert caught.value.code == 'whisper_not_installed'
    readiness.require_transcription(srt_available=True, analysis_mode='auto')
    readiness.require_transcription(srt_available=False, analysis_mode='visual')


@pytest.mark.own_whisper_status  # simulates its own Whisper runtime / model state
def test_completed_download_flips_readiness_immediately(monkeypatch, isolated):
    # W157 IA: right after the download thread reports "downloaded", readiness must say installed.
    from backend.services.whisper_model_manager import get_model_manager
    small = document(transcription=Transcription(model='small'))
    manager = get_model_manager()
    manager._download_state['small'] = {'status': 'downloaded', 'progress': 100, 'error': None}
    try:
        assert report_for(monkeypatch, small)['checks']['transcription'] == {
            'ok': True, 'code': 'whisper_installed', 'repair': 'none'}
    finally:
        manager._download_state.pop('small', None)


@pytest.mark.parametrize('mode', ['auto', 'visual', 'subtitle'])
@pytest.mark.parametrize('status', ['failed', 'unchecked', 'ok'])
def test_separate_vision_validation_gates_readiness_and_runtime(mode, status):
    from backend.services import ai_model_settings as ai
    from backend.services.studio import readiness, vision_settings
    settings = document(
        connections=[
            Connection(id='ai', name='Analysis', provider='openai', api_key='fixture', validation_status='ok'),
            Connection(id='vision', name='Vision', provider='openai', api_key='fixture', validation_status=status),
        ],
        vision=Assignment(connection_id='vision', model='gpt-4o', capability='multimodal'),
        analysis_mode=mode,
    )
    ai.save(settings)
    original = ai.path().read_bytes()
    result = readiness.report()
    blocked = status == 'failed' and mode == 'visual'  # S5: auto falls back to subtitles
    assert result['ready'] is not blocked
    if blocked:
        assert result['checks']['visual'] == {'ok': False, 'code': 'validation_failed', 'repair': 'settings_vision'}
        for read in (readiness.ensure_analysis_usable, lambda: ai.require_analysis(ai.load()), vision_settings.effective):
            with pytest.raises(ValueError, match='未通过校验'):
                read()
    else:
        readiness.ensure_analysis_usable()
    if status == 'failed':
        # A confirmation can explicitly request vision even when the saved mode is subtitle.
        with pytest.raises(ValueError, match='未通过校验'):
            vision_settings.effective()
    assert ai.path().read_bytes() == original
