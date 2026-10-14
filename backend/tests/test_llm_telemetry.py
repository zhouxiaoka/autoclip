"""成功率埋点字段脱敏：只留域名与枚举，不含 key / 完整 URL / 用户内容。"""
from __future__ import annotations

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
    assert telemetry.sanitize_model("has space") is None
    assert telemetry.sanitize_model("a" * 65) is None
    assert telemetry.sanitize_model(PROMPT) is None
    assert telemetry.sanitize_provider("API88") == "api88"
    assert telemetry.sanitize_provider("siliconflow") is None
    assert telemetry.sanitize_provider("whisper_local", allow_asr=True) == "whisper_local"
    assert telemetry.sanitize_provider("whisper_local") is None


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
        "duration_ms": 320,
        "outcome": "error",
        "finish_reason": "stop",
        "api_key": SECRET,
        "prompt": PROMPT,
        "messages": [{"role": "user", "content": PROMPT}],
        "url": "https://88api.ai/v1/chat/completions",
    })
    dumped = str(out)
    assert SECRET not in dumped
    assert PROMPT not in dumped
    assert "88api.ai/v1" not in dumped
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
        "prompt": PROMPT,
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
    assert PROMPT not in str(out)


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
