"""Offline regressions for provider and outer-client exception log boundaries."""
import logging
from types import SimpleNamespace

import pytest

from backend.core import llm_providers as providers

pytestmark = pytest.mark.stdlib_only

# Deliberately synthetic values; no real provider or user data is used.
ENDPOINT = "https://api.example.com/private-route?key=fixture-query"
ERROR = 'request failed: {"authorization": "Bearer fixture-credential"} ' + ENDPOINT


def fail(*args, **kwargs):
    raise RuntimeError(ERROR)


@pytest.fixture(autouse=True)
def offline_observation(monkeypatch):
    from backend.core import llm_telemetry
    monkeypatch.setattr(llm_telemetry, "observe_provider_call",
                        lambda provider, impl, *args, **kwargs: impl(provider, *args, **kwargs))


def assert_safe(text):
    assert "fixture-credential" not in text
    assert "fixture-query" not in text
    assert "https://" not in text
    assert "/private-route" not in text
    assert "api.example.com" in text


def make_provider(kind):
    # Bypass constructors so SDK initialization cannot make network requests.
    cls = {
        "dashscope-native": providers.DashScopeProvider,
        "dashscope-compatible": providers.DashScopeProvider,
        "openai": providers.OpenAIProvider,
        "gemini": providers.GeminiProvider,
        "siliconflow": providers.SiliconFlowProvider,
    }[kind]
    provider = object.__new__(cls)
    provider.api_key = "sk-fixture-key"
    provider.model_name = "fixture-model"
    provider.base_url = ENDPOINT
    provider.is_custom_endpoint = True
    provider.mode = "native" if kind.endswith("-native") else "compatible"
    provider._ds_generation = SimpleNamespace(call=fail)
    provider.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fail)),
        models=SimpleNamespace(generate_content=fail),
    )
    return provider


@pytest.mark.parametrize("kind", [
    "dashscope-native", "dashscope-compatible", "openai", "gemini", "siliconflow",
])
def test_provider_call_and_connection_logs_are_sanitized(kind, monkeypatch, caplog):
    import requests
    monkeypatch.setattr(requests, "post", fail)
    # DashScope native mode temporarily sets this variable.
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fixture-original")
    provider = make_provider(kind)
    caplog.set_level(logging.DEBUG, logger=providers.__name__)
    with pytest.raises(RuntimeError):
        provider.call("fixture prompt")
    assert_safe(caplog.text)
    caplog.clear()
    assert provider.test_connection() is False
    assert_safe(caplog.text)


def test_dashscope_outer_connection_error_is_sanitized(caplog):
    class InvalidKey:
        strip = staticmethod(fail)

    provider = make_provider("dashscope-native")
    provider.api_key = InvalidKey()
    assert provider.test_connection() is False
    assert_safe(caplog.text)


@pytest.mark.parametrize("kind", ["dashscope-native", "dashscope-compatible"])
def test_dashscope_constructed_api_errors_are_sanitized(kind, monkeypatch, caplog):
    import requests
    provider = make_provider(kind)
    monkeypatch.setenv("DASHSCOPE_API_KEY", "fixture-original")
    provider._ds_generation = SimpleNamespace(call=lambda **kwargs: SimpleNamespace(
        status_code=401, code="invalid_key", message=ERROR,
    ))
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: SimpleNamespace(
        status_code=401, json=lambda: {"message": ERROR},
    ))
    with pytest.raises(Exception) as raised:
        provider.call("fixture prompt")
    assert_safe(str(raised.value))
    assert_safe(caplog.text)


def test_provider_catalog_failure_is_sanitized(monkeypatch, caplog):
    monkeypatch.setattr(providers.LLMProviderFactory, "_providers", {providers.ProviderType.OPENAI: fail})
    assert providers.LLMProviderFactory.get_all_available_models() == {providers.ProviderType.OPENAI: []}
    assert_safe(caplog.text)


@pytest.mark.parametrize("kind", ["dashscope-compatible", "openai"])
def test_connection_key_format_warning_does_not_log_key(kind, monkeypatch, caplog):
    provider = make_provider(kind)
    provider.api_key = "fixture-key-prefix-must-stay-private"
    provider.is_custom_endpoint = False
    monkeypatch.setattr(provider, "call", fail)
    assert provider.test_connection() is False
    assert "fixture-key" not in caplog.text
    assert_safe(caplog.text)


def test_dashscope_request_metadata_does_not_log_keys_or_content(monkeypatch, caplog):
    import requests
    monkeypatch.setattr(requests, "post", fail)
    provider = make_provider("dashscope-compatible")
    provider.api_key = "fixture-key-private"
    provider.model_name = "AIza" + "A" * 35
    caplog.set_level(logging.DEBUG, logger=providers.__name__)
    with pytest.raises(RuntimeError):
        provider.call("fixture prompt", extra_body={"content": "fixture-private-content"})
    assert_safe(caplog.text)
    for private in ("fixture-key", "fixture-private-content", provider.model_name):
        assert private not in caplog.text


@pytest.mark.parametrize("model", ["AIza" + "A" * 35, "xai-" + "a" * 48])
def test_openai_retry_and_usage_logs_sanitize_model(model, caplog):
    provider = make_provider("openai")
    provider.model_name = model
    requests = []

    def create(**payload):
        requests.append(payload)
        if len(requests) == 1:
            error = RuntimeError("use max_completion_tokens instead of max_tokens")
            error.status_code = 400
            raise error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="fixture response"), finish_reason="stop")],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    provider.client.chat.completions.create = create
    caplog.set_level(logging.INFO, logger=providers.__name__)
    assert provider.call("fixture prompt", max_tokens=1).content == "fixture response"
    assert len(requests) == 2
    assert "redacted" in caplog.text
    assert model not in caplog.text


@pytest.mark.parametrize("method", ["call", "call_with_retry"])
def test_outer_client_failure_is_sanitized(method, caplog):
    from backend.utils.llm_client import LLMClient
    client = object.__new__(LLMClient)
    client.llm_manager = SimpleNamespace(call=fail, call_with_retry=fail)
    with pytest.raises(RuntimeError):
        getattr(client, method)("fixture prompt")
    assert_safe(caplog.text)
