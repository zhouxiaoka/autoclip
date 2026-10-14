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
    notes = []

    def boom():
        n["i"] += 1
        n["models"].append("qwen-plus")
        raise _http(429, "rate", "rate_limit_exceeded")

    manager = _manager(boom, source="user", model="qwen-plus")
    manager.note_same_provider_degrade = lambda: notes.append("noted")
    with pytest.raises(Exception, match="rate"):
        manager.call_with_retry("p")
    assert n["i"] == 3
    assert n["models"] == ["qwen-plus", "qwen-plus", "qwen-plus"]
    assert manager.settings["model_name"] == "qwen-plus"
    assert notes == []


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


def test_degrade_calls_note_same_provider_degrade_once(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    notes = []

    def flaky():
        if manager.current_provider.model_name == "qwen-plus":
            raise _http(429, "rate", "rate_limit_exceeded")
        return "ok"

    manager = _manager(flaky, source="preset", model="qwen-plus")
    manager.note_same_provider_degrade = lambda: notes.append("noted")
    assert manager.call_with_retry("p") == "ok"
    assert notes == ["noted"]


def test_degrade_works_when_r2_hook_missing_or_raises(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    def flaky():
        if manager.current_provider.model_name == "qwen-plus":
            raise _http(429, "rate", "rate_limit_exceeded")
        return "ok"

    manager = _manager(flaky, source="preset", model="qwen-plus")
    assert not hasattr(manager, "note_same_provider_degrade")
    assert manager.call_with_retry("p") == "ok"

    notes = []

    def boom():
        notes.append("called")
        raise RuntimeError("telemetry down")

    manager = _manager(flaky, source="preset", model="qwen-plus")
    manager.note_same_provider_degrade = boom
    assert manager.call_with_retry("p") == "ok"
    assert notes == ["called"]


def test_degrade_falls_back_to_increment_degrade_count(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    counts = []
    monkeypatch.setattr(
        "backend.core.llm_telemetry.increment_degrade_count",
        lambda: counts.append(1) or 1,
        raising=False,
    )

    def flaky():
        if manager.current_provider.model_name == "qwen-plus":
            raise _http(429, "rate", "rate_limit_exceeded")
        return "ok"

    manager = _manager(flaky, source="preset", model="qwen-plus")
    assert manager.call_with_retry("p") == "ok"
    assert counts == [1]


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
