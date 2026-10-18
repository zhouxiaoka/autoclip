"""R25 (replaces frontend/tests/auto-degrade-real-entry.test.cjs): degrade_reason freeze proven on the real chain.
The REAL backend writes the state (inspect_project -> _inspect -> settle_generation -> store.write -> receipt) and
GET /studio/{pid} snapshots are fed to the REAL frontend import entry + observer (helpers/auto-degrade-entry.cjs).
The observer first sees the terminal only after a re-screen replaced the plan (plan2, no reason): only a reason
frozen in the receipt can reach the event. Also #345/#347: flow_id and the counts come from the receipt."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from backend.services.studio import jobs, store
from backend.tests import attempt_flow as flow

FRONTEND = Path(__file__).resolve().parents[2] / 'frontend'
REASONS = ['frame_extract_subtitle_fallback', 'source_too_long_subtitle_route']


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    if not shutil.which('node') or not (FRONTEND / 'node_modules' / 'typescript').is_dir():
        pytest.skip('frontend toolchain not installed')
    flow.setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'ensure_project_thumbnail', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'source', lambda pid: store.directory(pid) / 'input.mp4')


def _frontend(pid, run, snapshots):
    done = subprocess.run(['node', 'tests/helpers/auto-degrade-entry.cjs'], input=json.dumps({'project_id': pid, 'run_id': run, 'snapshots': snapshots}),
                          cwd=FRONTEND, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)


@pytest.mark.parametrize('reason', REASONS)
def test_real_backend_receipt_carries_the_frozen_reason_through_the_real_entry(monkeypatch, reason):
    from backend.services.studio import planning
    plans = iter([{'mode': 'local', 'recommended_analysis': 'subtitle', 'confirmed_analysis': 'subtitle', 'preferences': {'goal': 'content'}, 'degrade_reason': reason},
                  {'mode': 'ai', 'recommended_analysis': 'visual', 'preferences': {'goal': 'content'}}])
    monkeypatch.setattr(planning, 'recommend', lambda *_a, **_k: next(plans))
    captured = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *a, **k: captured.append((fn, a)))
    posted = []

    def fake(req, timeout=0):
        posted.append(json.loads(req.data.decode()))
        raise OSError('tests do not send')

    monkeypatch.setattr('urllib.request.urlopen', fake)
    monkeypatch.setenv('AUTOCLIP_POSTHOG_KEY', 'phc_test')
    monkeypatch.setenv('AUTOCLIP_MODE', 'desktop')
    monkeypatch.setenv('AUTOCLIP_BUILD_ENVIRONMENT', 'production')
    pid = flow.new_project()
    run = flow.auto_import(pid)
    snapshots = [flow.workspace(pid)]
    fn, args = captured.pop(0)
    fn(*args)  # real _inspect: plan written, attempt bound to it, production starts (_auto_generate not run)
    captured.clear()
    snapshots.append(flow.workspace(pid))
    flow.render_outcome(pid, {'a': ('completed', None, None), 'b': ('completed', None, None)})
    receipt = flow.receipts(pid)[0]
    # re-screen before the observer saw the terminal: plan2 has no reason, a new manual screening replaces the plan
    jobs.inspect_project(pid, flow.MANUAL)
    fn, args = captured.pop(0)
    fn(*args)
    late = flow.workspace(pid)
    assert 'degrade_reason' not in late['plan'] and late['plan']['id'] != receipt.get('plan_id')
    late['output_variants'] = [late['output_variants'][0]]  # the live workspace moved on (one variant left)
    snapshots += [late, json.loads(json.dumps(late))]
    [finished] = [body for body in posted if body['event'] == 'studio_generation_finished']
    assert [body['event'] for body in posted if body['event'] == 'studio_generation_finished'] == ['studio_generation_finished']
    events = _frontend(pid, run, snapshots)
    assert [e for e in events if e['event'] == 'studio_generation_finished'] == []
    finished = {'props': finished['properties']}
    assert finished['props']['degrade_reason'] == reason
    assert finished['props']['flow_id'] == receipt['flow_id']  # #345: the backend flow, not the browser context
    assert finished['props']['completed_variant_count'] == 2 and finished['props']['variant_count'] == 2  # #347
    assert finished['props']['recommendation_mode'] == 'local' and finished['props']['route'] == 'subtitle'
