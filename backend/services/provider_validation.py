"""Settings-page provider access check: GET /models then a tiny real chat call.

Save may persist a failed result (marked red). Generation reads the stored
status and blocks. Never returns keys, full URLs, or provider error text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from backend.core.llm_providers import is_local_url, uses_max_completion_tokens
from backend.core.provider_endpoint import (
    hint_provider_for_key,
    is_console_host,
    looks_like_html,
    normalize_provider_base_url,
    telemetry_host,
)
from backend.core.upstream_errors import classify_http, classify_upstream_error, fields_from_http_body
from backend.services import ai_model_settings as ai_models

PROBE_MAX_TOKENS = 16
PROBE_REASONING_MAX_TOKENS = 256
MODELS_TIMEOUT = 12.0
PROBE_TIMEOUT = 20.0


@dataclass
class ValidationResult:
    ok: bool
    result: str
    error_type: str = ''
    key_hint: Optional[str] = None
    normalized_base_url: str = ''
    base_url_host: str = ''
    model_ids: list[str] = field(default_factory=list)

    def as_api(self) -> dict:
        return {
            'success': self.ok,
            'ok': self.ok,
            'result': self.result,
            'error_type': self.error_type,
            'key_hint': self.key_hint,
            'normalized_base_url': self.normalized_base_url,
            'base_url_host': self.base_url_host,
            'models': self.model_ids,
        }


def _failed(error_type: str, base: str, key_hint: Optional[str], models: Optional[list[str]] = None) -> ValidationResult:
    return ValidationResult(
        ok=False, result='failed', error_type=error_type, key_hint=key_hint,
        normalized_base_url=base, base_url_host=telemetry_host(base), model_ids=models or [],
    )


def _ok(base: str, key_hint: Optional[str], models: list[str]) -> ValidationResult:
    return ValidationResult(
        ok=True, result='ok', key_hint=key_hint,
        normalized_base_url=base, base_url_host=telemetry_host(base), model_ids=models,
    )


def _extract_ids(payload) -> list[str]:
    raw = payload.get('data', payload) if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        return []
    ids = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            ids.append(item.strip())
        elif isinstance(item, dict):
            name = str(item.get('id') or item.get('name') or '').removeprefix('models/').strip()
            if name:
                ids.append(name)
    return ids


def _classify_response(status: int, text: str, *, models_path: bool) -> str:
    ctype_html = looks_like_html(text)
    if ctype_html:
        return 'bad_endpoint'
    if models_path and status == 404:
        return 'bad_endpoint'
    return classify_http(status, text)


def _get_models(base: str, api_key: str) -> tuple[list[str], Optional[str]]:
    import httpx
    url = base.rstrip('/') + '/models'
    try:
        with httpx.Client(timeout=MODELS_TIMEOUT, trust_env=not is_local_url(base)) as client:
            response = client.get(url, headers={'Authorization': 'Bearer ' + (api_key or 'EMPTY')})
    except httpx.TimeoutException:
        return [], 'timeout'
    except httpx.RequestError:
        return [], 'connection'
    text = response.text or ''
    content_type = (response.headers.get('content-type') or '').lower()
    if 'text/html' in content_type or looks_like_html(text):
        host = urlparse(base).hostname or ''
        return [], 'console_host' if is_console_host(host) else 'bad_endpoint'
    if response.status_code >= 400:
        return [], _classify_response(response.status_code, text[:4000], models_path=True)
    try:
        payload = response.json()
    except ValueError:
        return [], 'bad_endpoint'
    ids = _extract_ids(payload)
    return ids, None


def _probe(base: str, api_key: str, model: str) -> Optional[str]:
    import httpx
    from backend.core.llm_providers import guarded_chat_kwargs, token_param_kwargs
    tokens = PROBE_REASONING_MAX_TOKENS if uses_max_completion_tokens(model, base) else PROBE_MAX_TOKENS
    payload = token_param_kwargs(model, base, guarded_chat_kwargs(base, {
        'model': model,
        'messages': [{'role': 'user', 'content': 'ok'}],
        'max_tokens': tokens,
    }))
    url = base.rstrip('/') + '/chat/completions'
    try:
        with httpx.Client(timeout=PROBE_TIMEOUT, trust_env=not is_local_url(base)) as client:
            response = client.post(
                url, json=payload,
                headers={'Authorization': 'Bearer ' + (api_key or 'EMPTY'), 'Content-Type': 'application/json'},
            )
    except httpx.TimeoutException:
        return 'timeout'
    except httpx.RequestError:
        return 'connection'
    text = response.text or ''
    content_type = (response.headers.get('content-type') or '').lower()
    if 'text/html' in content_type or looks_like_html(text):
        return 'bad_endpoint'
    if response.status_code >= 400:
        return classify_upstream_error(**fields_from_http_body(response.status_code, text[:4000]))
    return None


def validate_connection(connection: ai_models.Connection, model: str) -> ValidationResult:
    resolved = ai_models.resolve_secret(connection, ai_models.for_editing())
    hint = hint_provider_for_key(resolved.api_key)
    if hint == resolved.provider:
        hint = None
    if resolved.provider == 'compatible' and resolved.base_url:
        normalized = normalize_provider_base_url(resolved.base_url)
        base = normalized.url
        if 'console_host' in normalized.warnings:
            return _failed('console_host', base, hint)
    else:
        base = ai_models.chat_endpoint(resolved, model or 'unused')['base_url']
    host = urlparse(base).hostname or ''
    if is_console_host(host):
        return _failed('console_host', base, hint)
    if resolved.provider == 'compatible' and not base:
        return _failed('bad_endpoint', base, hint)
    api_key = resolved.api_key or ''
    models, models_error = _get_models(base, api_key)
    if models_error:
        return _failed(models_error, base, hint, models)
    if not (model or '').strip():
        return _failed('model_not_found', base, hint, models)
    probe_error = _probe(base, api_key, model.strip())
    if probe_error:
        return _failed(probe_error, base, hint, models)
    return _ok(base, hint, models)
