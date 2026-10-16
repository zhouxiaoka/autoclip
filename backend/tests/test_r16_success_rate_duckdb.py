"""R16 #46/#47: execute docs/analytics/success_rate.sql for real (DuckDB with a small ClickHouse/HogQL
shim) on synthetic events. Expected numbers are computed by hand below; mutations of the per-flow
definition (last -> any success, last -> first, ignoring retry_of) must change them."""
import re
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / 'docs/analytics/success_rate.sql').read_text(encoding='utf-8')
PROPS = ('attempt_id', 'flow_id', 'retry_of', 'outcome', 'error_code', 'upstream_error_type', 'failure_stage',
         'app_version', 'analytics_environment', 'runtime', 'provider')
COHORT = 641509
DAY = datetime(2026, 10, 12, 8, 0, 0)
PARAMS = {'date_from': "'2026-10-09 00:00:00'", 'date_to': "'2026-10-16 00:00:00'", 'internal_cohort_id': str(COHORT)}


def statements(sql=SQL):
    body = re.sub(r'--[^\n]*', '', sql)
    for key, value in PARAMS.items():
        body = body.replace('{%s}' % key, value)
    return [part.strip() for part in body.split(';') if part.strip()]


def _split_args(text, start):
    """Args of the call whose '(' is at text[start]; returns (args, index after ')')."""
    depth, args, current, i = 0, [], '', start
    while True:
        ch = text[i]
        if ch == '(':
            depth += 1
            if depth == 1:
                i += 1
                continue
        elif ch == ')':
            depth -= 1
            if depth == 0:
                args.append(current.strip())
                return args, i + 1
        elif ch == "'":
            end = text.index("'", i + 1)
            current += text[i:end + 1]
            i = end + 1
            continue
        if ch == ',' and depth == 1:
            args.append(current.strip())
            current = ''
        else:
            current += ch
        i += 1


def _rewrite_calls(text, name, render):
    pattern = re.compile(r'\b%s\(' % name)
    while (match := pattern.search(text)):
        args, end = _split_args(text, match.end() - 1)
        text = text[:match.start()] + render([_rewrite_calls(a, name, render) for a in args]) + text[end:]
    return text


def to_duckdb(sql):
    """Only syntax: no semantic change. HogQL -> DuckDB."""
    sql = _rewrite_calls(sql, 'multiIf', lambda a: 'CASE ' + ' '.join(
        f'WHEN {a[i]} THEN {a[i + 1]}' for i in range(0, len(a) - 1, 2)) + f' ELSE {a[-1]} END')
    sql = _rewrite_calls(sql, 'argMinIf', lambda a: f'arg_min({a[0]}, {a[1]}) FILTER (WHERE {a[2]})')
    sql = _rewrite_calls(sql, 'countIf', lambda a: f'count(*) FILTER (WHERE {a[0]})')
    sql = _rewrite_calls(sql, 'argMax', lambda a: f'arg_max({a[0]}, {a[1]})')
    sql = _rewrite_calls(sql, 'toDateTime', lambda a: f'CAST({a[0]} AS TIMESTAMP)')
    sql = _rewrite_calls(sql, 'toDate', lambda a: f'CAST({a[0]} AS DATE)')
    sql = _rewrite_calls(sql, 'toString', lambda a: f'CAST({a[0]} AS VARCHAR)')
    sql = sql.replace('count()', 'count(*)')
    sql = re.sub(r'person_id NOT IN COHORT (\d+)', r'person_id NOT IN (SELECT person_id FROM cohort_people WHERE cohort_id = \1)', sql)
    return sql


class Events:
    def __init__(self):
        self.rows, self.n = [], 0

    def add(self, person, minutes, event='studio_generation_finished', env='production', runtime='desktop',
            app_version='1.5.8', **props):
        self.n += 1
        props = {'analytics_environment': env, 'runtime': runtime, 'app_version': app_version, **props}
        self.rows.append((f'u{self.n:04d}', event, person, DAY + timedelta(minutes=minutes), props))

    def run(self, sql):
        con = duckdb.connect()
        struct = ', '.join(f'{name} VARCHAR' for name in PROPS)
        con.execute(f'CREATE TABLE events (uuid VARCHAR, event VARCHAR, person_id VARCHAR, timestamp TIMESTAMP, properties STRUCT({struct}))')
        for uuid, event, person, ts, props in self.rows:
            con.execute('INSERT INTO events VALUES (?, ?, ?, ?, ?)', [uuid, event, person, ts, {k: props.get(k) for k in PROPS}])
        con.execute('CREATE TABLE cohort_people (cohort_id INTEGER, person_id VARCHAR)')
        con.execute('INSERT INTO cohort_people VALUES (?, ?)', [COHORT, 'staff'])
        cursor = con.execute(to_duckdb(sql))
        names = [d[0] for d in cursor.description]
        return [dict(zip(names, row)) for row in cursor.fetchall()]


def fixture():
    e = Events()
    # A: fail, one-click retry (new flow_id) succeeds -> flow success via retry_of.
    e.add('A', 0, attempt_id='a1', flow_id='FA', outcome='error', error_code='timeout')
    e.add('A', 5, attempt_id='a2', flow_id='FA2', retry_of='a1', outcome='completed')
    # B: success, then a retry of it fails -> flow = LAST attempt = error.
    e.add('B', 0, attempt_id='b1', flow_id='FB', outcome='completed')
    e.add('B', 9, attempt_id='b2', flow_id='FB2', retry_of='b1', outcome='error', error_code='render')
    # C: 3-hop chain c1 <- c2 <- c3(success) <- c4(error); last is error.
    e.add('C', 0, attempt_id='c1', flow_id='FC', outcome='error', error_code='timeout')
    e.add('C', 2, attempt_id='c2', flow_id='FC2', retry_of='c1', outcome='error', error_code='timeout')
    e.add('C', 4, attempt_id='c3', flow_id='FC3', retry_of='c2', outcome='success')
    e.add('C', 6, attempt_id='c4', flow_id='FC4', retry_of='c3', outcome='error', error_code='unexpected')
    # I: fail then retried success (breaks the A/B symmetry so last->first is caught too).
    e.add('I', 0, attempt_id='i1', flow_id='FI', outcome='error', error_code='timeout')
    e.add('I', 7, attempt_id='i2', flow_id='FI2', retry_of='i1', outcome='completed')
    # D: user_hard (invalid key) -> out of both denominators; also an earlier duplicate row of a2's attempt.
    e.add('D', 1, attempt_id='d1', flow_id='FD', outcome='error', error_code='invalid_key')
    # E: product-only exclusion (connection) and a partial delivery.
    e.add('E', 0, attempt_id='e1', flow_id='FE', outcome='error', error_code='connection')
    e.add('E', 3, attempt_id='e2', flow_id='FE2', outcome='partial', error_code='render', app_version='1.5.7')
    # Duplicate terminal rows for one attempt: last row wins (attempt was error, then completed).
    e.add('F', 0, event='studio_production_finished', attempt_id='f1', flow_id='FF', outcome='error', error_code='render', app_version='1.5.7')
    e.add('F', 1, attempt_id='f1', flow_id='FF', outcome='completed', app_version='1.5.7')
    # Noise that must be filtered out.
    e.add('staff', 0, attempt_id='s1', flow_id='FS', outcome='completed')
    e.add('G', 0, attempt_id='g1', flow_id='FG', outcome='error', runtime='web')
    e.add('G', 0, attempt_id='g2', flow_id='FG2', outcome='error', env='development')
    e.add('G', 60 * 24 * 10, attempt_id='g3', flow_id='FG3', outcome='error')
    e.add('G', 1, event='llm_request_finished', outcome='error', upstream_error_type='timeout', provider='deepseek')
    return e


# attempts (after filters/dedupe): a1 E, a2 S, b1 S, b2 E, c1 E, c2 E, c3 S, c4 E, i1 E, i2 S, d1 hard, e1 x, e2 P, f1 S
# ok=5; q_all = 14 - d1 = 13; q_prod = 13 - e1 = 12; partial 1/12
# flows: FA S (a2), FB E (b2), FC E (c4), FI S (i2), FD hard, FE x(e1), FE2 P, FF S -> flow_ok=3, fq_all=7, fq_prod=6
# any-success would give FB/FC success (5); first-attempt would give FA/FI error (2); no retry_of splits every flow.
EXPECTED_DAY = {'ok': 5, 'q_all': 13, 'q_prod': 12, 'flow_ok': 3, 'fq_all': 7, 'fq_prod': 6,
                'overall_attempt_rate': 0.385, 'product_attempt_rate': 0.417,
                'overall_flow_rate': 0.429, 'product_flow_rate': 0.5, 'partial_delivery_rate': 0.083}


def _daily(sql=SQL):
    rows = fixture().run(statements(sql)[0])
    assert len(rows) == 1 and rows[0]['dt'] == '2026-10-12'
    return {k: rows[0][k] for k in EXPECTED_DAY}


def test_daily_attempt_and_flow_rates_match_hand_count():
    assert _daily() == EXPECTED_DAY


MUTATIONS = {
    'last->any success': ("argMax(o, ts) AS fo", "if(max(o = 'success'), 'success', 'error') AS fo"),
    'last->first': ("argMax(o, ts) AS fo", "argMin(o, ts) AS fo"),
    'ignore retry_of': ("b.fid) AS chain_fid", "b.fid) AS chain_fid_unused, b.fid AS chain_fid"),
}


@pytest.mark.parametrize('name', MUTATIONS)
def test_flow_definition_mutations_are_caught(name):
    old, new = MUTATIONS[name]
    first = statements()[0]
    assert old in first, name
    mutated = first.replace(old, new).replace('argMin(', 'arg_min(')
    assert _daily(mutated) != EXPECTED_DAY, name


def test_retry_chain_follows_at_most_four_hops():
    e = Events()
    ids = [f'h{i}' for i in range(6)]
    for i, aid in enumerate(ids):
        e.add('H', i, attempt_id=aid, flow_id=f'F{aid}', outcome='completed' if i == 5 else 'error', error_code='timeout',
              **({'retry_of': ids[i - 1]} if i else {}))
    flows = e.run(statements()[0])[0]
    # h0..h4 collapse into Fh0 (h4 is 4 hops from h0); h5 is 5 hops away -> its own walk ends at Fh1.
    assert flows['fq_all'] == 2 and flows['flow_ok'] == 1


def test_first_production_per_person():
    row = fixture().run(statements()[1])[0]
    # person first qualifying (overall): A E, B S, C E, I E, E E(e1), F S(f1 last row) -> 2/6; D none.
    # product: A E, B S, C E, I E, E P(e2), F S -> 2/6
    assert (row['overall_first_ok'], row['overall_people']) == (2, 6)
    assert (row['product_first_ok'], row['product_people']) == (2, 6)


def test_failure_identity_breakdown():
    rows = fixture().run(statements()[2])
    got = {(r['error_code'], r['outcome'], r['attribution']): r['attempts'] for r in rows}
    assert got[('timeout', 'error', 'product')] == 4
    assert got[('invalid_key', 'error', 'user_both')] == 1
    assert got[('connection', 'error', 'user_product_only')] == 1
    assert got[('render', 'partial', 'product')] == 1
    assert sum(got.values()) == 9


def test_upstream_diagnostic():
    rows = fixture().run(statements()[3])
    assert rows == [{'provider': 'deepseek', 'upstream_error_type': 'timeout', 'events': 1}]


def test_per_version_query():
    rows = {r['app_version']: r for r in fixture().run(statements()[4])}
    assert set(rows) == {'1.5.7', '1.5.8'}
    # 1.5.7: e2 P, f1 S -> ok 1, q_all 2, q_prod 2; flows FE2 P, FF S -> 1/2
    assert {k: rows['1.5.7'][k] for k in ('ok', 'q_all', 'q_prod', 'flow_ok', 'fq_all', 'fq_prod')} == {
        'ok': 1, 'q_all': 2, 'q_prod': 2, 'flow_ok': 1, 'fq_all': 2, 'fq_prod': 2}
    # 1.5.8: 12 attempts, ok 4, q_all 11, q_prod 10; flows FA S, FB E, FC E, FI S, FD hard, FE x -> 2/5, 2/4
    assert {k: rows['1.5.8'][k] for k in ('ok', 'q_all', 'q_prod', 'flow_ok', 'fq_all', 'fq_prod')} == {
        'ok': 4, 'q_all': 11, 'q_prod': 10, 'flow_ok': 2, 'fq_all': 5, 'fq_prod': 4}
    assert rows['1.5.7']['partial_delivery_rate'] == 0.5


def test_per_version_last_any_mutation_is_caught():
    stmt = statements()[4]
    old = "argMax(o, ts) AS fo"
    assert old in stmt
    rows = {r['app_version']: r for r in fixture().run(stmt.replace(old, "if(max(o = 'success'), 'success', 'error') AS fo"))}
    assert rows['1.5.8']['flow_ok'] != 2
