"""1.5.8 R18 #72-#78: Whisper import gate on submit / CLI / MCP routes, staging cleanup, CLI+MCP contracts."""
import json
import shutil
import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services import ai_model_settings as ai
from backend.services import whisper_runtime
from backend.services.studio import readiness

GATE = '需要先安装本地转写'
SRT = '1\n00:00:00,000 --> 00:00:02,000\nhi\n'


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"analytics":false,"crash_reports":false}')
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda: None)


def media(path, seconds=40):
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg required')
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', f'color=c=gray:s=160x90:d={seconds}',
                    '-f', 'lavfi', '-i', f'sine=frequency=440:duration={seconds}', '-shortest', '-pix_fmt', 'yuv420p', str(path)], check=True)
    return path


def settings(mode='subtitle'):
    ai.save(ai.ModelSettings(
        connections=[ai.Connection(id='a', name='A', provider='ollama', validation_status='ok')],
        analysis=ai.Assignment(connection_id='a', model='local-text', capability='text'),
        transcription=ai.Transcription(provider='whisper_local'), analysis_mode=mode))


def whisper(monkeypatch, status='missing'):
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda *a, **k: {'status': status})


def project_dirs(tmp_path):
    from backend.core.path_utils import get_projects_directory
    root = get_projects_directory()
    return [p for p in root.iterdir()] if root.exists() else []


# ---- 72: tasks/{id}/submit
class _Task:
    task_type = 'video_processing'
    project_id = 'p'

    def __init__(self, video, srt=None):
        self.task_config = {'input_video_path': str(video), **({'input_srt_path': str(srt)} if srt else {})}


def _submit(monkeypatch, task):
    from backend.api.v1 import tasks as api
    queued = []

    class Svc:
        def __init__(self, db):
            pass

        def get_task_by_id(self, tid):
            return task

    class Queue:
        def __init__(self, db):
            pass

        def submit_video_processing_task(self, **kw):
            queued.append(kw)
            return {'task_id': 'q'}
    monkeypatch.setattr(api, 'TaskService', Svc)
    monkeypatch.setattr(api, 'TaskQueueService', Queue)
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[api.get_db] = lambda: None
    return TestClient(app).post('/t1/submit'), queued


def test_tasks_submit_is_gated_before_queueing(monkeypatch, tmp_path):
    settings(); whisper(monkeypatch)
    r, queued = _submit(monkeypatch, _Task(media(tmp_path / 'v.mp4')))
    assert r.status_code == 422 and GATE in r.text
    assert queued == []


def test_tasks_submit_with_subtitle_is_queued(monkeypatch, tmp_path):
    settings(); whisper(monkeypatch)
    srt = tmp_path / 'sub.srt'; srt.write_text(SRT, encoding='utf-8')
    r, queued = _submit(monkeypatch, _Task(media(tmp_path / 'v.mp4'), srt))
    assert r.status_code == 200, r.text
    assert len(queued) == 1


# ---- 73: missing settings file / global visual mode must not skip the gate on content routes
def test_missing_settings_file_still_gates_content_route_like_runtime(monkeypatch, tmp_path):
    whisper(monkeypatch)
    assert ai.load() is None  # no new-style settings document
    assert readiness.transcription_check()['code'] == 'whisper_not_installed'  # what the pipeline would hit
    video = media(tmp_path / 'v.mp4')
    with pytest.raises(readiness.TranscriptionNotReady, match=GATE):
        readiness.ensure_local_transcription_for_import(srt_available=False, video=video, route='content')
    with pytest.raises(readiness.TranscriptionNotReady, match=GATE):
        readiness.ensure_local_transcription_for_paths(video)  # legacy / CLI default is the content route


def test_visual_mode_still_gates_content_route_but_not_studio(monkeypatch, tmp_path):
    settings('visual'); whisper(monkeypatch)
    from backend.services.studio import intelligence
    monkeypatch.setattr(intelligence, 'ready', lambda: True)  # visual route needs a vision model (R21 #174)
    video = media(tmp_path / 'v.mp4')
    readiness.ensure_local_transcription_for_import(srt_available=False, video=video)  # studio honours visual
    with pytest.raises(readiness.TranscriptionNotReady, match=GATE):
        readiness.ensure_local_transcription_for_import(srt_available=False, video=video, route='content')


@pytest.mark.parametrize('mode', ['visual', None])
def test_cli_run_blocked_before_project_creation(monkeypatch, tmp_path, capsys, mode):
    """visual + CLI, and no settings file + CLI: exit 2, invalid_input JSON on stdout, no project dir (#73 #76 #78)."""
    if mode:
        settings(mode)
    whisper(monkeypatch)
    from backend import cli
    from backend.services import local_runner
    monkeypatch.setattr(local_runner, 'configure_llm', lambda override: {})
    ran = []
    monkeypatch.setattr(local_runner, 'run_pipeline', lambda *a, **k: ran.append(1) or {'status': 'succeeded'})
    video = media(tmp_path / 'src' / 'v.mp4')
    code = cli.main(['run', str(video), '--json', '--no-db'])
    out = capsys.readouterr().out.strip()
    assert code == 2
    payload = json.loads(out)
    assert payload['ok'] is False and payload['error_code'] == 'invalid_input' and GATE in payload['error']
    assert ran == []
    assert project_dirs(tmp_path) == []


# ---- 74: input.srt beside the source does not count unless it is copied
def test_cli_stray_input_srt_beside_source_does_not_pass_gate(monkeypatch, tmp_path):
    settings(); whisper(monkeypatch)
    from backend.services import local_runner
    video = media(tmp_path / 'src' / 'v.mp4')
    (video.parent / 'input.srt').write_text(SRT, encoding='utf-8')  # never copied by prepare_project
    req = local_runner.RunRequest(video=video, register_db=False, project_id='cli-stray-srt')
    with pytest.raises(readiness.TranscriptionNotReady, match=GATE):
        local_runner.prepare_project(req)
    assert project_dirs(tmp_path) == []


def test_cli_explicit_srt_passes_and_is_copied(monkeypatch, tmp_path):
    settings(); whisper(monkeypatch)
    from backend.services import local_runner
    video = media(tmp_path / 'src' / 'v.mp4')
    srt = tmp_path / 'src' / 'subs.srt'; srt.write_text(SRT, encoding='utf-8')
    req = local_runner.RunRequest(video=video, srt=srt, register_db=False, project_id='cli-explicit-srt')
    target = local_runner.prepare_project(req)
    assert (target.parent / 'input.srt').read_text(encoding='utf-8') == SRT


def test_project_raw_input_srt_still_counts(monkeypatch, tmp_path):
    settings(); whisper(monkeypatch)
    from backend.core.path_utils import get_project_raw_directory
    raw = get_project_raw_directory('proj-with-srt')
    media(raw / 'input.mp4'); (raw / 'input.srt').write_text(SRT, encoding='utf-8')
    readiness.ensure_local_transcription_for_project('proj-with-srt')  # pipeline reads raw/input.srt


# ---- 75: staging cleanup on move / mkdir failure
def _staging_empty(tmp_path):
    staging = tmp_path / 'import-staging'
    return not staging.exists() or not any(staging.iterdir())


def test_legacy_upload_move_failure_removes_staging(monkeypatch, tmp_path):
    from backend.api.v1 import projects as api
    settings(); whisper(monkeypatch)
    short = media(tmp_path / 'short.mp4', 2)  # passes the gate via the probe -> upload is staged

    class Proj:
        id = 'legacy-move'

    class Svc:
        db = None

        def create_project(self, *a, **k):
            return Proj()

    def boom(*a, **k):
        raise OSError('disk full')
    monkeypatch.setattr(shutil, 'move', boom)
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[api.get_project_service] = lambda: Svc()
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post('/upload', files={'video_file': ('a.mp4', short.read_bytes(), 'video/mp4')}, data={'project_name': 'x'})
    assert r.status_code >= 400
    assert (tmp_path / 'import-staging').exists()  # the upload really was staged
    assert _staging_empty(tmp_path)


def test_studio_raw_mkdir_failure_removes_staging(monkeypatch, tmp_path):
    from pathlib import Path
    from backend.api.v1 import studio as api
    settings(); whisper(monkeypatch)
    short = media(tmp_path / 'short.mp4', 2)

    class Proj:
        id = 'studio-mkdir'
        status = 'pending'
    monkeypatch.setattr(api.ProjectService, 'create_project', lambda *a, **k: Proj())
    real_mkdir = Path.mkdir

    def mkdir(self, *a, **k):
        if self.name == 'raw':
            raise PermissionError('denied')
        return real_mkdir(self, *a, **k)
    monkeypatch.setattr(Path, 'mkdir', mkdir)

    class DB:
        def commit(self):
            pass
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[api.get_db] = lambda: DB()
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post('/import', files={'video': ('a.mp4', short.read_bytes(), 'video/mp4')}, data={'auto_start': 'true'})
    assert r.status_code == 500
    assert (tmp_path / 'import-staging').exists()
    assert _staging_empty(tmp_path)


# ---- 76 / 77: MCP keeps the error code and only maps the gate to invalid_input
def test_mcp_clip_video_preserves_invalid_input(monkeypatch, tmp_path):
    import asyncio
    settings(); whisper(monkeypatch)
    from backend import mcp_server
    from backend.services import local_runner
    monkeypatch.setattr(local_runner, 'configure_llm', lambda override: {})

    class Ctx:
        async def report_progress(self, *a, **k):
            pass
    fn = getattr(mcp_server.clip_video, 'fn', mcp_server.clip_video)
    result = asyncio.run(fn(str(media(tmp_path / 'v.mp4')), Ctx()))
    assert result['ok'] is False and result['error_code'] == 'invalid_input' and GATE in result['error']


def test_mcp_other_value_error_is_product_failure(monkeypatch, tmp_path):
    settings(); whisper(monkeypatch)
    from backend import mcp_server
    from backend.services import local_runner
    monkeypatch.setattr(local_runner, 'configure_llm', lambda override: {})
    srt = tmp_path / 's.srt'; srt.write_text(SRT, encoding='utf-8')

    def bad_pipeline(*a, **k):
        raise ValueError('invalid literal for int()')
    monkeypatch.setattr(local_runner, 'run_pipeline', bad_pipeline)
    req = local_runner.RunRequest(video=media(tmp_path / 'v.mp4'), srt=srt, register_db=False, project_id='mcp-valueerror')
    job = mcp_server._run_job(req, None, True)
    assert job['status'] == 'failed' and job['error_code'] == 'failed'


def test_cli_other_value_error_is_not_invalid_input(monkeypatch, tmp_path):
    settings(); whisper(monkeypatch)
    from backend import cli
    from backend.services import local_runner
    monkeypatch.setattr(local_runner, 'configure_llm', lambda override: {})

    def bad_prepare(req, link=True):
        raise ValueError('bug inside prepare')
    monkeypatch.setattr(local_runner, 'prepare_project', bad_prepare)
    with pytest.raises(ValueError, match='bug inside prepare'):
        cli.main(['run', str(media(tmp_path / 'v.mp4')), '--json', '--no-db'])


# ---- 78: quick_output blocked before any project exists
def test_quick_output_blocked_before_project_creation(monkeypatch, tmp_path):
    settings(); whisper(monkeypatch)
    from backend.services import quick_output_runner
    created = []
    from backend.services.project_service import ProjectService
    monkeypatch.setattr(ProjectService, 'create_project', lambda *a, **k: created.append(1))
    with pytest.raises(readiness.TranscriptionNotReady, match=GATE):
        quick_output_runner.start(str(media(tmp_path / 'v.mp4')), ['douyin'])
    assert created == []
    assert project_dirs(tmp_path) == []
