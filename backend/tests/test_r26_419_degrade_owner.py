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


def test_363_screening_failure_before_its_plan_does_not_freeze_the_previous_outputs(monkeypatch):
    pid = flow.new_project()
    fn, args = _screen(pid, monkeypatch)
    fn(*args)
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('failed', 'timeout', None)})
    first = flow.receipts(pid)[0]
    assert first['summary']['variant_count'] == 2 and first['summary']['completed_variant_count'] == 1
    _screen(pid, monkeypatch, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.screening_failed(pid, 'timeout')  # the previous run's two outputs are still in the workspace
    second = flow.receipts(pid)[1]
    for key in ('variant_count', 'completed_variant_count', 'failed_variant_count'):
        assert key not in second['summary'], key
    assert second['summary']['platform_count'] == 2  # request fields stay


def test_364_variant_retry_keeps_the_source_plans_degrade_reason(monkeypatch):
    pid = flow.new_project()
    fn, args = _screen(pid, monkeypatch)
    fn(*args)
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('failed', 'timeout', None)})
    flow.retry_variant(pid, 'bad', 'v1')
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('completed', None, None)})
    retried = flow.receipts(pid)[1]
    assert retried['state'] == 'completed' and retried['degrade_reason'] == 'frame_extract_subtitle_fallback'
    assert retried['summary']['recommendation_mode'] == 'local'


def test_364_variant_retry_after_a_rescreen_still_reports_the_source_plan(monkeypatch):
    pid = flow.new_project()
    fn, args = _screen(pid, monkeypatch)
    fn(*args)
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('failed', 'timeout', None)})
    flow.store.change(pid, lambda d: d.update(plan={'id': 'plan-other', 'mode': 'ai'}))  # the workspace plan moved on
    flow.retry_variant(pid, 'bad', 'v1')
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('completed', None, None)})
    retried = flow.receipts(pid)[1]
    assert retried['degrade_reason'] == 'frame_extract_subtitle_fallback' and retried['summary']['recommendation_mode'] == 'local'


def test_365_manual_confirm_binds_the_confirmed_plan_without_test_prebinding(monkeypatch):
    pid = flow.new_project()
    jobs.inspect_project(pid, flow.MANUAL)
    plan_id = flow.awaiting_confirmation(pid)
    store.change(pid, lambda d: d['plan'].update(degrade_reason='source_too_long_subtitle_route', mode='local'))
    flow.confirm(pid, plan_id, monkeypatch)  # the real confirm_project; nothing bound by the test
    flow.production_finished(pid, 'completed')
    [receipt] = flow.receipts(pid)
    assert receipt['state'] == 'completed' and receipt['degrade_reason'] == 'source_too_long_subtitle_route'
