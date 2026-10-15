"""Address lock, console-host detection, and key hints.

Settings line B (roadmap #S). Official URLs come from
``backend/presets/provider_presets.json``. URL rewrite goes through ``provider_url``
(cleanup only — never rejects or raises).
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Optional
from urllib.parse import urlparse

from backend.core.llm_providers import normalize_base_url
from backend.core.provider_presets import get_catalog, get_provider, iter_providers
from backend.core.provider_url import NormalizeResult, cleanup_base_url, normalize_provider_url
from backend.core.provider_url import normalize_provider_base_url as rewrite_provider_base_url

_KEY_HINTS = (
    (re.compile(r'^AIza'), 'gemini'),
    (re.compile(r'^xai-'), 'grok'),
    (re.compile(r'^sk-proj-'), 'openai'),
    (re.compile(r'^sk-svcacct-'), 'openai'),
    (re.compile(r'^sk-or-'), 'compatible'),
    (re.compile(r'^sk-ant-'), 'compatible'),
)


def official_chat_url(provider: Optional[str]) -> Optional[str]:
    """Catalog base URL, with Gemini's native root mapped to the chat path.

    Gemini's JSON row stores the generative-language root; the OpenAI-compatible
    client needs the ``/v1beta/openai`` convention from ``provider_url``.
    """
    preset = get_provider(provider)
    if not preset or not preset.base_url:
        return None
    cleaned = cleanup_base_url(preset.base_url)
    if (preset.protocol or '') != 'google-generative-ai':
        return cleaned
    return rewrite_provider_base_url(cleaned, preset.id) or cleaned


def locked_preset_url(provider: Optional[str]) -> Optional[str]:
    preset = get_provider(provider)
    if not preset or not preset.locked:
        return None
    return official_chat_url(provider)


def locked_presets() -> dict[str, str]:
    """Live map so tests can swap ``AUTOCLIP_PROVIDER_PRESETS``."""
    return {
        preset.id: url
        for preset in iter_providers()
        if preset.locked and (url := official_chat_url(preset.id))
    }


class _LockedPresetMap(Mapping[str, str]):
    """Live view of address-locked official URLs. Reads the catalog on each lookup."""

    def __getitem__(self, key: str) -> str:
        url = locked_preset_url(key)
        if url is None:
            raise KeyError(key)
        return url

    def __iter__(self):
        return iter(locked_presets())

    def __len__(self) -> int:
        return len(locked_presets())


LOCKED_PRESETS = _LockedPresetMap()
# A live keys view keeps the existing set API in sync with catalog lock flags.
ADDRESS_LOCKED_PROVIDERS = LOCKED_PRESETS.keys()


def is_console_host(host: Optional[str]) -> bool:
    value = (host or '').lower().strip('.')
    if not value:
        return False
    # The same live catalog drives routing and validation. A documented API host
    # (including an accepted legacy host) takes precedence over console hints.
    if any(value in _accepted_hosts(preset.id, preset.base_url) for preset in iter_providers()):
        return False
    catalog = get_catalog()
    if value in catalog.console_hosts:
        return True
    return any(value.endswith(suffix) for suffix in catalog.console_suffixes)


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


def normalize_provider_base_url(
    url: Optional[str],
    provider: Optional[str] = 'compatible',
) -> NormalizeResult:
    """Cleanup via ``provider_url``. Never rejects or raises.

    Warnings (``console_host``, ``chat_completions``, ``missing_v1``) are
    informational. Callers may still persist the returned URL.
    """
    cleaned = cleanup_base_url(url)
    parsed = urlparse(cleaned)
    if parsed.hostname and is_console_host(parsed.hostname):
        return NormalizeResult(url=cleaned, warnings=('console_host',))
    return normalize_provider_url(cleaned, provider)


def _hostname(url: Optional[str]) -> str:
    return (urlparse(url or '').hostname or '').lower()


def _accepted_hosts(provider: Optional[str], official: Optional[str]) -> set[str]:
    preset = get_provider(provider)
    hosts = {host.lower() for host in (preset.accepted_hosts if preset else ())}
    official_host = _hostname(official)
    if official_host:
        hosts.add(official_host)
    return hosts


def locked_chat_url(provider: Optional[str], base_url: Optional[str] = None) -> Optional[str]:
    """Forced official URL, or None to keep the existing chat_endpoint resolution.

    A stored URL whose host is in the catalog ``accepted_hosts`` (or the
    official host) is kept — 88API's previous host still works. OpenAI with a
    foreign stored URL stays as-is (legacy rows the UI already shows as
    自定义兼容). DashScope with a dedicated Aliyun host keeps the existing
    compatible-mode rewrite.
    """
    official = locked_preset_url(provider)
    if provider in {'api88', 'infistar', 'deepseek', 'gemini'}:
        cleaned = normalize_base_url(base_url)
        if cleaned:
            host = _hostname(cleaned)
            if host and host in _accepted_hosts(provider, official):
                return rewrite_provider_base_url(cleaned, provider) or cleaned
        return official
    if provider == 'openai':
        cleaned = normalize_base_url(base_url)
        aliases = {official} if official else set()
        if official:
            aliases.add(official.removesuffix('/v1'))
        if not cleaned or cleaned in aliases:
            return official
        return None
    if provider == 'dashscope':
        if not normalize_base_url(base_url):
            return official
        return None
    return None
