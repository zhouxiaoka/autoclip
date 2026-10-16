"""1.5.8 R23 #230-#233: every async entry runs the gate in the threadpool and the gate runs ffprobe once; an
unreadable source is classified by one rule on every route (never "install Whisper"); installing / model
downloading keep their own code on confirm; the readiness report reads one analysis-mode source."""
import asyncio
import json
import subprocess
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.pipeline import media_precheck
from backend.services import whisper_runtime
from backend.services.studio import intelligence, planning, readiness
from backend.tests import test_r158_whisper_gate_paths as paths
from backend.tests import test_r158_whisper_gate_r19 as r19
from backend.tests.test_r158_whisper_gate_r19 import isolated, media, settings  # noqa: F401


@pytest.fixture
def vision(monkeypatch):
    monkeypatch.setattr(intelligence, 'ready', lambda: True)


@pytest.fixture
def where_gate_runs(monkeypatch):
    seen = []
    real = readiness.ensure_local_transcription_for_import

    def gate(**kw):
        try:
            asyncio.get_running_loop()
            seen.append('event-loop')
        except RuntimeError:
            seen.append('worker')
        return real(**kw)
    monkeypatch.setattr(readiness, 'ensure_local_transcription_for_import', gate)
    return seen


@pytest.fixture
def raw_project(tmp_path):
    from backend.core.path_utils import get_project_raw_directory
    pid = 'proj-gate-r23'
    media(get_project_raw_directory(pid) / 'input.mp4')
    return pid


# ---- #230: process / projects process+retry / smart retry / tasks submit+retry: gate never on the event loop
@pytest.mark.parametrize('entry', ['processing.process', 'projects.process+retry', 'enhanced_retry.processing_only'])
def test_230_project_entries_run_the_gate_in_a_worker_thread(monkeypatch, raw_project, where_gate_runs, entry):
    driver = {'processing.process': paths.test_processing_process_is_gated,
              'projects.process+retry': paths.test_projects_process_and_retry_are_gated,
              'enhanced_retry.processing_only': paths.test_smart_retry_processing_only_is_gated}[entry]
    driver(monkeypatch, raw_project)  # still a coded 422 before any side effect
    assert where_gate_runs and set(where_gate_runs) == {'worker'}, where_gate_runs


@pytest.mark.parametrize('action', ['submit', 'retry'])
def test_230_task_entries_run_the_gate_in_a_worker_thread(monkeypatch, tmp_path, where_gate_runs, action):
    settings()
    r, queued, updates = r19._call(monkeypatch, r19._Task(media(tmp_path / 'v.mp4')), action)
    assert r.status_code == 422 and r.json()['detail']['code'] == 'whisper_not_installed'
    assert queued == [] and updates == []
    assert where_gate_runs == ['worker']


def _count_ffprobe(monkeypatch):
    calls = []
    real = subprocess.run

    def run(cmd, *a, **k):
        if 'ffprobe' in str(cmd[0]):
            calls.append(cmd)
        return real(cmd, *a, **k)
    monkeypatch.setattr(subprocess, 'run', run)
    return calls


@pytest.mark.parametrize('route,mode,goal', [('studio', 'subtitle', 'auto'), ('studio', 'visual', 'content'), ('content', 'subtitle', 'auto')])
def test_230_gate_runs_ffprobe_once_on_a_readable_source(monkeypatch, tmp_path, vision, route, mode, goal):
    settings(mode)
    video = media(tmp_path / 'v.mp4')
    calls = _count_ffprobe(monkeypatch)
    with pytest.raises(readiness.TranscriptionNotReady):
        readiness.ensure_local_transcription_for_import(srt_available=False, video=video, route=route, goal=goal)
    assert len(calls) == 1, [c[:3] for c in calls]


# ---- #231: content / CLI / MCP with an unreadable source: same classification, never the Whisper prompt
def _broken(tmp_path):
    broken = tmp_path / 'broken.mp4'
    broken.write_bytes(b'not a video at all' * 64)
    return broken




def test_231_unreadable_source_is_classified_once_for_every_route(tmp_path):
    failure = media_precheck.subtitle_source_failure(_broken(tmp_path), srt_available=False)
    assert failure is not None and failure.code == 'source_unreadable'


@pytest.mark.parametrize('mode', ['subtitle', 'auto', 'visual'])
def test_231_content_paths_do_not_ask_for_whisper_on_an_unreadable_source(tmp_path, vision, mode):
    settings(mode)
    broken = _broken(tmp_path)
    readiness.ensure_local_transcription_for_paths(broken, sibling_srt=False, route='content')  # process / submit / retry


def test_231_cli_and_mcp_prepare_pass_an_unreadable_source_to_the_pipeline(monkeypatch, tmp_path):
    from backend.services import local_runner
    settings()
    broken = _broken(tmp_path)
    placed = local_runner.prepare_project(local_runner.RunRequest(video=broken, register_db=False, project_id='cli-r23-1'))
    assert placed.is_file()


def test_231_content_pipeline_reports_source_unreadable_not_whisper(monkeypatch, tmp_path):
    from backend.services.simple_pipeline_adapter import SimplePipelineAdapter
    settings()
    broken = _broken(tmp_path)
    result = asyncio.run(SimplePipelineAdapter('r23-unreadable', task_id='t-r23').process_project_sync(str(broken), None))
    assert result.get('error_code') == 'source_unreadable', result
    assert 'Whisper' not in (result.get('error') or ''), result


def test_231_unreadable_source_still_gated_when_a_readable_one_is(tmp_path):
    settings()
    with pytest.raises(readiness.TranscriptionNotReady):
        readiness.ensure_local_transcription_for_paths(media(tmp_path / 'v.mp4'), sibling_srt=False, route='content')


# ---- #232: confirm keeps installing / model downloading as waiting states
def _confirm(monkeypatch, tmp_path):
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
        return client.post('/p1/start', json={'plan_id': 'plan1', 'goals': ['content']})


@pytest.mark.own_whisper_status
def test_232_confirm_while_whisper_installs_is_a_wait_not_a_reinstall(monkeypatch, tmp_path):
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda *a, **k: {'status': 'installing'})
    r = _confirm(monkeypatch, tmp_path)
    assert r.status_code == 422, r.text
    assert r.json()['detail']['code'] == 'whisper_installing'
    assert r.json()['detail']['message'] == readiness.LOCAL_TRANSCRIPTION_INSTALLING


@pytest.mark.own_whisper_status
def test_232_confirm_while_the_model_downloads_is_a_wait_not_a_reinstall(monkeypatch, tmp_path):
    from backend.services.whisper_model_manager import get_model_manager
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda *a, **k: {'status': 'installed'})
    manager = get_model_manager()
    monkeypatch.setattr(manager, 'get_local_model_path', lambda model: None)
    monkeypatch.setitem(manager._download_state, 'base', {'status': 'downloading', 'progress': 10, 'error': None})
    r = _confirm(monkeypatch, tmp_path)
    assert r.status_code == 422, r.text
    assert r.json()['detail']['code'] == 'whisper_model_downloading'
    assert r.json()['detail']['message'] == readiness.LOCAL_TRANSCRIPTION_DOWNLOADING


# ---- #233: every report field follows the one analysis-mode source planning and the gate read
@pytest.mark.own_whisper_status
def test_233_report_mode_visual_check_and_skippable_follow_one_source(monkeypatch, tmp_path, vision):
    from backend.services import ai_model_settings as ai
    from backend.services.studio import analysis_preferences
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda *a, **k: {'status': 'missing'})
    # The editing document still says auto; the preference planning reads says visual.
    doc = ai.ModelSettings(analysis_mode='auto')
    monkeypatch.setattr(ai, 'for_editing', lambda: doc)
    reads = []
    monkeypatch.setattr(analysis_preferences, 'load',
                        lambda: reads.append(1) or analysis_preferences.AnalysisPreferences(analysis_mode='visual'))
    report = readiness.report()
    assert report['analysis_mode'] == 'visual'
    assert report['checks']['visual']['code'] != 'optional'  # the visual-mode check, not the auto-mode answer
    assert report['checks']['transcription'].get('skippable') is True
    assert len(reads) == 1  # read once for every field
