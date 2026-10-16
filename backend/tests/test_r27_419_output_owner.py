"""R27 #376/#377 (design: output ownership is stored, not inferred). Every output variant records the attempt
that produced it (produced_by_attempt) and that attempt's plan (produced_by_plan) when it is created. A receipt's
summary counts only outputs owned by this attempt (or, for a variant retry, by the attempt whose outputs it
re-renders); a variant retry takes its plan from the retried variant itself, never from "the latest failure".
Real _inspect / retry_variant / store.write; only planning.recommend and the executor are stubbed."""
import pytest

from backend.services.studio import attempts, jobs, store
from backend.tests import attempt_flow as flow

PLAN_A = {'mode': 'local', 'recommended_analysis': 'subtitle', 'confirmed_analysis': 'subtitle',
          'preferences': {'goal': 'content'}, 'degrade_reason': 'frame_extract_subtitle_fallback'}
PLAN_B = {'mode': 'ai', 'recommended_analysis': 'visual', 'confirmed_analysis': 'visual', 'preferences': {'goal': 'content'}}
COUNTS = ('variant_count', 'completed_variant_count', 'failed_variant_count')


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    flow.setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'ensure_project_thumbnail', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'source', lambda pid: store.directory(pid) / 'input.mp4')


def _screen_and_plan(pid, monkeypatch, plan, **retry):
    """Real inspect_project + real _inspect: the plan is written and bound where production starts."""
    from backend.services.studio import planning
    monkeypatch.setattr(planning, 'recommend', lambda *_a, **_k: dict(plan))
    captured = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *a, **k: captured.append((fn, a)))
    jobs.inspect_project(pid, flow.AUTO, **retry)
    fn, args = captured[0]
    fn(*args)  # writes the plan, binds it, submits _auto_generate (captured, not run)
    return store.read(pid)['plan']['id']


def _plan_a_partial(pid, monkeypatch):
    plan_a = _screen_and_plan(pid, monkeypatch, PLAN_A)
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('failed', 'timeout', None)})
    first = flow.receipts(pid)[0]
    assert first['state'] == 'partial' and first['summary']['variant_count'] == 2
    return plan_a, first


def test_376_outputs_carry_the_attempt_and_plan_that_produced_them(monkeypatch):
    pid = flow.new_project()
    plan_a, first = _plan_a_partial(pid, monkeypatch)
    for variant in store.read(pid)['output_variants']:
        assert (variant['produced_by_attempt'], variant['produced_by_plan']) == (first['attempt_id'], plan_a)


def test_376_new_plan_failing_before_its_outputs_does_not_freeze_the_previous_outputs(monkeypatch):
    """Dong/sol/astra: a re-screen builds and binds a new plan, then fails in production before any output -
    the receipt used to freeze the previous run's variant=2/completed=1/failed=1 because it had a plan_id."""
    pid = flow.new_project()
    _plan_a, first = _plan_a_partial(pid, monkeypatch)
    plan_b = _screen_and_plan(pid, monkeypatch, PLAN_B, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.production_failed_before_outputs(pid)
    second = flow.receipts(pid)[1]
    assert second['plan_id'] == plan_b and second['state'] == 'failed'   # it HAD its own plan
    assert len(store.read(pid)['output_variants']) == 2                  # plan A's outputs are still in the workspace
    for key in COUNTS:
        assert key not in second['summary'], key
    assert second['summary']['platform_count'] == 2                       # request fields stay


def _rescreen_fails_then_retry_a_variant(pid, monkeypatch):
    """Degraded plan A partially completes -> whole-flow retry (plan B) fails -> 「重试这条」 on A's failed output."""
    plan_a, first = _plan_a_partial(pid, monkeypatch)
    _screen_and_plan(pid, monkeypatch, PLAN_B, retry={'key': 'r1', 'parent_attempt_id': first['attempt_id']})
    flow.production_failed_before_outputs(pid)
    flow.retry_variant(pid, 'bad', 'v1')
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('completed', None, None)})
    return plan_a, first, flow.receipts(pid)[2]


def test_377_variant_retry_after_a_failed_rescreen_belongs_to_the_plan_that_produced_the_output(monkeypatch):
    pid = flow.new_project()
    plan_a, first, retried = _rescreen_fails_then_retry_a_variant(pid, monkeypatch)
    assert retried['trigger'] == 'variant_retry' and retried['state'] == 'completed'
    assert retried['plan_id'] == plan_a                     # not plan B, not dropped (m3 drops it)
    assert retried['degrade_reason'] == 'frame_extract_subtitle_fallback'
    assert (retried['summary']['recommendation_mode'], retried['summary']['analysis_mode']) == ('local', 'subtitle')


def test_377_variant_retry_counts_the_retried_outputs(monkeypatch):
    pid = flow.new_project()
    _plan_a, _first, retried = _rescreen_fails_then_retry_a_variant(pid, monkeypatch)
    assert (retried['summary']['variant_count'], retried['summary']['completed_variant_count'],
            retried['summary']['failed_variant_count']) == (2, 2, 0)


def test_377_variant_retry_counts_do_not_depend_on_the_plan_id(monkeypatch):
    """The direct variant retry (no re-screen in between): its output counts come from output ownership, so the
    plan id is asserted on its own (the R26 m3 mutation - inherit without plan_id - survived every test)."""
    pid = flow.new_project()
    plan_a, first = _plan_a_partial(pid, monkeypatch)
    flow.retry_variant(pid, 'bad', 'v1')
    flow.render_outcome(pid, {'ok': ('completed', None, None), 'bad': ('completed', None, None)})
    retried = flow.receipts(pid)[1]
    assert retried['plan_id'] == plan_a and retried['retry_of'] == first['attempt_id']
    assert (retried['summary']['variant_count'], retried['summary']['completed_variant_count']) == (2, 2)


def test_376_real_auto_generate_stamps_the_outputs_it_creates(monkeypatch):
    """The production write itself (jobs._auto_generate persist) stamps each new output with the open attempt and
    its bound plan - not a test helper."""
    from backend.tests.test_on_demand_variants import _auto_fixture, _base
    state, _exports = _auto_fixture(monkeypatch, [_base(n, 1) for n in range(3)], ['douyin'])
    state['attempts'] = [{'attempt_id': 't-gen', 'kind': 'generation', 'state': 'open', 'sequence': 1, 'plan_id': 'plan-a'},
                         {'attempt_id': 't-old', 'kind': 'generation', 'state': 'partial', 'sequence': 0, 'plan_id': 'plan-0'}]
    state['generation']['attempt_id'] = 't-gen'
    jobs._auto_generate('p1', {'id': 'plan-a'})
    assert state['output_variants']
    assert {(v['produced_by_attempt'], v.get('produced_by_plan')) for v in state['output_variants']} == {('t-gen', 'plan-a')}
