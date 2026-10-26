"""A clip/generation job stops at a wall-clock cap instead of stacking 600s provider reads."""
import asyncio
import time

import pytest

from backend.core.failure_codes import sentence, user_visible_error
from backend.core.job_budget import (
    CLIP_JOB_BUDGET_SEC,
    JobDurationExceeded,
    bound_clip_job,
    budget_expired,
    clip_job_read_timeout,
    ensure_clip_job_budget,
    pause_clip_job_budget,
)
from backend.core.llm_retry import classify_for_retry
from backend.core.project_cancellation import checkpoint
from backend.core.sentry_setup import studio_error_code
from backend.core.upstream_errors import UpstreamErrorType
from backend.tests.test_result_retry import _manager


def test_env_budget_overrides_the_default_and_is_still_a_timeout(monkeypatch):
    """AUTOCLIP_CLIP_JOB_BUDGET_SEC is the knob a desktop repro uses to force the cap."""
    from backend.core.job_budget import clip_job_budget_seconds

    monkeypatch.setenv('AUTOCLIP_CLIP_JOB_BUDGET_SEC', '1.5')
    assert clip_job_budget_seconds() == 1.5
    for raw in ('0', '-3', 'nope', ''):
        monkeypatch.setenv('AUTOCLIP_CLIP_JOB_BUDGET_SEC', raw)
        assert clip_job_budget_seconds() == float(CLIP_JOB_BUDGET_SEC)
    monkeypatch.setenv('AUTOCLIP_CLIP_JOB_BUDGET_SEC', '0.05')
    with bound_clip_job():
        time.sleep(0.08)
        with pytest.raises(JobDurationExceeded):
            ensure_clip_job_budget()
    assert studio_error_code(JobDurationExceeded()) == 'timeout'


def test_default_cap_covers_one_slow_read_but_not_an_unbounded_retry_stack():
    assert CLIP_JOB_BUDGET_SEC == 20 * 60
    # One provider read is 600s and the SDK may retry it once. The cap stops the next one.
    from backend.core.llm_providers import LLM_READ_TIMEOUT_SEC, LLM_SDK_MAX_RETRIES
    assert CLIP_JOB_BUDGET_SEC >= LLM_READ_TIMEOUT_SEC * (1 + LLM_SDK_MAX_RETRIES)
    assert CLIP_JOB_BUDGET_SEC < LLM_READ_TIMEOUT_SEC * (1 + LLM_SDK_MAX_RETRIES) * 3


def test_checkpoint_stops_a_job_that_has_used_its_budget():
    checkpoint()  # no job: cancellation rules only
    with bound_clip_job(0):
        with pytest.raises(JobDurationExceeded):
            checkpoint()
    checkpoint()


def test_pause_does_not_spend_the_budget_on_local_work():
    with bound_clip_job(0.05):
        with pause_clip_job_budget():
            time.sleep(0.08)
            ensure_clip_job_budget()
        ensure_clip_job_budget()
    assert budget_expired() is False


def test_read_timeout_shrinks_to_the_time_left():
    assert clip_job_read_timeout(600) == 600
    with bound_clip_job(12):
        assert 0 < clip_job_read_timeout(600) <= 12
    with bound_clip_job(0):
        with pytest.raises(JobDurationExceeded):
            clip_job_read_timeout(600)


def test_duration_cap_is_a_timeout_the_user_can_read_and_is_not_retried():
    error = JobDurationExceeded()
    assert studio_error_code(error) == "timeout"
    assert "时间上限" in user_visible_error(error)
    assert user_visible_error(error) != sentence("unknown")
    info, _status, _retry_after = classify_for_retry(error)
    assert info.error_type is UpstreamErrorType.UNKNOWN
    assert info.retryable is False
    calls = []

    def boom():
        calls.append(1)
        raise JobDurationExceeded()

    with pytest.raises(JobDurationExceeded):
        _manager(boom).call_with_retry("p")
    assert calls == [1]


def test_an_expired_budget_does_not_start_another_provider_call():
    def boom():
        raise AssertionError("provider")

    with bound_clip_job(0):
        with pytest.raises(JobDurationExceeded):
            _manager(boom).call_with_retry("p")


def test_pipeline_reports_the_cap_as_a_failed_timeout(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AUTOCLIP_APP_DIR", str(tmp_path))
    from backend.services.simple_pipeline_adapter import create_simple_pipeline_adapter

    adapter = create_simple_pipeline_adapter("p-budget", "t-budget")
    with bound_clip_job(0):
        result = asyncio.run(adapter.process_project_sync(str(tmp_path / "in.mp4"), None, clips_only=True))
    assert result["status"] == "failed"
    assert result["error_code"] == "timeout"
    assert result["stage"] == "ANALYZE"
    assert "时间上限" in result["error"]


def test_openai_call_uses_the_remaining_budget_as_its_read_timeout(monkeypatch):
    import sys
    import types
    import httpx
    from backend.core import llm_providers as lp

    calls = []

    class Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            usage = type("U", (), {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2})()
            message = type("M", (), {"content": "ok"})()
            choice = type("C", (), {"message": message, "finish_reason": "stop"})()
            return type("R", (), {"choices": [choice], "usage": usage})()

    class Client:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": Completions()})()

    module = types.ModuleType("openai")
    module.OpenAI = Client
    monkeypatch.setitem(sys.modules, "openai", module)
    provider = lp.OpenAIProvider(api_key="sk-test", model_name="gpt-4o-mini", base_url="https://example.test/v1")
    with bound_clip_job(9):
        provider.call("hi")
    timeout = calls[0]["timeout"]
    assert calls[0]["stream"] is True
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.read <= 9


def test_connection_test_rejects_an_empty_answer(monkeypatch):
    from backend.core import llm_providers as lp

    class Completions:
        def create(self, **kwargs):
            message = type("M", (), {"content": "   "})()
            choice = type("C", (), {"message": message, "finish_reason": "stop"})()
            return type("R", (), {"choices": [choice], "usage": None})()

    provider = lp.OpenAIProvider.__new__(lp.OpenAIProvider)
    provider.api_key = "sk-test-key-123456"
    provider.model_name = "gpt-4o-mini"
    provider.base_url = ""
    provider.is_custom_endpoint = False
    provider.client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    assert provider.test_connection() is False
