"""云端兼容预设：DeepSeek / Kimi / GLM / Grok 还原成 openai + 官方地址。"""
import sys
import types

import pytest

from backend.core.cloud_presets import CLOUD_PRESETS, resolve_cloud_preset
from backend.core.llm_manager import LLMManager


class _FakeOpenAIClient:
    created = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        _FakeOpenAIClient.created.append(kwargs)
        message = types.SimpleNamespace(content="ok")
        choice = types.SimpleNamespace(message=message, finish_reason="stop")

        class _Completions:
            def create(self, **params):
                return types.SimpleNamespace(choices=[choice], usage=None)

        self.chat = types.SimpleNamespace(completions=_Completions())


@pytest.fixture
def fake_openai(monkeypatch):
    module = types.ModuleType("openai")
    module.OpenAI = _FakeOpenAIClient
    monkeypatch.setitem(sys.modules, "openai", module)
    _FakeOpenAIClient.created.clear()
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    for name in ("LLM_PROVIDER", "API_MODEL_NAME", "LLM_MODEL", "API_OPENAI_API_KEY", "OPENAI_API_KEY", "API_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    from backend.core import llm_manager as manager_module
    monkeypatch.setattr(manager_module.config_sync_service, "is_sync_needed", lambda: False)
    return _FakeOpenAIClient


def test_resolve_cloud_presets_use_official_endpoints():
    provider, url, preset = resolve_cloud_preset("deepseek")
    assert provider == "openai"
    assert url == "https://api.deepseek.com"
    assert preset.default_model == "deepseek-flash"

    assert resolve_cloud_preset("kimi")[1] == "https://api.moonshot.cn/v1"
    assert resolve_cloud_preset("glm")[2].default_model == "glm-5.3"
    assert resolve_cloud_preset("xai")[2].key == "grok"
    assert resolve_cloud_preset("dashscope") is None
    assert resolve_cloud_preset("openai") is None


def test_manager_uses_deepseek_official_key_not_openai(fake_openai, tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(
        '{"api": {"api_keys": {"openai": "sk-openai-should-not-be-used", "deepseek": "sk-deepseek-official"}, '
        '"api_provider": "deepseek", "api_model": "deepseek-flash"}}',
        encoding="utf-8",
    )
    info = LLMManager(settings_file=settings).get_current_provider_info()
    assert info["provider"] == "deepseek"
    assert info["backend_provider"] == "openai"
    assert info["base_url"] == "https://api.deepseek.com"
    assert info["model"] == "deepseek-flash"
    assert info["available"] is True
    assert fake_openai.created[-1]["api_key"] == "sk-deepseek-official"
    assert fake_openai.created[-1]["base_url"] == "https://api.deepseek.com"


def test_curated_lists_drop_retired_aliases():
    assert "gpt-4o" not in CLOUD_PRESETS
    assert set(CLOUD_PRESETS) == {"deepseek", "kimi", "glm", "grok"}
