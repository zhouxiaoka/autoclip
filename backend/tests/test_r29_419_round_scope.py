"""R29 #419 I440-I445: missing attempt record falls back to the whole workspace; appending platforms is its own
attempt; on_demand-only scope; N and error wording scoped to this round. Real store.settle_generation /
attempts.reconcile / jobs.append_platform_variants; only rendering and media are stubbed."""
import pytest

from backend.services.studio import attempts, jobs, store
from backend.services.studio.store import ConflictError


def _data(attempt_id, variants, records=()):
    return {'generation': {'status': 'rendering', 'attempt_id': attempt_id}, 'jobs': [], 'output_variants': variants,
            'attempts': [dict(r) for r in records]}


# --- I440: only attempt_id is left, the record is gone -> whole workspace ---

def test_i440_missing_record_with_stamps_left_is_judged_on_the_whole_workspace():
    data = _data('t-gone', [{'id': 'a', 'status': 'completed', 'produced_by_attempt': 't-gone'},
                            {'id': 'b', 'status': 'failed', 'error_code': 'timeout', 'produced_by_attempt': 't-old'}])
    assert attempts.round_outputs(data) is None   # R31: owners_of removed (scope = this attempt's stamps only)
    store.settle_generation(data)
    assert (data['generation']['status'], data['generation']['error_code']) == ('partial', 'timeout')   # not 'completed'


def test_i440_missing_record_with_only_on_demand_stamped_is_not_a_validation_failure():
    data = _data('t-gone', [{'id': 'a', 'status': 'on_demand', 'produced_by_attempt': 't-gone'},
                            {'id': 'b', 'status': 'completed'}])
    store.settle_generation(data)
    assert data['generation']['status'] == 'completed' and data['generation'].get('error_code') != 'validation'


# --- I442: a recorded round whose stamped outputs are all on_demand -> validation (unchanged behaviour) ---

def test_i442_recorded_round_with_only_on_demand_outputs_is_validation():
    data = _data('t-1', [{'id': 'a', 'status': 'on_demand', 'produced_by_attempt': 't-1'},
                         {'id': 'old', 'status': 'completed', 'produced_by_attempt': 't-0'}],
                 records=[{'attempt_id': 't-1', 'kind': 'generation', 'state': 'open', 'sequence': 2}])
    store.settle_generation(data)
    assert (data['generation']['status'], data['generation']['error_code']) == ('failed', 'validation')
    assert data['generation']['error'] == '没有自动生成的成片，可选择备选片段继续生成'


# --- I444: N counts only failed outputs outside the round; the error text comes from the round only ---

def test_i444_not_redone_counts_only_failed_outside_outputs():
    data = _data('t-2', [{'id': 'old-bad', 'status': 'failed', 'produced_by_attempt': 't-1'},
                         {'id': 'old-queued', 'status': 'queued', 'produced_by_attempt': 't-1'},
                         {'id': 'old-backup', 'status': 'on_demand', 'produced_by_attempt': 't-1'},
                         {'id': 'new', 'status': 'completed', 'produced_by_attempt': 't-2'}],
                 records=[{'attempt_id': 't-2', 'kind': 'generation', 'state': 'open', 'sequence': 2}])
    store.settle_generation(data)
    assert data['generation']['status'] == 'completed' and data['generation']['not_redone_failed_count'] == 1


def test_i444_error_text_comes_from_this_round_only():
    data = _data('t-2', [{'id': 'old-bad', 'status': 'failed', 'error': 'OLD-ROUND', 'produced_by_attempt': 't-1'},
                         {'id': 'new-bad', 'status': 'failed', 'error_code': 'timeout', 'produced_by_attempt': 't-2'}],
                 records=[{'attempt_id': 't-2', 'kind': 'generation', 'state': 'open', 'sequence': 2}])
    store.settle_generation(data)
    assert data['generation']['status'] == 'failed' and data['generation'].get('error') != 'OLD-ROUND'
    assert data['analysis'].get('error') != 'OLD-ROUND'


# --- I441: appending platforms is a new attempt with its own settle, receipt and terminal ---

@pytest.fixture
def appended(monkeypatch):
    from backend.tests.test_on_demand_variants import _auto_fixture, _base
    state, _exports = _auto_fixture(monkeypatch, [_base(n, 1) for n in range(2)], ['douyin'])
    from backend.tests.test_r30_419_append_lifecycle import _Inline
    monkeypatch.setattr(jobs, 'executor', _Inline())                      # R31: preparation is a background job
    state['attempts'] = [{'attempt_id': 't-gen', 'kind': 'generation', 'state': 'open', 'sequence': 1, 'plan_id': 'plan-a',
                          'flow_id': 'f-1', 'summary': {'route': 'subtitle', 'recommendation_mode': 'local'}}]
    state['attempt_sequence'] = 1
    state['generation']['attempt_id'] = 't-gen'
    jobs._auto_generate('p1', {'id': 'plan-a'})
    for v in state['output_variants']:
        v['status'] = 'completed'
    store.settle_generation(state)
    attempts.reconcile(state)
    assert state['attempts'][0]['state'] == 'completed'
    state['attempts'][0]['summary']['route'] = 'subtitle'                # what the screening record froze
    first = dict(state['attempts'][0])
    before = {v['id'] for v in state['output_variants']}
    jobs.append_platform_variants('p1', ['bilibili'], {'outro_enabled': False})
    added = [v for v in state['output_variants'] if v['id'] not in before]
    return state, first, added


def test_i441_append_opens_its_own_attempt_inheriting_plan_and_route(appended):
    state, first, added = appended
    receipt = attempts.current(state)
    assert receipt and receipt['attempt_id'] != 't-gen' and receipt['trigger'] == 'append_platform'
    assert state['generation']['attempt_id'] == receipt['attempt_id'] and receipt['retry_of'] is None
    assert receipt['plan_id'] == 'plan-a' and receipt['inherited']['route'] == 'subtitle'
    assert not receipt.get('sources')                                     # old outputs are not this round's
    assert added and {(v['produced_by_attempt'], v.get('produced_by_plan')) for v in added} == {(receipt['attempt_id'], 'plan-a')}
    assert state['attempts'][0] == first                                  # the finished round is untouched


def test_i441_failed_append_settles_its_own_receipt_and_terminal(appended):
    state, first, added = appended
    automatic = [v for v in added if v['status'] != 'on_demand']
    assert len(automatic) >= 2
    automatic[0]['status'] = 'completed'
    for v in automatic[1:]:
        v.update(status='failed', error_code='timeout')
    store.settle_generation(state)
    attempts.reconcile(state)
    receipt = state['attempts'][-1]
    assert state['generation']['status'] == receipt['state'] == 'partial'
    assert receipt['error_code'] == 'timeout' and receipt['summary']['variant_count'] == len(added)
    assert state['attempts'][0] == first and first['state'] == 'completed'


def test_i441_append_is_refused_while_another_attempt_runs(appended):
    state, _first, _added = appended
    with pytest.raises(ConflictError):
        jobs.append_platform_variants('p1', ['xiaohongshu'], {'outro_enabled': False})
