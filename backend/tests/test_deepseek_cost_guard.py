"""DeepSeek thinking mode is on by default and bills reasoning as output tokens."""

import sys
import types
from types import SimpleNamespace

from backend.core.llm_providers import (
    DEEPSEEK_COMPLETION_TOKEN_CAP,
    deepseek_chat_kwargs,
    is_deepseek_endpoint,
)


def test_only_official_deepseek_host_is_guarded():
    assert is_deepseek_endpoint("https://api.deepseek.com")
    assert is_deepseek_endpoint("https://api.deepseek.com/v1")
    assert not is_deepseek_endpoint("")
    assert not is_deepseek_endpoint("https://api.openai.com/v1")
    assert not is_deepseek_endpoint("http://localhost:11434/v1")


def test_deepseek_disables_thinking_and_caps_unspecified_output():
    sent = deepseek_chat_kwargs("https://api.deepseek.com/v1", {"model": "deepseek-flash"})
    assert sent["extra_body"]["thinking"] == {"type": "disabled"}
    assert sent["max_tokens"] == DEEPSEEK_COMPLETION_TOKEN_CAP
    assert DEEPSEEK_COMPLETION_TOKEN_CAP < 384_000


def test_deepseek_keeps_caller_max_tokens():
    sent = deepseek_chat_kwargs(
        "https://api.deepseek.com",
        {"model": "deepseek-flash", "max_tokens": 1},
    )
    assert sent["max_tokens"] == 1
    assert sent["extra_body"]["thinking"]["type"] == "disabled"


def test_other_endpoints_are_left_unchanged():
    original = {"model": "gpt-5-mini", "max_tokens": 8}
    assert deepseek_chat_kwargs("", original) is original
    assert deepseek_chat_kwargs("https://api.openai.com/v1", original) is original


def _install_fake_openai(monkeypatch):
    calls = []

    class Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            usage = SimpleNamespace(prompt_tokens=3, completion_tokens=4, total_tokens=7)
            message = SimpleNamespace(content="ok")
            choice = SimpleNamespace(message=message, finish_reason="stop")
            return SimpleNamespace(choices=[choice], usage=usage)

    class Client:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.chat = SimpleNamespace(completions=Completions())

    module = types.ModuleType("openai")
    module.OpenAI = Client
    monkeypatch.setitem(sys.modules, "openai", module)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    return calls


def test_provider_call_sends_deepseek_guard(monkeypatch):
    calls = _install_fake_openai(monkeypatch)
    from backend.core.llm_providers import OpenAIProvider

    provider = OpenAIProvider(
        api_key="sk-deepseek",
        model_name="deepseek-flash",
        base_url="https://api.deepseek.com",
    )
    response = provider.call("提取大纲", {"text": "字幕"})
    assert response.content == "ok"
    assert calls[0]["model"] == "deepseek-flash"
    assert calls[0]["extra_body"]["thinking"] == {"type": "disabled"}
    assert calls[0]["max_tokens"] == DEEPSEEK_COMPLETION_TOKEN_CAP
    assert "字幕" in calls[0]["messages"][0]["content"]


def test_provider_call_leaves_official_openai_alone(monkeypatch):
    calls = _install_fake_openai(monkeypatch)
    from backend.core.llm_providers import OpenAIProvider

    provider = OpenAIProvider(api_key="sk-openai-key", model_name="gpt-5-mini")
    provider.call("hi", max_tokens=8)
    assert "extra_body" not in calls[0]
    assert calls[0]["max_tokens"] == 8
