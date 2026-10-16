"""1.5.8: local file + local Whisper selected + runtime missing + no SRT -> import blocked up front.
Never switches to cloud transcription, never installs anything."""
import shutil
import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services import ai_model_settings as ai
from backend.services import whisper_runtime
from backend.services.studio import readiness


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"analytics":false,"crash_reports":false}')


def _media(path, seconds, audio=True):
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg required')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', f'color=c=gray:s=160x90:d={seconds}']
    if audio:
        cmd += ['-f', 'lavfi', '-i', f'sine=frequency=440:duration={seconds}', '-shortest']
    cmd += ['-pix_fmt', 'yuv420p', str(path)]
    subprocess.run(cmd, check=True)
    return path


def _settings(provider='whisper_local', mode='subtitle'):
    ai.save(ai.ModelSettings(
        connections=[ai.Connection(id='a', name='A', provider='ollama', validation_status='ok')],
        analysis=ai.Assignment(connection_id='a', model='local-text', capability='text'),
        transcription=ai.Transcription(provider=provider), analysis_mode=mode))


def _whisper(monkeypatch, status):
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda *a, **k: {'status': status})
    installs = []
    for name in ('install', 'start_install', 'install_async'):
        if hasattr(whisper_runtime, name):
            monkeypatch.setattr(whisper_runtime, name, lambda *a, **k: installs.append(1))
    return installs


@pytest.mark.parametrize('status', ['missing', 'error'])
def test_gate_blocks_missing_local_whisper_without_srt(monkeypatch, status):
    _settings()
    installs = _whisper(monkeypatch, status)
    with pytest.raises(ValueError, match='需要先安装本地转写'):
        readiness.ensure_local_transcription_for_import(srt_available=False)
    assert installs == []
    assert ai.load().transcription.provider == 'whisper_local'  # never silently switched to cloud


@pytest.mark.parametrize('kw,status,provider,mode', [
    ({'srt_available': True}, 'missing', 'whisper_local', 'subtitle'),
    ({'srt_available': False}, 'installed', 'whisper_local', 'subtitle'),
    # R20 #144: visual mode passes once the staged source shows it fits the visual route.
    ({'srt_available': False, 'video': 'staged.mp4'}, 'missing', 'whisper_local', 'visual'),
])
def test_gate_allows_srt_installed_cloud_or_visual(monkeypatch, kw, status, provider, mode):
    _settings(provider, mode)
    _whisper(monkeypatch, status)
    monkeypatch.setattr(readiness, '_whisper_model', lambda model: {'ok': True, 'code': 'whisper_installed'})
    monkeypatch.setattr(readiness, '_source_duration', lambda video: 60.0)
    readiness.ensure_local_transcription_for_import(**kw)


def test_import_endpoint_blocks_before_creating_a_project(monkeypatch, tmp_path):
    _settings()
    _whisper(monkeypatch, 'missing')
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda: None)
    from backend.api.v1 import studio as api
    created = []
    monkeypatch.setattr(api.ProjectService, 'create_project', lambda *a, **k: created.append(1))
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app) as client:
        blob = _media(tmp_path / 'ok.mp4', 40).read_bytes()
        r = client.post('/import', files={'video': ('a.mp4', blob, 'video/mp4')}, data={'auto_start': 'true'})
    assert r.status_code == 422 and '需要先安装本地转写' in r.text
    assert created == []
    assert not any((tmp_path / 'import-staging').glob('*'))  # staged upload removed


def test_quick_output_file_path_is_gated(monkeypatch, tmp_path):
    _settings()
    _whisper(monkeypatch, 'missing')
    from backend.services import quick_output_runner
    video = _media(tmp_path / 'v.mp4', 40)
    with pytest.raises(ValueError, match='需要先安装本地转写'):
        quick_output_runner.start(str(video), ['douyin'])


@pytest.mark.parametrize('seconds,audio', [(2, True), (40, False)])
def test_source_that_cannot_take_subtitle_route_is_not_gated(monkeypatch, tmp_path, seconds, audio):
    """Too short / no audio needs no Whisper: the pipeline must report source_too_short / source_no_audio."""
    _settings()
    _whisper(monkeypatch, 'missing')
    video = _media(tmp_path / 'v.mp4', seconds, audio)
    readiness.ensure_local_transcription_for_import(srt_available=False, video=video)
    with pytest.raises(ValueError, match='需要先安装本地转写'):
        readiness.ensure_local_transcription_for_import(srt_available=False, video=_media(tmp_path / 'ok.mp4', 40))
