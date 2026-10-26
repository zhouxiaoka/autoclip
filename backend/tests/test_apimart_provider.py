"""APIMart provider: catalog wiring, live model tags, and existing error codes.

No test contacts APIMart. HTTP is a mock of the documented response shapes:
https://docs.apimart.ai/en/api-reference/texts/models/list
https://docs.apimart.ai/en/development
https://docs.apimart.ai/en/api-reference/texts/gemini/quickstart
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.core.cloud_presets import resolve_cloud_preset
from backend.core.error_middleware import (
    global_exception_handler,
    http_exception_handler_safe,
    validation_exception_handler,
)
from backend.core.log_redaction import redact_text
from backend.core.model_catalog import is_chat_model, is_non_chat_family, supports_vision
from backend.core.model_recovery import clear_remembered_models, pick_available_vision_model, resolve_available_model
from backend.core.model_registry import _records
from backend.core.provider_model_fetch import fetch_provider_models
from backend.core.provider_presets import get_provider
from backend.core.upstream_errors import UpstreamErrorType, classify_upstream_error
from backend.services import ai_model_settings as ai
from backend.services.provider_validation import validate_connection


SECRET = "sk-apimart-secret-should-never-leak"
BASE = "https://api.apimart.ai/v1"
KEY_URL = "https://go.apimart.ai/tw-autoclip"

CHAT_IDS = [
    "chatgpt-4o-latest",
    "gpt-4-vision-preview",
    "gpt-4o",
    "gemini-3.8-flash",
    "qwen3.8-flash",
    "claude-haiku-5-5",
    "deepseek-v4-flash",
]


def _row(model_id, tags, category="chat"):
    return {
        "id": model_id,
        "object": "model",
        "created": 1626777600,
        "owned_by": "apimart",
        "supported_endpoint_types": ["openai"],
        "category": category,
        "capability_tags": tags,
    }


# Text tags on Gemini / Qwen / Claude must not veto vision. Vision tags on
# realtime, search, moderation and legacy completion models must not make them chat.
LIVE_LIST = {
    "success": True,
    "object": "list",
    "data": [
        _row("chatgpt-4o-latest", ["Vision"]),
        _row("gpt-4-vision-preview", ["Vision"]),
        _row("gpt-4o", ["Text"]),
        _row("gpt-4o-realtime-preview", ["Vision"]),
        _row("gpt-4o-mini-transcribe", ["Vision"]),
        _row("omni-moderation-latest", ["Vision"]),
        _row("o3-deep-research", ["Vision"]),
        _row("o4-mini-deep-research", ["Vision"]),
        _row("gpt-5-search-api", ["Vision"]),
        _row("babbage-002", ["Text"]),
        _row("davinci-002", ["Text"]),
        _row("text-davinci-001", ["Text"]),
        _row("text-moderation-001", ["Text"]),
        _row("embed-only", ["Embedding"]),
        _row("wan2.6", ["Text to Video"], category="video"),
        _row("gemini-3.8-flash", ["Text"]),
        _row("qwen3.8-flash", ["Text"]),
        _row("claude-haiku-5-5", ["Text"]),
        _row("deepseek-v4-flash", ["Text"]),
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
    assert preset.capabilities == ("language", "image", "video")
    # Ordering hints only. They are intersected with the live list, never a menu.
    assert preset.default_model == ""
    assert preset.catalog == ()
    assert preset.catalog_image == ()
    assert preset.candidates["analysis"] == ("qwen3.8-flash", "gemini-3.8-flash", "deepseek-v4-flash")
    assert preset.candidates["vision"] == ("qwen3.8-flash", "gemini-3.8-flash")
    assert preset.candidates["image"] == ()
    # Catalog badges declare language / image / video. Empty image lists stay empty:
    # OpenRouter (the peer with the same three caps) does not ship a model menu either.
    assert "生成画面" not in preset.hint
    assert "语言、图像和视频" in preset.hint
    assert preset.cloud_hint == preset.hint
    transport, base_url, cloud = resolve_cloud_preset("apimart")
    assert transport == "openai"
    assert base_url == BASE
    assert cloud.api_key_setting == "apimart_api_key"


def test_live_list_uses_capability_tags_and_drops_non_chat_models():
    http = _http(LIVE_LIST)
    result = fetch_provider_models(base_url=BASE, api_key=SECRET, provider="apimart", http=http)
    assert result.ok
    assert result.models[:3] == ["qwen3.8-flash", "gemini-3.8-flash", "deepseek-v4-flash"]
    assert set(result.models) == set(CHAT_IDS)
    # Vision/Omni adds multimodal. A Text tag is not stored and does not veto.
    assert result.capabilities == {
        "chatgpt-4o-latest": "multimodal",
        "gpt-4-vision-preview": "multimodal",
    }
    assert result.recommended["analysis"] == ["qwen3.8-flash", "gemini-3.8-flash", "deepseek-v4-flash"]
    assert result.recommended["vision"] == ["qwen3.8-flash", "gemini-3.8-flash"]
    assert http.seen[0]["url"] == BASE + "/models?expand=category"
    assert http.seen[0]["headers"]["Authorization"] == "Bearer " + SECRET
    dumped = json.dumps(result.as_api())
    assert SECRET not in dumped
    assert "expand" not in dumped


def test_text_tag_does_not_veto_vision_and_non_chat_families_are_dropped():
    assert supports_vision("gpt-4o")
    assert supports_vision("gemini-3.8-flash")
    assert supports_vision("qwen3.8-flash")
    assert supports_vision("claude-haiku-5-5")
    assert not supports_vision("deepseek-v4-flash")
    for name in (
        "gpt-4o-realtime-preview", "gpt-4o-mini-transcribe", "omni-moderation-latest",
        "o3-deep-research", "gpt-5-search-api", "babbage-002", "davinci-002",
        "text-davinci-001", "text-moderation-001",
    ):
        assert is_non_chat_family(name)
        assert not is_chat_model(name, "openai", official=False)
    rows = _records(SimpleNamespace(provider="apimart"), LIVE_LIST["data"], {})
    by_id = {row["id"]: row for row in rows}
    assert set(by_id) == set(CHAT_IDS)
    for name in ("gpt-4o", "gemini-3.8-flash", "qwen3.8-flash", "claude-haiku-5-5"):
        assert by_id[name]["capability"] == "multimodal"
        assert by_id[name]["capability_source"] == "name"
        assert by_id[name]["analysis"] is True
    assert by_id["chatgpt-4o-latest"]["capability"] == "multimodal"
    assert by_id["chatgpt-4o-latest"]["capability_source"] == "provider"
    assert by_id["deepseek-v4-flash"]["capability"] != "multimodal"
    assert by_id["deepseek-v4-flash"]["analysis"] is True
    assert pick_available_vision_model(
        "apimart",
        CHAT_IDS,
        capabilities={"gpt-4o": "text", "chatgpt-4o-latest": "multimodal"},
    ) == "qwen3.8-flash"
    assert pick_available_vision_model(
        "apimart",
        ["gpt-4o"],
        capabilities={"gpt-4o": "text"},
    ) == "gpt-4o"
    assert pick_available_vision_model(
        "apimart",
        ["gpt-5-search-api", "o3-deep-research", "babbage-002", "gpt-4o-realtime-preview"],
        capabilities={"gpt-5-search-api": "multimodal", "o3-deep-research": "multimodal"},
    ) is None


def test_retired_model_falls_back_to_a_live_candidate_not_chatgpt_4o_latest(caplog):
    clear_remembered_models()
    http = _http(LIVE_LIST)
    caplog.set_level(logging.INFO)
    alt = resolve_available_model(
        base_url=BASE,
        api_key=SECRET,
        provider="apimart",
        failed_model="chatgpt-4o-latest",
        http=http,
    )
    assert alt == "qwen3.8-flash"
    assert SECRET not in caplog.text
    assert pick_available_vision_model("apimart", ["text-only-model", "custom-vl"]) == "custom-vl"


@pytest.mark.parametrize(
    "status, body, expected",
    [
        (401, {"error": {"message": f"Incorrect API key provided: {SECRET}", "type": "invalid_request_error", "code": "invalid_api_key"}}, UpstreamErrorType.INVALID_KEY),
        (503, {"error": {"message": "No available channel for model retired-id", "type": "invalid_request_error", "code": "model_not_found"}}, UpstreamErrorType.UPSTREAM_UNAVAILABLE),
        (404, {"error": {"code": "DeploymentNotFound", "message": "DeploymentNotFound"}}, UpstreamErrorType.MODEL_NOT_FOUND),
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
    # The list endpoint treats 5xx as unavailable and 404 as a wrong models URL.
    # The same bodies on a chat call use `expected` (see classify above).
    if status == 404:
        assert fetched.error_type == UpstreamErrorType.BAD_ENDPOINT.value
    elif status >= 500:
        assert fetched.error_type == UpstreamErrorType.UPSTREAM_UNAVAILABLE.value
    else:
        assert fetched.error_type == expected.value


def test_callers_stream_and_the_probe_stays_a_single_json_body():
    """Analysis calls consume SSE. The connection probe still forces stream false (#492)."""
    posted = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"data": [{"id": "qwen3.8-flash"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode() or "{}")
            posted.append(payload)
            if payload.get("stream") is not False:
                # Deltas assemble to the same answer the JSON branch returns.
                first = json.dumps({"choices": [{"delta": {"content": '{"ok": '}}]})
                second = json.dumps({"choices": [{"index": 0, "delta": {"content": "true}"}, "finish_reason": "stop"}]})
                sse = f"data: {first}\n\ndata: {second}\n\ndata: [DONE]\n\n".encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(sse)))
                self.end_headers()
                self.wfile.write(sse)
                return
            body = json.dumps({
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": payload.get("model") or "qwen3.8-flash",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": '{"ok": true}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}/v1"
    try:
        import httpx
        bare = httpx.post(base + "/chat/completions", json={"model": "qwen3.8-flash", "messages": [{"role": "user", "content": "ok"}]}, timeout=5)
        assert bare.status_code == 200
        assert "text/event-stream" in bare.headers["content-type"]
        assert posted[-1].get("stream") is not False

        connection = ai.Connection(id="c", name="local", provider="compatible", base_url=base, api_key=SECRET)
        probed = validate_connection(connection, "qwen3.8-flash")
        assert probed.ok is True, probed.error_type
        assert posted[-1]["stream"] is False

        from backend.services.studio import intelligence
        seen = intelligence.vision_call(
            [{"type": "text", "text": "look"}],
            config={"base_url": base, "model": "qwen3.8-flash", "api_key": SECRET, "timeout": 10},
        )
        assert seen == {"ok": True}
        assert posted[-1]["stream"] is True

        from backend.core.llm_providers import OpenAIProvider
        reply = OpenAIProvider(SECRET, "qwen3.8-flash", base_url=base).call("测试", max_tokens=16)
        assert reply.content == '{"ok": true}'
        assert posted[-1]["stream"] is True
    finally:
        server.shutdown()


def test_connection_validation_does_not_leak_the_key_tail(caplog):
    key = "sk-" + ("b" * 80) + "TAIL99"
    with pytest.raises(ValidationError) as caught:
        ai.Connection(id="c", name="n", provider="compatible", base_url="", api_key=key)
    assert "TAIL99" not in str(caught.value)
    assert key not in str(caught.value)
    leaked = "input_value={'id': 'c', 'api_key': 'sk-bbbb...bbbbTAIL99'}, input_type=dict"
    assert "TAIL99" not in redact_text(leaked)

    app = FastAPI()
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler_safe)

    @app.post("/discover")
    def discover(body: ai.Connection):
        return {"ok": True}

    @app.post("/saved")
    def saved():
        try:
            ai.Connection(id="c", name="n", provider="compatible", base_url="", api_key=key)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=redact_text(str(exc))) from exc
        return {}

    with TestClient(app) as client:
        denied = client.post("/discover", json={
            "id": "c", "name": "n", "provider": "compatible", "base_url": "", "api_key": key,
        })
        assert denied.status_code == 422
        assert "TAIL99" not in denied.text
        assert key not in denied.text
        echoed = client.post("/saved")
        assert echoed.status_code == 422
        assert "TAIL99" not in echoed.text

    class _Request:
        method = "POST"

        class url:
            path = "/settings/ai-models/discover"

        class state:
            request_id = "r"

    caplog.set_level(logging.ERROR)
    asyncio.run(global_exception_handler(_Request(), RuntimeError(leaked)))
    assert "TAIL99" not in caplog.text
    assert "bbbb" not in caplog.text
