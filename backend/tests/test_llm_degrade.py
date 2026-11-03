"""same-provider preset degrade, frequency-only, 6-HTTP chunk cap."""
import json
import threading
from types import SimpleNamespace

import pytest

from backend.core import llm_degrade as degrade
from backend.core.llm_manager import LLMManager
from backend.core.llm_providers import LLM_SDK_MAX_RETRIES
from backend.core.llm_telemetry import sanitize_llm_request_properties
from backend.pipeline import concurrency


def _http(status, message, code=None, extra=None):
    error = Exception(message)
    error.status_code = status
    body = extra if extra is not None else (
        {"error": {"code": code, "message": message}} if code else {"error": {"message": message}}
    )
    error.body = body
    return error


def _model_of(*_args, **kwargs):
    return kwargs.get("model") or degrade.bound_request_model()


def _manager(fn, *, source="user", provider="dashscope", model="qwen-plus"):
    manager = LLMManager.__new__(LLMManager)
    manager.settings = {
        "model_source": source,
        "model_name": model,
        "connection_provider": provider,
        "llm_provider": "openai",
    }
    manager.current_provider = SimpleNamespace(model_name=model)
    manager._reload_if_settings_changed = lambda: None

    def call_stub(*args, **kwargs):
        return fn(*args, **kwargs)

    manager.call = call_stub
    return manager


def test_missing_source_is_user():
    assert degrade.resolve_model_source({}) == "user"
    assert degrade.resolve_model_source(None) == "user"
    assert degrade.resolve_model_source({"model_source": "preset"}) == "preset"
    assert degrade.resolve_model_source({}, SimpleNamespace(source="preset")) == "preset"
    assert degrade.resolve_model_source({}, SimpleNamespace(model_source="user")) == "user"


def test_candidate_order_is_sponsor_popular_other():
    assert degrade.order_candidates([
        ("other-m", "other"),
        ("sponsor-m", "sponsor"),
        ("popular-m", "popular"),
    ]) == ["sponsor-m", "popular-m", "other-m"]
    assert degrade.provider_group("api88") == "sponsor"
    assert degrade.provider_group("infistar") == "sponsor"
    assert degrade.provider_group("apimart") == "sponsor"
    assert degrade.provider_group("dashscope") == "popular"
    assert degrade.provider_group("compatible") == "other"


def test_same_provider_candidates_never_leave_provider():
    names = degrade.same_provider_candidates("dashscope", "qwen-plus")
    assert names[0] == "qwen-plus"
    assert "qwen3.8-flash" in names
    assert all(not item.startswith("gpt-") for item in names)
    assert all(item != "deepseek-flash" for item in names)
    assert len(names) <= degrade.MAX_CANDIDATES


def test_user_source_lists_only_current_model():
    assert degrade.candidates_for_call({
        "model_source": "user",
        "model_name": "qwen-plus",
        "connection_provider": "dashscope",
    }) == ("qwen-plus",)


def test_frequency_codes_degrade_quota_does_not():
    assert degrade.should_degrade_to_next(_http(429, "rate", "rate_limit_exceeded")) is True
    assert degrade.should_degrade_to_next(_http(429, "限流", "limit_requests")) is True
    assert degrade.should_degrade_to_next(_http(429, "Limit.Requests", "Limit.Requests")) is True
    assert degrade.should_degrade_to_next(
        _http(429, "You exceeded your current quota", "insufficient_quota")
    ) is False
    assert degrade.should_degrade_to_next(
        _http(403, "余额不足", "insufficient_user_quota")
    ) is False
    assert degrade.should_degrade_to_next(_http(429, "rate limit")) is False
    assert degrade.should_degrade_to_next(_http(500, "internal server error")) is False
    assert degrade.should_degrade_to_next(_http(401, "invalid api key")) is False


def test_http_attempts_include_sdk_retries():
    assert degrade.http_attempts_per_call() == 1 + LLM_SDK_MAX_RETRIES
    assert 1 + LLM_SDK_MAX_RETRIES == 2
    assert degrade.CHUNK_CALL_CAP == 6


def test_user_source_never_degrades(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    n = {"i": 0, "models": []}
    notes = []

    def boom(*_a, **k):
        n["i"] += 1
        n["models"].append(_model_of(*_a, **k) or "qwen-plus")
        raise _http(429, "rate", "rate_limit_exceeded")

    manager = _manager(boom, source="user", model="qwen-plus")
    manager.note_same_provider_degrade = lambda: notes.append("noted")
    with pytest.raises(Exception, match="rate"):
        manager.call_with_retry("p")
    assert n["i"] == 3
    assert n["models"] == ["qwen-plus", "qwen-plus", "qwen-plus"]
    assert manager.settings["model_name"] == "qwen-plus"
    assert manager.current_provider.model_name == "qwen-plus"
    assert notes == []


def test_preset_degrades_on_rate_limit_exceeded(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    seen = []

    def flaky(*_a, **k):
        name = _model_of(*_a, **k) or manager.settings["model_name"]
        seen.append(name)
        if name == "qwen-plus":
            raise _http(429, "rate", "rate_limit_exceeded")
        return f"ok:{name}"

    manager = _manager(flaky, source="preset", model="qwen-plus")
    assert manager.call_with_retry("p") == "ok:qwen3.8-flash"
    assert seen[0] == "qwen-plus"
    assert "qwen3.8-flash" in seen
    assert manager.settings["model_name"] == "qwen-plus"
    assert manager.current_provider.model_name == "qwen-plus"


def test_preset_degrades_on_limit_requests(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    seen = []

    def flaky(*_a, **k):
        name = _model_of(*_a, **k) or manager.settings["model_name"]
        seen.append(name)
        if name == "qwen-plus":
            raise _http(429, "Throttling", "limit_requests")
        return "ok"

    manager = _manager(flaky, source="preset", model="qwen-plus")
    assert manager.call_with_retry("p") == "ok"
    assert seen[0] == "qwen-plus"
    assert any(name != "qwen-plus" for name in seen)
    assert manager.settings["model_name"] == "qwen-plus"
    assert manager.current_provider.model_name == "qwen-plus"


def test_preset_does_not_degrade_on_quota(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    seen = []

    def boom(*_a, **k):
        seen.append(_model_of(*_a, **k) or manager.settings["model_name"])
        raise _http(429, "You exceeded your current quota", "insufficient_quota")

    manager = _manager(boom, source="preset", model="qwen-plus")
    with pytest.raises(Exception, match="quota"):
        manager.call_with_retry("p")
    assert seen == ["qwen-plus"]
    assert manager.settings["model_name"] == "qwen-plus"


def test_chunk_budget_caps_http_including_sdk_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    n = {"i": 0}

    def always(*_a, **_k):
        n["i"] += 1
        raise _http(429, "rate", "rate_limit_exceeded")

    manager = _manager(always, source="preset", model="qwen-plus")
    with pytest.raises(Exception, match="rate"):
        manager.call_with_retry("p")
    # 6 HTTP / (1 + SDK retry) = 3 manager calls; #358 budget is also 3 and not reset.
    assert n["i"] == degrade.CHUNK_CALL_CAP // degrade.http_attempts_per_call()
    assert n["i"] == 3
    assert manager.settings["model_name"] == "qwen-plus"


def test_358_outer_budget_is_shared_across_candidates(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    seen = []

    def always(*_a, **k):
        seen.append(_model_of(*_a, **k) or "qwen-plus")
        raise _http(429, "rate", "rate_limit_exceeded")

    manager = _manager(always, source="preset", model="qwen-plus")
    with pytest.raises(Exception, match="rate"):
        manager.call_with_retry("p")
    assert len(seen) == 3
    assert seen[0] == "qwen-plus"
    assert len(set(seen)) > 1
    assert manager.settings["model_name"] == "qwen-plus"
    assert manager.current_provider.model_name == "qwen-plus"


def test_failed_degrade_does_not_persist_fallback(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    writes = []

    def always(*_a, **_k):
        raise _http(429, "rate", "rate_limit_exceeded")

    manager = _manager(always, source="preset", model="qwen-plus")
    manager._save_settings = lambda: writes.append("saved")
    with pytest.raises(Exception):
        manager.call_with_retry("p")
    assert manager.settings["model_name"] == "qwen-plus"
    assert manager.current_provider.model_name == "qwen-plus"
    assert writes == []


def test_preset_does_not_degrade_on_server_error(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    seen = []

    def boom(*_a, **k):
        seen.append(_model_of(*_a, **k) or manager.settings["model_name"])
        raise _http(500, "internal server error")

    manager = _manager(boom, source="preset", model="qwen-plus")
    with pytest.raises(Exception, match="internal"):
        manager.call_with_retry("p")
    assert set(seen) == {"qwen-plus"}
    assert manager.settings["model_name"] == "qwen-plus"


def test_parallel_chunks_do_not_mutate_shared_model(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    concurrency.reset_limiter()
    monkeypatch.setenv("AUTOCLIP_LLM_CONCURRENCY", "2")
    seen = []
    lock = threading.Lock()

    def flaky(*_a, **k):
        name = _model_of(*_a, **k) or manager.settings["model_name"]
        with lock:
            seen.append((
                threading.current_thread().name,
                name,
                manager.settings["model_name"],
                manager.current_provider.model_name,
            ))
        if name == "qwen-plus":
            raise _http(429, "rate", "rate_limit_exceeded")
        return f"ok:{name}"

    manager = _manager(flaky, source="preset", model="qwen-plus")
    assert concurrency.map_chunks(lambda prompt: manager.call_with_retry(prompt), ["a", "b"]) == [
        "ok:qwen3.8-flash",
        "ok:qwen3.8-flash",
    ]
    assert manager.settings["model_name"] == "qwen-plus"
    assert manager.current_provider.model_name == "qwen-plus"
    assert all(row[2] == "qwen-plus" and row[3] == "qwen-plus" for row in seen)
    concurrency.reset_limiter()


def test_degrade_calls_note_same_provider_degrade_once(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    notes = []

    def flaky(*_a, **k):
        if (_model_of(*_a, **k) or manager.settings["model_name"]) == "qwen-plus":
            raise _http(429, "rate", "rate_limit_exceeded")
        return "ok"

    manager = _manager(flaky, source="preset", model="qwen-plus")
    manager.note_same_provider_degrade = lambda: notes.append("noted")
    assert manager.call_with_retry("p") == "ok"
    assert notes == ["noted"]


def test_degrade_works_when_r2_hook_missing_or_raises(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    def flaky(*_a, **k):
        if (_model_of(*_a, **k) or manager.settings["model_name"]) == "qwen-plus":
            raise _http(429, "rate", "rate_limit_exceeded")
        return "ok"

    manager = _manager(flaky, source="preset", model="qwen-plus")
    # The integrated manager has the hook; explicitly exercise its absence.
    manager.note_same_provider_degrade = None
    assert manager.call_with_retry("p") == "ok"

    notes = []
    backup = []
    monkeypatch.setattr(
        "backend.core.llm_telemetry.increment_degrade_count",
        lambda: backup.append(1) or 1,
        raising=False,
    )

    def boom():
        notes.append("called")
        raise RuntimeError("telemetry down")

    manager = _manager(flaky, source="preset", model="qwen-plus")
    manager.note_same_provider_degrade = boom
    assert manager.call_with_retry("p") == "ok"
    assert notes == ["called"]
    assert backup == [1]


def test_degrade_falls_back_to_increment_degrade_count(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    counts = []
    monkeypatch.setattr(
        "backend.core.llm_telemetry.increment_degrade_count",
        lambda: counts.append(1) or 1,
        raising=False,
    )

    def flaky(*_a, **k):
        if (_model_of(*_a, **k) or manager.settings["model_name"]) == "qwen-plus":
            raise _http(429, "rate", "rate_limit_exceeded")
        return "ok"

    manager = _manager(flaky, source="preset", model="qwen-plus")
    assert manager.call_with_retry("p") == "ok"
    assert counts == [1]


def test_real_http_calls_under_concurrency_stay_within_chunk_cap(monkeypatch):
    import httpx
    import openai

    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    concurrency.reset_limiter()
    monkeypatch.setenv("AUTOCLIP_LLM_CONCURRENCY", "2")

    from backend.core.llm_providers import OpenAIProvider

    hits: list[tuple[str, str]] = []
    lock = threading.Lock()

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        prompt = ""
        messages = body.get("messages") or []
        if messages:
            prompt = str(messages[0].get("content") or "")
        with lock:
            hits.append((prompt, str(body.get("model") or "")))
            assert manager.settings["model_name"] == "qwen-plus"
            assert manager.current_provider.model_name == "qwen-plus"
        return httpx.Response(
            429,
            json={"error": {"code": "rate_limit_exceeded", "message": "rate"}},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.api_key = "sk-test"
    provider.model_name = "qwen-plus"
    provider.kwargs = {}
    provider.base_url = "https://llm.test/v1"
    provider.is_custom_endpoint = True
    provider.client = openai.OpenAI(
        api_key="sk-test",
        base_url="https://llm.test/v1",
        max_retries=LLM_SDK_MAX_RETRIES,
        http_client=http_client,
    )

    manager = LLMManager.__new__(LLMManager)
    manager.settings = {
        "model_source": "preset",
        "model_name": "qwen-plus",
        "connection_provider": "dashscope",
        "llm_provider": "openai",
        "openai_base_url": "https://llm.test/v1",
    }
    manager.current_provider = provider
    manager._reload_if_settings_changed = lambda: None
    manager.get_current_provider_info = lambda: {
        "provider": "dashscope",
        "model": "qwen-plus",
        "base_url": "https://llm.test/v1",
    }

    with pytest.raises(Exception):
        concurrency.map_chunks(
            lambda prompt: manager.call_with_retry(prompt),
            ["chunk-a", "chunk-b"],
        )

    by_chunk: dict[str, list[str]] = {"chunk-a": [], "chunk-b": []}
    for prompt, model in hits:
        for key in by_chunk:
            if key in prompt:
                by_chunk[key].append(model)
    assert len(by_chunk["chunk-a"]) == degrade.CHUNK_CALL_CAP
    assert len(by_chunk["chunk-b"]) == degrade.CHUNK_CALL_CAP
    assert len(hits) == degrade.CHUNK_CALL_CAP * 2
    assert manager.settings["model_name"] == "qwen-plus"
    assert provider.model_name == "qwen-plus"
    concurrency.reset_limiter()


def test_degrade_log_and_telemetry_omit_secrets():
    props = sanitize_llm_request_properties({
        "provider": "dashscope",
        "model": "qwen-plus",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-secret-value",
        "prompt": "用户字幕不应出现",
        "title": "私密标题",
    })
    blob = str(props)
    assert "sk-secret-value" not in blob
    assert "用户字幕" not in blob
    assert "私密标题" not in blob
    assert "https://dashscope.aliyuncs.com" not in blob
    assert props.get("base_url_host") == "dashscope.aliyuncs.com"
    assert "api_key" not in props
    assert "prompt" not in props


def test_nested_retry_calls_share_chunk_lifecycle_budget():
    calls = []
    manager = _manager(lambda *_args, **_kwargs: calls.append(1) or "ok")
    with degrade.chunk_call_budget() as budget:
        for _ in range(degrade.CHUNK_CALL_CAP // degrade.http_attempts_per_call()):
            assert manager.call_with_retry("fixture") == "ok"
        with pytest.raises(RuntimeError, match="budget exhausted"):
            manager.call_with_retry("fixture")
        assert budget.used == degrade.CHUNK_CALL_CAP
    assert len(calls) == degrade.CHUNK_CALL_CAP // degrade.http_attempts_per_call()
    # A new chunk owns a fresh ledger.
    assert manager.call_with_retry("next fixture") == "ok"


@pytest.mark.parametrize("remaining", [0, 1, 1 + LLM_SDK_MAX_RETRIES])
def test_token_parameter_resend_deducts_budget_before_sending(remaining, caplog):
    from backend.core.llm_providers import OpenAIProvider

    calls = []
    error = _http(400, "Use max_completion_tokens instead of max_tokens")

    def create(**payload):
        calls.append(payload)
        if "max_tokens" in payload:
            raise error
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content="ok"), finish_reason="stop",
        )], usage=None)

    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.api_key = "test-fixture"
    provider.model_name = "fixture-model"
    provider.base_url = "https://fixture.example/private-path"
    provider.client = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=create),
    ))
    with degrade.chunk_call_budget() as budget:
        # Seed HTTP units: the compatibility resend reserves its SDK retries too.
        for _ in range(degrade.CHUNK_CALL_CAP - remaining):
            assert degrade.consume_chunk_call(cost=1)
        allowed = remaining >= degrade.http_attempts_per_call()
        if allowed:
            assert provider.call("fixture", max_tokens=1).content == "ok"
        else:
            with pytest.raises(Exception) as caught:
                provider.call("fixture", max_tokens=1)
            assert caught.value.status_code == error.status_code
            assert degrade.error_code_tokens(caught.value) == degrade.error_code_tokens(error)
            assert str(error) not in str(caught.value)
        assert budget.used == degrade.CHUNK_CALL_CAP - remaining + (degrade.http_attempts_per_call() if allowed else 0)
    assert len(calls) == 1 + int(allowed)
    assert "private-path" not in caplog.text


def test_retry_failure_log_stays_redacted(monkeypatch, caplog):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    def fail(*_args, **_kwargs):
        raise _http(500, "https://fixture.example/private-path?key=fixture-private")

    with pytest.raises(Exception):
        _manager(fail).call_with_retry("fixture")
    assert "fixture-private" not in caplog.text
    assert "private-path" not in caplog.text
    assert "https://" not in caplog.text
