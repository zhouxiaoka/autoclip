"""A completed automatic visual render must settle the actual project list too."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.base import Base
from backend.models.project import Project, ProjectStatus
from backend.schemas.base import PaginationParams
from backend.schemas.project import ProjectFilter, ProjectStatus as ResponseStatus
from backend.services.project_service import ProjectService
from backend.services.studio import jobs, store


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (store.directory('visual') / 'metadata').mkdir(parents=True)
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr('backend.core.database.SessionLocal', sessions)
    with sessions() as db:
        db.add(Project(id='visual', name='公开 游戏', status=ProjectStatus.PROCESSING,
                       processing_config={'smart_import': {'auto_start': True}, 'creative': {'goal': 'highlight'}, 'kept': 'original'},
                       project_metadata={'kept': 'original'}))
        db.commit()
    yield sessions
    engine.dispose()


def state(statuses):
    return {'generation': {'status': 'rendering', 'auto_start': True},
            'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'flow', 'instance': store.INSTANCE},
            'drafts': [{'id': 'draft-' + str(i)} for i in range(len(statuses))],
            'jobs': [{'job_id': 'job-' + str(i), 'status': status, 'instance': store.INSTANCE} for i, status in enumerate(statuses)],
            'output_variants': [{'id': str(i), 'render_job_id': 'job-' + str(i), 'status': status, 'instance': store.INSTANCE} for i, status in enumerate(statuses)]}


def test_last_visual_render_finishes_database_and_home(project):
    store.write('visual', state(['completed', 'running', 'on_demand']))
    jobs._sync_variant_status('visual', 'job-1', 'completed')
    with project() as db:
        row = db.get(Project, 'visual')
        assert row.status is ProjectStatus.COMPLETED
        assert row.completed_at is not None
        assert row.processing_config['kept'] == 'original'
        assert row.project_metadata == {'kept': 'original'}
        response = ProjectService(db).get_projects_paginated(PaginationParams())
        assert response.items[0].status is ResponseStatus.COMPLETED
        assert response.items[0].total_clips == 2
        assert response.items[0].settings.get('studio_draft_count', 0) == 3


def test_visual_home_counts_drafts_separately_from_multiple_platform_outputs(project):
    data = state(['completed'] * 4)
    data['drafts'] = [{'id': 'first'}, {'id': 'second'}]
    store.settle_generation(data)
    store.write('visual', data)
    with project() as db:
        response = ProjectService(db).get_project_with_stats('visual')
        assert response.status is ResponseStatus.COMPLETED
        assert response.total_clips == 4
        assert response.settings.get('studio_draft_count', 0) == 2


@pytest.mark.parametrize('statuses, expected', [
    (['completed', 'completed'], ProjectStatus.COMPLETED),
    (['completed', 'failed'], ProjectStatus.FAILED),
    (['failed', 'failed'], ProjectStatus.FAILED),
    (['completed', 'queued'], ProjectStatus.PROCESSING),
    (['completed', 'preparing'], ProjectStatus.PROCESSING),
])
def test_render_terminals_and_pending_workers(project, statuses, expected):
    initial = state(statuses)
    store.write('visual', initial)
    jobs._sync_variant_status('visual', 'job-0', statuses[0])
    with project() as db:
        assert db.get(Project, 'visual').status is expected
    assert [item['status'] for item in store.read('visual')['output_variants']] == statuses


def test_old_completed_generation_recovers_before_status_filter_without_changing_outputs(project):
    data = state(['completed', 'on_demand'])
    store.settle_generation(data)
    store.write('visual', data)
    path = store.directory('visual') / 'metadata' / 'studio.json'
    original = path.read_bytes()
    with project() as db:
        result = ProjectService(db).get_projects_paginated(PaginationParams(), ProjectFilter(status=ResponseStatus.COMPLETED))
        assert [row.id for row in result.items] == ['visual']
        assert db.get(Project, 'visual').status is ProjectStatus.COMPLETED
    assert path.read_bytes() == original


@pytest.mark.parametrize('bad', ['missing', 'broken', 'nonautomatic'])
def test_invalid_or_nonautomatic_receipt_does_not_change_project(project, bad):
    path = store.directory('visual') / 'metadata' / 'studio.json'
    if bad == 'broken':
        path.write_text('{')
    elif bad == 'nonautomatic':
        data = state(['completed']); store.settle_generation(data); data['generation']['auto_start'] = False
        store.write('visual', data)
    with project() as db:
        response = ProjectService(db).get_project_with_stats('visual')
        assert response.status is ResponseStatus.PROCESSING
        assert db.get(Project, 'visual').status is ProjectStatus.PROCESSING


def test_busy_index_does_not_fail_saved_video_and_next_list_recovers(project, monkeypatch):
    from sqlalchemy.exc import OperationalError
    from backend.services.studio.project_completion import sync_project_completion
    data = state(['completed']); store.settle_generation(data); store.write('visual', data)
    path = store.directory('visual') / 'metadata' / 'studio.json'; original = path.read_bytes()
    with project() as db:
        with monkeypatch.context() as denied:
            def busy():
                raise OperationalError('controlled fixture', {}, Exception('database is locked'))
            denied.setattr(db, 'commit', busy)
            assert sync_project_completion('visual', db) is False
        assert db.get(Project, 'visual').status is ProjectStatus.PROCESSING
        assert ProjectService(db).get_project_with_stats('visual').status is ResponseStatus.COMPLETED
    assert path.read_bytes() == original


@pytest.mark.parametrize('bad', ['[]', '{"generation": []}', '{"generation": {"auto_start": true, "status": "completed"}, "analysis": 1}', '{"generation": {"auto_start": true, "status": "completed"}, "analysis": {"status": "completed"}, "output_variants": [1]}', '{"generation": {"auto_start": true, "status": "completed"}, "analysis": {"status": "completed"}, "drafts": [1]}'])
def test_malformed_receipt_never_breaks_the_project_list(project, bad):
    path = store.directory('visual') / 'metadata' / 'studio.json'; path.write_text(bad)
    with project() as db:
        assert ProjectService(db).get_projects_paginated(PaginationParams()).items[0].status is ResponseStatus.PROCESSING
    assert path.read_text() == bad
