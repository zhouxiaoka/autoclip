"""R30 #419 I490-I496: appending platforms runs the full attempt lifecycle (check + open inside the lock, then
prepare, then persist or settle failed; the receipt goes back to the caller). Real jobs.append_platform_variants /
attempts / store.settle_generation; only media, framing, packaging and rendering are stubbed."""
import pytest
from fastapi import HTTPException

from backend.api.v1 import studio as studio_api
from backend.services.studio import attempts, jobs, store


def _state(monkeypatch, on_demand=False, error=None):
    from backend.tests.test_on_demand_variants import _auto_fixture, _base
    state, _ = _auto_fixture(monkeypatch, [_base(n, 1) for n in range(2)], ['douyin'])
    state['attempts'] = [{'attempt_id': 't-gen', 'kind': 'generation', 'state': 'open', 'sequence': 1, 'plan_id': 'plan-a',
                          'flow_id': 'f-1', 'summary': {'route': 'subtitle'}}]
    state['attempt_sequence'] = 1
    state['generation']['attempt_id'] = 't-gen'
    jobs._auto_generate('p1', {'id': 'plan-a'})
    for v in state['output_variants']:
        v['status'] = 'on_demand' if on_demand else ('failed' if error else 'completed')
        if error:
            v.update(error='OLD-ROUND', error_code='timeout')
    store.settle_generation(state)
    attempts.reconcile(state)
    state['attempts'][0]['summary']['route'] = 'subtitle'                # what the screening record froze
    return state


def _append(platforms=('bilibili',)):
    return jobs.append_platform_variants('p1', list(platforms), {'outro_enabled': False})


def _added(state, result):
    ids = {v['id'] for v in result['variants']}
    return [v for v in state['output_variants'] if v['id'] in ids]


# --- I490: the receipt goes back to the caller (the frontend watches it like a retry's) ---

def test_i490_append_returns_its_attempt_receipt(monkeypatch):
    state = _state(monkeypatch)
    result = _append()
    receipt = attempts.current(state)
    assert result['attempt']['attempt_id'] == receipt['attempt_id'] and result['attempt']['trigger'] == 'append_platform'
    assert result['attempt']['kind'] == 'generation' and result['variants']


def test_i490_preparation_failure_settles_the_attempt_failed_and_still_returns_the_receipt(monkeypatch):
    state = _state(monkeypatch)
    def boom(*_a, **_k):
        raise TimeoutError('framing timed out')
    monkeypatch.setattr(jobs, '_apply_framing', boom)
    before = len(state['output_variants'])
    result = _append()
    attempts.reconcile(state)                                             # store.write settles (stubbed store here)
    receipt = attempts.find(state, result['attempt']['attempt_id'])
    assert receipt['state'] == 'failed' and result['variants'] == [] and len(state['output_variants']) == before
    assert state['attempts'][0]['state'] == 'completed'          # the finished round is untouched


# --- I491: plan/route from the output the new version derives from ---

def test_i491_source_is_the_latest_output_of_the_derived_moment_not_the_oldest(monkeypatch):
    state = _state(monkeypatch)
    first = state['output_variants'][0]
    state['output_variants'].insert(0, {**first, 'id': 'older', 'strategy_id': 'tiktok', 'produced_by_attempt': 't-old', 'produced_by_plan': 'plan-old'})
    state['attempts'].insert(0, {'attempt_id': 't-old', 'kind': 'generation', 'state': 'completed', 'sequence': 0, 'plan_id': 'plan-old', 'summary': {'route': 'visual'}})
    state['attempts'].append({'attempt_id': 't-retry', 'kind': 'generation', 'state': 'completed', 'sequence': 2, 'plan_id': 'plan-a', 'sources': ['t-gen'], 'summary': {'route': 'subtitle'}})
    state['generation']['attempt_id'] = 't-retry'                         # after a variant retry (no own stamps)
    _append()
    receipt = attempts.current(state)
    assert receipt['plan_id'] == 'plan-a' and receipt['inherited']['route'] == 'subtitle'


def test_i491_an_unrelated_older_round_without_the_moment_is_never_the_source(monkeypatch):
    state = _state(monkeypatch)   # Dong Q1: an older stamped output whose draft is gone
    state['output_variants'].insert(0, {'id': 'old', 'status': 'completed', 'strategy_id': 'xx', 'draft_id': 'none', 'produced_by_attempt': 't-old', 'produced_by_plan': 'plan-old'})
    state['attempts'].insert(0, {'attempt_id': 't-old', 'kind': 'generation', 'state': 'completed', 'sequence': 0, 'plan_id': 'plan-old', 'summary': {'route': 'visual'}})
    state['attempts'].append({'attempt_id': 't-retry', 'kind': 'generation', 'state': 'completed', 'sequence': 2, 'plan_id': 'plan-a', 'sources': ['t-gen'], 'summary': {'route': 'subtitle'}})
    state['generation']['attempt_id'] = 't-retry'                         # after a variant retry (no own stamps)
    _append()
    assert attempts.current(state)['plan_id'] == 'plan-a'


# --- I492: check and open first, prepare after; an existing platform is a coded 409 ---

def test_i492_existing_platform_is_a_coded_409_before_any_preparation_or_attempt(monkeypatch):
    state = _state(monkeypatch)
    monkeypatch.setattr(jobs, '_apply_framing', lambda *a, **k: pytest.fail('prepared before the check'))
    with pytest.raises(store.ConflictError) as caught:   # AppendRejected
        _append(['douyin'])
    assert (getattr(caught.value, 'error_code', None), getattr(caught.value, 'status', None)) == ('append_platform_exists', 409)
    assert len(state['attempts']) == 1


def test_i492_running_attempt_refuses_before_preparation(monkeypatch):
    state = _state(monkeypatch)
    _append()
    monkeypatch.setattr(jobs, '_apply_framing', lambda *a, **k: pytest.fail('prepared before the check'))
    with pytest.raises(store.ConflictError) as caught:   # AppendRejected
        _append(['xiaohongshu'])
    assert getattr(caught.value, 'error_code', None) == 'append_attempt_running' and len(state['attempts']) == 2


def test_i492_preparation_runs_after_the_attempt_is_open(monkeypatch):
    state = _state(monkeypatch)
    seen = []
    real = jobs._apply_framing
    monkeypatch.setattr(jobs, '_apply_framing', lambda *a, **k: (seen.append(attempts.current(state) and attempts.current(state)['trigger']), real(*a, **k))[1])
    _append()
    assert seen and set(seen) == {'append_platform'}


# --- I493: a new round starts without the previous round's terminal fields ---

def test_i493_failed_append_after_a_failed_round_does_not_reuse_the_old_error(monkeypatch):
    state = _state(monkeypatch, error=True)
    assert state['generation']['error'] == 'OLD-ROUND'
    result = _append()
    assert 'error' not in state['generation'] and 'not_redone_failed_count' not in state['generation']
    for v in _added(state, result):
        if v['status'] != 'on_demand':
            v.update(status='failed', error_code='timeout')
    store.settle_generation(state)
    assert state['generation']['status'] == 'failed' and state['generation'].get('error') != 'OLD-ROUND'


# --- I494: nothing automatic -> coded 400, no attempt ---

def test_i494_all_on_demand_is_a_400_without_an_attempt(monkeypatch):
    state = _state(monkeypatch, on_demand=True)
    with pytest.raises(store.ConflictError) as caught:   # AppendRejected
        _append()
    assert (getattr(caught.value, 'error_code', None), getattr(caught.value, 'status', None)) == ('append_no_auto_output', 400)
    assert len(state['attempts']) == 1 and attempts.current(state) is None


# --- I495: a manual retry waiting for confirmation is not abandoned ---

def test_i495_pending_manual_retry_is_a_coded_409_and_stays_open(monkeypatch):
    state = _state(monkeypatch)
    state['attempts'].append({'attempt_id': 't-man', 'kind': 'production', 'state': 'open', 'sequence': 2, 'flow_id': 'f-1', 'retry_of': 't-gen', 'run_id': None})
    with pytest.raises(store.ConflictError) as caught:   # AppendRejected
        _append()
    assert (getattr(caught.value, 'error_code', None), getattr(caught.value, 'status', None)) == ('append_retry_pending', 409)
    assert attempts.find(state, 't-man')['state'] == 'open' and len(state['attempts']) == 2


# --- I496: no unread run_id; no stamping without an open attempt ---

def test_i496_append_receipt_has_no_run_id_and_own_outputs_needs_an_open_attempt(monkeypatch):
    state = _state(monkeypatch)
    _append()
    assert attempts.current(state).get('run_id') is None
    data = {'generation': {'attempt_id': 't-x'}, 'attempts': [{'attempt_id': 't-x', 'kind': 'generation', 'state': 'completed'}]}
    item = {'id': 'v'}
    attempts.own_outputs(data, [item])
    assert 'produced_by_attempt' not in item


# --- HTTP: the coded refusals keep their status and code ---

@pytest.mark.parametrize('code,status', [('append_platform_exists', 409), ('append_no_auto_output', 400), ('append_retry_pending', 409)])
def test_coded_refusal_maps_to_its_status_and_error_code(code, status):
    def refuse():
        raise attempts.AppendRejected('x', code, status=status)
    with pytest.raises(HTTPException) as caught:
        studio_api.call(refuse)
    assert caught.value.status_code == status and caught.value.detail['error_code'] == code
