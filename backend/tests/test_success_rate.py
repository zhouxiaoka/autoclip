"""Behavior tests for the success-rate query, history terminals, and tracking docs."""
import re
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from backend.tests.success_rate_sql import COHORT, PARAMS, SQL, run_sql, statements, to_duckdb  # noqa: F401 (#229: one adapter)


# 70/#71: every v4 exclusion rule and every forced product failure, mutated one by one

import json  # noqa: E402
import json
import shutil
import subprocess

from backend.services.studio import store

from backend.services.studio import attempts, store
"""execute docs/analytics/success_rate.sql for real (DuckDB with a small ClickHouse/HogQL
shim) on synthetic events. Expected numbers are computed by hand below; mutations of the per-flow
definition (last -> any success, last -> first, ignoring retry_of) must change them."""

ROOT = Path(__file__).resolve().parents[2]
DAY = datetime(2026, 10, 12, 8, 0, 0)


class Events:
    def __init__(self):
        self.rows, self.n = [], 0

    def add(self, person, minutes, event='studio_generation_finished', env='production', runtime='desktop',
            app_version='1.5.7', **props):
        self.n += 1
        props = {'analytics_environment': env, 'runtime': runtime, 'app_version': app_version, **props}
        self.rows.append((f'u{self.n:04d}', event, person, DAY + timedelta(minutes=minutes), props))

    def run(self, sql):
        return run_sql(sql, self.rows, staff=('staff',), cohort=COHORT)


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
    e.add('E', 3, attempt_id='e2', flow_id='FE2', outcome='partial', error_code='render', app_version='1.5.6')
    # Duplicate terminal rows for one attempt: last row wins (attempt was error, then completed).
    e.add('F', 0, event='studio_production_finished', attempt_id='f1', flow_id='FF', outcome='error', error_code='render', app_version='1.5.6')
    e.add('F', 1, attempt_id='f1', flow_id='FF', outcome='completed', app_version='1.5.6')
    # Noise that must be filtered out.
    e.add('staff', 0, attempt_id='s1', flow_id='FS', outcome='completed')
    e.add('G', 0, attempt_id='g1', flow_id='FG', outcome='error', runtime='web')
    e.add('G', 0, attempt_id='g2', flow_id='FG2', outcome='error', env='development')
    # validation is still excluded by analytics_environment.
    e.add('G', 2, attempt_id='g4', flow_id='FG4', outcome='completed', env='validation')
    # Pre-release production 1.5.7 (one hour before the fixture release cutoff). Must stay out of the 1.5.7 bucket.
    e.add('P', -60, attempt_id='p0', flow_id='FP0', outcome='completed')
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
    'last->any success': ("argMax(o, ord) AS fo", "if(max(o = 'success'), 'success', 'error') AS fo"),
    'last->first': ("argMax(o, ord) AS fo", "argMin(o, ord) AS fo"),
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
    assert set(rows) == {'1.5.6', '1.5.7'}
    # 1.5.6: e2 P, f1 S -> ok 1, q_all 2, q_prod 2; flows FE2 P, FF S -> 1/2
    assert {k: rows['1.5.6'][k] for k in ('ok', 'q_all', 'q_prod', 'flow_ok', 'fq_all', 'fq_prod')} == {
        'ok': 1, 'q_all': 2, 'q_prod': 2, 'flow_ok': 1, 'fq_all': 2, 'fq_prod': 2}
    # 1.5.7 production: 12 attempts, ok 4, q_all 11, q_prod 10; flows FA S, FB E, FC E, FI S, FD hard, FE x -> 2/5, 2/4
    # g4 (validation) and p0 (pre-release production) stay out of this bucket.
    assert {k: rows['1.5.7'][k] for k in ('ok', 'q_all', 'q_prod', 'flow_ok', 'fq_all', 'fq_prod')} == {
        'ok': 4, 'q_all': 11, 'q_prod': 10, 'flow_ok': 2, 'fq_all': 5, 'fq_prod': 4}
    assert rows['1.5.6']['partial_delivery_rate'] == 0.5


def test_release_cutoff_keeps_earlier_versions_and_drops_pre_release_1_5_7():
    """1.5.6 before the cutoff still counts. A production 1.5.7 before it does not enter the 1.5.7 bucket.
    An event at the cutoff (inclusive) does. A blank release time drops every 1.5.7 event."""
    e = Events()
    e.add('Old', -120, attempt_id='old', flow_id='Fold', outcome='completed', app_version='1.5.6')
    e.add('Pre', -30, attempt_id='pre', flow_id='Fpre', outcome='completed')
    e.add('On', 0, attempt_id='on', flow_id='Fon', outcome='error', error_code='render')
    rows = {r['app_version']: r for r in e.run(statements()[4])}
    assert set(rows) == {'1.5.6', '1.5.7'}
    assert rows['1.5.6']['ok'] == 1 and rows['1.5.6']['q_all'] == 1
    assert rows['1.5.7']['ok'] == 0 and rows['1.5.7']['q_all'] == 1
    blank = dict(PARAMS)
    blank['release_1_5_7'] = "''"
    only_old = {r['app_version']: r for r in e.run(statements(params=blank)[4])}
    assert set(only_old) == {'1.5.6'}
    assert '{release_1_5_7}' in SQL and "SELECT '1.5.7' AS app_version, '20" not in SQL


def test_per_version_last_any_mutation_is_caught():
    stmt = statements()[4]
    old = "argMax(o, ord) AS fo"
    assert old in stmt
    rows = {r['app_version']: r for r in fixture().run(stmt.replace(old, "if(max(o = 'success'), 'success', 'error') AS fo"))}
    assert rows['1.5.7']['flow_ok'] != 2

V4 = json.loads((ROOT / 'docs/analytics/event_catalog.json').read_text(encoding='utf-8'))['attribution']['success_rate_v4']
# every forced product failure also in upstream_error_type form.
PRODUCT_FAILURE_UPSTREAM = ('model_not_found', 'bad_endpoint', 'whisper_not_installed', 'service_restarted')


def exclusion_fixture():
    """Two successes + one single-attempt flow per rule (each its own person and flow)."""
    e = Events()
    n = iter(range(1000))

    def one(**props):
        i = next(n)
        e.add(f'X{i}', i, attempt_id=f'x{i}', flow_id=f'FX{i}', **props)
    one(outcome='completed')
    one(outcome='success')
    one(outcome='cancelled')                                            # user_hard: outcome
    one(outcome='canceled')                                             # ... US spelling alias (#140)
    for code in V4['overall_excluded_error_codes']:                     # user_hard: error_code
        one(outcome='error', error_code=code)
    for kind in V4['overall_excluded_upstream_types']:                  # user_hard: upstream auth/quota
        one(outcome='error', error_code='provider_error', upstream_error_type=kind)
    for code in V4['product_extra_excluded_error_codes']:               # user_x: product-only exclusion
        one(outcome='error', error_code=code)
    for code in V4['product_failure_codes']:                            # forced product failures
        one(outcome='error', error_code=code)
    for kind in PRODUCT_FAILURE_UPSTREAM:                               # ... also as upstream type
        one(outcome='error', error_code='provider_error', upstream_error_type=kind)
    return e


N_HARD = 2 + len(V4['overall_excluded_error_codes']) + len(V4['overall_excluded_upstream_types'])
N_X = len(V4['product_extra_excluded_error_codes'])
N_PF = len(V4['product_failure_codes']) + len(PRODUCT_FAILURE_UPSTREAM)
EXPECTED_EXCL = {'ok': 2, 'q_all': 2 + N_X + N_PF, 'q_prod': 2 + N_PF,
                 'flow_ok': 2, 'fq_all': 2 + N_X + N_PF, 'fq_prod': 2 + N_PF}


def _excl(sql=None):
    rows = exclusion_fixture().run(sql or statements()[0])
    return {k: rows[0][k] for k in EXPECTED_EXCL}


def test_catalog_lists_every_rule_dong_named():
    assert set(V4['overall_excluded_outcomes']) == {'cancelled'}
    assert {'cancelled', 'user_cancelled', 'authentication', 'llm_auth_invalid', 'invalid_key',
            'insufficient_quota', 'llm_not_configured'} <= set(V4['overall_excluded_error_codes'])
    assert set(V4['overall_excluded_upstream_types']) == {'invalid_key', 'insufficient_quota', 'permission_denied'}
    assert set(V4['product_extra_excluded_error_codes']) == {'connection', 'source_too_short', 'source_no_audio', 'source_unreadable', 'source_blocked', 'source_not_found'}
    assert set(V4['product_failure_codes']) == {'whisper_not_installed', 'service_restarted', 'model_not_found', 'bad_endpoint'}


def test_every_exclusion_and_product_failure_lands_in_the_right_denominator():
    # 2 ok; hard (N_HARD) out of both; user_x (N_X) only out of product; forced failures (N_PF) in both.
    assert _excl() == EXPECTED_EXCL
    assert (N_HARD, N_X, N_PF) == (12, 6, 8)
    # 8 forced product failures; user_x now includes source_not_found -> all/product denominators 16/10.
    assert (EXPECTED_EXCL['q_all'], EXPECTED_EXCL['q_prod']) == (16, 10)
    assert set(PRODUCT_FAILURE_UPSTREAM) == set(V4['product_failure_codes'])


def test_forced_product_failures_count_in_both_rates_and_attribution():
    rows = exclusion_fixture().run(statements()[2])
    by_code = {}
    for r in rows:
        by_code.setdefault(r['error_code'], set()).add(r['attribution'])
    for code in V4['product_failure_codes']:
        assert by_code[code] == {'product'}, code
    for code in V4['product_extra_excluded_error_codes']:
        assert by_code[code] == {'user_product_only'}, code
    for code in V4['overall_excluded_error_codes']:
        assert by_code[code] == {'user_both'}, code
    # per-person first production also counts them as failures in both scopes
    first = exclusion_fixture().run(statements()[1])[0]
    assert (first['overall_first_ok'], first['overall_people']) == (2, 2 + N_X + N_PF)
    assert (first['product_first_ok'], first['product_people']) == (2, 2 + N_PF)


def _list_mutation(stmt, list_pattern, transform):
    match = re.search(list_pattern, stmt)
    assert match, list_pattern
    items = re.findall(r"'(\w+)'", match.group(1))
    new = ', '.join(f"'{x}'" for x in transform(items))
    return stmt[:match.start(1)] + new + stmt[match.end(1):]


HARD_EC = r"OR ec IN \(([^)]*)\)\s*OR ue IN"
HARD_UE = r"OR ue IN \(([^)]*)\)\) AS user_hard"
EXTRA_EC = r"user_hard OR ec IN \(([^)]*)\)\) AS user_x"


def _mutations():
    out = {'cancel no longer excluded': lambda s: re.sub(r"\(o = 'cancelled'\s*OR", '(false OR', s, count=1),
           # dropping the US-spelling alias must be caught in every figure.
           "'canceled' alias dropped": lambda s: s.replace("o_raw IN ('cancelled', 'canceled')", "o_raw IN ('cancelled')")}
    for code in V4['overall_excluded_error_codes']:
        out[f'error_code {code} no longer excluded'] = lambda s, c=code: _list_mutation(s, HARD_EC, lambda xs: [x for x in xs if x != c])
    for kind in V4['overall_excluded_upstream_types']:
        out[f'upstream {kind} no longer excluded'] = lambda s, k=kind: _list_mutation(s, HARD_UE, lambda xs: [x for x in xs if x != k])
    for code in V4['product_extra_excluded_error_codes']:
        out[f'{code} no longer product-excluded'] = lambda s, c=code: _list_mutation(s, EXTRA_EC, lambda xs: [x for x in xs if x != c])
        out[f'{code} wrongly excluded from overall'] = lambda s, c=code: _list_mutation(s, HARD_EC, lambda xs: xs + [c])
    for code in V4['product_failure_codes']:
        out[f'{code} wrongly product-excluded'] = lambda s, c=code: _list_mutation(s, EXTRA_EC, lambda xs: xs + [c])
        out[f'{code} wrongly excluded from overall'] = lambda s, c=code: _list_mutation(s, HARD_EC, lambda xs: xs + [c])
    for kind in PRODUCT_FAILURE_UPSTREAM:
        out[f'upstream {kind} wrongly excluded'] = lambda s, k=kind: _list_mutation(s, HARD_UE, lambda xs: xs + [k])
    return out


MUTATIONS_R18 = _mutations()


@pytest.mark.parametrize('name', sorted(MUTATIONS_R18))
def test_each_exclusion_rule_mutation_is_caught(name):
    original = statements()[0]
    mutated = MUTATIONS_R18[name](original)
    assert mutated != original, name
    assert _excl(mutated) != EXPECTED_EXCL, name


# 103: the same rule mutations must be caught in every figure that carries the rules (1, 2, 3, 5),
# each figure mutated on its own (the other statements stay intact). ---

RATE_KEYS = ('ok', 'q_all', 'q_prod', 'flow_ok', 'fq_all', 'fq_prod')


def _fig1(rows):
    return {k: rows[0][k] for k in RATE_KEYS}


def _fig2(rows):
    r = rows[0]
    return (r['overall_first_ok'], r['overall_people'], r['product_first_ok'], r['product_people'])


def _fig3(rows):
    return sorted((str(r['error_code']), str(r['outcome']), str(r['attribution']), r['attempts']) for r in rows)


def _fig5(rows):
    assert len(rows) == 1 and rows[0]['app_version'] == '1.5.7'
    return {k: rows[0][k] for k in RATE_KEYS}


FIGURES = {'fig1_daily': (0, _fig1), 'fig2_first_per_person': (1, _fig2),
           'fig3_failure_identity': (2, _fig3), 'fig5_per_version': (4, _fig5)}


def test_figure_baselines_match_hand_count():
    stmts = statements()
    run = lambda i: exclusion_fixture().run(stmts[i])
    assert _fig1(run(0)) == EXPECTED_EXCL
    assert _fig5(run(4)) == EXPECTED_EXCL
    assert _fig2(run(1)) == (2, 2 + N_X + N_PF, 2, 2 + N_PF)


@pytest.mark.parametrize('figure', sorted(FIGURES))
@pytest.mark.parametrize('name', sorted(MUTATIONS_R18))
def test_each_rule_mutation_is_caught_in_every_figure(figure, name):
    index, extract = FIGURES[figure]
    stmt = statements()[index]
    mutated = MUTATIONS_R18[name](stmt)
    assert mutated != stmt, (figure, name)
    baseline = extract(exclusion_fixture().run(stmt))
    assert extract(exclusion_fixture().run(mutated)) != baseline, (figure, name)


# 142: an empty denominator yields NULL, never NaN/inf

def _only_product_excluded():
    """One person whose only attempt is a product-only exclusion: product denominators are 0."""
    e = Events()
    e.add('Z', 0, attempt_id='z1', flow_id='FZ', outcome='error', error_code='connection')
    return e


def test_142_zero_product_denominator_is_null_not_nan():
    stmts = statements()
    day = _only_product_excluded().run(stmts[0])[0]
    assert (day['q_all'], day['q_prod'], day['fq_prod']) == (1, 0, 0)
    for key in ('product_attempt_rate', 'product_flow_rate', 'partial_delivery_rate'):
        assert day[key] is None, key
    assert day['overall_attempt_rate'] == 0.0
    version = _only_product_excluded().run(stmts[4])[0]
    for key in ('product_attempt_rate', 'product_flow_rate', 'partial_delivery_rate'):
        assert version[key] is None, key
    first = _only_product_excluded().run(stmts[1])[0]
    assert first['product_people'] == 0 and first['product_first_rate'] is None


def test_142_every_rate_division_is_guarded():
    body = re.sub(r'--[^\n]*', '', SQL)
    divisions = re.findall(r'[\w.]+ / [^\n,]+', body)
    assert len(divisions) == 12
    for expr in divisions:
        assert re.fullmatch(r'[\w.]+ / nullIf\([\w.]+', expr.strip()), expr


# 203: the overall (全量) denominators can be 0 too: NULL, never 0%

OVERALL_RATES = ('overall_attempt_rate', 'overall_flow_rate')
ALL_RATES = (*OVERALL_RATES, 'product_attempt_rate', 'product_flow_rate', 'partial_delivery_rate')


def _all_user_excluded():
    """Every attempt is a user cause (cancel / auth / quota): overall AND product denominators are 0."""
    e = Events()
    e.add('Y', 0, attempt_id='y1', flow_id='FY', outcome='cancelled')
    e.add('Y', 5, attempt_id='y2', flow_id='FY2', outcome='error', error_code='authentication')
    e.add('W', 9, attempt_id='w1', flow_id='FW', outcome='error', upstream_error_type='insufficient_quota')
    return e


def _assert_all_excluded_is_null(stmts):
    for index in (0, 4):                                   # fig1 daily, fig5 per version
        row = _all_user_excluded().run(stmts[index])[0]
        assert (row['q_all'], row['q_prod'], row['fq_all'], row['fq_prod']) == (0, 0, 0, 0), index
        for key in ALL_RATES:
            assert row[key] is None, (index, key)
    first = _all_user_excluded().run(stmts[1])[0]
    assert (first['overall_people'], first['product_people']) == (0, 0)
    assert first['overall_first_rate'] is None and first['product_first_rate'] is None


def test_203_all_excluded_window_every_rate_is_null_per_column():
    _assert_all_excluded_is_null(statements())


def test_203_empty_window_has_no_zero_rate():
    stmts = statements()
    assert Events().run(stmts[0]) == [] and Events().run(stmts[4]) == []   # no day/version row at all
    first = Events().run(stmts[1])[0]
    assert first['overall_people'] == 0 and first['overall_first_rate'] is None
    assert first['product_first_rate'] is None


@pytest.mark.parametrize('column', [*OVERALL_RATES, 'overall_first_rate'])
def test_203_zero_filling_an_overall_rate_is_caught(column):
    """mutation (survived): ifNull(<overall rate>, 0) must fail the NULL regression."""
    pattern = re.compile(r'round\(([^\n]*?)\) AS ' + column + r'\b')
    mutated = pattern.sub(lambda m: f'ifNull(round({m.group(1)}), 0) AS {column}', SQL)
    assert mutated != SQL
    with pytest.raises(AssertionError):
        _assert_all_excluded_is_null(statements(mutated))


# 346: the flow's last attempt is the backend sequence, not the observation time

def _out_of_order():
    """partial -> retry completed, but the retry's terminal is observed BEFORE the partial (offline client, replay)."""
    e = Events()
    e.add('S', 9, attempt_id='s1', flow_id='FS', outcome='partial', error_code='timeout', attempt_sequence='1')
    e.add('S', 1, attempt_id='s2', flow_id='FS', retry_of='s1', outcome='completed', attempt_sequence='2')
    return e


def test_346_out_of_order_observation_keeps_the_flow_successful_in_figure_1_and_5():
    e = _out_of_order()
    [day] = e.run(statements()[0])
    assert (day['flow_ok'], day['fq_all'], day['overall_flow_rate']) == (1, 1, 1.0)
    [version] = e.run(statements()[4])
    assert (version['flow_ok'], version['fq_all']) == (1, 1)


@pytest.mark.parametrize('figure', [0, 4])
def test_346_ordering_by_observation_time_is_caught(figure):
    stmt = statements()[figure]
    assert stmt.count('(ifNull(seq, 0), leaf, ts) AS ord') == 1
    rows = _out_of_order().run(stmt.replace('(ifNull(seq, 0), leaf, ts) AS ord', '(ts) AS ord'))
    assert rows[0]['flow_ok'] == 0  # the old argMax(o, ts): 100% -> 0%


def test_346_legacy_rows_without_sequence_still_order_by_time():
    e = Events()
    e.add('L', 0, attempt_id='l1', flow_id='FL', outcome='error', error_code='timeout')
    e.add('L', 5, attempt_id='l2', flow_id='FL', retry_of='l1', outcome='completed')
    assert e.run(statements()[0])[0]['flow_ok'] == 1


# 362: legacy flows (no attempt_sequence)
# The fixture has no attempt_sequence at all: it IS the legacy data set. Its hand counts (EXPECTED_DAY,
# per-version) are the pre-#346 SQL results and are asserted unchanged above; here the unknown column is 0.

@pytest.mark.parametrize('figure', [0, 4])
def test_362_legacy_fixture_results_unchanged_and_no_unknown_flow(figure):
    rows = fixture().run(statements()[figure])
    assert all(r['unknown_flows'] == 0 for r in rows)
    if figure == 0:
        assert _daily() == EXPECTED_DAY


def _legacy_out_of_order(e, retry_linked):
    """an old flow: fail, then success - but the success is observed first. retry_linked: the success names the
    failure in retry_of (its end is provable); else both carry the same flow_id and nothing else (unprovable)."""
    e.add('Z', 30, attempt_id='z2', flow_id='FZ', outcome='completed', **({'retry_of': 'z1'} if retry_linked else {}))
    e.add('Z', 40, attempt_id='z1', flow_id='FZ', outcome='error', error_code='timeout')
    return e


def test_362_unprovable_legacy_flow_is_unknown_and_out_of_the_flow_denominator():
    [day] = _legacy_out_of_order(fixture(), retry_linked=False).run(statements()[0])
    # base fixture flows 3/7; the old SQL judged FZ by observation time -> 3/8 = 37.5%; now 3/7 = 42.9% + 1 unknown
    assert (day['flow_ok'], day['fq_all'], day['overall_flow_rate'], day['unknown_flows']) == (3, 7, 0.429, 1)
    assert day['q_all'] == EXPECTED_DAY['q_all'] + 2 and day['ok'] == EXPECTED_DAY['ok'] + 1  # attempts still count
    rows = {r['app_version']: r for r in _legacy_out_of_order(fixture(), retry_linked=False).run(statements()[4])}
    assert (rows['1.5.7']['flow_ok'], rows['1.5.7']['fq_all'], rows['1.5.7']['unknown_flows']) == (2, 5, 1)


def test_362_retry_linked_legacy_flow_takes_the_chain_end_whatever_the_arrival_order():
    [day] = _legacy_out_of_order(fixture(), retry_linked=True).run(statements()[0])
    assert (day['flow_ok'], day['fq_all'], day['unknown_flows']) == (4, 8, 0)  # 4/8 = 50%


LEGACY_MUTATIONS = {
    'no unknown rule': ("(countIf(seq IS NOT NULL) = 0 AND sum(leaf) > 1) AS unknown", "(1 = 0) AS unknown"),
    'every legacy multi-attempt flow unknown': ("(countIf(seq IS NOT NULL) = 0 AND sum(leaf) > 1) AS unknown", "(countIf(seq IS NOT NULL) = 0 AND count() > 1) AS unknown"),
    'unknown still in the denominator': ("countIf(fqa AND NOT unknown) AS fq_all", "countIf(fqa) AS fq_all"),
    'chain end ignored': ("(ifNull(seq, 0), leaf, ts) AS ord", "(ifNull(seq, 0), ts) AS ord"),
}


@pytest.mark.parametrize('figure', [0, 4])
@pytest.mark.parametrize('name', LEGACY_MUTATIONS)
def test_362_legacy_rule_mutations_are_caught(figure, name):
    old, new = LEGACY_MUTATIONS[name]
    stmt = statements()[figure]
    assert old in stmt, name
    mutated = stmt.replace(old, new)
    key = (lambda r: (r['flow_ok'], r['fq_all'], r['unknown_flows'])) if figure == 0 else (lambda r: next((x['flow_ok'], x['fq_all'], x['unknown_flows']) for x in [r]))
    def got(e):
        rows = e.run(mutated)
        return [key(r) for r in rows]
    def want(e):
        return [key(r) for r in e.run(stmt)]
    cases = [fixture(), _legacy_out_of_order(fixture(), False), _legacy_out_of_order(fixture(), True)]
    assert any(got(c) != want(c) for c in cases), name


# 380 (PM P3-b): the documented ordering key is the SQL's real key, (seq, leaf, ts)

ORD = '(ifNull(seq, 0), leaf, ts) AS ord'


def test_380_header_and_tracking_plan_name_the_real_ordering_key():
    for stmt in (statements()[0], statements()[4]):
        assert stmt.count(ORD) == 1            # the key the docs describe is the one both figures use
    header = SQL.split('WITH version_releases', 1)[0]
    assert '(attempt_sequence, leaf, ts)' in header, 'success_rate.sql header must spell out the ordering key'
    plan = (ROOT / 'docs/analytics/TRACKING_PLAN.md').read_text(encoding='utf-8')
    assert '(attempt_sequence, leaf, ts)' in plan, 'TRACKING_PLAN §6.1 must spell out the ordering key'


# 381 (PM P3-c): one flow mixing attempts with and without attempt_sequence

def _mixed(retry_linked, old_outcome, new_outcome):
    """z1 is a pre-#419 attempt (no sequence), z2 a newer retry WITH a sequence, same flow. z2's terminal is
    observed first and z1 is the chain end only by time, so the sequence alone must decide."""
    e = Events()
    e.add('Z', 30, attempt_id='z2', flow_id='FZ', attempt_sequence='1', outcome=new_outcome,
          **({'retry_of': 'z1'} if retry_linked else {}), **({} if new_outcome == 'completed' else {'error_code': 'timeout'}))
    e.add('Z', 40, attempt_id='z1', flow_id='FZ', outcome=old_outcome,
          **({} if old_outcome == 'completed' else {'error_code': 'timeout'}))
    return e


MIXED_CASES = [  # (retry_linked, z1 old, z2 new sequenced) -> flow_ok; the sequenced attempt always wins, never unknown
    (True, 'error', 'completed', 1),     # old unsequenced, new sequenced retry_of old -> new wins
    (False, 'error', 'completed', 1),
    (False, 'completed', 'error', 0),    # the later-observed unsequenced success must not win
]


def _mixed_result(stmt, case):
    linked, old, new, _ = case
    [row] = _mixed(linked, old, new).run(stmt)
    return row['flow_ok'], row['fq_all'], row['unknown_flows']


@pytest.mark.parametrize('figure', [0, 4])
@pytest.mark.parametrize('case', MIXED_CASES)
def test_381_mixed_flow_takes_the_last_sequenced_attempt(figure, case):
    assert _mixed_result(statements()[figure], case) == (case[3], 1, 0)


MIXED_MUTATIONS = {
    'sequence after time': (ORD, '(leaf, ts, ifNull(seq, 0)) AS ord'),
    'any unsequenced attempt makes it unknown': ("(countIf(seq IS NOT NULL) = 0 AND sum(leaf) > 1) AS unknown",
                                                 "(countIf(seq IS NULL) > 0 AND count() > 1) AS unknown"),
}


@pytest.mark.parametrize('figure', [0, 4])
@pytest.mark.parametrize('name', MIXED_MUTATIONS)
def test_381_mixed_flow_mutations_are_caught(figure, name):
    old, new = MIXED_MUTATIONS[name]
    stmt = statements()[figure]
    assert old in stmt
    mutated = stmt.replace(old, new)
    assert any(_mixed_result(mutated, c) != (c[3], 1, 0) for c in MIXED_CASES), name
"""the tracking plan must not claim the live dashboard already shows NULL as
empty. #416's SQL is valid without #419's retry_of producer and can merge on its own."""

PLAN = (Path(__file__).resolve().parents[2] / 'docs/analytics/TRACKING_PLAN.md').read_text(encoding='utf-8')


def test_204_dashboard_null_claim_waits_for_the_post_merge_sync():
    assert '看板显示为空' not in PLAN
    assert '合入后同步' in PLAN


def test_205_416_can_merge_without_419_producer():
    """#416's SQL is valid when retry_of is absent. #419 is what emits it; they do not have to merge together."""
    assert '#419' in PLAN and '#416' in PLAN
    assert '可以单独合入' in PLAN
    assert '先于 #419' in PLAN
    assert '同批合入' not in PLAN


def test_225_sql_header_does_not_claim_live_dashboard_is_aligned():
    """the live insights are synced after this file merges, so line 1 must not say they
already match. Fails on 101deaf4."""
    sql = (Path(__file__).resolve().parents[2] / 'docs/analytics/success_rate.sql').read_text(encoding='utf-8')
    header = sql.splitlines()[0]
    assert '对齐' not in header
    assert '合入后同步' in header
"""run identity survives analysis_history and reaches the terminal event on the real
path: store.write -> later run replaces live analysis -> store.read -> frontend WorkflowTracker."""

FRONTEND = Path(__file__).resolve().parents[2] / 'frontend'
PRESETS = Path(__file__).resolve().parents[1] / 'presets' / 'provider_presets.json'

SCRIPT = r"""
const fs=require('fs'),path=require('path'),vm=require('vm'),ts=require('typescript')
const {loadTs}=require('./tests/load-ts.cjs')
const [kind,id,run,presets]=process.argv.slice(1)
const snapshot=JSON.parse(fs.readFileSync(0,'utf8'))
const exports={}
const deps={'@provider-presets':{__esModule:true,default:JSON.parse(fs.readFileSync(presets,'utf8'))}}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join('src','analytics','workflow.ts'),'utf8'),
 {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText,
 {exports,Date,Math,JSON,Number,Array,Object,Map,Set,String,URL,require:(d)=>{
  if(d==='./failureCodes') return loadTs(path.resolve('src/analytics/failureCodes.ts'))
  if(d in deps)return deps[d]
  throw new Error('dep '+d)
 }})
const events=[],storage=new Map()
const tracker=new exports.WorkflowTracker({getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 ()=>true,(name,props)=>{events.push({name,props});return true})
tracker.watch(kind,id,undefined,undefined,{},false,run)
const watch=tracker.list().find(item=>item.kind===kind)
tracker.observeStudio(watch,snapshot)
process.stdout.write(JSON.stringify(events.filter(e=>e.name.endsWith('_finished'))))
"""

IDENTITY = {'provider': 'gemini', 'config_source': 'customized', 'upstream_error_type': 'rate_limited',
            'failure_stage': 'screening', 'shutdown_kind': 'crash'}


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    store.directory('p').mkdir(parents=True)
    return 'p'


def _capture(kind, watch_id, snapshot):
    if not shutil.which('node') or not (FRONTEND / 'node_modules' / 'typescript').is_dir():
        # never skip (quality_gate treats an unexpected skip as BLOCKED). The frontend toolchain
        # is a required test dependency: `cd frontend && npm ci` (docs/TESTING_ACCEPTANCE.md).
        pytest.fail('frontend toolchain missing: run `cd frontend && npm ci` (node + frontend/node_modules/typescript are required)')
    done = subprocess.run(['node', '-e', SCRIPT, kind, watch_id, 'run', str(PRESETS)], input=json.dumps(snapshot),
                          cwd=FRONTEND, capture_output=True, text=True, check=True, timeout=60)
    return json.loads(done.stdout)


def _posted(monkeypatch):
    posted = []

    def fake(req, timeout=0):
        posted.append(json.loads(req.data.decode()))
        raise OSError('tests do not send')

    monkeypatch.setattr('urllib.request.urlopen', fake)
    monkeypatch.setattr('backend.services.studio.terminal_outbox._RETRY_DELAYS', ())
    return posted


@pytest.mark.parametrize('phase,kind,watch_id', [('screening', 'studio-screen', 'p'), ('production', 'studio-production', 'plan')])
def test_identity_survives_history_to_terminal(project, phase, kind, watch_id, monkeypatch, tmp_path):
    identity = {**IDENTITY, 'failure_stage': phase}
    posted = _posted(monkeypatch)
    if phase == 'production':
        monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
        monkeypatch.setenv('AUTOCLIP_MODE', 'desktop')
        monkeypatch.setenv('AUTOCLIP_BUILD_ENVIRONMENT', 'production')
        monkeypatch.setenv('AUTOCLIP_POSTHOG_KEY', 'phc_test')
    state = {'plan': {'id': 'plan', 'mode': 'local'},
             'analysis': {'status': 'failed', 'phase': phase, 'run_id': 'run', 'error_code': 'service_restarted', **identity}}
    if phase == 'production':
        # v4 production terminals are the settled receipt (#419). The history row still keeps the identity.
        state['attempts'] = [{'attempt_id': 't-aaaaaaaaaaaaaaaa', 'flow_id': 't-ffffffffffffffff', 'sequence': 1,
                              'kind': 'production', 'state': 'open', 'run_id': 'run', 'trigger': 'initial', 'causes': []}]
        state['attempt_sequence'] = 1
        store.write(project, {**state, 'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'run', 'instance': store.INSTANCE}})
        assert posted == []
    store.write(project, state)
    if phase == 'production':
        from backend.services.studio.terminal_outbox import wait_until_idle
        assert wait_until_idle()
        bodies = [item for item in posted if item['event'] == 'studio_production_finished']
        assert len(bodies) == 1, posted
        for key, value in identity.items():
            assert bodies[0]['properties'].get(key) == value, (key, bodies[0]['properties'])
    kept = store.read(project).get('attempts') if phase == 'production' else None
    later = {'plan': {'id': 'plan2', 'mode': 'local'},
             'analysis': {'status': 'running', 'phase': 'screening', 'run_id': 'run2', 'instance': store.INSTANCE}}
    if kept:
        later['attempts'] = kept
    store.write(project, later)
    snapshot = store.read(project)
    receipt = next(row for row in snapshot['analysis_history'] if row['run_id'] == 'run')
    for key, value in identity.items():
        assert receipt['analysis'][key] == value, key
    finished = _capture(kind, watch_id, snapshot)
    if phase == 'production':
        assert finished == []  # 成功率终态由后端在结算时发出，打开结果页不再补一条
        assert len([item for item in posted if item['event'] == 'studio_production_finished']) == 1
        return
    assert len(finished) == 1, finished
    props = finished[0]['props']
    for key, value in identity.items():
        assert props.get(key) == value, (key, props)
"""(#406): degrade_reason survives the terminal record (analysis_history allowlist) and
reaches the frontend terminal event on the real path: store -> frontend read -> capture.
the terminal is a projection of the backend attempt receipt; the reason is frozen in the receipt at settle
from that attempt's own plan, so a later re-screen (plan2, no reason) cannot drop or change it."""
REASONS = ['frame_extract_subtitle_fallback', 'source_too_long_subtitle_route']

SCRIPT__r13_degrade_reason_terminal = r"""
const fs=require('fs'),path=require('path'),vm=require('vm'),ts=require('typescript')
const {loadTs}=require('./tests/load-ts.cjs')
const [kind,id,run]=process.argv.slice(1)
const snapshot=JSON.parse(fs.readFileSync(0,'utf8'))
const exports={}
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join('src','analytics','workflow.ts'),'utf8'),
 {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText,
 {exports,Date,Math,JSON,Number,Array,Object,Map,Set,String,URL,require:(id)=>{
  if(id==='./failureCodes') return loadTs(path.resolve('src/analytics/failureCodes.ts'))
  throw new Error('dep '+id)
 }})
const events=[],storage=new Map()
const tracker=new exports.WorkflowTracker({getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 ()=>true,(name,props)=>{events.push({name,props});return true})
tracker.watch(kind,id,undefined,undefined,{},false,run)
const watch=tracker.list().find(item=>item.kind===kind)
tracker.observeStudio(watch,snapshot)
tracker.observeStudio(watch,JSON.parse(JSON.stringify(snapshot)))
process.stdout.write(JSON.stringify(events.filter(e=>e.name.endsWith('_finished'))))
"""


def _capture__r13_degrade_reason_terminal(kind, watch_id, snapshot):
    if not shutil.which('node') or not (FRONTEND / 'node_modules' / 'typescript').is_dir():
        pytest.skip('frontend toolchain not installed')
    done = subprocess.run(['node', '-e', SCRIPT__r13_degrade_reason_terminal, kind, watch_id, 'run'], input=json.dumps(snapshot),
                          cwd=FRONTEND, capture_output=True, text=True, check=True, timeout=60)
    return json.loads(done.stdout)


def _terminal(reason, auto):
    plan = {'id': 'plan', 'mode': 'local', 'recommended_analysis': 'subtitle',
            'confirmed_analysis': 'subtitle', 'degrade_reason': reason}
    return {
        'plan': plan,
        'analysis': {'status': 'completed', 'outcome': 'completed', 'phase': 'production', 'run_id': 'run'},
        'generation': {'auto_start': auto, 'status': 'completed', 'route': 'subtitle'},
    }


@pytest.mark.parametrize('reason', REASONS)
@pytest.mark.parametrize('entry', ['auto', 'manual'])
def test_degrade_reason_reaches_terminal_event_from_stored_record(project, reason, entry, monkeypatch, tmp_path):
    auto = entry == 'auto'
    opened = {}
    receipt_kind = 'generation' if auto else 'production'
    seed = _terminal(reason, auto)
    seed['generation']['status'] = 'production'
    seed['analysis'] = {'status': 'running', 'phase': 'production', 'run_id': 'run', 'instance': store.INSTANCE}

    def start(data):
        data.update(seed)
        receipt = attempts.open_attempt(data, receipt_kind, run_id='run')
        attempts.bind_plan(receipt, data['plan'])  # what _inspect / confirm_project do for the attempt's own plan
        opened.update(receipt)
        if auto:
            data['generation']['attempt_id'] = opened['attempt_id']
        return data
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_MODE', 'desktop')
    monkeypatch.setenv('AUTOCLIP_BUILD_ENVIRONMENT', 'production')
    monkeypatch.setenv('AUTOCLIP_POSTHOG_KEY', 'phc_test')
    posted = _posted(monkeypatch)
    store.write(project, start(store.read(project)))
    assert posted == []  # 还没到终态
    done = store.read(project)
    done.update({k: v for k, v in _terminal(reason, auto).items() if k != 'generation'})
    done['generation'] = {**_terminal(reason, auto)['generation'], **({'attempt_id': opened['attempt_id']} if auto else {})}
    store.write(project, done)
    from backend.services.studio.terminal_outbox import wait_until_idle
    assert wait_until_idle()
    assert len(posted) == 1, posted
    assert posted[0]['properties']['degrade_reason'] == reason
    # The live run moves on (re-screen / plan rewrite); only the persisted terminal record
    # still describes run 'run'. A second write must not emit the terminal again.
    later = store.read(project)
    later['plan'] = {'id': 'plan2', 'mode': 'local', 'recommended_analysis': 'vision'}
    later['analysis'] = {'status': 'running', 'phase': 'analysis', 'run_id': 'run2', 'instance': store.INSTANCE}
    store.write(project, later)
    assert len(posted) == 1  # 结果页打开时任务已经结束：前端不再补发，后端也不再发一次
    snapshot = store.read(project)
    settled = attempts.find(snapshot, opened['attempt_id'])
    assert settled['state'] == 'completed' and settled['degrade_reason'] == reason
    receipt = next(row for row in snapshot['analysis_history'] if row['run_id'] == 'run')
    assert receipt['plan']['degrade_reason'] == reason
    kind = 'studio-generation' if auto else 'studio-production'
    assert _capture__r13_degrade_reason_terminal(kind, 'p' if auto else 'plan', snapshot) == []
