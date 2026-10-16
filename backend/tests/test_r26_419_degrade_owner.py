"""R25 #348: the degrade_reason frozen in a receipt comes from that attempt's own plan. The automatic run goes
through the real _inspect (planning stubbed only at recommend) so the plan is bound where production writes it; a
retry whose screening fails before a new plan exists must not freeze the previous plan's reason."""
import pytest

from backend.services.studio import jobs, store
from backend.tests import attempt_flow as flow


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    flow.setup_env(tmp_path, monkeypatch)
    from backend.services.studio import planning
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'ensure_project_thumbnail', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'source', lambda pid: store.directory(pid) / 'input.mp4')
    monkeypatch.setattr(planning, 'recommend', lambda *_a, **_k: {'mode': 'local', 'recommended_analysis': 'subtitle', 'confirmed_analysis': 'subtitle',
                                                                 'preferences': {'goal': 'content'}, 'degrade_reason': 'frame_extract_subtitle_fallback'})


def _screen(pid, monkeypatch, **retry):
    captured = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *a, **k: captured.append((fn, a)))
    jobs.inspect_project(pid, flow.AUTO, **retry)
    return captured[0]


def test_348_retry_failing_before_its_plan_does_not_freeze_the_previous_reason(monkeypatch):
    pid = flow.new_project()
    fn, args = _screen(pid, monkeypatch)
    fn(*args)  # real _inspect: writes plan and starts production (submit captured)
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('failed', 'timeout', None)})
    first = flow.receipts(pid)[0]
    assert first['state'] == 'partial' and first['degrade_reason'] == 'frame_extract_subtitle_fallback'
    _screen(pid, monkeypatch, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.screening_failed(pid, 'timeout')  # the retry fails before its own plan exists; the old plan is still stored
    assert store.read(pid)['plan']['degrade_reason'] == 'frame_extract_subtitle_fallback'
    second = flow.receipts(pid)[1]
    assert second['state'] == 'failed' and 'degrade_reason' not in second


def test_m2_only_catalog_enum_reasons_are_frozen():
    from backend.services.studio import attempts
    receipt = {'attempt_id': 't-x0000000000', 'state': 'open', 'plan_id': 'p'}
    attempts.settle(receipt, 'completed', {'status': 'completed'}, plan={'id': 'p', 'degrade_reason': 'free text /Users/x'})
    assert 'degrade_reason' not in receipt
