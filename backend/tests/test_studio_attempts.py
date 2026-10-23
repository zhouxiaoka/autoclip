"""Behavior tests for studio attempt receipts, retry, and round scope."""
import json

import pytest

from backend.services.studio import attempts, jobs, store
from backend.tests import attempt_flow as flow
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from backend.tests import attempt_flow as flow  # noqa: E402
from backend.tests.success_rate_sql import SQL, figure, run_sql  # noqa: E402

from backend.services.studio import jobs, store
from backend.services.studio.attempts import generation_summary

from backend.services.studio import attempts, jobs

from backend.tests import receipt_bridge
from backend.services.studio import attempts, store
"""#419 rewrite acceptance (design-retro.md "Attempt 回执模型"): the backend owns attempts.

Invariants checked here: one retry command validates the parent and creates the attempt atomically; idempotency
key; serial retries (a second 「重试这条」 joins); sequence strictly increasing and persisted (restart keeps the
lineage); causes are a structured list; the primary cause is the catalog tier choice (product first) whatever the
goal order; settle_generation never writes 'multiple' (#265); history keeps the secondary fields (#267)."""


@pytest.fixture
def env(tmp_path, monkeypatch):
    return flow.setup_env(tmp_path, monkeypatch)


@pytest.mark.usefixtures('env')
def test_initial_automatic_run_opens_one_backend_attempt_bound_to_the_generation():
    pid = flow.new_project()
    run = flow.auto_import(pid)
    [receipt] = flow.receipts(pid)
    assert receipt['kind'] == 'generation' and receipt['state'] == 'open' and receipt['run_id'] == run
    assert receipt['sequence'] == 1 and receipt['retry_of'] is None and receipt['attempt_id'].startswith('t-')
    assert store.read(pid)['generation']['attempt_id'] == receipt['attempt_id']


@pytest.mark.usefixtures('env')
def test_failed_attempt_settles_once_with_structured_causes():
    pid = flow.new_project(); flow.auto_import(pid)
    flow.screening_failed(pid, 'timeout')
    [receipt] = flow.receipts(pid)
    assert receipt['state'] == 'failed' and receipt['error_code'] == 'timeout'
    assert receipt['causes'] == [{'goal': None, 'stage': 'analyze', 'code': 'timeout', 'upstream': '', 'identity': ''}]
    finished = receipt['finished_at']
    store.change(pid, lambda data: data['generation'].update(status='completed'))  # a late rewrite never resettles it
    assert flow.receipts(pid)[0]['state'] == 'failed' and flow.receipts(pid)[0]['finished_at'] == finished


@pytest.mark.usefixtures('env')
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


@pytest.mark.usefixtures('env')
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


@pytest.mark.usefixtures('env')
def test_completed_attempt_is_not_a_retry_parent():
    pid = flow.new_project(); flow.auto_import(pid)
    flow.render_outcome(pid, {'v1': ('completed', None, None)})
    done = flow.receipts(pid)[0]
    assert done['state'] == 'completed' and done['causes'] == []
    with pytest.raises(attempts.RetryRejected):
        jobs.inspect_project(pid, flow.AUTO, retry={'key': 'k1', 'parent_attempt_id': done['attempt_id']})
    jobs.inspect_project(pid, flow.AUTO, retry={'key': 'k2', 'parent_attempt_id': None})  # no failed parent: no retry_of
    assert flow.receipts(pid)[-1]['retry_of'] is None


@pytest.mark.usefixtures('env')
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


@pytest.mark.usefixtures('env')
def test_restart_keeps_lineage_and_sequence_never_goes_back(monkeypatch):
    pid = flow.new_project(); flow.auto_import(pid); flow.screening_failed(pid)
    jobs.inspect_project(pid, flow.AUTO, retry={'key': 'k1'})
    before = json.loads(json.dumps(flow.receipts(pid)))
    monkeypatch.setattr(store, '_pending_links', {}); monkeypatch.setattr(store, '_read_failures', {})
    assert flow.receipts(pid) == before  # state is the file, not a process or browser cache
    # a rejected dispatch rolls the whole reservation back (state exactly as before): the receipt never existed for
    # any consumer (an open receipt emits nothing), so its number is not a gap in the sequence
    flow.screening_failed(pid)
    def reject(*_a, **_k):
        raise RuntimeError('pool closed')
    monkeypatch.setattr(jobs.executor, 'submit', reject)
    with pytest.raises(ValueError):
        jobs.inspect_project(pid, flow.AUTO, retry={'key': 'k2'})
    assert len(flow.receipts(pid)) == 2 and store.read(pid)['attempt_sequence'] == 2
    monkeypatch.undo()


@pytest.mark.parametrize('order', [('auth', 'timeout'), ('timeout', 'auth')])
@pytest.mark.usefixtures('env')
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


@pytest.mark.usefixtures('env')
def test_267_history_row_keeps_secondary_fields():
    pid = flow.new_project(); flow.auto_import(pid)
    flow.render_outcome(pid, {'a': ('failed', 'timeout', None), 'b': ('failed', 'authentication', 'invalid_key')})
    [row] = [r for r in store.read(pid)['analysis_history'] if r['analysis'].get('phase') == 'rendering']
    assert row['analysis']['secondary_error_codes'] == ['authentication']
    assert row['analysis']['secondary_upstream_error_types'] == ['invalid_key']


@pytest.mark.usefixtures('env')
def test_receipts_carry_no_user_content():
    pid = flow.new_project(); flow.auto_import(pid)
    flow.render_outcome(pid, {'a': ('failed', 'timeout', None)})
    allowed = {'attempt_id', 'flow_id', 'sequence', 'retry_of', 'kind', 'trigger', 'state', 'run_id', 'causes', 'created_at',
               'finished_at', 'summary', 'error_code', 'failure_stage', 'upstream_error_type', 'secondary_error_codes',
               'secondary_upstream_error_types', 'secondary_failure_stages'}
    for receipt in flow.workspace(pid)['attempts']:
        assert set(receipt) <= allowed and 'idempotency_key' not in receipt


def _kill_previous_process(pid):
    path = store.directory(pid) / 'metadata' / 'studio.json'
    data = json.loads(path.read_text())
    data['analysis']['instance'] = 'previous-process'
    path.write_text(json.dumps(data))


@pytest.mark.usefixtures('env')
def test_a_run_killed_by_a_restart_settles_its_attempt_as_failed():
    pid = flow.new_project(); flow.auto_import(pid)
    _kill_previous_process(pid)
    store.recover(pid)  # startup recovery persists the terminal; a plain read does not
    [receipt] = flow.receipts(pid)
    assert receipt['state'] == 'failed' and receipt['error_code'] == store.RESTART_CODE


@pytest.mark.usefixtures('env')
def test_a_new_import_settles_the_interrupted_attempt_before_opening_another():
    pid = flow.new_project(); flow.auto_import(pid)
    _kill_previous_process(pid)
    jobs.inspect_project(pid, flow.AUTO)
    first, last = flow.receipts(pid)[0], flow.receipts(pid)[-1]
    assert first['state'] == 'failed' and first['error_code'] == store.RESTART_CODE
    assert last['state'] == 'open' and last['attempt_id'] != first['attempt_id']


@pytest.mark.usefixtures('env')
def test_confirm_settles_the_interrupted_attempt_before_the_conflict():
    from backend.services.studio.models import ConfirmPlan
    pid = flow.new_project(); flow.auto_import(pid)
    _kill_previous_process(pid)
    with pytest.raises(store.ConflictError):
        jobs.confirm_project(pid, ConfirmPlan(plan_id='missing', goals=['content']))
    [receipt] = flow.receipts(pid)
    assert receipt['state'] == 'failed' and receipt['error_code'] == store.RESTART_CODE


@pytest.mark.usefixtures('env')
def test_editing_the_plan_settles_the_interrupted_attempt_before_refusing(monkeypatch):
    from fastapi import HTTPException
    from backend.api.v1 import studio as studio_api
    pid = flow.new_project(); flow.auto_import(pid)
    _kill_previous_process(pid)
    project = type('Project', (), {'project_metadata': {}, 'processing_config': {}})()
    monkeypatch.setattr(studio_api, 'project_or_404', lambda *_a, **_k: project)
    with pytest.raises(HTTPException) as raised:
        studio_api.correct_plan(pid, flow.AUTO, type('DB', (), {'commit': lambda self: None})())
    assert raised.value.status_code == 404
    [receipt] = flow.receipts(pid)
    assert receipt['state'] == 'failed' and receipt['error_code'] == store.RESTART_CODE


@pytest.mark.usefixtures('env')
def test_a_live_run_is_still_refused_and_its_attempt_stays_open():
    pid = flow.new_project(); flow.auto_import(pid)
    with pytest.raises(ValueError, match='当前任务正在运行'):
        jobs.inspect_project(pid, flow.AUTO)
    [receipt] = flow.receipts(pid)
    assert receipt['state'] == 'open'


@pytest.mark.usefixtures('env')
def test_editing_a_live_plan_is_still_refused(monkeypatch):
    from fastapi import HTTPException
    from backend.api.v1 import studio as studio_api
    pid = flow.new_project(); flow.auto_import(pid)
    project = type('Project', (), {'project_metadata': {}, 'processing_config': {}})()
    monkeypatch.setattr(studio_api, 'project_or_404', lambda *_a, **_k: project)
    with pytest.raises(HTTPException) as raised:
        studio_api.correct_plan(pid, flow.AUTO, type('DB', (), {'commit': lambda self: None})())
    assert raised.value.status_code == 409
    [receipt] = flow.receipts(pid)
    assert receipt['state'] == 'open'


@pytest.mark.usefixtures('env')
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


@pytest.mark.usefixtures('env')
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


@pytest.mark.usefixtures('env')
def test_settle_picks_the_tier_primary_even_from_an_unranked_record():
    receipt = {'attempt_id': 't-x0000000000', 'state': 'open'}
    record = {'status': 'failed', 'error_code': 'authentication', 'upstream_error_type': 'invalid_key', 'failure_stage': 'subtitle',
              'secondary_error_codes': ['timeout'], 'secondary_upstream_error_types': [''], 'secondary_failure_stages': ['analyze']}
    attempts.settle(receipt, 'failed', record)
    assert receipt['error_code'] == 'timeout' and receipt['failure_stage'] == 'analyze'
    assert [c['code'] for c in receipt['causes']] == ['timeout', 'authentication']
    assert receipt['secondary_upstream_error_types'] == ['invalid_key'] and receipt['secondary_failure_stages'] == ['subtitle']
"""acceptance, the real chain (design-retro: store -> history -> observer -> send -> official SQL).
The real backend (store + jobs, executor stubbed) produces the partial generation, the retry-command response and
the final state; the real frontend tracker/api/StudioResults button project them into events; the repo's
docs/analytics/success_rate.sql (DuckDB adapter) counts them. Replaces the flow test whose events came from
frontend-invented attempts."""

IN_CI = bool(os.environ.get('CI'))
if IN_CI:
    import duckdb  # noqa: F401
else:
    pytest.importorskip('duckdb')

ROOT = Path(__file__).resolve().parents[2]
WINDOW = {'date_from': "'2026-10-01 00:00:00'", 'date_to': "'2026-11-01 00:00:00'", 'internal_cohort_id': '641509',
          'release_1_5_7': "'2026-10-01 00:00:00'"}


@pytest.fixture
def env__r25_419_receipt_chain_duckdb(tmp_path, monkeypatch):
    flow.setup_env(tmp_path, monkeypatch)
    monkeypatch.setenv('AUTOCLIP_POSTHOG_KEY', 'phc_test')
    monkeypatch.setenv('AUTOCLIP_MODE', 'desktop')
    monkeypatch.setenv('AUTOCLIP_BUILD_ENVIRONMENT', 'production')
    posted = []

    def fake(req, timeout=0):
        posted.append(json.loads(req.data.decode()))
        raise OSError('tests do not send')

    monkeypatch.setattr('urllib.request.urlopen', fake)
    monkeypatch.setattr('backend.services.studio.terminal_outbox._RETRY_DELAYS', ())
    return posted


def _node(payload):
    node = shutil.which('node')
    if not node or not (ROOT / 'frontend' / 'node_modules').exists():
        if IN_CI:
            pytest.fail('node + frontend deps are installed in CI; refusing to skip the v4 chain test')
        pytest.skip('node + frontend deps required')
    out = subprocess.run([node, 'tests/helpers/receipt-flow.cjs'], cwd=ROOT / 'frontend', input=json.dumps(payload),
                         capture_output=True, text=True, timeout=120, check=True)
    return json.loads(out.stdout)


def _chain(posted, order=('ok', 'bad')):
    pid = flow.new_project()
    run = flow.auto_import(pid)
    spec = {'ok': ('completed', None, None), 'bad': ('failed', 'timeout', None)}
    flow.render_outcome(pid, {k: spec[k] for k in order})
    partial = flow.workspace(pid)
    response = flow.retry_variant(pid, 'bad', 'click-1')
    flow.render_outcome(pid, {k: ('completed', None, None) for k in order})
    from backend.services.studio.terminal_outbox import wait_until_idle
    assert wait_until_idle()
    result = _node({'pid': pid, 'import_run': run, 'partial': partial, 'retry_response': response,
                    'retry_variant': 'bad', 'final': flow.workspace(pid)})
    assert not [e for e in result['events'] if e['event'] in ('studio_generation_finished', 'studio_production_finished')]
    terminals = [{'event': body['event'], 'props': body['properties']} for body in posted
                 if body['event'] in ('studio_generation_finished', 'studio_production_finished')]
    result['events'] = [e for e in result['events'] if e['event'] not in ('studio_generation_finished', 'studio_production_finished')] + terminals
    return result, flow.receipts(pid)


def _rows(events):
    return [(f'u{i}', e['event'], 'person-1', datetime(2026, 10, 10, 10, i),
             {**e['props'], 'analytics_environment': 'production', 'runtime': 'desktop',
              'app_version': e['props'].get('app_version') or '1.5.7'}) for i, e in enumerate(events)]


@pytest.mark.usefixtures('env__r25_419_receipt_chain_duckdb')
def test_events_are_projections_of_backend_receipts(env__r25_419_receipt_chain_duckdb):
    result, receipts = _chain(env__r25_419_receipt_chain_duckdb)
    [post] = result['posts']
    assert post['url'] == '/studio/p1/retry' and post['body']['scope'] == 'variant'
    gen = [e['props'] for e in result['events'] if e['event'] == 'studio_generation_finished']
    assert [g['attempt_id'] for g in gen] == [r['attempt_id'] for r in receipts]  # one each, restart re-sent nothing
    assert gen[1]['retry_of'] == receipts[0]['attempt_id'] == gen[0]['attempt_id']
    assert [g['outcome'] for g in gen] == ['partial', 'success'] and gen[0]['error_code'] == 'timeout'


@pytest.mark.parametrize('fig', [1, 5])
@pytest.mark.parametrize('order', [('ok', 'bad'), ('bad', 'ok')])
@pytest.mark.usefixtures('env__r25_419_receipt_chain_duckdb')
def test_partial_then_retry_is_one_successful_flow_whatever_the_goal_order(fig, order, env__r25_419_receipt_chain_duckdb):
    result, _ = _chain(env__r25_419_receipt_chain_duckdb, order)
    [row] = run_sql(figure(fig, SQL, WINDOW), _rows(result['events']))
    assert row['q_all'] == 2 and row['ok'] == 1
    assert (row['flow_ok'], row['fq_all'], row['fq_prod']) == (1, 1, 1), row
    assert row['overall_flow_rate'] == 1.0 and row['product_flow_rate'] == 1.0


@pytest.mark.parametrize('fig', [1, 5])
@pytest.mark.usefixtures('env__r25_419_receipt_chain_duckdb')
def test_duplicate_deliveries_still_count_one_attempt_each(fig, env__r25_419_receipt_chain_duckdb):
    result, _ = _chain(env__r25_419_receipt_chain_duckdb)
    events = result['events'] + [json.loads(json.dumps(e)) for e in result['events'] if e['event'] == 'studio_generation_finished']
    [row] = run_sql(figure(fig, SQL, WINDOW), _rows(events))
    assert row['q_all'] == 2 and row['fq_all'] == 1


@pytest.mark.parametrize('fig', [1, 5])
@pytest.mark.usefixtures('env__r25_419_receipt_chain_duckdb')
def test_mutation_guard_without_the_receipt_retry_of_it_is_two_flows(fig, env__r25_419_receipt_chain_duckdb):
    result, _ = _chain(env__r25_419_receipt_chain_duckdb)
    for e in result['events']:
        e['props'].pop('retry_of', None)
        if e['event'] == 'studio_generation_finished':
            e['props']['flow_id'] = e['props']['attempt_id']
    [row] = run_sql(figure(fig, SQL, WINDOW), _rows(result['events']))
    assert row['fq_all'] == 2 and row['overall_flow_rate'] == 0.5


@pytest.mark.parametrize('fig', [1, 5])
@pytest.mark.usefixtures('env__r25_419_receipt_chain_duckdb')
def test_346_out_of_order_observation_is_still_one_successful_flow(fig, env__r25_419_receipt_chain_duckdb):
    """on the real chain: the retry's terminal is observed BEFORE the partial one (offline client); the
events carry the receipt sequence and success_rate.sql orders by it, so figures 1 and 5 stay at 100%."""
    result, receipts = _chain(env__r25_419_receipt_chain_duckdb)
    gen = [e for e in result['events'] if e['event'] == 'studio_generation_finished']
    assert [e['props']['attempt_sequence'] for e in gen] == [r['sequence'] for r in receipts] == [1, 2]
    reordered = [e for e in result['events'] if e not in gen] + list(reversed(gen))
    [row] = run_sql(figure(fig, SQL, WINDOW), _rows(reordered))
    assert (row['flow_ok'], row['fq_all']) == (1, 1), row
    assert row['unknown_flows'] == 0
    for e in reordered:  # without sequence AND without the retry_of link the last attempt is unprovable: unknown (#362)
        e['props'].pop('attempt_sequence', None)
        e['props'].pop('retry_of', None)
        e['props']['flow_id'] = gen[0]['props']['flow_id'] if e in gen else e['props'].get('flow_id')
    [row] = run_sql(figure(fig, SQL, WINDOW), _rows(reordered))
    assert (row['flow_ok'] or 0, row['fq_all'] or 0, row['unknown_flows']) == (0, 0, 1)
"""(replaces frontend/tests/auto-degrade-real-entry.test.cjs): degrade_reason freeze proven on the real chain.
The REAL backend writes the state (inspect_project -> _inspect -> settle_generation -> store.write -> receipt) and
GET /studio/{pid} snapshots are fed to the REAL frontend import entry + observer (helpers/auto-degrade-entry.cjs).
The observer first sees the terminal only after a re-screen replaced the plan (plan2, no reason): only a reason
frozen in the receipt can reach the event. Also #345/#347: flow_id and the counts come from the receipt."""

FRONTEND = Path(__file__).resolve().parents[2] / 'frontend'
REASONS = ['frame_extract_subtitle_fallback', 'source_too_long_subtitle_route']


@pytest.fixture
def env__r26_419_auto_degrade_real_entry(tmp_path, monkeypatch):
    if not shutil.which('node') or not (FRONTEND / 'node_modules' / 'typescript').is_dir():
        pytest.skip('frontend toolchain not installed')
    flow.setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'ensure_project_thumbnail', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'source', lambda pid: store.directory(pid) / 'input.mp4')


def _frontend(pid, run, snapshots):
    done = subprocess.run(['node', 'tests/helpers/auto-degrade-entry.cjs'], input=json.dumps({'project_id': pid, 'run_id': run, 'snapshots': snapshots}),
                          cwd=FRONTEND, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


@pytest.mark.parametrize('reason', REASONS)
@pytest.mark.usefixtures('env__r26_419_auto_degrade_real_entry')
def test_real_backend_receipt_carries_the_frozen_reason_through_the_real_entry(monkeypatch, reason):
    from backend.services.studio import planning
    plans = iter([{'mode': 'local', 'recommended_analysis': 'subtitle', 'confirmed_analysis': 'subtitle', 'preferences': {'goal': 'content'}, 'degrade_reason': reason},
                  {'mode': 'ai', 'recommended_analysis': 'visual', 'preferences': {'goal': 'content'}}])
    monkeypatch.setattr(planning, 'recommend', lambda *_a, **_k: next(plans))
    captured = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *a, **k: captured.append((fn, a)))
    posted = []

    def fake(req, timeout=0):
        posted.append(json.loads(req.data.decode()))
        raise OSError('tests do not send')

    monkeypatch.setattr('urllib.request.urlopen', fake)
    monkeypatch.setattr('backend.services.studio.terminal_outbox._RETRY_DELAYS', ())
    monkeypatch.setenv('AUTOCLIP_POSTHOG_KEY', 'phc_test')
    monkeypatch.setenv('AUTOCLIP_MODE', 'desktop')
    monkeypatch.setenv('AUTOCLIP_BUILD_ENVIRONMENT', 'production')
    pid = flow.new_project()
    run = flow.auto_import(pid)
    snapshots = [flow.workspace(pid)]
    fn, args = captured.pop(0)
    fn(*args)  # real _inspect: plan written, attempt bound to it, production starts (_auto_generate not run)
    captured.clear()
    snapshots.append(flow.workspace(pid))
    flow.render_outcome(pid, {'a': ('completed', None, None), 'b': ('completed', None, None)})
    receipt = flow.receipts(pid)[0]
    # re-screen before the observer saw the terminal: plan2 has no reason, a new manual screening replaces the plan
    jobs.inspect_project(pid, flow.MANUAL)
    fn, args = captured.pop(0)
    fn(*args)
    late = flow.workspace(pid)
    assert 'degrade_reason' not in late['plan'] and late['plan']['id'] != receipt.get('plan_id')
    late['output_variants'] = [late['output_variants'][0]]  # the live workspace moved on (one variant left)
    snapshots += [late, json.loads(json.dumps(late))]
    from backend.services.studio.terminal_outbox import wait_until_idle
    assert wait_until_idle()
    [finished] = [body for body in posted if body['event'] == 'studio_generation_finished']
    assert [body['event'] for body in posted if body['event'] == 'studio_generation_finished'] == ['studio_generation_finished']
    events = _frontend(pid, run, snapshots)
    assert [e for e in events if e['event'] == 'studio_generation_finished'] == []
    finished = {'props': finished['properties']}
    assert finished['props']['degrade_reason'] == reason
    assert finished['props']['flow_id'] == receipt['flow_id']  # #345: the backend flow, not the browser context
    assert finished['props']['completed_variant_count'] == 2 and finished['props']['variant_count'] == 2  # #347
    assert finished['props']['recommendation_mode'] == 'local' and finished['props']['route'] == 'subtitle'
"""the degrade_reason frozen in a receipt comes from that attempt's own plan. The automatic run goes
through the real _inspect (planning stubbed only at recommend) so the plan is bound where production writes it; a
retry whose screening fails before a new plan exists must not freeze the previous plan's reason."""


@pytest.fixture
def env__r26_419_degrade_owner(tmp_path, monkeypatch):
    flow.setup_env(tmp_path, monkeypatch)
    from backend.services.studio import planning
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'ensure_project_thumbnail', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'source', lambda pid: store.directory(pid) / 'input.mp4')
    monkeypatch.setattr(planning, 'recommend', lambda *_a, **_k: {'mode': 'local', 'recommended_analysis': 'subtitle', 'confirmed_analysis': 'subtitle',
                                                                 'preferences': {'goal': 'content'}, 'degrade_reason': 'frame_extract_subtitle_fallback'})


def _screen(pid, monkeypatch, **retry):
    captured = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *a, **k: captured.append((fn, a)))
    jobs.inspect_project(pid, flow.AUTO, **retry)
    return captured[0]


@pytest.mark.usefixtures('env__r26_419_degrade_owner')
def test_348_retry_failing_before_its_plan_does_not_freeze_the_previous_reason(monkeypatch):
    pid = flow.new_project()
    fn, args = _screen(pid, monkeypatch)
    fn(*args)  # real _inspect: writes plan and starts production (submit captured)
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('failed', 'timeout', None)})
    first = flow.receipts(pid)[0]
    assert first['state'] == 'partial' and first['degrade_reason'] == 'frame_extract_subtitle_fallback'
    _screen(pid, monkeypatch, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.screening_failed(pid, 'timeout')  # the retry fails before its own plan exists; the old plan is still stored
    assert store.read(pid)['plan']['degrade_reason'] == 'frame_extract_subtitle_fallback'
    second = flow.receipts(pid)[1]
    assert second['state'] == 'failed' and 'degrade_reason' not in second


@pytest.mark.usefixtures('env__r26_419_degrade_owner')
def test_m2_only_catalog_enum_reasons_are_frozen():
    from backend.services.studio import attempts
    receipt = {'attempt_id': 't-x0000000000', 'state': 'open', 'plan_id': 'p'}
    attempts.settle(receipt, 'completed', {'status': 'completed'}, plan={'id': 'p', 'degrade_reason': 'free text /Users/x'})
    assert 'degrade_reason' not in receipt


@pytest.mark.usefixtures('env__r26_419_degrade_owner')
def test_363_screening_failure_before_its_plan_does_not_freeze_the_previous_outputs(monkeypatch):
    pid = flow.new_project()
    fn, args = _screen(pid, monkeypatch)
    fn(*args)
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('failed', 'timeout', None)})
    first = flow.receipts(pid)[0]
    assert first['summary']['variant_count'] == 2 and first['summary']['completed_variant_count'] == 1
    _screen(pid, monkeypatch, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.screening_failed(pid, 'timeout')  # the previous run's two outputs are still in the workspace
    second = flow.receipts(pid)[1]
    for key in ('variant_count', 'completed_variant_count', 'failed_variant_count'):
        assert key not in second['summary'], key
    assert second['summary']['platform_count'] == 2  # request fields stay


@pytest.mark.usefixtures('env__r26_419_degrade_owner')
def test_364_variant_retry_keeps_the_source_plans_degrade_reason(monkeypatch):
    pid = flow.new_project()
    fn, args = _screen(pid, monkeypatch)
    fn(*args)
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('failed', 'timeout', None)})
    flow.retry_variant(pid, 'bad', 'v1')
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('completed', None, None)})
    retried = flow.receipts(pid)[1]
    assert retried['state'] == 'completed' and retried['degrade_reason'] == 'frame_extract_subtitle_fallback'
    assert retried['summary']['recommendation_mode'] == 'local'


@pytest.mark.usefixtures('env__r26_419_degrade_owner')
def test_364_variant_retry_after_a_rescreen_still_reports_the_source_plan(monkeypatch):
    pid = flow.new_project()
    fn, args = _screen(pid, monkeypatch)
    fn(*args)
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('failed', 'timeout', None)})
    flow.store.change(pid, lambda d: d.update(plan={'id': 'plan-other', 'mode': 'ai'}))  # the workspace plan moved on
    flow.retry_variant(pid, 'bad', 'v1')
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('completed', None, None)})
    retried = flow.receipts(pid)[1]
    assert retried['degrade_reason'] == 'frame_extract_subtitle_fallback' and retried['summary']['recommendation_mode'] == 'local'


@pytest.mark.usefixtures('env__r26_419_degrade_owner')
def test_365_manual_confirm_binds_the_confirmed_plan_without_test_prebinding(monkeypatch):
    pid = flow.new_project()
    jobs.inspect_project(pid, flow.MANUAL)
    plan_id = flow.awaiting_confirmation(pid)
    store.change(pid, lambda d: d['plan'].update(degrade_reason='source_too_long_subtitle_route', mode='local'))
    flow.confirm(pid, plan_id, monkeypatch)  # the real confirm_project; nothing bound by the test
    flow.production_finished(pid, 'completed')
    [receipt] = flow.receipts(pid)
    assert receipt['state'] == 'completed' and receipt['degrade_reason'] == 'source_too_long_subtitle_route'
"""the generation summary rules live only in backend attempts.generation_summary (frozen into the
receipt). These are the cases frontend/tests used to assert on the deleted workflow.generationSummary copy."""

SNAPSHOT = {
    'generation': {'auto_start': True, 'status': 'partial', 'requested_platforms': ['douyin', 'tiktok'], 'skipped': [{'strategy_id': 'youtube_long', 'reason': 'x'}],
                   'source_has_burned_subtitles': False, 'created_at': '2026-09-30T10:00:00Z', 'finished_at': '2026-09-30T10:04:00Z'},
    'output_variants': [
        {'draft_id': 'a', 'strategy_id': 'douyin', 'status': 'completed', 'framing': 'speaker'},
        {'draft_id': 'b', 'strategy_id': 'tiktok', 'status': 'failed', 'framing': 'full_frame', 'trimmed_to_sec': 180},
        {'draft_id': 'c', 'strategy_id': 'douyin', 'status': 'on_demand'},
    ],
    'drafts': [{'id': 'a', 'title': 'Private title', 'packaging': {'template': 'interview_zh', 'fallback': False}},
               {'id': 'b', 'packaging': {'template': 'podcast_en', 'fallback': True}}],
}


def test_counts_templates_framing_and_fallbacks_without_content():
    assert generation_summary(SNAPSHOT) == {
        'variant_count': 3, 'completed_variant_count': 1, 'failed_variant_count': 1, 'on_demand_variant_count': 1, 'skipped_variant_count': 1,
        'platform_count': 2, 'interview_count': 1, 'podcast_count': 1, 'landscape_count': 0, 'editorial_count': 0, 'street_count': 0,
        'news_count': 0, 'cinema_count': 0,
        'classic_count': 2, 'html_downgrade_count': 0, 'speaker_framed_count': 1, 'full_frame_count': 1, 'framing_pending_count': 0,
        'framing_captions_count': 0, 'outro_applied_count': 0, 'outro_fallback_count': 0, 'outro_unknown_count': 1,
        'packaging_fallback_count': 1, 'trimmed_count': 1, 'burned_captions': False, 'duration_ms': 240000}
    assert 'Private' not in str(generation_summary(SNAPSHOT))


def test_outro_metrics_separate_result_disabled_fallback_and_missing_evidence():
    state = {'generation': {'portrait_style': 'podcast', 'branding': {'outro_enabled': True}}, 'output_variants': [
        *({'id': i, 'draft_id': i, 'render_job_id': i, 'strategy_id': 'douyin', 'status': 'completed', 'branding': {'outro_enabled': True}} for i in ('applied', 'fallback', 'disabled', 'unknown')),
        {'id': 'failed', 'draft_id': 'failed', 'render_job_id': 'failed', 'strategy_id': 'douyin', 'status': 'failed'}],
        'jobs': [{'job_id': 'applied', 'status': 'completed', 'brand_outro': True, 'result': {'outro_applied': True}},
                 {'job_id': 'fallback', 'status': 'completed', 'brand_outro': True, 'result': {'outro_applied': False, 'warnings': ['private error']}},
                 {'job_id': 'disabled', 'status': 'completed', 'brand_outro': False, 'result': {'outro_applied': False}},
                 {'job_id': 'failed', 'status': 'failed', 'brand_outro': True, 'result': {'outro_applied': False}}]}
    s = generation_summary(state)
    assert (s['portrait_style'], s['outro_applied_count'], s['outro_fallback_count'], s['outro_unknown_count']) == ('podcast', 1, 1, 1)
    assert 'private' not in str(s)


def test_a_rank_skip_is_classic_and_not_a_downgrade():
    s = generation_summary({'output_variants': [
        {'draft_id': 'a', 'render_job_id': 'j1', 'strategy_id': 'douyin', 'status': 'completed'},
        {'draft_id': 'b', 'render_job_id': 'j2', 'strategy_id': 'douyin', 'status': 'completed'}], 'jobs': [
        {'job_id': 'j1', 'status': 'completed', 'result': {'template_render': {'template': 'classic', 'requested_template': 'editorial', 'downgraded': False, 'downgrade_reason': 'rank', 'outcome': 'skipped'}}},
        {'job_id': 'j2', 'status': 'completed', 'result': {'template_render': {'template': 'classic', 'requested_template': 'editorial', 'downgraded': True, 'downgrade_reason': 'over_budget', 'outcome': 'downgraded'}}}],
        'drafts': []})
    assert (s['html_downgrade_count'], s['classic_count'], s['editorial_count'], s['news_count'], s['cinema_count']) == (1, 2, 0, 0, 0)


def test_news_and_cinema_renders_are_counted_unless_downgraded():
    s = generation_summary({'output_variants': [
        {'draft_id': 'n', 'render_job_id': 'jn', 'strategy_id': 'douyin', 'status': 'completed'},
        {'draft_id': 'c', 'render_job_id': 'jc', 'strategy_id': 'douyin', 'status': 'completed'},
        {'draft_id': 'd', 'render_job_id': 'jd', 'strategy_id': 'douyin', 'status': 'completed'}], 'jobs': [
        {'job_id': 'jn', 'status': 'completed', 'result': {'template_render': {'template': 'news', 'downgraded': False}}},
        {'job_id': 'jc', 'status': 'completed', 'result': {'template_render': {'template': 'cinema', 'downgraded': False}}},
        {'job_id': 'jd', 'status': 'completed', 'result': {'template_render': {'template': 'news', 'downgraded': True}}}],
        'drafts': []})
    assert (s['news_count'], s['cinema_count'], s['html_downgrade_count'], s['classic_count']) == (1, 1, 1, 1)


def test_recommendation_fields_are_kept():
    s = generation_summary({'generation': {'recommended_template': 'editorial', 'accepted_recommendation': False}, 'output_variants': [], 'jobs': [], 'drafts': []})
    assert s['recommended_template'] == 'editorial' and s['accepted_recommendation'] is False
"""a second 「重试这条」 joining the open variant-retry attempt goes through the same parent check and
idempotency registration as the first request."""


def _partial(pid):
    flow.auto_import(pid)
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad1': ('failed', 'timeout', None), 'bad2': ('failed', 'timeout', None)})
    return flow.receipts(pid)[0]


@pytest.mark.usefixtures('env')
def test_343_joined_request_replayed_after_failure_creates_no_new_attempt(env):
    pid = flow.new_project(); _partial(pid)
    flow.retry_variant(pid, 'bad1', 'c1')
    flow.retry_variant(pid, 'bad2', 'c2')  # joins
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad1': ('failed', 'timeout', None), 'bad2': ('failed', 'timeout', None)})
    dispatched = env.count('_dispatch_pending_variants')
    replay = flow.retry_variant(pid, 'bad2', 'c2')  # the joined click re-sent (network retry) after the attempt failed
    assert len(flow.receipts(pid)) == 2 and replay['attempt']['attempt_id'] == flow.receipts(pid)[1]['attempt_id']
    assert env.count('_dispatch_pending_variants') == dispatched  # not dispatched again


@pytest.mark.usefixtures('env')
def test_344_join_with_unknown_parent_is_rejected():
    pid = flow.new_project(); _partial(pid)
    flow.retry_variant(pid, 'bad1', 'c1')
    with pytest.raises(attempts.RetryRejected):
        jobs.retry_variant(pid, 'bad2', {'key': 'c2', 'parent_attempt_id': 't-doesnotexist00'})
    assert attempts.by_key(flow.store.read(pid), 'c2') is None


@pytest.mark.usefixtures('env')
def test_344_join_naming_another_parent_is_rejected_but_the_right_one_joins():
    pid = flow.new_project(); parent = _partial(pid)
    first = flow.retry_variant(pid, 'bad1', 'c1')['attempt']
    with pytest.raises(attempts.RetryRejected):  # the open attempt itself is not a retryable parent
        jobs.retry_variant(pid, 'bad2', {'key': 'c2', 'parent_attempt_id': first['attempt_id']})
    jobs.retry_variant(pid, 'bad2', {'key': 'c3', 'parent_attempt_id': parent['attempt_id']})
    assert len(flow.receipts(pid)) == 2


@pytest.mark.usefixtures('env')
def test_joined_key_is_not_in_the_public_receipt():
    pid = flow.new_project(); _partial(pid)
    flow.retry_variant(pid, 'bad1', 'c1'); flow.retry_variant(pid, 'bad2', 'c2')
    assert all('joined_keys' not in r for r in flow.workspace(pid)['attempts'])
"""(P1): the manual production path through the REAL entry (confirm_project -> _produce_selected), with
no run_id / phase pre-filled by the test. The worker's terminal write carries neither (store.write inherits them
from the running record), so the receipt must settle after that identity and the run telemetry are filled in:
it reaches its terminal, a retry is accepted, and the frozen receipt carries the last call's telemetry."""


@pytest.fixture
def env__r26_419_real_entry(tmp_path, monkeypatch):
    flow.setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *a, **k: None)
    from backend.core import llm_telemetry
    monkeypatch.setattr(llm_telemetry, 'run_snapshot', lambda _pid=None: {'provider': 'deepseek', 'llm_calls': 3, 'retry_count': 1})


def _produce(pid, monkeypatch, outcome):
    """confirm_project submits _produce_selected; run it exactly as the executor would."""
    captured = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *a, **k: captured.append((fn, a)))
    run = flow.confirm(pid, flow.awaiting_confirmation(pid), monkeypatch)
    [(fn, args)] = captured
    def content(_pid, _video):
        if outcome == 'failed':
            raise TimeoutError('upstream timed out')
        return [{'id': 'c1'}]
    monkeypatch.setattr(jobs, 'run_content', content)
    fn(*args)
    return run


@pytest.mark.parametrize('outcome', ['failed', 'completed'])
@pytest.mark.usefixtures('env__r26_419_real_entry')
def test_342_real_manual_production_settles_the_receipt(monkeypatch, outcome):
    pid = flow.new_project()
    jobs.inspect_project(pid, flow.MANUAL)
    run = _produce(pid, monkeypatch, outcome)
    assert store.read(pid)['analysis']['run_id'] == run  # inherited by store.write, not written by the worker
    [receipt] = flow.receipts(pid)
    assert receipt['state'] == outcome and receipt['run_id'] == run
    # Usage numbers freeze on the receipt. An unpaired provider is not an identity (#415).
    assert receipt['summary'].get('llm_calls') == 3 and receipt['summary'].get('retry_count') == 1
    assert receipt['summary'].get('provider') is None


@pytest.mark.usefixtures('env__r26_419_real_entry')
def test_342_real_manual_failure_can_be_retried(monkeypatch):
    pid = flow.new_project()
    jobs.inspect_project(pid, flow.MANUAL)
    _produce(pid, monkeypatch, 'failed')
    first = flow.receipts(pid)[0]
    jobs.inspect_project(pid, flow.MANUAL, retry={'key': 'm1', 'parent_attempt_id': first['attempt_id']})
    assert flow.receipts(pid)[1]['retry_of'] == first['attempt_id']
"""(design: output ownership is stored, not inferred). Every output variant records the attempt
that produced it (produced_by_attempt) and that attempt's plan (produced_by_plan) when it is created. A receipt's
summary counts only outputs owned by this attempt (or, for a variant retry, by the attempt whose outputs it
re-renders); a variant retry takes its plan from the retried variant itself, never from "the latest failure".
Real _inspect / retry_variant / store.write; only planning.recommend and the executor are stubbed."""

PLAN_A = {'mode': 'local', 'recommended_analysis': 'subtitle', 'confirmed_analysis': 'subtitle',
          'preferences': {'goal': 'content'}, 'degrade_reason': 'frame_extract_subtitle_fallback'}
PLAN_B = {'mode': 'ai', 'recommended_analysis': 'visual', 'confirmed_analysis': 'visual', 'preferences': {'goal': 'content'}}
COUNTS = ('variant_count', 'completed_variant_count', 'failed_variant_count')


@pytest.fixture
def env__r27_419_output_owner(tmp_path, monkeypatch):
    flow.setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'ensure_project_thumbnail', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'source', lambda pid: store.directory(pid) / 'input.mp4')


def _screen_and_plan(pid, monkeypatch, plan, **retry):
    """Real inspect_project + real _inspect: the plan is written and bound where production starts."""
    from backend.services.studio import planning
    monkeypatch.setattr(planning, 'recommend', lambda *_a, **_k: dict(plan))
    captured = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *a, **k: captured.append((fn, a)))
    jobs.inspect_project(pid, flow.AUTO, **retry)
    fn, args = captured[0]
    fn(*args)  # writes the plan, binds it, submits _auto_generate (captured, not run)
    return store.read(pid)['plan']['id']


def _plan_a_partial(pid, monkeypatch):
    plan_a = _screen_and_plan(pid, monkeypatch, PLAN_A)
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('failed', 'timeout', None)})
    first = flow.receipts(pid)[0]
    assert first['state'] == 'partial' and first['summary']['variant_count'] == 2
    return plan_a, first


@pytest.mark.usefixtures('env__r27_419_output_owner')
def test_376_outputs_carry_the_attempt_and_plan_that_produced_them(monkeypatch):
    pid = flow.new_project()
    plan_a, first = _plan_a_partial(pid, monkeypatch)
    for variant in store.read(pid)['output_variants']:
        assert (variant['produced_by_attempt'], variant['produced_by_plan']) == (first['attempt_id'], plan_a)


@pytest.mark.usefixtures('env__r27_419_output_owner')
def test_376_new_plan_failing_before_its_outputs_does_not_freeze_the_previous_outputs(monkeypatch):
    """/sol/astra: a re-screen builds and binds a new plan, then fails in production before any output the receipt used to freeze the previous run's variant=2/completed=1/failed=1 because it had a plan_id."""
    pid = flow.new_project()
    _plan_a, first = _plan_a_partial(pid, monkeypatch)
    plan_b = _screen_and_plan(pid, monkeypatch, PLAN_B, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.production_failed_before_outputs(pid)
    second = flow.receipts(pid)[1]
    assert second['plan_id'] == plan_b and second['state'] == 'failed'   # it HAD its own plan
    assert len(store.read(pid)['output_variants']) == 2                  # plan A's outputs are still in the workspace
    for key in COUNTS:
        assert key not in second['summary'], key
    assert second['summary']['platform_count'] == 2                       # request fields stay


def _rescreen_fails_then_retry_a_variant(pid, monkeypatch):
    """Degraded plan A partially completes -> whole-flow retry (plan B) fails -> 「重试这条」 on A's failed output."""
    plan_a, first = _plan_a_partial(pid, monkeypatch)
    _screen_and_plan(pid, monkeypatch, PLAN_B, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.production_failed_before_outputs(pid)
    flow.retry_variant(pid, 'bad', 'v1')
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('completed', None, None)})
    return plan_a, first, flow.receipts(pid)[2]


@pytest.mark.usefixtures('env__r27_419_output_owner')
def test_377_variant_retry_after_a_failed_rescreen_belongs_to_the_plan_that_produced_the_output(monkeypatch):
    pid = flow.new_project()
    plan_a, first, retried = _rescreen_fails_then_retry_a_variant(pid, monkeypatch)
    assert retried['trigger'] == 'variant_retry' and retried['state'] == 'completed'
    assert retried['plan_id'] == plan_a                     # not plan B, not dropped (m3 drops it)
    assert retried['degrade_reason'] == 'frame_extract_subtitle_fallback'
    assert (retried['summary']['recommendation_mode'], retried['summary']['analysis_mode']) == ('local', 'subtitle')


@pytest.mark.usefixtures('env__r27_419_output_owner')
def test_377_variant_retry_counts_the_retried_outputs(monkeypatch):
    pid = flow.new_project()
    _plan_a, _first, retried = _rescreen_fails_then_retry_a_variant(pid, monkeypatch)
    assert (retried['summary']['variant_count'], retried['summary']['completed_variant_count'],
            retried['summary']['failed_variant_count']) == (1, 1, 0)   # only 'bad' (redone); was (2, 2, 0)


@pytest.mark.usefixtures('env__r27_419_output_owner')
def test_377_variant_retry_counts_do_not_depend_on_the_plan_id(monkeypatch):
    """The direct variant retry (no re-screen in between): its output counts come from output ownership, so the
plan id is asserted on its own (the m3 mutation inherit without plan_id survived every test)."""
    pid = flow.new_project()
    plan_a, first = _plan_a_partial(pid, monkeypatch)
    flow.retry_variant(pid, 'bad', 'v1')
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('completed', None, None)})
    retried = flow.receipts(pid)[1]
    assert retried['plan_id'] == plan_a and retried['retry_of'] == first['attempt_id']
    assert (retried['summary']['variant_count'], retried['summary']['completed_variant_count']) == (1, 1)   # ; was (2, 2)


@pytest.mark.usefixtures('env__r27_419_output_owner')
def test_376_real_auto_generate_stamps_the_outputs_it_creates(monkeypatch):
    """The production write itself (jobs._auto_generate persist) stamps each new output with the open attempt and
    its bound plan - not a test helper."""
    from backend.tests.test_on_demand_variants import _auto_fixture, _base
    state, _exports = _auto_fixture(monkeypatch, [_base(n, 1) for n in range(3)], ['douyin'])
    state['attempts'] = [{'attempt_id': 't-gen', 'kind': 'generation', 'state': 'open', 'sequence': 1, 'plan_id': 'plan-a'},
                         {'attempt_id': 't-old', 'kind': 'generation', 'state': 'partial', 'sequence': 0, 'plan_id': 'plan-0'}]
    state['generation']['attempt_id'] = 't-gen'
    jobs._auto_generate('p1', {'id': 'plan-a'})
    assert state['output_variants']
    assert {(v['produced_by_attempt'], v.get('produced_by_plan')) for v in state['output_variants']} == {('t-gen', 'plan-a')}


@pytest.mark.usefixtures('env__r27_419_output_owner')
def test_376_a_rerun_counts_only_its_own_outputs_next_to_the_previous_ones(monkeypatch):
    pid = flow.new_project()
    _plan_a, first = _plan_a_partial(pid, monkeypatch)
    _screen_and_plan(pid, monkeypatch, PLAN_B, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.render_outcome(pid, {'new': ('completed', None, None)})
    assert len(store.read(pid)['output_variants']) == 3              # plan A's two outputs are still there
    second = flow.receipts(pid)[1]
    # counts only: the generation outcome itself is still judged over the workspace by store.settle_generation
    # (plan A's failed output makes this 'partial') reported to as a separate finding, not changed here.
    assert (second['summary']['variant_count'], second['summary']['completed_variant_count'],
            second['summary']['failed_variant_count']) == (1, 1, 0)
"""the test bridge (receipt_bridge.py) must not manufacture a premise the real entry never has. The real
entry binds the plan only when screening hands over to production (jobs._inspect.start_automatic) and stamps outputs
only when production creates them, so a snapshot that failed in screening carries neither the stored plan's
mode/route/degrade_reason nor the workspace's output counts whatever plan and outputs are lying around."""

PLAN = {'id': 'p-old', 'mode': 'ai', 'recommended_analysis': 'visual', 'confirmed_analysis': 'visual',
        'degrade_reason': 'vision_unavailable_subtitle_fallback'}
OUTPUTS = [{'id': 'v1', 'draft_id': 'd1', 'strategy_id': 'douyin', 'status': 'completed'},
           {'id': 'v2', 'draft_id': 'd2', 'strategy_id': 'douyin', 'status': 'failed'}]


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"crash_reports":false}')
    from backend.services.studio import attempts, store
    monkeypatch.setattr(store, '_read_failures', {})
    monkeypatch.setattr(store, '_pending_links', {})
    monkeypatch.setattr(store, '_io_failures', {})
    def run(snapshot):
        out = receipt_bridge.materialize({'kind': 'generation', 'run_id': 'r1', 'seed': 's', 'snapshot': snapshot}, attempts, store)
        return next(a for a in out['attempts'] if a['attempt_id'] == out['attempt_id'])
    return run


def test_378_screening_failure_snapshot_gets_no_plan_or_outputs_from_the_bridge(bridge):
    receipt = bridge({'plan': PLAN, 'output_variants': OUTPUTS, 'drafts': [],
                      'generation': {'status': 'failed', 'error_code': 'provider_error', 'failure_stage': 'screening'},
                      'analysis': {'status': 'failed', 'phase': 'screening', 'error_code': 'provider_error'}})
    assert receipt['state'] == 'failed'
    for key in ('recommendation_mode', 'analysis_mode', 'route', 'variant_count', 'completed_variant_count'):
        assert key not in receipt['summary'], key
    assert 'degrade_reason' not in receipt


def test_378_production_snapshot_is_bound_and_owns_its_outputs_like_the_real_entry(bridge):
    receipt = bridge({'plan': PLAN, 'output_variants': OUTPUTS, 'drafts': [],
                      'generation': {'status': 'partial'}, 'analysis': {'status': 'completed', 'phase': 'production'}})
    assert receipt['state'] == 'partial' and receipt['degrade_reason'] == PLAN['degrade_reason']
    assert (receipt['summary']['recommendation_mode'], receipt['summary']['variant_count'], receipt['summary']['completed_variant_count']) == ('ai', 2, 1)
"""missing attempt record falls back to the whole workspace; on_demand-only scope; N and error
wording stay on this round. Real store.settle_generation. Appending platforms is out of 1.5.7."""


def _data(attempt_id, variants, records=()):
    return {'generation': {'status': 'rendering', 'attempt_id': attempt_id}, 'jobs': [], 'output_variants': variants,
            'attempts': [dict(r) for r in records]}


# only attempt_id is left, the record is gone -> whole workspace

def test_i440_missing_record_with_stamps_left_is_judged_on_the_whole_workspace():
    data = _data('t-gone', [{'id': 'a', 'status': 'completed', 'produced_by_attempt': 't-gone'},
                            {'id': 'b', 'status': 'failed', 'error_code': 'timeout', 'produced_by_attempt': 't-old'}])
    assert attempts.round_outputs(data) is None   # owners_of removed (scope = this attempt's stamps only)
    store.settle_generation(data)
    assert (data['generation']['status'], data['generation']['error_code']) == ('partial', 'timeout')   # not 'completed'


def test_i440_missing_record_with_only_on_demand_stamped_is_not_a_validation_failure():
    data = _data('t-gone', [{'id': 'a', 'status': 'on_demand', 'produced_by_attempt': 't-gone'},
                            {'id': 'b', 'status': 'completed'}])
    store.settle_generation(data)
    assert data['generation']['status'] == 'completed' and data['generation'].get('error_code') != 'validation'


# a recorded round whose stamped outputs are all on_demand -> validation (unchanged behaviour)

def test_i442_recorded_round_with_only_on_demand_outputs_is_validation():
    data = _data('t-1', [{'id': 'a', 'status': 'on_demand', 'produced_by_attempt': 't-1'},
                         {'id': 'old', 'status': 'completed', 'produced_by_attempt': 't-0'}],
                 records=[{'attempt_id': 't-1', 'kind': 'generation', 'state': 'open', 'sequence': 2}])
    store.settle_generation(data)
    assert (data['generation']['status'], data['generation']['error_code']) == ('failed', 'validation')
    assert data['generation']['error'] == '没有自动生成的成片，可选择备选片段继续生成'


# N counts only failed outputs outside the round; the error text comes from the round only

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
"""One scope rule (attempts.round_outputs) judges a generation round: store.settle_generation's
status / counts / error code / wording / 'all done' gate and the receipt summary. Real inspect_project, _inspect,
retry_variant, store.write; only planning.recommend and the executor are stubbed."""

OK, BAD = ('completed', None, None), ('failed', 'timeout', None)


def _rerun(pid, monkeypatch, first, outcome):
    _screen_and_plan(pid, monkeypatch, PLAN_B, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.render_outcome(pid, outcome)
    return store.read(pid), flow.receipts(pid)[-1]


@pytest.mark.usefixtures('env__r27_419_output_owner')
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


@pytest.mark.usefixtures('env__r27_419_output_owner')
def test_409a_a_rerun_with_its_own_failure_is_partial(monkeypatch):
    pid = flow.new_project()
    _plan_a, first = _plan_a_partial(pid, monkeypatch)
    data, receipt = _rerun(pid, monkeypatch, first, {'new': OK, 'new2': ('failed', 'service_restarted', None)})
    g = data['generation']
    assert (g['status'], g['error_code'], receipt['state'], receipt['error_code']) == ('partial', 'service_restarted', 'partial', 'service_restarted')
    assert 'secondary_error_codes' not in g and g['not_redone_failed_count'] == 1                               # A's timeout is not a secondary cause


@pytest.mark.usefixtures('env__r27_419_output_owner')
def test_409b_retrying_one_of_two_failures_is_judged_on_the_redone_one(monkeypatch):
    pid = flow.new_project()
    _screen_and_plan(pid, monkeypatch, PLAN_A)
    flow.render_outcome(pid, {'b1': BAD, 'b2': BAD})
    assert flow.receipts(pid)[0]['state'] == 'failed'
    flow.retry_variant(pid, 'b1', 'v1')
    flow.render_outcome(pid, {'b1': OK})
    data, receipt = store.read(pid), flow.receipts(pid)[1]
    # (10:42): a 「重试这条」 round is judged only on what it redid (redone_by_attempt) b2 belongs to
    # the earlier round. Was: ('partial', 'timeout', 'partial') with b2 in scope and N == 0.
    assert (data['generation']['status'], data['generation'].get('error_code'), receipt['state']) == ('completed', None, 'completed')
    assert data['generation']['not_redone_failed_count'] == 1             # b2: an earlier round's failure, not redone


def _legacy(data):
    for v in data['output_variants']:
        v.pop('produced_by_attempt', None)
        v.pop('produced_by_plan', None)


@pytest.mark.usefixtures('env__r27_419_output_owner')
def test_409c_unstamped_old_project_settles_as_before():
    old = {'generation': {'status': 'rendering'}, 'jobs': [], 'output_variants': [
        {'id': 'a', 'status': 'completed'}, {'id': 'b', 'status': 'failed', 'error_code': 'timeout'}, {'id': 'c', 'status': 'on_demand'}]}
    for generation_attempt in (None, 't-missing'):                       # no attempt record / attempt with no stamps
        data = {**old, 'generation': {'status': 'rendering', **({'attempt_id': generation_attempt} if generation_attempt else {})},
                'output_variants': [dict(v) for v in old['output_variants']]}
        store.settle_generation(data)
        assert (data['generation']['status'], data['generation']['completed_variant_count'], data['generation']['error_code']) == ('partial', 1, 'timeout')


@pytest.mark.usefixtures('env__r27_419_output_owner')
def test_409d_variant_retry_of_an_unstamped_output_is_never_a_validation_failure(monkeypatch):
    pid = flow.new_project()
    _plan_a_partial(pid, monkeypatch)
    store.change(pid, _legacy)                                            # outputs from before the change
    flow.retry_variant(pid, 'bad', 'v1')
    flow.render_outcome(pid, {'bad': OK})
    data, receipt = store.read(pid), flow.receipts(pid)[1]
    assert data['generation']['status'] == 'completed' and data['generation'].get('error_code') != 'validation'
    # the retried output is stamped redone_by_attempt when it is retried, so the receipt counts it (a stored
    # stamp, not an inference). Was: no counts at all ('variant_count' not in summary).
    assert receipt['state'] == 'completed' and (receipt['summary'].get('variant_count'), receipt['summary'].get('completed_variant_count')) == (1, 1)


@pytest.mark.usefixtures('env__r27_419_output_owner')
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
    assert data['generation']['not_redone_failed_count'] == 0             # a queued leftover is not N
    store.change(pid, lambda d: next(v for v in d['output_variants'] if v['id'] == 'stuck').update(status='completed'))
    assert store.read(pid)['generation']['status'] == 'completed'          # the leftover finishing later changes nothing


@pytest.mark.usefixtures('env__r27_419_output_owner')
def test_409_the_receipt_and_settle_share_one_scope(monkeypatch):
    pid = flow.new_project()
    _plan_a, first = _plan_a_partial(pid, monkeypatch)
    data, receipt = _rerun(pid, monkeypatch, first, {'new': OK})
    assert [v['id'] for v in attempts.round_outputs(data)] == ['new']
    assert receipt['summary']['completed_variant_count'] == data['generation']['completed_variant_count'] == 1


# --- #411 the variant retry's route comes from the source output's plan ---

@pytest.mark.usefixtures('env__r27_419_output_owner')
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

@pytest.mark.usefixtures('env__r27_419_output_owner')
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

@pytest.mark.usefixtures('env__r27_419_output_owner')
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


@pytest.mark.usefixtures('env__r27_419_output_owner')
def test_409b_variant_retry_is_judged_on_the_round_it_redid(monkeypatch):
    """A partial -> re-run B partial -> 「重试这条」 on A's failed output succeeds: the retry is judged on A's outputs
the round is the output it redid (redone_by_attempt); A's other outputs and B's failure are not its."""
    pid = flow.new_project()
    _plan_a, first = _plan_a_partial(pid, monkeypatch)
    _screen_and_plan(pid, monkeypatch, PLAN_B, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.render_outcome(pid, {'b-ok': OK, 'b-bad': BAD})
    flow.retry_variant(pid, 'bad', 'v1')
    flow.render_outcome(pid, {'bad': OK})
    data, receipt = store.read(pid), flow.receipts(pid)[-1]
    # only the output this retry redid; A's earlier completed output is not this round's. Was: variant_count 2.
    assert (data['generation']['status'], receipt['state'], receipt['summary']['variant_count']) == ('completed', 'completed', 1)
    assert data['generation']['not_redone_failed_count'] == 1          # B's failed output, still listed
