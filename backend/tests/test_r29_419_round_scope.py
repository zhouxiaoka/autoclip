"""R29 #419: missing attempt record falls back to the whole workspace; on_demand-only scope; N and error
wording stay on this round. Real store.settle_generation. Appending platforms is out of 1.5.8."""
from backend.services.studio import attempts, store


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
