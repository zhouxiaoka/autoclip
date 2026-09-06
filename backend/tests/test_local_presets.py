"""本地模型预设（ollama / lmstudio）：provider 解析、LLMManager 还原、test-api 接受预设、本地地址不走代理"""
import asyncio
import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class _FakeOpenAIClient:
    created = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        _FakeOpenAIClient.created.append(kwargs)
        message = types.SimpleNamespace(content="ok")
        choice = types.SimpleNamespace(message=message, finish_reason="stop")

        class _Completions:
            def create(self, **params):
                _FakeOpenAIClient.last_model = params["model"]
                return types.SimpleNamespace(choices=[choice], usage=None)

        self.chat = types.SimpleNamespace(completions=_Completions())


@pytest.fixture
def fake_openai(monkeypatch):
    module = types.ModuleType("openai")
    module.OpenAI = _FakeOpenAIClient
    monkeypatch.setitem(sys.modules, "openai", module)
    _FakeOpenAIClient.created.clear()
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    for name in ("LLM_PROVIDER", "API_MODEL_NAME", "LLM_MODEL", "API_OPENAI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    from backend.core import llm_manager as manager_module
    monkeypatch.setattr(manager_module.config_sync_service, "is_sync_needed", lambda: False)
    return _FakeOpenAIClient


# ---------------------------------------------------------------- resolve ---
def test_resolve_provider_maps_presets_to_openai_compatible():
    from backend.core.local_presets import resolve_provider

    assert resolve_provider("ollama") == ("openai", "http://localhost:11434/v1", "ollama")
    assert resolve_provider("LM-Studio") == ("openai", "http://localhost:1234/v1", "lmstudio")
    # 用户改了端口：保留自定义地址
    assert resolve_provider("ollama", "http://192.168.1.8:11434/v1") == ("openai", "http://192.168.1.8:11434/v1", "ollama")
    # 非预设原样返回
    assert resolve_provider("dashscope") == ("dashscope", "", None)
    assert resolve_provider("openai", "https://api.deepseek.com/v1") == ("openai", "https://api.deepseek.com/v1", None)


def test_is_local_url_detects_loopback_and_lan():
    from backend.core.llm_providers import is_local_url

    assert is_local_url("http://localhost:11434/v1")
    assert is_local_url("http://127.0.0.1:1234/v1")
    assert is_local_url("http://[::1]:8000/v1")
    assert is_local_url("http://192.168.1.8:11434/v1")
    assert is_local_url("http://host.docker.internal:11434/v1")
    assert not is_local_url("https://api.openai.com/v1")
    assert not is_local_url("https://api.deepseek.com/v1")
    assert not is_local_url("")


def test_local_endpoint_client_bypasses_system_proxy(fake_openai):
    from backend.core.llm_providers import OpenAIProvider

    OpenAIProvider(api_key="", model_name="qwen2.5:7b", base_url="http://localhost:11434/v1")
    assert fake_openai.created[-1]["http_client"].trust_env is False

    OpenAIProvider(api_key="sk-x", model_name="deepseek-chat", base_url="https://api.deepseek.com/v1")
    assert "http_client" not in fake_openai.created[-1]


# ---------------------------------------------------------------- manager ---
def _write(path: Path, **api):
    base = {"api_keys": {"dashscope": "", "openai": "sk-user-openai-key", "gemini": "", "siliconflow": ""},
            "api_model": "qwen-plus"}
    base.update(api)
    path.write_text(json.dumps({"api": base}), encoding="utf-8")


def test_manager_restores_ollama_preset(fake_openai, tmp_path):
    from backend.core.llm_manager import LLMManager

    settings = tmp_path / "settings.json"
    _write(settings, api_provider="ollama", api_base_url="", api_model="qwen2.5:7b")
    manager = LLMManager(settings_file=settings)

    info = manager.get_current_provider_info()
    assert info["provider"] == "ollama"
    assert info["backend_provider"] == "openai"
    assert info["base_url"] == "http://localhost:11434/v1"
    assert info["model"] == "qwen2.5:7b"
    assert info["available"] is True
    assert "本地" in info["display_name"]
    # 不把用户的 OpenAI key 发给本地服务
    assert fake_openai.created[-1]["api_key"] == "EMPTY"


def test_manager_preset_uses_default_model_when_unset(fake_openai, tmp_path):
    from backend.core.llm_manager import LLMManager

    settings = tmp_path / "settings.json"
    _write(settings, api_provider="ollama")  # api_model 仍是 dashscope 的默认 qwen-plus
    info = LLMManager(settings_file=settings).get_current_provider_info()
    assert info["model"] == "qwen2.5:7b"


def test_manager_env_provider_ollama(fake_openai, tmp_path, monkeypatch):
    """Docker / CLI：LLM_PROVIDER=ollama 也能用"""
    from backend.core.llm_manager import LLMManager

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "llama3.1:8b")
    info = LLMManager(settings_file=tmp_path / "missing.json").get_current_provider_info()
    assert (info["provider"], info["model"], info["base_url"]) == ("ollama", "llama3.1:8b", "http://localhost:11434/v1")


# ---------------------------------------------------------------- api ---
def test_test_api_accepts_preset_provider(fake_openai, monkeypatch):
    from backend.api.v1 import settings as settings_api

    monkeypatch.setattr(settings_api, "check_desktop_mode", lambda relaxed=False: True)
    req = settings_api.TestApiRequest(provider="ollama", api_key="", model="qwen2.5:7b")
    result = asyncio.run(settings_api.test_api_connection(req))

    assert result["success"] is True, result
    assert result["provider"] == "ollama"
    assert fake_openai.created[-1]["base_url"] == "http://localhost:11434/v1"
    assert _FakeOpenAIClient.last_model == "qwen2.5:7b"


def test_local_presets_endpoint_lists_both():
    from backend.api.v1 import settings as settings_api

    data = asyncio.run(settings_api.get_local_presets())
    keys = [p["key"] for p in data["presets"]]
    assert keys == ["ollama", "lmstudio"]
    assert all(p["base_url"].startswith("http://localhost") for p in data["presets"])
