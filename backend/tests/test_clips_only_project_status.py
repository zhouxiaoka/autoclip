"""RC156 Win QA #8: a Studio clips-only sub-run must not settle the project before its videos render.

Studio calls the content pipeline with clips_only=True and then renders; the project index terminal
belongs to Studio (mark_project / sync_project_completion). The legacy full pipeline keeps writing it.
"""
import json
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.base import Base
from backend.models.project import Project, ProjectStatus
from backend.models.task import Task, TaskStatus


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    from backend.tasks import processing
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)

    @contextmanager
    def scope():
        session = sessions()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    monkeypatch.setattr(processing, 'session_scope', scope)
    monkeypatch.setattr('backend.core.database.SessionLocal', sessions)
    monkeypatch.setattr(processing, 'run_async_notification', lambda coro: coro.close())
    with sessions() as session:
        session.add(Project(id='p', name='synthetic', status=ProjectStatus.PROCESSING,
                            processing_config={'smart_import': {'auto_start': True}}))
        session.commit()
    yield sessions
    engine.dispose()


def run(monkeypatch, outcome, clips_only):
    from backend.tasks import processing

    class Adapter:
        async def process_project_sync(self, video, srt, clips_only=False):
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

    monkeypatch.setattr('backend.services.simple_pipeline_adapter.create_simple_pipeline_adapter', lambda *args: Adapter())
    return processing.process_video_pipeline.apply(kwargs={
        'project_id': 'p', 'input_video_path': 'synthetic.mp4', 'clips_only': clips_only,
    })


def project_and_task(sessions):
    with sessions() as session:
        project = session.get(Project, 'p')
        task = session.query(Task).filter(Task.project_id == 'p').one()
        return project.status, project.completed_at, task.status


def test_clips_only_success_leaves_project_processing_for_studio(db, monkeypatch):
    result = run(monkeypatch, {'status': 'succeeded', 'result': {'titled_clips': [{'id': '1'}]}}, True).get()
    assert result['success'] is True
    status, completed_at, task_status = project_and_task(db)
    assert task_status is TaskStatus.COMPLETED
    assert status is ProjectStatus.PROCESSING
    assert completed_at is None


def test_clips_only_failure_leaves_terminal_to_studio(db, monkeypatch):
    result = run(monkeypatch, {'status': 'failed', 'error': 'synthetic', 'stage': 'ANALYZE'}, True).get()
    assert result['success'] is False
    status, _, task_status = project_and_task(db)
    assert task_status is TaskStatus.FAILED
    assert status is ProjectStatus.PROCESSING


def test_clips_only_exception_leaves_terminal_to_studio(db, monkeypatch):
    with pytest.raises(RuntimeError):
        run(monkeypatch, RuntimeError('synthetic'), True).get()
    status, _, task_status = project_and_task(db)
    assert task_status is TaskStatus.FAILED
    assert status is ProjectStatus.PROCESSING


def test_full_pipeline_still_settles_the_project(db, monkeypatch):
    run(monkeypatch, {'status': 'succeeded', 'result': {}}, False).get()
    status, completed_at, _ = project_and_task(db)
    assert status is ProjectStatus.COMPLETED
    assert completed_at is not None


def test_full_pipeline_failure_still_fails_the_project(db, monkeypatch):
    run(monkeypatch, {'status': 'failed', 'error': 'synthetic'}, False).get()
    assert project_and_task(db)[0] is ProjectStatus.FAILED


def test_project_completes_only_after_studio_generation_terminal(db, monkeypatch, tmp_path):
    from backend.services.studio import store
    from backend.services.studio.project_completion import sync_project_completion
    run(monkeypatch, {'status': 'succeeded', 'result': {'titled_clips': [{'id': '1'}]}}, True).get()
    (store.directory('p') / 'metadata').mkdir(parents=True, exist_ok=True)
    path = store.directory('p') / 'metadata' / 'studio.json'
    rendering = {'generation': {'status': 'rendering', 'auto_start': True}, 'analysis': {'status': 'completed'},
                 'drafts': [{'id': 'd'}], 'output_variants': [{'id': 'v', 'status': 'running'}]}
    path.write_text(json.dumps(rendering), encoding='utf-8')
    assert sync_project_completion('p') is False
    assert project_and_task(db)[0] is ProjectStatus.PROCESSING
    done = {**rendering, 'generation': {'status': 'completed', 'auto_start': True},
            'output_variants': [{'id': 'v', 'status': 'completed'}]}
    path.write_text(json.dumps(done), encoding='utf-8')
    assert sync_project_completion('p') is True
    status, completed_at, _ = project_and_task(db)
    assert status is ProjectStatus.COMPLETED
    assert completed_at is not None
