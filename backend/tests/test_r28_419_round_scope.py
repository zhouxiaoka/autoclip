"""R28 #409-#413. One scope rule (attempts.round_outputs) judges a generation round: store.settle_generation's
status / counts / error code / wording / 'all done' gate and the receipt summary. Real inspect_project, _inspect,
retry_variant, store.write; only planning.recommend and the executor are stubbed."""
import pytest

from backend.services.studio import attempts, jobs, store
from backend.tests import attempt_flow as flow
from backend.tests.test_r27_419_output_owner import PLAN_A, PLAN_B, _plan_a_partial, _screen_and_plan

OK, BAD = ('completed', None, None), ('failed', 'timeout', None)


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    flow.setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'ensure_project_thumbnail', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'source', lambda pid: store.directory(pid) / 'input.mp4')


def _rerun(pid, monkeypatch, first, outcome):
    _screen_and_plan(pid, monkeypatch, PLAN_B, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.render_outcome(pid, outcome)
    return store.read(pid), flow.receipts(pid)[-1]


def test_409a_previous_round_failure_does_not_taint_an_all_successful_rerun(monkeypatch):
    pid = flow.new_project()
    _plan_a, first = _plan_a_partial(pid, monkeypatch)                    # round A: ok + bad (timeout)
    data, receipt = _rerun(pid, monkeypatch, first, {'new': OK})
    g = data['generation']
    assert (g['status'], g['completed_variant_count'], g.get('error_code')) == ('completed', 1, None)
    assert g['not_redone_failed_count'] == 1
    assert data['analysis']['outcome'] == 'completed' and 'error_code' not in data['analysis']
    assert receipt['state'] == 'completed' and 'error_code' not in receipt
    assert len(data['output_variants']) == 3                              # the page still lists every output


def test_409a_a_rerun_with_its_own_failure_is_partial(monkeypatch):
    pid = flow.new_project()
    _plan_a, first = _plan_a_partial(pid, monkeypatch)
    data, receipt = _rerun(pid, monkeypatch, first, {'new': OK, 'new2': ('failed', 'service_restarted', None)})
    g = data['generation']
    assert (g['status'], g['error_code'], receipt['state'], receipt['error_code']) == ('partial', 'service_restarted', 'partial', 'service_restarted')
    assert 'secondary_error_codes' not in g and g['not_redone_failed_count'] == 1                               # A's timeout is not a secondary cause


def test_409b_retrying_one_of_two_failures_stays_partial(monkeypatch):
    pid = flow.new_project()
    _screen_and_plan(pid, monkeypatch, PLAN_A)
    flow.render_outcome(pid, {'b1': BAD, 'b2': BAD})
    assert flow.receipts(pid)[0]['state'] == 'failed'
    flow.retry_variant(pid, 'b1', 'v1')
    flow.render_outcome(pid, {'b1': OK})
    data, receipt = store.read(pid), flow.receipts(pid)[1]
    assert (data['generation']['status'], data['generation']['error_code'], receipt['state']) == ('partial', 'timeout', 'partial')
    assert data['generation']['not_redone_failed_count'] == 0             # b2 is in scope, not "outside"


def _legacy(data):
    for v in data['output_variants']:
        v.pop('produced_by_attempt', None)
        v.pop('produced_by_plan', None)


def test_409c_unstamped_old_project_settles_as_before():
    old = {'generation': {'status': 'rendering'}, 'jobs': [], 'output_variants': [
        {'id': 'a', 'status': 'completed'}, {'id': 'b', 'status': 'failed', 'error_code': 'timeout'}, {'id': 'c', 'status': 'on_demand'}]}
    for generation_attempt in (None, 't-missing'):                       # no attempt record / attempt with no stamps
        data = {**old, 'generation': {'status': 'rendering', **({'attempt_id': generation_attempt} if generation_attempt else {})},
                'output_variants': [dict(v) for v in old['output_variants']]}
        store.settle_generation(data)
        assert (data['generation']['status'], data['generation']['completed_variant_count'], data['generation']['error_code']) == ('partial', 1, 'timeout')


def test_409d_variant_retry_of_an_unstamped_output_is_never_a_validation_failure(monkeypatch):
    pid = flow.new_project()
    _plan_a_partial(pid, monkeypatch)
    store.change(pid, _legacy)                                            # outputs from before the change
    flow.retry_variant(pid, 'bad', 'v1')
    flow.render_outcome(pid, {'bad': OK})
    data, receipt = store.read(pid), flow.receipts(pid)[1]
    assert data['generation']['status'] == 'completed' and data['generation'].get('error_code') != 'validation'
    assert receipt['state'] == 'completed' and 'variant_count' not in receipt['summary']   # no inferred counts


def test_409e_previous_round_queued_leftover_does_not_block_this_round(monkeypatch):
    pid = flow.new_project()
    _screen_and_plan(pid, monkeypatch, PLAN_A)
    flow.render_outcome(pid, {'ok': OK, 'stuck': ('queued', None, None)})
    def ended(d):  # round A ended without its leftover (a restart)
        d['generation'].update(status='failed', error_code='timeout')
        d['analysis'] = {'status': 'failed', 'phase': 'rendering', 'run_id': d['analysis'].get('run_id'), 'error_code': 'timeout'}
    store.change(pid, ended)
    first = flow.receipts(pid)[0]
    store.change(pid, lambda d: [r.update(state='failed') for r in attempts.receipts(d) if r['attempt_id'] == first['attempt_id']])
    data, receipt = _rerun(pid, monkeypatch, flow.receipts(pid)[0], {'new': OK})
    assert data['generation']['status'] == 'completed' and receipt['state'] == 'completed'
    assert data['generation']['not_redone_failed_count'] == 0             # R29 #444: a queued leftover is not N
    store.change(pid, lambda d: next(v for v in d['output_variants'] if v['id'] == 'stuck').update(status='completed'))
    assert store.read(pid)['generation']['status'] == 'completed'          # the leftover finishing later changes nothing


def test_409_the_receipt_and_settle_share_one_scope(monkeypatch):
    pid = flow.new_project()
    _plan_a, first = _plan_a_partial(pid, monkeypatch)
    data, receipt = _rerun(pid, monkeypatch, first, {'new': OK})
    assert [v['id'] for v in attempts.round_outputs(data)] == ['new']
    assert receipt['summary']['completed_variant_count'] == data['generation']['completed_variant_count'] == 1


# --- #410 / R29 #441 append_platform_variants stamps its outputs with its own attempt and the source plan ---

def test_410_appended_outputs_record_the_generation_round_and_plan(monkeypatch):
    from backend.tests.test_on_demand_variants import _auto_fixture, _base
    state, _exports = _auto_fixture(monkeypatch, [_base(n, 1) for n in range(2)], ['douyin'])
    state['attempts'] = [{'attempt_id': 't-gen', 'kind': 'generation', 'state': 'partial', 'sequence': 1, 'plan_id': 'plan-a'}]
    state['generation']['attempt_id'] = 't-gen'
    jobs._auto_generate('p1', {'id': 'plan-a'})
    before = {v['id'] for v in state['output_variants']}
    jobs.append_platform_variants('p1', ['bilibili'], {'outro_enabled': False})
    added = [v for v in state['output_variants'] if v['id'] not in before]
    # R29 #441: appending opens its own attempt; it inherits the source round's plan, not its stamp
    own = state['generation']['attempt_id']
    assert own != 't-gen' and added and {(v['produced_by_attempt'], v.get('produced_by_plan')) for v in added} == {(own, 'plan-a')}


# --- #411 the variant retry's route comes from the source output's plan ---

def test_411_variant_retry_after_a_failed_visual_rescreen_reports_the_captions_route(monkeypatch):
    pid = flow.new_project()
    _plan_a, first = _plan_a_partial(pid, monkeypatch)                    # A: captions (subtitle)
    _screen_and_plan(pid, monkeypatch, PLAN_B, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.production_failed_before_outputs(pid)                            # B: visual, fails
    assert store.read(pid)['generation']['route'] == 'visual'
    flow.retry_variant(pid, 'bad', 'v1')
    flow.render_outcome(pid, {'bad': OK})
    retried = flow.receipts(pid)[2]
    assert (retried['summary']['route'], retried['summary']['recommendation_mode']) == ('subtitle', 'local')


# --- #412 the bridge never re-stamps an old output ---

def test_412_bridge_keeps_an_old_stamp(tmp_path, monkeypatch):
    from backend.tests import receipt_bridge
    out = receipt_bridge.materialize({'kind': 'generation', 'run_id': 'r1', 'seed': 's', 'snapshot': {
        'plan': {'id': 'p-new', 'mode': 'ai'}, 'drafts': [], 'generation': {'status': 'partial'},
        'analysis': {'status': 'completed', 'phase': 'production'},
        'output_variants': [{'id': 'old', 'draft_id': 'd', 'strategy_id': 'douyin', 'status': 'failed', 'produced_by_attempt': 't-older'},
                            {'id': 'new', 'draft_id': 'd2', 'strategy_id': 'douyin', 'status': 'completed'}]}}, attempts, store)
    data = store.read('p')
    stamps = {v['id']: v['produced_by_attempt'] for v in data['output_variants']}
    assert stamps == {'old': 't-older', 'new': out['attempt_id']}
    receipt = next(a for a in out['attempts'] if a['attempt_id'] == out['attempt_id'])
    assert (receipt['summary']['variant_count'], receipt['summary']['completed_variant_count']) == (1, 1)   # its own output only


# --- #413 a joined variant retry keeps the FIRST retried output's plan ---

def test_413_joined_variant_retries_from_two_plans_keep_the_first_plan(monkeypatch):
    pid = flow.new_project()
    plan_a, first = _plan_a_partial(pid, monkeypatch)                     # A: ok, bad
    plan_b = _screen_and_plan(pid, monkeypatch, PLAN_B, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.render_outcome(pid, {'b-ok': OK, 'b-bad': BAD})                  # B: partial, its own outputs
    flow.retry_variant(pid, 'bad', 'v1')                                  # first: A's output
    flow.retry_variant(pid, 'b-bad', 'v2')                                # joins the open retry: B's output
    receipt = attempts.current(store.read(pid))
    assert receipt['plan_id'] == plan_a and receipt['plan_id'] != plan_b
    assert receipt['inherited']['recommendation_mode'] == 'local'


def test_409b_variant_retry_is_judged_on_the_round_it_redid(monkeypatch):
    """A partial -> re-run B partial -> 「重试这条」 on A's failed output succeeds: the retry is judged on A's outputs
    (owners = the retry + its source attempt A), so A is now complete; B's failure is not this round's."""
    pid = flow.new_project()
    _plan_a, first = _plan_a_partial(pid, monkeypatch)
    _screen_and_plan(pid, monkeypatch, PLAN_B, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.render_outcome(pid, {'b-ok': OK, 'b-bad': BAD})
    flow.retry_variant(pid, 'bad', 'v1')
    flow.render_outcome(pid, {'bad': OK})
    data, receipt = store.read(pid), flow.receipts(pid)[-1]
    assert (data['generation']['status'], receipt['state'], receipt['summary']['variant_count']) == ('completed', 'completed', 2)
    assert data['generation']['not_redone_failed_count'] == 1          # B's failed output, still listed
