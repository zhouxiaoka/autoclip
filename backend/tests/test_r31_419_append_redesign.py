"""R31 #419 I530-I535 / I539-I541 + Dong's four additions: appending platforms is an ordinary generation.
The request validates, opens the attempt and freezes its input, then returns the receipt; preparation runs in the
background through _auto_generate (same worker entry and failure branch); the round is judged only on outputs
stamped by its own attempt. Real jobs / attempts / store.settle_generation / store recovery; only media, framing,
packaging, rendering and the executor are stubbed. Every test here fails on 913f416d on an assertion (I541-a is
a regression lock - the normal path was already right there - and says so)."""
import httpx
import pytest

from backend.services.studio import attempts, jobs, store
from backend.tests.test_r30_419_append_lifecycle import _added, _append, _state
from backend.tests.test_studio import client, root, source  # noqa: F401  (shared HTTP client fixture)


class _Recorder:
    """An executor that only records: the receipt has returned, the background job has not run yet."""
    def __init__(self):
        self.calls = []

    def submit(self, fn, *args, **kwargs):
        self.calls.append((fn, args, dict(kwargs)))

    def run(self):
        fn, args, kwargs = self.calls.pop(0)
        return fn(*args, **kwargs)


def _recorded(monkeypatch, **kwargs):
    state = _state(monkeypatch, **kwargs)
    recorder = _Recorder()
    monkeypatch.setattr(jobs, 'executor', recorder)
    return state, recorder


def _append_receipt(state):
    return next(a for a in state['attempts'] if a.get('trigger') == 'append_platform')


def _rate_limited():
    import openai
    response = httpx.Response(429, request=httpx.Request('POST', 'https://api.example.invalid/v1/chat/completions'))
    return openai.RateLimitError('rate limited', response=response, body=None)


# --- I530: while the append prepares, nothing settles it on other rounds' outputs ---

def test_i530_a_render_callback_during_preparation_does_not_settle_the_append(monkeypatch):
    state = _state(monkeypatch)                                           # the first round's outputs all completed
    real = jobs._apply_framing
    def framing(*a, **k):
        store.settle_generation(state)                                    # an old output's render callback lands now
        attempts.reconcile(state)
        return real(*a, **k)
    monkeypatch.setattr(jobs, '_apply_framing', framing)
    result = _append()
    receipt = attempts.find(state, result['attempt']['attempt_id'])
    assert receipt['state'] == 'open'                                     # 913f416d: settled 'completed'
    added = _added(state, result)
    assert added and {v['produced_by_attempt'] for v in added} == {receipt['attempt_id']}   # 913f416d: unstamped


# --- Dong addition 1 / I530: the process dies after the receipt returned, before the background job ran ---

def test_addition1_process_dies_before_the_background_job_settles_service_restarted(monkeypatch):
    state, recorder = _recorded(monkeypatch)
    before = {v['id']: v['status'] for v in state['output_variants']}
    result = _append()
    state['analysis']['instance'] = 'a-process-that-died'                 # restart: the worker never ran
    assert store._recover_interrupted_run(state) is True
    attempts.reconcile(state)
    receipt = attempts.find(state, result['attempt']['attempt_id'])
    assert (state['generation']['status'], state['generation'].get('error_code')) == ('failed', 'service_restarted')
    assert receipt['state'] == 'failed' and receipt.get('error_code') == 'service_restarted'   # terminal reached
    assert isinstance(receipt['summary'].get('duration_ms'), int)          # I534: even with no output of its own
    assert {v['id']: v['status'] for v in state['output_variants']} == before   # the workspace is not rolled back


def test_addition1_a_live_append_is_not_mistaken_for_a_dead_one(monkeypatch):
    """Counter-case of addition 1: the same process reads the project while the job is queued - not recovered."""
    state, recorder = _recorded(monkeypatch)
    result = _append()
    assert store._recover_interrupted_run(state) is False
    attempts.reconcile(state)
    assert state['generation']['status'] == 'production'
    assert attempts.find(state, result['attempt']['attempt_id'])['state'] == 'open'
    recorder.run()
    assert _added(state, result)


def test_i530_b_an_append_closed_during_preparation_persists_nothing(monkeypatch):
    """The attempt was closed while preparing (here: settled failed by recovery) - its late preparation adds nothing
    and does not reopen it."""
    state = _state(monkeypatch)
    before = len(state['output_variants'])
    real = jobs._apply_framing
    def framing(*a, **k):
        state['generation'].update(status='failed', error_code='service_restarted')
        attempts.reconcile(state)
        return real(*a, **k)
    monkeypatch.setattr(jobs, '_apply_framing', framing)
    result = _append()
    receipt = attempts.find(state, result['attempt']['attempt_id'])
    assert len(state['output_variants']) == before
    assert receipt['state'] == 'failed' and receipt.get('error_code') == 'service_restarted'


def test_i530_c_a_closed_round_that_stamped_nothing_still_settles_on_the_workspace():
    """round_outputs returns [] only for an open attempt still preparing; a round from before stamping (receipt but no
    stamps) keeps settling on the whole workspace (R29 #440). Regression lock: 913f416d already did this; it pins the
    mutant that settles such a round on nothing."""
    state = {'generation': {'attempt_id': 't-legacy', 'status': 'rendering', 'auto_start': True},
             'attempts': [{'attempt_id': 't-legacy', 'kind': 'generation', 'state': 'open', 'sequence': 1}],
             'output_variants': [{'id': 'v1', 'draft_id': 'd', 'strategy_id': 'tiktok', 'status': 'completed'},
                                 {'id': 'v2', 'draft_id': 'd', 'strategy_id': 'bilibili', 'status': 'completed'}],
             'drafts': [], 'analysis': {}}
    assert attempts.round_outputs(state) is None
    store.settle_generation(state)
    assert state['generation']['status'] == 'completed'


# --- I531: the receipt returns before preparation, which is the submitted worker job ---

def test_i531_http_append_returns_the_open_receipt_before_any_preparation(client, monkeypatch):
    state, recorder = _recorded(monkeypatch)
    prepared = []
    monkeypatch.setattr(jobs, '_apply_framing', lambda *a, **k: prepared.append(1) or (a[1], 'full_frame'))
    response = client.post('/studio/p1/platforms', json={'platforms': ['bilibili']})
    assert response.status_code == 200
    body = response.json()
    assert prepared == []                                                 # 913f416d: prepared inside the request
    assert body['variants'] == [] and body['attempt']['state'] == 'open' and body['attempt']['trigger'] == 'append_platform'
    [(fn, args, kwargs)] = recorder.calls
    run_id = state['analysis'].get('run_id')
    assert fn.__name__ == '_auto_generate' and args == ('p1', None)
    assert kwargs == {'append_attempt': body['attempt']['attempt_id'], '_io_receipt': ('analysis', run_id, 'production')}
    assert 'input' not in body['attempt']                                 # the frozen input stays server-side
    recorder.run()
    assert prepared and _added(state, {'attempt': body['attempt']})


# --- I532: one choice of (source output, its draft) feeds preparation and inheritance ---

def test_i532_same_scenes_in_two_plans_prepares_and_inherits_from_the_same_source(monkeypatch):
    state = _state(monkeypatch)
    a = state['drafts'][0]
    b = {**a, 'id': 'draft-b', 'title': 'B-TITLE'}                       # same scenes, other plan
    state['drafts'].append(b)
    state['attempts'].append({'attempt_id': 't-b', 'kind': 'generation', 'state': 'completed', 'sequence': 2, 'plan_id': 'plan-b',
                              'summary': {'route': 'visual'}})
    state['output_variants'].append({'id': 'out-b', 'draft_id': 'draft-b', 'strategy_id': 'tiktok', 'status': 'completed',
                                     'produced_by_attempt': 't-b', 'produced_by_plan': 'plan-b'})
    result = _append()
    receipt = attempts.find(state, result['attempt']['attempt_id'])
    assert receipt['plan_id'] == 'plan-b' and receipt['inherited']['route'] == 'visual'
    drafts = {d['id']: d for d in state['drafts']}
    titles = {drafts[v['draft_id']]['title'] for v in _added(state, result) if v['draft_id'] in drafts}
    moment = [v for v in _added(state, result) if drafts.get(v['draft_id'], {}).get('scenes') == a['scenes']]
    assert moment and {drafts[v['draft_id']]['title'] for v in moment} == {'B-TITLE'}, titles   # 913f416d: A's title


# --- I533: preparation uses the input frozen in the lock; a changed draft fails the append ---

def test_i533_a_draft_changed_during_preparation_fails_the_append_without_outputs(monkeypatch):
    state = _state(monkeypatch)
    before = len(state['output_variants'])
    real = jobs._apply_framing
    def framing(*a, **k):
        draft = state['drafts'][0]
        draft.update(title='EDITED', revision=(draft.get('revision') or 1) + 1)   # the user edits it meanwhile
        return real(*a, **k)
    monkeypatch.setattr(jobs, '_apply_framing', framing)
    result = _append()
    attempts.reconcile(state)
    receipt = attempts.find(state, result['attempt']['attempt_id'])
    assert receipt['state'] == 'failed' and state['generation']['error_code'] == 'validation'   # 913f416d: persisted
    assert len(state['output_variants']) == before


# --- I534 + I535 + I539 + Dong addition 2: a preparation failure takes the generation failure branch ---

def test_i535_preparation_failure_carries_attribution_run_id_duration_and_marks_the_project(monkeypatch):
    state, recorder = _recorded(monkeypatch)
    marked = []
    monkeypatch.setattr(jobs, 'mark_project', lambda pid, status, **k: marked.append(status))
    def framing(*_a, **_k):
        raise _rate_limited()
    monkeypatch.setattr(jobs, '_apply_framing', framing)
    result = _append()
    run_id = state['analysis'].get('run_id')
    assert run_id                                                         # 913f416d: the append's analysis has no run_id
    recorder.run()
    attempts.reconcile(state)
    generation, analysis = state['generation'], state['analysis']
    receipt = attempts.find(state, result['attempt']['attempt_id'])
    assert (generation['error_code'], generation.get('http_status'), generation.get('failure_stage')) == ('rate_limited', 429, 'production')
    assert generation.get('upstream_error_type')                          # studio_failure_context (#415)
    assert (analysis['status'], analysis['phase'], analysis.get('run_id')) == ('failed', 'production', run_id)   # I539
    assert receipt['run_id'] == run_id and receipt['causes'][0]['upstream']   # what receiptFailureInfo matches on
    assert isinstance(analysis.get('duration_ms'), int) and marked == ['failed']
    assert receipt['state'] == 'failed' and receipt['error_code'] == 'rate_limited'
    assert isinstance(receipt['summary'].get('duration_ms'), int) and receipt['summary']['duration_ms'] >= 0   # I534


# --- I540: drafts of a manual confirmation are owned by its attempt ---

def test_i540_manual_confirmation_drafts_are_owned_by_the_confirming_attempt(tmp_path, monkeypatch):
    from backend.pipeline import media_precheck
    from backend.services.studio import intelligence, subtitle_highlights
    from backend.services.studio.models import ConfirmPlan
    from backend.tests import attempt_flow as flow
    flow.setup_env(tmp_path, monkeypatch)
    monkeypatch.setattr(jobs, 'mark_project', lambda *a, **k: None)
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *a, **k: None)
    pid = flow.new_project()
    jobs.inspect_project(pid, flow.MANUAL)
    plan_id = flow.awaiting_confirmation(pid)
    store.change(pid, lambda d: d['drafts'].append({'id': 'older', 'title': 'older', 'scenes': []}))
    captured = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *a, **k: captured.append((fn, a)))
    video = store.directory(pid) / 'input.mp4'
    video.write_bytes(b'')
    (store.directory(pid) / 'input.srt').write_text('1\n00:00:00,000 --> 00:00:01,000\nx\n')
    monkeypatch.setattr(jobs, 'source', lambda _pid: video)
    monkeypatch.setattr(media_precheck, 'subtitle_route_failure', lambda *a, **k: None)
    jobs.confirm_project(pid, ConfirmPlan(plan_id=plan_id, goals=['highlight']))
    monkeypatch.setattr(jobs, 'run_content', lambda *_: [{'id': 'c1'}])
    monkeypatch.setattr(intelligence, '_probe', lambda *_: {'duration': 60})
    monkeypatch.setattr(subtitle_highlights, 'make_highlights', lambda *a, **k: [{'id': 'h1', 'title': 'H', 'scenes': []}])
    [(fn, args)] = captured
    fn(*args)
    [receipt] = flow.receipts(pid)
    assert receipt['kind'] == 'production' and receipt.get('draft_ids') == ['h1']   # 913f416d: no ownership; never 'older'


# --- I541: a receipt counts only outputs stamped by its own attempt ---

def test_i541_a_append_receipt_counts_only_its_own_outputs_regression_lock(monkeypatch):
    """Regression lock (Dong addition 3): at 913f416d the normal append path already counted only its own outputs."""
    state = _state(monkeypatch)
    old = len([v for v in state['output_variants'] if v['status'] == 'completed'])
    result = _append()
    added = [v for v in _added(state, result) if v['status'] != 'on_demand']
    for v in added:
        v['status'] = 'completed'
    store.settle_generation(state)
    attempts.reconcile(state)
    receipt = attempts.find(state, result['attempt']['attempt_id'])
    assert old and receipt['summary']['completed_variant_count'] == len(added) and receipt['state'] == 'completed'


def test_i541_b_variant_retry_counts_only_the_output_it_redid(monkeypatch):
    state = _state(monkeypatch, error=True)                               # first round: every output failed
    monkeypatch.setattr(jobs, '_dispatch_pending_variants', lambda _pid: None)
    first, second = [v for v in state['output_variants'] if v['status'] != 'on_demand'][:2]
    second.update(status='completed', error_code=None)                    # one earlier output already fine
    jobs.retry_variant('p1', first['id'])
    first['status'] = 'completed'
    store.settle_generation(state)
    attempts.reconcile(state)
    receipt = state['attempts'][-1]
    assert receipt['trigger'] == 'variant_retry' and first.get('redone_by_attempt') == receipt['attempt_id']
    assert (receipt['summary']['variant_count'], receipt['summary']['completed_variant_count']) == (1, 1)   # 913f416d: 2
