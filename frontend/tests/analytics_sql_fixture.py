"""SQLite query regression fixture, run by analytics-sql.test.cjs with frontend deps."""
import json
import re
import sqlite3
import subprocess
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


def queries(name):
    """Adapt HogQL functions/properties to SQLite, preserving query predicates."""
    sql = (ROOT / 'docs/analytics' / name).read_text(encoding='utf-8')
    sql = re.sub(r'--[^\n]*', '', sql)
    sql = re.sub(r'properties\.(\w+)', r"json_extract(properties, '$.\1')", sql)
    sql = re.sub(r'INTERVAL (\d+) DAY', r'(\1 * 86400)', sql)
    return [statement.strip() for statement in sql.split(';') if statement.strip()]


class AnalyticsSqlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use the real frontend producer, not a test copy of its outcome mapping.
        result = subprocess.run(['node', '-e', """
const path = require('node:path')
const { loadTs } = require('./frontend/tests/load-ts.cjs')
const workflow = loadTs(path.resolve('frontend/src/analytics/workflow.ts'))
const events = []
for (const kind of ['studio-export', 'studio-generation']) {
  for (const status of ['completed', 'failed']) {
    const tracker = new workflow.WorkflowTracker(
      { getItem: () => null, setItem() {}, removeItem() {} },
      () => true, (event, props) => { events.push({ event, props }); return true })
    tracker.watch(kind, 'fixture')
    tracker.observeStudio(tracker.list()[0], {
      material_origin: 'user', generation: { status },
      jobs: [{ job_id: 'fixture', status }],
    })
  }
}
process.stdout.write(JSON.stringify(events))
"""], cwd=ROOT, capture_output=True, text=True, check=True)
        cls.frontend_events = json.loads(result.stdout)

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
        self.db.execute('CREATE TABLE events (distinct_id TEXT, timestamp INTEGER, event TEXT, properties TEXT)')

    def insert(self, device, event, outcome=None, age=1, **props):
        properties = {
            'app_version': '1.5.8', 'studio_schema_version': 2, 'analytics_environment': 'production',
            'material_origin': 'user', 'runtime': 'tauri', 'outcome': outcome,
            'flow_id': device, 'artifact_id': device, 'completed_variant_count': 1,
        }
        properties.update(props)
        self.db.execute('INSERT INTO events VALUES (?, ?, ?, ?)',
                        (device, NOW - age * DAY, event, json.dumps(properties)))

    def terminals(self, age=1):
        for event in ('studio_generation_finished', 'studio_export_finished', 'social_publish_finished'):
            for outcome in ('completed', 'failed', 'partial', 'running', None):
                self.insert(f'{event}-{outcome}', event, outcome, age)
        for row in self.frontend_events:
            self.insert(f"{row['event']}-{row['props']['outcome']}", row['event'],
                        age=age, **row['props'])
        for outcome in ('success', 'error'):
            self.insert(f'social_publish_finished-{outcome}', 'social_publish_finished', outcome, age)

    def test_auth_failures_are_excluded_from_every_fixed_success_rate_denominator(self):
        for code in ('llm_auth_invalid', 'llm_not_configured', 'provider_error'):
            self.insert(code, 'studio_generation_finished', 'error', error_code=code)
        for name in ('success_rate.sql', 'TRACKING_PLAN.md'):
            sql = (ROOT / 'docs/analytics' / name).read_text(encoding='utf-8')
            predicates = re.findall(r"coalesce\(properties.error_code, ''\) NOT IN\s*\([^)]*\)", sql)
            self.assertEqual(len(predicates), 2, name)
            for predicate in predicates:
                predicate = predicate.replace('properties.error_code', "json_extract(properties, '$.error_code')")
                rows = self.db.execute('SELECT distinct_id FROM events WHERE ' + predicate).fetchall()
                self.assertEqual([row[0] for row in rows], ['provider_error'], name)

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
