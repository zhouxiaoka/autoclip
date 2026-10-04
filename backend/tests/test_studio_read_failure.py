"""Accepted workers remain observable after metadata read access returns."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.v1.studio import router
from backend.api.v1.projects import router as projects_router
from backend.core import database
from backend.models import Base, Project
from backend.models.project import ProjectStatus
from backend.services.studio import jobs, store
from backend.services.studio.models import Draft, Scene


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"crash_reports":false,"analytics":false}')
    monkeypatch.setattr(store, '_io_failures', {})
    monkeypatch.setattr(store, '_read_failures', {})
    monkeypatch.setattr(store, '_pending_links', {})
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *a, **k: None)
    monkeypatch.setattr(jobs, '_design_covers', lambda *a, **k: None)
    root = store.directory('p1')
    (root / 'raw').mkdir(parents=True)
    (root / 'output').mkdir()
    source = root / 'raw/input.mp4'
    ready = root / 'output/ready.mp4'
    source.write_bytes(b'synthetic source; never decoded')
    ready.write_bytes(b'existing completed output')
    draft = Draft(id='active-draft', title='Synthetic', scenes=[Scene(id='s1', start=0, end=1)], subtitles=False)
    store.write('p1', {
        'drafts': [draft.model_dump()], 'events': [],
        'jobs': [{'job_id': 'ready', 'status': 'completed', 'result': {'path': 'ready.mp4'}}],
        'analysis': {'status': 'running', 'phase': 'rendering', 'run_id': 'flow-a', 'instance': store.INSTANCE},
        'generation': {'status': 'rendering', 'auto_start': True},
        'output_variants': [
            {'id': 'ready', 'status': 'completed', 'render_job_id': 'ready', 'cover': 'keep.jpg'},
            {'id': 'active', 'draft_id': draft.id, 'status': 'queued', 'branding': {'outro_enabled': False}},
        ],
    })
    engine = create_engine('sqlite:///' + str(tmp_path / 'api.sqlite'), connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(database, 'SessionLocal', sessions)
    with sessions() as db:
        db.add(Project(id='p1', name='Synthetic', status=ProjectStatus.PROCESSING, video_path=str(source), processing_config={'smart_import': {'auto_start': True}}))
        db.commit()
    def get_db():
        with sessions() as db:
            yield db
    app = FastAPI()
    app.include_router(router, prefix='/studio')
    app.include_router(projects_router, prefix='/projects')
    app.dependency_overrides[database.get_db] = get_db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield SimpleNamespace(client=client, source=source, ready=ready, draft=draft,
                              path=root / 'metadata/studio.json', root=root, sessions=sessions)
    engine.dispose()


class GatedExecutor:
    """Actual background workers; gates control binding/failure order only."""
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='read-denial-render')
        self.gates = {}
        self.futures = []

    def submit(self, fn, *args, **kwargs):
        draft_id = args[1].id
        gate = threading.Event()
        self.gates[draft_id] = gate
        def run():
            assert gate.wait(3), 'worker scheduling gate was not released'
            return fn(*args, **kwargs)
        future = self.pool.submit(run)
        self.futures.append(future)
        return future

    def close(self):
        for gate in self.gates.values():
            gate.set()
        self.pool.shutdown(wait=True)


def deny_reads(project, monkeypatch, mode):
    original = Path.read_text
    control = SimpleNamespace(blocked=False, calls=0, terminal=False)
    def read(path, *args, **kwargs):
        denied = control.blocked and path == project.path
        if mode == 'once':
            denied = denied and control.calls == 0
        if denied:
            control.calls += 1
            raise PermissionError('controlled metadata read denial')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', read)
    return control


def assert_preserved(project, state):
    assert project.source.read_bytes() == b'synthetic source; never decoded'
    assert project.ready.read_bytes() == b'existing completed output'
    assert next(j for j in state['jobs'] if j['job_id'] == 'ready') == {
        'job_id': 'ready', 'status': 'completed', 'result': {'path': 'ready.mp4'},
    }
    assert next(v for v in state['output_variants'] if v['id'] == 'ready') == {
        'id': 'ready', 'status': 'completed', 'render_job_id': 'ready', 'cover': 'keep.jpg',
    }


@pytest.mark.parametrize('mode,before_link', [('once', False), ('persistent', False), ('persistent', True), ('terminal', False)])
def test_real_dispatcher_read_failure_is_terminal_and_retry_starts_new_worker(project, monkeypatch, mode, before_link):
    executor = GatedExecutor()
    monkeypatch.setattr(jobs, 'render_executor', executor)
    control = deny_reads(project, monkeypatch, mode)
    renders = []
    def render(pid, source, draft, job_id, progress, **kwargs):
        renders.append(job_id)
        if mode == 'terminal' and len(renders) == 1:
            control.blocked = True
            raise RuntimeError('controlled encoder failure')
        return {'path': 'retry.mp4'}
    monkeypatch.setattr(jobs, 'render_draft', render)
    change = store.change
    wait_before_link = []
    if before_link:
        def bind_after_worker(pid, mutate):
            if threading.current_thread() is threading.main_thread() and executor.futures and not wait_before_link:
                wait_before_link.append(True)
                control.blocked = True
                executor.gates[project.draft.id].set()
                executor.futures[0].exception(timeout=3)
                control.blocked = False
            return change(pid, mutate)
        monkeypatch.setattr(store, 'change', bind_after_worker)
    try:
        jobs._dispatch_pending_variants('p1')
        assert len(executor.futures) == 1
        if not before_link:
            control.blocked = mode != 'terminal'
            executor.gates[project.draft.id].set()
        executor.futures[0].exception(timeout=3)
        assert executor.futures[0].done()
        disk = project.path.read_bytes()
        if mode in ('persistent', 'terminal') and not before_link:
            denied = project.client.get('/studio/p1')
            assert denied.status_code == 500
            assert project.path.read_bytes() == disk
        control.blocked = False
        response = project.client.get('/studio/p1')
        assert response.status_code == 200
        live = response.json()
        failed = next(j for j in live['jobs'] if j['job_id'] != 'ready')
        variant = next(v for v in live['output_variants'] if v['id'] == 'active')
        assert failed['status'] == variant['status'] == 'failed'
        assert live['generation']['status'] == 'partial'
        assert live['analysis']['status'] == 'completed'
        assert not executor.futures[0].exception()
        assert_preserved(project, live)
        # The same draft must not dedupe to the terminated worker's queued job.
        retry = project.client.post('/studio/p1/output-variants/active/retry')
        assert retry.status_code == 200, retry.text
        assert len(executor.futures) == 2
        executor.gates[project.draft.id].set()
        executor.futures[1].result(timeout=3)
        complete = project.client.get('/studio/p1').json()
        active = next(v for v in complete['output_variants'] if v['id'] == 'active')
        assert active['status'] == 'completed'
        assert active['render_job_id'] != failed['job_id']
        assert complete['generation']['status'] == 'completed'
        assert next(j for j in complete['jobs'] if j['job_id'] == failed['job_id'])['status'] == 'failed'
        assert_preserved(project, complete)
        assert not list(project.path.parent.glob('*.tmp'))
    finally:
        control.blocked = False
        executor.close()


def test_read_failure_does_not_fail_another_accepted_job_in_the_same_project(project, monkeypatch):
    other = project.draft.model_copy(update={'id': 'healthy-draft', 'title': 'Healthy'})
    def add(data):
        data['drafts'].append(other.model_dump())
        data['output_variants'].append({'id': 'healthy', 'draft_id': other.id, 'status': 'queued', 'branding': {'outro_enabled': False}})
    store.change('p1', add)
    executor = GatedExecutor()
    monkeypatch.setattr(jobs, 'render_executor', executor)
    control = deny_reads(project, monkeypatch, 'persistent')
    monkeypatch.setattr(jobs, 'render_draft', lambda *a, **k: {'path': 'healthy.mp4'})
    try:
        jobs._dispatch_pending_variants('p1')
        assert len(executor.futures) == 2
        control.blocked = True
        executor.gates[project.draft.id].set()
        executor.futures[0].exception(timeout=3)
        control.blocked = False
        live = project.client.get('/studio/p1').json()
        assert next(v for v in live['output_variants'] if v['id'] == 'active')['status'] == 'failed'
        assert next(v for v in live['output_variants'] if v['id'] == 'healthy')['status'] == 'queued'
        assert live['generation']['status'] == 'rendering'
        assert live['analysis']['status'] == 'running'
        assert_preserved(project, live)
        executor.gates[other.id].set()
        executor.futures[1].result(timeout=3)
        done = project.client.get('/studio/p1').json()
        assert next(v for v in done['output_variants'] if v['id'] == 'healthy')['status'] == 'completed'
        assert next(v for v in done['output_variants'] if v['id'] == 'active')['status'] == 'failed'
        assert done['generation']['status'] == 'partial'
        assert_preserved(project, done)
    finally:
        control.blocked = False
        executor.close()


def test_read_failure_patch_does_not_cross_project_data_roots(project, monkeypatch, tmp_path):
    executor = GatedExecutor()
    monkeypatch.setattr(jobs, 'render_executor', executor)
    control = deny_reads(project, monkeypatch, 'persistent')
    monkeypatch.setattr(jobs, 'render_draft', lambda *a, **k: pytest.fail('denied state must not render'))
    try:
        jobs._dispatch_pending_variants('p1')
        control.blocked = True
        executor.gates[project.draft.id].set()
        executor.futures[0].exception(timeout=3)
        control.blocked = False
        same_job = json.loads(project.path.read_bytes())['jobs'][0]['job_id']
        monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path / 'other-root'))
        store.directory('p1').mkdir(parents=True)
        store.write('p1', {'drafts': [], 'events': [], 'jobs': [{'job_id': same_job, 'status': 'queued', 'instance': store.INSTANCE}], 'analysis': None, 'output_variants': []})
        assert store.read('p1')['jobs'][0]['status'] == 'queued'
    finally:
        control.blocked = False
        executor.close()


def test_read_failure_without_a_completed_variant_settles_whole_generation(project, monkeypatch):
    store.change('p1', lambda data: data.update(
        jobs=[], output_variants=[v for v in data['output_variants'] if v['id'] != 'ready']))
    executor = GatedExecutor()
    monkeypatch.setattr(jobs, 'render_executor', executor)
    control = deny_reads(project, monkeypatch, 'persistent')
    monkeypatch.setattr(jobs, 'render_draft', lambda *a, **k: pytest.fail('denied state must not render'))
    try:
        jobs._dispatch_pending_variants('p1')
        control.blocked = True
        executor.gates[project.draft.id].set()
        executor.futures[0].exception(timeout=3)
        control.blocked = False
        live = project.client.get('/studio/p1').json()
        assert live['jobs'][0]['status'] == live['output_variants'][0]['status'] == 'failed'
        assert live['generation']['status'] == live['analysis']['status'] == 'failed'
        assert project.source.read_bytes() == b'synthetic source; never decoded'
        assert project.ready.read_bytes() == b'existing completed output'
    finally:
        control.blocked = False
        executor.close()


@pytest.mark.parametrize('success', [True, False])
def test_terminal_worker_before_binding_and_concurrent_dispatch_stays_consistent(project, monkeypatch, success):
    executor = GatedExecutor()
    monkeypatch.setattr(jobs, 'render_executor', executor)
    def render(*args, **kwargs):
        if not success:
            raise ValueError('ordinary render failure')
        return {'path': 'fast.mp4'}
    monkeypatch.setattr(jobs, 'render_draft', render)
    change = store.change
    intercepted = []
    def bind_after_worker(pid, mutate):
        if threading.current_thread() is threading.main_thread() and executor.futures and not intercepted:
            intercepted.append(True)
            # A second real dispatcher sees the claimed attempt before any binding.
            jobs._dispatch_pending_variants(pid)
            assert len(executor.futures) == 1
            executor.gates[project.draft.id].set()
            executor.futures[0].result(timeout=3)
        return change(pid, mutate)
    monkeypatch.setattr(store, 'change', bind_after_worker)
    try:
        jobs._dispatch_pending_variants('p1')
        state = project.client.get('/studio/p1').json()
        variant = next(v for v in state['output_variants'] if v['id'] == 'active')
        job = next(j for j in state['jobs'] if j['job_id'] == variant['render_job_id'])
        assert variant['status'] == job['status'] == ('completed' if success else 'failed')
        assert state['generation']['status'] == ('completed' if success else 'partial')
        assert json.loads(project.path.read_bytes())['generation'] == state['generation']
        assert len(executor.futures) == 1
        assert_preserved(project, state)
    finally:
        executor.close()


@pytest.mark.parametrize('mode', ['once', 'persistent'])
def test_saved_render_cannot_be_revoked_by_post_render_metadata_denial(project, monkeypatch, mode):
    executor = GatedExecutor()
    monkeypatch.setattr(jobs, 'render_executor', executor)
    control = deny_reads(project, monkeypatch, mode)
    monkeypatch.setattr(jobs, 'render_draft', lambda *a, **k: {'path': 'saved.mp4'})
    def cover(*args):
        control.blocked = True
        store.read('p1')
    monkeypatch.setattr(jobs, '_design_covers', cover)
    try:
        jobs._dispatch_pending_variants('p1')
        executor.gates[project.draft.id].set()
        executor.futures[0].result(timeout=3)
        control.blocked = False
        state = project.client.get('/studio/p1').json()
        variant = next(v for v in state['output_variants'] if v['id'] == 'active')
        job = next(j for j in state['jobs'] if j['job_id'] == variant['render_job_id'])
        assert job['status'] == variant['status'] == 'completed'
        assert job['result'] == {'path': 'saved.mp4'}
        assert state['generation']['status'] == 'completed'
        assert 'error' not in job
        assert_preserved(project, state)
    finally:
        control.blocked = False
        executor.close()


def test_home_first_recovery_is_durable_and_raw_observer_does_not_consume_receipt(project, monkeypatch):
    executor = GatedExecutor()
    monkeypatch.setattr(jobs, 'render_executor', executor)
    monkeypatch.setattr(jobs, 'render_draft', lambda *a, **k: pytest.fail('denied initial state must not render'))
    control = deny_reads(project, monkeypatch, 'persistent')
    try:
        jobs._dispatch_pending_variants('p1')
        original = project.path.read_bytes()
        control.blocked = True
        executor.gates[project.draft.id].set()
        executor.futures[0].result(timeout=3)
        control.blocked = False
        assert store.read('p1', recover=False)['generation']['status'] == 'rendering'
        assert project.path.read_bytes() == original
        assert store.has_pending_receipts('p1')
        listing = project.client.get('/projects/')
        assert listing.status_code == 200
        detail = project.client.get('/projects/p1').json()
        assert detail['status'] == 'failed'  # partial has an existing playable output
        durable = json.loads(project.path.read_bytes())
        assert durable['generation']['status'] == 'partial'
        assert durable['analysis']['status'] == 'completed'
        assert durable['analysis_history'][-1]['run_id'] == 'flow-a'
        assert not store.has_pending_receipts('p1')
        monkeypatch.setattr(store, 'INSTANCE', 'new-process')
        monkeypatch.setattr(store, '_read_failures', {})
        state = project.client.get('/studio/p1').json()
        assert state['generation']['status'] == 'partial'
        assert project.client.get('/projects/p1').json()['status'] == 'failed'
        assert_preserved(project, state)
    finally:
        control.blocked = False
        executor.close()


def test_recovered_read_receipt_survives_failed_atomic_save(project, monkeypatch):
    executor = GatedExecutor()
    monkeypatch.setattr(jobs, 'render_executor', executor)
    control = deny_reads(project, monkeypatch, 'persistent')
    try:
        jobs._dispatch_pending_variants('p1')
        original = project.path.read_bytes()
        control.blocked = True
        executor.gates[project.draft.id].set()
        executor.futures[0].result(timeout=3)
        control.blocked = False
        with monkeypatch.context() as blocked:
            blocked.setattr(store, '_replace_state', lambda *a: (_ for _ in ()).throw(PermissionError('atomic save denied')))
            assert store.read('p1')['generation']['status'] == 'partial'
            assert project.path.read_bytes() == original
            assert store.has_pending_receipts('p1')
            assert not list(project.path.parent.glob('*.tmp'))
        assert store.read('p1')['generation']['status'] == 'partial'
        assert json.loads(project.path.read_bytes())['generation']['status'] == 'partial'
        assert not store.has_pending_receipts('p1')
    finally:
        control.blocked = False
        executor.close()


class GatedCalls:
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.calls = []

    def submit(self, fn, *args, **kwargs):
        gate = threading.Event()
        def call():
            assert gate.wait(5)
            return fn(*args, **kwargs)
        future = self.pool.submit(call)
        self.calls.append(SimpleNamespace(name=fn.__name__, gate=gate, future=future))
        return future

    def drain(self, start=0):
        index = start
        while index < len(self.calls):
            assert index < 15
            self.calls[index].gate.set()
            self.calls[index].future.result(timeout=5)
            index += 1

    def close(self):
        for call in self.calls:
            call.gate.set()
        self.pool.shutdown(wait=True)


@pytest.mark.parametrize('worker', ['_inspect', '_auto_generate', '_analyze', '_produce_selected', '_produce_on_demand', '_ai_cover_job'])
def test_each_accepted_caller_recovers_and_a_real_retry_can_complete(project, monkeypatch, worker):
    from copy import deepcopy
    from backend.services.studio.models import ImportOptions, ConfirmPlan, Preferences
    executor = GatedCalls()
    for name in ('executor', 'cover_executor', 'render_executor'):
        monkeypatch.setattr(jobs, name, executor)
    options = ImportOptions(auto_start=worker == '_auto_generate', platforms=['original'])
    plan = {'id': 'fixture-plan', 'preferences': Preferences().model_dump(), 'aspect': 'original',
            'recommended_analysis': 'subtitle', 'overrides': {}, 'mode': 'fixture'}
    inert_worker_services(project, monkeypatch)
    def initial(data):
        data['analysis'] = {'status': 'awaiting_confirmation', 'run_id': 'prior'} if worker == '_produce_selected' else None
        data['generation'] = {'status': 'completed', 'auto_start': False}
        data['plan'] = deepcopy(plan)
        data['output_variants'] = [v for v in data['output_variants'] if v['id'] == 'ready']
        if worker == '_ai_cover_job':
            data['output_variants'][0]['strategy_id'] = 'original'
        if worker == '_produce_on_demand':
            data['output_variants'].append({'id': 'active', 'draft_id': project.draft.id, 'draft_revision': 1,
                                           'strategy_id': 'original', 'branding': {}, 'status': 'on_demand'})
    store.change('p1', initial)
    def accepted():
        if worker in ('_inspect', '_auto_generate'):
            return jobs.inspect_project('p1', options)
        if worker == '_analyze':
            return jobs.analyze_project('p1', Preferences())
        if worker == '_produce_selected':
            return jobs.confirm_project('p1', ConfirmPlan(plan_id=store.read('p1')['plan']['id'], analysis_mode='subtitle', goals=['content']))
        if worker == '_produce_on_demand':
            return jobs.produce_variant('p1', 'active')
        return jobs.request_ai_cover('p1', 'ready')
    control = deny_reads(project, monkeypatch, 'persistent')
    try:
        accepted()
        if worker == '_auto_generate':
            executor.calls[0].gate.set()
            executor.calls[0].future.result(timeout=5)
        call = next(call for call in executor.calls if call.name == worker)
        saved = project.path.read_bytes()
        control.blocked = True
        call.gate.set()
        call.future.result(timeout=5)
        assert call.future.done()
        assert project.client.get('/studio/p1').status_code == 500
        assert project.path.read_bytes() == saved
        control.blocked = False
        state = project.client.get('/studio/p1').json()
        if worker == '_produce_on_demand':
            variant = next(v for v in state['output_variants'] if v['id'] == 'active')
            old_attempt = variant['preparation_run_id']
            assert variant['status'] == 'failed' and variant['needs_prepare']
        elif worker == '_ai_cover_job':
            assert state['output_variants'][0]['cover_job']['status'] == 'failed'
        else:
            assert state['analysis']['status'] == 'failed'
            assert state['analysis']['run_id']
        previous_count = len(executor.calls)
        if worker == '_produce_on_demand':
            jobs.retry_variant('p1', 'active')
            assert next(v for v in store.read('p1')['output_variants'] if v['id'] == 'active')['preparation_run_id'] != old_attempt
        elif worker == '_produce_selected':
            # The actual result UI re-screens to obtain a fresh confirmation plan.
            jobs.inspect_project('p1', ImportOptions(auto_start=False, platforms=['original']))
            executor.drain(previous_count)
            accepted()
        else:
            accepted()
        assert len(executor.calls) > previous_count
        executor.drain(previous_count)
        state = project.client.get('/studio/p1').json()
        if worker == '_produce_on_demand':
            assert next(v for v in state['output_variants'] if v['id'] == 'active')['status'] == 'completed'
        elif worker == '_ai_cover_job':
            assert state['output_variants'][0]['cover_job']['status'] == 'completed'
        else:
            assert state['analysis']['status'] in ('awaiting_confirmation', 'completed')
        assert project.source.read_bytes() == b'synthetic source; never decoded'
        assert project.ready.read_bytes() == b'existing completed output'
    finally:
        control.blocked = False
        executor.close()


def inert_worker_services(project, monkeypatch):
    from copy import deepcopy
    from backend.services import cover
    from backend.services.studio import intelligence, planning, publish_kit
    from backend.services.studio.models import Preferences
    plan = {'id': 'fixture-plan', 'preferences': Preferences().model_dump(), 'aspect': 'original',
            'recommended_analysis': 'subtitle', 'overrides': {}, 'mode': 'fixture'}
    monkeypatch.setattr(jobs, '_prepare_speaker_framing', lambda *a: None)
    monkeypatch.setattr(jobs, 'ensure_project_thumbnail', lambda *a: None)
    monkeypatch.setattr(planning, 'recommend', lambda *a: deepcopy(plan))
    monkeypatch.setattr(intelligence, 'ready', lambda: True)
    monkeypatch.setattr(intelligence, '_probe', lambda *a: {'duration': 1})
    monkeypatch.setattr(jobs, 'analyze', lambda video, prefs, stage, *a: (stage('Synthetic analysis') or [], {}))
    monkeypatch.setattr(jobs, 'make_drafts', lambda *a, **k: [])
    monkeypatch.setattr(jobs, 'run_content', lambda *a: [])
    monkeypatch.setattr(jobs, '_content_drafts', lambda *a: [project.draft.model_dump()])
    monkeypatch.setattr(jobs, '_source_has_burned_subtitles', lambda *a: False)
    monkeypatch.setattr(jobs, '_apply_framing', lambda pid, raw, *a: (raw, None))
    monkeypatch.setattr(jobs, '_apply_packaging', lambda pid, raw, *a: raw)
    monkeypatch.setattr(jobs, '_prefetch_packaging', lambda *a: None)
    monkeypatch.setattr(jobs, '_posts_for', lambda *a: {})
    monkeypatch.setattr(jobs, 'render_draft', lambda *a, **k: {'path': 'retry.mp4'})
    monkeypatch.setattr(cover, 'load_config', lambda: SimpleNamespace(enabled=True, configured=True, allow_send_frame=True))
    monkeypatch.setattr(publish_kit, 'ai_cover', lambda *a: True)
    return plan


@pytest.mark.parametrize('parent', ['automatic', 'preparation'])
def test_binding_read_denial_preserves_the_real_accepted_child_worker(project, monkeypatch, parent):
    from backend.services.studio.models import ImportOptions
    executor = GatedCalls()
    renders = GatedCalls()
    monkeypatch.setattr(jobs, 'executor', executor)
    monkeypatch.setattr(jobs, 'render_executor', renders)
    inert_worker_services(project, monkeypatch)
    def initial(data):
        data['analysis'] = None
        data['output_variants'] = [v for v in data['output_variants'] if v['id'] == 'ready']
        if parent == 'preparation':
            data['output_variants'].append({'id': 'active', 'draft_id': project.draft.id, 'draft_revision': 1,
                                           'strategy_id': 'original', 'branding': {}, 'status': 'on_demand'})
    store.change('p1', initial)
    control = deny_reads(project, monkeypatch, 'persistent')
    remember = store.remember_render_link
    def deny_after_accept(pid, expected, job_id):
        remember(pid, expected, job_id)
        control.blocked = True
    monkeypatch.setattr(store, 'remember_render_link', deny_after_accept)
    try:
        if parent == 'preparation':
            jobs.produce_variant('p1', 'active')
        else:
            jobs.inspect_project('p1', ImportOptions(auto_start=True, platforms=['original']))
            executor.calls[0].gate.set()
            executor.calls[0].future.result(timeout=5)
        executor.drain()
        assert len(renders.calls) == 1
        assert not renders.calls[0].future.done()
        assert project.client.get('/studio/p1').status_code == 500
        control.blocked = False
        state = project.client.get('/studio/p1').json()
        variant = next(v for v in state['output_variants'] if v['id'] != 'ready')
        job = next(j for j in state['jobs'] if j['job_id'] == variant['render_job_id'])
        assert job['status'] == variant['status'] == 'queued'
        assert state['generation']['status'] == 'rendering'
        assert not variant.get('needs_prepare')
        assert not store.has_pending_receipts('p1')
        renders.drain()
        completed = project.client.get('/studio/p1').json()
        assert next(v for v in completed['output_variants'] if v['id'] == variant['id'])['status'] == 'completed'
        assert completed['generation']['status'] == 'completed'
        assert project.ready.read_bytes() == b'existing completed output'
    finally:
        control.blocked = False
        executor.close()
        renders.close()


def test_old_receipt_and_late_binding_cannot_mutate_later_attempts(project, monkeypatch):
    def prepare(data):
        data['analysis'] = {'status': 'running', 'run_id': 'new-run', 'phase': 'production', 'instance': store.INSTANCE}
        data['generation']['status'] = 'production'
        data['output_variants'][1].update(status='preparing', preparation_run_id='new-prep', render_attempt_id='new-render', instance=store.INSTANCE)
        data['output_variants'][0]['cover_job'] = {'job_id': 'new-cover', 'status': 'queued', 'instance': store.INSTANCE}
    store.change('p1', prepare)
    before = store.read('p1', recover=False)
    path = project.path
    # This identity-only replay exercises cached receipts after another accepted
    # attempt supersedes their saved IDs; no exception text or content is cached.
    old_variant = ('active', project.draft.id, None, 'old-prep', 'old-render')
    store._read_failures[path] = [
        {'identity': ('analysis', 'old-run', 'production'), 'pending': {}},
        {'identity': ('preparation', 'active', 'old-prep'), 'pending': {'active': old_variant}},
        {'identity': ('cover', 'ready', 'old-cover'), 'pending': {}},
    ]
    store._pending_links[path] = {old_variant: 'ready'}
    after = project.client.get('/studio/p1').json()
    assert {key: after[key] for key in before} == before
    assert not store.has_pending_receipts('p1')
    assert not store.bind_render(after, old_variant, 'ready')
    assert {key: after[key] for key in before} == before


def test_screening_rejected_handoff_with_read_denial_terminates_only_accepted_parent(project, monkeypatch):
    from backend.services.studio.models import ImportOptions
    executor = GatedCalls()
    inert_worker_services(project, monkeypatch)
    store.change('p1', lambda data: data.update(analysis=None))
    control = deny_reads(project, monkeypatch, 'persistent')
    def submit(fn, *args, **kwargs):
        if fn.__name__ == '_auto_generate':
            control.blocked = True
            raise RuntimeError('child executor rejects submission')
        return executor.submit(fn, *args, **kwargs)
    monkeypatch.setattr(jobs, 'executor', SimpleNamespace(submit=submit))
    try:
        run_id = jobs.inspect_project('p1', ImportOptions(auto_start=True, platforms=['original']))
        executor.drain()
        assert len(executor.calls) == 1
        assert executor.calls[0].name == '_inspect'
        control.blocked = False
        state = project.client.get('/studio/p1').json()
        assert state['analysis']['status'] == state['generation']['status'] == 'failed'
        assert state['analysis']['run_id'] == run_id
        assert state['analysis']['phase'] == 'production'
    finally:
        control.blocked = False
        executor.close()


@pytest.mark.parametrize('accepted_status', [None, 'queued', 'completed'])
def test_restart_recovers_only_the_exact_durable_render_claim_and_association(project, monkeypatch, accepted_status):
    from concurrent.futures import Future
    executor = SimpleNamespace(futures=[])
    def submit(*args, **kwargs):
        future = Future()
        executor.futures.append(future)
        return future
    executor.submit = submit
    monkeypatch.setattr(jobs, 'render_executor', executor)
    expected = store.change('p1', lambda data: store.claim_render(data, store.variant_identity(data['output_variants'][1])))
    assert expected
    try:
        if accepted_status:
            job = jobs.export('p1', project.draft, _variant_identity=expected)
            assert len(executor.futures) == 1
            durable = json.loads(project.path.read_bytes())
            accepted = next(j for j in durable['jobs'] if j['job_id'] == job['job_id'])
            assert accepted['variant_links'] == [list(expected)]
            if accepted_status == 'completed':
                # Reconstruct the exact durable accepted-job receipt at a crash
                # before a dispatcher link save; no snapshot inference is used.
                accepted.update(status='completed', result={'path': 'saved-before-crash.mp4'})
                project.path.write_text(json.dumps(durable))
        monkeypatch.setattr(store, 'INSTANCE', 'restarted')
        monkeypatch.setattr(store, '_read_failures', {})
        monkeypatch.setattr(store, '_pending_links', {})
        state = project.client.get('/studio/p1').json()
        variant = next(v for v in state['output_variants'] if v['id'] == 'active')
        assert variant['status'] == ('completed' if accepted_status == 'completed' else 'failed')
        assert not variant.get('render_dispatch_claimed')
        assert json.loads(project.path.read_bytes())['generation']['status'] == ('completed' if accepted_status == 'completed' else 'partial')
        if accepted_status:
            recovered = next(j for j in state['jobs'] if j['job_id'] == job['job_id'])
            assert variant['render_job_id'] == job['job_id']
            if accepted_status == 'completed':
                assert recovered['result'] == {'path': 'saved-before-crash.mp4'}
                assert recovered['status'] == 'completed'
        assert_preserved(project, state)
        # The accepted Futures belong to the modeled process which exited.
        for future in executor.futures:
            assert future.cancel()
    finally:
        # These accepted Futures belong to the modeled process which exited.
        for future in executor.futures:
            future.cancel()



@pytest.mark.parametrize('consent', [False, True])
@pytest.mark.parametrize('worker', ['analysis', 'cover'])
def test_owned_background_read_error_reports_once_with_consent_and_safe_tags(project, monkeypatch, consent, worker):
    import sentry_sdk
    from backend.core import sentry_setup
    from backend.services.studio.models import Preferences
    (project.root.parent.parent / 'privacy.json').write_text(json.dumps({'crash_reports': consent}))
    monkeypatch.setattr(sentry_setup, '_initialized', True)
    monkeypatch.setattr(jobs, 'capture_studio_exception', sentry_setup.capture_studio_exception)
    captured = []
    def capture(error):
        tags = dict(sentry_sdk.get_current_scope()._tags)
        event = sentry_setup.before_send({'tags': tags, 'exception': {'values': [{'type': type(error).__name__, 'value': str(error)}]}})
        captured.append(event)
    monkeypatch.setattr(sentry_sdk, 'capture_exception', capture)
    monkeypatch.setattr(jobs.intelligence, 'ready', lambda: True)
    monkeypatch.setattr(jobs, 'analyze', lambda video, prefs, stage, *args: (stage('Synthetic stage') or [], {}))
    store.change('p1', lambda data: data.update(analysis=None))
    executor = GatedCalls()
    monkeypatch.setattr(jobs, 'executor', executor)
    monkeypatch.setattr(jobs, 'cover_executor', executor)
    from backend.services import cover
    monkeypatch.setattr(cover, 'load_config', lambda: SimpleNamespace(enabled=True, configured=True, allow_send_frame=True))
    control = deny_reads(project, monkeypatch, 'once' if worker == 'cover' else 'persistent')
    try:
        if worker == 'cover':
            jobs.request_ai_cover('p1', 'ready')
        else:
            jobs.analyze_project('p1', Preferences())
        control.blocked = True
        executor.drain()
        control.blocked = False
        state = store.read('p1')
        if worker == 'cover':
            assert state['output_variants'][0]['cover_job']['status'] == 'failed'
            assert state['output_variants'][0]['status'] == 'completed'
        else:
            assert state['analysis']['status'] == 'failed'
        assert len(captured) == int(consent)
        if consent:
            assert captured[0]['tags']['phase'] == ('production' if worker == 'cover' else 'analysis')
            assert captured[0]['tags']['error_code'] == 'unexpected'
            assert 'controlled metadata' not in str(captured[0])
    finally:
        control.blocked = False
        executor.close()


def test_render_primary_error_and_denied_failure_write_do_not_report_twice(project, monkeypatch):
    executor = GatedExecutor()
    monkeypatch.setattr(jobs, 'render_executor', executor)
    control = deny_reads(project, monkeypatch, 'persistent')
    captured = []
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda error, phase, **kwargs: captured.append((type(error).__name__, phase)))
    def fail(*args, **kwargs):
        control.blocked = True
        raise RuntimeError('controlled primary render failure')
    monkeypatch.setattr(jobs, 'render_draft', fail)
    try:
        jobs._dispatch_pending_variants('p1')
        executor.gates[project.draft.id].set()
        executor.futures[0].result(timeout=3)
        control.blocked = False
        assert next(v for v in store.read('p1')['output_variants'] if v['id'] == 'active')['status'] == 'failed'
        assert captured == [('RuntimeError', 'render')]
    finally:
        control.blocked = False
        executor.close()


@pytest.mark.parametrize('invalid', [[], {'generation': ['malformed'], 'analysis': {}, 'output_variants': []},
                                  {'generation': {}, 'analysis': {}, 'jobs': None, 'output_variants': []}])
def test_home_pending_receipt_preserves_existing_malformed_state_guards(project, monkeypatch, invalid):
    executor = GatedExecutor()
    monkeypatch.setattr(jobs, 'render_executor', executor)
    control = deny_reads(project, monkeypatch, 'persistent')
    try:
        jobs._dispatch_pending_variants('p1')
        original = project.path.read_bytes()
        control.blocked = True
        executor.gates[project.draft.id].set()
        executor.futures[0].result(timeout=3)
        control.blocked = False
        project.path.write_text(json.dumps(invalid))
        malformed = project.path.read_bytes()
        assert project.client.get('/projects/').status_code == 200
        assert project.path.read_bytes() == malformed
        assert store.has_pending_receipts('p1')
        project.path.write_bytes(original)
        assert project.client.get('/projects/').status_code == 200
        assert json.loads(project.path.read_bytes())['generation']['status'] == 'partial'
    finally:
        control.blocked = False
        executor.close()


def test_real_render_submission_rejection_then_read_denial_cannot_leave_a_queued_job(project, monkeypatch):
    from backend.services.studio.models import ImportOptions
    executor = GatedCalls()
    inert_worker_services(project, monkeypatch)
    monkeypatch.setattr(jobs, 'executor', executor)
    store.change('p1', lambda data: data.update(analysis=None, output_variants=[data['output_variants'][0]]))
    control = deny_reads(project, monkeypatch, 'persistent')
    rejected = []
    def reject(*args, **kwargs):
        rejected.append(True)
        control.blocked = True
        raise RuntimeError('real executor rejection; no child Future accepted')
    monkeypatch.setattr(jobs, 'render_executor', SimpleNamespace(submit=reject))
    try:
        jobs.inspect_project('p1', ImportOptions(auto_start=True, platforms=['original']))
        executor.drain()
        assert rejected == [True]
        assert len(executor.calls) == 2  # accepted screening and production parents only
        assert project.client.get('/studio/p1').status_code == 500
        control.blocked = False
        assert project.client.get('/projects/').status_code == 200
        state = project.client.get('/studio/p1').json()
        variant = next(v for v in state['output_variants'] if v['id'] != 'ready')
        job = next(j for j in state['jobs'] if j['job_id'] == variant['render_job_id'])
        assert job['status'] == variant['status'] == 'failed'
        assert state['generation']['status'] == 'partial'
        assert state['analysis']['status'] == 'completed'
        assert project.client.get('/projects/p1').json()['status'] == 'failed'
        assert not store.has_pending_receipts('p1')
        assert json.loads(project.path.read_bytes())['generation']['status'] == 'partial'
        assert project.ready.read_bytes() == b'existing completed output'
    finally:
        control.blocked = False
        executor.close()


def test_unaccepted_export_read_denial_creates_no_worker_or_receipt(project, monkeypatch):
    executor = GatedExecutor()
    monkeypatch.setattr(jobs, 'render_executor', executor)
    control = deny_reads(project, monkeypatch, 'persistent')
    saved = project.path.read_bytes()
    try:
        control.blocked = True
        with pytest.raises(PermissionError):
            jobs.export('p1', project.draft)
        assert not executor.futures
        assert not store.has_pending_receipts('p1')
        assert project.path.read_bytes() == saved
    finally:
        control.blocked = False
        executor.close()


@pytest.mark.parametrize('public', ['inspect', 'analyze', 'confirm', 'preparation', 'cover', 'export'])
def test_each_persisted_reservation_rejection_recovers_without_a_phantom_worker(project, monkeypatch, public):
    from copy import deepcopy
    from backend.services.studio.models import ImportOptions, ConfirmPlan, Preferences
    plan = inert_worker_services(project, monkeypatch)
    def initial(data):
        data['analysis'] = {'status': 'awaiting_confirmation', 'run_id': 'prior'} if public == 'confirm' else None
        data['generation'] = {'status': 'completed', 'auto_start': False}
        data['plan'] = deepcopy(plan)
        data['output_variants'] = [data['output_variants'][0]]
        data['output_variants'][0]['strategy_id'] = 'original'
        if public == 'preparation':
            data['output_variants'].append({'id': 'active', 'draft_id': project.draft.id, 'draft_revision': 1,
                                           'strategy_id': 'original', 'branding': {}, 'status': 'on_demand'})
    store.change('p1', initial)
    control = deny_reads(project, monkeypatch, 'persistent')
    rejected = []
    def reject(*args, **kwargs):
        rejected.append(True)
        control.blocked = True
        raise RuntimeError('real public submission rejected before accepting a Future')
    for name in ('executor', 'cover_executor', 'render_executor'):
        monkeypatch.setattr(jobs, name, SimpleNamespace(submit=reject))
    def request():
        if public == 'inspect':
            return jobs.inspect_project('p1', ImportOptions(auto_start=False, platforms=['original']))
        if public == 'analyze':
            return jobs.analyze_project('p1', Preferences())
        if public == 'confirm':
            return jobs.confirm_project('p1', ConfirmPlan(plan_id=store.read('p1')['plan']['id'], goals=['content'], analysis_mode='subtitle'))
        if public == 'preparation':
            return jobs.produce_variant('p1', 'active')
        if public == 'cover':
            return jobs.request_ai_cover('p1', 'ready')
        return jobs.export('p1', project.draft)
    executor = GatedCalls()
    try:
        with pytest.raises(PermissionError):
            request()
        assert rejected == [True]
        assert not executor.calls
        assert project.client.get('/studio/p1').status_code == 500
        control.blocked = False
        state = project.client.get('/studio/p1').json()
        if public == 'export':
            assert state['jobs'][0]['status'] == 'failed'
            assert '未能启动' in state['jobs'][0]['error']
        elif public == 'cover':
            assert state['output_variants'][0]['cover_job']['status'] == 'failed'
        elif public == 'preparation':
            variant = next(v for v in state['output_variants'] if v['id'] == 'active')
            assert variant['status'] == 'failed' and variant['needs_prepare']
        else:
            assert state['analysis']['status'] == 'failed'
        assert not store.has_pending_receipts('p1')
        assert json.loads(project.path.read_bytes()) == store.read('p1', recover=False)
        for name in ('executor', 'cover_executor', 'render_executor'):
            monkeypatch.setattr(jobs, name, executor)
        if public == 'preparation':
            jobs.retry_variant('p1', 'active')
        elif public == 'confirm':
            jobs.inspect_project('p1', ImportOptions(auto_start=False, platforms=['original']))
            executor.drain()
            request()
        else:
            request()
        assert executor.calls
        executor.drain()
        state = project.client.get('/studio/p1').json()
        if public == 'export':
            assert state['jobs'][0]['status'] == 'completed'
        elif public == 'cover':
            assert state['output_variants'][0]['cover_job']['status'] == 'completed'
        elif public == 'preparation':
            assert next(v for v in state['output_variants'] if v['id'] == 'active')['status'] == 'completed'
        else:
            assert state['analysis']['status'] in ('awaiting_confirmation', 'completed')
        assert project.source.read_bytes() == b'synthetic source; never decoded'
        assert project.ready.read_bytes() == b'existing completed output'
    finally:
        control.blocked = False
        executor.close()


@pytest.mark.parametrize('links', [None, 7, [], ['scalar'], [[]], [['short']], [{'invalid': True}]])
def test_malformed_optional_saved_links_are_ignored_without_rewriting_state(project, links):
    data = json.loads(project.path.read_bytes())
    data['jobs'][0]['variant_links'] = links
    project.path.write_text(json.dumps(data))
    original = project.path.read_bytes()
    assert project.client.get('/studio/p1').status_code == 200
    assert project.client.get('/projects/').status_code == 200
    assert project.path.read_bytes() == original
    assert store.read('p1', recover=False)['jobs'][0]['variant_links'] == links
