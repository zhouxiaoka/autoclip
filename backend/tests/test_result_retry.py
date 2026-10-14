"""#8: retry only invalid_response / timeline_empty; stop at 2 retries."""
import pytest

from backend.core.llm_manager import LLMManager
from backend.core.result_retry import (
    MAX_ATTEMPTS,
    MAX_RETRIES,
    RETRYABLE_RESULT_TYPES,
    classify_for_retry,
    is_retryable_result,
    max_attempts_for,
)
from backend.core.upstream_errors import UpstreamErrorType, classify_upstream_error
from backend.pipeline.failures import PipelineFailure
from backend.tests.test_pipeline_failures import SRT


@pytest.fixture
def prompt_files(tmp_path):
    path = tmp_path / "outline.txt"
    path.write_text("提取大纲", encoding="utf-8")
    return {"outline": path}


def _manager(fn):
    manager = LLMManager.__new__(LLMManager)
    manager.call = lambda *a, **k: fn()
    return manager


def _http(status, message):
    error = Exception(message)
    error.status_code = status
    return error


def test_shared_classifier_marks_http_types_not_retryable_here():
    assert MAX_RETRIES == 2
    assert MAX_ATTEMPTS == 3
    assert RETRYABLE_RESULT_TYPES == {"invalid_response", "timeline_empty"}
    assert is_retryable_result("invalid_response") is True
    assert is_retryable_result("timeline_empty") is True
    assert max_attempts_for("invalid_response") == 3
    assert max_attempts_for("timeline_empty") == 3
    for status, body, kind in (
        (401, {"error": {"code": "invalid_api_key"}}, UpstreamErrorType.INVALID_KEY),
        (403, {"error": {"code": "insufficient_user_quota"}}, UpstreamErrorType.INSUFFICIENT_QUOTA),
        (429, {"error": {"code": "rate_limit_exceeded"}}, UpstreamErrorType.RATE_LIMITED),
        (500, {"error": {"type": "server_error"}}, UpstreamErrorType.UPSTREAM_UNAVAILABLE),
        (404, {"error": {"message": "does not exist"}}, UpstreamErrorType.MODEL_NOT_FOUND),
    ):
        info = classify_upstream_error(status, body)
        assert info.error_type is kind
        assert is_retryable_result(None, status=status, body=body) is False
        assert classify_for_retry(status=status, body=body) == (kind.value, False)
        assert max_attempts_for(kind.value) == 1
    assert is_retryable_result(TimeoutError("timed out")) is False
    assert is_retryable_result(ConnectionError("connection error")) is False
    assert is_retryable_result(PipelineFailure("ANALYZE", "x", code="unexpected")) is False


@pytest.mark.parametrize("code", ["invalid_response", "timeline_empty"])
def test_call_with_retry_stops_after_two_retries(monkeypatch, code):
    sleeps = []
    monkeypatch.setattr("time.sleep", sleeps.append)
    n = {"i": 0}

    def boom():
        n["i"] += 1
        raise PipelineFailure("ANALYZE", code, "", code=code)

    with pytest.raises(PipelineFailure) as caught:
        _manager(boom).call_with_retry("p")
    assert caught.value.code == code
    assert n["i"] == 3
    assert len(sleeps) == 2


@pytest.mark.parametrize("code", ["invalid_response", "timeline_empty"])
def test_caller_cannot_raise_result_retry_ceiling(monkeypatch, code):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    n = {"i": 0}

    def boom():
        n["i"] += 1
        raise PipelineFailure("ANALYZE", code, "", code=code)

    with pytest.raises(PipelineFailure):
        _manager(boom).call_with_retry("p", max_retries=10)
    assert n["i"] == 3


@pytest.mark.parametrize(
    "factory",
    [
        lambda: _http(401, "invalid api key"),
        lambda: _http(403, "insufficient_user_quota"),
        lambda: _http(429, "rate limit"),
        lambda: _http(500, "internal server error"),
        lambda: _http(404, "does not exist"),
        lambda: TimeoutError("timed out"),
        lambda: ConnectionError("connection error"),
        lambda: PipelineFailure("ANALYZE", "x", code="authentication"),
    ],
    ids=("401", "403", "429", "500", "404", "timeout", "connection", "authentication"),
)
def test_other_error_types_are_not_retried(monkeypatch, factory):
    sleeps = []
    monkeypatch.setattr("time.sleep", sleeps.append)
    n = {"i": 0}

    def boom():
        n["i"] += 1
        raise factory()

    with pytest.raises(Exception):
        _manager(boom).call_with_retry("p")
    assert n["i"] == 1
    assert sleeps == []


def test_invalid_response_recovers_on_second_retry(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    n = {"i": 0}

    def flaky():
        n["i"] += 1
        if n["i"] < 3:
            raise PipelineFailure("ANALYZE", "bad json", "", code="invalid_response")
        return "ok"

    assert _manager(flaky).call_with_retry("p") == "ok"
    assert n["i"] == 3


def test_step1_unparseable_outline_retries_twice_then_stops(tmp_path, prompt_files, monkeypatch):
    from backend.pipeline import step1_outline as step1

    calls = []

    class FakeLLM:
        def call_with_retry(self, prompt, input_data=None, **kw):
            calls.append(1)
            return "抱歉，我无法完成这个任务。"

    monkeypatch.setattr(step1, "LLMClient", lambda: FakeLLM())
    extractor = step1.OutlineExtractor(metadata_dir=tmp_path / "meta", prompt_files=prompt_files)
    srt = tmp_path / "a.srt"
    srt.write_text(SRT, encoding="utf-8")
    with pytest.raises(PipelineFailure) as caught:
        extractor.extract_outline(srt)
    assert caught.value.code == "invalid_response"
    assert len(calls) == 3


def test_step1_http_error_is_not_retried(tmp_path, prompt_files, monkeypatch):
    from backend.pipeline import step1_outline as step1

    calls = []

    class FakeLLM:
        def call_with_retry(self, prompt, input_data=None, **kw):
            calls.append(1)
            raise TimeoutError("synthetic timeout")

    monkeypatch.setattr(step1, "LLMClient", lambda: FakeLLM())
    extractor = step1.OutlineExtractor(metadata_dir=tmp_path / "meta", prompt_files=prompt_files)
    srt = tmp_path / "a.srt"
    srt.write_text(SRT, encoding="utf-8")
    with pytest.raises(PipelineFailure) as caught:
        extractor.extract_outline(srt)
    assert caught.value.code == "timeout"
    assert len(calls) == 1


def test_timeline_empty_retries_twice_then_stops(tmp_path, monkeypatch):
    from backend.pipeline.failures import PipelineFailure
    from backend.pipeline.quality import save_profile, profile_for
    from backend.tests.test_recent_feedback import (
        cue,
        prepared_extractor,
        run_prepared_step2,
        topic,
    )

    obj = prepared_extractor(tmp_path)
    (obj.srt_chunks_dir / "chunk_0.json").write_text(
        __import__("json").dumps([dict(cue(0, 10), index=1)])
    )
    save_profile(profile_for(10), tmp_path)
    calls = []

    def always(*a, **k):
        calls.append(1)
        return __import__("json").dumps([topic("short", 0, 10)])

    obj.llm_client.call_with_retry = always
    with pytest.raises(PipelineFailure) as caught:
        run_prepared_step2(obj, monkeypatch)
    assert caught.value.code == "timeline_empty"
    assert len(calls) == 3


def test_step2_call_failure_is_still_one_attempt(tmp_path, monkeypatch):
    from backend.pipeline.failures import PipelineFailure
    from backend.tests.test_recent_feedback import prepared_extractor, run_prepared_step2

    obj = prepared_extractor(tmp_path)
    calls = []

    def fail(*a, **k):
        calls.append(1)
        raise TimeoutError("synthetic timeout")

    obj.llm_client.call_with_retry = fail
    with pytest.raises(PipelineFailure) as caught:
        run_prepared_step2(obj, monkeypatch)
    assert caught.value.code == "timeout"
    assert len(calls) == 1
