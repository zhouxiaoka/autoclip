"""RC156 Win QA #18: Qwen3.5–3.8 hybrid models on Bailian think by default.

One clip_finder call on qwen3.8-flash spent 43,055 completion tokens (578 s) for a 255-character
answer. Allowlisted hybrid models on DashScope endpoints get enable_thinking=false on every text and
vision path; thinking-only models, models off the list and non-DashScope endpoints are unchanged.
"""
import io
import json
import sys
import types
from types import SimpleNamespace

import pytest

from backend.core import llm_providers as lp

CN = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
INTL = 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1'
MAAS = 'https://llm-x.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'
HYBRID = ['qwen3.8-flash', 'qwen3.8-max', 'qwen3.7-plus', 'qwen3.6-flash', 'qwen3.5-plus', 'Qwen3.8-Flash ']
THINKING_ONLY = ['qwen3.8-2.4t-a95b', 'qwen3.7-max-preview', 'qwen3.7-max-2026-05-17', 'qwq-plus',
                 'qwen3-235b-a22b-thinking-2507', 'qwen3-vl-235b-a22b-thinking']
OFF_LIST = ['qwen-plus', 'qwen-flash', 'qwen3-max', 'qwen3-vl-flash', 'qwen3-32b', 'qwen3.8-omni-flash',
            'qwen3.9-flash', 'gpt-5-mini', 'deepseek-v4-flash', '']


@pytest.mark.parametrize('base', [CN, INTL, MAAS, 'https://dashscope-us.aliyuncs.com/compatible-mode/v1',
                                  'https://ws-1.ap-southeast-1.maas.aliyuncs.com/api/v1'])
def test_dashscope_endpoints_are_recognised(base):
    assert lp.is_dashscope_endpoint(base)


@pytest.mark.parametrize('base', ['', None, 'https://api.openai.com/v1', 'http://localhost:11434/v1',
                                  'https://proxy.example.com/v1', 'https://dashscope.aliyuncs.com.evil.example/v1',
                                  'https://oss-cn-beijing.aliyuncs.com', 'https://api.deepseek.com'])
def test_other_endpoints_are_not_dashscope(base):
    assert not lp.is_dashscope_endpoint(base)


@pytest.mark.parametrize('model', HYBRID)
@pytest.mark.parametrize('base', [CN, INTL, MAAS])
def test_allowlisted_hybrid_model_gets_enable_thinking_false(model, base):
    sent = lp.guarded_chat_kwargs(base, {'model': model, 'messages': []})
    assert sent['extra_body'] == {'enable_thinking': False}
    assert 'max_tokens' not in sent


@pytest.mark.parametrize('model', THINKING_ONLY + OFF_LIST)
def test_thinking_only_and_unlisted_models_are_unchanged(model):
    request = {'model': model, 'messages': []}
    assert lp.guarded_chat_kwargs(CN, request) is request


@pytest.mark.parametrize('base', ['', 'https://proxy.example.com/v1', 'http://localhost:11434/v1', 'https://api.openai.com/v1'])
def test_non_dashscope_endpoints_are_unchanged_even_for_listed_models(base):
    request = {'model': 'qwen3.8-flash', 'messages': []}
    assert lp.guarded_chat_kwargs(base, request) is request


def test_caller_choice_wins_and_other_extra_body_is_kept():
    sent = lp.guarded_chat_kwargs(CN, {'model': 'qwen3.8-flash', 'extra_body': {'enable_thinking': True, 'x': 1}})
    assert sent['extra_body'] == {'enable_thinking': True, 'x': 1}
    sent = lp.guarded_chat_kwargs(CN, {'model': 'qwen3.8-flash', 'extra_body': {'x': 1}})
    assert sent['extra_body'] == {'x': 1, 'enable_thinking': False}


def test_deepseek_guard_is_unchanged():
    sent = lp.guarded_chat_kwargs('https://api.deepseek.com', {'model': 'deepseek-flash'})
    assert sent['extra_body'] == {'thinking': {'type': 'disabled'}}
    assert sent['max_tokens'] == lp.DEEPSEEK_COMPLETION_TOKEN_CAP


def test_thinking_only_models_are_never_on_the_list():
    assert not set(THINKING_ONLY) & lp.QWEN_HYBRID_THINKING_MODELS
    assert not any('thinking' in name or name.startswith('qwq') for name in lp.QWEN_HYBRID_THINKING_MODELS)


# ------------------------------------------------------------------ provider request payloads

def _fake_openai(monkeypatch):
    calls, clients = [], []

    class Completions:
        def create(self, **kwargs):
            calls.append(kwargs)
            usage = SimpleNamespace(prompt_tokens=3, completion_tokens=4, total_tokens=7)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='ok'), finish_reason='stop')], usage=usage)

    class Client:
        def __init__(self, **kwargs):
            clients.append(kwargs)
            self.chat = SimpleNamespace(completions=Completions())

    module = types.ModuleType('openai')
    module.OpenAI = Client
    monkeypatch.setitem(sys.modules, 'openai', module)
    monkeypatch.delenv('OPENAI_BASE_URL', raising=False)
    return calls, clients


@pytest.mark.parametrize('model,expected', [('qwen3.8-flash', {'enable_thinking': False}),
                                            ('qwen3.8-2.4t-a95b', None), ('qwen-plus', None)])
def test_openai_provider_payload_on_bailian(monkeypatch, model, expected):
    calls, _ = _fake_openai(monkeypatch)
    lp.OpenAIProvider(api_key='sk-test', model_name=model, base_url=MAAS).call('挑片', {'rows': '1|00:00|x'})
    assert calls[0].get('extra_body') == expected
    assert calls[0]['model'] == model


def test_openai_provider_relay_payload_is_unchanged(monkeypatch):
    calls, _ = _fake_openai(monkeypatch)
    lp.OpenAIProvider(api_key='sk-test', model_name='qwen3.8-flash', base_url='https://proxy.example.com/v1').call('x')
    assert 'extra_body' not in calls[0]


def test_openai_client_has_explicit_timeout_and_one_sdk_retry(monkeypatch):
    import httpx
    _, clients = _fake_openai(monkeypatch)
    lp.OpenAIProvider(api_key='sk-test', model_name='qwen3.8-flash', base_url=CN)
    timeout = clients[0]['timeout']
    assert isinstance(timeout, httpx.Timeout) and timeout.read == lp.LLM_READ_TIMEOUT_SEC and timeout.connect == lp.LLM_CONNECT_TIMEOUT_SEC
    assert clients[0]['max_retries'] == lp.LLM_SDK_MAX_RETRIES == 1


@pytest.mark.parametrize('model,expected', [('qwen3.8-flash', False), ('qwq-plus', None), ('qwen-plus', None)])
def test_dashscope_compatible_payload_and_timeout(monkeypatch, model, expected):
    import requests
    sent = []

    def post(url, headers=None, json=None, timeout=None):
        sent.append((json, timeout))
        return SimpleNamespace(status_code=200, json=lambda: {'choices': [{'message': {'content': 'ok'}, 'finish_reason': 'stop'}]})

    monkeypatch.setattr(requests, 'post', post)
    lp.DashScopeProvider('sk-test', model, base_url=CN, mode='compatible').call('x')
    payload, timeout = sent[0]
    assert payload.get('enable_thinking') == expected
    assert timeout == (lp.LLM_CONNECT_TIMEOUT_SEC, lp.LLM_READ_TIMEOUT_SEC)


@pytest.mark.parametrize('model,expected', [('qwen3.8-flash', False), ('qwen3.8-2.4t-a95b', None), ('qwen-plus', None)])
def test_dashscope_native_sdk_kwargs(monkeypatch, model, expected):
    seen = []

    class Generation:
        @staticmethod
        def call(**kwargs):
            seen.append(kwargs)
            return SimpleNamespace(status_code=200, output=SimpleNamespace(text='ok', finish_reason='stop'), usage=None)

    module = types.ModuleType('dashscope')
    module.Generation = Generation
    monkeypatch.setitem(sys.modules, 'dashscope', module)
    monkeypatch.delenv('DASHSCOPE_BASE_URL', raising=False)
    monkeypatch.delenv('DASHSCOPE_MODE', raising=False)
    provider = lp.DashScopeProvider('sk-test', model)
    assert provider.mode == 'native'
    provider.call('x')
    assert seen[0].get('enable_thinking') == expected


# ------------------------------------------------------------------ vision

@pytest.mark.parametrize('model,base,expected', [
    ('qwen3.8-flash', CN, False),
    ('qwen3.8-flash', MAAS, False),
    ('qwen3.8-flash', 'https://proxy.example.com/v1', None),
    ('qwen3-vl-flash', CN, None),
    ('qwen3-vl-235b-a22b-thinking', CN, None),
    ('doubao-seed-2-1-pro-260915', 'https://ark.cn-beijing.volces.com/api/v3', None),
])
def test_vision_call_payload(monkeypatch, model, base, expected):
    from backend.services.studio import intelligence as vision
    bodies = []

    def send(req, **kwargs):
        bodies.append(json.loads(req.data))
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': '{"events": []}'}}]}).encode())

    monkeypatch.setattr(vision.urllib.request, 'urlopen', send)
    vision.vision_call([], config={'base_url': base, 'model': model, 'api_key': 'k', 'timeout': 10})
    assert bodies[0].get('enable_thinking') == expected


class _Session:
    def __init__(self, reply):
        self.sent, self.reply = [], reply

    def post(self, url, headers=None, json=None, timeout=None):
        self.sent.append((url, json))
        return SimpleNamespace(status_code=200, json=lambda: self.reply, text='')


@pytest.mark.parametrize('model,expected', [('qwen3.8-flash', {'enable_thinking': False}), ('qwen-vl-plus', None)])
def test_cover_ocr_native_dashscope_payload(model, expected):
    from backend.core import image_providers as ip
    session = _Session({'output': {'choices': [{'message': {'content': [{'text': '标题'}]}}]}})
    assert ip.read_image_text(provider='dashscope', api_key='k', base_url='', model=model, image=b'\xff\xd8\xff', session=session) == '标题'
    assert session.sent[0][1].get('parameters') == expected


@pytest.mark.parametrize('model,base,expected', [('qwen3.8-flash', CN, False), ('qwen3.8-flash', 'https://proxy.example.com/v1', None),
                                                 ('gpt-4o-mini', '', None)])
def test_cover_ocr_compatible_payload(model, base, expected):
    from backend.core import image_providers as ip
    session = _Session({'choices': [{'message': {'content': '标题'}}]})
    assert ip.read_image_text(provider='openai', api_key='k', base_url=base, model=model, image=b'\xff\xd8\xff', session=session) == '标题'
    assert session.sent[0][1].get('enable_thinking') == expected
