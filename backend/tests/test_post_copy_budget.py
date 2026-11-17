"""Optional publishing copy must leave a usable generation able to render."""
import pytest

from backend.core import job_budget
from backend.core.project_cancellation import JobStopped, ProjectDeleted, ServiceRestarted
from backend.services.studio import intelligence, jobs


@pytest.fixture
def copy_run(monkeypatch):
    from backend.pipeline import concurrency
    now = [100.0]
    monkeypatch.setattr(job_budget.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(concurrency, 'workers', lambda: 1)
    monkeypatch.setattr(jobs, '_packaging_inputs', lambda *args: None)
    items = [('douyin', {'title': 'A useful clip', 'scenes': [{'start': 0, 'end': 5}]}),
             ('douyin', {'title': 'Another clip', 'scenes': [{'start': 5, 'end': 10}]})]
    cache = {'entries': [{'start_time': '00:00:00,000', 'end_time': '00:00:10,000', 'text': 'Useful source words'}]}
    return now, items, cache


def test_optional_copy_cannot_spend_the_whole_generation_budget(copy_run, monkeypatch):
    now, items, cache = copy_run
    calls = []
    def slow(*args):
        calls.append(True)
        while not job_budget.budget_expired():
            now[0] += 30
        raise job_budget.JobDurationExceeded()
    monkeypatch.setattr(intelligence, 'text_json', slow)
    with job_budget.bound_clip_job(seconds=1200):
        jobs._posts_for('isolated-project', items, cache)
        # The next persistence/render checkpoint must still be reachable.
        job_budget.ensure_clip_job_budget()
        assert job_budget.clip_job_read_timeout(1200) > 0
    assert len(calls) == 1


def test_optional_copy_never_extends_an_exhausted_parent(copy_run, monkeypatch):
    now, items, cache = copy_run
    def slow(*args):
        now[0] += 60
        raise job_budget.JobDurationExceeded()
    monkeypatch.setattr(intelligence, 'text_json', slow)
    with job_budget.bound_clip_job(seconds=60), pytest.raises(job_budget.JobDurationExceeded):
        jobs._posts_for('isolated-project', items, cache)


def test_copy_leaves_short_remaining_budget_for_persistence(copy_run, monkeypatch):
    _, items, cache = copy_run
    calls = []
    monkeypatch.setattr(intelligence, 'text_json', lambda *args: calls.append(True) or {})
    with job_budget.bound_clip_job(seconds=20):
        assert jobs._posts_for('isolated-project', items, cache) == {}
        job_budget.ensure_clip_job_budget()
    assert calls == []


def test_copy_preserves_completed_posts_when_a_later_one_times_out(copy_run, monkeypatch):
    now, items, cache = copy_run
    calls = []
    def call(*args):
        calls.append(True)
        if len(calls) == 1:
            return {'posts': {'douyin': {'title': 'A usable title', 'description': 'Summary', 'tags': []}}}
        while not job_budget.budget_expired():
            now[0] += 30
        raise job_budget.JobDurationExceeded()
    monkeypatch.setattr(intelligence, 'text_json', call)
    with job_budget.bound_clip_job():
        posts = jobs._posts_for('isolated-project', items, cache)
        job_budget.ensure_clip_job_budget()
    assert len(posts) == 1
    assert next(iter(posts.values()))['title'] == 'A usable title'


def test_copy_does_not_repair_transport_failures(copy_run, monkeypatch):
    from backend.services.studio import post_copy
    calls = []
    def call(*args):
        calls.append(True)
        raise RuntimeError('transport unavailable')
    posts = post_copy.build_posts('Source title', ['Source words'], ['douyin'], call=call)
    assert posts['douyin']['title'] == 'Source title'
    assert calls == [True]


@pytest.mark.parametrize('error', [JobStopped, ProjectDeleted, ServiceRestarted])
def test_copy_stops_without_retrying_or_swallowing_control_signals(copy_run, monkeypatch, error):
    _, items, cache = copy_run
    calls = []
    def stopped(*args):
        calls.append(True)
        raise error()
    monkeypatch.setattr(intelligence, 'text_json', stopped)
    with job_budget.bound_clip_job(), pytest.raises(error):
        jobs._posts_for('isolated-project', items, cache)
    assert len(calls) == 1
