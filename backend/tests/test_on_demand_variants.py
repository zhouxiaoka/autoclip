"""Only the best clips render automatically; the rest are produced when the user asks (no rendering)."""
import json
from copy import deepcopy

import pytest

from backend.services.studio import jobs, store


def _base(n, score):
    return {'id': f'd{n}', 'title': f't{n}', 'scenes': [{'id': f's{n}', 'label': 'x', 'start': n * 100.0, 'end': n * 100.0 + 90}],
            jobs.SCORE_KEY: score}


def test_the_top_scored_clips_render_now_and_unscored_ones_always_do():
    drafts = [_base(n, n / 20) for n in range(15)]
    automatic = jobs._automatic_drafts(drafts)
    assert automatic == {f'd{n}' for n in range(5, 15)}  # ten highest scores
    few = [_base(n, .1) for n in range(3)] + [{'id': 'visual', 'scenes': []}]
    assert jobs._automatic_drafts(few) == {'d0', 'd1', 'd2', 'visual'}


def test_on_demand_variants_do_not_keep_the_generation_open(monkeypatch):
    state = {'generation': {'status': 'rendering'}, 'analysis': {}, 'output_variants': [
        {'id': 'a', 'render_job_id': 'j1', 'status': 'running'}, {'id': 'b', 'status': 'on_demand'}]}
    monkeypatch.setattr(store, 'change', lambda _pid, fn: fn(state))
    jobs._sync_variant_status('p1', 'j1', 'completed')
    assert state['generation']['status'] == 'completed' and state['generation']['completed_variant_count'] == 1


def test_producing_a_variant_frames_packages_and_queues_it(monkeypatch):
    state = {'generation': {'status': 'completed'}, 'drafts': [{**_base(1, .5), 'id': 'v1-draft'}],
             'output_variants': [{'id': 'v1', 'draft_id': 'v1-draft', 'strategy_id': 'douyin', 'status': 'on_demand'}]}
    state['drafts'][0].pop(jobs.SCORE_KEY)
    monkeypatch.setattr(store, 'read', lambda _pid: deepcopy(state))
    monkeypatch.setattr(store, 'change', lambda _pid, fn: fn(state))
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *args: fn(*args))
    monkeypatch.setattr(jobs, 'source', lambda _pid: 'video.mp4')
    monkeypatch.setattr(jobs, '_source_has_burned_subtitles', lambda *_: False)
    monkeypatch.setattr(jobs, '_apply_framing', lambda _p, value, *_a: ({**value, 'layout': 'window'}, 'speaker'))
    monkeypatch.setattr(jobs, '_apply_packaging', lambda _p, value, *_a: {**value, 'packaging': None})
    dispatched = []
    monkeypatch.setattr(jobs, '_dispatch_pending_variants', lambda pid: dispatched.append(pid))
    jobs.produce_variant('p1', 'v1')
    variant = state['output_variants'][0]
    assert variant['status'] == 'queued' and variant['framing'] == 'speaker' and dispatched == ['p1']
    assert state['drafts'][0]['layout'] == 'window' and state['generation']['status'] == 'rendering'


def test_english_platform_versions_are_titled_in_english():
    value = {'title': '一次挑片的中文标题', 'packaging': {'title_lines': ['Choose partners', 'for your worst day']}}
    assert jobs._audience_title(value, 'tiktok', None)['title'] == 'Choose partners for your worst day'
    no_lines = {'title': '中文标题', 'packaging': {'title_lines': []}}
    assert jobs._audience_title(no_lines, 'youtube_shorts', {'title': 'Bet on yourself'})['title'] == 'Bet on yourself'
    assert jobs._audience_title(value, 'douyin', None)['title'] == '一次挑片的中文标题'


def _on_demand_state():
    state = {'generation': {'status': 'completed'}, 'analysis': {}, 'drafts': [{**_base(1, .5), 'id': 'v1-draft'}],
             'output_variants': [{'id': 'v1', 'draft_id': 'v1-draft', 'strategy_id': 'douyin', 'status': 'on_demand', 'branding': {}}]}
    state['drafts'][0].pop(jobs.SCORE_KEY)
    return state


def _patch_store(monkeypatch, state):
    monkeypatch.setattr(store, 'read', lambda _pid: deepcopy(state))
    monkeypatch.setattr(store, 'change', lambda _pid, fn: fn(state))


def test_a_variant_being_prepared_is_never_rendered_raw_and_cannot_be_claimed_twice(monkeypatch):
    state = _on_demand_state()
    _patch_store(monkeypatch, state)
    submitted = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *args: submitted.append(args))
    exported = []
    monkeypatch.setattr(jobs, 'export', lambda *a, **k: exported.append(a) or {'job_id': 'j'})
    jobs.produce_variant('p1', 'v1')
    assert state['output_variants'][0]['status'] == 'preparing' and len(submitted) == 1
    jobs._dispatch_pending_variants('p1')  # e.g. another card finishing meanwhile
    assert exported == [], 'the unframed, unpackaged draft must not be rendered'
    with pytest.raises(ValueError):
        jobs.produce_variant('p1', 'v1')
    assert len(submitted) == 1, 'a double click does not prepare it twice'


def test_a_failed_preparation_settles_the_generation_and_retry_prepares_again(monkeypatch):
    state = _on_demand_state()
    _patch_store(monkeypatch, state)
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *args: None)
    jobs.produce_variant('p1', 'v1')

    def gone(_pid):
        raise FileNotFoundError('gone')
    monkeypatch.setattr(jobs, 'source', gone)
    jobs._produce_on_demand('p1', 'v1')
    variant = state['output_variants'][0]
    assert variant['status'] == 'failed' and variant['needs_prepare']
    assert state['generation']['status'] == 'failed', 'the generation does not stay rendering forever'
    submitted = []
    monkeypatch.setattr(jobs.executor, 'submit', lambda fn, *args: submitted.append(fn))
    monkeypatch.setattr(jobs, '_dispatch_pending_variants', lambda _pid: submitted.append('dispatch'))
    jobs.retry_variant('p1', 'v1')
    variant = state['output_variants'][0]
    assert submitted == [jobs._produce_on_demand] and variant['status'] == 'preparing' and 'needs_prepare' not in variant


def test_a_variant_left_preparing_by_a_previous_run_can_be_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(store, 'get_projects_directory', lambda: tmp_path)
    meta = tmp_path / 'p1' / 'metadata'
    meta.mkdir(parents=True)
    (meta / 'studio.json').write_text(json.dumps({'output_variants': [{'id': 'v1', 'status': 'preparing', 'instance': 'old'}]}))
    variant = store.read('p1')['output_variants'][0]
    assert variant['status'] == 'failed' and variant['needs_prepare']


def _auto_fixture(monkeypatch, drafts, platforms):
    state = {'generation': {'status': 'production', 'auto_start': True, 'requested_platforms': platforms, 'branding': {'outro_enabled': False}},
             'analysis': {'status': 'running', 'phase': 'production', 'run_id': 'run'}, 'jobs': [], 'drafts': [], 'output_variants': []}
    monkeypatch.setattr(store, 'read', lambda _pid, **kwargs: deepcopy(state))
    monkeypatch.setattr(store, 'change', lambda _pid, fn: fn(state))
    monkeypatch.setattr(jobs, 'source', lambda _pid: 'video.mp4')
    monkeypatch.setattr(jobs, '_content_drafts', lambda *_: drafts)
    monkeypatch.setattr(jobs, '_source_has_burned_subtitles', lambda *_: False)
    monkeypatch.setattr(jobs, '_apply_framing', lambda _p, value, *_: (value, 'full_frame'))
    monkeypatch.setattr(jobs, '_prefetch_packaging', lambda *_: None)
    monkeypatch.setattr(jobs, '_posts_for', lambda *_: {})
    monkeypatch.setattr(jobs, '_apply_packaging', lambda _p, value, *_: value)
    monkeypatch.setattr(jobs, 'mark_project', lambda *_a, **_k: None)
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *_: None)
    exports = []
    def export(_pid, draft, **_kwargs):
        job = {'job_id': f'job{len(exports)}', 'draft_id': draft.id, 'status': 'queued'}
        state['jobs'].append(job)
        exports.append(draft)
        return job
    monkeypatch.setattr(jobs, 'export', export)
    return state, exports


def _long(n, score):
    draft = _base(n, score)
    draft['scenes'][0]['end'] = draft['scenes'][0]['start'] + 210
    return draft


def test_long_platform_queues_its_only_eligible_clip_below_global_top_ten(monkeypatch):
    drafts = [_base(n, 1) for n in range(10)] + [_long(10, .1)]
    state, exports = _auto_fixture(monkeypatch, drafts, ['youtube_long'])
    jobs._auto_generate('p1', {})
    assert len(exports) == 1, 'eligible long clip must render rather than remain a backup'
    assert len(state['output_variants']) == 1
    variant = state['output_variants'][0]
    assert variant['status'] == 'queued' and variant['render_job_id'] == 'job0'
    assert state['generation']['status'] == 'rendering'
    assert len(state['generation']['skipped']) == 10
    state['jobs'][0]['status'] = 'completed'
    jobs._sync_variant_status('p1', 'job0', 'completed')
    assert state['generation']['status'] == 'completed'
    from backend.services.quick_output_runner import status
    assert status('p1')['status'] == 'completed', 'CLI and MCP observers see a terminal outcome'


def test_each_platform_ranks_its_eligible_candidates_and_retains_backups(monkeypatch):
    drafts = [_base(n, 2) for n in range(10)] + [_long(n, n / 100) for n in range(10, 22)]
    state, exports = _auto_fixture(monkeypatch, drafts, ['bilibili', 'youtube_long'])
    jobs._auto_generate('p1', {})
    assert len(exports) == 20
    by_id = {d['id']: d for d in state['drafts']}
    queued = {platform: {by_id[v['draft_id']]['scenes'][0]['id'] for v in state['output_variants']
                         if v['strategy_id'] == platform and v['status'] == 'queued'} for platform in ['bilibili', 'youtube_long']}
    assert queued['bilibili'] == {f's{n}' for n in range(10)}
    assert queued['youtube_long'] == {f's{n}' for n in range(12, 22)}
    assert sum(v['status'] == 'on_demand' and v['strategy_id'] == 'youtube_long' for v in state['output_variants']) == 2


def test_no_eligible_long_clip_fails_explicitly_without_any_queued_task(monkeypatch):
    state, exports = _auto_fixture(monkeypatch, [_base(n, 1) for n in range(11)], ['youtube_long'])
    jobs._auto_generate('p1', {})
    assert exports == [] and state['jobs'] == [] and state['output_variants'] == []
    assert state['generation']['status'] == 'failed' and state['generation']['finished_at']
    assert '没有可生成' in state['generation']['error']


def test_automatic_production_preserves_structured_subtitle_failure(monkeypatch):
    from backend.pipeline.failures import PipelineFailure
    state, exports = _auto_fixture(monkeypatch, [], ['tiktok'])
    def fail(*args):
        raise PipelineFailure('SUBTITLE', 'Synthetic missing local runtime', code='whisper_not_installed')
    monkeypatch.setattr(jobs, '_content_drafts', fail)
    jobs._auto_generate('p1', {})
    assert not exports
    assert state['generation']['status'] == state['analysis']['status'] == 'failed'
    assert state['generation']['error_code'] == state['analysis']['error_code'] == 'whisper_not_installed'
    assert state['analysis']['phase'] == 'production'


def test_backup_only_dispatch_settles_instead_of_waiting_forever(monkeypatch):
    state = _on_demand_state()
    state['generation']['status'] = 'rendering'
    _patch_store(monkeypatch, state)
    monkeypatch.setattr(jobs, 'export', lambda *_a, **_k: pytest.fail('backup must not render unexpectedly'))
    jobs._dispatch_pending_variants('p1')
    assert state['generation']['status'] == 'failed'
    assert state['analysis']['status'] == 'failed'
    assert state['generation']['completed_variant_count'] == 0
    assert '备选' in state['generation']['error']


def test_dispatch_missing_draft_is_terminal_without_render_callback(monkeypatch):
    state = _on_demand_state()
    state['drafts'] = []
    state['generation']['status'] = 'rendering'
    state['output_variants'][0]['status'] = 'queued'
    _patch_store(monkeypatch, state)
    jobs._dispatch_pending_variants('p1')
    assert state['output_variants'][0]['status'] == 'failed'
    assert state['generation']['status'] == 'failed'


@pytest.mark.parametrize('codes,expected', [(['timeout'], 'timeout'), (['rate_limited', 'timeout'], 'multiple'), (['private/path'], 'unexpected'), ([{'private': 'path'}], 'unexpected')])
def test_render_failures_keep_controlled_generation_codes(codes, expected):
    state = {'generation': {'status': 'rendering'}, 'analysis': {'run_id': 'run'},
             'jobs': [{'job_id': f'j{i}', 'error_code': code} for i, code in enumerate(codes)],
             'output_variants': [{'id': f'v{i}', 'render_job_id': f'j{i}', 'status': 'failed'} for i in range(len(codes))]}
    store.settle_generation(state)
    assert state['generation']['error_code'] == state['analysis']['error_code'] == expected
    state['output_variants'][0]['status'] = 'completed'
    store.settle_generation(state)
    if len(codes) == 1:
        assert 'error_code' not in state['generation'] and 'error_code' not in state['analysis']


def test_screening_failure_settles_automatic_generation(monkeypatch):
    from backend.services.studio.models import ImportOptions
    from backend.services.studio import planning
    state = {'generation': {'status': 'screening', 'auto_start': True},
             'analysis': {'status': 'running', 'phase': 'screening', 'run_id': 'screen'}}
    monkeypatch.setattr(store, 'change', lambda _pid, fn: fn(state))
    monkeypatch.setattr(jobs, 'mark_project', lambda *_a, **_k: None)
    monkeypatch.setattr(jobs, 'source', lambda *_a: 'missing.mp4')
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *_a: None)
    def fail(*args):
        raise FileNotFoundError('private local path')
    monkeypatch.setattr(planning, 'recommend', fail)
    jobs._inspect('p1', ImportOptions(auto_start=True), None, None)
    assert state['analysis']['status'] == state['generation']['status'] == 'failed'
    assert state['generation']['error_code'] == 'missing_resource'
    assert state['generation']['finished_at']


@pytest.mark.parametrize('retry', [False, True])
def test_on_demand_dispatch_failure_remains_retryable(monkeypatch, retry):
    state = _on_demand_state()
    if retry:
        state['output_variants'][0].update(status='failed', needs_prepare=True)
    _patch_store(monkeypatch, state)
    def reject(*args):
        raise RuntimeError('private executor details')
    monkeypatch.setattr(jobs.executor, 'submit', reject)
    with pytest.raises(ValueError, match='未能启动'):
        (jobs.retry_variant if retry else jobs.produce_variant)('p1', 'v1')
    variant = state['output_variants'][0]
    assert variant['status'] == 'failed' and variant['needs_prepare']
    assert state['generation']['status'] == 'failed'
    assert 'private' not in variant['error']


def test_render_dispatch_rejection_settles_and_can_retry(monkeypatch):
    state = _on_demand_state()
    state['output_variants'][0]['status'] = 'queued'
    state['generation']['status'] = 'rendering'
    _patch_store(monkeypatch, state)
    calls = []
    def export(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise RuntimeError('private executor details')
        return {'job_id': 'retry-job'}
    monkeypatch.setattr(jobs, 'export', export)
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *_a: None)
    jobs._dispatch_pending_variants('p1')
    assert state['generation']['status'] == 'failed'
    assert state['output_variants'][0]['status'] == 'failed'
    assert 'private' not in state['output_variants'][0]['error']
    jobs.retry_variant('p1', 'v1')
    assert state['output_variants'][0]['render_job_id'] == 'retry-job'
    assert len(calls) == 2


def test_visual_analysis_dispatch_rejection_is_retryable(monkeypatch):
    from backend.services.studio.models import Preferences
    state = {'drafts': [{'id': 'prior'}], 'analysis': None}
    monkeypatch.setattr(store, 'change', lambda _pid, fn: fn(state))
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *_a: None)
    def reject(*args):
        raise RuntimeError('private executor details')
    monkeypatch.setattr(jobs.executor, 'submit', reject)
    with pytest.raises(ValueError, match='未能启动'):
        jobs.analyze_project('p1', Preferences())
    assert state['analysis']['status'] == 'failed'
    assert state['drafts'] == [{'id': 'prior'}]
    assert 'private' not in state['analysis']['error']


@pytest.mark.parametrize('claimed_status', ['queued', 'running', 'completed'])
def test_stale_failed_retry_preserves_a_concurrent_claim(tmp_path, monkeypatch, claimed_status):
    monkeypatch.setattr(store, 'get_projects_directory', lambda: tmp_path)
    (tmp_path / 'p1').mkdir()
    initial = _on_demand_state()
    initial['output_variants'][0]['status'] = 'failed'
    initial['generation']['status'] = 'failed'
    store.write('p1', initial)
    read = store.read
    intervened = False

    def read_then_other_request(project_id, **kwargs):
        nonlocal intervened
        snapshot = read(project_id, **kwargs)
        if not intervened:
            intervened = True
            # Another retry wins after this request reads 'failed', before it writes.
            def claim(data):
                data['output_variants'][0].update(status=claimed_status, render_job_id='other-job')
                data['jobs'] = [{'job_id': 'other-job', 'status': claimed_status, 'instance': store.INSTANCE}]
                data['generation']['status'] = 'completed' if claimed_status == 'completed' else 'rendering'
            store.change(project_id, claim)
        return snapshot

    monkeypatch.setattr(store, 'read', read_then_other_request)
    dispatched = []
    monkeypatch.setattr(jobs, '_dispatch_pending_variants', lambda pid: dispatched.append(pid))
    with pytest.raises(ValueError, match='只有失败'):
        jobs.retry_variant('p1', 'v1')
    saved = read('p1')
    assert saved['output_variants'][0]['status'] == claimed_status
    assert saved['output_variants'][0]['render_job_id'] == 'other-job'
    assert not dispatched
