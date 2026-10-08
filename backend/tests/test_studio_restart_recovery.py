"""RC156 Win QA #13: a Studio run killed with the app (LLM stage or render) ends failed with a reason after restart."""
import json
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.base import Base
from backend.models.project import Project, ProjectStatus
from backend.schemas.base import PaginationParams
from backend.services.project_service import ProjectService
from backend.services.studio import store
from backend.services.studio.restart_recovery import reconcile_interrupted_projects

OLD = 'previous-process'


@pytest.fixture
def sessions(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr('backend.core.database.SessionLocal', factory)
    yield factory
    engine.dispose()


def _project(sessions, data, *, status=ProjectStatus.PROCESSING, project_id='p', auto=True, metadata=None):
    (store.directory(project_id) / 'metadata').mkdir(parents=True)
    (store.directory(project_id) / 'metadata' / 'studio.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    with sessions() as db:
        db.add(Project(id=project_id, name=project_id, status=status, processing_config={'smart_import': {'auto_start': auto}},
                       project_metadata=metadata or {}))
        db.commit()


def _disk(project_id='p'):
    return json.loads((store.directory(project_id) / 'metadata' / 'studio.json').read_text(encoding='utf-8'))


def _row(sessions, project_id='p'):
    with sessions() as db:
        return ProjectService(db).get_project_with_stats(project_id)


def _production(instance=OLD, stage='production'):
    return {'generation': {'status': stage, 'auto_start': True, 'requested_platforms': ['douyin']},
            'analysis': {'status': 'running', 'phase': stage, 'run_id': 'run-1', 'message': '正在制作可发布成片', 'instance': instance},
            'drafts': [], 'jobs': [], 'output_variants': []}


@pytest.mark.parametrize('stage', ['production', 'screening'])
def test_startup_closes_a_run_killed_during_the_llm_stage(sessions, stage):
    _project(sessions, _production(stage=stage))
    assert reconcile_interrupted_projects(sessions) == ['p']
    disk = _disk()
    assert disk['generation']['status'] == 'failed'
    assert disk['generation']['error'] == store.RESTART_MESSAGE == '服务已重启，请重新生成'
    assert disk['generation']['error_code'] == 'service_restarted'
    assert disk['generation']['failure_stage'] == stage
    assert disk['analysis']['status'] == 'failed' and disk['analysis']['error'] == store.RESTART_MESSAGE
    assert 'message' not in disk['analysis'] and 'instance' not in disk['analysis']  # no stale 「正在制作可发布成片」
    assert disk['analysis']['run_id'] == 'run-1'
    row = _row(sessions)
    assert row.status.value == 'failed'
    assert row.error_message == store.RESTART_MESSAGE and row.error_code == 'service_restarted'
    # Idempotent: a second restart changes nothing.
    assert reconcile_interrupted_projects(sessions) == []


def test_previous_release_shape_completed_with_zero_clips_is_failed(sessions):
    # Before #8 the clips-only child run wrote completed while generation stayed in production.
    _project(sessions, _production(), status=ProjectStatus.COMPLETED)
    reconcile_interrupted_projects(sessions)
    assert _row(sessions).status.value == 'failed'


def test_home_list_heals_an_interrupted_run_without_the_startup_pass(sessions):
    _project(sessions, _production())
    with sessions() as db:
        listing = ProjectService(db).get_projects_paginated(PaginationParams())
    item = listing.items[0]
    assert item.status.value == 'failed' and item.error_message == store.RESTART_MESSAGE
    assert _disk()['generation']['status'] == 'failed'


def test_run_owned_by_this_process_is_left_running(sessions):
    _project(sessions, _production(instance=store.INSTANCE))
    assert reconcile_interrupted_projects(sessions) == []
    assert _disk()['generation']['status'] == 'production'
    with sessions() as db:
        ProjectService(db).get_projects_paginated(PaginationParams())
    assert _row(sessions).status.value == 'processing'


def test_live_cli_producer_is_not_failed_by_the_desktop(sessions):
    import psutil
    data = _production()
    data['generation']['producer'] = {'pid': os.getppid(), 'created_at': psutil.Process(os.getppid()).create_time()}
    _project(sessions, data)
    assert reconcile_interrupted_projects(sessions) == []
    assert store.read('p')['analysis']['status'] == 'running'
    assert _disk()['generation']['status'] == 'production'


def test_dead_cli_producer_is_recovered(sessions):
    data = _production()
    data['generation']['producer'] = {'pid': 2 ** 22 + 12345, 'created_at': 1.0}
    _project(sessions, data)
    assert reconcile_interrupted_projects(sessions) == ['p']
    assert _row(sessions).status.value == 'failed'


def test_killed_during_render_has_a_reason_on_the_project(sessions):
    # RC156 case 4b: previously failed with an empty error_message.
    _project(sessions, {
        'generation': {'status': 'rendering', 'auto_start': True},
        'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'r', 'instance': OLD},
        'drafts': [{'id': 'd1'}, {'id': 'd2'}],
        'jobs': [{'job_id': 'j1', 'status': 'running', 'instance': OLD}],
        'output_variants': [{'id': 'v1', 'render_job_id': 'j1', 'status': 'running'},
                            {'id': 'v2', 'status': 'queued'}]})
    assert reconcile_interrupted_projects(sessions) == ['p']
    disk = _disk()
    assert [v['status'] for v in disk['output_variants']] == ['failed', 'failed']
    assert {v['error_code'] for v in disk['output_variants']} == {'service_restarted'}
    assert disk['jobs'][0]['error_code'] == 'service_restarted'
    assert disk['generation']['status'] == 'failed' and disk['generation']['error'] == store.RESTART_MESSAGE
    assert disk['generation']['error_code'] == 'service_restarted'
    assert disk['analysis']['error'] == store.RESTART_MESSAGE
    row = _row(sessions)
    assert row.status.value == 'failed' and row.error_message == store.RESTART_MESSAGE and row.error_code == 'service_restarted'


def test_render_killed_after_one_saved_video_is_partial_and_keeps_it(sessions):
    _project(sessions, {
        'generation': {'status': 'rendering', 'auto_start': True},
        'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'r', 'instance': OLD},
        'drafts': [{'id': 'd1'}, {'id': 'd2'}],
        'jobs': [{'job_id': 'j1', 'status': 'completed', 'instance': OLD}, {'job_id': 'j2', 'status': 'running', 'instance': OLD}],
        'output_variants': [{'id': 'v1', 'render_job_id': 'j1', 'status': 'completed'},
                            {'id': 'v2', 'render_job_id': 'j2', 'status': 'running'}]})
    reconcile_interrupted_projects(sessions)
    disk = _disk()
    assert disk['generation']['status'] == 'partial' and disk['generation']['completed_variant_count'] == 1
    assert disk['output_variants'][0]['status'] == 'completed'


def test_project_reason_prefers_the_generation_over_a_stale_task_error(sessions):
    from backend.models.task import Task, TaskStatus, TaskType
    _project(sessions, _production())
    with sessions() as db:
        db.add(Task(project_id='p', name='old', task_type=TaskType.VIDEO_PROCESSING, status=TaskStatus.FAILED, error_message='上一次的旧错误'))
        db.commit()
    reconcile_interrupted_projects(sessions)
    assert _row(sessions).error_message == store.RESTART_MESSAGE


def test_manual_confirmation_run_is_failed_and_keeps_its_wording(sessions):
    data = _production()
    data['generation'] = {'status': 'awaiting_confirmation', 'auto_start': False}
    data['analysis']['message'] = '开始制作所选内容'
    _project(sessions, data, auto=False)
    assert reconcile_interrupted_projects(sessions) == ['p']
    disk = _disk()
    assert disk['analysis']['status'] == 'failed' and disk['analysis']['error'] == '服务已重启，请重试分析'
    assert disk['analysis']['error_code'] == 'service_restarted' and 'message' not in disk['analysis']
    row = _row(sessions)
    assert row.status.value == 'failed' and row.error_message == '服务已重启，请重试分析'


def test_one_unreadable_project_does_not_stop_the_others(sessions):
    _project(sessions, _production(), project_id='good')
    (store.directory('bad') / 'metadata').mkdir(parents=True)
    (store.directory('bad') / 'metadata' / 'studio.json').write_text('{not json', encoding='utf-8')
    with sessions() as db:
        db.add(Project(id='bad', name='bad', status=ProjectStatus.PROCESSING, processing_config={'smart_import': {'auto_start': True}}))
        db.commit()
    assert reconcile_interrupted_projects(sessions) == ['good']


def test_restart_code_is_known_and_never_reported():
    from backend.core import sentry_setup
    assert 'service_restarted' in sentry_setup.STUDIO_ERROR_CODES
    assert 'service_restarted' in sentry_setup.UNREPORTED_STUDIO_ERROR_CODES
