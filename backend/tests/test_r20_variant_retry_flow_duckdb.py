"""R19/R20 #108, R21 #160/#161: the events the real 「重试这条」 flow emits, run through the real v4 success-rate SQL (DuckDB).

Events come from the real frontend tracker + studio api (node helper). The SQL is read ONLY from the repo file
docs/analytics/success_rate.sql (one copy, no fixture, no keyword fallback). ClickHouse -> DuckDB through backend/tests/success_rate_sql.py,
the one syntax-only adapter shared with test_r16 (R23 #229).

Base includes #416: only the repo file is read (no fixture copy, no skip, no fallback).
"""
import json
from datetime import datetime
import shutil
import subprocess
from pathlib import Path

import os

import pytest

# In CI (requirements-test.txt pins duckdb) a missing dependency is a failure, never a silent skip.
IN_CI = bool(os.environ.get('CI'))
if IN_CI:
    import duckdb  # noqa: F401
else:
    pytest.importorskip('duckdb')
from backend.tests.success_rate_sql import SQL, figure, run_sql  # noqa: E402  (R23 #229: the one SQL adapter)

ROOT = Path(__file__).resolve().parents[2]
WINDOW = {'date_from': "'2026-10-01 00:00:00'", 'date_to': "'2026-11-01 00:00:00'", 'internal_cohort_id': '641509'}


def _rows(events):
    return [(f'u{i}', e['event'], 'person-1', datetime(2026, 10, 10, 10, i),
             {**e['props'], 'analytics_environment': 'production', 'runtime': 'desktop',
              'app_version': e['props'].get('app_version') or '1.5.8'}) for i, e in enumerate(events)]


def _flow_events():
    node = shutil.which('node')
    if not node or not (ROOT / 'frontend' / 'node_modules').exists():
        if IN_CI:
            pytest.fail('node + frontend deps are installed in CI; refusing to skip the v4 SQL flow test')
        pytest.skip('node + frontend deps required')
    out = subprocess.run([node, 'tests/helpers/variant-retry-flow.cjs'], cwd=ROOT / 'frontend',
                         capture_output=True, text=True, timeout=120, check=True)
    return json.loads(out.stdout)


def _chart(n, events):
    return run_sql(figure(n, SQL, WINDOW), _rows(events))


def _one_flow(row, attempts, ok):
    assert row['q_all'] == attempts and row['ok'] == ok
    assert (row['flow_ok'], row['fq_all'], row['fq_prod']) == (1, 1, 1), row
    assert row['overall_flow_rate'] == 1.0 and row['product_flow_rate'] == 1.0


@pytest.mark.parametrize('figure', [1, 5])
def test_partial_then_variant_retry_counts_one_successful_flow(figure):
    events = _flow_events()
    gen = [e['props'] for e in events if e['event'] == 'studio_generation_finished']
    assert len(gen) == 2 and gen[1]['attempt_id'] != gen[0]['attempt_id'] and gen[1]['retry_of'] == gen[0]['attempt_id']
    [row] = _chart(figure, events)
    _one_flow(row, attempts=2, ok=1)   # attempt level: partial + success; flow level: exactly one, successful


@pytest.mark.parametrize('figure', [1, 5])
def test_duplicate_terminal_events_still_one_attempt_each(figure):
    events = _flow_events()
    events += [json.loads(json.dumps(e)) for e in events if e['event'] == 'studio_generation_finished']
    [row] = _chart(figure, events)
    _one_flow(row, attempts=2, ok=1)


@pytest.mark.parametrize('figure', [1, 5])
def test_multi_hop_retry_chain_is_one_flow(figure):
    """failed -> partial -> success, each retry pointing at the previous attempt; every hop has a new flow_id."""
    hops = [('t-aaaaaaaaaaaa', 'failed', None), ('t-bbbbbbbbbbbb', 'partial', 't-aaaaaaaaaaaa'), ('t-cccccccccccc', 'completed', 't-bbbbbbbbbbbb')]
    events = [{'event': 'studio_generation_finished', 'props': {'attempt_id': a, 'flow_id': 'f-' + a, 'outcome': o, 'retry_of': r,
               'error_code': None if o == 'completed' else 'timeout'}} for a, o, r in hops]
    [row] = _chart(figure, events)
    _one_flow(row, attempts=3, ok=1)


@pytest.mark.parametrize('figure', [1, 5])
def test_without_retry_of_the_same_events_count_two_flows(figure):
    """Mutation guard: drop retry_of (or reuse a new flow) and the flow rate is no longer 1/1."""
    events = _flow_events()
    for e in events:
        e['props'].pop('retry_of', None)
        if e['event'] == 'studio_generation_finished':
            e['props']['flow_id'] = e['props']['attempt_id']
    [row] = _chart(figure, events)
    assert row['overall_flow_rate'] == 0.5 and row['fq_all'] == 2
