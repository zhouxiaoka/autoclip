"""APIMart provider: catalog wiring, live model tags, and existing error codes.

No test contacts APIMart. HTTP is a mock of the documented response shapes:
https://docs.apimart.ai/en/api-reference/texts/models/list
https://docs.apimart.ai/en/development
https://docs.apimart.ai/en/api-reference/texts/gemini/quickstart
"""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest

from backend.core.cloud_presets import resolve_cloud_preset
from backend.core.model_catalog import supports_vision
from backend.core.model_recovery import clear_remembered_models, pick_available_vision_model, resolve_available_model
from backend.core.model_registry import _records
from backend.core.provider_model_fetch import fetch_provider_models
from backend.core.provider_presets import get_provider
from backend.core.upstream_errors import UpstreamErrorType, classify_upstream_error


SECRET = "sk-apimart-secret-should-never-leak"
BASE = "https://api.apimart.ai/v1"
KEY_URL = "https://go.apimart.ai/tw-autoclip"

# Documented list shape. gpt-4o is text-only here on purpose: the name heuristic
# would call it vision-ready, and the live tags must win.
LIVE_LIST = {
    "success": True,
    "object": "list",
    "data": [
        {
            "id": "gpt-4o",
            "object": "model",
            "created": 1626777600,
            "owned_by": "openai",
            "supported_endpoint_types": ["openai"],
            "category": "chat",
            "capability_tags": ["Text"],
        },
        {
            "id": "retired-vision",
            "object": "model",
            "created": 1626777600,
            "owned_by": "openai",
            "supported_endpoint_types": ["openai"],
            "category": "chat",
            "capability_tags": ["Text", "Vision"],
        },
        {
            "id": "live-vision",
            "object": "model",
            "created": 1626777600,
            "owned_by": "google",
            "supported_endpoint_types": ["openai"],
            "category": "chat",
            "capability_tags": ["Text", "Vision"],
        },
        {
            "id": "embed-only",
            "object": "model",
            "created": 1626777600,
            "owned_by": "openai",
            "supported_endpoint_types": ["openai"],
            "category": "chat",
            "capability_tags": ["Embedding"],
        },
        {
            "id": "wan2.6",
            "object": "model",
            "created": 1626777600,
            "owned_by": "alibaba",
            "supported_endpoint_types": ["openai"],
            "category": "video",
            "capability_tags": ["Text to Video"],
        },
    ],
}


class _Response:
    def __init__(self, status, payload):
        self.status_code = status
        self.headers = {"content-type": "application/json"}
        self._payload = payload
        self.text = payload if isinstance(payload, str) else json.dumps(payload)

    def json(self):
        if isinstance(self._payload, str):
            return json.loads(self._payload)
        return self._payload


def _http(payload, status=200):
    seen = []

    def getter(url, *, headers, timeout, trust_env):
        seen.append({"url": url, "headers": dict(headers), "timeout": timeout, "trust_env": trust_env})
        return _Response(status, payload)

    getter.seen = seen
    return getter


def test_apimart_preset_is_an_openai_compatible_sponsor():
    preset = get_provider("apimart")
    assert preset is not None
    assert preset.base_url == BASE
    assert preset.auth == "api_key"
    assert preset.protocol == "openai-completions"
    assert preset.docs_url == KEY_URL
    assert preset.sponsor["register_url"] == KEY_URL
    assert preset.api_key_setting == "apimart_api_key"
    assert preset.group == "recommended"
    assert preset.capabilities == ("language",)
    # No hardcoded model menu. Preset ids stay empty and are only a fallback order.
    assert preset.default_model == ""
    assert preset.catalog == ()
    assert preset.catalog_image == ()
    assert preset.candidates["analysis"] == ()
    assert preset.candidates["vision"] == ()
    assert "生成画面" not in preset.hint
    transport, base_url, cloud = resolve_cloud_preset("apimart")
    assert transport == "openai"
    assert base_url == BASE
    assert cloud.api_key_setting == "apimart_api_key"


def test_live_list_uses_capability_tags_and_drops_non_chat_models():
    http = _http(LIVE_LIST)
    result = fetch_provider_models(base_url=BASE, api_key=SECRET, provider="apimart", http=http)
    assert result.ok
    assert result.models == ["gpt-4o", "retired-vision", "live-vision"]
    assert result.capabilities == {
        "gpt-4o": "text",
        "retired-vision": "multimodal",
        "live-vision": "multimodal",
    }
    assert http.seen[0]["url"] == BASE + "/models?expand=category"
    assert http.seen[0]["headers"]["Authorization"] == "Bearer " + SECRET
    dumped = json.dumps(result.as_api())
    assert SECRET not in dumped
    assert "expand" not in dumped


def test_text_only_tag_is_not_vision_ready_even_when_the_name_is():
    assert supports_vision("gpt-4o")
    rows = _records(SimpleNamespace(provider="apimart"), LIVE_LIST["data"], {})
    by_id = {row["id"]: row for row in rows}
    assert by_id["gpt-4o"]["capability"] == "text"
    assert by_id["gpt-4o"]["capability_source"] == "provider"
    assert by_id["gpt-4o"]["analysis"] is True
    assert by_id["live-vision"]["capability"] == "multimodal"
    assert "wan2.6" not in by_id
    assert "embed-only" not in by_id
    assert pick_available_vision_model(
        "apimart",
        ["gpt-4o", "live-vision"],
        capabilities={"gpt-4o": "text", "live-vision": "multimodal"},
    ) == "live-vision"


def test_retired_model_falls_back_to_the_next_listed_vision_model(caplog):
    clear_remembered_models()
    # The saved id has been removed. The remaining gpt-4o row is text-only.
    listed = {
        "success": True,
        "object": "list",
        "data": [item for item in LIVE_LIST["data"] if item["id"] != "retired-vision"],
    }
    http = _http(listed)
    caplog.set_level(logging.INFO)
    alt = resolve_available_model(
        base_url=BASE,
        api_key=SECRET,
        provider="apimart",
        failed_model="retired-vision",
        http=http,
    )
    assert alt == "live-vision"
    assert SECRET not in caplog.text
    assert "gpt-4o" not in (alt or "")
    # No tags: the existing name heuristic is the fallback, not a hardcoded menu.
    assert pick_available_vision_model(
        "apimart",
        ["text-only-model", "custom-vl"],
    ) == "custom-vl"
    assert pick_available_vision_model(
        "apimart",
        ["gpt-4o"],
        capabilities={"gpt-4o": "text"},
    ) is None


@pytest.mark.parametrize(
    "status, body, expected",
    [
        (401, {"error": {"code": 401, "message": f"Authentication failed, please check your API Key {SECRET}", "type": "authentication_error"}}, UpstreamErrorType.INVALID_KEY),
        (401, {"error": {"code": 401, "message": "Invalid authentication credentials", "status": "UNAUTHENTICATED"}}, UpstreamErrorType.INVALID_KEY),
        (402, {"error": {"code": 402, "message": "Insufficient balance, please recharge", "status": "PAYMENT_REQUIRED"}}, UpstreamErrorType.INSUFFICIENT_QUOTA),
        (403, {"error": {"code": 403, "message": "Access denied", "status": "PERMISSION_DENIED"}}, UpstreamErrorType.PERMISSION_DENIED),
        (404, {"error": {"code": 404, "message": "Model not found", "status": "NOT_FOUND"}}, UpstreamErrorType.MODEL_NOT_FOUND),
        (429, {"error": {"code": 429, "message": "Rate limit exceeded, please try again later", "status": "RESOURCE_EXHAUSTED"}}, UpstreamErrorType.RATE_LIMITED),
        (500, {"error": {"code": 500, "message": "Internal server error", "status": "INTERNAL"}}, UpstreamErrorType.UPSTREAM_UNAVAILABLE),
        (503, {"error": {"code": 503, "message": "Service temporarily unavailable", "status": "UNAVAILABLE"}}, UpstreamErrorType.UPSTREAM_UNAVAILABLE),
    ],
)
def test_documented_errors_use_existing_codes(status, body, expected):
    classified = classify_upstream_error(status, body)
    assert classified.error_type is expected
    assert SECRET not in classified.hint_key
    assert SECRET not in classified.error_type.value
    http = _http(body, status=status)
    fetched = fetch_provider_models(base_url=BASE, api_key=SECRET, provider="apimart", http=http)
    assert fetched.ok is False
    dumped = json.dumps(fetched.as_api())
    assert SECRET not in dumped
    # /models 404 means the list endpoint itself is wrong; a chat 404 is model_not_found.
    if status == 404:
        assert fetched.error_type == UpstreamErrorType.BAD_ENDPOINT.value
    else:
        assert fetched.error_type == expected.value
