"""#419 acceptance, the real chain (design-retro: store -> history -> observer -> send -> official SQL).

The real backend (store + jobs, executor stubbed) produces the partial generation, the retry-command response and
the final state; the real frontend tracker/api/StudioResults button project them into events; the repo's
docs/analytics/success_rate.sql (DuckDB adapter) counts them. Replaces the R20 flow test whose events came from
frontend-invented attempts."""
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import pytest

IN_CI = bool(os.environ.get('CI'))
if IN_CI:
    import duckdb  # noqa: F401
else:
    pytest.importorskip('duckdb')
from backend.tests import attempt_flow as flow  # noqa: E402
from backend.tests.success_rate_sql import SQL, figure, run_sql  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WINDOW = {'date_from': "'2026-10-01 00:00:00'", 'date_to': "'2026-11-01 00:00:00'", 'internal_cohort_id': '641509',
          'release_1_5_7': "'2026-10-01 00:00:00'"}


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    flow.setup_env(tmp_path, monkeypatch)
    monkeypatch.setenv('AUTOCLIP_POSTHOG_KEY', 'phc_test')
    monkeypatch.setenv('AUTOCLIP_MODE', 'desktop')
    monkeypatch.setenv('AUTOCLIP_BUILD_ENVIRONMENT', 'production')
    posted = []

    def fake(req, timeout=0):
        posted.append(json.loads(req.data.decode()))
        raise OSError('tests do not send')

    monkeypatch.setattr('urllib.request.urlopen', fake)
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


def test_events_are_projections_of_backend_receipts(env):
    result, receipts = _chain(env)
    [post] = result['posts']
    assert post['url'] == '/studio/p1/retry' and post['body']['scope'] == 'variant'
    gen = [e['props'] for e in result['events'] if e['event'] == 'studio_generation_finished']
    assert [g['attempt_id'] for g in gen] == [r['attempt_id'] for r in receipts]  # one each, restart re-sent nothing
    assert gen[1]['retry_of'] == receipts[0]['attempt_id'] == gen[0]['attempt_id']
    assert [g['outcome'] for g in gen] == ['partial', 'success'] and gen[0]['error_code'] == 'timeout'


@pytest.mark.parametrize('fig', [1, 5])
@pytest.mark.parametrize('order', [('ok', 'bad'), ('bad', 'ok')])
def test_partial_then_retry_is_one_successful_flow_whatever_the_goal_order(fig, order, env):
    result, _ = _chain(env, order)
    [row] = run_sql(figure(fig, SQL, WINDOW), _rows(result['events']))
    assert row['q_all'] == 2 and row['ok'] == 1
    assert (row['flow_ok'], row['fq_all'], row['fq_prod']) == (1, 1, 1), row
    assert row['overall_flow_rate'] == 1.0 and row['product_flow_rate'] == 1.0


@pytest.mark.parametrize('fig', [1, 5])
def test_duplicate_deliveries_still_count_one_attempt_each(fig, env):
    result, _ = _chain(env)
    events = result['events'] + [json.loads(json.dumps(e)) for e in result['events'] if e['event'] == 'studio_generation_finished']
    [row] = run_sql(figure(fig, SQL, WINDOW), _rows(events))
    assert row['q_all'] == 2 and row['fq_all'] == 1


@pytest.mark.parametrize('fig', [1, 5])
def test_mutation_guard_without_the_receipt_retry_of_it_is_two_flows(fig, env):
    result, _ = _chain(env)
    for e in result['events']:
        e['props'].pop('retry_of', None)
        if e['event'] == 'studio_generation_finished':
            e['props']['flow_id'] = e['props']['attempt_id']
    [row] = run_sql(figure(fig, SQL, WINDOW), _rows(result['events']))
    assert row['fq_all'] == 2 and row['overall_flow_rate'] == 0.5


@pytest.mark.parametrize('fig', [1, 5])
def test_346_out_of_order_observation_is_still_one_successful_flow(fig, env):
    """R25 #346 on the real chain: the retry's terminal is observed BEFORE the partial one (offline client); the
    events carry the receipt sequence and success_rate.sql orders by it, so figures 1 and 5 stay at 100%."""
    result, receipts = _chain(env)
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
