"""1.5.8 R19 #112-#115: tasks retry gate, single quick-output decision, queue SRT parity, no-settings Studio gate."""
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
    monkeypatch.setattr(whisper_runtime, 'get_status', lambda *a, **k: {'status': 'missing'})


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


# ---- tasks retry / submit
class _Task:
    task_type = 'video_processing'
    project_id = 'p'

    def __init__(self, video, srt=None):
        self.task_config = {'input_video_path': str(video), **({'input_srt_path': str(srt)} if srt else {})}


def _call(monkeypatch, task, action):
    from backend.api.v1 import tasks as api
    queued, updates = [], []

    class Svc:
        def __init__(self, db):
            pass

        def get_task_by_id(self, tid):
            return task

        def update_task(self, *a):
            updates.append(a)

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
    with TestClient(app, raise_server_exceptions=False) as client:
        return client.post(f'/t1/{action}'), queued, updates


def test_112_retry_gated_before_reset_and_queue(monkeypatch, tmp_path):
    settings()
    r, queued, updates = _call(monkeypatch, _Task(media(tmp_path / 'v.mp4')), 'retry')
    assert r.status_code == 422 and GATE in r.text
    assert queued == [] and updates == []


def test_112_retry_with_queued_srt_passes(monkeypatch, tmp_path):
    settings()
    srt = tmp_path / 'sub.srt'; srt.write_text(SRT, encoding='utf-8')
    r, queued, updates = _call(monkeypatch, _Task(media(tmp_path / 'v.mp4'), srt), 'retry')
    assert r.status_code == 200, r.text
    assert len(queued) == 1 and queued[0]['input_srt_path'] == str(srt)


@pytest.mark.parametrize('action', ['retry', 'submit'])
def test_112_only_the_gate_maps_to_422(monkeypatch, tmp_path, action):
    """Any other ValueError while checking is a server failure, not a user-facing gate refusal."""
    settings()
    monkeypatch.setattr(readiness, 'ensure_local_transcription_for_paths', lambda *a, **k: (_ for _ in ()).throw(ValueError('bug')))
    r, queued, updates = _call(monkeypatch, _Task(media(tmp_path / 'v.mp4')), action)
    assert r.status_code == 500
    assert queued == []


@pytest.mark.parametrize('action', ['retry', 'submit'])
def test_114_input_srt_beside_video_does_not_count_when_queue_gets_none(monkeypatch, tmp_path, action):
    settings()
    video = media(tmp_path / 'raw' / 'input.mp4')
    (video.parent / 'input.srt').write_text(SRT, encoding='utf-8')  # queue receives input_srt_path=None
    r, queued, updates = _call(monkeypatch, _Task(video), action)
    assert r.status_code == 422 and GATE in r.text
    assert queued == []


# ---- quick output: one decision for the route it really runs
@pytest.fixture
def quick(monkeypatch):
    from backend.services import quick_output_runner
    from backend.services.project_service import ProjectService
    from backend.services.studio import jobs
    created, inspected = [], []

    class Proj:
        id = 'quick-r19'
        name = 'q'
        video_path = None

    def create(self, *a, **k):
        created.append(1)
        return Proj()
    monkeypatch.setattr(ProjectService, 'create_project', create)
    monkeypatch.setattr(jobs, 'inspect_project', lambda *a, **k: inspected.append(a))
    import backend.core.database as database

    class DB:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def commit(self):
            pass
    monkeypatch.setattr(database, 'SessionLocal', lambda: DB())
    monkeypatch.setattr(database, 'create_tables', lambda: None)
    return quick_output_runner, created, inspected


def test_113_visual_quick_output_is_not_rejected_by_inner_content_gate(quick, tmp_path):
    runner, created, inspected = quick
    settings('visual')  # Studio visual analysis needs no ASR
    pid = runner.start(str(media(tmp_path / 'v.mp4')), ['douyin'])
    assert pid == 'quick-r19' and created == [1] and len(inspected) == 1


def test_113_rejected_quick_output_leaves_no_project(quick, tmp_path):
    runner, created, inspected = quick
    settings('subtitle')
    with pytest.raises(readiness.TranscriptionNotReady, match=GATE):
        runner.start(str(media(tmp_path / 'v.mp4')), ['douyin'])
    assert created == [] and inspected == []
    from backend.core.path_utils import get_projects_directory
    root = get_projects_directory()
    assert not root.exists() or not any(root.iterdir())


def test_113_quick_output_checks_the_gate_once(quick, tmp_path, monkeypatch):
    runner, created, inspected = quick
    settings('visual')
    seen = []
    real = readiness.ensure_local_transcription_for_import
    monkeypatch.setattr(readiness, 'ensure_local_transcription_for_import', lambda **k: seen.append(k.get('route')) or real(**k))
    runner.start(str(media(tmp_path / 'v.mp4')), ['douyin'])
    assert seen == ['studio']


# ---- 115: Studio with no settings document still blocks before creating a project
def test_115_studio_import_without_settings_file_is_blocked(monkeypatch, tmp_path):
    assert ai.load() is None
    from backend.api.v1 import studio as api
    created = []
    monkeypatch.setattr(api.ProjectService, 'create_project', lambda *a, **k: created.append(1))
    app = FastAPI(); app.include_router(api.router)
    with TestClient(app) as client:
        r = client.post('/import', files={'video': ('a.mp4', media(tmp_path / 'v.mp4').read_bytes(), 'video/mp4')},
                        data={'auto_start': 'true'})
    assert r.status_code == 422 and GATE in r.text
    assert created == []
    staging = tmp_path / 'import-staging'
    assert not staging.exists() or not any(staging.iterdir())
