"""The ONE ClickHouse/HogQL -> DuckDB adapter for docs/analytics/success_rate.sql (#229).
Syntax only, no semantic change. Every SQL test reads the repo file through this module."""
import re
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
SQL = (ROOT / 'docs/analytics/success_rate.sql').read_text(encoding='utf-8')
PROPS = ('attempt_id', 'flow_id', 'retry_of', 'outcome', 'error_code', 'upstream_error_type', 'failure_stage',
         'app_version', 'analytics_environment', 'runtime', 'provider', 'attempt_sequence')
COHORT = 641509
# release_1_5_7 is the fixture clock (DAY in the success-rate tests), not a production publish time.
# The SQL file keeps the {release_1_5_7} token; callers overlay their own window when events are earlier.
PARAMS = {
    'date_from': "'2026-10-09 00:00:00'",
    'date_to': "'2026-10-16 00:00:00'",
    'internal_cohort_id': str(COHORT),
    'release_1_5_7': "'2026-10-12 08:00:00'",
}


def statements(sql=SQL, params=None):
    body = re.sub(r'--[^\n]*', '', sql)
    merged = dict(PARAMS)
    if params:
        merged.update(params)
    for key, value in merged.items():
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
    sql = _rewrite_calls(sql, 'toInt', lambda a: f'TRY_CAST({a[0]} AS BIGINT)')  # HogQL toInt: NULL when not a number
    sql = _rewrite_calls(sql, 'ifNull', lambda a: f'coalesce({a[0]}, {a[1]})')
    sql = sql.replace('count()', 'count(*)')
    sql = re.sub(r'person_id NOT IN COHORT (\d+)', r'person_id NOT IN (SELECT person_id FROM cohort_people WHERE cohort_id = \1)', sql)
    return sql


def figure(n, sql=SQL, params=None):
    """Statement of "-- 图 n" (statements are in figure order)."""
    assert f'-- 图 {n}' in sql, f'success_rate.sql has no figure {n}'
    return statements(sql, params)[n - 1]


def run_sql(sql, rows, staff=(), cohort=COHORT):
    """rows: (uuid, event, person_id, timestamp, props dict). staff: person_ids in the internal cohort."""
    con = duckdb.connect()
    struct = ', '.join(f'{name} VARCHAR' for name in PROPS)
    con.execute(f'CREATE TABLE events (uuid VARCHAR, event VARCHAR, person_id VARCHAR, timestamp TIMESTAMP, properties STRUCT({struct}))')
    for uuid, event, person, ts, props in rows:
        con.execute('INSERT INTO events VALUES (?, ?, ?, ?, ?)', [uuid, event, person, ts,
                    {k: None if props.get(k) is None else str(props[k]) for k in PROPS}])
    con.execute('CREATE TABLE cohort_people (cohort_id INTEGER, person_id VARCHAR)')
    for person in staff:
        con.execute('INSERT INTO cohort_people VALUES (?, ?)', [cohort, person])
    cursor = con.execute(to_duckdb(sql))
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]
