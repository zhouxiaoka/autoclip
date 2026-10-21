"""Vision calls recover once when the saved model id is no longer offered.

The account list is the source of truth. Preset ids only order that list.
No test here contacts a provider or prints a key.
"""
import io
import json
import logging
import urllib.error

import pytest

from backend.core.model_catalog import supports_vision
from backend.core.model_recovery import (
    clear_remembered_models,
    pick_available_vision_model,
    provider_for_endpoint,
    remembered_model,
    resolve_available_model,
)
from backend.core.provider_model_fetch import AccountModelList
from backend.services.studio import intelligence


SECRET = "sk-live-secret-should-never-leak"
BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
OK = {"choices": [{"message": {"content": '{"events": []}'}, "finish_reason": "stop"}]}
MISSING = {"error": {"message": "Model not exist.", "type": "invalid_request_error", "code": "model_not_found"}}


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_remembered_models()
    yield
    clear_remembered_models()


def test_qwen3_vl_plus_is_vision_capable_without_being_hardcoded_as_the_only_choice():
    assert supports_vision("qwen3-vl-plus")
    assert supports_vision("qwen3-vl-flash")
    assert not supports_vision("qwen-plus")


def test_preset_order_is_a_hint_and_a_dead_id_is_skipped():
    live = ["qwen-plus", "qwen-vl-plus", "qwen3-vl-plus", "qwen3.8-flash", "wanx2.1-t2i-turbo"]
    # qwen-vl-plus is still advertised, but it just 404'd, so it is not eligible.
    # The next DashScope vision hint that is actually listed wins over a later -vl id.
    assert pick_available_vision_model("dashscope", live, exclude=["qwen-vl-plus"]) == "qwen3.8-flash"


def test_live_list_supplies_a_vision_model_when_no_preset_hint_is_offered():
    live = ["qwen-plus", "qwen3-vl-plus", "wanx2.1-t2i-turbo"]
    assert pick_available_vision_model("dashscope", live, exclude=["qwen-vl-plus"]) == "qwen3-vl-plus"
    assert pick_available_vision_model("dashscope", ["qwen-plus", "qwen-vl-plus"], exclude=["qwen-vl-plus"]) is None
    assert pick_available_vision_model("compatible", ["text-only-model", "custom-vl"], exclude=["retired"]) == "custom-vl"


def test_provider_comes_from_the_endpoint_identity_or_the_bailian_host():
    assert provider_for_endpoint({"identity": {"provider": "api88"}, "base_url": BASE}) == "api88"
    assert provider_for_endpoint({"base_url": BASE}) == "dashscope"
    assert provider_for_endpoint({"base_url": "https://example.test/v1"}) == "compatible"


class _ModelsResponse:
    def __init__(self, payload):
        self.status_code = 200
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(payload)
        self._payload = payload

    def json(self):
        return self._payload


def test_resolve_uses_the_live_list_and_does_not_log_the_key(caplog):
    seen = {}

    def http(url, *, headers, timeout, trust_env):
        seen["url"] = url
        seen["auth"] = headers.get("Authorization")
        return _ModelsResponse({"data": [{"id": "qwen-plus"}, {"id": "qwen3-vl-plus"}]})

    with caplog.at_level(logging.INFO):
        alt = resolve_available_model(
            base_url=BASE, api_key=SECRET, provider="dashscope",
            failed_model="qwen-vl-plus", http=http,
        )
    assert alt == "qwen3-vl-plus"
    assert seen["url"].endswith("/models")
    assert SECRET in seen["auth"]
    logged = caplog.text
    assert SECRET not in logged
    assert "qwen-vl-plus" in logged and "qwen3-vl-plus" in logged


def test_resolve_returns_none_when_the_list_cannot_be_read(monkeypatch):
    monkeypatch.setattr(
        "backend.core.provider_model_fetch.list_account_models",
        lambda **kwargs: AccountModelList(ok=False, error_type="invalid_key"),
    )
    assert resolve_available_model(
        base_url=BASE, api_key=SECRET, provider="dashscope", failed_model="qwen-vl-plus",
    ) is None


def _http_error(status, payload):
    raw = json.dumps(payload).encode()
    return urllib.error.HTTPError(BASE, status, "error", {}, io.BytesIO(raw))


def test_saved_retired_model_retries_once_with_a_listed_vision_model(monkeypatch):
    sent = []

    def urlopen(req, timeout=None):
        sent.append(json.loads(req.data.decode()))
        if len(sent) == 1:
            raise _http_error(404, MISSING)
        return io.BytesIO(json.dumps(OK).encode())

    monkeypatch.setattr(intelligence.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(
        "backend.core.model_recovery.resolve_available_model",
        lambda **kwargs: "qwen3-vl-plus" if kwargs["failed_model"] == "qwen-vl-plus" else None,
    )
    config = {"base_url": BASE, "model": "qwen-vl-plus", "api_key": SECRET, "timeout": 10,
              "identity": {"provider": "dashscope", "config_source": "preset"}}
    assert intelligence.vision_call([{"type": "text", "text": "x"}], config=config) == {"events": []}
    assert [item["model"] for item in sent] == ["qwen-vl-plus", "qwen3-vl-plus"]
    assert config["model"] == "qwen-vl-plus"
    assert SECRET not in json.dumps(sent)


def test_a_second_missing_model_does_not_retry_again(monkeypatch):
    calls = {"n": 0, "resolve": 0}

    def urlopen(req, timeout=None):
        calls["n"] += 1
        raise _http_error(404, MISSING)

    def resolve(**kwargs):
        calls["resolve"] += 1
        assert kwargs["api_key"] == SECRET
        return "qwen3-vl-plus"

    monkeypatch.setattr(intelligence.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr("backend.core.model_recovery.resolve_available_model", resolve)
    config = {"base_url": BASE, "model": "qwen-vl-plus", "api_key": SECRET, "timeout": 10,
              "identity": {"provider": "dashscope", "config_source": "user"}}
    with pytest.raises(intelligence.VisionRequestError) as caught:
        intelligence.vision_call([], config=config)
    assert calls == {"n": 2, "resolve": 1}
    exposed = str(caught.value) + json.dumps(caught.value.diagnostics())
    assert SECRET not in exposed and "dashscope.aliyuncs.com" not in exposed
    assert remembered_model("dashscope", BASE, SECRET, "qwen-vl-plus") is None


def test_a_model_that_answered_is_reused_without_another_404(monkeypatch):
    sent = []

    def urlopen(req, timeout=None):
        sent.append(json.loads(req.data.decode())["model"])
        if sent == ["qwen-vl-plus"]:
            raise _http_error(400, {"code": "InvalidParameter", "message": "Model not exist."})
        return io.BytesIO(json.dumps(OK).encode())

    monkeypatch.setattr(intelligence.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(
        "backend.core.model_recovery.resolve_available_model",
        lambda **kwargs: "qwen3-vl-plus",
    )
    config = {"base_url": BASE, "model": "qwen-vl-plus", "api_key": SECRET, "timeout": 10,
              "identity": {"provider": "dashscope", "config_source": "user"}}
    assert intelligence.vision_call([], config=config) == {"events": []}
    assert intelligence.vision_call([], config=config) == {"events": []}
    assert sent == ["qwen-vl-plus", "qwen3-vl-plus", "qwen3-vl-plus"]


def test_other_http_errors_do_not_fetch_a_substitute(monkeypatch):
    def urlopen(req, timeout=None):
        raise _http_error(401, {"error": {"message": "Invalid API-key", "code": "invalid_api_key"}})

    def resolve(**kwargs):
        raise AssertionError("must not re-resolve")

    monkeypatch.setattr(intelligence.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr("backend.core.model_recovery.resolve_available_model", resolve)
    config = {"base_url": BASE, "model": "qwen-vl-plus", "api_key": SECRET, "timeout": 10}
    with pytest.raises(intelligence.VisionRequestError):
        intelligence.vision_call([], config=config)
