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


# ---- #144 / R21 #174 #175: the gate asks planning (one route rule, final goal, same duration fallback)
@pytest.fixture
def vision(monkeypatch):
    from backend.services.studio import intelligence
    monkeypatch.setattr(intelligence, 'ready', lambda: True)


def test_144_visual_mode_with_goal_content_is_gated_before_creating_a_project(monkeypatch, tmp_path, vision):
    settings('visual')
    r, created = _studio_import(monkeypatch, tmp_path, {'goal': 'content'})
    assert r.status_code == 422 and r.json()['detail']['code'] == 'whisper_not_installed'
    assert created == [] and _staging_empty(tmp_path)


def test_144_visual_mode_with_a_source_over_the_visual_limit_is_gated(monkeypatch, tmp_path, vision):
    settings('visual')
    from backend.services.studio import planning
    monkeypatch.setattr(planning, 'source_duration', lambda video, info=None: planning.VISUAL_MAX_SOURCE_SEC + 1)
    r, created = _studio_import(monkeypatch, tmp_path, {'goal': 'auto'})
    assert r.status_code == 422 and r.json()['detail']['code'] == 'whisper_not_installed'
    assert created == [] and _staging_empty(tmp_path)


def test_144_visual_mode_auto_goal_with_vision_model_passes_the_gate(monkeypatch, tmp_path, vision):
    settings('visual')
    readiness.ensure_local_transcription_for_import(srt_available=False, video=media(tmp_path / 'v.mp4'), goal='auto')


def test_174_visual_mode_auto_goal_without_vision_model_is_gated(monkeypatch, tmp_path):
    # planning falls back to goal=content (subtitle route) when no vision model is configured
    settings('visual')
    from backend.services.studio import intelligence
    monkeypatch.setattr(intelligence, 'ready', lambda: False)
    r, created = _studio_import(monkeypatch, tmp_path, {'goal': 'auto'})
    assert r.status_code == 422 and r.json()['detail']['code'] == 'whisper_not_installed'
    assert created == [] and _staging_empty(tmp_path)


def test_174_gate_route_matches_planning_final_goal():
    from backend.services.studio import planning
    assert planning.final_goal('auto', 'visual', configured=False) == 'content'
    assert planning.final_goal('auto', 'visual', configured=True) != 'content'
    assert planning.final_goal('auto', 'visual', configured=True, screened='content') != 'content'  # E2
    assert planning.final_goal('auto', 'auto', configured=True) == 'content'  # unknown before screening
    assert planning.final_goal('highlight', 'visual', configured=False) == 'highlight'


def test_175_gate_uses_the_ffmpeg_duration_fallback_like_planning(monkeypatch, tmp_path, vision):
    settings('visual')
    from backend.pipeline import media_precheck
    from backend.services.studio import intelligence
    monkeypatch.setattr(intelligence, '_probe', lambda video: {'duration': 0})  # ffprobe has no duration
    monkeypatch.setattr(media_precheck, 'probe', lambda video: {'duration': None, 'audio': True})
    monkeypatch.setattr(media_precheck, 'probe_duration', lambda video: (60.0, ''))  # ffmpeg decode finds it
    readiness.ensure_local_transcription_for_import(srt_available=False, video=media(tmp_path / 'v.mp4'), goal='auto')


@pytest.mark.parametrize('mode,goal,duration,ai,degraded,route', [
    ('visual', 'highlight', 60, False, False, 'visual'), ('visual', 'highlight', 7200, False, False, 'visual'),
    ('visual', 'content', 60, False, False, 'subtitle'), ('visual', 'highlight', 7201, False, False, 'subtitle'),
    ('visual', 'highlight', None, False, False, 'subtitle'), ('visual', 'highlight', 60, False, True, 'subtitle'),
    ('auto', 'highlight', 60, True, False, 'visual'), ('auto', 'highlight', 60, False, False, 'subtitle'),
    ('subtitle', 'highlight', 60, True, False, 'subtitle')])
def test_144_one_route_rule(mode, goal, duration, ai, degraded, route):
    from backend.services.studio import planning
    assert planning.resolve_route(mode, goal, duration, ai_screened=ai, degraded=degraded) == route


def test_144_quick_output_visual_over_the_limit_is_rejected(quick, tmp_path, monkeypatch, vision):
    runner, created, inspected = quick
    settings('visual')
    from backend.services.studio import planning
    monkeypatch.setattr(planning, 'source_duration', lambda video, info=None: planning.VISUAL_MAX_SOURCE_SEC + 1)
    with pytest.raises(readiness.TranscriptionNotReady):
        runner.start(str(media(tmp_path / 'v.mp4')), ['douyin'])
    assert created == [] and inspected == []


def test_178_quick_output_gates_with_the_goal_it_will_run(quick, tmp_path, monkeypatch, vision):
    runner, created, inspected = quick
    settings('visual')
    from backend.services.studio import models

    class ContentOptions(models.ImportOptions):
        goal: str = 'content'
    monkeypatch.setattr(models, 'ImportOptions', ContentOptions)
    with pytest.raises(readiness.TranscriptionNotReady):
        runner.start(str(media(tmp_path / 'v.mp4')), ['douyin'])
    assert created == [] and inspected == []


# ---- #146: every failure after staging removes the staged upload; only the gate becomes a 422
def test_146_studio_import_cleans_staged_file_on_os_error(monkeypatch, tmp_path, vision):
    settings('visual')
    from backend.services.studio import planning

    def boom(*a, **k):
        raise OSError('disk')
    monkeypatch.setattr(planning, 'route_before_screening', boom)
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
def test_148_cli_entry_gates_once_before_placing_the_video(monkeypatch, tmp_path):
    from backend.services import local_runner
    import backend.core.path_utils as path_utils
    monkeypatch.setattr(path_utils, 'get_project_directory', lambda pid: tmp_path / 'projects' / pid)
    events = []
    real = readiness.ensure_local_transcription_for_paths
    monkeypatch.setattr(readiness, 'ensure_local_transcription_for_paths', lambda *a, **k: events.append('gate') or real(*a, **k))
    monkeypatch.setattr(readiness, 'ensure_local_transcription_for_import', lambda **k: events.append('gate:import'))
    video = media(tmp_path / 'src' / 'v.mp4')
    target = local_runner.prepare_project(local_runner.RunRequest(video=video, project_id='p148', register_db=False))
    assert events == ['gate', 'gate:import'] and target.is_file()


def test_148_quick_output_gates_once_and_before_creating_the_project(quick, tmp_path, monkeypatch):
    runner, created, inspected = quick
    settings('subtitle')
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda *a, **k: {'status': 'installed'})
    monkeypatch.setattr(readiness, '_whisper_model', lambda name: {'ok': True, 'code': 'whisper_installed'})
    events = []
    from backend.services.project_service import ProjectService
    real_create = ProjectService.create_project
    monkeypatch.setattr(ProjectService, 'create_project', lambda self, *a, **k: events.append('create') or real_create(self, *a, **k))
    for name in ('ensure_local_transcription_for_import', 'ensure_local_transcription_for_paths'):
        real = getattr(readiness, name)
        monkeypatch.setattr(readiness, name, (lambda real, name: lambda *a, **k: events.append(name) or real(*a, **k))(real, name))
    runner.start(str(media(tmp_path / 'v.mp4')), ['douyin'])
    assert events == ['ensure_local_transcription_for_import', 'create']


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


# ---- R21 code health: the desktop no longer infers the route; the readiness report says whether it may skip ASR
@pytest.mark.parametrize('mode,ready,skippable', [('visual', True, True), ('visual', False, False), ('subtitle', True, False), ('auto', True, False)])
def test_r21_readiness_report_marks_transcription_skippable_from_planning(monkeypatch, mode, ready, skippable):
    settings(mode)
    from backend.services.studio import intelligence
    monkeypatch.setattr(intelligence, 'ready', lambda: ready)
    check = readiness.report()['checks']['transcription']
    assert check['ok'] is False
    assert check.get('skippable', False) is skippable
