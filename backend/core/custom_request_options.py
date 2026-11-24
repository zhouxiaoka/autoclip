"""Validated optional settings for an OpenAI-compatible gateway.

Transport headers are secrets; framing/routing headers and application-owned
request fields cannot be overridden by provider options.
"""
from __future__ import annotations

import copy
import json
import re
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

HEADER_NAME = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]{1,100}$")
BLOCKED_HEADERS = frozenset({'host', 'content-length', 'transfer-encoding', 'connection',
                             'proxy-authorization', 'proxy-connection', 'trailer', 'te', 'upgrade'})
RESERVED_BODY_FIELDS = frozenset({'model', 'messages', 'stream', 'stream_options', 'max_tokens',
                                  'max_completion_tokens', 'max_output_tokens', 'response_format',
                                  'api_key', 'base_url', 'timeout', 'headers', 'http_headers',
                                  'extra_headers', 'extra_body', 'reasoning_effort'})
ReasoningEffort = Literal['none', 'minimal', 'low', 'medium', 'high', 'xhigh']


class CustomRequestOptions(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)
    # None means keep the previously saved secret; an empty map explicitly clears it.
    http_headers: dict[str, str] | None = Field(default=None, max_length=32, repr=False)
    reasoning_effort: ReasoningEffort | None = None
    extra_body: dict[str, JsonValue] = Field(default_factory=dict, max_length=64, repr=False)

    @field_validator('http_headers')
    @classmethod
    def valid_headers(cls, value):
        if value is None:
            return None
        seen = set()
        for name, text in value.items():
            lower = name.lower()
            if not HEADER_NAME.fullmatch(name) or lower in BLOCKED_HEADERS or lower in seen:
                raise ValueError('Invalid custom HTTP headers')
            if len(text) > 4096 or any(ord(c) < 32 or ord(c) > 126 for c in text):
                raise ValueError('Invalid custom HTTP header value')
            seen.add(lower)
        return value

    @field_validator('extra_body')
    @classmethod
    def valid_body(cls, value):
        if RESERVED_BODY_FIELDS.intersection(value):
            raise ValueError('Provider parameters cannot override application request fields')
        try:
            encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
        except (ValueError, TypeError, RecursionError):
            raise ValueError('Provider parameters must be a finite JSON object') from None
        if len(encoded) > 16384:
            raise ValueError('Provider parameters must be at most 16 KB')
        return value


def request_options(config) -> dict:
    """Omit defaults so legacy endpoints and callers retain their exact contract."""
    get = config.get if isinstance(config, Mapping) else lambda key: getattr(config, key, None)
    return {key: copy.deepcopy(get(key)) for key in ('http_headers', 'reasoning_effort', 'extra_body') if get(key)}


def merge_headers(defaults: Mapping[str, str], custom: Mapping[str, str] | None = None) -> dict[str, str]:
    headers = dict(defaults)
    for name, value in (custom or {}).items():
        headers = {key: text for key, text in headers.items() if key.lower() != name.lower()}
        headers[name] = value
    return headers


def apply_chat_options(payload: dict, config) -> dict:
    """Explicit call arguments win; the SDK flattens extra_body, raw HTTP must too."""
    options = request_options(config)
    body = dict(payload)
    if options.get('reasoning_effort'):
        body.setdefault('reasoning_effort', options['reasoning_effort'])
    if options.get('extra_body'):
        extra = {**options['extra_body'], **(body.get('extra_body') or {})}
        # The SDK merges extra_body LAST, unlike raw HTTP. Remove top-level collisions
        # here so explicit call fields win identically on both transports.
        body['extra_body'] = {key: value for key, value in extra.items() if key not in body}
    return body


def no_redirect_open(request, *, timeout):
    """urllib otherwise forwards custom secret headers on redirects."""
    import urllib.request
    from backend.core.llm_providers import is_local_url

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    proxy = urllib.request.ProxyHandler({}) if is_local_url(request.full_url) else urllib.request.ProxyHandler()
    return urllib.request.build_opener(proxy, NoRedirect()).open(request, timeout=timeout)
