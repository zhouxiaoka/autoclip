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
from backend.core.failure_codes import sentence
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
    assert disk['generation']['error'] == store.RESTART_MESSAGE == sentence('service_restarted')
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


@pytest.mark.parametrize('marker,reason', [
    ('user_quit', 'user_quit'),
    ('update', 'update'),
    (None, 'crash'),
    ('unacked', 'unknown'),
    ('parent_lost', 'crash'),
])
def test_reconcile_writes_restart_reason(sessions, marker, reason):
    from backend.services.studio import shutdown_marker
    instance = 'ab' * 16
    shutdown_marker._consumed.clear()
    shutdown_marker._restart_cached.clear()
    if marker == 'unacked':
        root = shutdown_marker._root()
        root.mkdir(parents=True, exist_ok=True)
        (root / instance).write_text('unacked', encoding='ascii')
    elif marker:
        assert shutdown_marker.mark(marker, instance)
    _project(sessions, _production(instance=instance, stage='production'))
    assert reconcile_interrupted_projects(sessions) == ['p']
    generation = _disk()['generation']
    assert generation['error_code'] == 'service_restarted'
    assert generation['failure_stage'] == 'production'
    assert generation['restart_reason'] == reason


def test_reconcile_unknown_instance_keeps_restart_reason_unknown(sessions):
    _project(sessions, _production(instance='previous-process', stage='screening'))
    assert reconcile_interrupted_projects(sessions) == ['p']
    assert _disk()['generation']['restart_reason'] == 'unknown'


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


def test_idle_producer_stays_in_production_until_the_process_exits(sessions):
    """A live, idle producer (~0% CPU, blocked in sleep) is not service_restarted.

    Killing that process is what closes the run. This is the desktop-backend
    distinction the health loop also uses: exit relaunches, an alive process does not.
    """
    import subprocess
    import sys

    import psutil

    proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    try:
        owner = psutil.Process(proc.pid)
        data = _production()
        data['generation']['producer'] = {'pid': proc.pid, 'created_at': owner.create_time()}
        _project(sessions, data)
        assert owner.is_running()
        assert reconcile_interrupted_projects(sessions) == []
        disk = _disk()
        assert disk['generation']['status'] == 'production'
        assert disk['analysis']['status'] == 'running'
        assert disk['analysis']['message'] == '正在制作可发布成片'
        assert _row(sessions).status.value == 'processing'
    finally:
        proc.kill()
        proc.wait(timeout=5)
    assert reconcile_interrupted_projects(sessions) == ['p']
    disk = _disk()
    assert disk['generation']['status'] == 'failed'
    assert disk['generation']['error_code'] == 'service_restarted'
    assert disk['generation']['error'] == store.RESTART_MESSAGE
    assert 'message' not in disk['analysis']
    row = _row(sessions)
    assert row.status.value == 'failed' and row.error_code == 'service_restarted'


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


def test_recover_uses_the_catalog_sentence_for_every_interrupted_piece(sessions):
    catalog = sentence('service_restarted')
    _project(sessions, {
        'generation': {'status': 'rendering', 'auto_start': True},
        'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'r', 'instance': OLD},
        'drafts': [{'id': 'd1'}, {'id': 'd2'}],
        'jobs': [{'job_id': 'j1', 'status': 'running', 'instance': OLD}],
        'output_variants': [
            {'id': 'v1', 'render_job_id': 'j1', 'status': 'running', 'instance': OLD},
            {'id': 'v2', 'status': 'completed', 'cover_job': {'status': 'running', 'instance': OLD}},
        ]})
    assert reconcile_interrupted_projects(sessions) == ['p']
    disk = _disk()
    assert disk['jobs'][0]['error'] == catalog
    assert disk['output_variants'][0]['error'] == catalog
    assert disk['output_variants'][1]['cover_job']['error'] == catalog
    assert disk['generation']['error'] == catalog
    assert _row(sessions).error_message == catalog


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


def test_restart_ignores_orphan_and_partial_files_without_completed_receipts(sessions):
    done_job, done = _linked(1, 'completed')
    cut_job, cut = _linked(2, 'running')
    _project(sessions, _render_run([done_job, cut_job], [done, cut]))
    folder = store.directory('p') / 'output/studio'
    folder.mkdir(parents=True)
    for name in ('j2.mp4', 'j2.part.mp4', 'j2.ready.part.mp4'):
        (folder / name).write_bytes(b'orphan output without a durable completed receipt')
    assert reconcile_interrupted_projects(sessions) == ['p']
    data = _disk()
    assert data['generation']['status'] == 'partial'
    assert data['generation']['completed_variant_count'] == 1
    assert data['output_variants'][1]['status'] == 'failed'
    row = _row(sessions)
    assert row.status.value == 'failed'
    assert row.total_clips == 1
    assert row.error_code == 'service_restarted'


def _render_run(jobs, variants):
    return {'generation': {'status': 'rendering', 'auto_start': True},
            'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'r', 'instance': OLD},
            'drafts': [{'id': f'd{i}'} for i in range(1, len(variants) + 1)], 'jobs': jobs, 'output_variants': variants}


def _linked(index, status, **job):
    identity = [f'v{index}', f'd{index}', 1, None, f'a{index}']
    return ({'job_id': f'j{index}', 'status': status, 'instance': OLD, 'variant_links': [identity], **job},
            {'id': f'v{index}', 'draft_id': f'd{index}', 'draft_revision': 1, 'render_attempt_id': f'a{index}',
             'render_job_id': f'j{index}', 'status': 'running'})


def test_render_killed_after_one_saved_video_tells_the_project_why(sessions):
    # RC156 #30: one video saved, the next one killed mid-render. The project failed with no reason and no code.
    done_job, done = _linked(1, 'completed', cover_pending=True)
    cut_job, cut = _linked(2, 'running')
    _project(sessions, _render_run([done_job, cut_job], [done, cut]))
    assert reconcile_interrupted_projects(sessions) == ['p']
    disk = _disk()
    assert disk['generation']['status'] == 'partial' and disk['generation']['completed_variant_count'] == 1
    assert disk['generation']['error'] == store.RESTART_MESSAGE and disk['generation']['error_code'] == 'service_restarted'
    first, second = disk['output_variants']
    assert first['status'] == 'completed'
    assert second['status'] == 'failed' and second['error_code'] == 'service_restarted'  # the card's retry finishes it
    row = _row(sessions)
    assert row.status.value == 'failed'
    assert row.error_message == store.RESTART_MESSAGE and row.error_code == 'service_restarted'


def test_render_killed_after_every_video_was_saved_stays_completed(sessions):
    # Killed while the last cover was pending: every video exists, so nothing is lost and nothing is retried.
    jobs, variants = zip(*(_linked(1, 'completed'), _linked(2, 'completed', cover_pending=True)))
    _project(sessions, _render_run(list(jobs), list(variants)))
    reconcile_interrupted_projects(sessions)
    disk = _disk()
    assert disk['generation']['status'] == 'completed' and disk['generation']['completed_variant_count'] == 2
    assert 'error' not in disk['generation'] and 'error_code' not in disk['generation']
    row = _row(sessions)
    assert row.status.value == 'completed' and row.error_message is None and row.error_code is None


def test_retrying_the_restarted_video_clears_the_reason():
    data = {'generation': {'status': 'rendering', 'error': store.RESTART_MESSAGE, 'error_code': 'service_restarted'},
            'analysis': {'run_id': 'r'}, 'jobs': [],
            'output_variants': [{'id': 'v1', 'status': 'completed'}, {'id': 'v2', 'status': 'completed'}]}
    store.settle_generation(data)
    assert data['generation']['status'] == 'completed'
    assert 'error' not in data['generation'] and 'error_code' not in data['generation']


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
    assert disk['analysis']['status'] == 'failed' and disk['analysis']['error'] == store.RESTART_MESSAGE == sentence('service_restarted')
    assert disk['analysis']['error_code'] == 'service_restarted' and 'message' not in disk['analysis']
    row = _row(sessions)
    assert row.status.value == 'failed' and row.error_message == sentence('service_restarted')


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


def test_long_video_stuck_in_processing_across_restarts_is_failed(sessions):
    """RC156 #13 case 3 (c3-long): analysis may already look failed while generation stays in
    production and the project index stays processing forever. Startup must close it."""
    # Disk shape after the previous process died mid clip_finder and an in-memory-only
    # recovery flipped analysis without writing/settling generation.
    _project(sessions, {
        'generation': {'status': 'production', 'auto_start': True},
        'analysis': {'status': 'failed', 'phase': 'production', 'run_id': 'r',
                     'message': '正在制作可发布成片'},  # stale message, no error
        'drafts': [], 'jobs': [], 'output_variants': []},
        status=ProjectStatus.PROCESSING)
    assert reconcile_interrupted_projects(sessions) == ['p']
    row = _row(sessions)
    assert row.status.value == 'failed'
    assert row.error_message == store.RESTART_MESSAGE and row.error_code == 'service_restarted'
    disk = _disk()
    assert disk['generation']['status'] == 'failed'
    assert disk['analysis']['error'] == store.RESTART_MESSAGE and 'message' not in disk['analysis']
    # Home card reads studio_generation_status=failed → 「重新生成」 entry.
    assert (row.settings or {}).get('studio_generation_status') == 'failed'


# --- 1.5.9 A1-2 ---------------------------------------------------------------------------------

def test_a1_2_crash_fields_from_heartbeat_exit_and_fault(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv('AUTOCLIP_SHUTDOWN_MARKER_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'data'))
    from backend.services.studio import shutdown_marker as sm, run_heartbeat
    sm._consumed.clear(); sm._restart_cached.clear()
    sm._crash_exit_cached.clear(); sm._crash_scene_cached.clear()
    instance = 'b' * 32
    (tmp_path / instance).write_text('exit:137', encoding='ascii')
    hb = {
        'ts': 1, 'uptime_s': 120, 'rss_mb': 1500, 'free_disk_mb': 8000,
        'stage': 'render', 'ffmpeg_children': 1,
    }
    (tmp_path / f'{instance}.hb').write_text(json.dumps(hb), encoding='utf-8')
    (tmp_path / f'{instance}.fault').write_text(
        'Fatal Python error: Segmentation fault\nFile "/Users/x/app/backend/services/studio/jobs.py", line 10 in _tracked\n',
        encoding='utf-8',
    )
    fields = sm.crash_fields(instance)
    assert fields['crash_exit'] == 'oom'
    assert fields['crash_stage'] == 'render'
    assert fields['crash_uptime_bucket'] in sm.CRASH_UPTIME_BUCKETS
    assert fields['crash_rss_bucket'] in sm.CRASH_RSS_BUCKETS
    assert fields['crash_disk_bucket'] in sm.CRASH_DISK_BUCKETS
    assert fields['crash_has_fault'] is True
    # Missing sidecars → unknown, no throw
    instance2 = 'c' * 32
    (tmp_path / instance2).write_text('exit:1', encoding='ascii')
    sm._consumed.clear(); sm._restart_cached.clear()
    sm._crash_exit_cached.clear(); sm._crash_scene_cached.clear()
    sparse = sm.crash_fields(instance2)
    assert sparse['crash_exit'] == 'nonzero_other'
    assert sparse['crash_stage'] == 'unknown'
    assert sparse['crash_has_fault'] is False


# --- 1.5.9 N4 ------------------------------------------------------------------------------------

def _fake_sentry(monkeypatch):
    """Enable real capture_crash_recovery with a fake SDK so once-per-instance dedupe holds."""
    from backend.core import sentry_setup as ss
    captured = []
    monkeypatch.setattr(ss, '_initialized', True)
    monkeypatch.setattr(ss, 'crash_reports_enabled', lambda: True)
    ss._crash_reported.clear()

    class Scope:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def set_tag(self, *a, **k): pass
        fingerprint = None

    class FakeSentry:
        @staticmethod
        def new_scope():
            return Scope()
        @staticmethod
        def capture_event(payload):
            captured.append(payload)
            return f'evt-{len(captured)}'

    import sys
    monkeypatch.setitem(sys.modules, 'sentry_sdk', FakeSentry)
    return captured


def test_n4_manual_confirmation_crash_reports_sentry_once(sessions, monkeypatch):
    """Manual (awaiting_confirmation) recover stamps analysis only — must still report Sentry."""
    from backend.services.studio import shutdown_marker
    captured = _fake_sentry(monkeypatch)
    instance = 'd' * 32
    shutdown_marker._consumed.clear(); shutdown_marker._restart_cached.clear()
    shutdown_marker._crash_exit_cached.clear(); shutdown_marker._crash_scene_cached.clear()
    data = _production(instance=instance)
    data['generation'] = {'status': 'awaiting_confirmation', 'auto_start': False}
    _project(sessions, data, auto=False)
    assert reconcile_interrupted_projects(sessions) == ['p']
    assert len(captured) == 1
    assert captured[0]['fingerprint'][:2] == ['studio', 'service_restarted']
    assert captured[0]['tags']['restart_reason'] == 'crash'
    # Idempotent: second reconcile must not re-fire.
    assert reconcile_interrupted_projects(sessions) == []
    assert len(captured) == 1


def test_n4_home_list_heal_reports_crash_via_recover(sessions, monkeypatch):
    """List-first heal calls store.recover without relying on reconcile's Sentry loop."""
    from backend.services.studio import shutdown_marker
    captured = _fake_sentry(monkeypatch)
    instance = 'e' * 32
    shutdown_marker._consumed.clear(); shutdown_marker._restart_cached.clear()
    shutdown_marker._crash_exit_cached.clear(); shutdown_marker._crash_scene_cached.clear()
    _project(sessions, _production(instance=instance))
    with sessions() as db:
        listing = ProjectService(db).get_projects_paginated(PaginationParams())
    assert listing.items[0].status.value == 'failed'
    assert len(captured) == 1
    assert captured[0]['tags']['restart_reason'] == 'crash'
    assert captured[0]['fingerprint'][:2] == ['studio', 'service_restarted']


# --- 1.5.9 N1 nested stage stack ---------------------------------------------------------------

def test_n1_nested_set_stage_stack_keeps_outer_production():
    """Nested render finishing must not report idle while outer production is still active."""
    from backend.services.studio import run_heartbeat

    run_heartbeat.set_stage('idle')  # clear any prior stack on this thread
    # Drain leftover frames if a previous test left the thread dirty.
    while run_heartbeat.current_stage() != 'idle':
        run_heartbeat.set_stage('idle')

    run_heartbeat.set_stage('analyze')  # outer production
    assert run_heartbeat.current_stage() == 'analyze'
    run_heartbeat.set_stage('render')  # nested
    assert run_heartbeat.current_stage() == 'render'
    run_heartbeat.set_stage('idle')  # nested done — outer must remain
    assert run_heartbeat.current_stage() == 'analyze'
    run_heartbeat.set_stage('idle')  # outer done
    assert run_heartbeat.current_stage() == 'idle'
