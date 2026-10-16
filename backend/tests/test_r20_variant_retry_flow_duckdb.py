"""R19/R20 #108: the events the real 「重试这条」 flow emits, run through the real v4 success-rate SQL (DuckDB).

Events come from the real frontend tracker + studio api (node helper). The SQL is #416's
docs/analytics/success_rate.sql (fix/158-success-rate-sql-v4); until #416 merges a verbatim copy lives in
tests/fixtures (sha256 pinned), afterwards the repo file itself is used. ClickHouse -> DuckDB via sqlglot,
with toString/toDateTime/toDate/multiIf shims only (no logic rewritten).
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import os

import pytest

# In CI (requirements-test.txt pins both) a missing dependency is a failure, never a silent skip.
IN_CI = bool(os.environ.get('CI'))
if IN_CI:
    import duckdb
    import sqlglot
else:
    duckdb = pytest.importorskip('duckdb')
    sqlglot = pytest.importorskip('sqlglot')

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / 'fixtures' / 'success_rate_v4_416.sql'
FIXTURE_SHA = 'd0fc6df1d62e3e98ab6330966cac80735f5e0dc5b278220a0d9ec2270cf00e23'
FIELDS = ['attempt_id', 'flow_id', 'outcome', 'error_code', 'upstream_error_type', 'failure_stage', 'app_version',
          'retry_of', 'analytics_environment', 'runtime']


def _v4_sql():
    repo = ROOT / 'docs' / 'analytics' / 'success_rate.sql'
    text = repo.read_text(encoding='utf-8') if repo.exists() else ''
    if 'retry chain' not in text:  # #416 not merged yet: pinned verbatim copy
        assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == FIXTURE_SHA
        text = FIXTURE.read_text(encoding='utf-8')
    q = text.split('-- 图 1')[1].split('-- 图 2')[0]
    q = q[q.index('\n') + 1:]
    q = (q.replace('{date_from}', "'2026-10-01 00:00:00'").replace('{date_to}', "'2026-11-01 00:00:00'")
         .replace('person_id NOT IN COHORT {internal_cohort_id}', 'person_id NOT IN (SELECT person_id FROM internal_cohort)'))
    return sqlglot.transpile(q, read='clickhouse', write='duckdb')[0]


def _db(events):
    con = duckdb.connect()
    con.execute("""CREATE MACRO tostring(x) AS CAST(x AS VARCHAR);
      CREATE MACRO todatetime(x, tz) AS CAST(x AS TIMESTAMP);
      CREATE MACRO todate(x) AS CAST(x AS DATE);
      CREATE MACRO multiif(c1,v1,e) AS CASE WHEN c1 THEN v1 ELSE e END,
        (c1,v1,c2,v2,e) AS CASE WHEN c1 THEN v1 WHEN c2 THEN v2 ELSE e END,
        (c1,v1,c2,v2,c3,v3,e) AS CASE WHEN c1 THEN v1 WHEN c2 THEN v2 WHEN c3 THEN v3 ELSE e END,
        (c1,v1,c2,v2,c3,v3,c4,v4,e) AS CASE WHEN c1 THEN v1 WHEN c2 THEN v2 WHEN c3 THEN v3 WHEN c4 THEN v4 ELSE e END;""")
    con.execute('CREATE TABLE internal_cohort(person_id VARCHAR)')
    con.execute('CREATE TABLE events(uuid VARCHAR, event VARCHAR, person_id VARCHAR, timestamp TIMESTAMP, properties STRUCT('
                + ', '.join(f'{f} VARCHAR' for f in FIELDS) + '))')
    for i, e in enumerate(events):
        props = {f: (None if e['props'].get(f) is None else str(e['props'][f])) for f in FIELDS}
        props.update(analytics_environment='production', runtime='desktop')
        con.execute('INSERT INTO events VALUES (?, ?, ?, ?, ?)',
                    [f'u{i}', e['event'], 'person-1', f'2026-10-10 10:{i:02d}:00', props])
    return con


def _flow_events():
    node = shutil.which('node')
    if not node or not (ROOT / 'frontend' / 'node_modules').exists():
        if IN_CI:
            pytest.fail('node + frontend deps are installed in CI; refusing to skip the v4 SQL flow test')
        pytest.skip('node + frontend deps required')
    out = subprocess.run([node, 'tests/helpers/variant-retry-flow.cjs'], cwd=ROOT / 'frontend',
                         capture_output=True, text=True, timeout=120, check=True)
    return json.loads(out.stdout)


def _chart1(events):
    con = _db(events)
    cur = con.execute(_v4_sql())
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def test_partial_then_variant_retry_counts_one_successful_flow():
    events = _flow_events()
    gen = [e['props'] for e in events if e['event'] == 'studio_generation_finished']
    assert len(gen) == 2 and gen[1]['attempt_id'] != gen[0]['attempt_id'] and gen[1]['retry_of'] == gen[0]['attempt_id']
    [row] = _chart1(events)
    assert row['q_all'] == 2 and row['ok'] == 1          # attempt level: partial + success
    assert row['overall_flow_rate'] == 1.0 and row['product_flow_rate'] == 1.0  # one flow, last attempt = success


def test_without_retry_of_the_same_events_count_two_flows():
    """Mutation guard: drop retry_of (or reuse a new flow) and the flow rate is no longer 1/1."""
    events = _flow_events()
    for e in events:
        e['props'].pop('retry_of', None)
        if e['event'] == 'studio_generation_finished':
            e['props']['flow_id'] = e['props']['attempt_id']
    [row] = _chart1(events)
    assert row['overall_flow_rate'] == 0.5
