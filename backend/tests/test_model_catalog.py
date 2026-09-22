"""云端模型目录：内置名单、过滤、合并，以及有密钥时实时拉取。"""
import asyncio

import pytest

from backend.core import model_catalog


@pytest.fixture(autouse=True)
def _clear_cache():
    model_catalog.clear_model_list_cache()
    yield
    model_catalog.clear_model_list_cache()


def test_curated_catalog_includes_current_flagships():
    dashscope = model_catalog.curated_models("dashscope")
    openai = model_catalog.curated_models("openai")
    gemini = model_catalog.curated_models("gemini")
    deepseek = model_catalog.curated_models("deepseek")
    seed = model_catalog.curated_models("seed")
    kimi = model_catalog.curated_models("kimi")

    assert dashscope[0] == "qwen3.8-max"
    assert "qwen-plus" in dashscope
    assert "qwen3.8-flash" in dashscope
    assert "qwen-turbo" not in dashscope
    assert "qwen-long" not in dashscope
    assert "gpt-5" in openai
    assert "gpt-5.6-terra" in openai
    assert "gpt-4o" not in openai
    assert "gpt-4o-mini" not in openai
    assert "gemini-3.8-flash" in gemini
    assert "gemini-2.5-flash" in gemini
    assert "gemini-1.5-pro" not in gemini
    assert "deepseek-flash" in deepseek
    assert "deepseek-v4-pro" in deepseek
    assert "deepseek-chat" not in deepseek
    assert "doubao-seed-2-1-lite-260915" in seed
    assert "doubao-seed-2-1-pro-260915" in seed
    assert "kimi-k3" in kimi
    assert "siliconflow" not in model_catalog.CURATED_MODELS
    assert model_catalog.default_model_for("dashscope") == "qwen-plus"
    assert model_catalog.default_model_for("gemini") == "gemini-3.8-flash"
    assert model_catalog.default_model_for("deepseek") == "deepseek-flash"
    assert model_catalog.default_model_for("seed") == "doubao-seed-2-1-lite-260915"


def test_is_chat_model_drops_embeddings_and_media():
    assert model_catalog.is_chat_model("qwen-plus", "dashscope")
    assert not model_catalog.is_chat_model("text-embedding-v4", "dashscope")
    assert not model_catalog.is_chat_model("qwen-audio-3.0-tts-plus", "dashscope")
    assert model_catalog.is_chat_model("gpt-5-mini", "openai", official=True)
    assert not model_catalog.is_chat_model("whisper-1", "openai", official=True)
    assert not model_catalog.is_chat_model("dall-e-3", "openai", official=True)
    # 自建兼容接口：自定义名字要留下来
    assert model_catalog.is_chat_model("glm-4-flash", "openai", official=False)
    assert not model_catalog.is_chat_model("bge-m3-embedding", "openai", official=False)
    assert model_catalog.is_chat_model("gemini-3.8-flash", "gemini")
    assert model_catalog.is_chat_model("gemini-2.5-flash", "gemini")
    assert not model_catalog.is_chat_model("imagen-4.0-generate", "gemini")
    assert not model_catalog.is_chat_model("gemini-3.8-live", "gemini")
    assert not model_catalog.is_chat_model("gemini-3.1-flash-image", "gemini")
    assert model_catalog.is_chat_model("doubao-seed-2-1-lite-260915", "seed")
    assert not model_catalog.is_chat_model("doubao-seedream-5-0-260128", "seed")
    assert not model_catalog.is_chat_model("doubao-seedance-2-0", "seed")


def test_merge_keeps_curated_first_and_drops_dated_snapshots():
    merged = model_catalog.merge_models(
        ["qwen-plus", "qwen3.8-max"],
        ["qwen3.8-max", "qwen3.8-max-2026-09-01", "qwen3.9-preview", "text-embedding-v4"],
    )
    assert merged[:2] == ["qwen-plus", "qwen3.8-max"]
    assert "qwen3.9-preview" in merged
    assert "qwen3.8-max-2026-09-01" not in merged


def test_should_fetch_live_only_with_key_or_custom_openai_url():
    assert not model_catalog.should_fetch_live("dashscope", "", "")
    assert model_catalog.should_fetch_live("dashscope", "sk-test-key-123", "")
    assert not model_catalog.should_fetch_live("openai", "", "")
    assert not model_catalog.should_fetch_live("openai", "", "https://api.openai.com/v1")
    assert model_catalog.should_fetch_live("openai", "", "https://api.deepseek.com/v1")
    assert not model_catalog.should_fetch_live("ollama", "sk-x", "")


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _FakeAsyncClient:
    calls = []
    routes = {}

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, headers=None, params=None):
        _FakeAsyncClient.calls.append({"url": url, "headers": headers or {}, "params": params or {}, "trust_env": self.kwargs.get("trust_env")})
        if url not in _FakeAsyncClient.routes:
            raise RuntimeError(f"unexpected url {url}")
        payload, status = _FakeAsyncClient.routes[url]
        return _FakeResponse(payload, status)


def test_list_available_models_without_key_stays_on_catalog():
    result = asyncio.run(model_catalog.list_available_models("dashscope"))
    assert result.source == "catalog"
    assert result.reachable is False
    assert "qwen3.8-max" in result.models
    assert result.catalog["openai"][0].startswith("gpt-")


def test_list_available_models_merges_live_dashscope(monkeypatch):
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.routes = {
        "https://dashscope.aliyuncs.com/compatible-mode/v1/models": (
            {"data": [
                {"id": "qwen3.8-max"},
                {"id": "qwen3.9-preview"},
                {"id": "text-embedding-v4"},
                {"id": "qwen-plus-2026-01-01"},
            ]},
            200,
        )
    }
    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(model_catalog.list_available_models("dashscope", api_key="sk-test-key-123456"))
    assert result.source == "live"
    assert result.reachable is True
    assert result.models[0] == "qwen3.8-max"
    assert "qwen-plus" in result.models
    assert "qwen3.9-preview" in result.models
    assert "text-embedding-v4" not in result.models
    assert "qwen-plus-2026-01-01" not in result.models
    assert _FakeAsyncClient.calls[0]["headers"]["Authorization"].startswith("Bearer sk-")


def test_list_available_models_gemini_pagination(monkeypatch):
    import httpx

    class _PagedClient(_FakeAsyncClient):
        async def get(self, url, headers=None, params=None):
            _FakeAsyncClient.calls.append({"url": url, "params": params or {}})
            if params and params.get("pageToken") == "p2":
                return _FakeResponse({
                    "models": [
                        {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
                        {"name": "models/imagen-4.0", "supportedGenerationMethods": ["generateContent"]},
                    ]
                })
            return _FakeResponse({
                "models": [
                    {"name": "models/gemini-3-pro", "supportedGenerationMethods": ["generateContent"]},
                    {"name": "models/embedding-001", "supportedGenerationMethods": ["embedContent"]},
                ],
                "nextPageToken": "p2",
            })

    _FakeAsyncClient.calls = []
    monkeypatch.setattr(httpx, "AsyncClient", _PagedClient)

    result = asyncio.run(model_catalog.list_available_models("gemini", api_key="AIza-test-key-123456"))
    assert result.source == "live"
    assert "gemini-3-pro" in result.models
    assert "gemini-2.5-flash" in result.models
    assert "embedding-001" not in result.models
    assert "imagen-4.0" not in result.models
    assert len(_FakeAsyncClient.calls) == 2


def test_list_available_models_live_failure_falls_back(monkeypatch):
    import httpx

    class _Boom(_FakeAsyncClient):
        async def get(self, url, headers=None, params=None):
            raise RuntimeError("timeout")

    monkeypatch.setattr(httpx, "AsyncClient", _Boom)
    result = asyncio.run(model_catalog.list_available_models("openai", api_key="sk-test-key-123456"))
    assert result.source == "catalog"
    assert result.reachable is False
    assert result.error
    assert "gpt-5" in result.models


def test_result_payload_shape_for_settings_page():
    result = model_catalog.ModelListResult(
        provider="dashscope",
        source="live",
        reachable=True,
        default_model="qwen-plus",
        models=["qwen-plus", "qwen3.8-max"],
        catalog={"dashscope": ["qwen-plus"]},
    )
    payload = result.as_dict()
    assert payload["source"] == "live"
    assert payload["models"] == ["qwen-plus", "qwen3.8-max"]
    assert payload["catalog"]["dashscope"] == ["qwen-plus"]
    assert "error" not in payload


def test_provider_catalog_infos_follow_curated_list():
    from backend.core.llm_providers import ProviderType, _catalog_model_infos

    names = [m.name for m in _catalog_model_infos(ProviderType.DASHSCOPE)]
    assert names == model_catalog.curated_models("dashscope")
    openai_names = [m.name for m in _catalog_model_infos(ProviderType.OPENAI)]
    assert "gpt-5" in openai_names
