"""R25 #342 (P1): the manual production path through the REAL entry (confirm_project -> _produce_selected), with
no run_id / phase pre-filled by the test. The worker's terminal write carries neither (store.write inherits them
from the running record), so the receipt must settle after that identity and the run telemetry are filled in:
it reaches its terminal, a retry is accepted, and the frozen receipt carries the last call's telemetry."""
import pytest

from backend.services.studio import attempts, jobs, store
from backend.tests import attempt_flow as flow


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    flow.setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *a, **k: None)
    from backend.core import llm_telemetry
    monkeypatch.setattr(llm_telemetry, 'run_snapshot', lambda _pid=None: {'provider': 'deepseek', 'llm_calls': 3, 'retry_count': 1})


def _produce(pid, monkeypatch, outcome):
    """confirm_project submits _produce_selected; run it exactly as the executor would."""
    captured = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *a, **k: captured.append((fn, a)))
    run = flow.confirm(pid, flow.awaiting_confirmation(pid), monkeypatch)
    [(fn, args)] = captured
    def content(_pid, _video):
        if outcome == 'failed':
            raise TimeoutError('upstream timed out')
        return [{'id': 'c1'}]
    monkeypatch.setattr(jobs, 'run_content', content)
    fn(*args)
    return run


@pytest.mark.parametrize('outcome', ['failed', 'completed'])
def test_342_real_manual_production_settles_the_receipt(monkeypatch, outcome):
    pid = flow.new_project()
    jobs.inspect_project(pid, flow.MANUAL)
    run = _produce(pid, monkeypatch, outcome)
    assert store.read(pid)['analysis']['run_id'] == run  # inherited by store.write, not written by the worker
    [receipt] = flow.receipts(pid)
    assert receipt['state'] == outcome and receipt['run_id'] == run
    assert receipt['summary'].get('llm_calls') == 3 and receipt['summary'].get('provider') == 'deepseek'


def test_342_real_manual_failure_can_be_retried(monkeypatch):
    pid = flow.new_project()
    jobs.inspect_project(pid, flow.MANUAL)
    _produce(pid, monkeypatch, 'failed')
    first = flow.receipts(pid)[0]
    jobs.inspect_project(pid, flow.MANUAL, retry={'key': 'm1', 'parent_attempt_id': first['attempt_id']})
    assert flow.receipts(pid)[1]['retry_of'] == first['attempt_id']
