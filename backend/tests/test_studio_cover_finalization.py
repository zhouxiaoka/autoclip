"""Saved videos stay active until their own optional designed cover settles.

Actual dispatcher/Future/store/HTTP callers, inert renderer/cover bytes only.
No model, frame extraction, media encoding, external request or native UI.
"""
import json
import threading

import pytest

from backend.services.studio import jobs, publish_kit, store
from backend.tests.test_studio_read_failure import GatedExecutor, assert_preserved, deny_reads, project  # noqa: F401

DESIGN_COVERS = jobs._design_covers


@pytest.mark.parametrize('before_link', [False, True])
@pytest.mark.parametrize('cover_success', [True, False])
def test_actual_render_completed_read_cannot_stop_card_poll_before_cover_finishes(project, monkeypatch, cover_success, before_link):
    executor = GatedExecutor()
    monkeypatch.setattr(jobs, 'render_executor', executor)
    monkeypatch.setattr(jobs, 'render_draft', lambda *a, **k: {'path': 'saved.mp4'})
    monkeypatch.setattr(jobs, '_design_covers', DESIGN_COVERS)
    monkeypatch.setattr(jobs, 'request_ai_cover', lambda *a: None)
    store.change('p1', lambda data: data['output_variants'][1].update(strategy_id='douyin'))
    started, release = threading.Event(), threading.Event()
    def design(*args):
        started.set()
        assert release.wait(3), 'cover scheduling barrier was not released'
        if not cover_success:
            raise ValueError('synthetic optional cover failure')
        (project.root / 'output' / 'designed-cover.jpg').write_bytes(b'synthetic cover; never decoded')
    monkeypatch.setattr(publish_kit, 'design_cover', design)
    change = store.change
    if before_link:
        deferred = []
        def bind_after_cover_started(pid, mutate):
            if threading.current_thread() is threading.main_thread() and executor.futures and not deferred:
                deferred.append(True)
                executor.gates[project.draft.id].set()
                assert started.wait(3)
                pending = store.read('p1')
                assert next(v for v in pending['output_variants'] if v['id'] == 'active')['status'] in ('queued', 'running')
            return change(pid, mutate)
        monkeypatch.setattr(store, 'change', bind_after_cover_started)
    try:
        jobs._dispatch_pending_variants('p1')
        executor.gates[project.draft.id].set()
        assert started.wait(3)
        assert not executor.futures[0].done()
        for _ in range(2):
            response = project.client.get('/studio/p1')
            assert response.status_code == 200
            pending = response.json()
            variant = next(v for v in pending['output_variants'] if v['id'] == 'active')
            job = next(j for j in pending['jobs'] if j['job_id'] == variant['render_job_id'])
            assert job['status'] == 'completed' and job['result'] == {'path': 'saved.mp4'}
            # These are the actual existing pollWorkspace conditions, with the
            # already saved video available while the optional work is active.
            assert variant['status'] in ('queued', 'running')
            assert pending['generation']['status'] == 'rendering'
            assert pending['analysis']['status'] == 'running'
            assert not variant.get('cover')
        release.set()
        executor.futures[0].result(timeout=3)
        completed = project.client.get('/studio/p1').json()
        variant = next(v for v in completed['output_variants'] if v['id'] == 'active')
        job = next(j for j in completed['jobs'] if j['job_id'] == variant['render_job_id'])
        assert job['status'] == variant['status'] == 'completed'
        assert job['result'] == {'path': 'saved.mp4'}
        assert not job.get('cover_pending')
        assert completed['generation']['status'] == 'completed'
        assert completed['analysis']['status'] == 'completed'
        assert variant.get('cover') == ('design' if cover_success else None)
        assert_preserved(project, completed)
    finally:
        release.set()
        executor.close()


def test_restart_finishes_optional_cover_fence_without_revoking_committed_video(project, monkeypatch):
    state = store.read('p1')
    variant = state['output_variants'][1]
    expected = store.variant_identity(variant)
    variant['render_job_id'] = 'saved-job'
    state['jobs'].append({'job_id': 'saved-job', 'status': 'completed', 'instance': 'previous-server',
                          'cover_pending': True, 'result': {'path': 'saved.mp4'}, 'variant_links': [list(expected)]})
    store.write('p1', state)
    result = project.client.get('/studio/p1').json()
    assert next(v for v in result['output_variants'] if v['id'] == 'active')['status'] == 'completed'
    job = next(j for j in result['jobs'] if j['job_id'] == 'saved-job')
    assert job['status'] == 'completed' and job['result'] == {'path': 'saved.mp4'}
    assert not job.get('cover_pending')
    assert result['generation']['status'] == 'completed'
    durable = json.loads(project.path.read_bytes())
    saved = next(j for j in durable['jobs'] if j['job_id'] == 'saved-job')
    assert saved['status'] == 'completed' and saved['result'] == job['result']
    assert not saved['cover_pending'] and saved['instance'] == 'previous-server'
    assert_preserved(project, result)


@pytest.mark.parametrize('failure', ['read', 'atomic_write'])
def test_finished_cover_worker_metadata_denial_cannot_leave_pending_or_lose_video(project, monkeypatch, failure):
    executor = GatedExecutor()
    monkeypatch.setattr(jobs, 'render_executor', executor)
    monkeypatch.setattr(jobs, 'render_draft', lambda *a, **k: {'path': 'saved.mp4'})
    control = deny_reads(project, monkeypatch, 'persistent')
    blocked = {'value': False}
    replace = store._replace_state
    def deny_replace(src, dst):
        if blocked['value'] and dst == project.path:
            raise PermissionError('synthetic terminal write refusal')
        return replace(src, dst)
    monkeypatch.setattr(store, '_replace_state', deny_replace)
    def cover(*args):
        if failure == 'read':
            control.blocked = True
            store.read('p1')
        else:
            blocked['value'] = True
    monkeypatch.setattr(jobs, '_design_covers', cover)
    try:
        jobs._dispatch_pending_variants('p1')
        executor.gates[project.draft.id].set()
        # The worker may report its terminal I/O refusal, but must finish and
        # release only its own optional cover fence once access returns.
        executor.futures[0].exception(timeout=3)
        control.blocked = False
        blocked['value'] = False
        recovered = project.client.get('/studio/p1').json()
        variant = next(v for v in recovered['output_variants'] if v['id'] == 'active')
        job = next(j for j in recovered['jobs'] if j['job_id'] == variant['render_job_id'])
        assert job['status'] == variant['status'] == 'completed'
        assert job['result'] == {'path': 'saved.mp4'}
        assert not job.get('cover_pending')
        assert recovered['generation']['status'] == 'completed'
        assert json.loads(project.path.read_bytes())['generation']['status'] == 'completed'
        assert_preserved(project, recovered)
    finally:
        control.blocked = False
        blocked['value'] = False
        executor.close()


@pytest.mark.parametrize('linked_variant', [True, False])
def test_old_cover_finish_receipt_cannot_finish_a_new_attempt_or_sibling(project, linked_variant):
    state = store.read('p1')
    variant = state['output_variants'][1]
    old_identity = store.variant_identity(variant)
    state['jobs'].append({'job_id': 'old', 'status': 'completed', 'instance': store.INSTANCE,
                          'cover_pending': True, 'result': {'path': 'old.mp4'}, 'variant_links': [list(old_identity)]})
    if linked_variant:
        variant['render_attempt_id'] = 'new-attempt'
        current = variant
    else:
        variant['render_job_id'] = 'old'
        current = {**variant, 'id': 'sibling', 'render_attempt_id': 'sibling-attempt'}
        state['output_variants'].append(current)
    current['render_job_id'] = 'new'
    state['jobs'].append({'job_id': 'new', 'status': 'completed', 'instance': store.INSTANCE,
                          'cover_pending': True, 'result': {'path': 'new.mp4'}, 'variant_links': [list(store.variant_identity(current))]})
    store.write('p1', state)
    with store.worker_read_scope('p1', ('render', 'old')):
        store.mark_render_finished('p1', 'old')
    result = project.client.get('/studio/p1').json()
    old = next(j for j in result['jobs'] if j['job_id'] == 'old')
    new = next(j for j in result['jobs'] if j['job_id'] == 'new')
    active = next(v for v in result['output_variants'] if v['id'] == current['id'])
    assert not old['cover_pending'] and old['result'] == {'path': 'old.mp4'}
    assert new['cover_pending'] and new['result'] == {'path': 'new.mp4'}
    assert active['render_job_id'] == 'new' and active['status'] == 'queued'
    assert result['generation']['status'] == 'rendering'
    assert not store.has_pending_receipts('p1')
    assert_preserved(project, result)
