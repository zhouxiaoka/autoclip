import json
from types import SimpleNamespace

from backend.core.llm_manager import LLMManager
from backend.core.llm_providers import (
    AtlasCloudProvider,
    LLMProviderFactory,
    ProviderType,
)


def test_atlascloud_provider_uses_openai_compatible_endpoint(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["request"] = kwargs
            return SimpleNamespace(
                choices=[SimpleNamespace(
                    message=SimpleNamespace(content="ok"),
                    finish_reason="stop",
                )],
                usage=None,
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setitem(
        __import__("sys").modules,
        "openai",
        SimpleNamespace(OpenAI=FakeOpenAI),
    )

    provider = AtlasCloudProvider("test-key")
    response = provider.call("hello")

    assert captured["client"] == {
        "api_key": "test-key",
        "base_url": "https://api.atlascloud.ai/v1",
    }
    assert captured["request"]["model"] == "deepseek-ai/deepseek-v4-pro"
    assert response.content == "ok"


def test_manager_loads_atlascloud_desktop_settings(monkeypatch, tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({
        "api": {
            "api_provider": "atlascloud",
            "api_model": "deepseek-ai/deepseek-v4-pro",
            "api_keys": {"atlascloud": "test-key"},
        }
    }), encoding="utf-8")
    captured = {}

    def create_provider(provider_type, api_key, model_name, **kwargs):
        captured.update({
            "provider_type": provider_type,
            "api_key": api_key,
            "model_name": model_name,
        })
        return SimpleNamespace()

    monkeypatch.setattr(LLMManager, "_sync_config_if_needed", lambda self: None)
    monkeypatch.setattr(
        LLMProviderFactory,
        "create_provider",
        staticmethod(create_provider),
    )

    manager = LLMManager(settings_file)

    assert manager.current_provider is not None
    assert captured == {
        "provider_type": ProviderType.ATLASCLOUD,
        "api_key": "test-key",
        "model_name": "deepseek-ai/deepseek-v4-pro",
    }


def test_atlascloud_environment_fallback_selects_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("ATLASCLOUD_API_KEY", "environment-key")
    monkeypatch.setattr(LLMManager, "_sync_config_if_needed", lambda self: None)
    captured = {}

    def create_provider(provider_type, api_key, model_name, **kwargs):
        captured.update({
            "provider_type": provider_type,
            "api_key": api_key,
            "model_name": model_name,
        })
        return SimpleNamespace()

    monkeypatch.setattr(
        LLMProviderFactory,
        "create_provider",
        staticmethod(create_provider),
    )

    LLMManager(tmp_path / "missing-settings.json")

    assert captured == {
        "provider_type": ProviderType.ATLASCLOUD,
        "api_key": "environment-key",
        "model_name": "deepseek-ai/deepseek-v4-pro",
    }
