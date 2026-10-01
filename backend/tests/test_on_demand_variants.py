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
