"""S1: provider base URL normalization. Cleanup only; never rejects."""
import pytest

from backend.core.provider_url import cleanup_base_url, normalize_provider_base_url
from backend.services import ai_model_settings as ai


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())


@pytest.mark.parametrize('raw,expected', [
    ('', ''),
    ('   ', ''),
    ('https://gw.example/v1/', 'https://gw.example/v1'),
    ('  https://gw.example /v1  \n', 'https://gw.example/v1'),
    ('HTTP://gw.example/v1', 'http://gw.example/v1'),
    ('gw.example/v1', 'https://gw.example/v1'),
    ('//gw.example/v1', 'https://gw.example/v1'),
    ('localhost:11434/v1', 'http://localhost:11434/v1'),
    ('127.0.0.1:11434/v1', 'http://127.0.0.1:11434/v1'),
    ('192.168.1.8:11434', 'http://192.168.1.8:11434'),
    ('not-an-endpoint', 'not-an-endpoint'),
])
def test_cleanup_collapses_spaces_slashes_and_scheme(raw, expected):
    assert cleanup_base_url(raw) == expected


@pytest.mark.parametrize('raw,provider,expected', [
    ('https://gw.example', 'compatible', 'https://gw.example/v1'),
    ('https://gw.example/', 'compatible', 'https://gw.example/v1'),
    ('https://gw.example/v1', 'compatible', 'https://gw.example/v1'),
    ('https://gw.example/v1/', 'compatible', 'https://gw.example/v1'),
    ('https://gw.example/v1/v1', 'compatible', 'https://gw.example/v1'),
    ('https://openrouter.ai/api/v1', 'compatible', 'https://openrouter.ai/api/v1'),
    ('https://api.deepseek.com', 'deepseek', 'https://api.deepseek.com/v1'),
    ('http://localhost:11434', 'ollama', 'http://localhost:11434/v1'),
    ('https://generativelanguage.googleapis.com', 'gemini', 'https://generativelanguage.googleapis.com/v1beta/openai'),
    ('https://generativelanguage.googleapis.com/v1beta/openai', 'gemini', 'https://generativelanguage.googleapis.com/v1beta/openai'),
    ('https://llm-x.cn-beijing.maas.aliyuncs.com', 'dashscope', 'https://llm-x.cn-beijing.maas.aliyuncs.com'),
    ('https://llm-x.cn-beijing.maas.aliyuncs.com/api/v1/', 'dashscope', 'https://llm-x.cn-beijing.maas.aliyuncs.com/api/v1'),
    ('https://dashscope.aliyuncs.com/compatible-mode/v1/', 'dashscope', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
    ('https://fal.run', 'compatible', 'https://fal.run'),
    ('https://fal.run/', 'compatible', 'https://fal.run'),
    ('https://ark.cn-beijing.volces.com/api/v3', 'seed', 'https://ark.cn-beijing.volces.com/api/v3'),
    ('https://open.bigmodel.cn/api/paas/v4', 'glm', 'https://open.bigmodel.cn/api/paas/v4'),
    ('https://88api.ai/v1', 'api88', 'https://88api.ai/v1'),
    ('https://api.88api.ai/v1', 'api88', 'https://api.88api.ai/v1'),
    ('', 'compatible', ''),
])
def test_normalize_adds_or_dedupes_v1_per_provider(raw, provider, expected):
    assert normalize_provider_base_url(raw, provider) == expected


def test_normalize_never_raises_on_odd_input():
    assert normalize_provider_base_url('not-an-endpoint', 'compatible') == 'not-an-endpoint'
    assert normalize_provider_base_url('ftp://gw.example/v1', 'compatible') == 'ftp://gw.example/v1'


def test_connection_normalizes_compatible_url_on_construct():
    connection = ai.Connection(
        id='c', name='c', provider='compatible',
        base_url='  HTTPS://gw.example /v1/v1/  \n', api_key='k',
    )
    assert connection.base_url == 'https://gw.example/v1'


def test_connection_adds_https_and_v1_when_scheme_is_missing():
    connection = ai.Connection(id='c', name='c', provider='compatible', base_url='gw.example', api_key='k')
    assert connection.base_url == 'https://gw.example/v1'


def test_connection_does_not_add_v1_to_dedicated_bailian_host():
    host = 'https://llm-x.cn-beijing.maas.aliyuncs.com'
    connection = ai.Connection(id='b', name='百炼', provider='dashscope', base_url=host)
    assert connection.base_url == host
    assert ai.chat_endpoint(connection, 'qwen-plus')['base_url'] == host + '/compatible-mode/v1'


def test_connection_leaves_fal_run_without_v1():
    fal = ai.Connection(id='f', name='fal', provider='compatible', base_url='https://fal.run', api_key='k', image_api='fal')
    assert fal.base_url == 'https://fal.run'
    assert ai.image_endpoint(fal)['base_url'] == 'https://fal.run'


def test_connection_still_refuses_secrets_in_the_url():
    with pytest.raises(Exception, match='接口地址'):
        ai.Connection(id='c', name='c', provider='compatible', base_url='https://gw.example/v1?api_key=secret', api_key='k')


def test_http_put_normalizes_compatible_base_url():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.api.v1.settings import router
    app = FastAPI()
    app.include_router(router)
    payload = ai.ModelSettings(
        connections=[ai.Connection(id='one', name='gw', provider='compatible', base_url='https://one.example/v1', api_key='sk-first-secret')],
        analysis=ai.Assignment(connection_id='one', model='gpt-4o-mini'),
    ).model_dump()
    payload['connections'][0]['base_url'] = '  https://gw.example /v1/  '
    with TestClient(app) as client:
        response = client.put('/settings/ai-models', json=payload)
    assert response.status_code == 200
    assert ai.load().connections[0].base_url == 'https://gw.example/v1'
