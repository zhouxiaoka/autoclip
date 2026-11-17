"""Request failures must not turn into format repairs or a second analysis pipeline."""
import threading

import pytest

from backend.core import job_budget, llm_telemetry
from backend.core.failure_attribution import ModelResponseInvalid
from backend.core.project_cancellation import JobStopped, ProjectDeleted, ServiceRestarted
from backend.pipeline import clip_finder, concurrency
from backend.services import simple_pipeline_adapter as pipeline
from backend.services.studio import intelligence


class ProviderFailure(RuntimeError):
    def __init__(self, status, kind):
        super().__init__('controlled provider failure')
        self.status_code = status
        self.body = {'error': {'code': kind, 'message': kind}}


@pytest.fixture
def one_pass(tmp_path, monkeypatch):
    from backend.pipeline import step3_scoring
    srt = tmp_path / 'input.srt'
    srt.write_text('1\n00:00:00,000 --> 00:01:00,000\n一段完整的观点。\n', encoding='utf-8')
    monkeypatch.setattr(pipeline, 'emit_progress', lambda *a, **k: None)
    monkeypatch.setattr(step3_scoring, 'resolve_min_score_threshold', lambda: 0.5)
    monkeypatch.setattr(clip_finder, 'window_size', lambda: clip_finder.CLOUD_WINDOW)
    adapter = pipeline.SimplePipelineAdapter('boundary-project', 'boundary-task')
    return lambda: adapter._find_clips_in_one_pass(srt, tmp_path)


@pytest.mark.parametrize('status,kind', [(402, 'insufficient_quota'), (401, 'invalid_api_key'), (404, 'bad_endpoint')])
@pytest.mark.parametrize('redacted', [False, True])
def test_permanent_failure_is_one_request_and_never_legacy(one_pass, monkeypatch, status, kind, redacted):
    original = ProviderFailure(status, kind)
    error = llm_telemetry.log_safe_exception(original) if redacted else original
    calls = []
    def call(*args):
        calls.append(args)
        raise error
    monkeypatch.setattr(intelligence, 'text_json', call)
    with pytest.raises(type(error)) as caught:
        one_pass()
    assert caught.value is error
    assert len(calls) == 1


@pytest.mark.parametrize('error', [JobStopped(), ProjectDeleted(), ServiceRestarted(), job_budget.JobDurationExceeded()])
@pytest.mark.parametrize('redacted', [False, True])
def test_stop_signals_do_not_retry_or_fall_back(one_pass, monkeypatch, error, redacted):
    calls = []
    def call(*args):
        calls.append(args)
        raise llm_telemetry.log_safe_exception(error) if redacted else error
    monkeypatch.setattr(intelligence, 'text_json', call)
    with pytest.raises(type(error)) as caught:
        one_pass()
    assert caught.value is error
    assert len(calls) == 1


def test_format_repair_is_still_available(one_pass, monkeypatch):
    calls = []
    def call(prompt, data):
        calls.append(data)
        if len(calls) == 1:
            raise ModelResponseInvalid('not JSON')
        return {'clips': [{'start': 0, 'end': 0, 'title': '完整观点', 'score': 0.9}]}
    monkeypatch.setattr(intelligence, 'text_json', call)
    assert one_pass()[0]['generated_title'] == '完整观点'
    assert len(calls) == 2 and 'previous_error' in calls[1]


@pytest.mark.parametrize('status', [429, 503])
@pytest.mark.parametrize('recovers', [True, False])
def test_transient_failure_has_one_bounded_retry_without_legacy(one_pass, monkeypatch, status, recovers):
    error = ProviderFailure(status, 'rate_limit_exceeded' if status == 429 else 'unavailable')
    calls = []
    monkeypatch.setattr(clip_finder, 'backoff_seconds', lambda *a: 0)
    def call(prompt, data):
        calls.append(data)
        if len(calls) == 1 or not recovers:
            raise error
        return {'clips': [{'start': 0, 'end': 0, 'title': '完整观点', 'score': 0.9}]}
    monkeypatch.setattr(intelligence, 'text_json', call)
    if recovers:
        assert one_pass()[0]['generated_title'] == '完整观点'
    else:
        with pytest.raises(ProviderFailure) as caught:
            one_pass()
        assert caught.value is error
    assert len(calls) == 2 and calls[0] == calls[1]
    concurrency.reset_limiter()


def test_format_then_transport_failure_does_not_reset_retry_budget(one_pass, monkeypatch):
    calls = []
    def call(*args):
        calls.append(args)
        if len(calls) == 1:
            return {'invalid': True}
        raise ProviderFailure(503, 'unavailable')
    monkeypatch.setattr(intelligence, 'text_json', call)
    with pytest.raises(ProviderFailure):
        one_pass()
    assert len(calls) == 2


def test_spent_job_budget_stops_before_retry(one_pass, monkeypatch):
    now = [100.0]
    calls = []
    monkeypatch.setattr(job_budget.time, 'monotonic', lambda: now[0])
    def call(*args):
        calls.append(args)
        now[0] += 61
        raise TimeoutError('controlled request timeout')
    monkeypatch.setattr(intelligence, 'text_json', call)
    with job_budget.bound_clip_job(60), pytest.raises(job_budget.JobDurationExceeded):
        one_pass()
    assert len(calls) == 1


def test_cancel_during_long_backoff_is_checked_promptly(one_pass, monkeypatch):
    waits, calls = [], []
    error = ProviderFailure(429, 'rate_limit_exceeded')
    error.retry_after = 120
    stopped = JobStopped()
    def checkpoint():
        if waits:
            raise stopped
    def wait(_event, seconds):
        waits.append(seconds)
        return False
    def call(*args):
        calls.append(args)
        raise error
    monkeypatch.setattr(clip_finder, 'checkpoint', checkpoint)
    monkeypatch.setattr(threading.Event, 'wait', wait)
    monkeypatch.setattr(intelligence, 'text_json', call)
    with pytest.raises(JobStopped) as caught:
        one_pass()
    assert caught.value is stopped
    assert len(calls) == 1
    assert waits and max(waits) <= 0.25
    concurrency.reset_limiter()


def test_terminal_window_failure_does_not_start_queued_windows(monkeypatch):
    monkeypatch.setenv('AUTOCLIP_LLM_CONCURRENCY', '2')
    concurrency.reset_limiter()
    calls = []
    lock = threading.Lock()
    error = ProviderFailure(402, 'insufficient_quota')
    def call(item):
        with lock:
            calls.append(item)
        raise error
    with pytest.raises(ProviderFailure) as caught:
        concurrency.map_chunks(call, range(30), stop_on_error=True)
    assert caught.value is error
    assert 1 <= len(calls) <= 2
    assert concurrency.map_chunks(lambda n: n, [1, 2], stop_on_error=True) == [1, 2]
