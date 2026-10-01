"""Only the best clips render automatically; the rest are produced when the user asks (no rendering)."""
from copy import deepcopy

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
