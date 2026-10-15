"""Settings-page provider access check: GET /models, plus a tiny call for chat models.

Image/audio connections check account model access without paid generation. They
must list the selected model; a public catalog is never proof of account access.

Save may persist a failed result (marked red). Generation reads the stored
status and blocks. Never returns keys, full URLs, or provider error text.

HTTP failures go through ``classify_upstream_error``; the returned
``hint_key`` is the official catalog sentence. Local remaps (console host,
HTML, GET /models 404) use ``hint_key_for`` of the same enum.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional
from urllib.parse import urlparse

from backend.core.llm_providers import is_local_url, uses_max_completion_tokens
from backend.core.llm_telemetry import hostname_of_base_url
from backend.core.provider_endpoint import (
    hint_provider_for_key,
    is_console_host,
    looks_like_html,
    normalize_provider_base_url,
)
from backend.core.upstream_errors import (
    UPSTREAM_ERROR_TYPES,
    ClassifiedUpstreamError,
    UpstreamErrorType,
    classify_upstream_error,
    hint_key_for,
    is_retryable,
)
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
    hint_key: str = ''
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
            'hint_key': self.hint_key,
            'key_hint': self.key_hint,
            'normalized_base_url': self.normalized_base_url,
            'base_url_host': self.base_url_host,
            'models': self.model_ids,
        }


def _host(base: str) -> str:
    return hostname_of_base_url(base) or 'unknown'


def _as_type(error_type: str | UpstreamErrorType) -> ClassifiedUpstreamError:
    typed = error_type if isinstance(error_type, UpstreamErrorType) else (
        UpstreamErrorType(error_type) if error_type in UPSTREAM_ERROR_TYPES else UpstreamErrorType.UNKNOWN
    )
    return ClassifiedUpstreamError(
        error_type=typed,
        retryable=is_retryable(typed),
        hint_key=hint_key_for(typed),
    )


def _classify(status: int | None, body: str | None = None, *, error_name: str | None = None) -> ClassifiedUpstreamError:
    return classify_upstream_error(status, body, error_name=error_name)


def _failed(
    classified: ClassifiedUpstreamError | str | UpstreamErrorType,
    base: str,
    key_hint: Optional[str],
    models: Optional[list[str]] = None,
) -> ValidationResult:
    if not isinstance(classified, ClassifiedUpstreamError):
        classified = _as_type(classified)
    return ValidationResult(
        ok=False, result='failed',
        error_type=classified.error_type.value,
        hint_key=classified.hint_key,
        key_hint=key_hint, normalized_base_url=base, base_url_host=_host(base), model_ids=models or [],
    )


def _ok(base: str, key_hint: Optional[str], models: list[str]) -> ValidationResult:
    return ValidationResult(
        ok=True, result='ok', key_hint=key_hint,
        normalized_base_url=base, base_url_host=_host(base), model_ids=models,
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


def _classify_response(status: int, text: str, *, models_path: bool) -> ClassifiedUpstreamError:
    classified = _classify(status, text)
    if models_path and status == 404:
        return _as_type(UpstreamErrorType.BAD_ENDPOINT)
    return classified


def _html_or_classify(status: int, text: str, content_type: str) -> ClassifiedUpstreamError | None:
    if 'text/html' in content_type or looks_like_html(text):
        classified = _classify(status, text)
        return classified if classified.error_type is UpstreamErrorType.BAD_ENDPOINT else _as_type(UpstreamErrorType.BAD_ENDPOINT)
    return None


def _get_models(base: str, api_key: str) -> tuple[list[str], Optional[ClassifiedUpstreamError]]:
    import httpx
    url = base.rstrip('/') + '/models'
    try:
        with httpx.Client(timeout=MODELS_TIMEOUT, trust_env=not is_local_url(base)) as client:
            response = client.get(url, headers={'Authorization': 'Bearer ' + (api_key or 'EMPTY')})
    except httpx.TimeoutException:
        return [], _classify(None, '', error_name='TimeoutError')
    except httpx.RequestError:
        return [], _classify(None, '', error_name='ConnectionError')
    text = response.text or ''
    content_type = (response.headers.get('content-type') or '').lower()
    html = _html_or_classify(response.status_code, text[:4000], content_type)
    if html:
        return [], html
    if response.status_code >= 400:
        return [], _classify_response(response.status_code, text[:4000], models_path=True)
    try:
        payload = response.json()
    except ValueError:
        return [], _as_type(UpstreamErrorType.BAD_ENDPOINT)
    ids = _extract_ids(payload)
    return ids, None


def _probe(base: str, api_key: str, model: str) -> Optional[ClassifiedUpstreamError]:
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
        return _classify(None, '', error_name='TimeoutError')
    except httpx.RequestError:
        return _classify(None, '', error_name='ConnectionError')
    text = response.text or ''
    content_type = (response.headers.get('content-type') or '').lower()
    html = _html_or_classify(response.status_code, text[:4000], content_type)
    if html:
        return html
    if response.status_code >= 400:
        return _classify(response.status_code, text[:4000])
    return None


def validate_connection(
    connection: ai_models.Connection, model: str,
    *, purpose: Literal['analysis', 'cover', 'transcription'] = 'analysis',
) -> ValidationResult:
    resolved = ai_models.resolve_secret(connection, ai_models.for_editing())
    hint = hint_provider_for_key(resolved.api_key)
    if hint == resolved.provider:
        hint = None
    if resolved.provider == 'compatible' and resolved.base_url:
        normalized = normalize_provider_base_url(resolved.base_url)
        base = normalized.url
        if 'console_host' in normalized.warnings:
            return _failed(UpstreamErrorType.BAD_ENDPOINT, base, hint)
    else:
        base = ai_models.chat_endpoint(resolved, model or 'unused')['base_url']
    if purpose == 'cover' and resolved.image_base_url:
        base = ai_models.image_endpoint(resolved)['base_url']
    host = urlparse(base).hostname or ''
    if is_console_host(host):
        return _failed(UpstreamErrorType.BAD_ENDPOINT, base, hint)
    if resolved.provider == 'compatible' and not base:
        return _failed(UpstreamErrorType.BAD_ENDPOINT, base, hint)
    api_key = resolved.api_key or ''
    models, models_error = _get_models(base, api_key)
    if models_error:
        return _failed(models_error, base, hint, models)
    if not (model or '').strip():
        return _failed(UpstreamErrorType.MODEL_NOT_FOUND, base, hint, models)
    if purpose in ('cover', 'transcription'):
        # Check authenticated account access, not paid image/audio generation. Never
        # send non-chat models to chat/completions or infer access from a catalog.
        if model.strip() not in models:
            return _failed(UpstreamErrorType.MODEL_NOT_FOUND, base, hint, models)
        return _ok(base, hint, models)
    probe_error = _probe(base, api_key, model.strip())
    if probe_error:
        return _failed(probe_error, base, hint, models)
    return _ok(base, hint, models)
