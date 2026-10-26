"""Vision calls recover once when the saved model id is no longer offered.

The account list is the source of truth. Preset ids only order that list.
No test here contacts a provider or prints a key.
"""
import io
import json
import logging
import urllib.error
from types import SimpleNamespace

import pytest

from backend.core.model_catalog import supports_vision
from backend.core.model_recovery import (
    clear_remembered_models,
    pick_available_analysis_model,
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


def test_analysis_order_skips_a_dead_id_and_non_chat_families():
    live = [
        "gpt-5-search-api", "omni-moderation-latest", "chatgpt-4o-latest",
        "other-chat", "qwen3.8-flash", "gemini-3.8-flash", "deepseek-v4-flash",
        "text-embedding-3-large",
    ]
    # The first analysis hint that is still listed wins over an earlier non-chat id.
    assert pick_available_analysis_model("apimart", live, exclude=["chatgpt-4o-latest"]) == "qwen3.8-flash"
    # A missing earlier hint keeps preset order. deepseek stays eligible: it is chat, not vision.
    assert pick_available_analysis_model(
        "apimart", ["other-chat", "deepseek-v4-flash", "gemini-3.8-flash"], exclude=["chatgpt-4o-latest"],
    ) == "gemini-3.8-flash"
    assert pick_available_analysis_model(
        "apimart", ["gpt-5-search-api", "deepseek-v4-flash"], exclude=["chatgpt-4o-latest"],
    ) == "deepseek-v4-flash"


def test_analysis_falls_back_to_the_first_live_chat_model():
    live = ["gpt-5-search-api", "omni-moderation-latest", "other-chat", "text-embedding-3-large"]
    assert pick_available_analysis_model("apimart", live, exclude=["chatgpt-4o-latest"]) == "other-chat"
    assert pick_available_analysis_model("compatible", live) == "other-chat"
    assert pick_available_analysis_model("apimart", ["gpt-5-search-api", "text-embedding-3-large"]) is None


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


class _OcrSession:
    def __init__(self, reply):
        self.sent = []
        self.reply = reply

    def post(self, url, headers=None, json=None, timeout=None):
        self.sent.append((url, json))
        status, payload = self.reply(json or {})
        return SimpleNamespace(status_code=status, json=lambda payload=payload: payload, text="")


def _models_http(ids, seen):
    def http(url, *, headers, timeout, trust_env):
        seen["urls"].append(url)
        seen["auth"] = headers.get("Authorization")
        return _ModelsResponse({"data": [{"id": name} for name in ids]})
    return http


NATIVE = "https://dashscope.aliyuncs.com/api/v1"
COMPAT = "https://dashscope.aliyuncs.com/compatible-mode/v1"
INTL_API = "https://dashscope-intl.aliyuncs.com/api/v1"
INTL_COMPAT = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
GONE = {"code": "InvalidParameter", "message": "Model not exist."}
OCR_OK = {"output": {"choices": [{"message": {"content": [{"text": "标题"}]}}]}}
CHAT_OK = {"choices": [{"message": {"content": "标题"}}]}
CHAT_GONE = {"error": {"message": "Model not exist.", "type": "invalid_request_error", "code": "model_not_found"}}


def test_bailian_ocr_default_comes_from_the_live_list_not_a_retired_id(caplog):
    from backend.core.image_providers import default_ocr_model

    seen = {"urls": []}
    with caplog.at_level(logging.INFO):
        chosen = default_ocr_model(
            "dashscope", model="wanx2.1-t2i-turbo", base_url=NATIVE, api_key=SECRET,
            http=_models_http(["qwen-plus", "qwen3-vl-plus"], seen),
        )
    assert chosen == "qwen3-vl-plus"
    assert seen["urls"] == [COMPAT + "/models"]
    assert SECRET not in caplog.text
    assert NATIVE not in caplog.text and COMPAT not in caplog.text
    assert SECRET in seen["auth"]


def test_bailian_catalog_rewrites_official_hosts_and_leaves_a_proxy_alone():
    from backend.core.image_providers import default_ocr_model

    intl = {"urls": []}
    assert default_ocr_model(
        "dashscope", base_url=INTL_API, api_key=SECRET,
        http=_models_http(["qwen3-vl-plus"], intl),
    ) == "qwen3-vl-plus"
    assert intl["urls"] == [INTL_COMPAT + "/models"]

    proxy = {"urls": []}
    assert default_ocr_model(
        "dashscope", base_url="https://proxy.example.com/v1", api_key=SECRET,
        http=_models_http(["custom-vl"], proxy),
    ) == "custom-vl"
    assert proxy["urls"] == ["https://proxy.example.com/v1/models"]


def test_bailian_ocr_default_is_empty_when_the_list_times_out():
    from backend.core.image_providers import ImageError, default_ocr_model, read_image_text

    def slow(url, *, headers, timeout, trust_env):
        raise TimeoutError("timed out")

    assert default_ocr_model("dashscope", model="qwen-vl-plus", api_key=SECRET, http=slow) == ""

    def refuse(body):
        raise AssertionError("posted")

    with pytest.raises(ImageError, match="跳过校对"):
        read_image_text(
            provider="dashscope", api_key=SECRET, base_url="", model="",
            image=b"\xff\xd8\xff", session=_OcrSession(refuse), http=slow,
        )


def test_a_second_ocr_default_reuses_the_account_list():
    from backend.core.image_providers import default_ocr_model

    seen = {"urls": []}
    http = _models_http(["qwen-plus", "qwen3-vl-plus"], seen)
    assert default_ocr_model("dashscope", api_key=SECRET, http=http) == "qwen3-vl-plus"
    assert default_ocr_model("dashscope", api_key=SECRET, http=http) == "qwen3-vl-plus"
    assert seen["urls"] == [COMPAT + "/models"]


def test_bailian_ocr_default_is_empty_when_the_list_has_no_vision_model():
    from backend.core.image_providers import default_ocr_model

    seen = {"urls": []}
    assert default_ocr_model(
        "dashscope", api_key=SECRET, http=_models_http(["qwen-plus", "wanx2.1-t2i-turbo"], seen),
    ) == ""
    assert seen["urls"] == [COMPAT + "/models"]
    assert default_ocr_model("openai") == "gpt-4o-mini"
    from backend.core.image_providers import SEEDREAM_DEFAULT_OCR
    assert default_ocr_model("seedream") == SEEDREAM_DEFAULT_OCR


def test_saved_bailian_ocr_model_retries_once_from_the_account_list(caplog):
    from backend.core.image_providers import read_image_text
    from backend.core.model_recovery import remembered_model

    seen = {"urls": []}

    def reply(body):
        if body.get("model") == "qwen-vl-plus":
            return 400, GONE
        return 200, OCR_OK

    session = _OcrSession(reply)
    with caplog.at_level(logging.INFO):
        text = read_image_text(
            provider="dashscope", api_key=SECRET, base_url="", model="qwen-vl-plus",
            image=b"\xff\xd8\xff", session=session,
            http=_models_http(["qwen-plus", "qwen-vl-plus", "qwen3-vl-plus", "qwen3.8-flash"], seen),
        )
    assert text == "标题"
    assert [body["model"] for _url, body in session.sent] == ["qwen-vl-plus", "qwen3.8-flash"]
    assert session.sent[0][1].get("parameters") is None
    assert session.sent[1][1].get("parameters") == {"enable_thinking": False}
    assert all("/api/v1/services/aigc/multimodal-generation/generation" in url for url, _body in session.sent)
    assert all("/compatible-mode/" not in url for url, _body in session.sent)
    assert seen["urls"] == [COMPAT + "/models"]
    assert SECRET not in caplog.text and COMPAT not in caplog.text
    assert remembered_model("dashscope", COMPAT, SECRET, "qwen-vl-plus") == "qwen3.8-flash"

    def boom(url, *, headers, timeout, trust_env):
        raise AssertionError("cached substitute must not list again")

    again = _OcrSession(reply)
    assert read_image_text(
        provider="dashscope", api_key=SECRET, base_url=NATIVE, model="qwen-vl-plus",
        image=b"\xff\xd8\xff", session=again, http=boom,
    ) == "标题"
    assert [body["model"] for _url, body in again.sent] == ["qwen3.8-flash"]
    assert seen["urls"] == [COMPAT + "/models"]


def test_compatible_bailian_ocr_recovers_and_the_native_path_reuses_it():
    from backend.core.image_providers import read_image_text

    seen = {"urls": []}

    def chat(body):
        if body.get("model") == "qwen-vl-plus":
            return 404, CHAT_GONE
        return 200, CHAT_OK

    session = _OcrSession(chat)
    assert read_image_text(
        provider="openai", api_key=SECRET, base_url=COMPAT, model="qwen-vl-plus",
        image=b"\xff\xd8\xff", session=session,
        http=_models_http(["qwen-vl-plus", "qwen3.8-flash"], seen),
    ) == "标题"
    assert [body["model"] for _url, body in session.sent] == ["qwen-vl-plus", "qwen3.8-flash"]
    assert all(url == COMPAT + "/chat/completions" for url, _body in session.sent)
    assert session.sent[1][1].get("enable_thinking") is False

    def native(body):
        if body.get("model") == "qwen-vl-plus":
            return 400, GONE
        return 200, OCR_OK

    def boom(url, *, headers, timeout, trust_env):
        raise AssertionError("native cover must reuse the compatible-path substitute")

    follow = _OcrSession(native)
    assert read_image_text(
        provider="dashscope", api_key=SECRET, base_url="", model="qwen-vl-plus",
        image=b"\xff\xd8\xff", session=follow, http=boom,
    ) == "标题"
    assert [body["model"] for _url, body in follow.sent] == ["qwen3.8-flash"]


def test_empty_bailian_ocr_model_posts_the_listed_vision_model():
    from backend.core.image_providers import read_image_text

    seen = {"urls": []}
    session = _OcrSession(lambda body: (200, OCR_OK))
    assert read_image_text(
        provider="dashscope", api_key=SECRET, base_url=NATIVE, model="",
        image=b"\xff\xd8\xff", session=session,
        http=_models_http(["qwen-plus", "qwen3-vl-plus"], seen),
    ) == "标题"
    assert [body["model"] for _url, body in session.sent] == ["qwen3-vl-plus"]
    assert seen["urls"] == [COMPAT + "/models"]
    assert "/api/v1/" not in seen["urls"][0]


def test_ocr_does_not_retry_when_the_list_has_no_other_vision_model():
    from backend.core.image_providers import ImageError, read_image_text

    seen = {"urls": []}
    session = _OcrSession(lambda body: (400, GONE))
    with pytest.raises(ImageError) as caught:
        read_image_text(
            provider="dashscope", api_key=SECRET, base_url="", model="qwen-vl-plus",
            image=b"\xff\xd8\xff", session=session,
            http=_models_http(["qwen-plus", "qwen-vl-plus"], seen),
        )
    assert [body["model"] for _url, body in session.sent] == ["qwen-vl-plus"]
    assert seen["urls"] == [COMPAT + "/models"]
    assert SECRET not in str(caught.value) and "aliyuncs.com" not in str(caught.value)


def test_ocr_without_a_vision_model_skips_before_calling_bailian():
    from backend.core.image_providers import ImageError, read_image_text

    def refuse(body):
        raise AssertionError("posted")

    session = _OcrSession(refuse)
    with pytest.raises(ImageError, match="跳过校对"):
        read_image_text(
            provider="dashscope", api_key=SECRET, base_url="", model="",
            image=b"\xff\xd8\xff", session=session,
            http=_models_http(["qwen-plus"], {"urls": []}),
        )


def test_a_second_missing_ocr_model_does_not_retry_again():
    from backend.core.image_providers import ImageError, read_image_text

    seen = {"urls": []}
    session = _OcrSession(lambda body: (400, GONE))
    with pytest.raises(ImageError):
        read_image_text(
            provider="dashscope", api_key=SECRET, base_url="", model="qwen-vl-plus",
            image=b"\xff\xd8\xff", session=session,
            http=_models_http(["qwen-vl-plus", "qwen3.8-flash"], seen),
        )
    assert [body["model"] for _url, body in session.sent] == ["qwen-vl-plus", "qwen3.8-flash"]
    assert seen["urls"] == [COMPAT + "/models"]


def test_advertised_retired_id_is_only_an_ordering_hint_and_recovers_once():
    from backend.core.image_providers import read_image_text

    seen = {"urls": []}

    def reply(body):
        if body.get("model") == "qwen-vl-plus":
            return 400, GONE
        return 200, OCR_OK

    session = _OcrSession(reply)
    assert read_image_text(
        provider="dashscope", api_key=SECRET, base_url="", model="",
        image=b"\xff\xd8\xff", session=session,
        http=_models_http(["qwen-vl-plus", "qwen3.8-flash", "qwen3-vl-plus"], seen),
    ) == "标题"
    assert [body["model"] for _url, body in session.sent] == ["qwen-vl-plus", "qwen3.8-flash"]
    assert seen["urls"] == [COMPAT + "/models"]


def test_other_ocr_errors_do_not_fetch_a_substitute():
    from backend.core.image_providers import ImageError, read_image_text

    def http(url, *, headers, timeout, trust_env):
        raise AssertionError("must not list models")

    session = _OcrSession(lambda body: (401, {"error": {"message": "Invalid API-key", "code": "invalid_api_key"}}))
    with pytest.raises(ImageError):
        read_image_text(
            provider="dashscope", api_key=SECRET, base_url="", model="qwen-vl-plus",
            image=b"\xff\xd8\xff", session=session, http=http,
        )
    assert len(session.sent) == 1


def test_a_working_ocr_model_is_not_replaced(caplog):
    from backend.core.image_providers import read_image_text

    def http(url, *, headers, timeout, trust_env):
        raise AssertionError("must not list models")

    session = _OcrSession(lambda body: (200, OCR_OK))
    with caplog.at_level(logging.INFO):
        assert read_image_text(
            provider="dashscope", api_key=SECRET, base_url="", model="qwen-vl-plus",
            image=b"\xff\xd8\xff", session=session, http=http,
        ) == "标题"
    assert [body["model"] for _url, body in session.sent] == ["qwen-vl-plus"]
    assert SECRET not in caplog.text


def test_verify_endpoint_keeps_a_saved_ocr_model_and_resolves_only_the_fallback(monkeypatch):
    from backend.services import cover
    from backend.services.cover import CoverConfig

    def boom(url, *, headers, timeout, trust_env):
        raise AssertionError("saved id must not fetch the list")

    monkeypatch.setattr("backend.core.provider_model_fetch._default_http_get", boom)
    saved = CoverConfig(provider="dashscope", model="wanx2.1-t2i-turbo", api_key=SECRET, ocr_model="qwen-vl-plus")
    assert cover.verify_endpoint(saved)["model"] == "qwen-vl-plus"
    assert saved.ocr_model == "qwen-vl-plus"

    monkeypatch.setattr("backend.services.studio.vision_settings.effective", dict)
    seen = {"urls": []}
    monkeypatch.setattr(
        "backend.core.provider_model_fetch._default_http_get",
        _models_http(["qwen-plus", "qwen3-vl-plus"], seen),
    )
    cfg = CoverConfig(provider="dashscope", model="wanx2.1-t2i-turbo", api_key=SECRET, base_url=NATIVE)
    endpoint = cover.verify_endpoint(cfg)
    assert endpoint["model"] == "qwen3-vl-plus"
    assert endpoint["provider"] == "dashscope"
    assert cfg.model == "wanx2.1-t2i-turbo" and cfg.ocr_model == ""
    assert seen["urls"] == [COMPAT + "/models"]

    clear_remembered_models()
    monkeypatch.setattr(
        "backend.core.provider_model_fetch._default_http_get",
        _models_http(["qwen-plus"], {"urls": []}),
    )
    with pytest.raises(cover.ImageError, match="跳过校对"):
        cover.verify_endpoint(cfg)


def test_text_only_model_length_is_not_reported_as_truncation(monkeypatch):
    from backend.core.failure_codes import UserFacingError
    from backend.services.provider_validation import VISION_BLOCK_MESSAGE

    def urlopen(req, timeout=None):
        return io.BytesIO(json.dumps(
            {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}
        ).encode())

    monkeypatch.setattr(intelligence.urllib.request, "urlopen", urlopen)
    config = {"base_url": "https://api.deepseek.com", "model": "deepseek-flash", "api_key": SECRET, "timeout": 10,
              "identity": {"provider": "deepseek", "config_source": "preset"}}
    with pytest.raises(UserFacingError) as caught:
        intelligence.vision_call([{"type": "text", "text": "look"}], config=config)
    assert str(caught.value) == VISION_BLOCK_MESSAGE
    assert "output_truncated" not in str(caught.value)
    assert "截断" not in str(caught.value)
