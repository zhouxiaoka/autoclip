"""SQLite query regression fixture, run by analytics-sql.test.cjs with frontend deps."""
import json
import re
import sqlite3
import subprocess
import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DAY = 86400
NOW = 30 * DAY


class Uniq:
    def __init__(self):
        self.values = set()

    def step(self, value, condition=True):
        if condition and value is not None:
            self.values.add(value)

    def finalize(self):
        return len(self.values)


def queries(name, internal=('internal',)):
    """Adapt HogQL functions/properties to SQLite, preserving query predicates.

    ``internal`` is the content of the internal cohort ({internal_cohort_id}); () = empty cohort."""
    sql = (ROOT / 'docs/analytics' / name).read_text(encoding='utf-8')
    sql = re.sub(r'--[^\n]*', '', sql)
    sql = re.sub(r'properties\.(\w+)', r"json_extract(properties, '$.\1')", sql)
    sql = re.sub(r'INTERVAL (\d+) DAY', r'(\1 * 86400)', sql)
    # v4 fixed UTC window + internal cohort parameters; the fixture window ends at NOW.
    sql = sql.replace("toDateTime({date_from}, 'UTC')", '(now() - 7 * 86400)')
    sql = sql.replace("toDateTime({date_to}, 'UTC')", '(now() + 1)')
    members = ', '.join(f"'{person}'" for person in internal)
    sql = sql.replace('person_id NOT IN COHORT {internal_cohort_id}',
                      f'person_id NOT IN ({members})' if members else '1 = 1')
    return [statement.strip() for statement in sql.split(';') if statement.strip()]


def generation_terminals():
    """The two success-rate generation rows, from the backend producer.

    Frontend CI Python has no backend dependencies. Stub ``backend.services`` so
    importing the studio package does not load ``services/__init__.py``.
    """
    sys.path.insert(0, str(ROOT))
    import backend  # noqa: F401 - real package so provider presets resolve
    if 'backend.services' not in sys.modules:
        stub = types.ModuleType('backend.services')
        stub.__path__ = [str(ROOT / 'backend' / 'services')]
        stub.__package__ = 'backend.services'
        sys.modules['backend.services'] = stub
    from backend.services.studio.attempts import _terminal_event
    events = []
    for status in ('completed', 'failed'):
        receipt = {
            'kind': 'generation', 'state': status, 'attempt_id': 't-fixture00000000',
            'flow_id': 't-flow0000000000', 'sequence': 1, 'summary': {},
        }
        if status == 'failed':
            receipt.update(error_code='unexpected', failure_stage='render')
        posted = _terminal_event(receipt)
        events.append({'event': posted['event'], 'props': posted['properties']})
    return events


class AnalyticsSqlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Export terminals still use the real frontend observer. Generation terminals
        # are posted by the backend; this process has no store, so the receipt is the
        # settled document and the event is attempts._terminal_event.
        result = subprocess.run(['node', '-e', """
const path = require('node:path')
const { loadTs } = require('./frontend/tests/load-ts.cjs')
const workflow = loadTs(path.resolve('frontend/src/analytics/workflow.ts'))
const events = []
for (const status of ['completed', 'failed']) {
  const tracker = new workflow.WorkflowTracker(
    { getItem: () => null, setItem() {}, removeItem() {} },
    () => true, (event, props) => { events.push({ event, props }); return true })
  tracker.watch('studio-export', 'fixture')
  tracker.observeStudio(tracker.list()[0], {
    material_origin: 'user', generation: { status, attempt_id: 't-fixture00000000' },
    jobs: [{ job_id: 'fixture', status }],
  })
}
process.stdout.write(JSON.stringify(events))
"""], cwd=ROOT, capture_output=True, text=True, check=True)
        cls.frontend_events = json.loads(result.stdout) + generation_terminals()

    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        self.db.create_function('now', 0, lambda: NOW)
        self.db.create_function('toString', 1, lambda value: None if value is None else str(value))
        self.db.create_function('toFloat', 1, lambda value: None if value is None else float(value))
        self.db.create_function('tuple', -1, lambda *values: json.dumps(values))
        self.db.create_aggregate('uniq', 1, Uniq)
        self.db.create_aggregate('uniqIf', 2, Uniq)
        self.db.execute('CREATE TABLE events (distinct_id TEXT, timestamp INTEGER, event TEXT, properties TEXT, person_id TEXT)')

    def insert(self, device, event, outcome=None, age=1, person=None, **props):
        properties = {
            'app_version': '1.5.7', 'studio_schema_version': 2, 'analytics_environment': 'production',
            'material_origin': 'user', 'runtime': 'tauri', 'outcome': outcome,
            'flow_id': device, 'artifact_id': device, 'completed_variant_count': 1,
        }
        properties.update(props)
        self.db.execute('INSERT INTO events VALUES (?, ?, ?, ?, ?)',
                        (device, NOW - age * DAY, event, json.dumps(properties), person or device))

    def terminals(self, age=1):
        for event in ('studio_generation_finished', 'studio_export_finished', 'social_publish_finished'):
            for outcome in ('completed', 'failed', 'partial', 'running', None):
                self.insert(f'{event}-{outcome}', event, outcome, age)
        for row in self.frontend_events:
            self.insert(f"{row['event']}-{row['props']['outcome']}", row['event'],
                        age=age, **row['props'])
        for outcome in ('success', 'error'):
            self.insert(f'social_publish_finished-{outcome}', 'social_publish_finished', outcome, age)

    def test_success_rate_v4_attribution_matches_catalog_in_every_statement(self):
        sql = (ROOT / 'docs/analytics/success_rate.sql').read_text(encoding='utf-8')
        body = re.sub(r'--[^\n]*', '', sql)
        v4 = json.loads((ROOT / 'docs/analytics/event_catalog.json').read_text(encoding='utf-8'))['attribution']['success_rate_v4']
        hard = re.findall(r"OR ec IN \(([^)]*)\)\s*OR ue IN \(([^)]*)\)\) AS user_hard", body)
        extra = re.findall(r"user_hard OR ec IN \(([^)]*)\)\) AS user_x", body)
        self.assertEqual(len(hard), 4)
        self.assertEqual(len(extra), 4)
        names = lambda text: re.findall(r"'(\w+)'", text)
        for codes, upstream in hard:
            self.assertEqual(names(codes), v4['overall_excluded_error_codes'])
            self.assertEqual(names(upstream), v4['overall_excluded_upstream_types'])
        for codes in extra:
            self.assertEqual(names(codes), v4['product_extra_excluded_error_codes'])
        excluded = set(v4['overall_excluded_error_codes'] + v4['overall_excluded_upstream_types'] + v4['product_extra_excluded_error_codes'])
        self.assertFalse(excluded & set(v4['product_failure_codes']))
        # partial is never success; attempts dedupe on attempt_id; people are person_id; fixed window; internal cohort.
        self.assertEqual(body.count("o_raw IN ('completed', 'success'), 'success', o_raw = 'partial', 'partial'"), 4)
        self.assertEqual(body.count('toString(coalesce(properties.attempt_id, toString(uuid))) AS aid'), 5)  # figures 1/2/3/5 + figure 6 (degrade_reason)
        self.assertIn('argMax(person_id, timestamp) AS pid', body)
        self.assertNotIn('distinct_id', body)
        self.assertNotIn('now()', body)
        self.assertEqual(body.count("timestamp >= toDateTime({date_from}, 'UTC')"), 6)
        self.assertEqual(body.count('person_id NOT IN COHORT {internal_cohort_id}'), 6)
        self.assertEqual(body.count('{release_1_5_7}'), 6)
        self.assertNotIn("SELECT '1.5.7' AS app_version, '20", body)
        self.assertIn('partial_delivery_rate', body)
        # per-flow = last attempt of the retry chain (retry_of -> root flow_id).
        self.assertEqual(v4['flow_definition']['retry_link_property'], 'retry_of')
        self.assertIn("argMax(coalesce(toString(properties.retry_of), ''), timestamp) AS rof", body)
        hops = v4['flow_definition']['max_retry_hops']
        for i in range(1, hops + 1):
            self.assertIn(f'LEFT JOIN base p{i} ON ', body)
        self.assertNotIn(f'LEFT JOIN base p{hops + 1} ', body)
        # last attempt by the backend sequence (observation time breaks ties only).
        self.assertEqual(v4['flow_definition']['order_property'], 'attempt_sequence')
        self.assertIn('max(toInt(properties.attempt_sequence)) AS seq', body)
        self.assertEqual(body.count('(ifNull(seq, 0), leaf, ts) AS ord'), 2)  # then the retry_of chain end
        self.assertIn('SELECT chain_fid AS fid, max(ts) AS fts, argMax(o, ord) AS fo', body)
        self.assertEqual(body.count('AS unknown_flows'), 2)
        for rate in ('overall_attempt_rate', 'product_attempt_rate', 'overall_flow_rate', 'product_flow_rate'):
            self.assertIn(rate, body)

    def test_production_results_excludes_internal_people_and_counts_person_id(self):
        self.insert('dev-a', 'studio_generation_finished', 'success', person='p1')
        self.insert('dev-b', 'studio_generation_finished', 'success', person='p1')
        self.insert('dev-c', 'studio_generation_finished', 'success', person='internal')
        self.insert('dev-old', 'studio_generation_finished', 'success', age=8, person='p2')
        rows = self.db.execute(queries('production_results.sql')[0]).fetchall()
        self.assertEqual([(row['devices'], row['people']) for row in rows], [(2, 1)])

    def test_frontend_fixture_emits_success_and_error(self):
        self.assertEqual({(row['event'], row['props']['outcome']) for row in self.frontend_events}, {
            (event, outcome) for event in ('studio_generation_finished', 'studio_export_finished')
            for outcome in ('success', 'error')})

    def test_delivery_accepts_both_success_schemas_without_counting_failures(self):
        self.terminals()
        for name, index in (('production_results.sql', 0), ('studio_delivery.sql', 0)):
            with self.subTest(query=name):
                rows = self.db.execute(queries(name)[index]).fetchall()
                counts = {}
                for row in rows:
                    counts[row['event']] = counts.get(row['event'], 0) + row['devices']
                expected = {'studio_export_finished': 2, 'social_publish_finished': 2}
                if name == 'production_results.sql':
                    expected['studio_generation_finished'] = 3  # Both successes plus partial.
                self.assertEqual(counts, expected)

    def test_failure_summary_preserves_both_terminal_schemas(self):
        self.terminals()
        rows = self.db.execute(queries('production_results.sql')[1]).fetchall()
        self.assertEqual({(row['event'], row['outcome'], row['events']) for row in rows}, {
            (event, outcome, 1)
            for event in ('studio_generation_finished', 'studio_export_finished', 'social_publish_finished')
            for outcome in ('completed', 'failed', 'success', 'error', 'partial', 'running', None)
        })

    def test_sample_followup_accepts_both_success_schemas_and_preserves_partial_rule(self):
        self.terminals(age=8)
        devices = [row[0] for row in self.db.execute('SELECT distinct_id FROM events')]
        self.insert('empty-partial', 'studio_generation_finished', 'partial', 8, completed_variant_count=0)
        devices.append('empty-partial')
        for device in devices:
            self.insert(device, 'example_project_viewed', age=9, experience_schema_version=1)
        for name, index, expected in (('production_results.sql', 2, 5), ('sample_to_real.sql', 0, 2)):
            with self.subTest(query=name):
                row = self.db.execute(queries(name)[index]).fetchone()
                self.assertEqual(row['observed_sample_devices'], len(devices))
                self.assertEqual(row['real_render_within_7d_devices'], expected)

    def test_sample_followup_excludes_internal_renders_and_empty_cohort_changes_nothing(self):
        # a device seen on the sample as a normal person, whose real render is by an internal person.
        self.insert('shared', 'example_project_viewed', age=9, person='p1', experience_schema_version=1)
        self.insert('shared', 'studio_export_finished', 'success', age=8, person='internal')
        self.insert('user', 'example_project_viewed', age=9, person='p2', experience_schema_version=1)
        self.insert('user', 'studio_export_finished', 'success', age=8, person='p2')
        rows = lambda internal: dict(self.db.execute(queries('production_results.sql', internal)[2]).fetchone())
        self.assertEqual(rows(('internal',)), {'observed_sample_devices': 2, 'real_render_within_7d_devices': 1})
        # Cohort 641509 is empty today: the exclusion is wired but the result equals the pre-#141 query (2).
        empty = rows(())
        self.assertEqual(empty, {'observed_sample_devices': 2, 'real_render_within_7d_devices': 2})

    def test_production_filters_still_exclude_validation_and_old_schema_events(self):
        for outcome in ('completed', 'success'):
            for props in ({'analytics_environment': 'validation'}, {'studio_schema_version': 1}):
                self.insert('excluded', 'studio_export_finished', outcome, **props)
        for name, index in (('production_results.sql', 0), ('production_results.sql', 1),
                            ('studio_delivery.sql', 0)):
            with self.subTest(query=name, index=index):
                self.assertEqual(self.db.execute(queries(name)[index]).fetchall(), [])


if __name__ == '__main__':
    unittest.main()
