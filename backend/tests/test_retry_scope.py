"""1.5.7 retry scope. Appending platforms does not run. An attempt with no outputs of its own is not
recorded completed from older renders. A refused dispatch does not fail a newer attempt."""
import pytest

from backend.services.studio import attempts, jobs, store
from backend.tests.test_studio import client, root, source  # noqa: F401  pytest fixtures


def _project():
    store.write('p1', {
        'schema_version': 2, 'drafts': [], 'events': [], 'jobs': [], 'output_variants': [],
        'generation': {'status': 'production', 'attempt_id': 't-old', 'auto_start': True},
        'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'run-old', 'instance': store.INSTANCE},
        'attempts': [{'attempt_id': 't-old', 'kind': 'generation', 'state': 'open', 'sequence': 1,
                      'run_id': 'run-old', 'trigger': 'initial'}],
        'attempt_sequence': 1,
    })


def test_append_entry_refuses_and_changes_nothing(client, root):
    _project()
    before = store.read('p1')
    with pytest.raises(attempts.AppendRejected) as caught:
        jobs.append_platform_variants('p1', ['tiktok'], {'outro_enabled': False})
    assert caught.value.error_code == 'append_platform_unavailable' and caught.value.status == 409
    response = client.post('/studio/p1/platforms', json={'platforms': ['tiktok']})
    assert response.status_code == 409, response.text
    assert response.json()['detail']['error_code'] == 'append_platform_unavailable'
    assert store.read('p1') == before


def test_open_retry_with_no_own_output_is_not_completed_from_older_renders():
    """generation.status is shared. Flipping it to rendering must not settle this attempt on older outputs."""
    state = {
        'generation': {'attempt_id': 't-retry', 'status': 'rendering', 'auto_start': True},
        'attempts': [{'attempt_id': 't-retry', 'kind': 'generation', 'state': 'open', 'sequence': 2,
                      'retry_of': 't-old', 'trigger': 'retry'}],
        'output_variants': [{'id': 'v1', 'status': 'completed', 'produced_by_attempt': 't-old',
                             'strategy_id': 'douyin', 'draft_id': 'd'}],
        'drafts': [], 'analysis': {}, 'jobs': [],
    }
    assert attempts.round_outputs(state) == []
    store.settle_generation(state)
    assert state['generation']['status'] == 'rendering'
    assert state['attempts'][0]['state'] == 'open'


def test_dispatch_rejection_fails_only_the_attempt_still_current(root, monkeypatch):
    _project()
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)

    class Boom:
        def submit(self, fn, *args, **kwargs):
            raise RuntimeError('queue full')

    monkeypatch.setattr(jobs, 'executor', Boom())
    jobs._submit_production('p1', 'run-old', None, attempt_id='t-old')
    state = store.read('p1')
    assert state['generation']['status'] == 'failed'
    assert state['generation']['failure_stage'] == 'dispatch'
    assert state['generation']['attempt_id'] == 't-old'
    assert attempts.find(state, 't-old')['state'] == 'failed'


def test_dispatch_rejection_does_not_close_a_newer_attempt(root, monkeypatch):
    """fail_automatic used to write generation with no attempt/run check."""
    _project()
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)

    class Takeover:
        def submit(self, fn, *args, **kwargs):
            def takeover(data):
                for item in data['attempts']:
                    if item['attempt_id'] == 't-old':
                        item.update(state='abandoned')
                data['attempts'].append({'attempt_id': 't-newer', 'kind': 'generation', 'state': 'open', 'sequence': 2,
                                         'retry_of': 't-old', 'trigger': 'retry', 'run_id': 'run-newer'})
                data['generation'].update(attempt_id='t-newer', status='screening')
                data['analysis'] = {'status': 'running', 'phase': 'screening', 'run_id': 'run-newer', 'instance': store.INSTANCE}
            store.change('p1', takeover)
            raise RuntimeError('queue full')

    monkeypatch.setattr(jobs, 'executor', Takeover())
    jobs._submit_production('p1', 'run-old', None, attempt_id='t-old')
    state = store.read('p1')
    assert state['generation']['attempt_id'] == 't-newer'
    assert state['generation']['status'] == 'screening'
    assert state['analysis']['run_id'] == 'run-newer'
    assert attempts.find(state, 't-newer')['state'] == 'open'
    assert attempts.find(state, 't-old')['state'] == 'abandoned'
