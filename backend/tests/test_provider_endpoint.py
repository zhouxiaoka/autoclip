from backend.core.provider_endpoint import (
    hint_provider_for_key,
    is_console_host,
    locked_chat_url,
    looks_like_html,
    normalize_provider_base_url,
    telemetry_host,
)


def test_normalize_strips_spaces_slash_and_chat_completions_then_adds_v1():
    result = normalize_provider_base_url(' https://88api.ai/ ')
    assert result.url == 'https://88api.ai/v1'
    assert 'missing_v1' in result.warnings
    pasted = normalize_provider_base_url('https://example.com/v1/chat/completions')
    assert pasted.url == 'https://example.com/v1'
    assert 'chat_completions' in pasted.warnings
    already = normalize_provider_base_url('https://infistar.cc/v1')
    assert already.url == 'https://infistar.cc/v1'
    assert 'missing_v1' not in already.warnings


def test_console_host_is_not_treated_as_an_api_root():
    result = normalize_provider_base_url('https://platform.openai.com/api-keys')
    assert 'console_host' in result.warnings
    assert result.url == 'https://platform.openai.com/api-keys'
    assert is_console_host('bailian.console.aliyun.com')
    assert is_console_host('aistudio.google.com')
    assert not is_console_host('api.openai.com')
    assert not is_console_host('88api.ai')
    assert looks_like_html('<!DOCTYPE html><html><title>控制台</title>')
    assert not looks_like_html('{"data":[]}')


def test_locked_presets_ignore_wrong_custom_urls_except_legacy_openai_and_bailian():
    assert locked_chat_url('api88', 'https://api.openai.com/v1') == 'https://api.88api.ai/v1'
    assert locked_chat_url('api88', 'https://88api.ai/v1') is None
    assert locked_chat_url('api88', '') == 'https://api.88api.ai/v1'
    assert locked_chat_url('infistar', 'https://wrong.example/v1') == 'https://infistar.cc/v1'
    assert locked_chat_url('deepseek', '') == 'https://api.deepseek.com'
    assert locked_chat_url('gemini', 'https://platform.openai.com') == 'https://generativelanguage.googleapis.com/v1beta/openai'
    assert locked_chat_url('openai', '') == 'https://api.openai.com/v1'
    assert locked_chat_url('openai', 'https://one.example/v1') is None
    assert locked_chat_url('dashscope', '') == 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    assert locked_chat_url('dashscope', 'https://llm-x.cn-beijing.maas.aliyuncs.com') is None


def test_key_hint_is_prefix_only_and_host_is_sanitized():
    assert hint_provider_for_key('  AIzaSySecret  ') == 'gemini'
    assert hint_provider_for_key('sk-proj-abc') == 'openai'
    assert hint_provider_for_key('sk-or-v1-abc') == 'compatible'
    assert hint_provider_for_key('sk-generic-88api-or-deepseek') is None
    assert telemetry_host('https://88api.ai/v1/chat/completions?key=secret') == '88api.ai'
    assert telemetry_host('http://127.0.0.1:11434/v1') == 'local'
    assert 'secret' not in telemetry_host('https://user:secret@evil.example/v1')
