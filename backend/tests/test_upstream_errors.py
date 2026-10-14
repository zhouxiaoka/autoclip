"""上游错误分类契约：各家真实信封样例。不触及调用链。"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.core.upstream_errors import (
    HINT_KEYS,
    RETRYABLE_TYPES,
    UPSTREAM_ERROR_TYPES,
    UpstreamErrorType,
    classify_exception,
    classify_upstream_error,
    http_error_parts,
)

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend/src/analytics/successRateContract.ts"
LOCALES = ROOT / "frontend/src/i18n/locales"
SECRET = "sk-live-secret-should-never-leak"


def _assert_safe(result, expected: UpstreamErrorType, retryable: bool) -> None:
    assert result.error_type is expected
    assert result.retryable is retryable
    assert result.hint_key == HINT_KEYS[expected]
    dumped = json.dumps(result.as_dict(), ensure_ascii=False)
    assert SECRET not in dumped
    assert "sk-" not in dumped
    assert "private-url" not in dumped


@pytest.mark.stdlib_only
@pytest.mark.parametrize(
    "status,body,expected,retryable",
    [
        (401, {"error": {"message": f"Incorrect API key provided: {SECRET}", "type": "invalid_request_error", "code": "invalid_api_key"}}, UpstreamErrorType.INVALID_KEY, False),
        (403, {"error": {"message": "You have insufficient permissions for this operation.", "type": "invalid_request_error", "code": None}}, UpstreamErrorType.PERMISSION_DENIED, False),
        (404, {"error": {"message": "The model `gpt-5-private` does not exist or you do not have access to it.", "type": "invalid_request_error", "code": "model_not_found"}}, UpstreamErrorType.MODEL_NOT_FOUND, False),
        (429, {"error": {"message": "Rate limit reached for gpt-4o", "type": "tokens", "code": "rate_limit_exceeded"}}, UpstreamErrorType.RATE_LIMITED, True),
        (500, {"error": {"message": "The server had an error while processing your request.", "type": "server_error", "code": None}}, UpstreamErrorType.UPSTREAM_UNAVAILABLE, True),
        (429, {"error": {"message": "You exceeded your current quota, please check your plan and billing details.", "type": "insufficient_quota", "code": "insufficient_quota"}}, UpstreamErrorType.INSUFFICIENT_QUOTA, False),
    ],
    ids=["openai-401-key", "openai-403", "openai-404-model", "openai-429", "openai-500", "openai-quota"],
)
def test_openai_envelopes(status, body, expected, retryable):
    _assert_safe(classify_upstream_error(status, body), expected, retryable)


@pytest.mark.stdlib_only
@pytest.mark.parametrize(
    "status,body,expected",
    [
        (401, {"error": {"message": "无效的令牌", "type": "new_api_error", "code": None}}, UpstreamErrorType.INVALID_KEY),
        (401, {"error": {"message": "无效的令牌：额度已用尽", "type": "new_api_error"}}, UpstreamErrorType.INSUFFICIENT_QUOTA),
        (403, {"error": {"message": "用户余额不足", "type": "new_api_error", "code": "insufficient_user_quota"}}, UpstreamErrorType.INSUFFICIENT_QUOTA),
        (403, {"error": {"message": "无权访问 default 分组", "type": "new_api_error"}}, UpstreamErrorType.PERMISSION_DENIED),
        (403, {"error": {"message": "该令牌无权访问模型 gpt-4o", "type": "new_api_error"}}, UpstreamErrorType.PERMISSION_DENIED),
        (503, {"error": {"message": "No available channel for model gpt-4o (under group default)", "type": "new_api_error", "code": "model_not_found"}}, UpstreamErrorType.MODEL_NOT_FOUND),
    ],
    ids=["newapi-401-token", "newapi-401-quota", "newapi-403-quota", "newapi-403-group", "newapi-403-model", "newapi-503-model"],
)
def test_new_api_envelopes(status, body, expected):
    result = classify_upstream_error(status, body)
    _assert_safe(result, expected, expected in RETRYABLE_TYPES)


@pytest.mark.stdlib_only
@pytest.mark.parametrize(
    "status,body,expected",
    [
        (400, {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT", "details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": "API_KEY_INVALID", "domain": "googleapis.com"}]}}, UpstreamErrorType.INVALID_KEY),
        (403, {"error": {"code": 403, "message": "Your API key is invalid or has insufficient permissions", "status": "PERMISSION_DENIED"}}, UpstreamErrorType.PERMISSION_DENIED),
        (404, {"error": {"code": 404, "message": "models/gemini-private is not found", "status": "NOT_FOUND"}}, UpstreamErrorType.MODEL_NOT_FOUND),
        (429, {"error": {"code": 429, "message": "Resource has been exhausted (e.g. check quota).", "status": "RESOURCE_EXHAUSTED"}}, UpstreamErrorType.INSUFFICIENT_QUOTA),
        (429, {"error": {"code": 429, "message": "Too many requests. Please retry later.", "status": "RESOURCE_EXHAUSTED"}}, UpstreamErrorType.RATE_LIMITED),
        (500, {"error": {"code": 500, "message": "Internal error encountered.", "status": "INTERNAL"}}, UpstreamErrorType.UPSTREAM_UNAVAILABLE),
    ],
    ids=["gemini-key", "gemini-permission", "gemini-404", "gemini-quota", "gemini-429", "gemini-500"],
)
def test_gemini_envelopes(status, body, expected):
    result = classify_upstream_error(status, body)
    _assert_safe(result, expected, expected in RETRYABLE_TYPES)


@pytest.mark.stdlib_only
@pytest.mark.parametrize(
    "status,body,expected",
    [
        (401, {"error": {"message": f"Authentication Fails, Your api key: {SECRET} is invalid", "type": "authentication_error", "code": "invalid_request_error"}}, UpstreamErrorType.INVALID_KEY),
        (402, {"error": {"message": "Insufficient Balance", "type": "unknown_error", "code": "invalid_request_error"}}, UpstreamErrorType.INSUFFICIENT_QUOTA),
        (429, {"error": {"message": "Rate limit reached", "type": "rate_limit_error", "code": "rate_limit_exceeded"}}, UpstreamErrorType.RATE_LIMITED),
        (500, {"error": {"message": "internal error", "type": "server_error"}}, UpstreamErrorType.UPSTREAM_UNAVAILABLE),
        (503, {"error": {"message": "Server is overloaded", "type": "server_error"}}, UpstreamErrorType.UPSTREAM_UNAVAILABLE),
    ],
    ids=["deepseek-401", "deepseek-402", "deepseek-429", "deepseek-500", "deepseek-503"],
)
def test_deepseek_envelopes(status, body, expected):
    result = classify_upstream_error(status, body)
    _assert_safe(result, expected, expected in RETRYABLE_TYPES)


@pytest.mark.stdlib_only
@pytest.mark.parametrize(
    "status,body,expected",
    [
        (401, {"code": "InvalidApiKey", "message": "Invalid API-key provided.", "request_id": "private-id"}, UpstreamErrorType.INVALID_KEY),
        (429, {"code": "Throttling.RateQuota", "message": "Request rate exceeded"}, UpstreamErrorType.RATE_LIMITED),
        (403, {"code": "AllocationQuota.FreeTierOnly", "message": "Free tier allocation quota exceeded"}, UpstreamErrorType.INSUFFICIENT_QUOTA),
    ],
    ids=["dashscope-key", "dashscope-rate", "dashscope-quota"],
)
def test_dashscope_native_envelopes(status, body, expected):
    result = classify_upstream_error(status, body)
    _assert_safe(result, expected, expected in RETRYABLE_TYPES)


@pytest.mark.stdlib_only
@pytest.mark.parametrize(
    "status,body",
    [
        (404, "<!DOCTYPE html><html><head><title>404</title></head><body>nginx</body></html>"),
        (200, "<html><head><title>88API 控制台</title></head><body>login</body></html>"),
        (404, b"<!DOCTYPE HTML PUBLIC \"-//IETF//DTD HTML 2.0//EN\"><html><body>Not Found</body></html>"),
        (404, None),
        (404, {"error": {"message": "Not Found", "code": "not_found"}}),
    ],
    ids=["html-404", "html-console", "html-bytes", "empty-404", "generic-not-found"],
)
def test_bad_endpoint_from_html_or_bare_404(status, body):
    _assert_safe(classify_upstream_error(status, body), UpstreamErrorType.BAD_ENDPOINT, False)


@pytest.mark.stdlib_only
def test_json_string_and_sdk_repr_do_not_change_class_or_leak():
    body = json.dumps({"error": {"code": "invalid_api_key", "message": f"Incorrect API key provided: {SECRET}"}})
    result = classify_upstream_error(401, body)
    _assert_safe(result, UpstreamErrorType.INVALID_KEY, False)
    wrapped = f"Error code: 401 - {body}"
    _assert_safe(classify_upstream_error(None, wrapped), UpstreamErrorType.INVALID_KEY, False)


@pytest.mark.stdlib_only
@pytest.mark.parametrize(
    "status,body,error_name,finish_reason,expected",
    [
        (None, "Request timed out.", "APITimeoutError", None, UpstreamErrorType.TIMEOUT),
        (None, "Connection error.", "APIConnectionError", None, UpstreamErrorType.CONNECTION),
        (None, "", "TimeoutError", None, UpstreamErrorType.TIMEOUT),
        (None, "", "ConnectionResetError", None, UpstreamErrorType.CONNECTION),
        (200, {"choices": [{"finish_reason": "length"}]}, None, "length", UpstreamErrorType.OUTPUT_TRUNCATED),
        (400, {"error": {"message": "private prompt leaked", "code": "unknown_option"}}, None, None, UpstreamErrorType.UNKNOWN),
        (408, {"error": {"message": "request timeout"}}, None, None, UpstreamErrorType.TIMEOUT),
    ],
    ids=["timeout-text", "connection-text", "timeout-name", "connection-name", "truncated", "unknown-400", "408"],
)
def test_transport_truncation_and_unknown(status, body, error_name, finish_reason, expected):
    result = classify_upstream_error(status, body, finish_reason=finish_reason, error_name=error_name)
    _assert_safe(result, expected, expected in RETRYABLE_TYPES)


@pytest.mark.stdlib_only
def test_classify_exception_reads_sdk_shape():
    error = SimpleNamespace(
        status_code=403,
        body={"error": {"code": "insufficient_user_quota", "message": f"quota {SECRET}"}},
    )
    # classify_exception expects BaseException; wrap a real one.
    exc = PermissionError("PermissionDeniedError")
    exc.status_code = 403
    exc.body = error.body
    result = classify_exception(exc)
    _assert_safe(result, UpstreamErrorType.INSUFFICIENT_QUOTA, False)
    status, body = http_error_parts(exc)
    assert status == 403
    assert body["error"]["code"] == "insufficient_user_quota"


@pytest.mark.stdlib_only
def test_every_type_has_hint_and_closed_set():
    assert set(HINT_KEYS) == set(UpstreamErrorType)
    assert UPSTREAM_ERROR_TYPES == {item.value for item in UpstreamErrorType}
    assert RETRYABLE_TYPES <= set(UpstreamErrorType)
    for item in UpstreamErrorType:
        assert HINT_KEYS[item]
        assert "sk-" not in HINT_KEYS[item]


@pytest.mark.stdlib_only
def test_existing_model_call_error_code_behavior_is_unchanged():
    """本契约不得改写旧分类：401/403 仍是 authentication，402 仍是 provider_error。"""
    from backend.pipeline.failures import model_call_error_code

    def _err(status: int) -> Exception:
        error = Exception(f"status={status}")
        error.status_code = status  # type: ignore[attr-defined]
        return error

    assert model_call_error_code(_err(401)) == "authentication"
    assert model_call_error_code(_err(403)) == "authentication"
    assert model_call_error_code(_err(402)) == "provider_error"
    assert model_call_error_code(_err(429)) == "rate_limited"
    assert model_call_error_code(_err(503)) == "provider_error"


@pytest.mark.stdlib_only
def test_hint_keys_match_existing_model_call_messages():
    from backend.pipeline.failures import MODEL_CALL_MESSAGES

    assert HINT_KEYS[UpstreamErrorType.TIMEOUT] == MODEL_CALL_MESSAGES["timeout"]
    assert HINT_KEYS[UpstreamErrorType.CONNECTION] == MODEL_CALL_MESSAGES["connection"]
    assert HINT_KEYS[UpstreamErrorType.RATE_LIMITED] == MODEL_CALL_MESSAGES["rate_limited"]


@pytest.mark.stdlib_only
def test_hint_keys_exist_in_all_locales():
    langs = ("zh", "en", "ja", "ko", "es", "pt", "ru", "fr")
    catalogs = {lang: json.loads((LOCALES / f"{lang}.json").read_text(encoding="utf-8")) for lang in langs}
    for hint in HINT_KEYS.values():
        for lang, catalog in catalogs.items():
            assert hint in catalog, f"{lang} missing {hint}"
            assert str(catalog[hint]).strip()


@pytest.mark.stdlib_only
def test_frontend_contract_lists_stay_aligned():
    text = FRONTEND.read_text(encoding="utf-8")

    def const_list(name: str) -> list[str]:
        match = __import__("re").search(rf"export const {name} = \[((?:.|\n)*?)\] as const", text)
        assert match, name
        return __import__("re").findall(r"'([a-z0-9_]+)'", match.group(1))

    assert set(const_list("UPSTREAM_ERROR_TYPES")) == UPSTREAM_ERROR_TYPES
    assert set(const_list("RETRYABLE_UPSTREAM_ERROR_TYPES")) == {item.value for item in RETRYABLE_TYPES}
    from backend.core import llm_telemetry as telemetry
    assert set(const_list("TELEMETRY_PROVIDERS")) == telemetry.TELEMETRY_PROVIDERS
    assert set(const_list("FAILURE_STAGES")) == telemetry.FAILURE_STAGES
    assert set(const_list("RUN_LEVEL_FIELDS")) == telemetry.RUN_LEVEL_FIELDS
    assert set(const_list("LLM_REQUEST_FIELDS")) == telemetry.LLM_REQUEST_FIELDS
    for error_type, hint in HINT_KEYS.items():
        assert f"{error_type.value}:" in text
        assert hint in text
