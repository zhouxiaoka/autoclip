"""R30 #419 I490, the real chain: the real append entry point (jobs.append_platform_variants through the real store)
-> its receipt -> the real frontend appendPlatforms + tracker -> terminal events -> docs/analytics/success_rate.sql.
The first round succeeded, the append failed: two flows, one successful (1/2), the old terminal is not re-sent."""
import json
import shutil
import subprocess

import pytest

from backend.tests import attempt_flow as flow
from backend.tests.test_r25_419_receipt_chain_duckdb import IN_CI, ROOT, WINDOW, _rows
from backend.services.studio import jobs, store

if not IN_CI:
    pytest.importorskip('duckdb')
from backend.tests.success_rate_sql import SQL, figure, run_sql  # noqa: E402


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    submitted = flow.setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(jobs, 'source', lambda _pid: 'video.mp4')
    monkeypatch.setattr(jobs, '_source_has_burned_subtitles', lambda *_: False)
    monkeypatch.setattr(jobs, '_eligible_for_platform', lambda *_: True)
    monkeypatch.setattr(jobs, '_fit_platform_limit', lambda _p, value, _s: (value, None))
    monkeypatch.setattr(jobs, '_apply_framing', lambda _p, value, *_: (value, 'full_frame'))
    monkeypatch.setattr(jobs, '_apply_packaging', lambda _p, value, *_: value)
    monkeypatch.setattr(jobs, '_posts_for', lambda *_: {})
    return submitted


def _node(payload):
    node = shutil.which('node')
    if not node or not (ROOT / 'frontend' / 'node_modules').exists():
        if IN_CI:
            pytest.fail('node + frontend deps are installed in CI; refusing to skip the append chain test')
        pytest.skip('node + frontend deps required')
    out = subprocess.run([node, 'tests/helpers/append-flow.cjs'], cwd=ROOT / 'frontend', input=json.dumps(payload),
                         capture_output=True, text=True, timeout=120, check=True)
    return json.loads(out.stdout)


def _first_round_succeeded(pid):
    flow.render_outcome(pid, {'ok': ('completed', None, None)})
    def scenes(data):  # the moment the output was cut from (render_outcome leaves drafts empty)
        data['drafts'][0]['scenes'] = [{'id': 's0', 'label': 'x', 'start': 0.0, 'end': 30.0}]
    store.change(pid, scenes)


def _append_failed(pid, ids):
    def mutate(data):
        for v in data['output_variants']:
            if v['id'] in ids:
                v.update(status='failed', error_code='timeout')
        store.settle_generation(data)
    store.change(pid, mutate)


def _chain():
    pid = flow.new_project()
    run = flow.auto_import(pid)
    _first_round_succeeded(pid)
    first = flow.workspace(pid)
    response = json.loads(json.dumps(jobs.append_platform_variants(pid, ['bilibili'], {'outro_enabled': False})))
    _append_failed(pid, {v['id'] for v in response['variants']})
    result = _node({'pid': pid, 'import_run': run, 'first': first, 'append_response': response, 'platforms': ['bilibili'],
                    'final': flow.workspace(pid)})
    return result, flow.receipts(pid)


def test_i490_append_terminal_is_emitted_once_from_its_receipt():
    result, receipts = _chain()
    [post] = result['posts']
    assert post['url'] == '/studio/p1/platforms'
    gen = [e['props'] for e in result['events'] if e['event'] == 'studio_generation_finished']
    assert [g['attempt_id'] for g in gen] == [r['attempt_id'] for r in receipts]       # one each, old one not re-sent
    assert [g['outcome'] for g in gen] == ['success', 'error'] and gen[1]['trigger'] == 'append_platform'
    assert gen[1]['flow_id'] != gen[0]['flow_id'] and 'retry_of' not in gen[1]


@pytest.mark.parametrize('fig', [1, 5])
def test_i490_success_then_failed_append_is_one_of_two(fig):
    result, _ = _chain()
    [row] = run_sql(figure(fig, SQL, WINDOW), _rows(result['events']))
    assert (row['flow_ok'], row['fq_all']) == (1, 2), row
    assert row['overall_flow_rate'] == 0.5
