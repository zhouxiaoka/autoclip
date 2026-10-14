"""Address normalization, locked presets, console-host detection, and key hints.

Settings line B (roadmap #S). Locked providers keep their official URL;
only `compatible` (and local presets) may edit the address.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from backend.core.cloud_presets import CLOUD_PRESETS
from backend.core.llm_providers import (
    DASHSCOPE_CN_COMPATIBLE_BASE_URL,
    OPENAI_OFFICIAL_BASE_URL,
    normalize_base_url,
)

LOCKED_PRESETS: dict[str, str] = {
    'api88': CLOUD_PRESETS['api88'].base_url,
    'infistar': CLOUD_PRESETS['infistar'].base_url,
    'deepseek': CLOUD_PRESETS['deepseek'].base_url,
    'gemini': 'https://generativelanguage.googleapis.com/v1beta/openai',
    'dashscope': DASHSCOPE_CN_COMPATIBLE_BASE_URL,
    'openai': OPENAI_OFFICIAL_BASE_URL,
}

# Beginners pick one of these and only paste a key. Custom gateways use `compatible`.
ADDRESS_LOCKED_PROVIDERS = frozenset(LOCKED_PRESETS)

CONSOLE_HOSTS = frozenset({
    'platform.openai.com', 'chatgpt.com', 'openai.com', 'www.openai.com',
    'platform.deepseek.com', 'chat.deepseek.com', 'www.deepseek.com', 'deepseek.com',
    'aistudio.google.com', 'ai.google.dev', 'makersuite.google.com',
    'console.cloud.google.com',
    'bailian.console.aliyun.com', 'dashscope.console.aliyun.com',
    'www.aliyun.com', 'aliyun.com',
    'console.volcengine.com', 'www.volcengine.com',
    'platform.moonshot.cn', 'www.moonshot.cn',
    'console.x.ai',
    'www.infistar.cc', 'www.infistar.ai', 'infistar.ai',
    'www.88api.ai',
})

_CONSOLE_SUFFIXES = ('.console.aliyun.com', '.console.volcengine.com')

_VERSIONED_PATH = re.compile(
    r'^/(?:v\d+(?:beta)?(?:/openai)?|compatible-mode/v\d+|api/v\d+|api/paas/v\d+|openai/v\d+)/?$',
    re.I,
)

_CHAT_SUFFIXES = (
    '/v1/chat/completions',
    '/chat/completions',
    '/v1/completions',
    '/completions',
)

_KEY_HINTS = (
    (re.compile(r'^AIza'), 'gemini'),
    (re.compile(r'^xai-'), 'grok'),
    (re.compile(r'^sk-proj-'), 'openai'),
    (re.compile(r'^sk-svcacct-'), 'openai'),
    (re.compile(r'^sk-or-'), 'compatible'),
    (re.compile(r'^sk-ant-'), 'compatible'),
)

@dataclass(frozen=True)
class NormalizeResult:
    url: str
    warnings: tuple[str, ...]


def is_console_host(host: Optional[str]) -> bool:
    value = (host or '').lower().strip('.')
    if not value:
        return False
    if value in CONSOLE_HOSTS:
        return True
    return any(value.endswith(suffix) for suffix in _CONSOLE_SUFFIXES)


def looks_like_html(text: Optional[str]) -> bool:
    head = (text or '').lstrip()[:200].lower()
    return head.startswith('<!doctype html') or head.startswith('<html') or head.startswith('<head')


def hint_provider_for_key(api_key: Optional[str]) -> Optional[str]:
    """High-confidence prefix only. Never auto-switch the selected provider (MS-18)."""
    key = (api_key or '').strip()
    for pattern, provider in _KEY_HINTS:
        if pattern.match(key):
            return provider
    return None


def telemetry_host(url: Optional[str]) -> str:
    """Hostname only. Loopback / private → `local`. Never the full URL."""
    from backend.core.llm_telemetry import hostname_of_base_url
    return hostname_of_base_url(url) or 'unknown'


def normalize_provider_base_url(url: Optional[str]) -> NormalizeResult:
    """Strip spaces / trailing slash, drop `/chat/completions`, add `/v1` when missing."""
    raw = re.sub(r'\s+', '', (url or '').strip()).rstrip('/')
    warnings: list[str] = []
    parsed = urlparse(raw)
    if parsed.hostname and is_console_host(parsed.hostname):
        warnings.append('console_host')
        return NormalizeResult(url=raw, warnings=tuple(warnings))
    lowered = raw.lower()
    for suffix in _CHAT_SUFFIXES:
        if lowered.endswith(suffix):
            raw = raw[: len(raw) - len(suffix)].rstrip('/')
            warnings.append('chat_completions')
            parsed = urlparse(raw)
            break
    path = parsed.path or ''
    if parsed.scheme in ('http', 'https') and parsed.hostname and not _VERSIONED_PATH.match(path):
        raw = raw.rstrip('/') + '/v1'
        warnings.append('missing_v1')
    return NormalizeResult(url=raw, warnings=tuple(warnings))


def locked_chat_url(provider: Optional[str], base_url: Optional[str] = None) -> Optional[str]:
    """Forced official URL, or None to keep the existing chat_endpoint resolution.

    OpenAI with a foreign stored URL stays as-is (legacy rows the UI already
    shows as 自定义兼容). DashScope with a dedicated Aliyun host keeps the
    existing compatible-mode rewrite.
    """
    if provider == 'api88':
        cleaned = normalize_base_url(base_url)
        if cleaned:
            from backend.core.cloud_presets import is_api88_host
            if is_api88_host(urlparse(cleaned).hostname):
                return None
        return LOCKED_PRESETS['api88']
    if provider in {'infistar', 'deepseek', 'gemini'}:
        return LOCKED_PRESETS[provider]
    if provider == 'openai':
        cleaned = normalize_base_url(base_url)
        if not cleaned or cleaned in {OPENAI_OFFICIAL_BASE_URL, 'https://api.openai.com'}:
            return OPENAI_OFFICIAL_BASE_URL
        return None
    if provider == 'dashscope':
        if not normalize_base_url(base_url):
            return LOCKED_PRESETS['dashscope']
        return None
    return None
