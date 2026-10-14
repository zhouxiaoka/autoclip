"""R1: same-provider preset degrade, frequency-only, 6-call chunk cap."""
from types import SimpleNamespace

import pytest

from backend.core import llm_degrade as degrade
from backend.core.llm_manager import LLMManager
from backend.core.llm_telemetry import sanitize_llm_request_properties


def _http(status, message, code=None, extra=None):
    error = Exception(message)
    error.status_code = status
    body = extra if extra is not None else (
        {"error": {"code": code, "message": message}} if code else {"error": {"message": message}}
    )
    error.body = body
    return error


def _manager(fn, *, source="user", provider="dashscope", model="qwen-plus"):
    manager = LLMManager.__new__(LLMManager)
    manager.settings = {
        "model_source": source,
        "model_name": model,
        "connection_provider": provider,
        "llm_provider": "openai",
    }
    manager.current_provider = SimpleNamespace(model_name=model)
    manager.call = lambda *a, **k: fn()
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


def test_user_source_never_degrades(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    n = {"i": 0, "models": []}

    def boom():
        n["i"] += 1
        n["models"].append("qwen-plus")
        raise _http(429, "rate", "rate_limit_exceeded")

    manager = _manager(boom, source="user", model="qwen-plus")
    with pytest.raises(Exception, match="rate"):
        manager.call_with_retry("p")
    assert n["i"] == 3
    assert n["models"] == ["qwen-plus", "qwen-plus", "qwen-plus"]
    assert manager.settings["model_name"] == "qwen-plus"


def test_preset_degrades_on_rate_limit_exceeded(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    seen = []

    def flaky():
        name = manager.current_provider.model_name
        seen.append(name)
        if name == "qwen-plus":
            raise _http(429, "rate", "rate_limit_exceeded")
        return f"ok:{name}"

    manager = _manager(flaky, source="preset", model="qwen-plus")
    assert manager.call_with_retry("p") == "ok:qwen3.8-flash"
    assert seen[0] == "qwen-plus"
    assert "qwen3.8-flash" in seen
    assert manager.settings["model_name"] == "qwen3.8-flash"


def test_preset_degrades_on_limit_requests(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    seen = []

    def flaky():
        name = manager.current_provider.model_name
        seen.append(name)
        if name == "qwen-plus":
            raise _http(429, "Throttling", "limit_requests")
        return "ok"

    manager = _manager(flaky, source="preset", model="qwen-plus")
    assert manager.call_with_retry("p") == "ok"
    assert seen[0] == "qwen-plus"
    assert any(name != "qwen-plus" for name in seen)


def test_preset_does_not_degrade_on_quota(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    seen = []

    def boom():
        seen.append(manager.current_provider.model_name)
        raise _http(429, "You exceeded your current quota", "insufficient_quota")

    manager = _manager(boom, source="preset", model="qwen-plus")
    with pytest.raises(Exception, match="quota"):
        manager.call_with_retry("p")
    assert seen == ["qwen-plus"]
    assert manager.settings["model_name"] == "qwen-plus"


def test_chunk_budget_caps_at_six_across_candidates_and_retries(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    n = {"i": 0}

    def always():
        n["i"] += 1
        raise _http(429, "rate", "rate_limit_exceeded")

    manager = _manager(always, source="preset", model="qwen-plus")
    with pytest.raises(Exception, match="rate"):
        manager.call_with_retry("p")
    assert n["i"] == 6
    assert manager.settings["model_name"] == "qwen-plus"


def test_failed_degrade_does_not_persist_fallback(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    writes = []

    def always():
        raise _http(429, "rate", "rate_limit_exceeded")

    manager = _manager(always, source="preset", model="qwen-plus")
    manager._save_settings = lambda: writes.append("saved")
    with pytest.raises(Exception):
        manager.call_with_retry("p")
    assert manager.settings["model_name"] == "qwen-plus"
    assert writes == []


def test_preset_does_not_degrade_on_server_error(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    seen = []

    def boom():
        seen.append(manager.current_provider.model_name)
        raise _http(500, "internal server error")

    manager = _manager(boom, source="preset", model="qwen-plus")
    with pytest.raises(Exception, match="internal"):
        manager.call_with_retry("p")
    assert set(seen) == {"qwen-plus"}
    assert manager.settings["model_name"] == "qwen-plus"


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
    manager = _manager(lambda: calls.append(1) or "ok")
    with degrade.chunk_call_budget() as budget:
        for _ in range(degrade.CHUNK_CALL_CAP):
            assert manager.call_with_retry("fixture") == "ok"
        with pytest.raises(RuntimeError, match="budget exhausted"):
            manager.call_with_retry("fixture")
        assert budget.used == degrade.CHUNK_CALL_CAP
    assert len(calls) == degrade.CHUNK_CALL_CAP
    # A new chunk owns a fresh ledger.
    assert manager.call_with_retry("next fixture") == "ok"


@pytest.mark.parametrize("remaining", [0, 1])
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
        # The manager has reserved the initial call already.
        for _ in range(degrade.CHUNK_CALL_CAP - remaining):
            assert degrade.consume_chunk_call()
        if remaining:
            assert provider.call("fixture", max_tokens=1).content == "ok"
        else:
            with pytest.raises(Exception) as caught:
                provider.call("fixture", max_tokens=1)
            assert caught.value is error
        assert budget.used == degrade.CHUNK_CALL_CAP
    assert len(calls) == 1 + remaining
    assert "private-path" not in caplog.text


def test_retry_failure_log_stays_redacted(monkeypatch, caplog):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    def fail():
        raise _http(500, "https://fixture.example/private-path?key=fixture-private")

    with pytest.raises(Exception):
        _manager(fail).call_with_retry("fixture")
    assert "fixture-private" not in caplog.text
    assert "private-path" not in caplog.text
    assert "https://" not in caplog.text
