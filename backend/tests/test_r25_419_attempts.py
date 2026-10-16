"""#419 rewrite acceptance (design-retro.md "Attempt 回执模型"): the backend owns attempts.

Invariants checked here: one retry command validates the parent and creates the attempt atomically; idempotency
key; serial retries (a second 「重试这条」 joins); sequence strictly increasing and persisted (restart keeps the
lineage); causes are a structured list; the primary cause is the catalog tier choice (product first) whatever the
goal order; settle_generation never writes 'multiple' (#265); history keeps the secondary fields (#267)."""
import json

import pytest

from backend.services.studio import attempts, jobs, store
from backend.tests import attempt_flow as flow


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    return flow.setup_env(tmp_path, monkeypatch)


def test_initial_automatic_run_opens_one_backend_attempt_bound_to_the_generation():
    pid = flow.new_project()
    run = flow.auto_import(pid)
    [receipt] = flow.receipts(pid)
    assert receipt['kind'] == 'generation' and receipt['state'] == 'open' and receipt['run_id'] == run
    assert receipt['sequence'] == 1 and receipt['retry_of'] is None and receipt['attempt_id'].startswith('t-')
    assert store.read(pid)['generation']['attempt_id'] == receipt['attempt_id']


def test_failed_attempt_settles_once_with_structured_causes():
    pid = flow.new_project(); flow.auto_import(pid)
    flow.screening_failed(pid, 'timeout')
    [receipt] = flow.receipts(pid)
    assert receipt['state'] == 'failed' and receipt['error_code'] == 'timeout'
    assert receipt['causes'] == [{'goal': None, 'stage': 'analyze', 'code': 'timeout', 'upstream': '', 'identity': ''}]
    finished = receipt['finished_at']
    store.change(pid, lambda data: data['generation'].update(status='completed'))  # a late rewrite never resettles it
    assert flow.receipts(pid)[0]['state'] == 'failed' and flow.receipts(pid)[0]['finished_at'] == finished


def test_retry_command_links_the_parent_and_is_idempotent():
    pid = flow.new_project(); flow.auto_import(pid); flow.screening_failed(pid)
    parent = flow.receipts(pid)[0]
    run = jobs.inspect_project(pid, flow.AUTO, retry={'key': 'click-1', 'parent_attempt_id': parent['attempt_id']})
    again = jobs.inspect_project(pid, flow.AUTO, retry={'key': 'click-1', 'parent_attempt_id': parent['attempt_id']})
    assert again == run  # same click re-sent: same receipt, nothing new
    first, second = flow.receipts(pid)
    assert len(flow.receipts(pid)) == 2
    assert second['retry_of'] == parent['attempt_id'] and second['flow_id'] == parent['flow_id']
    assert second['sequence'] == 2 and second['trigger'] == 'retry' and second['run_id'] == run


def test_retry_refused_while_one_is_open_and_for_a_bad_parent():
    pid = flow.new_project(); flow.auto_import(pid); flow.screening_failed(pid)
    parent = flow.receipts(pid)[0]
    jobs.inspect_project(pid, flow.AUTO, retry={'key': 'k1', 'parent_attempt_id': parent['attempt_id']})
    with pytest.raises(attempts.RetryRejected):  # serial: the open attempt has not settled
        jobs.inspect_project(pid, flow.AUTO, retry={'key': 'k2', 'parent_attempt_id': None})
    flow.screening_failed(pid)
    with pytest.raises(attempts.RetryRejected):  # an attempt that was already retried is not a parent again
        jobs.inspect_project(pid, flow.AUTO, retry={'key': 'k3', 'parent_attempt_id': parent['attempt_id']})
    with pytest.raises(attempts.RetryRejected):
        jobs.inspect_project(pid, flow.AUTO, retry={'key': 'k4', 'parent_attempt_id': 't-doesnotexist00'})
    assert len(flow.receipts(pid)) == 2


def test_completed_attempt_is_not_a_retry_parent():
    pid = flow.new_project(); flow.auto_import(pid)
    flow.render_outcome(pid, {'v1': ('completed', None, None)})
    done = flow.receipts(pid)[0]
    assert done['state'] == 'completed' and done['causes'] == []
    with pytest.raises(attempts.RetryRejected):
        jobs.inspect_project(pid, flow.AUTO, retry={'key': 'k1', 'parent_attempt_id': done['attempt_id']})
    jobs.inspect_project(pid, flow.AUTO, retry={'key': 'k2', 'parent_attempt_id': None})  # no failed parent: no retry_of
    assert flow.receipts(pid)[-1]['retry_of'] is None


def test_variant_retries_are_one_aggregate_attempt_serial_and_joined():
    pid = flow.new_project(); flow.auto_import(pid)
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad1': ('failed', 'timeout', None), 'bad2': ('failed', 'timeout', None)})
    partial = flow.receipts(pid)[0]
    assert partial['state'] == 'partial'
    a = flow.retry_variant(pid, 'bad1', 'c1')
    b = flow.retry_variant(pid, 'bad2', 'c2')  # second 「重试这条」 while the first is open: joins it
    again = flow.retry_variant(pid, 'bad1', 'c1')
    assert a['attempt']['attempt_id'] == b['attempt']['attempt_id'] == again['attempt']['attempt_id']
    assert a['attempt']['retry_of'] == partial['attempt_id'] and len(flow.receipts(pid)) == 2
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad1': ('completed', None, None), 'bad2': ('completed', None, None)})
    assert flow.receipts(pid)[1]['state'] == 'completed'


def test_restart_keeps_lineage_and_sequence_never_goes_back(monkeypatch):
    pid = flow.new_project(); flow.auto_import(pid); flow.screening_failed(pid)
    jobs.inspect_project(pid, flow.AUTO, retry={'key': 'k1'})
    before = json.loads(json.dumps(flow.receipts(pid)))
    monkeypatch.setattr(store, '_pending_links', {}); monkeypatch.setattr(store, '_read_failures', {})
    assert flow.receipts(pid) == before  # state is the file, not a process or browser cache
    # a rejected dispatch rolls the reservation back but keeps the sequence counter moving forward
    flow.screening_failed(pid)
    def reject(*_a, **_k):
        raise RuntimeError('pool closed')
    monkeypatch.setattr(jobs.executor, 'submit', reject)
    with pytest.raises(ValueError):
        jobs.inspect_project(pid, flow.AUTO, retry={'key': 'k2'})
    assert len(flow.receipts(pid)) == 2 and store.read(pid)['attempt_sequence'] == 3
    monkeypatch.undo()


@pytest.mark.parametrize('order', [('auth', 'timeout'), ('timeout', 'auth')])
def test_265_settle_generation_primary_is_the_tier_choice_never_multiple(order):
    pid = flow.new_project(); flow.auto_import(pid)
    spec = {'auth': ('failed', 'authentication', 'invalid_key'), 'timeout': ('failed', 'timeout', None)}
    flow.render_outcome(pid, {name: spec[name] for name in order})
    data = store.read(pid)
    assert data['generation']['error_code'] == 'timeout' and data['analysis']['error_code'] == 'timeout'
    assert 'multiple' not in json.dumps(data)
    receipt = flow.receipts(pid)[0]
    assert receipt['error_code'] == 'timeout'  # product first (PM rule) for the statistics
    assert [c['code'] for c in receipt['causes']] == ['timeout', 'authentication']
    assert receipt['secondary_error_codes'] == ['authentication'] and receipt['secondary_upstream_error_types'] == ['invalid_key']


def test_267_history_row_keeps_secondary_fields():
    pid = flow.new_project(); flow.auto_import(pid)
    flow.render_outcome(pid, {'a': ('failed', 'timeout', None), 'b': ('failed', 'authentication', 'invalid_key')})
    [row] = [r for r in store.read(pid)['analysis_history'] if r['analysis'].get('phase') == 'rendering']
    assert row['analysis']['secondary_error_codes'] == ['authentication']
    assert row['analysis']['secondary_upstream_error_types'] == ['invalid_key']


def test_receipts_carry_no_user_content():
    pid = flow.new_project(); flow.auto_import(pid)
    flow.render_outcome(pid, {'a': ('failed', 'timeout', None)})
    allowed = {'attempt_id', 'flow_id', 'sequence', 'retry_of', 'kind', 'trigger', 'state', 'run_id', 'causes', 'created_at',
               'finished_at', 'summary', 'error_code', 'failure_stage', 'upstream_error_type', 'secondary_error_codes',
               'secondary_upstream_error_types', 'secondary_failure_stages'}
    for receipt in flow.workspace(pid)['attempts']:
        assert set(receipt) <= allowed and 'idempotency_key' not in receipt


def test_a_run_killed_by_a_restart_settles_its_attempt_as_failed():
    pid = flow.new_project(); flow.auto_import(pid)
    path = store.directory(pid) / 'metadata' / 'studio.json'
    data = json.loads(path.read_text())
    data['analysis']['instance'] = 'previous-process'
    path.write_text(json.dumps(data))
    store.read(pid)  # the recovering read persists the terminal
    [receipt] = flow.receipts(pid)
    assert receipt['state'] == 'failed' and receipt['error_code'] == store.RESTART_CODE


def test_manual_retry_opens_the_production_attempt_and_confirmation_binds_it(monkeypatch):
    pid = flow.new_project()
    jobs.inspect_project(pid, flow.MANUAL)
    assert flow.receipts(pid) == []  # screening alone is not a v4 attempt
    run = flow.confirm(pid, flow.awaiting_confirmation(pid), monkeypatch)
    [first] = flow.receipts(pid)
    assert first['kind'] == 'production' and first['run_id'] == run and first['state'] == 'open'
    flow.production_finished(pid, 'failed', 'timeout')
    assert flow.receipts(pid)[0]['state'] == 'failed'
    jobs.inspect_project(pid, flow.MANUAL, retry={'key': 'm1'})
    pending = flow.receipts(pid)[1]
    assert pending['run_id'] is None and pending['retry_of'] == first['attempt_id']
    run2 = flow.confirm(pid, flow.awaiting_confirmation(pid), monkeypatch)
    bound = flow.receipts(pid)[1]
    assert len(flow.receipts(pid)) == 2 and bound['run_id'] == run2 and bound['retry_of'] == first['attempt_id']
    flow.production_finished(pid, 'completed')
    assert flow.receipts(pid)[1]['state'] == 'completed'


def test_manual_retry_whose_screening_failed_can_be_retried_again(monkeypatch):
    pid = flow.new_project()
    jobs.inspect_project(pid, flow.MANUAL)
    flow.confirm(pid, flow.awaiting_confirmation(pid), monkeypatch)
    flow.production_finished(pid, 'failed', 'timeout')
    first = flow.receipts(pid)[0]
    jobs.inspect_project(pid, flow.MANUAL, retry={'key': 'm1'})
    store.change(pid, lambda d: d.update(analysis={'status': 'failed', 'phase': 'screening', 'run_id': d['analysis']['run_id'], 'error_code': 'timeout'}))
    jobs.inspect_project(pid, flow.MANUAL, retry={'key': 'm2'})  # the unbound attempt never ran: replaced, not blocking
    states = [(r['state'], r['retry_of']) for r in flow.receipts(pid)]
    assert states == [('failed', None), ('abandoned', first['attempt_id']), ('open', first['attempt_id'])]
