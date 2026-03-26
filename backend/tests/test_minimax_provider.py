"""
MiniMax LLM Provider Unit & Integration Tests
"""
import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

from backend.core.llm_providers import (
    ProviderType,
    ModelInfo,
    LLMResponse,
    LLMProvider,
    MiniMaxProvider,
    LLMProviderFactory,
)


# ---------------------------------------------------------------------------
# Helper: create a MiniMaxProvider with mocked openai client
# ---------------------------------------------------------------------------

def _make_provider(model_name="MiniMax-M2.7"):
    """Create a MiniMaxProvider with the openai.OpenAI constructor mocked."""
    mock_client = MagicMock()
    with patch.dict("sys.modules", {"openai": MagicMock()}):
        import openai as mock_openai_mod
        mock_openai_mod.OpenAI.return_value = mock_client
        provider = MiniMaxProvider(api_key="test-key", model_name=model_name)
    provider.client = mock_client
    return provider, mock_client


def _mock_response(content="hello", finish_reason="stop", with_usage=True):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.choices[0].finish_reason = finish_reason
    if with_usage:
        resp.usage = MagicMock()
        resp.usage.prompt_tokens = 10
        resp.usage.completion_tokens = 5
        resp.usage.total_tokens = 15
    else:
        resp.usage = None
    return resp


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------

class TestProviderTypeEnum:
    """ProviderType enum includes MiniMax"""

    def test_minimax_enum_exists(self):
        assert ProviderType.MINIMAX.value == "minimax"

    def test_minimax_enum_from_string(self):
        assert ProviderType("minimax") == ProviderType.MINIMAX

    def test_all_providers_present(self):
        names = {p.value for p in ProviderType}
        assert "minimax" in names
        assert len(names) >= 5


class TestMiniMaxProviderInit:
    """MiniMaxProvider initialization"""

    def test_default_model(self):
        provider, _ = _make_provider()
        assert provider.model_name == "MiniMax-M2.7"
        assert provider.api_key == "test-key"

    def test_custom_model(self):
        provider, _ = _make_provider("MiniMax-M2.5")
        assert provider.model_name == "MiniMax-M2.5"

    def test_base_url_constant(self):
        assert MiniMaxProvider.BASE_URL == "https://api.minimax.io/v1"


class TestMiniMaxProviderCall:
    """MiniMaxProvider.call()"""

    def test_basic_call(self):
        provider, client = _make_provider()
        client.chat.completions.create.return_value = _mock_response("hi")
        result = provider.call("test prompt")
        assert isinstance(result, LLMResponse)
        assert result.content == "hi"
        assert result.usage["total_tokens"] == 15
        assert result.finish_reason == "stop"

    def test_call_with_input_data_string(self):
        provider, client = _make_provider()
        client.chat.completions.create.return_value = _mock_response("ok")
        provider.call("prompt", input_data="extra data")
        args = client.chat.completions.create.call_args
        msg = args[1]["messages"][0]["content"]
        assert "extra data" in msg

    def test_call_with_input_data_dict(self):
        provider, client = _make_provider()
        client.chat.completions.create.return_value = _mock_response("ok")
        provider.call("prompt", input_data={"key": "value"})
        args = client.chat.completions.create.call_args
        msg = args[1]["messages"][0]["content"]
        assert "key" in msg and "value" in msg

    def test_think_tag_stripping(self):
        provider, client = _make_provider()
        content = "<think>internal reasoning</think>actual answer"
        client.chat.completions.create.return_value = _mock_response(content)
        result = provider.call("test")
        assert result.content == "actual answer"
        assert "<think>" not in result.content

    def test_no_think_tag_passthrough(self):
        provider, client = _make_provider()
        client.chat.completions.create.return_value = _mock_response("plain text")
        result = provider.call("test")
        assert result.content == "plain text"

    def test_temperature_clamping_zero(self):
        provider, client = _make_provider()
        client.chat.completions.create.return_value = _mock_response("ok")
        provider.call("test", temperature=0)
        args = client.chat.completions.create.call_args
        assert args[1]["temperature"] == 0.01

    def test_temperature_clamping_above_one(self):
        provider, client = _make_provider()
        client.chat.completions.create.return_value = _mock_response("ok")
        provider.call("test", temperature=2.0)
        args = client.chat.completions.create.call_args
        assert args[1]["temperature"] == 1.0

    def test_temperature_valid_passthrough(self):
        provider, client = _make_provider()
        client.chat.completions.create.return_value = _mock_response("ok")
        provider.call("test", temperature=0.7)
        args = client.chat.completions.create.call_args
        assert args[1]["temperature"] == 0.7

    def test_temperature_edge_one(self):
        provider, client = _make_provider()
        client.chat.completions.create.return_value = _mock_response("ok")
        provider.call("test", temperature=1.0)
        args = client.chat.completions.create.call_args
        assert args[1]["temperature"] == 1.0

    def test_call_no_usage(self):
        provider, client = _make_provider()
        resp = _mock_response("ok", with_usage=False)
        client.chat.completions.create.return_value = resp
        result = provider.call("test")
        assert result.usage is None

    def test_call_none_content(self):
        provider, client = _make_provider()
        resp = _mock_response()
        resp.choices[0].message.content = None
        client.chat.completions.create.return_value = resp
        result = provider.call("test")
        assert result.content == ""

    def test_call_api_error(self):
        provider, client = _make_provider()
        client.chat.completions.create.side_effect = Exception("API error")
        with pytest.raises(Exception, match="API error"):
            provider.call("test")

    def test_model_passed_to_api(self):
        provider, client = _make_provider("MiniMax-M2.5-highspeed")
        client.chat.completions.create.return_value = _mock_response("ok")
        provider.call("test")
        args = client.chat.completions.create.call_args
        assert args[1]["model"] == "MiniMax-M2.5-highspeed"

    def test_no_temperature_kwarg_when_not_given(self):
        provider, client = _make_provider()
        client.chat.completions.create.return_value = _mock_response("ok")
        provider.call("test")
        args = client.chat.completions.create.call_args
        assert "temperature" not in args[1]


class TestMiniMaxProviderTestConnection:
    """MiniMaxProvider.test_connection()"""

    def test_connection_success_chinese(self):
        provider, client = _make_provider()
        client.chat.completions.create.return_value = _mock_response("测试成功")
        assert provider.test_connection() is True

    def test_connection_success_english(self):
        provider, client = _make_provider()
        client.chat.completions.create.return_value = _mock_response("Success")
        assert provider.test_connection() is True

    def test_connection_failure(self):
        provider, client = _make_provider()
        client.chat.completions.create.side_effect = Exception("fail")
        assert provider.test_connection() is False

    def test_connection_unrelated_response(self):
        provider, client = _make_provider()
        client.chat.completions.create.return_value = _mock_response("unrelated")
        assert provider.test_connection() is False


class TestMiniMaxProviderGetModels:
    """MiniMaxProvider.get_available_models()"""

    def test_model_list(self):
        provider, _ = _make_provider()
        models = provider.get_available_models()
        assert len(models) == 4
        names = [m.name for m in models]
        assert "MiniMax-M2.7" in names
        assert "MiniMax-M2.7-highspeed" in names
        assert "MiniMax-M2.5" in names
        assert "MiniMax-M2.5-highspeed" in names

    def test_model_info_fields(self):
        provider, _ = _make_provider()
        models = provider.get_available_models()
        m27 = [m for m in models if m.name == "MiniMax-M2.7"][0]
        assert isinstance(m27, ModelInfo)
        assert m27.provider == ProviderType.MINIMAX
        assert m27.max_tokens == 1000000

    def test_model_provider_type(self):
        provider, _ = _make_provider()
        for model in provider.get_available_models():
            assert model.provider == ProviderType.MINIMAX

    def test_m25_context_length(self):
        provider, _ = _make_provider()
        models = provider.get_available_models()
        m25 = [m for m in models if m.name == "MiniMax-M2.5"][0]
        assert m25.max_tokens == 204800


class TestLLMProviderFactory:
    """LLMProviderFactory includes MiniMax"""

    def test_minimax_in_providers(self):
        assert ProviderType.MINIMAX in LLMProviderFactory._providers

    def test_minimax_provider_class(self):
        assert LLMProviderFactory._providers[ProviderType.MINIMAX] is MiniMaxProvider

    def test_create_minimax_provider(self):
        provider, _ = _make_provider()
        assert isinstance(provider, MiniMaxProvider)
        assert provider.model_name == "MiniMax-M2.7"


class TestLLMManagerMiniMax:
    """LLM Manager recognizes MiniMax"""

    def test_default_settings_include_minimax_key(self):
        from backend.core.llm_manager import LLMManager
        with patch.object(LLMManager, "_initialize_provider"):
            manager = LLMManager.__new__(LLMManager)
            manager.settings_file = MagicMock()
            manager.settings_file.exists.return_value = False
            manager.current_provider = None
            settings = manager._load_settings()
            assert "minimax_api_key" in settings

    def test_get_api_key_for_minimax(self):
        from backend.core.llm_manager import LLMManager
        with patch.object(LLMManager, "_initialize_provider"):
            manager = LLMManager.__new__(LLMManager)
            manager.settings_file = MagicMock()
            manager.settings_file.exists.return_value = False
            manager.current_provider = None
            manager.settings = {"minimax_api_key": "test-key-123"}
            key = manager._get_api_key_for_provider(ProviderType.MINIMAX)
            assert key == "test-key-123"

    def test_display_name(self):
        from backend.core.llm_manager import LLMManager
        with patch.object(LLMManager, "_initialize_provider"):
            manager = LLMManager.__new__(LLMManager)
            manager.current_provider = None
            name = manager._get_provider_display_name(ProviderType.MINIMAX)
            assert name == "MiniMax"

    def test_empty_minimax_key_returns_empty(self):
        from backend.core.llm_manager import LLMManager
        with patch.object(LLMManager, "_initialize_provider"):
            manager = LLMManager.__new__(LLMManager)
            manager.settings = {"minimax_api_key": ""}
            key = manager._get_api_key_for_provider(ProviderType.MINIMAX)
            assert key == ""


# ---------------------------------------------------------------------------
# Integration Tests (require MINIMAX_API_KEY env var)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.environ.get("MINIMAX_API_KEY"),
    reason="MINIMAX_API_KEY not set"
)
class TestMiniMaxIntegration:
    """Integration tests against live MiniMax API"""

    def _make_live_provider(self, model="MiniMax-M2.7"):
        api_key = os.environ["MINIMAX_API_KEY"]
        return MiniMaxProvider(api_key=api_key, model_name=model)

    def test_live_call(self):
        provider = self._make_live_provider()
        result = provider.call("Reply with exactly: hello")
        assert isinstance(result, LLMResponse)
        assert len(result.content) > 0

    def test_live_test_connection(self):
        provider = self._make_live_provider()
        assert provider.test_connection() is True

    def test_live_call_highspeed(self):
        provider = self._make_live_provider("MiniMax-M2.7-highspeed")
        result = provider.call("Reply with exactly: hi")
        assert isinstance(result, LLMResponse)
        assert len(result.content) > 0
