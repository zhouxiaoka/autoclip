"""1.5.8 R20 #144 #146 #147 #148 #168: the import gate follows the route planning really takes,
cleans the staged upload on every failure, covers quick output without settings, has one entry
per create-project path, and answers with a stable code instead of Chinese text."""
import inspect

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services import ai_model_settings as ai
from backend.services import whisper_runtime
from backend.services.studio import readiness
from backend.tests.test_r158_whisper_gate_r19 import GATE, isolated, media, quick, settings  # noqa: F401


def _studio_import(monkeypatch, tmp_path, data):
    from backend.api.v1 import studio as api
    created = []
    monkeypatch.setattr(api.ProjectService, 'create_project', lambda *a, **k: created.append(1))
    app = FastAPI(); app.include_router(api.router)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post('/import', files={'video': ('a.mp4', media(tmp_path / 'v.mp4').read_bytes(), 'video/mp4')},
                        data={'auto_start': 'true', **data})
    return r, created


def _staging_empty(tmp_path):
    staging = tmp_path / 'import-staging'
    return not staging.exists() or not any(staging.iterdir())


# ---- #144: visual mode only skips the gate when planning will really take the visual route
def test_144_visual_mode_with_goal_content_is_gated_before_creating_a_project(monkeypatch, tmp_path):
    settings('visual')
    r, created = _studio_import(monkeypatch, tmp_path, {'goal': 'content'})
    assert r.status_code == 422 and r.json()['detail']['code'] == 'whisper_not_installed'
    assert created == [] and _staging_empty(tmp_path)


def test_144_visual_mode_with_a_source_over_the_visual_limit_is_gated(monkeypatch, tmp_path):
    settings('visual')
    from backend.services.studio import planning
    monkeypatch.setattr(readiness, '_source_duration', lambda video: planning.VISUAL_MAX_SOURCE_SEC + 1)
    r, created = _studio_import(monkeypatch, tmp_path, {'goal': 'auto'})
    assert r.status_code == 422 and r.json()['detail']['code'] == 'whisper_not_installed'
    assert created == [] and _staging_empty(tmp_path)


@pytest.mark.parametrize('goal,duration,visual', [
    ('auto', 60, True), ('highlight', 7200, True), ('content', 60, False), ('auto', 7201, False), ('auto', None, False)])
def test_144_gate_and_planning_share_one_route_rule(goal, duration, visual):
    from backend.services.studio import planning
    assert planning.takes_visual_route('visual', goal, duration) is visual
    assert planning.takes_visual_route('subtitle', goal, duration) is False


def test_144_quick_output_visual_over_the_limit_is_rejected(quick, tmp_path, monkeypatch):
    runner, created, inspected = quick
    settings('visual')
    from backend.services.studio import planning
    monkeypatch.setattr(readiness, '_source_duration', lambda video: planning.VISUAL_MAX_SOURCE_SEC + 1)
    with pytest.raises(readiness.TranscriptionNotReady):
        runner.start(str(media(tmp_path / 'v.mp4')), ['douyin'])
    assert created == [] and inspected == []


# ---- #146: every failure after staging removes the staged upload; only the gate becomes a 422
def test_146_studio_import_cleans_staged_file_on_os_error(monkeypatch, tmp_path):
    settings('visual')
    from backend.services.studio import planning

    def boom(*a):
        raise OSError('disk')
    monkeypatch.setattr(planning, 'takes_visual_route', boom)
    r, created = _studio_import(monkeypatch, tmp_path, {'goal': 'auto'})
    assert r.status_code == 500
    assert created == [] and _staging_empty(tmp_path)


def test_146_legacy_upload_cleans_staged_file_on_os_error(monkeypatch, tmp_path):
    settings('subtitle')

    def boom(*a):
        raise OSError('disk')
    monkeypatch.setattr(readiness, '_source_cannot_take_subtitle_route', boom)
    from backend.api.v1 import projects as api
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[api.get_db] = lambda: None
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post('/upload', files={'video_file': ('a.mp4', media(tmp_path / 'v.mp4').read_bytes(), 'video/mp4')},
                        data={'project_name': 'x'})
    assert r.status_code == 500
    assert _staging_empty(tmp_path)


# ---- #147: quick output with no settings document falls back to default local Whisper and refuses
def test_147_quick_output_without_settings_file_is_rejected_and_creates_nothing(quick, tmp_path):
    runner, created, inspected = quick
    assert ai.load() is None
    with pytest.raises(readiness.TranscriptionNotReady, match=GATE):
        runner.start(str(media(tmp_path / 'v.mp4')), ['douyin'])
    assert created == [] and inspected == []


# ---- #148: no gate switch; each create-project entry runs the gate once
def test_148_prepare_project_has_no_gate_switch_and_place_video_never_gates(monkeypatch, tmp_path):
    from backend.services import local_runner
    assert 'gate' not in inspect.signature(local_runner.prepare_project).parameters
    monkeypatch.setattr(local_runner, 'get_project_directory', lambda pid: tmp_path / pid, raising=False)
    import backend.core.path_utils as path_utils
    monkeypatch.setattr(path_utils, 'get_project_directory', lambda pid: tmp_path / 'projects' / pid)

    def refuse(*a, **k):
        raise AssertionError('place_video must not gate')
    monkeypatch.setattr(readiness, 'ensure_local_transcription_for_paths', refuse)
    monkeypatch.setattr(readiness, 'ensure_local_transcription_for_import', refuse)
    video = media(tmp_path / 'src' / 'v.mp4')
    target = local_runner.place_video(local_runner.RunRequest(video=video, project_id='p148', register_db=False))
    assert target.is_file()


def test_148_quick_output_runner_does_not_call_prepare_project():
    from backend.services import quick_output_runner
    assert 'prepare_project' not in inspect.getsource(quick_output_runner)


# ---- #168: 422 carries a stable code; the desktop never parses the Chinese text
@pytest.mark.parametrize('status,code', [('missing', 'whisper_not_installed'), ('installing', 'whisper_installing')])
def test_168_studio_import_422_carries_the_check_code(monkeypatch, tmp_path, status, code):
    settings('subtitle')
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda *a, **k: {'status': status})
    r, created = _studio_import(monkeypatch, tmp_path, {})
    assert r.status_code == 422
    detail = r.json()['detail']
    assert detail['code'] == code and isinstance(detail['message'], str) and detail['message']
    assert created == []


def test_168_tasks_submit_422_carries_the_check_code(monkeypatch, tmp_path):
    settings('subtitle')
    from backend.tests.test_r158_whisper_gate_r19 import _Task, _call
    r, queued, _ = _call(monkeypatch, _Task(media(tmp_path / 'v.mp4')), 'submit')
    assert r.status_code == 422 and r.json()['detail']['code'] == 'whisper_not_installed'
    assert queued == []


def test_168_gate_exception_keeps_cli_mcp_contract():
    exc = readiness.TranscriptionNotReady('whisper_installing')
    assert exc.error_code == 'invalid_input' and str(exc) == readiness.LOCAL_TRANSCRIPTION_INSTALLING
    assert exc.detail == {'code': 'whisper_installing', 'message': readiness.LOCAL_TRANSCRIPTION_INSTALLING}
