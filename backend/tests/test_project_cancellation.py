"""RC156 Win QA #12: deleting a project mid-generation must stop its workers and clear its directory.

Repro: DELETE during Studio rendering returned 200 / 404 on the APIs, but the render kept
writing the mp4 (13 s later), then cover + studio.json (3 min later); 14 minutes later the
project directory still had 24 files / 9.2 MB.
"""
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core import project_cancellation as cancel


@pytest.fixture(autouse=True)
def _isolation(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    cancel._cancelled.clear()
    cancel._stopped.clear()
    cancel._processes.clear()
    cancel._leaders.clear()
    cancel._temporary.clear()
    cancel._binds.clear()
    cancel._round_ignored.clear()
    yield
    cancel._cancelled.clear()
    cancel._stopped.clear()
    cancel._processes.clear()
    cancel._leaders.clear()
    cancel._temporary.clear()
    cancel._binds.clear()
    cancel._round_ignored.clear()


def _project(path: Path, project_id='p-del'):
    folder = path / 'data' / 'projects' / project_id
    (folder / 'raw').mkdir(parents=True)
    (folder / 'metadata').mkdir()
    (folder / 'output' / 'studio').mkdir(parents=True)
    (folder / 'raw' / 'input.mp4').write_bytes(b'x')
    (folder / 'metadata' / 'studio.json').write_text('{"schema_version":2,"drafts":[],"jobs":[],"analysis":null,"output_variants":[]}', encoding='utf-8')
    return folder


def test_stop_keeps_finished_video_and_raises_job_stopped(tmp_path):
    folder = _project(tmp_path, 'p-stop')
    finished = folder / 'output' / 'studio' / 'done.mp4'
    partial = folder / 'output' / 'studio' / 'done.part.mp4'
    finished.write_bytes(b'keep')
    partial.write_bytes(b'partial')
    cancel.note_temporary(folder / 'scratch.tmp', 'p-stop')
    (folder / 'scratch.tmp').write_text('temp', encoding='utf-8')
    cancel.stop('p-stop')
    with pytest.raises(cancel.JobStopped) as caught:
        cancel.checkpoint('p-stop')
    assert caught.value.project_id == 'p-stop'
    assert not isinstance(caught.value, cancel.ProjectDeleted)
    assert finished.read_bytes() == b'keep'
    assert not partial.exists()
    assert not (folder / 'scratch.tmp').exists()
    assert folder.is_dir()


def test_cancel_raises_at_checkpoints_and_is_not_a_crash():
    cancel.cancel('gone')
    with pytest.raises(cancel.ProjectDeleted) as caught:
        cancel.checkpoint('gone')
    assert caught.value.project_id == 'gone' and '删除' in str(caught.value)
    from backend.core import sentry_setup
    assert sentry_setup.capture_studio_exception(caught.value, 'render') is None


def test_bind_clears_files_written_after_delete(tmp_path):
    folder = _project(tmp_path)
    leftover = folder / 'output' / 'studio' / 'late.mp4'
    with cancel.bind('p-del'):
        cancel.cancel('p-del')
        leftover.write_bytes(b'mid-step write after delete')
        assert leftover.is_file()
        with pytest.raises(cancel.ProjectDeleted):
            cancel.checkpoint()
    assert not folder.exists()


def test_delete_kills_a_bound_ffmpeg_child(tmp_path):
    folder = _project(tmp_path)
    started = threading.Event()
    finished = []

    def worker():
        with cancel.bind('p-del'):
            try:
                # A long child that exit-on-signal; the delete must kill it before the sleep ends.
                cancel.run(['bash', '-c', 'echo ready; sleep 30'], capture_output=True, timeout=60)
                finished.append('ok')
            except cancel.ProjectDeleted:
                finished.append('deleted')
            except Exception as error:
                finished.append(type(error).__name__)

    # Patch cancel.run to signal readiness right after Popen registration by wrapping.
    original = cancel.run

    def watched(cmd, **kwargs):
        started.set()
        return original(cmd, **kwargs)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(cancel, 'run', watched)
    try:
        thread = threading.Thread(target=worker)
        thread.start()
        assert started.wait(5)
        time.sleep(0.2)  # let the child start
        cancel.cancel('p-del')
        thread.join(10)
        assert not thread.is_alive()
        assert finished == ['deleted']
        assert not folder.exists()
    finally:
        monkeypatch.undo()


def test_store_write_and_change_refuse_a_cancelled_project(tmp_path):
    from backend.services.studio import store
    folder = _project(tmp_path)
    store.write('p-del', {'schema_version': 2, 'drafts': [], 'jobs': [], 'analysis': None, 'output_variants': [], 'events': []})
    cancel.cancel('p-del')
    with pytest.raises(cancel.ProjectDeleted):
        store.write('p-del', {'schema_version': 2, 'drafts': [], 'jobs': [], 'analysis': None, 'output_variants': [], 'events': []})
    with pytest.raises(cancel.ProjectDeleted):
        store.change('p-del', lambda data: data.update(drafts=[{'id': 'x'}]))
    # The binder is what clears the directory; cancel alone leaves it for the worker to finish.
    assert folder.exists()


def test_llm_call_and_vision_stop_after_cancel(tmp_path, monkeypatch):
    from backend.core.llm_manager import LLMManager
    from backend.services.studio import intelligence
    cancel.cancel('p-del')
    with cancel.bind('p-del'):
        with pytest.raises(cancel.ProjectDeleted):
            LLMManager().call('hello')
        with pytest.raises(cancel.ProjectDeleted):
            intelligence.vision_call([{'type': 'text', 'text': 'x'}], config={'base_url': 'http://x', 'model': 'm'})


def test_llm_usage_never_recreates_a_deleted_project_directory(tmp_path):
    from backend.core import llm_usage
    folder = cancel.project_directory('p-del')
    assert not folder.exists()
    with cancel.bind('p-del'), llm_usage.tracking('p-del'):
        with llm_usage.timed('render'):
            cancel.cancel('p-del')  # deleted while the step runs: its timing row is not written
            llm_usage.record('m', {'prompt_tokens': 1, 'completion_tokens': 1}, prompt_chars=1, completion_chars=1)
        with pytest.raises(cancel.ProjectDeleted):
            with llm_usage.timed('next-step'):
                pass
    assert not folder.exists()


def test_studio_render_worker_stops_without_writing_an_mp4(tmp_path, monkeypatch):
    from backend.services.studio import jobs, store
    from backend.services.studio.models import Draft, Scene
    folder = _project(tmp_path)
    called = []

    def fake_render(project_id, video, draft, job_id, progress, *, brand_outro=False):
        called.append('start')
        cancel.cancel(project_id)  # the user deleted mid-render
        cancel.checkpoint(project_id)
        called.append('wrote')
        return {'title': 'x', 'duration': 1, 'width': 64, 'height': 36, 'warnings': [], 'outro_applied': False}

    monkeypatch.setattr(jobs, 'render_draft', fake_render)
    monkeypatch.setattr(jobs, 'source', lambda pid: folder / 'raw' / 'input.mp4')
    monkeypatch.setattr(jobs, '_design_covers', lambda *a, **k: called.append('cover'))
    store.write('p-del', {'schema_version': 2, 'drafts': [], 'jobs': [
        {'job_id': 'j1', 'status': 'queued', 'percent': 0, 'draft_id': 'd1', 'title': 't', 'revision': 1,
         'brand_outro': False, 'created_at': store.now(), 'instance': store.INSTANCE,
         'snapshot': Draft(id='d1', title='t', scenes=[Scene(id='s', start=0, end=1)], subtitles=False).model_dump()}
    ], 'analysis': None, 'output_variants': [], 'events': []})
    draft = Draft(id='d1', title='t', scenes=[Scene(id='s', start=0, end=1)], subtitles=False)
    # _tracked catches ProjectDeleted and returns None; the binder then clears leftovers.
    assert jobs._render('p-del', draft, 'j1') is None
    assert called == ['start']  # never reached the write / cover
    assert not folder.exists()
    assert not list((tmp_path / 'data' / 'projects').glob('*'))


def test_pipeline_adapter_stops_before_llm_after_cancel(tmp_path, monkeypatch):
    from backend.services import simple_pipeline_adapter as adapter_module
    adapter = adapter_module.SimplePipelineAdapter('p-del', 't')
    reached = []
    monkeypatch.setattr(adapter, '_preflight_llm', lambda: reached.append('llm') or cancel.cancel('p-del'))
    monkeypatch.setattr(adapter, '_generate_subtitle_automatically', lambda *a, **k: reached.append('srt'))
    cancel.cancel('p-del')  # already deleted before the adapter starts
    with cancel.bind('p-del'):
        with pytest.raises(cancel.ProjectDeleted):
            import asyncio
            asyncio.run(adapter.process_project_sync(str(tmp_path / 'x.mp4'), None, clips_only=True))
    assert reached == []


def test_delete_project_with_files_cancels_and_clears_directory(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.models import Base, Project
    from backend.models.project import ProjectStatus
    from backend.services.project_service import ProjectService

    folder = _project(tmp_path, 'p-api')
    engine = create_engine('sqlite:///' + str(tmp_path / 'api.sqlite'))
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add(Project(id='p-api', name='Deleting', status=ProjectStatus.COMPLETED, video_path=str(folder / 'raw' / 'input.mp4')))
        db.commit()
        service = ProjectService(db)
        # A bound worker that would write after the delete if cancel did not stop it.
        written = []

        def worker():
            with cancel.bind('p-api'):
                try:
                    for _ in range(50):
                        cancel.checkpoint()
                        time.sleep(0.05)
                    (folder / 'output' / 'studio' / 'late.mp4').write_bytes(b'late')
                    written.append('late')
                except cancel.ProjectDeleted:
                    written.append('stopped')

        thread = threading.Thread(target=worker)
        thread.start()
        time.sleep(0.1)
        assert service.delete_project_with_files('p-api') is True
        thread.join(5)
        assert written == ['stopped']
        assert not folder.exists()
        assert db.query(Project).filter(Project.id == 'p-api').first() is None
    engine.dispose()


def test_delete_restore_when_blocked_by_running_task(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.models import Base, Project, Task
    from backend.models.project import ProjectStatus
    from backend.models.task import TaskStatus, TaskType
    from backend.services.project_service import ProjectService

    folder = _project(tmp_path, 'p-busy')
    engine = create_engine('sqlite:///' + str(tmp_path / 'api.sqlite'))
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add(Project(id='p-busy', name='Busy', status=ProjectStatus.PROCESSING, video_path=str(folder / 'raw' / 'input.mp4')))
        db.add(Task(id='t1', project_id='p-busy', name='导入处理', task_type=TaskType.VIDEO_PROCESSING, status=TaskStatus.RUNNING))
        db.commit()
        assert ProjectService(db).delete_project_with_files('p-busy') is False
        assert not cancel.is_cancelled('p-busy')  # cancelled briefly then restored
        assert folder.exists()
    engine.dispose()


def test_delete_during_render_stops_the_job_and_removes_the_directory(tmp_path, monkeypatch):
    """End-to-end: DELETE during _render must leave no mp4/cover and no project directory."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.models import Base, Project
    from backend.models.project import ProjectStatus
    from backend.services.project_service import ProjectService
    from backend.services.studio import jobs, store
    from backend.services.studio.models import Draft, Scene

    folder = _project(tmp_path)
    draft = Draft(id='d1', title='t', scenes=[Scene(id='s', start=0, end=1)], subtitles=False)
    store.write('p-del', {'schema_version': 2, 'drafts': [], 'events': [], 'analysis': None, 'output_variants': [], 'jobs': [
        {'job_id': 'j1', 'status': 'queued', 'percent': 0, 'draft_id': 'd1', 'title': 't', 'revision': 1, 'brand_outro': False,
         'created_at': store.now(), 'instance': store.INSTANCE, 'snapshot': draft.model_dump()}]})
    engine = create_engine('sqlite:///' + str(tmp_path / 'api.sqlite'))
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add(Project(id='p-del', name='x', status=ProjectStatus.PROCESSING, video_path=str(folder / 'raw' / 'input.mp4')))
        db.commit()

    rendering, deleted, wrote = threading.Event(), threading.Event(), []

    def fake_render(project_id, video, draft, job_id, progress, *, brand_outro=False):
        rendering.set()
        assert deleted.wait(10)
        progress(60)
        out = store.directory(project_id) / 'output' / 'studio'
        out.mkdir(parents=True, exist_ok=True)
        (out / f'{job_id}.mp4').write_bytes(b'mp4')
        wrote.append('mp4')
        return {'title': 't', 'duration': 1, 'width': 64, 'height': 36, 'warnings': [], 'outro_applied': False}

    monkeypatch.setattr(jobs, 'render_draft', fake_render)
    monkeypatch.setattr(jobs, 'source', lambda pid: folder / 'raw' / 'input.mp4')
    monkeypatch.setattr(jobs, '_design_covers', lambda *a, **k: wrote.append('cover'))
    worker = threading.Thread(target=lambda: jobs._render('p-del', draft, 'j1'))
    worker.start()
    assert rendering.wait(10)
    with sessions() as db:
        assert ProjectService(db).delete_project_with_files('p-del') is True
    deleted.set()
    worker.join(10)
    engine.dispose()
    assert wrote == [] and not folder.exists()


def test_a_new_round_after_cancel_is_not_already_stopped(tmp_path):
    import sys
    _project(tmp_path, 'p-redo')
    cancel.stop('p-redo')
    with pytest.raises(cancel.JobStopped):
        cancel.checkpoint('p-redo')
    with cancel.bind('p-redo'):
        cancel.checkpoint()
        result = cancel.run([sys.executable, '-c', 'print(1)'], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0
    assert '1' in result.stdout


def test_disk_marker_stops_the_render_without_a_local_stop(tmp_path):
    import sys
    _project(tmp_path, 'p-mark')
    started = threading.Event()
    finished = []

    def worker():
        with cancel.bind('p-mark'):
            started.set()
            try:
                cancel.run([sys.executable, '-c', 'import time; time.sleep(30)'], timeout=40)
                finished.append('ok')
            except cancel.JobStopped:
                finished.append('stopped')
            except Exception as error:  # noqa: BLE001 - reported by the assertion
                finished.append(type(error).__name__)

    thread = threading.Thread(target=worker)
    thread.start()
    assert started.wait(5)
    time.sleep(0.3)
    assert 'p-mark' not in cancel._stopped
    cancel.write_stop_marker('p-mark')
    thread.join(10)
    assert not thread.is_alive()
    assert finished == ['stopped']


def test_kill_reaches_grandchildren_after_the_leader_exits(tmp_path):
    import os
    import sys
    if os.name == 'nt':
        pytest.skip('killpg is the POSIX path; Windows uses taskkill /T on a live tree')
    marker = tmp_path / 'grand.pid'
    code = (
        'import pathlib, subprocess, sys, time\n'
        'path = pathlib.Path(sys.argv[1])\n'
        'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])\n'
        'path.write_text(str(child.pid))\n'
        'time.sleep(0.2)\n'
    )
    proc = subprocess.Popen([sys.executable, '-c', code, str(marker)], start_new_session=True)
    with cancel._lock:
        cancel._leaders.add(proc.pid)
        cancel._processes.setdefault('p-exit', set()).add(proc)
    try:
        deadline = time.time() + 5
        while proc.poll() is None or not marker.exists():
            assert time.time() < deadline
            time.sleep(0.05)
        grand = int(marker.read_text())
        import psutil
        assert psutil.Process(grand).is_running()
        cancel.stop('p-exit')
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                psutil.Process(grand)
            except psutil.NoSuchProcess:
                break
            time.sleep(0.05)
        else:
            raise AssertionError('grandchild still running')
    finally:
        cancel._leaders.discard(proc.pid)
        cancel._processes.pop('p-exit', None)
        if proc.poll() is None:
            proc.kill()


def test_disk_marker_keeps_a_finished_render_from_being_completed(tmp_path, monkeypatch):
    from backend.services.studio import jobs, store
    from backend.services.studio.models import Draft, Scene
    folder = _project(tmp_path, 'p-mark')
    draft = Draft(id='d1', title='t', scenes=[Scene(id='s', start=0, end=1)], subtitles=False)

    def fake_render(project_id, video, draft, job_id, progress, **kwargs):
        cancel.write_stop_marker(project_id)
        return {'title': 'x', 'duration': 1, 'width': 64, 'height': 36, 'warnings': [], 'outro_applied': False}

    monkeypatch.setattr(jobs, 'render_draft', fake_render)
    monkeypatch.setattr(jobs, 'source', lambda pid: folder / 'raw' / 'input.mp4')
    monkeypatch.setattr(jobs, '_design_covers', lambda *a, **k: None)
    store.write('p-mark', {'schema_version': 2, 'drafts': [], 'jobs': [
        {'job_id': 'j1', 'status': 'queued', 'percent': 0, 'draft_id': 'd1', 'title': 't', 'revision': 1,
         'brand_outro': False, 'created_at': store.now(), 'instance': store.INSTANCE,
         'snapshot': draft.model_dump()}
    ], 'analysis': None, 'output_variants': [], 'events': []})
    assert jobs._render('p-mark', draft, 'j1') is None
    assert store.read('p-mark', recover=False)['jobs'][0]['status'] == 'cancelled'
