"""Optional packaging must leave prepared clips able to enter rendering."""
from types import SimpleNamespace

import pytest

from backend.core import job_budget
from backend.core.project_cancellation import JobStopped, ProjectDeleted, ServiceRestarted
from backend.services.studio import intelligence, jobs, packaging


@pytest.fixture
def packaging_run(monkeypatch):
    from backend.pipeline import concurrency
    now = [100.0]
    monkeypatch.setattr(job_budget.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(concurrency, 'workers', lambda: 1)
    monkeypatch.setattr(jobs, '_packaging_inputs', lambda *args: None)
    strategy = SimpleNamespace(template='interview_zh', audience_language='zh')
    monkeypatch.setattr(jobs, '_project_strategy', lambda *args: strategy)
    items = [('douyin', {'title': 'Useful clip', 'scenes': [{'start': 0, 'end': 5}]}),
             ('douyin', {'title': 'Another clip', 'scenes': [{'start': 5, 'end': 10}]})]
    cache = {'entries': [{'start_time': '00:00:00,000', 'end_time': '00:00:10,000', 'text': 'Useful source words'}], 'names': ''}
    return now, items, cache, strategy


def test_packaging_deadline_keeps_source_captions_and_parent_budget(packaging_run, monkeypatch):
    now, items, cache, _ = packaging_run
    calls = []
    def slow(*args):
        calls.append(True)
        while not job_budget.budget_expired():
            now[0] += 30
        raise job_budget.JobDurationExceeded()
    monkeypatch.setattr(intelligence, 'text_json', slow)
    with job_budget.bound_clip_job(seconds=1200):
        jobs._prefetch_packaging('isolated-project', items, False, cache)
        job_budget.ensure_clip_job_budget()
        for platform, value in items:
            packed = jobs._apply_packaging('isolated-project', value, platform, False, cache)['packaging']
            assert packed['fallback'] is True
            assert packed['cues'][0]['text'] == 'Useful source words'
    assert len(calls) == 1


def test_packaging_timeout_preserves_completed_cache(packaging_run, monkeypatch):
    now, items, cache, _ = packaging_run
    key = (((0, 5),), 'interview_zh', 'zh')
    completed = {'title_lines': ['已完成'], 'fallback': False}
    cache[key] = completed
    def slow(*args):
        now[0] += 301
        raise job_budget.JobDurationExceeded()
    monkeypatch.setattr(intelligence, 'text_json', slow)
    with job_budget.bound_clip_job():
        jobs._prefetch_packaging('isolated-project', items, False, cache)
        job_budget.ensure_clip_job_budget()
    assert cache[key] is completed
    assert jobs._apply_packaging('isolated-project', items[1][1], 'douyin', False, cache)['packaging']['fallback']


def test_packaging_cannot_restore_expired_parent(packaging_run, monkeypatch):
    now, items, cache, _ = packaging_run
    def slow(*args):
        now[0] += 1200
        raise job_budget.JobDurationExceeded()
    monkeypatch.setattr(intelligence, 'text_json', slow)
    with job_budget.bound_clip_job(), pytest.raises(job_budget.JobDurationExceeded):
        jobs._prefetch_packaging('isolated-project', items, False, cache)


def test_packaging_reserves_short_remaining_budget_without_calling_model(packaging_run, monkeypatch):
    _, items, cache, _ = packaging_run
    calls = []
    monkeypatch.setattr(intelligence, 'text_json', lambda *args: calls.append(True) or {})
    with job_budget.bound_clip_job(seconds=20):
        jobs._prefetch_packaging('isolated-project', items, False, cache)
        job_budget.ensure_clip_job_budget()
    assert calls == []


@pytest.mark.parametrize('error', [JobStopped, ProjectDeleted, ServiceRestarted, job_budget.JobDurationExceeded])
@pytest.mark.parametrize('translation', [False, True])
def test_packaging_propagates_control_signals_without_another_model_call(packaging_run, error, translation):
    _, _, _, strategy = packaging_run
    calls = []
    def call(*args):
        calls.append(True)
        if translation and len(calls) <= 2:
            raise ValueError('invalid packaging')
        raise error()
    with pytest.raises(error):
        packaging.build_packaging({'title': 'Title'}, [{'start': 0, 'end': 5, 'text': 'Source words'}], strategy, call=call)
    assert len(calls) == (3 if translation else 1)
