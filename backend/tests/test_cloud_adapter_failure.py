"""Cloud failures must survive the real auto router and adapter without local-ASR advice.

The request protocol is genuine; audio extraction and HTTP transport are controlled,
so these regressions never encode media or contact a provider.
"""
import asyncio
import json
import logging
from types import SimpleNamespace
import wave

import httpx
import pytest

from backend.services import ai_model_settings, cloud_transcription as asr
from backend.services import simple_pipeline_adapter as pipeline
from backend.services.ai_model_settings import Connection, ModelSettings, Transcription

MODELS = ('qwen-audio-3.0-asr-flash', 'qwen-audio-3.1-asr-flash', 'fun-asr-flash-2026-06-15')


@pytest.fixture
def cloud_adapter(tmp_path, monkeypatch):
    # Import optional speech dependencies before the narrow subprocess boundary is patched.
    from backend.utils import speech_recognizer  # noqa: F401
    from backend.core import path_utils
    from backend.services import simple_progress, whisper_runtime

    events, requests = [], []
    original_client = httpx.Client
    monkeypatch.setattr(path_utils, 'get_project_directory', lambda pid: tmp_path / pid)
    monkeypatch.setattr(pipeline, 'clear_progress', lambda pid: None)
    def progress(pid, stage, message='', subpercent=None):
        events.append((stage, message))
    monkeypatch.setattr(pipeline, 'emit_progress', progress)
    monkeypatch.setattr(simple_progress, 'emit_progress', progress)
    monkeypatch.setattr(pipeline.SimplePipelineAdapter, '_prompt_files', lambda self, folder: {})
    monkeypatch.setattr(pipeline.SimplePipelineAdapter, '_preflight_llm', staticmethod(lambda: None))
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda: {'status': 'not_installed'})
    monkeypatch.setattr(asr, 'UPLOAD_WORKERS', 1)
    monkeypatch.setattr(asr.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(asr, 'get_ffmpeg_path', lambda: 'controlled-extraction')
    def extract(command, **kwargs):
        assert command[0] == 'controlled-extraction'
        with wave.open(command[-1], 'wb') as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(b'\0\0' * 16000)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(asr.subprocess, 'run', extract)
    video = tmp_path / 'public-controlled.mp4'
    video.write_bytes(b'controlled-input-not-decoded')
    adapter = pipeline.SimplePipelineAdapter('cloud-project', 'cloud-task')

    def configure(model, reply):
        settings = ModelSettings(connections=[Connection(id='asr', name='ASR', provider='dashscope',
                api_key='fixture-key')],
            transcription=Transcription(provider='cloud', connection_id='asr', model=model))
        monkeypatch.setattr(ai_model_settings, 'load', lambda: settings)
        def handler(request):
            body = json.loads(request.content)
            assert body['model'] == model
            assert request.headers['X-DashScope-SSE'] == 'enable'
            requests.append(body['model'])
            return reply(request)
        monkeypatch.setattr(asr.httpx, 'Client', lambda **kwargs:
                            original_client(transport=httpx.MockTransport(handler), **kwargs))
        return settings
    return SimpleNamespace(adapter=adapter, video=video, events=events, requests=requests,
                           configure=configure, tmp_path=tmp_path)


@pytest.mark.parametrize('model', MODELS)
@pytest.mark.parametrize('status', [409, 401, 500])
def test_real_cloud_http_failure_keeps_provider_status(cloud_adapter, model, status, caplog):
    case = cloud_adapter
    case.configure(model, lambda request: httpx.Response(status,
        json={'error': {'message': 'raw-provider-secret-body'}}, request=request))
    with caplog.at_level(logging.INFO, logger=pipeline.__name__):
        result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    assert result['status'] == 'failed'
    assert result['stage'] == 'SUBTITLE'
    assert result['error_code'] == 'provider_error'
    assert f'HTTP {status}' in result['error']
    assert '云端转写' in result['error']
    assert 'Whisper' not in result['error']
    assert 'raw-provider-secret-body' not in result['error']
    assert 'raw-provider-secret-body' not in caplog.text
    assert 'Whisper' not in caplog.text
    assert result['message'] == result['error']
    assert len(case.requests) == (asr.CHUNK_ATTEMPTS if status == 500 else 1)
    assert case.events[-1][0] == 'SUBTITLE'
    assert not list(case.tmp_path.rglob('*.srt'))
    assert not list(case.tmp_path.rglob('step1_outline.json'))


@pytest.mark.parametrize('model', MODELS)
@pytest.mark.parametrize('kind', ['connection', 'invalid_response', 'empty'])
def test_real_cloud_non_http_failure_has_no_local_install_advice(cloud_adapter, model, kind):
    case = cloud_adapter
    def reply(request):
        if kind == 'connection':
            raise httpx.ConnectError('private-network-detail', request=request)
        if kind == 'invalid_response':
            return httpx.Response(200, text='not-json', request=request)
        return httpx.Response(200, json={'output': {}}, request=request)
    case.configure(model, reply)
    result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    assert result['status'] == 'failed'
    assert result['stage'] == 'SUBTITLE'
    assert result['error_code'] == 'provider_error'
    assert '云端转写' in result['error']
    assert 'Whisper' not in result['error']
    assert 'private-network-detail' not in result['error']
    assert len(case.requests) == (asr.CHUNK_ATTEMPTS if kind == 'connection' else 1)
    assert not list(case.tmp_path.rglob('*.srt'))


@pytest.mark.parametrize('model', MODELS)
def test_cloud_missing_output_does_not_probe_local_whisper(cloud_adapter, model, monkeypatch):
    from backend.services import whisper_runtime
    case = cloud_adapter
    case.configure(model, lambda request: httpx.Response(200, request=request))
    async def no_srt(self, video, metadata_dir):
        return None
    monkeypatch.setattr(pipeline.SimplePipelineAdapter, '_generate_subtitle_automatically', no_srt)
    def local_probe():
        pytest.fail('Cloud failure must not inspect local Whisper installation')
    monkeypatch.setattr(whisper_runtime, 'get_status', local_probe)
    result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
    assert result['status'] == 'failed'
    assert result['stage'] == 'SUBTITLE'
    assert result['error_code'] == 'provider_error'
    assert '云端转写' in result['error']
    assert 'Whisper' not in result['error']
    assert not case.requests


@pytest.mark.parametrize('model', MODELS)
def test_auto_router_cloud_success_keeps_subtitle_and_provider_neutral_log(cloud_adapter, model, caplog):
    case = cloud_adapter
    case.configure(model, lambda request: httpx.Response(200, request=request, json={'output': {
        'sentence': {'sentence_end': True, 'sentence_id': 0, 'begin_time': 0, 'end_time': 800, 'text': '授权素材字幕'}
    }}))
    metadata = case.tmp_path / 'metadata'
    metadata.mkdir()
    with caplog.at_level(logging.INFO, logger=pipeline.__name__):
        output = asyncio.run(case.adapter._generate_subtitle_automatically(str(case.video), metadata))
    assert '授权素材字幕' in output.read_text(encoding='utf-8')
    assert len(case.requests) == 1
    assert 'Whisper' not in caplog.text


@pytest.mark.parametrize('model', MODELS)
def test_cloud_failure_survives_auto_generation_terminal_store(cloud_adapter, model, monkeypatch):
    """Real router/adapter, run_content and production/store; only the Celery DB wrapper is inert."""
    from backend.services.studio import jobs, store
    from backend.services.studio.models import Preferences
    from backend.tasks.processing import process_video_pipeline
    case = cloud_adapter
    case.configure(model, lambda request: httpx.Response(409, request=request,
        json={'error': {'message': 'raw-provider-secret-body'}}))
    monkeypatch.setattr(store, 'get_projects_directory', lambda: case.tmp_path)
    monkeypatch.setattr(jobs, 'source', lambda pid: case.video)
    statuses, dispatched = [], []
    monkeypatch.setattr(jobs, 'mark_project', lambda pid, status: statuses.append(status))
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *args: None)
    def apply(*, kwargs, throw):
        assert throw is True
        assert kwargs == {'project_id': 'cloud-project', 'input_video_path': str(case.video),
                          'input_srt_path': None, 'clips_only': True}
        result = asyncio.run(case.adapter.process_project_sync(str(case.video), '', clips_only=True))
        dispatched.append(result)
        return SimpleNamespace(get=lambda: {'success': False, 'error': result['error'], 'result': result})
    monkeypatch.setattr(process_video_pipeline, 'apply', apply)
    plan = {'id': 'manual-plan', 'mode': 'manual', 'recommended_analysis': 'subtitle',
            'preferences': Preferences(goal='highlight').model_dump()}
    (case.tmp_path / 'cloud-project').mkdir()
    store.write('cloud-project', {'schema_version': 2, 'drafts': [], 'events': [], 'jobs': [],
        'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'accepted-run',
                     'instance': store.INSTANCE},
        'generation': {'auto_start': True, 'status': 'running', 'requested_platforms': ['douyin']},
        'output_variants': [], 'plan': plan})
    jobs._auto_generate('cloud-project', plan)
    state = store.read('cloud-project')
    for terminal in (state['generation'], state['analysis']):
        assert terminal['status'] == 'failed'
        assert terminal['error_code'] == 'provider_error'
        assert '云端转写' in terminal['error'] and 'HTTP 409' in terminal['error']
        assert 'Whisper' not in terminal['error']
        assert 'raw-provider-secret-body' not in terminal['error']
    assert state['analysis']['phase'] == 'production'
    assert state['analysis']['run_id'] == 'accepted-run'
    assert dispatched[0]['stage'] == 'SUBTITLE'
    assert state['generation']['finished_at']
    assert state['output_variants'] == []
    assert statuses == ['failed']
    assert len(case.requests) == 1


@pytest.mark.parametrize('model', MODELS)
def test_legacy_import_preserves_typed_cloud_failure(cloud_adapter, model, monkeypatch):
    from backend.core import desktop_config
    from backend.tasks import import_processing as imports
    case = cloud_adapter
    case.configure(model, lambda request: httpx.Response(409, request=request,
        json={'error': {'message': 'raw-provider-secret-body'}}))
    speech = SimpleNamespace(method='whisper_local', enable_fallback=True, fallback_method='whisper_local',
                             whisper_config=SimpleNamespace(language='auto', timeout=0))
    monkeypatch.setattr(desktop_config, 'get_desktop_config',
                        lambda: SimpleNamespace(speech_recognition=speech))
    progress = []
    task = SimpleNamespace(update_state=lambda **kwargs: progress.append(kwargs))
    subtitle, error = imports._generate_import_subtitle(task, 'cloud-project', str(case.video))
    assert subtitle is None
    failure = imports.import_subtitle_failure(error)
    assert failure.stage == 'SUBTITLE'
    assert failure.code == 'provider_error'
    assert isinstance(error, asr.CloudTranscriptionError)
    assert 'HTTP 409' in failure.user_message() and '云端转写' in failure.user_message()
    assert 'Whisper' not in failure.user_message()
    assert 'raw-provider-secret-body' not in failure.user_message()
    assert len(case.requests) == 1
    assert progress[0]['state'] == 'PROGRESS'
    project = SimpleNamespace(status='pending', project_metadata={})
    service = SimpleNamespace(
        update_project_status=lambda pid, status: setattr(project, 'status', status),
        get=lambda pid: project,
        update=lambda pid, **kwargs: setattr(project, 'project_metadata', kwargs['project_metadata']))
    with pytest.raises(imports.ImportProcessingError) as caught:
        imports._fail_import(service, 'cloud-project', failure.user_message(), error_code=failure.code)
    assert 'Whisper' not in str(caught.value)
    assert project.status == 'failed'
    assert project.project_metadata['last_error_code'] == 'provider_error'
    assert 'HTTP 409' in project.project_metadata['last_error']
