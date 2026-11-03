"""成功率埋点字段脱敏：只留域名与枚举，不含 key / 完整 URL / 用户内容。"""
from __future__ import annotations

import contextvars
import threading
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import pytest

from backend.core import llm_telemetry as telemetry
from backend.core.upstream_errors import UpstreamErrorType

pytestmark = pytest.mark.stdlib_only

SECRET = "sk-live-secret-should-never-leak"
PROMPT = "用户口播：把这段广告词发到抖音"


def test_hostname_keeps_domain_and_collapses_local():
    assert telemetry.hostname_of_base_url("https://88api.ai/v1/chat/completions") == "88api.ai"
    assert telemetry.hostname_of_base_url("https://api.deepseek.com") == "api.deepseek.com"
    assert telemetry.hostname_of_base_url(f"https://user:{SECRET}@generativelanguage.googleapis.com/v1beta") == "generativelanguage.googleapis.com"
    assert telemetry.hostname_of_base_url("http://127.0.0.1:11434/v1") == "local"
    assert telemetry.hostname_of_base_url("http://localhost:1234/v1") == "local"
    assert telemetry.hostname_of_base_url("http://192.168.1.10:8080/v1") == "local"
    assert telemetry.hostname_of_base_url("http://[::1]:11434/v1") == "local"
    assert telemetry.hostname_of_base_url("https://ollama.local/v1") == "local"
    assert telemetry.hostname_of_base_url(SECRET) is None
    assert telemetry.hostname_of_base_url("") is None
    assert telemetry.hostname_of_base_url(None) is None


def test_sanitize_model_and_provider():
    assert telemetry.sanitize_model("gpt-4o-mini") == "gpt-4o-mini"
    assert telemetry.sanitize_model("Qwen/Qwen2.5-7B-Instruct") == "Qwen/Qwen2.5-7B-Instruct"
    assert telemetry.sanitize_model("qwen2.5:7b") == "qwen2.5:7b"
    assert telemetry.sanitize_model("has space") == "redacted"
    assert telemetry.sanitize_model("a" * 65) == "redacted"
    assert telemetry.sanitize_model(PROMPT) == "redacted"
    assert telemetry.sanitize_provider("API88") == "api88"
    assert telemetry.sanitize_provider("siliconflow") == "siliconflow"  # every preset is its own slug
    assert telemetry.sanitize_provider("whisper_local", allow_asr=True) == "whisper_local"
    assert telemetry.sanitize_provider("whisper_local") is None


def test_sanitize_model_rejects_secrets_disguised_as_ids():
    assert telemetry.sanitize_model("https://api.openai.com/v1") == "redacted"
    assert telemetry.sanitize_model("https://api.openai.com/v1/chat/completions?key=sk-live") == "redacted"
    assert telemetry.sanitize_model(SECRET) == "redacted"
    assert telemetry.sanitize_model("sk-proj-abc123def456") == "redacted"
    assert telemetry.sanitize_model("api.openai.com/v1/models") == "redacted"
    assert telemetry.sanitize_model("用户口播把这段广告词发到抖音") == "redacted"
    assert telemetry.sanitize_model(f"gpt-4o-mini {SECRET}") == "redacted"
    assert telemetry.sanitize_model("") is None
    assert telemetry.sanitize_model(None) is None


def test_sanitize_exception_text_keeps_host_drops_keys_and_body():
    raw = (
        f"POST https://api.openai.com/v1/chat/completions Authorization: Bearer {SECRET} "
        f"{PROMPT} token={SECRET}"
    )
    cleaned = telemetry.sanitize_exception_text(raw)
    assert SECRET not in cleaned
    assert "sk-" not in cleaned.lower()
    assert PROMPT not in cleaned
    assert "https://" not in cleaned
    assert "/chat/completions" not in cleaned
    assert "api.openai.com" in cleaned
    assert telemetry.sanitize_exception_text(RuntimeError(raw)) == cleaned


@pytest.mark.parametrize("name", ["AIza" + "A" * 35, "xai-" + "a" * 48])
def test_sanitize_model_rejects_google_and_xai_credentials(name):
    assert telemetry.sanitize_model(name) == "redacted"
    for sanitize in (telemetry.sanitize_llm_request_properties, telemetry.sanitize_run_properties):
        assert sanitize({"model": name})["model"] == "redacted"


@pytest.mark.parametrize("field", [
    "api_key", "apiKey", "key", "token", "authorization", "x-api-key", "x-goog-api-key",
])
@pytest.mark.parametrize("quote", ['"', "'"])
@pytest.mark.parametrize("value", ["fixture-credential", "Bearer fixture-credential", "fixture with spaces"])
def test_sanitize_exception_redacts_quoted_credential_fields(field, quote, value):
    raw = f"request failed: {{{quote}{field}{quote}: {quote}{value}{quote}}} status=401"
    cleaned = telemetry.sanitize_exception_text(raw)
    assert "fixture" not in cleaned
    assert "Bearer" not in cleaned
    assert cleaned == "invalid_key"


@pytest.mark.parametrize("raw", [
    "Bearer fixture-credential",
    "Authorization: Bearer fixture-credential",
    "authorization=Bearer fixture-credential",
    "x-goog-api-key: fixture-credential",
    "X-Goog-Api-Key=fixture-credential",
    "x-api-key: fixture-credential",
    '"api_key": "fixture-escaped-\\\"credential"',
    "'api_key': 'fixture-escaped-\\'credential'",
    "AIza" + "A" * 35,
    "xai-" + "a" * 48,
])
def test_sanitize_exception_redacts_whole_credential(raw):
    assert telemetry.sanitize_exception_text(raw) == "unknown"


def test_llm_request_properties_drop_secrets_and_user_text():
    out = telemetry.sanitize_llm_request_properties({
        "provider": "api88",
        "model": "gpt-4o-mini",
        "base_url": f"https://user:{SECRET}@88api.ai/v1/chat/completions?api_key={SECRET}",
        "kind": "text",
        "stage": "analyze",
        "http_status": 401,
        "upstream_error_type": UpstreamErrorType.INVALID_KEY,
        "prompt_tokens": 12,
        "completion_tokens": 0,
        "reasoning_tokens": 0,
        "retry_count": 0,
        "degrade_count": 1,
        "duration_ms": 320,
        "outcome": "error",
        "finish_reason": "stop",
        "api_key": SECRET,
        "prompt": PROMPT,
        "messages": [{"role": "user", "content": PROMPT}],
        "url": "https://88api.ai/v1/chat/completions",
        "title": "我的旅行vlog",
        "transcript": "大家好今天我们来聊",
    })
    dumped = str(out)
    assert SECRET not in dumped
    assert PROMPT not in dumped
    assert "88api.ai/v1" not in dumped
    assert "旅行" not in dumped
    assert "大家好" not in dumped
    assert out == {
        "success_rate_schema_version": 1,
        "provider": "api88",
        "model": "gpt-4o-mini",
        "base_url_host": "88api.ai",
        "kind": "text",
        "stage": "analyze",
        "http_status": 401,
        "upstream_error_type": "invalid_key",
        "prompt_tokens": 12,
        "completion_tokens": 0,
        "reasoning_tokens": 0,
        "retry_count": 0,
        "degrade_count": 1,
        "duration_ms": 320,
        "outcome": "error",
        "finish_reason": "stop",
    }


def test_run_properties_reject_success_status_and_unknown_enums():
    out = telemetry.sanitize_run_properties({
        "provider": "not-a-vendor",
        "model": "ok-model",
        "base_url_host": "api.openai.com",
        "http_status": 200,
        "upstream_error_type": "authentication",
        "failure_stage": "private-stage",
        "llm_calls": 3,
        "billable_calls_before_failure": 2,
        "retry_count": -1,
        "degrade_count": -2,
        "prompt": PROMPT,
        "path": "/Users/private/movie.mp4",
        "title": "我的旅行vlog",
        "transcript": "大家好今天我们来聊",
    })
    assert out["success_rate_schema_version"] == 1
    assert "provider" not in out
    assert out["model"] == "ok-model"
    assert out["base_url_host"] == "api.openai.com"
    assert "http_status" not in out
    assert "upstream_error_type" not in out
    assert "failure_stage" not in out
    assert out["llm_calls"] == 3
    assert out["billable_calls_before_failure"] == 2
    assert "retry_count" not in out
    assert "degrade_count" not in out
    assert PROMPT not in str(out)
    assert "movie.mp4" not in str(out)
    assert "旅行" not in str(out)
    assert "大家好" not in str(out)


def test_validation_and_asr_payloads():
    asr = telemetry.sanitize_asr_readiness_properties({
        "provider": "whisper_local",
        "code": "whisper_not_installed",
        "has_subtitle": False,
        "blocked": True,
        "path": "/Users/private/movie.mp4",
    })
    assert asr == {
        "success_rate_schema_version": 1,
        "provider": "whisper_local",
        "code": "whisper_not_installed",
        "has_subtitle": False,
        "blocked": True,
    }
    validation = telemetry.sanitize_provider_validation_properties({
        "provider": "api88",
        "base_url": "https://88api.ai/",
        "result": "failed",
        "error_type": "bad_endpoint",
        "api_key": SECRET,
    })
    assert validation["base_url_host"] == "88api.ai"
    assert validation["upstream_error_type"] == "bad_endpoint"
    assert validation["result"] == "failed"
    assert SECRET not in str(validation)


def test_request_properties_redact_a_url_disguised_as_model():
    out = telemetry.sanitize_llm_request_properties({
        "provider": "openai",
        "model": f"https://api.openai.com/v1/chat/completions?api_key={SECRET}",
        "kind": "text",
        "outcome": "error",
        "prompt": PROMPT,
    })
    assert out["model"] == "redacted"
    assert SECRET not in str(out)
    assert "https://" not in str(out)
    assert PROMPT not in str(out)


def test_llm_manager_call_logs_sanitized_exception(monkeypatch, caplog):
    from backend.core import llm_manager as lm

    class Fake:
        model_name = "gpt-4o-mini"

        def call(self, *args, **kwargs):
            raise RuntimeError(
                f"POST https://api.openai.com/v1/chat/completions {SECRET} {PROMPT}"
            )

        def _build_full_input(self, *args, **kwargs):
            return "x"

    monkeypatch.setattr("backend.core.project_cancellation.checkpoint", lambda: None)
    mgr = lm.LLMManager.__new__(lm.LLMManager)
    mgr.current_provider = Fake()
    mgr.settings = {}
    monkeypatch.setattr(mgr, "_reload_if_settings_changed", lambda: None)
    monkeypatch.setattr(lm, "_llm_cache_path", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        mgr,
        "get_current_provider_info",
        lambda: {"provider": "openai", "model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"},
    )
    with caplog.at_level("ERROR"):
        with pytest.raises(RuntimeError):
            mgr.call("prompt")
    assert SECRET not in caplog.text
    assert PROMPT not in caplog.text
    assert "https://api.openai.com/v1/chat/completions" not in caplog.text
    assert "api.openai.com" in caplog.text


def test_openai_provider_call_logs_sanitized_exception(caplog):
    from backend.core import llm_providers as lp

    class Completions:
        @staticmethod
        def create(**kwargs):
            raise RuntimeError(
                f"POST https://api.openai.com/v1/chat/completions Bearer {SECRET} {PROMPT}"
            )

    class Chat:
        completions = Completions()

    provider = lp.OpenAIProvider.__new__(lp.OpenAIProvider)
    provider.model_name = "gpt-4o-mini"
    provider.base_url = "https://api.openai.com/v1"
    provider.client = type("Client", (), {"chat": Chat()})()
    provider._build_full_input = lambda *args, **kwargs: "prompt"
    with caplog.at_level("ERROR", logger=lp.__name__):
        with pytest.raises(RuntimeError):
            provider.call("prompt")
    assert SECRET not in caplog.text
    assert PROMPT not in caplog.text
    assert "https://api.openai.com/v1/chat/completions" not in caplog.text
    assert "api.openai.com" in caplog.text


def test_r1_increment_hook_lives_on_llm_manager():
    text = Path(__file__).resolve().parents[1].joinpath("core", "llm_manager.py").read_text(encoding="utf-8")
    assert "def note_same_provider_degrade" in text
    assert "increment_degrade_count" in text
    assert "degrade_count" in text
    assert "call_with_retry" in text


def test_increment_degrade_count_is_exported_and_capped():
    token = telemetry.set_degrade_count(0)
    try:
        assert telemetry.current_degrade_count() == 0
        assert telemetry.increment_degrade_count() == 1
        assert telemetry.increment_degrade_count() == 2
        telemetry.set_degrade_count(40)
        assert telemetry.current_degrade_count() == 32
    finally:
        telemetry.reset_degrade_count(token)


def test_increment_degrade_count_without_run_does_not_allocate(monkeypatch):
    from backend.core import llm_emit

    monkeypatch.setattr(llm_emit, "_degrade_runs", {})

    def check_unbound_counting():
        for _ in range(2):
            assert telemetry.increment_degrade_count() == 0
            assert telemetry.current_degrade_count() == 0
            assert llm_emit._degrade_run_id.get() is None
            assert llm_emit._degrade_runs == {}

    contextvars.Context().run(check_unbound_counting)


def test_parallel_context_copies_do_not_undercount_degrades():
    """Pipeline chunks copy_context(); two degrades must not both record as 1."""
    from backend.core.llm_usage import run_in_context

    workers = 8
    barrier = threading.Barrier(workers)

    def bump(_index: int) -> int:
        barrier.wait(timeout=2)
        return telemetry.increment_degrade_count()

    with telemetry.track_run():
        wrapped = run_in_context(bump)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = [pool.submit(wrapped, index) for index in range(workers)]
            wait(pending, return_when=ALL_COMPLETED)
            observed = [future.result() for future in pending]
        assert telemetry.current_degrade_count() == workers
        snapshot = telemetry.run_snapshot()
    assert sorted(observed) == list(range(1, workers + 1))
    assert snapshot["degrade_count"] == workers
    assert telemetry.current_degrade_count() == 0


def test_degrade_count_is_non_negative_and_drops_user_payloads():
    kept = telemetry.sanitize_run_properties({
        "degrade_count": 3,
        "api_key": SECRET,
        "base_url": "https://api.openai.com/v1/chat/completions",
        "title": "我的旅行vlog",
    })
    assert kept["degrade_count"] == 3
    assert "api_key" not in kept
    assert "base_url" not in kept
    assert "title" not in kept
    assert "chat/completions" not in str(kept)
    rejected = telemetry.sanitize_llm_request_properties({
        "degrade_count": -1,
        "retry_count": 1.5,
        "prompt": PROMPT,
    })
    assert "degrade_count" not in rejected
    assert "retry_count" not in rejected
    assert PROMPT not in str(rejected)
