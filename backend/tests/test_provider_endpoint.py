import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

from backend.core import provider_presets
from backend.core.provider_endpoint import (
    ADDRESS_LOCKED_PROVIDERS,
    LOCKED_PRESETS,
    hint_provider_for_key,
    is_console_host,
    locked_chat_url,
    locked_preset_url,
    looks_like_html,
    normalize_provider_base_url,
    official_chat_url,
    telemetry_host,
)
from backend.core.provider_presets import get_provider
from backend.services import ai_model_settings as ai

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'backend' / 'presets' / 'provider_presets.json'
ENDPOINT_SRC = ROOT / 'backend' / 'core' / 'provider_endpoint.py'


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('AUTOCLIP_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('AUTOCLIP_APP_DIR', str(tmp_path))
    monkeypatch.setattr(ai, 'migrate_legacy', lambda: ai.ModelSettings())
    yield
    provider_presets.reset_catalog_cache()


def test_normalize_strips_spaces_slash_and_chat_completions_then_adds_v1():
    result = normalize_provider_base_url(' https://gw.example/ ')
    assert result.url == 'https://gw.example/v1'
    assert 'missing_v1' in result.warnings
    pasted = normalize_provider_base_url('https://example.com/v1/chat/completions')
    assert pasted.url == 'https://example.com/v1'
    assert 'chat_completions' in pasted.warnings
    already = normalize_provider_base_url('https://gw.example/v1')
    assert already.url == 'https://gw.example/v1'
    assert 'missing_v1' not in already.warnings


def test_normalize_reuses_provider_url_and_never_raises():
    assert normalize_provider_base_url('').url == ''
    assert normalize_provider_base_url('   ').url == ''
    assert normalize_provider_base_url('not-an-endpoint').url == 'not-an-endpoint'
    assert normalize_provider_base_url('ftp://gw.example/v1').url == 'ftp://gw.example/v1'
    assert normalize_provider_base_url('HTTP://gw.example/v1').url == 'http://gw.example/v1'
    assert normalize_provider_base_url('localhost:11434', 'ollama').url == 'http://localhost:11434/v1'
    host = 'https://llm-x.cn-beijing.maas.aliyuncs.com'
    assert normalize_provider_base_url(host, 'dashscope').url == host
    text = ENDPOINT_SRC.read_text(encoding='utf-8')
    assert 'rewrite_provider_base_url' in text
    assert '_VERSIONED_PATH' not in text
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    for key in ADDRESS_LOCKED_PROVIDERS:
        url = (catalog['providers'].get(key) or {}).get('base_url') or ''
        if url:
            assert url not in text, f'hard-coded catalog URL {url}'


def test_console_host_is_not_treated_as_an_api_root():
    result = normalize_provider_base_url('https://platform.openai.com/api-keys')
    assert 'console_host' in result.warnings
    assert result.url == 'https://platform.openai.com/api-keys'
    assert is_console_host('bailian.console.aliyun.com')
    assert is_console_host('aistudio.google.com')
    assert not is_console_host('api.openai.com')
    assert not is_console_host('infistar.ai')
    assert 'console_host' not in normalize_provider_base_url('https://infistar.ai/v1', 'infistar').warnings
    assert not is_console_host('example.com')
    assert looks_like_html('<!DOCTYPE html><html><title>控制台</title>')
    assert not looks_like_html('{"data":[]}')


def test_normalize_warns_but_connection_rejects_console_host():
    url = 'https://platform.openai.com/api-keys'
    assert normalize_provider_base_url(url).url == url
    with pytest.raises(ValueError, match='这是控制台或官网地址，不是模型接口'):
        ai.Connection(
            id='c', name='c', provider='compatible', base_url=url, api_key='k',
        )
    connection = ai.Connection(
        id='c', name='c', provider='compatible',
        base_url='https://infistar.ai/v1', api_key='k',
    )
    assert connection.base_url == 'https://infistar.ai/v1'
    assert normalize_provider_base_url('not-an-endpoint').url == 'not-an-endpoint'


def test_locked_presets_read_catalog_urls_except_legacy_openai_and_bailian():
    api88 = get_provider('api88').base_url
    infistar = get_provider('infistar').base_url
    deepseek = get_provider('deepseek').base_url
    dashscope = get_provider('dashscope').base_url
    openai = get_provider('openai').base_url
    assert locked_chat_url('api88', 'https://wrong.example/v1') == api88
    assert locked_chat_url('api88', 'https://88api.ai/v1') == 'https://88api.ai/v1'
    assert locked_chat_url('infistar', 'https://wrong.example/v1') == infistar
    assert locked_chat_url('deepseek', '') == deepseek
    assert locked_chat_url('gemini', 'https://platform.openai.com') == official_chat_url('gemini')
    assert official_chat_url('gemini').endswith('/openai')
    assert locked_chat_url('openai', '') == openai
    assert locked_chat_url('openai', 'https://one.example/v1') is None
    assert locked_chat_url('dashscope', '') == dashscope
    assert locked_chat_url('dashscope', 'https://llm-x.cn-beijing.maas.aliyuncs.com') is None
    assert set(LOCKED_PRESETS) == set(ADDRESS_LOCKED_PROVIDERS)
    assert LOCKED_PRESETS['api88'] == api88
    assert locked_preset_url('siliconflow') == get_provider('siliconflow').base_url
    assert locked_preset_url('ollama') is None


@pytest.mark.parametrize('host', ['infistar.ai', 'infistar.cc', 'www.infistar.ai', 'www.infistar.cc'])
def test_infistar_preserves_accepted_gateway_through_save_and_chat(host):
    url = f'https://{host}/v1'
    assert host in get_provider('infistar').accepted_hosts
    assert locked_chat_url('infistar', url) == url
    connection = ai.Connection(id='gateway', name='fixture', provider='infistar', base_url=url, api_key='fixture')
    document = ai.ModelSettings(connections=[connection], analysis=ai.Assignment(connection_id='gateway', model='fixture-model'))
    ai.save(document)
    saved = ai.load().connections[0]
    assert saved.base_url == url
    assert ai.chat_endpoint(saved, 'fixture-model')['base_url'] == url
    assert locked_chat_url('infistar', '') == 'https://infistar.cc/v1'
    assert locked_chat_url('infistar', 'https://infistar.ai.attacker.test/v1') == 'https://infistar.cc/v1'


def test_locked_urls_follow_swapped_json_catalog(tmp_path, monkeypatch):
    raw = json.loads(CATALOG.read_text(encoding='utf-8'))
    raw['providers']['api88']['base_url'] = 'https://lock.example.test/v1'
    raw['providers']['siliconflow']['locked'] = False
    raw['providers']['ollama']['locked'] = True
    path = tmp_path / 'provider_presets.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    monkeypatch.setenv('AUTOCLIP_PROVIDER_PRESETS', str(path))
    provider_presets.reset_catalog_cache()
    assert locked_chat_url('api88', 'https://wrong.example/v1') == 'https://lock.example.test/v1'
    assert LOCKED_PRESETS['api88'] == 'https://lock.example.test/v1'
    assert 'siliconflow' not in ADDRESS_LOCKED_PROVIDERS
    assert locked_preset_url('siliconflow') is None
    assert 'ollama' in ADDRESS_LOCKED_PROVIDERS
    assert LOCKED_PRESETS['ollama'] == get_provider('ollama').base_url


def test_console_detection_allows_live_catalog_api_hosts(tmp_path, monkeypatch):
    raw = json.loads(CATALOG.read_text(encoding='utf-8'))
    raw['providers']['api88']['base_url'] = 'https://platform.deepseek.com/v1'
    raw['providers']['api88']['accepted_hosts'] = ['aistudio.google.com']
    raw['address_rules']['console_hosts'].append('control.fixture.test')
    raw['address_rules']['console_suffixes'].append('.console.fixture.test')
    path = tmp_path / 'provider_presets.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    monkeypatch.setenv('AUTOCLIP_PROVIDER_PRESETS', str(path))
    provider_presets.reset_catalog_cache()
    assert not is_console_host('platform.deepseek.com')
    assert not is_console_host('aistudio.google.com')
    assert 'console_host' not in normalize_provider_base_url('https://platform.deepseek.com/v1').warnings
    connection = ai.Connection(
        id='catalog', name='catalog', provider='compatible',
        base_url='https://platform.deepseek.com/v1', api_key='k',
    )
    assert connection.base_url == 'https://platform.deepseek.com/v1'
    assert is_console_host('platform.openai.com')
    assert is_console_host('control.fixture.test')
    assert is_console_host('account.console.fixture.test')
    provider_presets.reset_catalog_cache()
    monkeypatch.delenv('AUTOCLIP_PROVIDER_PRESETS')
    assert is_console_host('platform.deepseek.com')
    assert is_console_host('aistudio.google.com')
    assert not is_console_host('control.fixture.test')
    assert not is_console_host('account.console.fixture.test')


def test_gemini_catalog_native_path_uses_shared_helper(tmp_path, monkeypatch):
    raw = json.loads(CATALOG.read_text(encoding='utf-8'))
    raw['providers']['gemini']['base_url'] = 'https://gemini.example.test/v1beta'
    path = tmp_path / 'provider_presets.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    monkeypatch.setenv('AUTOCLIP_PROVIDER_PRESETS', str(path))
    provider_presets.reset_catalog_cache()
    assert official_chat_url('gemini') == 'https://gemini.example.test/v1beta/openai'


@pytest.mark.parametrize('provider', ['api88', 'infistar', 'deepseek', 'gemini'])
def test_catalog_change_preserves_frozen_connection_but_updates_new_one(tmp_path, monkeypatch, provider):
    ai.save(ai.ModelSettings(
        connections=[ai.Connection(id='saved', name='saved', provider=provider)],
        analysis=ai.Assignment(connection_id='saved', model='fixture-model'),
    ))
    original = ai.load().connections[0]
    frozen_url = ai.chat_endpoint(original, 'fixture-model')['base_url']
    assert original.base_url == frozen_url
    assert original.preset_version > 0
    raw = json.loads(CATALOG.read_text(encoding='utf-8'))
    raw['version'] += 1
    # A catalog migration must explicitly continue accepting the frozen host;
    # preset_version alone cannot authorize an arbitrary saved address.
    raw['providers'][provider].setdefault('accepted_hosts', []).append(urlparse(frozen_url).hostname)
    raw['providers'][provider]['base_url'] = 'https://changed.example.test/v1beta' if provider == 'gemini' else 'https://changed.example.test/v1'
    path = tmp_path / 'provider_presets.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    monkeypatch.setenv('AUTOCLIP_PROVIDER_PRESETS', str(path))
    provider_presets.reset_catalog_cache()
    restored = ai.load().connections[0]
    assert ai.chat_endpoint(restored, 'fixture-model')['base_url'] == frozen_url
    fresh = ai.Connection(id='fresh', name='fresh', provider=provider)
    expected = 'https://changed.example.test/v1beta/openai' if provider == 'gemini' else 'https://changed.example.test/v1'
    assert ai.chat_endpoint(fresh, 'fixture-model')['base_url'] == expected


@pytest.mark.parametrize('provider', ['api88', 'infistar', 'deepseek', 'gemini'])
def test_stamped_urls_use_live_catalog_hosts_and_shared_chat_path(tmp_path, monkeypatch, provider):
    raw = json.loads(CATALOG.read_text(encoding='utf-8'))
    raw['providers'][provider]['base_url'] = 'https://current.example.test/v1'
    raw['providers'][provider]['accepted_hosts'] = ['legacy.example.test']
    path = tmp_path / 'provider_presets.json'
    path.write_text(json.dumps(raw), encoding='utf-8')
    monkeypatch.setenv('AUTOCLIP_PROVIDER_PRESETS', str(path))
    provider_presets.reset_catalog_cache()
    saved = 'http://legacy.example.test:8443/v1beta' if provider == 'gemini' else 'http://legacy.example.test:8443/v1'
    connection = ai.Connection(
        id='saved', name='saved', provider=provider, base_url=saved,
        base_url_source='preset', preset_version=99,
    )
    expected = saved + '/openai' if provider == 'gemini' else saved
    assert ai.chat_endpoint(connection, 'fixture-model')['base_url'] == expected
    wrong = ai.Connection(
        id='wrong', name='wrong', provider=provider, base_url='https://wrong.example.test/v1',
        base_url_source='preset', preset_version=99,
    )
    assert ai.chat_endpoint(wrong, 'fixture-model')['base_url'] == official_chat_url(provider)


def test_key_hint_is_prefix_only_and_host_is_sanitized():
    assert hint_provider_for_key('  AIzaSySecret  ') == 'gemini'
    assert hint_provider_for_key('sk-proj-abc') == 'openai'
    assert hint_provider_for_key('sk-or-v1-abc') == 'compatible'
    assert hint_provider_for_key('sk-generic-88api-or-deepseek') is None
    assert telemetry_host('https://example.com/v1/chat/completions?key=secret') == 'example.com'
    assert telemetry_host('http://127.0.0.1:11434/v1') == 'local'
    assert 'secret' not in telemetry_host('https://user:secret@evil.example/v1')


def test_catalog_api_hosts_are_not_console_hosts_and_locks_match_catalog():
    from urllib.parse import urlparse
    from backend.core.provider_presets import get_catalog
    from backend.core.provider_endpoint import ADDRESS_LOCKED_PROVIDERS, LOCKED_PRESETS
    from backend.services.ai_model_settings import Connection
    catalog = get_catalog()
    assert not is_console_host('infistar.ai')
    assert Connection(id='inf', name='Infistar', provider='compatible', base_url='https://infistar.ai/v1').base_url == 'https://infistar.ai/v1'
    assert ADDRESS_LOCKED_PROVIDERS == {p.id for p in catalog.providers.values() if p.locked and p.base_url}
    for preset in catalog.providers.values():
        if preset.base_url:
            assert not is_console_host(urlparse(preset.base_url).hostname)
        if preset.id in LOCKED_PRESETS:
            expected = preset.base_url + ('/openai' if preset.protocol == 'google-generative-ai' else '')
            assert LOCKED_PRESETS[preset.id] == expected
