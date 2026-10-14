"""Normalize a provider base URL. Cleanup only — never rejects or raises.

Idempotent: running the same URL through again returns the same result.

Rules (applied in order):

1. Collapse every whitespace (including interior spaces and newlines).
2. Strip trailing slashes.
3. Scheme: lowercase ``http`` / ``https``; a host-like value without a scheme
   gets ``http://`` when the host is loopback / private / ``*.local``, otherwise
   ``https://``. Protocol-relative ``//host`` is treated the same way.
4. ``/v1`` add or dedupe, per provider convention (see
   ``normalize_provider_base_url``). Empty input stays empty.

This module does not flag console hosts, strip ``/chat/completions``, or
block save. Existing Connection validation still refuses credentials, query
strings, and fragments in the URL.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse, urlunparse

from backend.core.llm_providers import is_local_url

# OpenAI-compatible chat roots use /v1 when the path is empty.
_OPENAI_V1_PROVIDERS = frozenset({
    'compatible', 'openai', 'api88', 'infistar', 'deepseek',
    'siliconflow', 'ollama', 'lmstudio', 'grok', 'kimi',
})

# Already a versioned API root — do not append another /v1.
_VERSIONED_PATH = re.compile(
    r'^/(?:v\d+(?:beta)?(?:/openai)?|compatible-mode/v\d+|api/v\d+|api/paas/v\d+|openai/v\d+)/?$',
    re.I,
)

_SCHEME = re.compile(r'^([a-zA-Z][a-zA-Z+\-.]*)://')
_IPV4 = re.compile(r'^(\d+)\.(\d+)\.(\d+)\.(\d+)$')
_LOCAL_NAMES = frozenset({'localhost', '0.0.0.0', 'host.docker.internal', '::1'})


def collapse_spaces(url: Optional[str]) -> str:
    """Remove every whitespace character. Does not strip slashes or add a scheme."""
    return re.sub(r'\s+', '', url or '')


def cleanup_base_url(url: Optional[str]) -> str:
    """Whitespace, trailing slashes, and scheme. No /v1 rewrite."""
    raw = collapse_spaces(url).rstrip('/')
    if not raw:
        return ''
    match = _SCHEME.match(raw)
    if match:
        scheme = match.group(1).lower()
        if scheme != match.group(1):
            raw = scheme + raw[len(match.group(1)):]
        return raw
    if raw.startswith('//'):
        host = _hostname(urlparse('http:' + raw))
        return ('http:' if _is_local_host(host) else 'https:') + raw
    if _looks_like_host_url(raw):
        host = _host_of_schemeless(raw)
        scheme = 'http' if _is_local_host(host) else 'https'
        return f'{scheme}://{raw}'
    return raw


def normalize_provider_base_url(url: Optional[str], provider: Optional[str] = 'compatible') -> str:
    """Cleanup plus provider ``/v1`` convention. Never raises."""
    cleaned = cleanup_base_url(url)
    if not cleaned:
        return ''
    parsed = urlparse(cleaned)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        return cleaned
    path = _dedupe_repeated_v1((parsed.path or '').rstrip('/'))
    host = (parsed.hostname or '').lower()
    key = (provider or '').strip().lower()
    path = _apply_convention(key, host, path)
    return urlunparse((parsed.scheme, parsed.netloc, path, '', '', ''))


def _apply_convention(provider: str, host: str, path: str) -> str:
    if host == 'fal.run' or host.endswith('.fal.run'):
        return path
    if _VERSIONED_PATH.match(path or '/'):
        return path
    if path and path != '/':
        return path
    if provider == 'dashscope' or provider == 'image':
        return path
    if provider == 'gemini' and host == 'generativelanguage.googleapis.com':
        return '/v1beta/openai'
    if provider in _OPENAI_V1_PROVIDERS or provider == 'gemini':
        return '/v1'
    return path


def _dedupe_repeated_v1(path: str) -> str:
    """``/v1/v1`` or ``/v1/v1/v1`` → ``/v1``. Mixed versions are left alone."""
    parts = [part for part in path.split('/') if part]
    if len(parts) >= 2 and all(re.fullmatch(r'v\d+', part, re.I) for part in parts):
        if len({part.lower() for part in parts}) == 1:
            return '/' + parts[0]
    return path


def _hostname(parsed) -> str:
    return (parsed.hostname or '').lower()


def _is_local_host(host: str) -> bool:
    if not host:
        return False
    wrapped = f'[{host}]' if ':' in host and not host.startswith('[') else host
    return is_local_url(f'http://{wrapped}')


def _host_of_schemeless(raw: str) -> str:
    if raw.startswith('['):
        end = raw.find(']')
        return raw[1:end] if end != -1 else ''
    first = raw.split('/', 1)[0]
    if first.count(':') == 1 and first.rsplit(':', 1)[-1].isdigit():
        return first.rsplit(':', 1)[0]
    return first


def _looks_like_host_url(raw: str) -> bool:
    host = _host_of_schemeless(raw)
    if not host:
        return False
    lowered = host.lower()
    if lowered in _LOCAL_NAMES or lowered.endswith('.local') or lowered.endswith('.localhost'):
        return True
    if _IPV4.match(lowered) or '.' in host or ':' in host:
        return True
    return False
