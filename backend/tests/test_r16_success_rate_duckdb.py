"""R16 #46/#47: execute docs/analytics/success_rate.sql for real (DuckDB with a small ClickHouse/HogQL
shim) on synthetic events. Expected numbers are computed by hand below; mutations of the per-flow
definition (last -> any success, last -> first, ignoring retry_of) must change them."""
import re
from datetime import datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from backend.tests.success_rate_sql import COHORT, PARAMS, SQL, run_sql, statements, to_duckdb  # noqa: F401 (R23 #229: one adapter)

ROOT = Path(__file__).resolve().parents[2]
DAY = datetime(2026, 10, 12, 8, 0, 0)


class Events:
    def __init__(self):
        self.rows, self.n = [], 0

    def add(self, person, minutes, event='studio_generation_finished', env='production', runtime='desktop',
            app_version='1.5.8', **props):
        self.n += 1
        # R25 #346: v4 rows carry the backend receipt sequence (here: insertion order); legacy=True drops it.
        if props.pop('legacy', False):
            props.pop('attempt_sequence', None)
        else:
            props.setdefault('attempt_sequence', str(self.n))
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
    'last->any success': ("argMax(o, (seq, ts)) AS fo", "if(max(o = 'success'), 'success', 'error') AS fo"),
    'last->first': ("argMax(o, (seq, ts)) AS fo", "argMin(o, (seq, ts)) AS fo"),
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
    old = "argMax(o, (seq, ts)) AS fo"
    assert old in stmt
    rows = {r['app_version']: r for r in fixture().run(stmt.replace(old, "if(max(o = 'success'), 'success', 'error') AS fo"))}
    assert rows['1.5.8']['flow_ok'] != 2


# --- R18 #70/#71: every v4 exclusion rule and every forced product failure, mutated one by one ---

import json  # noqa: E402

V4 = json.loads((ROOT / 'docs/analytics/event_catalog.json').read_text(encoding='utf-8'))['attribution']['success_rate_v4']
# R19 #104: every forced product failure also in upstream_error_type form.
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
    one(outcome='canceled')                                             # ... US spelling alias (R20 #140)
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
    assert set(V4['product_extra_excluded_error_codes']) == {'connection', 'source_too_short', 'source_no_audio', 'source_unreadable', 'source_blocked'}
    assert set(V4['product_failure_codes']) == {'whisper_not_installed', 'service_restarted', 'model_not_found', 'bad_endpoint'}


def test_every_exclusion_and_product_failure_lands_in_the_right_denominator():
    # 2 ok; hard (N_HARD) out of both; user_x (N_X) only out of product; forced failures (N_PF) in both.
    assert _excl() == EXPECTED_EXCL
    assert (N_HARD, N_X, N_PF) == (12, 5, 8)
    # R19 #104: 8 forced product failures -> all/product denominators 15/10.
    assert (EXPECTED_EXCL['q_all'], EXPECTED_EXCL['q_prod']) == (15, 10)
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
           # R20 #140: dropping the US-spelling alias must be caught in every figure.
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


# --- R19 #103: the same rule mutations must be caught in every figure that carries the rules (1, 2, 3, 5),
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
    assert len(rows) == 1 and rows[0]['app_version'] == '1.5.8'
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


# --- R20 #142: an empty denominator yields NULL, never NaN/inf --------------------------------------

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


# --- R21 #203: the overall (全量) denominators can be 0 too: NULL, never 0% -------------------------

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
    """R21 #203 mutation (survived R21): ifNull(<overall rate>, 0) must fail the NULL regression."""
    pattern = re.compile(r'round\(([^\n]*?)\) AS ' + column + r'\b')
    mutated = pattern.sub(lambda m: f'ifNull(round({m.group(1)}), 0) AS {column}', SQL)
    assert mutated != SQL
    with pytest.raises(AssertionError):
        _assert_all_excluded_is_null(statements(mutated))


# --- R25 #346: the flow's last attempt is the backend sequence, not the observation time ---

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
    assert stmt.count(', (seq, ts))') >= 3
    rows = _out_of_order().run(stmt.replace(', (seq, ts))', ', ts)'))
    assert rows[0]['flow_ok'] == 0  # the old argMax(o, ts): 100% -> 0%


def _legacy(e, person, base=0):
    """pre-#419 rows: no attempt_sequence. One success flow and one fail -> retry-success flow."""
    e.add(person, base, attempt_id=person + 'l1', flow_id='F' + person + '1', outcome='completed', legacy=True)
    e.add(person, base + 1, attempt_id=person + 'l2', flow_id='F' + person + '2', outcome='error', error_code='timeout', legacy=True)
    e.add(person, base + 2, attempt_id=person + 'l3', flow_id='F' + person + '3', retry_of=person + 'l2', outcome='completed', legacy=True)


@pytest.mark.parametrize('figure', [0, 4])
def test_346_legacy_only_has_empty_denominators_and_counts_unknown(figure):
    e = Events(); _legacy(e, 'L')
    [row] = e.run(statements()[figure])
    assert (row['ok'], row['q_all'], row['q_prod'], row['flow_ok'] or 0, row['fq_all'] or 0, row['unknown_attempts']) == (0, 0, 0, 0, 0, 3)
    assert row['overall_attempt_rate'] is None and row['product_attempt_rate'] is None and row['overall_flow_rate'] is None


@pytest.mark.parametrize('figure', [0, 4])
def test_346_mixed_counts_only_rows_with_a_sequence(figure):
    e = Events(); _legacy(e, 'L')
    e.add('N', 0, attempt_id='n1', flow_id='FN', outcome='error', error_code='timeout')
    e.add('N', 1, attempt_id='n2', flow_id='FN', retry_of='n1', outcome='completed')
    [row] = e.run(statements()[figure])
    assert (row['ok'], row['q_all'], row['flow_ok'], row['fq_all'], row['unknown_attempts']) == (1, 2, 1, 1, 3)
    assert row['overall_attempt_rate'] == 0.5 and row['overall_flow_rate'] == 1.0


LEGACY_MUTATIONS = {
    'legacy counted in denominators': ('(seq IS NOT NULL) AS known', 'TRUE AS known'),
    'legacy counted as failures': ("(known AND (o = 'success' OR NOT user_hard)) AS qual_all", "(NOT known OR o = 'success' OR NOT user_hard) AS qual_all"),
    'legacy successes in the numerator': ("countIf(o = 'success' AND known) AS ok", "countIf(o = 'success') AS ok"),
    'legacy rows in flows': ('FROM c WHERE known GROUP BY chain_fid', 'FROM c GROUP BY chain_fid'),
    'legacy ordered as 0 (old rule)': ('max(toInt(properties.attempt_sequence)) AS seq', 'max(ifNull(toInt(properties.attempt_sequence), 0)) AS seq'),
}


@pytest.mark.parametrize('figure', [0, 4])
@pytest.mark.parametrize('name', LEGACY_MUTATIONS)
def test_346_legacy_rule_mutations_are_caught(figure, name):
    old, new = LEGACY_MUTATIONS[name]
    stmt = statements()[figure]
    assert old in stmt, name
    mutated = stmt.replace(old, new)
    def run(e):
        return e.run(mutated)[0]
    only = Events(); _legacy(only, 'L')
    mixed = Events(); _legacy(mixed, 'L')
    mixed.add('N', 0, attempt_id='n1', flow_id='FN', outcome='error', error_code='timeout')
    mixed.add('N', 1, attempt_id='n2', flow_id='FN', retry_of='n1', outcome='completed')
    a, b = run(only), run(mixed)
    got = ((a['ok'], a['q_all'], a['fq_all'] or 0, a['unknown_attempts']), (b['ok'], b['q_all'], b['flow_ok'], b['fq_all'], b['unknown_attempts']))
    assert got != ((0, 0, 0, 3), (1, 2, 1, 1, 3)), name
