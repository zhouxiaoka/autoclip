"""R29b #419 (Dong): an appended platform round is its own flow; its terminal carries trigger=append_platform
(registered in the catalog and TRACKING_PLAN) and its duration_ms runs from THIS attempt's start, not from the
generation's first created_at. Real attempts.reconcile / event_catalog.validate_event."""
import json
from pathlib import Path

from backend.core import event_catalog
from backend.services.studio import attempts

ROOT = Path(__file__).resolve().parents[2]


def _appended_round(trigger='append_platform'):
    return {'generation': {'status': 'completed', 'attempt_id': 't-append', 'created_at': '2026-10-17T00:00:00Z',
                           'finished_at': '2026-10-17T00:10:00Z'},
            'jobs': [], 'analysis': {},
            'output_variants': [{'id': 'old', 'status': 'completed', 'produced_by_attempt': 't-first'},
                                {'id': 'new', 'status': 'completed', 'produced_by_attempt': 't-append'}],
            'attempts': [{'attempt_id': 't-first', 'kind': 'generation', 'trigger': 'initial', 'state': 'completed', 'sequence': 1,
                          'created_at': '2026-10-17T00:00:00Z'},
                         {'attempt_id': 't-append', 'kind': 'generation', 'trigger': trigger, 'state': 'open', 'sequence': 2,
                          'run_id': 'r-2', 'created_at': '2026-10-17T00:08:20Z'}]}


def test_r29b_append_round_duration_excludes_earlier_rounds():
    data = _appended_round()
    attempts.reconcile(data, '2026-10-17T00:10:00Z')
    receipt = attempts.find(data, 't-append')
    assert receipt['state'] == 'completed'
    assert receipt['summary']['duration_ms'] == 100_000   # 00:08:20 -> 00:10:00, not 600_000 from the first round


def test_r29b_no_attempt_start_falls_back_to_generation_created_at():
    data = _appended_round()
    data['attempts'][1].pop('created_at')
    attempts.reconcile(data, '2026-10-17T00:10:00Z')
    assert attempts.find(data, 't-append')['summary']['duration_ms'] == 600_000


def test_r29b_trigger_is_registered_on_the_generation_terminal():
    for catalog_path in ('backend/core/event_catalog.json', 'docs/analytics/event_catalog.json'):
        catalog = json.loads((ROOT / catalog_path).read_text(encoding='utf-8'))
        spec = catalog['events']['studio_generation_finished']
        assert spec['enums'].get('trigger') == 'attempt_trigger', catalog_path
        assert 'append_platform' in catalog['enums']['attempt_trigger'], catalog_path
        assert 'trigger' in spec['optional_properties'], catalog_path
    ok = {'outcome': 'success', 'trigger': 'append_platform'}
    assert event_catalog.validate_event('studio_generation_finished', ok) == []
    assert event_catalog.validate_event('studio_generation_finished', {'outcome': 'success', 'trigger': 'auto'})


def test_r29b_tracking_plan_lists_trigger_on_the_generation_terminal():
    plan = (ROOT / 'docs/analytics/TRACKING_PLAN.md').read_text(encoding='utf-8')
    [row] = [line for line in plan.splitlines() if line.startswith('| `studio_generation_finished` |')]
    assert '`trigger`' in row and 'append_platform' in row
