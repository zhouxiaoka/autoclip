"""#333: OpenAI o-series / gpt-5+ reject max_tokens and ask for max_completion_tokens."""
import io
import json
import urllib.error

import pytest

from backend.core import llm_providers
from backend.core.llm_providers import OpenAIProvider, token_param_kwargs, uses_max_completion_tokens

UNSUPPORTED = ("Error code: 400 - {'error': {'message': \"Unsupported parameter: 'max_tokens' is not supported "
               "with this model. Use 'max_completion_tokens' instead.\", 'param': 'max_tokens'}}")


@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-5.6-luna", "gpt-5", "gpt-5-mini", "o1", "o3-mini", "o4-mini", "gpt-10"])
def test_known_reasoning_models_on_official_openai(model):
    assert uses_max_completion_tokens(model, "")
    assert uses_max_completion_tokens(model, "https://api.openai.com/v1")


@pytest.mark.parametrize("model,base", [
    ("gpt-4o-mini", ""), ("gpt-4.1", ""), ("gpt-3.5-turbo", ""),
    ("gpt-5", "https://api.deepseek.com"), ("o3", "http://localhost:11434/v1"),
    ("qwen3.8-flash", "https://dashscope.aliyuncs.com/compatible-mode/v1"), ("deepseek-chat", "https://api.deepseek.com"),
])
def test_other_models_and_compatible_endpoints_keep_max_tokens(model, base):
    request = {"model": model, "max_tokens": 5}
    assert token_param_kwargs(model, base, request) == request


class _BadRequest(Exception):
    status_code = 400


class _Completions:
    def __init__(self, fail_first):
        self.calls, self.fail_first = [], fail_first

    def create(self, **payload):
        self.calls.append(payload)
        if self.fail_first and len(self.calls) == 1:
            raise _BadRequest(UNSUPPORTED)
        message = type("M", (), {"content": "ok"})()
        choice = type("C", (), {"message": message, "finish_reason": "stop"})()
        return type("R", (), {"choices": [choice], "usage": None})()


def _provider(model, base_url="", fail_first=False):
    provider = OpenAIProvider("sk-test-key-123456", model, base_url=base_url)
    completions = _Completions(fail_first)
    provider.client = type("Client", (), {"chat": type("Chat", (), {"completions": completions})()})()
    return provider, completions


def test_connection_test_sends_max_completion_tokens_for_gpt6():
    provider, completions = _provider("gpt-6-luna")
    assert provider.test_connection()
    assert "max_tokens" not in completions.calls[0] and completions.calls[0]["max_completion_tokens"] >= 16


def test_gpt4o_mini_connection_test_still_uses_max_tokens():
    provider, completions = _provider("gpt-4o-mini")
    assert provider.test_connection()
    assert completions.calls[0]["max_tokens"] == 1 and "max_completion_tokens" not in completions.calls[0]


def test_unknown_model_retries_once_when_400_names_the_param():
    provider, completions = _provider("future-reasoner", base_url="https://relay.example.com/v1", fail_first=True)
    assert provider.call("hi", max_tokens=100).content == "ok"
    assert len(completions.calls) == 2
    assert completions.calls[0]["max_tokens"] == 100
    assert completions.calls[1]["max_completion_tokens"] == 100 and "max_tokens" not in completions.calls[1]


def test_other_400s_are_not_retried():
    provider, completions = _provider("gpt-4o-mini")
    completions.create = lambda **p: completions.calls.append(p) or (_ for _ in ()).throw(_BadRequest("invalid model"))
    with pytest.raises(_BadRequest):
        provider.call("hi", max_tokens=10)
    assert len(completions.calls) == 1


def _vision_config(model, base="https://api.openai.com/v1"):
    return {"api_key": "sk-x", "base_url": base, "model": model, "timeout": 5}


def _ok_response():
    body = {"choices": [{"message": {"content": '{"color": "red"}'}, "finish_reason": "stop"}]}
    return io.BytesIO(json.dumps(body).encode())


@pytest.fixture
def no_checkpoint(monkeypatch):
    monkeypatch.setattr("backend.core.project_cancellation.checkpoint", lambda: None)


def test_vision_pipeline_uses_max_completion_tokens_for_gpt5(monkeypatch, no_checkpoint):
    from backend.services.studio import intelligence
    sent = []
    def urlopen(req, timeout=None):
        sent.append(json.loads(req.data))
        return _ok_response()
    monkeypatch.setattr(intelligence.urllib.request, "urlopen", urlopen)
    assert intelligence.vision_call([{"type": "text", "text": "x"}], config=_vision_config("gpt-5")) == {"color": "red"}
    assert "max_tokens" not in sent[0] and sent[0]["max_completion_tokens"] == 4000


def test_vision_pipeline_retries_once_on_named_400(monkeypatch, no_checkpoint):
    from backend.services.studio import intelligence
    sent = []
    def urlopen(req, timeout=None):
        sent.append(json.loads(req.data))
        if len(sent) == 1:
            raise urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, io.BytesIO(UNSUPPORTED.encode()))
        return _ok_response()
    monkeypatch.setattr(intelligence.urllib.request, "urlopen", urlopen)
    config = _vision_config("relay-vision", base="https://relay.example.com/v1")
    assert intelligence.vision_call([{"type": "text", "text": "x"}], config=config) == {"color": "red"}
    assert sent[0]["max_tokens"] == 4000 and sent[1]["max_completion_tokens"] == 4000 and len(sent) == 2


def test_vision_pipeline_keeps_max_tokens_for_qwen(monkeypatch, no_checkpoint):
    from backend.services.studio import intelligence
    sent = []
    monkeypatch.setattr(intelligence.urllib.request, "urlopen", lambda req, timeout=None: sent.append(json.loads(req.data)) or _ok_response())
    intelligence.vision_call([{"type": "text", "text": "x"}], config=_vision_config("qwen3-vl-plus", "https://dashscope.aliyuncs.com/compatible-mode/v1"))
    assert sent[0]["max_tokens"] == 4000 and "max_completion_tokens" not in sent[0]
