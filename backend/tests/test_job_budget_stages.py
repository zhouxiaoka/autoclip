"""Production and render tracked work share the clip-job cap.

The content pipeline still binds its own budget. Later model work — boundaries,
burned captions, post copy, packaging, and render — runs inside ``_tracked``
and must stop on the same cap, including the write that records the stop.
"""
from pathlib import Path

import pytest

from backend.core.job_budget import JobDurationExceeded, clip_job_active
from backend.services.studio import jobs, store


def _project(project_id):
    root = store.directory(project_id)
    (root / 'raw').mkdir(parents=True, exist_ok=True)
    (root / 'raw' / 'input.mp4').write_bytes(b'fixture')
    return root


def _running(phase, run_id):
    """Owned by this process, so recover() does not settle it as a restart first."""
    return {'status': 'running', 'phase': phase, 'run_id': run_id, 'instance': store.INSTANCE}


def _spend_then_call_the_model():
    """What ``LLMManager.call`` does once this job's clock is already spent."""
    from backend.core.job_budget import _current

    assert clip_job_active()
    _current.get().seconds = 0
    from backend.core.llm_manager import LLMManager

    manager = LLMManager.__new__(LLMManager)

    def provider(*_args, **_kwargs):
        raise AssertionError('provider')

    manager._snapshot_call_route = provider
    manager._invoke_text = provider
    manager.call('prompt', {'text': 'clip'})


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    (tmp_path / 'privacy.json').write_text('{"crash_reports":false}')
    monkeypatch.setattr(jobs, 'capture_studio_exception', lambda *args, **kwargs: None)
    monkeypatch.setattr(jobs, 'mark_project', lambda *args, **kwargs: None)
    monkeypatch.setattr(jobs, 'sync_project_completion', lambda *args, **kwargs: None)


def test_pipeline_unbind_does_not_drop_later_production_stages():
    seen = {}

    def work(project_id):
        from backend.core.job_budget import bind_clip_job, unbind_clip_job

        token = bind_clip_job()
        try:
            seen['during_pipeline'] = clip_job_active()
        finally:
            unbind_clip_job(token)
        seen['after_pipeline'] = clip_job_active()
        _spend_then_call_the_model()

    with pytest.raises(JobDurationExceeded):
        jobs._tracked('production')(work)('budget-stages')
    assert seen == {'during_pipeline': True, 'after_pipeline': True}
    assert clip_job_active() is False


def test_whisper_pause_still_freezes_a_production_budget(monkeypatch):
    import time

    from backend.core import job_budget

    monkeypatch.setattr(job_budget, 'clip_job_budget_seconds', lambda: 0.05)

    def work(project_id):
        with job_budget.pause_clip_job_budget():
            time.sleep(0.08)
            job_budget.ensure_clip_job_budget()
        job_budget.ensure_clip_job_budget()

    jobs._tracked('production')(work)('budget-whisper')
    assert clip_job_active() is False


def test_screening_and_cover_stay_outside_the_clip_budget():
    seen = []

    def work(project_id):
        seen.append(clip_job_active())

    jobs._tracked('screening')(work)('budget-screen')
    jobs._tracked('ai_cover')(work)('budget-cover')
    assert seen == [False, False]


def test_auto_production_records_a_spent_budget(isolated, monkeypatch):
    _project('prod-budget')
    store.write('prod-budget', {
        'drafts': [], 'events': [], 'jobs': [], 'output_variants': [],
        'generation': {'status': 'production', 'requested_platforms': ['douyin']},
        'analysis': _running('production', 'run-1'),
    })
    monkeypatch.setattr(jobs, 'source', lambda _project_id: Path('video.mp4'))

    def derive(*_args, **_kwargs):
        _spend_then_call_the_model()

    monkeypatch.setattr(jobs, '_initial_derive', derive)
    jobs._auto_generate('prod-budget', {'recommended_analysis': 'subtitle'})
    state = store.read('prod-budget')
    assert state['generation']['status'] == 'failed'
    assert state['generation']['error_code'] == 'timeout'
    assert '时间上限' in state['generation']['error']
    assert state['analysis']['status'] == 'failed'
    assert state['analysis']['run_id'] == 'run-1'
    assert clip_job_active() is False


def test_on_demand_packaging_stops_at_the_clip_budget(isolated, monkeypatch):
    draft = {'id': 'v1-draft', 'title': 't', 'scenes': [{'id': 's1', 'label': 'x', 'start': 0.0, 'end': 12.0}]}
    _project('ondemand-budget')
    store.write('ondemand-budget', {
        'drafts': [draft], 'events': [], 'jobs': [],
        'generation': {'status': 'rendering'},
        'analysis': _running('rendering', 'run-od'),
        'output_variants': [{
            'id': 'v1', 'draft_id': 'v1-draft', 'strategy_id': 'douyin', 'status': 'preparing',
        }],
    })
    monkeypatch.setattr(jobs, 'source', lambda _project_id: Path('video.mp4'))
    monkeypatch.setattr(jobs, '_source_has_burned_subtitles', lambda *_args, **_kwargs: False)
    monkeypatch.setattr(jobs, '_apply_framing', lambda _project_id, value, *_args, **_kwargs: (value, None))

    def packaging(*_args, **_kwargs):
        _spend_then_call_the_model()

    monkeypatch.setattr(jobs, '_apply_packaging', packaging)
    jobs._produce_on_demand('ondemand-budget', 'v1')
    state = store.read('ondemand-budget')
    variant = state['output_variants'][0]
    assert variant['status'] == 'failed'
    assert variant['needs_prepare'] is True
    assert variant['error_code'] == 'timeout'
    assert '时间上限' in variant['error']
    assert clip_job_active() is False


def test_confirmed_production_records_a_spent_budget(isolated, monkeypatch):
    _project('confirm-budget')
    store.write('confirm-budget', {
        'drafts': [], 'events': [], 'jobs': [], 'output_variants': [],
        'generation': {'status': 'production'},
        'analysis': _running('production', 'run-c'),
    })

    def source(_project_id):
        _spend_then_call_the_model()

    monkeypatch.setattr(jobs, 'source', source)
    jobs._produce_selected('confirm-budget', {
        'selected_goals': ['content'],
        'confirmed_analysis': 'subtitle',
        'confirmed_preferences': {'goal': 'content'},
    })
    state = store.read('confirm-budget')
    assert state['analysis']['status'] == 'failed'
    assert state['analysis']['error_code'] == 'timeout'
    assert '时间上限' in state['analysis']['error']
    assert state['analysis']['run_id'] == 'run-c'
    assert clip_job_active() is False


def test_render_model_work_stops_at_the_clip_budget(isolated, monkeypatch):
    _project('render-budget')
    store.write('render-budget', {
        'drafts': [], 'events': [],
        'jobs': [{'job_id': 'active', 'status': 'queued', 'percent': 0, 'instance': store.INSTANCE}],
        'output_variants': [{'id': 'v1', 'status': 'queued', 'render_job_id': 'active'}],
        'generation': {'status': 'rendering'},
        'analysis': _running('rendering', 'run-r'),
    })

    def render_draft(*_args, **_kwargs):
        _spend_then_call_the_model()

    monkeypatch.setattr(jobs, 'render_draft', render_draft)
    jobs._render('render-budget', object(), 'active')
    state = store.read('render-budget')
    job = next(item for item in state['jobs'] if item['job_id'] == 'active')
    assert job['status'] == 'failed'
    assert job['error_code'] == 'timeout'
    assert '时间上限' in job['error']
    assert state['output_variants'][0]['status'] == 'failed'
    assert '时间上限' in state['output_variants'][0]['error']
    assert clip_job_active() is False


def test_render_ffmpeg_wall_time_does_not_spend_clip_budget(isolated, monkeypatch):
    """P1 #8: slow ffmpeg must not trip the model budget (AUTOCLIP_CLIP_JOB_BUDGET_SEC).

    Progress updates go through store.change → checkpoint → ensure_clip_job_budget;
    while pause_clip_job_budget is active those checks must not see wall time advance.
    """
    import subprocess
    import time

    from backend.core.job_budget import _current
    from backend.services.studio import render as render_mod
    from backend.services.studio.models import Draft, Scene

    monkeypatch.setenv('AUTOCLIP_CLIP_JOB_BUDGET_SEC', '2')
    root = _project('render-pause')
    source = root / 'raw' / 'input.mp4'
    subprocess.run(
        ['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=64x64:r=30:d=1',
         '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-y', str(source)],
        check=True, capture_output=True,
    )
    store.write('render-pause', {
        'drafts': [], 'events': [],
        'jobs': [{'job_id': 'active', 'status': 'queued', 'percent': 0, 'instance': store.INSTANCE}],
        'output_variants': [{'id': 'v1', 'status': 'queued', 'render_job_id': 'active'}],
        'generation': {'status': 'rendering'},
        'analysis': _running('rendering', 'run-pause'),
    })
    monkeypatch.setattr(jobs, 'source', lambda _project_id: source)
    monkeypatch.setattr(jobs, '_design_covers', lambda *_args, **_kwargs: None)

    depths = []
    slept = []
    real_run = render_mod.project_cancellation.run

    def slow_run(cmd, **kwargs):
        budget = _current.get()
        depths.append(None if budget is None else budget.pause_depth)
        # One 5s stall exceeds the 2s model budget unless encode is paused.
        if not slept:
            slept.append(1)
            time.sleep(5)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(render_mod.project_cancellation, 'run', slow_run)
    draft = Draft(
        id='d', title='pause', subtitles=False, original_audio=False,
        aspect='original', scenes=[Scene(id='s', start=0, end=0.5)],
    )
    jobs._render('render-pause', draft, 'active')
    state = store.read('render-pause')
    job = next(item for item in state['jobs'] if item['job_id'] == 'active')
    assert job['status'] == 'completed', job
    assert slept == [1]
    assert depths and all(depth and depth >= 1 for depth in depths), depths
    assert clip_job_active() is False
