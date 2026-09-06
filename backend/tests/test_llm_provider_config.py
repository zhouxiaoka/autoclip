"""OpenAI 兼容接口（自定义 base_url）与 provider 持久化 / 热重载的回归测试"""
import asyncio
import json
import os
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


@pytest.fixture
def fake_openai(monkeypatch):
    module = types.ModuleType("openai")
    module.OpenAI = _FakeOpenAIClient
    monkeypatch.setitem(sys.modules, "openai", module)
    _FakeOpenAIClient.created.clear()
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    return _FakeOpenAIClient


def test_openai_provider_defaults_to_official_endpoint(fake_openai):
    from backend.core.llm_providers import OpenAIProvider

    provider = OpenAIProvider(api_key="sk-test", model_name="gpt-4o-mini")

    assert provider.base_url == ""
    assert provider.is_custom_endpoint is False
    assert fake_openai.created[-1] == {"api_key": "sk-test"}


def test_openai_provider_uses_custom_base_url_and_placeholder_key(fake_openai):
    from backend.core.llm_providers import (
        OPENAI_COMPATIBLE_PLACEHOLDER_KEY,
        OpenAIProvider,
    )

    provider = OpenAIProvider(api_key="", model_name="qwen2.5:7b", base_url="http://localhost:11434/v1/")

    assert provider.base_url == "http://localhost:11434/v1"
    assert provider.is_custom_endpoint is True
    assert fake_openai.created[-1] == {
        "api_key": OPENAI_COMPATIBLE_PLACEHOLDER_KEY,
        "base_url": "http://localhost:11434/v1",
    }


def test_openai_provider_reads_base_url_from_env(fake_openai, monkeypatch):
    from backend.core.llm_providers import OpenAIProvider

    monkeypatch.setenv("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    provider = OpenAIProvider(api_key="zhipu-key-1234567890", model_name="glm-4-flash")

    assert provider.base_url == "https://open.bigmodel.cn/api/paas/v4"
    assert fake_openai.created[-1]["base_url"] == "https://open.bigmodel.cn/api/paas/v4"


def test_official_endpoint_still_rejects_short_key(fake_openai):
    from backend.core.llm_providers import OpenAIProvider

    provider = OpenAIProvider(api_key="short", model_name="gpt-4o-mini")
    assert provider.test_connection() is False


def _write_client_settings(path: Path, **api_overrides):
    api = {
        "api_keys": {"dashscope": "", "openai": "", "gemini": "", "siliconflow": ""},
        "api_model": "qwen-plus",
    }
    api.update(api_overrides)
    path.write_text(json.dumps({"api": api}), encoding="utf-8")


@pytest.fixture
def manager_env(monkeypatch, tmp_path, fake_openai):
    for name in ("LLM_PROVIDER", "API_MODEL_NAME", "LLM_MODEL", "API_OPENAI_API_KEY", "OPENAI_API_KEY",
                 "API_DASHSCOPE_API_KEY", "DASHSCOPE_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    # 不让配置同步服务碰真实用户目录
    from backend.core import llm_manager as manager_module
    monkeypatch.setattr(manager_module.config_sync_service, "is_sync_needed", lambda: False)
    return tmp_path / "settings.json"


def test_manager_honours_saved_provider_and_base_url(manager_env):
    from backend.core.llm_manager import LLMManager

    _write_client_settings(
        manager_env,
        api_provider="openai",
        api_base_url="https://api.deepseek.com/v1",
        api_model="deepseek-chat",
        api_keys={"dashscope": "", "openai": "sk-deepseek-key", "gemini": "", "siliconflow": ""},
    )
    manager = LLMManager(settings_file=manager_env)

    info = manager.get_current_provider_info()
    assert info["provider"] == "openai"
    assert info["model"] == "deepseek-chat"
    assert info["base_url"] == "https://api.deepseek.com/v1"
    assert info["available"] is True
    assert manager.current_provider.base_url == "https://api.deepseek.com/v1"


def test_manager_allows_keyless_custom_endpoint(manager_env):
    from backend.core.llm_manager import LLMManager

    _write_client_settings(manager_env, api_provider="openai", api_base_url="http://localhost:11434/v1",
                           api_model="qwen2.5:7b")
    manager = LLMManager(settings_file=manager_env)

    assert manager.current_provider is not None
    assert manager.current_provider.is_custom_endpoint is True


def test_manager_reloads_when_settings_file_changes(manager_env):
    from backend.core.llm_manager import LLMManager

    _write_client_settings(manager_env)  # 没有 key -> 未配置
    manager = LLMManager(settings_file=manager_env)
    assert manager.get_current_provider_info()["available"] is False

    _write_client_settings(manager_env, api_provider="openai", api_base_url="http://localhost:11434/v1",
                           api_model="qwen2.5:7b")
    # 同一秒内写两次 mtime 可能相同，强制改一下
    os.utime(manager_env, (manager_env.stat().st_atime, manager_env.stat().st_mtime + 5))

    info = manager.get_current_provider_info()
    assert info["available"] is True
    assert info["provider"] == "openai"
    assert info["model"] == "qwen2.5:7b"


def test_manager_env_fallbacks_for_docker(manager_env, monkeypatch):
    from backend.core.llm_manager import LLMManager

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    monkeypatch.setenv("API_OPENAI_API_KEY", "zhipu-key-1234567890")
    monkeypatch.setenv("API_MODEL_NAME", "glm-4-flash")

    manager = LLMManager(settings_file=manager_env)  # 文件不存在

    info = manager.get_current_provider_info()
    assert info == {
        "provider": "openai",
        "model": "glm-4-flash",
        "available": True,
        "display_name": "OpenAI / 兼容接口",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    }


class _ChatCapableClient(_FakeOpenAIClient):
    """带 chat.completions.create 的假客户端，记录请求模型名"""
    last_model = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        outer = self

        class _Completions:
            def create(self, **params):
                _ChatCapableClient.last_model = params["model"]
                message = types.SimpleNamespace(content="ok")
                choice = types.SimpleNamespace(message=message, finish_reason="stop")
                return types.SimpleNamespace(choices=[choice], usage=None)

        self.chat = types.SimpleNamespace(completions=_Completions())
        self.outer = outer


def test_test_api_endpoint_accepts_keyless_custom_endpoint(monkeypatch, fake_openai):
    sys.modules["openai"].OpenAI = _ChatCapableClient
    from backend.api.v1 import settings as settings_api

    monkeypatch.setattr(settings_api, "check_desktop_mode", lambda relaxed=False: True)
    request = settings_api.TestApiRequest(provider="openai", api_key="", base_url="http://localhost:11434/v1",
                                          model="qwen2.5:7b")

    result = asyncio.run(settings_api.test_api_connection(request))

    assert result["success"] is True, result
    assert _ChatCapableClient.created[-1]["base_url"] == "http://localhost:11434/v1"
    assert _ChatCapableClient.last_model == "qwen2.5:7b"


def test_test_api_endpoint_still_validates_official_key(monkeypatch, fake_openai):
    from backend.api.v1 import settings as settings_api

    monkeypatch.setattr(settings_api, "check_desktop_mode", lambda relaxed=False: True)
    request = settings_api.TestApiRequest(provider="openai", api_key="short")

    result = asyncio.run(settings_api.test_api_connection(request))

    assert result["success"] is False
    assert "过短" in result["error"]


def test_settings_file_provider_wins_over_env(manager_env, monkeypatch):
    from backend.core.llm_manager import LLMManager

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("API_MODEL_NAME", "glm-4-flash")
    _write_client_settings(manager_env, api_provider="dashscope", api_model="qwen-max",
                           api_keys={"dashscope": "", "openai": "", "gemini": "", "siliconflow": ""})

    manager = LLMManager(settings_file=manager_env)
    assert manager.settings["llm_provider"] == "dashscope"
    assert manager.settings["model_name"] == "qwen-max"
