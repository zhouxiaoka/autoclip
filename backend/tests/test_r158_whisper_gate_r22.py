"""1.5.8 R22 #206-#212: the import gate reads duration off the event loop and only when it matters, lets an
unreadable source through to source_unreadable, reads the same analysis preference as planning (legacy file
included), the duration fallback is tested at the ffprobe/ffmpeg layer, confirm answers a coded 422, and a
whisper failure keeps its install hint."""
import asyncio
import json
import subprocess
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.pipeline import media_precheck
from backend.services import ai_model_settings as ai
from backend.services.studio import intelligence, planning, readiness
from backend.tests.test_r158_whisper_gate_r19 import isolated, media, settings  # noqa: F401


@pytest.fixture
def vision(monkeypatch):
    monkeypatch.setattr(intelligence, 'ready', lambda: True)


# ---- #206: no blocking duration read on the event loop, none at all when the route is already subtitle
def test_206_upload_gate_runs_in_a_worker_thread_not_on_the_event_loop(monkeypatch, tmp_path):
    from backend.api.v1 import studio as api
    seen = []
    real = readiness.ensure_local_transcription_for_import

    def gate(**kw):
        if kw.get('video') is None:
            raise readiness.TranscriptionNotReady('whisper_not_installed')  # ask the caller to stage the file
        try:
            asyncio.get_running_loop()
            seen.append('event-loop')
        except RuntimeError:
            seen.append('worker')
        return real(**kw)
    monkeypatch.setattr(readiness, 'ensure_local_transcription_for_import', gate)
    settings('visual')
    monkeypatch.setattr(api.ProjectService, 'create_project', lambda *a, **k: None)
    app = FastAPI(); app.include_router(api.router)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post('/import', files={'video': ('a.mp4', media(tmp_path / 'v.mp4').read_bytes(), 'video/mp4')},
                        data={'auto_start': 'true', 'goal': 'content'})
    assert r.status_code == 422 and r.json()['detail']['code'] == 'whisper_not_installed'
    assert seen == ['worker']


@pytest.mark.parametrize('mode,goal', [('visual', 'content'), ('auto', 'auto'), ('subtitle', 'highlight')])
def test_206_subtitle_route_known_before_duration_never_decodes(monkeypatch, tmp_path, vision, mode, goal):
    settings(mode)
    decodes = []
    monkeypatch.setattr(media_precheck, '_ffmpeg_decode_duration', lambda video: decodes.append(1) or (60.0, ''))
    monkeypatch.setattr(planning, 'source_duration', lambda *a, **k: decodes.append('rule') or 60.0)
    with pytest.raises(readiness.TranscriptionNotReady):
        readiness.ensure_local_transcription_for_import(srt_available=False, video=media(tmp_path / 'v.mp4'), goal=goal)
    assert decodes == []


# ---- #207: an unreadable source is not "Whisper missing"; the pipeline reports source_unreadable
@pytest.mark.parametrize('mode,goal', [('visual', 'auto'), ('auto', 'auto'), ('visual', 'content')])
def test_207_unreadable_source_passes_the_gate(monkeypatch, tmp_path, vision, mode, goal):
    settings(mode)
    broken = tmp_path / 'broken.mp4'
    broken.write_bytes(b'not a video at all' * 64)
    readiness.ensure_local_transcription_for_import(srt_available=False, video=broken, goal=goal)
    with pytest.raises(media_precheck.SourceUnreadable) as caught:
        planning.source_duration(broken)
    assert caught.value.code == 'source_unreadable'


# ---- #208: only the legacy analysis-preferences.json -> gate and planning read the same mode
def _legacy_only(tmp_path, mode):
    assert not ai.path().exists()
    (tmp_path / 'analysis-preferences.json').write_text(json.dumps({'analysis_mode': mode}), encoding='utf-8')


def test_208_legacy_visual_preference_is_honoured_by_the_gate(monkeypatch, tmp_path, vision):
    from backend.services.studio import analysis_preferences
    _legacy_only(tmp_path, 'visual')
    assert analysis_preferences.load().analysis_mode == 'visual'  # what recommend() reads
    readiness.ensure_local_transcription_for_import(srt_available=False, video=media(tmp_path / 'v.mp4'), goal='auto')


def test_208_legacy_subtitle_preference_is_still_gated(monkeypatch, tmp_path, vision):
    _legacy_only(tmp_path, 'subtitle')
    with pytest.raises(readiness.TranscriptionNotReady):
        readiness.ensure_local_transcription_for_import(srt_available=False, video=media(tmp_path / 'v.mp4'), goal='auto')


def test_208_readiness_report_skippable_follows_the_same_preference(monkeypatch, tmp_path, vision):
    _legacy_only(tmp_path, 'visual')
    assert planning.transcription_may_be_skipped() is True
    _legacy_only(tmp_path, 'auto')
    assert planning.transcription_may_be_skipped() is False


# ---- #210: the duration fallback is exercised at the ffprobe / ffmpeg subprocess layer
def _fake_tools(monkeypatch, decoded_seconds):
    calls = []
    real_run = subprocess.run

    def run(cmd, *a, **k):
        tool = str(cmd[0])
        if 'ffprobe' in tool:
            calls.append('ffprobe')
            return subprocess.CompletedProcess(cmd, 0, stdout='{}', stderr='')
        if 'ffmpeg' in tool and '-f' in cmd and 'null' in cmd:
            calls.append('ffmpeg-decode')
            h, rest = divmod(decoded_seconds, 3600); m, s = divmod(rest, 60)
            return subprocess.CompletedProcess(cmd, 0, stdout='', stderr=f'frame=1 time={int(h):02d}:{int(m):02d}:{s:05.2f} bitrate=1\n')
        return real_run(cmd, *a, **k)
    monkeypatch.setattr(media_precheck.subprocess, 'run', run)
    monkeypatch.setattr(intelligence, '_probe', lambda video: {'duration': 0})
    return calls


def test_210_source_duration_recovers_through_the_ffmpeg_decode(monkeypatch, tmp_path):
    video = media(tmp_path / 'v.mp4')
    calls = _fake_tools(monkeypatch, 60)
    assert planning.source_duration(video) == 60.0
    assert calls == ['ffprobe', 'ffmpeg-decode']


def test_210_gate_uses_the_decoded_duration_to_pick_the_route(monkeypatch, tmp_path, vision):
    # ffprobe has no duration; only the ffmpeg decode shows the source is over the visual limit -> subtitle -> gated.
    # Without the fallback the source would look unreadable and pass (R22 #207), so this fails if the fallback goes.
    settings('visual')
    video = media(tmp_path / 'v.mp4')
    calls = _fake_tools(monkeypatch, planning.VISUAL_MAX_SOURCE_SEC + 60)
    with pytest.raises(readiness.TranscriptionNotReady):
        readiness.ensure_local_transcription_for_import(srt_available=False, video=video, goal='auto')
    assert 'ffmpeg-decode' in calls


# ---- #211: confirm (POST /{id}/start) with transcription not ready answers a coded 422
def test_211_confirm_subtitle_plan_without_whisper_is_a_coded_422(monkeypatch, tmp_path):
    from backend.api.v1 import studio as api
    from backend.services.studio import jobs, store
    settings('auto')
    video = media(tmp_path / 'raw' / 'input.mp4')
    state = {'plan': {'id': 'plan1', 'recommended_analysis': 'subtitle', 'source_duration': 40.0, 'preferences': {}},
             'analysis': {'status': 'awaiting_confirmation'}}
    monkeypatch.setattr(api, 'project_or_404', lambda pid, db: SimpleNamespace(id=pid))
    monkeypatch.setattr(store, 'read', lambda pid: state)
    monkeypatch.setattr(store, 'directory', lambda pid: tmp_path)
    monkeypatch.setattr(jobs, 'source', lambda pid: video)
    monkeypatch.setattr(store, 'write', lambda *a: pytest.fail('must refuse before writing'))
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[api.get_db] = lambda: None
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post('/p1/start', json={'plan_id': 'plan1', 'goals': ['content']})
    assert r.status_code == 422, r.text
    assert r.json()['detail']['code'] == 'whisper_not_installed'


# ---- #212: a whisper failure during screening keeps the install hint
def test_212_screening_failure_keeps_the_install_hint(monkeypatch, tmp_path):
    from backend.pipeline.failures import transcription_not_ready_failure
    from backend.services.studio import jobs
    error = transcription_not_ready_failure({'code': 'whisper_not_installed'})

    def recommend(video, options):
        raise error
    monkeypatch.setattr(planning, 'recommend', recommend)
    saved = {'analysis': {}, 'generation': {'auto_start': True}}
    monkeypatch.setattr(jobs.store, 'change', lambda pid, fn: fn(saved))
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'source', lambda pid: tmp_path / 'input.mp4')
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *a, **k: None)
    jobs._inspect('p1', SimpleNamespace(auto_start=True), None, None)
    assert error.hint and error.hint in saved['analysis']['error']
    assert error.hint in saved['generation']['error']
    assert saved['analysis']['error_code'] == 'whisper_not_installed'
