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
    for name in ("LLM_PROVIDER", "API_MODEL_NAME", "LLM_MODEL", "API_OPENAI_API_KEY", "OPENAI_API_KEY", "API_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY", "API_INFISTAR_API_KEY", "INFISTAR_API_KEY", "API_API88_API_KEY", "API88_API_KEY"):
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
    assert resolve_cloud_preset("doubao")[1] == "https://ark.cn-beijing.volces.com/api/v3"
    assert resolve_cloud_preset("ark")[2].default_model == "doubao-seed-2-1-lite-260915"
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


def test_manager_uses_seed_ark_key_not_openai(fake_openai, tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(
        '{"api": {"api_keys": {"openai": "sk-openai-should-not-be-used", "seed": "ark-seed-official-key"}, '
        '"api_provider": "seed", "api_model": "doubao-seed-2-1-lite-260915"}}',
        encoding="utf-8",
    )
    info = LLMManager(settings_file=settings).get_current_provider_info()
    assert info["provider"] == "seed"
    assert info["backend_provider"] == "openai"
    assert info["base_url"] == "https://ark.cn-beijing.volces.com/api/v3"
    assert info["model"] == "doubao-seed-2-1-lite-260915"
    assert info["available"] is True
    assert fake_openai.created[-1]["api_key"] == "ark-seed-official-key"
    assert fake_openai.created[-1]["base_url"] == "https://ark.cn-beijing.volces.com/api/v3"


def test_curated_lists_drop_retired_aliases():
    assert "gpt-4o" not in CLOUD_PRESETS
    assert set(CLOUD_PRESETS) == {"deepseek", "seed", "kimi", "glm", "grok", "infistar", "api88"}


def test_infistar_sponsor_preset_uses_gateway_and_own_key(fake_openai, tmp_path):
    provider, url, preset = resolve_cloud_preset("infistar")
    assert provider == "openai"
    assert url == "https://infistar.cc/v1"
    # 多模型网关不预设型号；专属注册链接带推广参数
    assert preset.default_model == ""
    assert "aff=" in preset.docs_url

    settings = tmp_path / "settings.json"
    settings.write_text(
        '{"api": {"api_keys": {"openai": "sk-openai-should-not-be-used", "infistar": "sk-infistar-key-123"}, '
        '"api_provider": "infistar", "api_model": "deepseek-v4-pro"}}',
        encoding="utf-8",
    )
    info = LLMManager(settings_file=settings).get_current_provider_info()
    assert info["provider"] == "infistar"
    assert info["base_url"] == "https://infistar.cc/v1"
    assert info["model"] == "deepseek-v4-pro"
    assert fake_openai.created[-1]["api_key"] == "sk-infistar-key-123"
    assert fake_openai.created[-1]["base_url"] == "https://infistar.cc/v1"


def test_infistar_key_from_env(fake_openai, tmp_path, monkeypatch):
    monkeypatch.setenv("INFISTAR_API_KEY", "sk-infistar-from-env")
    settings = tmp_path / "settings.json"
    settings.write_text('{"api": {"api_keys": {}, "api_provider": "infistar", "api_model": "gpt-5-mini"}}', encoding="utf-8")
    LLMManager(settings_file=settings).get_current_provider_info()
    assert fake_openai.created[-1]["api_key"] == "sk-infistar-from-env"


def test_api88_sponsor_preset_uses_gateway_and_own_key(fake_openai, tmp_path):
    provider, url, preset = resolve_cloud_preset("api88")
    assert provider == "openai"
    assert url == "https://88api.ai/v1"
    # 多模型网关不预设型号；专属注册链接带推广参数
    assert preset.default_model == ""
    assert "aff=" in preset.docs_url

    settings = tmp_path / "settings.json"
    settings.write_text(
        '{"api": {"api_keys": {"openai": "sk-openai-should-not-be-used", "api88": "sk-api88-key-123"}, '
        '"api_provider": "api88", "api_model": "deepseek-v4-pro"}}',
        encoding="utf-8",
    )
    info = LLMManager(settings_file=settings).get_current_provider_info()
    assert info["provider"] == "api88"
    assert info["base_url"] == "https://88api.ai/v1"
    assert info["model"] == "deepseek-v4-pro"
    assert fake_openai.created[-1]["api_key"] == "sk-api88-key-123"
    assert fake_openai.created[-1]["base_url"] == "https://88api.ai/v1"


@pytest.mark.parametrize("env_name", ["API88_API_KEY", "API_API88_API_KEY"])
def test_api88_key_from_env(fake_openai, tmp_path, monkeypatch, env_name):
    monkeypatch.setenv(env_name, "sk-api88-from-env")
    settings = tmp_path / "settings.json"
    settings.write_text('{"api": {"api_keys": {}, "api_provider": "api88", "api_model": "gpt-5-mini"}}', encoding="utf-8")
    LLMManager(settings_file=settings).get_current_provider_info()
    assert fake_openai.created[-1]["api_key"] == "sk-api88-from-env"
