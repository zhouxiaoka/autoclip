"""1.5.8 R17 60-63: every start path shares the local-transcription gate; staging is always cleaned up."""
import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.services import ai_model_settings as ai
from backend.services import whisper_runtime
from backend.services.studio import readiness

GATE = '需要先安装本地转写'
WAIT = '等待安装完成'


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"analytics":false,"crash_reports":false}')
    monkeypatch.setattr(readiness, 'ensure_analysis_usable', lambda: None)


def media(path, seconds=40):
    if not shutil.which('ffmpeg'):
        pytest.skip('ffmpeg required')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', f'color=c=gray:s=160x90:d={seconds}',
                    '-f', 'lavfi', '-i', f'sine=frequency=440:duration={seconds}', '-shortest', '-pix_fmt', 'yuv420p', str(path)], check=True)
    return path


def settings(provider='whisper_local'):
    transcription = ai.Transcription(provider='cloud', model='whisper-1', connection_id='asr') if provider == 'cloud' else ai.Transcription(provider=provider)
    ai.save(ai.ModelSettings(
        connections=[ai.Connection(id='a', name='A', provider='ollama', validation_status='ok'),
                     ai.Connection(id='asr', name='ASR', provider='openai', validation_status='ok')],
        analysis=ai.Assignment(connection_id='a', model='local-text', capability='text'),
        transcription=transcription, analysis_mode='subtitle'))


def whisper(monkeypatch, status):
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda *a, **k: {'status': status})


# ---- 61: installing blocks with its own prompt
def test_installing_blocks_with_wait_prompt(monkeypatch, tmp_path):
    settings(); whisper(monkeypatch, 'installing')
    with pytest.raises(ValueError, match=WAIT):
        readiness.ensure_local_transcription_for_import(srt_available=False, video=media(tmp_path / 'v.mp4'))


# ---- 63: cloud transcription really configured -> never gated
def test_cloud_transcription_config_is_not_gated(monkeypatch, tmp_path):
    settings('cloud'); whisper(monkeypatch, 'missing')
    assert ai.load().transcription.provider == 'cloud'
    readiness.ensure_local_transcription_for_import(srt_available=False, video=media(tmp_path / 'v.mp4'))
    readiness.ensure_local_transcription_for_paths(tmp_path / 'v.mp4')


# ---- studio /analyze (analyze_again) and /plan (re-plan)
@pytest.fixture
def studio_api(monkeypatch, tmp_path):
    from backend.api.v1 import studio as api
    video = media(tmp_path / 'raw' / 'input.mp4') if (tmp_path / 'raw').mkdir() is None else None

    class P:
        processing_config = {}
        project_metadata = {}
    monkeypatch.setattr(api, 'project_or_404', lambda *a, **k: P())
    monkeypatch.setattr(api.jobs, 'source', lambda pid: video)
    monkeypatch.setattr(api.store, 'read', lambda pid, **k: {})
    started = []
    monkeypatch.setattr(api.jobs, 'inspect_project', lambda *a, **k: started.append(1) or 'run')
    app = FastAPI(); app.include_router(api.router)
    return TestClient(app), started, video


@pytest.mark.parametrize('method,path', [('post', '/p1/analyze'), ('put', '/p1/plan')])
@pytest.mark.parametrize('status,prompt', [('missing', GATE), ('installing', WAIT)])
def test_studio_rerun_paths_are_gated(monkeypatch, studio_api, method, path, status, prompt):
    client, started, video = studio_api
    settings(); whisper(monkeypatch, status)
    r = getattr(client, method)(path, **({'json': {}} if method == 'put' else {}))
    assert r.status_code == 422 and prompt in r.text
    assert started == []


@pytest.mark.parametrize('method,path', [('post', '/p1/analyze'), ('put', '/p1/plan')])
def test_studio_rerun_paths_pass_with_subtitle(monkeypatch, studio_api, method, path):
    client, started, video = studio_api
    (video.parent / 'input.srt').write_text('1\n00:00:00,000 --> 00:00:02,000\nhi\n', encoding='utf-8')
    settings(); whisper(monkeypatch, 'missing')
    r = getattr(client, method)(path, **({'json': {}} if method == 'put' else {}))
    assert r.status_code == 200, r.text
    assert started == [1]


# ---- 62: staging cleanup
def test_import_staging_removed_on_mid_upload_error(tmp_path):
    from backend.api.v1 import studio as api

    class Broken:
        async def read(self, n):
            raise ConnectionResetError('client went away')
    with pytest.raises(ConnectionResetError):
        asyncio.run(api.stage_upload(Broken(), b'abc', '.mp4'))
    staging = tmp_path / 'import-staging'
    assert not staging.exists() or not any(staging.iterdir())


def test_import_staging_removed_when_project_creation_fails_after_pass(monkeypatch, tmp_path):
    from backend.api.v1 import studio as api
    settings(); whisper(monkeypatch, 'missing')
    # passes the gate only because the source is too short (no Whisper needed) -> staged upload is kept for the project
    short = media(tmp_path / 'short.mp4', 2)

    def boom(*a, **k):
        raise RuntimeError('db down')
    monkeypatch.setattr(api.ProjectService, 'create_project', boom)
    app = FastAPI(); app.include_router(api.router)
    with TestClient(app, raise_server_exceptions=False) as client:
        r = client.post('/import', files={'video': ('a.mp4', short.read_bytes(), 'video/mp4')}, data={'auto_start': 'true'})
    assert r.status_code == 500
    staging = tmp_path / 'import-staging'
    assert staging.exists() and not any(staging.iterdir())


# ---- legacy HTTP paths
def test_projects_upload_is_gated_before_creating_a_project(monkeypatch, tmp_path):
    from backend.api.v1 import projects as api
    settings(); whisper(monkeypatch, 'missing')
    created = []

    class Svc:
        db = None
        def create_project(self, *a, **k):
            created.append(1)
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[api.get_project_service] = lambda: Svc()
    with TestClient(app) as client:
        r = client.post('/upload', files={'video_file': ('a.mp4', media(tmp_path / 'v.mp4').read_bytes(), 'video/mp4')}, data={'project_name': 'x'})
    assert r.status_code == 422 and GATE in r.text
    assert created == []
    assert not any((tmp_path / 'import-staging').glob('*'))


@pytest.fixture
def raw_project(tmp_path):
    from backend.core.path_utils import get_project_raw_directory
    pid = 'proj-gate-1'
    media(get_project_raw_directory(pid) / 'input.mp4')
    return pid


def test_processing_process_is_gated(monkeypatch, raw_project):
    from backend.api.v1 import processing as api
    settings(); whisper(monkeypatch, 'missing')
    called = []

    class Svc:
        def process_project(self, pid):
            called.append(pid)
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[api.get_processing_service] = lambda: Svc()
    r = TestClient(app).post(f'/projects/{raw_project}/process')
    assert r.status_code == 422 and GATE in r.text and called == []


def test_projects_process_and_retry_are_gated(monkeypatch, raw_project):
    from backend.api.v1 import projects as api
    from backend.core.path_utils import get_project_raw_directory
    settings(); whisper(monkeypatch, 'missing')
    video = get_project_raw_directory(raw_project) / 'input.mp4'

    class Status:
        value = 'failed'

    class Proj:
        status = Status(); video_path = str(video); processing_config = {}; project_metadata = {}
    statuses = []

    class Svc:
        db = None
        def get(self, pid):
            return Proj()

        def get_project(self, pid):
            return Proj()
        def update_project_status(self, *a):
            statuses.append(a)
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[api.get_project_service] = lambda: Svc()
    app.dependency_overrides[api.get_processing_service] = lambda: object()
    client = TestClient(app)
    for path in (f'/{raw_project}/process', f'/{raw_project}/retry'):
        r = client.post(path)
        assert r.status_code == 422 and GATE in r.text, (path, r.status_code, r.text)
    assert statuses == []


def test_smart_retry_processing_only_is_gated(monkeypatch, raw_project):
    from backend.api.v1 import enhanced_retry as api
    settings(); whisper(monkeypatch, 'missing')
    called = []

    async def processing_only(*a, **k):
        called.append(1)
        return {}
    monkeypatch.setattr(api, 'retry_processing_only', processing_only)

    class Q:
        def filter(self, *a):
            return self
        def first(self):
            return object()

    class DB:
        def query(self, *a):
            return Q()
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[api.get_db] = lambda: DB()
    r = TestClient(app).post(f'/retry/projects/{raw_project}/smart-retry', json={'strategy': 'processing_only'})
    assert r.status_code == 422 and GATE in r.text and called == []


# ---- CLI / MCP run
def test_local_runner_cli_and_mcp_return_clear_error(monkeypatch, tmp_path):
    from backend.services import local_runner
    settings(); whisper(monkeypatch, 'missing')
    video = media(tmp_path / 'v.mp4')
    req = local_runner.RunRequest(video=video, register_db=False, project_id='cli-gate-1')
    with pytest.raises(ValueError, match=GATE):
        local_runner.prepare_project(req)
    from backend import mcp_server
    monkeypatch.setattr(local_runner, 'configure_llm', lambda override: {})
    job = mcp_server._run_job(local_runner.RunRequest(video=video, register_db=False, project_id='mcp-gate-1'), None, True)
    assert job['status'] == 'failed' and job['error_code'] == 'invalid_input' and GATE in job['error']


def test_tasks_retry_video_processing_is_gated_before_reset(monkeypatch, tmp_path):
    from backend.api.v1 import tasks as api
    settings(); whisper(monkeypatch, 'missing')
    video = media(tmp_path / 'v.mp4')
    updates = []

    class Task:
        task_type = 'video_processing'; project_id = 'p'; task_config = {'input_video_path': str(video)}

    class Svc:
        def __init__(self, db):
            pass
        def get_task_by_id(self, tid):
            return Task()
        def update_task(self, *a):
            updates.append(a)
    monkeypatch.setattr(api, 'TaskService', Svc)
    app = FastAPI(); app.include_router(api.router)
    app.dependency_overrides[api.get_db] = lambda: None
    r = TestClient(app).post('/t1/retry')
    assert r.status_code == 422 and GATE in r.text and updates == []
