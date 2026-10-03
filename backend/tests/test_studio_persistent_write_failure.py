"""Observable terminal state, old outputs and recovery after persistent disk denial."""
import json

import pytest

from backend.services.studio import jobs, store


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"crash_reports":false}')
    root = store.directory('p1')
    (root / 'raw').mkdir(parents=True)
    (root / 'raw' / 'input.mp4').write_bytes(b'local protocol fixture')
    store.write('p1', {'drafts': [], 'events': [], 'jobs': [
        {'job_id': 'active', 'status': 'queued', 'percent': 0, 'instance': store.INSTANCE},
        {'job_id': 'ready', 'status': 'completed', 'result': {'path': 'existing.mp4'}},
    ], 'analysis': None, 'output_variants': []})
    return root / 'metadata' / 'studio.json'


def deny_state(monkeypatch):
    replace = store.os.replace
    def denied(source, destination):
        if destination.name == 'studio.json':
            error = PermissionError('controlled persistent sharing violation')
            error.winerror = 32
            raise error
        return replace(source, destination)
    monkeypatch.setattr(store.os, 'replace', denied)


def test_worker_does_not_remain_queued_and_can_retry_after_permission_returns(project, monkeypatch):
    original = project.read_bytes()
    with monkeypatch.context() as blocked:
        deny_state(blocked)
        blocked.setattr(jobs, 'render_draft', lambda *a, **k: pytest.fail('Denied initial state must not render'))
        with pytest.raises(PermissionError):
            jobs._render('p1', object(), 'active')
        live = store.read('p1')
        assert live['jobs'][0]['status'] == 'failed'
        assert live['jobs'][0]['error'] == store.IO_FAILURE_MESSAGE
        assert live['jobs'][1]['result'] == {'path': 'existing.mp4'}
        assert project.read_bytes() == original
        assert not list(project.parent.glob('*.tmp'))
    assert store.read('p1')['jobs'][0]['status'] == 'failed'
    store.change('p1', lambda data: data['jobs'].append(
        {'job_id': 'retry', 'status': 'queued', 'percent': 0, 'instance': store.INSTANCE}))
    monkeypatch.setattr(jobs, 'render_draft', lambda *a, **k: {'path': 'retried.mp4'})
    monkeypatch.setattr(jobs, '_design_covers', lambda *a, **k: None)
    jobs._render('p1', object(), 'retry')
    durable = json.loads(project.read_text(encoding='utf-8'))
    assert durable['jobs'][0]['status'] == 'failed'
    assert durable['jobs'][-1]['status'] == 'completed'
    assert durable['jobs'][-1]['result']['path'] == 'retried.mp4'
    assert durable['jobs'][1]['result'] == {'path': 'existing.mp4'}


def test_render_failure_settles_only_linked_variant_and_keeps_ready_output(project, monkeypatch):
    def prepare(data):
        data.update(generation={'status': 'rendering', 'auto_start': True},
                    analysis={'status': 'running', 'phase': 'rendering', 'instance': store.INSTANCE, 'run_id': 'flow-a'})
        data['output_variants'] = [
            {'id': 'ready', 'status': 'completed', 'render_job_id': 'ready', 'cover': 'keep.jpg'},
            {'id': 'active', 'status': 'queued', 'render_job_id': 'active'},
        ]
    store.change('p1', prepare)
    original = project.read_bytes()
    deny_state(monkeypatch)
    with pytest.raises(PermissionError):
        store.change('p1', lambda data: data['jobs'][0].update(status='running'))
    live = store.read('p1')
    assert live['output_variants'][1]['status'] == 'failed'
    assert live['output_variants'][0] == {'id': 'ready', 'status': 'completed', 'render_job_id': 'ready', 'cover': 'keep.jpg'}
    assert live['generation']['status'] == 'partial'
    assert live['generation']['completed_variant_count'] == 1
    assert live['analysis']['run_id'] == 'flow-a'
    assert store.read('p1')['generation']['finished_at'] == live['generation']['finished_at']
    assert project.read_bytes() == original


@pytest.mark.parametrize('phase', ['screening', 'production'])
def test_analysis_failure_is_terminal_without_destroying_source_or_plan(project, monkeypatch, phase):
    def prepare(data):
        data.update(generation={'status': phase, 'auto_start': True}, plan={'id': 'existing-plan'},
                    analysis={'status': 'running', 'phase': phase, 'instance': store.INSTANCE, 'run_id': 'flow-a'})
    store.change('p1', prepare)
    original = project.read_bytes()
    deny_state(monkeypatch)
    with pytest.raises(PermissionError):
        store.change('p1', lambda data: data['analysis'].update(message='controlled progress'))
    live = store.read('p1')
    assert live['analysis']['status'] == live['generation']['status'] == 'failed'
    assert live['analysis']['run_id'] == 'flow-a'
    assert live['plan'] == {'id': 'existing-plan'}
    assert project.read_bytes() == original
    assert (project.parent.parent / 'raw' / 'input.mp4').read_bytes() == b'local protocol fixture'


def test_failed_preparation_is_retryable_with_packaging_still_required(project, monkeypatch):
    store.change('p1', lambda data: data.update(
        generation={'status': 'rendering'}, output_variants=[{'id': 'v1', 'status': 'preparing', 'instance': store.INSTANCE}]))
    deny_state(monkeypatch)
    with pytest.raises(PermissionError):
        store.change('p1', lambda data: data['output_variants'][0].update(status='queued'))
    live = store.read('p1')
    assert live['output_variants'][0]['status'] == 'failed'
    assert live['output_variants'][0]['needs_prepare']
    assert live['generation']['status'] == 'failed'


def test_cover_state_failure_preserves_completed_video_and_original_cover(project, monkeypatch):
    store.change('p1', lambda data: data.update(output_variants=[{
        'id': 'ready', 'status': 'completed', 'cover': 'existing.jpg',
        'cover_job': {'job_id': 'cover-job', 'status': 'queued', 'instance': store.INSTANCE},
    }]))
    deny_state(monkeypatch)
    with pytest.raises(PermissionError):
        store.change('p1', lambda data: data['output_variants'][0]['cover_job'].update(status='running'))
    live = store.read('p1')['output_variants'][0]
    assert live['status'] == 'completed' and live['cover'] == 'existing.jpg'
    assert live['cover_job']['status'] == 'failed'


def test_unaccepted_new_job_does_not_poison_existing_worker(project, monkeypatch):
    original = project.read_bytes()
    deny_state(monkeypatch)
    with pytest.raises(PermissionError):
        store.change('p1', lambda data: data['jobs'].append({'job_id': 'unaccepted', 'status': 'queued'}))
    live = store.read('p1')
    assert len(live['jobs']) == 2 and live['jobs'][0]['status'] == 'queued'
    assert project.read_bytes() == original


def test_failure_patch_does_not_cross_data_roots(project, monkeypatch, tmp_path):
    with monkeypatch.context() as blocked:
        deny_state(blocked)
        with pytest.raises(PermissionError):
            store.change('p1', lambda data: data['jobs'][0].update(status='running'))
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'other'))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path / 'other'))
    store.directory('p1').mkdir(parents=True)
    store.write('p1', {'jobs': [{'job_id': 'active', 'status': 'queued', 'instance': store.INSTANCE}]})
    assert store.read('p1')['jobs'][0]['status'] == 'queued'


def test_one_failed_render_does_not_finish_generation_with_another_worker_pending(project, monkeypatch):
    def prepare(data):
        data.update(generation={'status': 'rendering'}, analysis=None)
        data['jobs'].append({'job_id': 'other', 'status': 'queued', 'instance': store.INSTANCE})
        data['output_variants'] = [
            {'id': 'active', 'status': 'queued', 'render_job_id': 'active'},
            {'id': 'other', 'status': 'queued', 'render_job_id': 'other'},
        ]
    store.change('p1', prepare)
    deny_state(monkeypatch)
    with pytest.raises(PermissionError):
        store.change('p1', lambda data: data['jobs'][0].update(status='running'))
    live = store.read('p1')
    assert live['output_variants'][0]['status'] == 'failed'
    assert live['output_variants'][1]['status'] == 'queued'
    assert live['jobs'][-1]['status'] == 'queued'
    assert live['generation']['status'] == 'rendering'
    assert 'finished_at' not in live['generation']
    assert live['analysis'] is None
