"""Settings-page provider access check: GET /models, plus a tiny call for chat models.

Image/audio connections check account model access without paid generation. They
must list the selected model; a public catalog is never proof of account access.

Save may persist a failed result (marked red). Generation blocks failed checks,
but permits transient errors. Never returns keys or provider error text.

HTTP failures go through ``classify_upstream_error``; the returned
``hint_key`` is the official catalog sentence. Local remaps (console host,
HTML, GET /models 404) use ``hint_key_for`` of the same enum.

A followed visual-understanding model without vision is a local capability
miss (``vision_unsupported``), not an upstream class: save stays allowed.

Custom, local, and user-supplied OpenAI-compatible addresses treat ``/models``
as advisory. A name missing from a successful list is ``warning``; the chat
probe can still be ok. Cover and transcription still require that name
(``model_not_found``) when the list succeeded. A 404 or unsupported ``/models``
does not fail those addresses by itself. Official cloud providers keep a hard
failure when ``/models`` itself fails.
"""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Literal, Optional
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

from backend.core.provider_model_fetch import AccountModelList, list_account_models
from backend.core.provider_model_fetch import get_models as fetch_account_models

PROBE_MAX_TOKENS = 16
PROBE_REASONING_MAX_TOKENS = 256
PROBE_TIMEOUT = 20.0

# E6: local model server (Ollama / LM Studio) not running -> connection refused on a local URL.
LOCAL_SERVICE_DOWN_HINT_KEY = '连不上本机模型服务。请先启动 Ollama（或 LM Studio），确认地址和端口正确后再点测试。'
# D2: selected name absent from a successful /models list. Non-blocking; also the i18n key.
MODEL_NOT_LISTED_WARNING = '这个模型名不在服务器的模型列表里。请改选列表中已有的模型，否则后面生成时可能会失败。'
VISION_BLOCK_MESSAGE = '画面理解使用的模型不能看图。请到「设置 → 服务商与模型」换一个能看图的模型后再生成。'


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
    recommended: dict[str, list[str]] = field(default_factory=dict)
    truncated: bool = False
    message_key: str = ''
    # Telemetry: closed-set code and integer upstream status only (no URL/key/body).
    http_status: Optional[int] = None
    network_kind: str = ''
    empty_key: bool = False
    # Symbolic upstream error.code / type, when the body had one. Not a message.
    upstream_code: str = ''
    # Non-blocking. Empty when the test has nothing extra to say.
    warning: str = ''
    # F2 trial-run probe (None when probe_kind=quick / not run).
    probe_kind: str = 'quick'
    trial_context_ok: Optional[bool] = None
    trial_rate_limited: Optional[bool] = None
    trial_json_ok: Optional[bool] = None
    trial_avg_ms: Optional[int] = None
    trial_estimate_requests: Optional[int] = None
    trial_estimate_minutes: Optional[float] = None
    trial_passed: Optional[bool] = None

    @property
    def error_code(self) -> str:
        if self.ok:
            return ''
        from backend.core.connection_test_codes import connection_test_error_code
        return connection_test_error_code(self.error_type, http_status=self.http_status,
                                          network_kind=self.network_kind, empty_key=self.empty_key,
                                          upstream_code=self.upstream_code)

    def as_api(self) -> dict:
        from backend.core.connection_test_codes import safe_http_status
        return {
            'error_code': self.error_code,
            'http_status': safe_http_status(self.http_status),
            'success': self.ok,
            'ok': self.ok,
            'result': self.result,
            'error_type': self.error_type,
            'hint_key': self.hint_key,
            'key_hint': self.key_hint,
            'normalized_base_url': self.normalized_base_url,
            'base_url_host': self.base_url_host,
            'models': self.model_ids,
            'recommended': {key: list(value) for key, value in self.recommended.items()},
            'truncated': self.truncated,
            'message_key': self.message_key,
            'warning': self.warning,
            'probe_kind': self.probe_kind,
            'trial_context_ok': self.trial_context_ok,
            'trial_rate_limited': self.trial_rate_limited,
            'trial_json_ok': self.trial_json_ok,
            'trial_avg_ms': self.trial_avg_ms,
            'trial_estimate_requests': self.trial_estimate_requests,
            'trial_estimate_minutes': self.trial_estimate_minutes,
            'trial_passed': self.trial_passed,
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
    *,
    recommended: Optional[dict[str, list[str]]] = None,
    truncated: bool = False,
    message_key: str = '',
    http_status: Optional[int] = None,
    network_kind: str = '',
) -> ValidationResult:
    if not isinstance(classified, ClassifiedUpstreamError):
        classified = _as_type(classified)
    return ValidationResult(
        http_status=http_status, network_kind=network_kind,
        upstream_code=getattr(classified, 'upstream_code', '') or '',
        ok=False, result='transient' if classified.retryable else 'failed',
        error_type=classified.error_type.value,
        hint_key=classified.hint_key,
        key_hint=key_hint, normalized_base_url=base, base_url_host=_host(base), model_ids=models or [],
        recommended=recommended or {}, truncated=truncated, message_key=message_key,
    )


def _ok(
    base: str,
    key_hint: Optional[str],
    models: list[str],
    *,
    recommended: Optional[dict[str, list[str]]] = None,
    truncated: bool = False,
    message_key: str = '',
    warning: str = '',
) -> ValidationResult:
    return ValidationResult(
        ok=True, result='ok', key_hint=key_hint,
        normalized_base_url=base, base_url_host=_host(base), model_ids=models,
        recommended=recommended or {}, truncated=truncated, message_key=message_key,
        warning=warning,
    )


def _html_or_classify(status: int, text: str, content_type: str) -> ClassifiedUpstreamError | None:
    if 'text/html' in content_type or looks_like_html(text):
        classified = _classify(status, text)
        return classified if classified.error_type is UpstreamErrorType.BAD_ENDPOINT else _as_type(UpstreamErrorType.BAD_ENDPOINT)
    return None


def _get_models(base: str, api_key: str, provider: str = 'compatible'):
    models, error, fetched = fetch_account_models(base, api_key, provider)
    return models, error, fetched


@dataclass(frozen=True)
class _ProbeClassified(ClassifiedUpstreamError):
    """Classified probe failure plus telemetry-only integer status / network kind."""
    http_status: Optional[int] = None
    network_kind: str = ''
    upstream_code: str = ''


def _with_detail(classified: ClassifiedUpstreamError, http_status=None, network_kind='', upstream_code='') -> ClassifiedUpstreamError:
    return _ProbeClassified(error_type=classified.error_type, retryable=classified.retryable,
                            hint_key=classified.hint_key, http_status=http_status, network_kind=network_kind,
                            upstream_code=upstream_code or '')


def _completion_text(message: Any) -> str:
    """Visible answer text. Empty, whitespace, and reasoning-only replies are not a success."""
    if not isinstance(message, dict):
        return ''
    content = message.get('content')
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and isinstance(item.get('text'), str):
                parts.append(item['text'])
        return ''.join(parts).strip()
    return ''


def _non_stream_completion(payload: Any) -> bool:
    """A chat completion with a non-empty answer, not an SSE stream, error object, or blank 2xx."""
    if not isinstance(payload, dict) or payload.get('error'):
        return False
    choices = payload.get('choices')
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return False
    return bool(_completion_text(choices[0].get('message')))


def _probe(base: str, api_key: str, model: str) -> Optional[ClassifiedUpstreamError]:
    import httpx
    from backend.core.llm_providers import guarded_chat_kwargs, http_chat_body, token_param_kwargs
    from backend.core.upstream_errors import symbolic_error_code
    tokens = PROBE_REASONING_MAX_TOKENS if uses_max_completion_tokens(model, base) else PROBE_MAX_TOKENS
    payload = http_chat_body(token_param_kwargs(model, base, guarded_chat_kwargs(base, {
        'model': model,
        'messages': [{'role': 'user', 'content': 'ok'}],
        'max_tokens': tokens,
    })))
    # Hosts such as APIMart default to text/event-stream unless this is false.
    payload['stream'] = False
    url = base.rstrip('/') + '/chat/completions'
    try:
        with httpx.Client(timeout=PROBE_TIMEOUT, trust_env=not is_local_url(base)) as client:
            response = client.post(
                url, json=payload,
                headers={'Authorization': 'Bearer ' + (api_key or 'EMPTY'), 'Content-Type': 'application/json'},
            )
    except httpx.TimeoutException:
        return _with_detail(_classify(None, '', error_name='TimeoutError'))
    except httpx.RequestError as exc:
        from backend.core.upstream_errors import network_kind_of
        return _with_detail(_classify(None, '', error_name='ConnectionError'), network_kind=network_kind_of(exc))
    status = response.status_code
    text = response.text or ''
    upstream = symbolic_error_code(text[:4000])
    if response.status_code == 429 or 500 <= response.status_code <= 599:
        return _with_detail(_as_type(UpstreamErrorType.RATE_LIMITED if response.status_code == 429 else UpstreamErrorType.UPSTREAM_UNAVAILABLE), status, upstream_code=upstream)
    content_type = (response.headers.get('content-type') or '').lower()
    html = _html_or_classify(response.status_code, text[:4000], content_type)
    if html:
        return _with_detail(html, status, upstream_code=upstream)
    if response.status_code >= 400:
        return _with_detail(_classify(response.status_code, text[:4000]), status, upstream_code=upstream)
    # A 200 SSE body used to look like success and then fail every real job.
    if 'text/event-stream' in content_type or text.lstrip().startswith('data:'):
        return _with_detail(_as_type(UpstreamErrorType.UNKNOWN), status, upstream_code=upstream)
    try:
        parsed = response.json()
    except Exception:  # noqa: BLE001 - non-JSON 2xx is not a completion
        return _with_detail(_as_type(UpstreamErrorType.UNKNOWN), status, upstream_code=upstream)
    if not _non_stream_completion(parsed):
        # Some gateways return HTTP 200 with an error envelope and no choices.
        classified = _classify(None, text[:4000])
        if classified.error_type is UpstreamErrorType.UNKNOWN:
            classified = _as_type(UpstreamErrorType.UNKNOWN)
        return _with_detail(classified, status, upstream_code=symbolic_error_code(parsed) or upstream)
    return None


def _is_loopback_url(url: str | None) -> bool:
    """only this machine counts. LAN IPs, link-local and ``.local`` gateways are
    remote self-hosted services, so "start local Ollama" would mislead there. (Proxy
    bypass still uses the wider ``is_local_url``.)"""
    if not url:
        return False
    try:
        from urllib.parse import urlparse
        import ipaddress
        host = (urlparse(url).hostname or '').lower().rstrip('.')
    except Exception:  # noqa: BLE001
        return False
    if host == 'localhost' or host.endswith('.localhost'):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _local_service_down(result: ValidationResult, base: str) -> ValidationResult:
    if not result.ok and result.error_type == UpstreamErrorType.CONNECTION.value and _is_loopback_url(base):
        result.hint_key = LOCAL_SERVICE_DOWN_HINT_KEY
    return result


def _custom_or_local_compat(connection: ai_models.Connection, base: str) -> bool:
    """Addresses where ``/models`` is advisory: custom compat, Ollama, LM Studio, localhost.

    Official cloud presets keep a hard failure when the list endpoint itself fails.
    A user-supplied OpenAI-compatible base URL (a relay pasted onto a preset) is included.
    """
    provider = (connection.provider or '').strip().lower()
    if provider in {'compatible', 'ollama', 'lmstudio'} or is_local_url(base):
        return True
    from backend.core.provider_presets import get_provider
    preset = get_provider(provider)
    if preset is None:
        return False
    if preset.local_compat_remap or preset.protocol == 'local':
        return True
    return (connection.base_url_source or '') == 'user' and preset.protocol == 'openai-completions'


def _models_unsupported(error: ClassifiedUpstreamError, fetched: Any) -> bool:
    """``/models`` 404, HTML, or a method the gateway does not implement.

    Auth, quota, rate limit, and connection failures are still real test failures.
    """
    if error.error_type is UpstreamErrorType.BAD_ENDPOINT:
        return True
    status = int(getattr(fetched, 'http_status', 0) or 0)
    return error.error_type is UpstreamErrorType.UNKNOWN and status in {404, 405, 501}


def validate_connection(
    connection: ai_models.Connection, model: str,
    *, purpose: Literal['analysis', 'cover', 'transcription'] = 'analysis',
) -> ValidationResult:
    resolved = ai_models.resolve_secret(connection, ai_models.for_editing())
    result = _validate_resolved(resolved, model, purpose=purpose)
    result.empty_key = not (resolved.api_key or '').strip()
    return _local_service_down(result, result.normalized_base_url)


def _validate_resolved(
    resolved: ai_models.Connection, model: str,
    *, purpose: Literal['analysis', 'cover', 'transcription'] = 'analysis',
) -> ValidationResult:
    hint = hint_provider_for_key(resolved.api_key)
    if hint == resolved.provider:
        hint = None
    if resolved.provider == 'compatible' and resolved.base_url:
        normalized = normalize_provider_base_url(resolved.base_url, resolved.provider)
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
    models, models_error, fetched = _get_models(base, api_key, resolved.provider)
    list_known = models_error is None
    advisory = _custom_or_local_compat(resolved, base)
    if models_error and advisory and _models_unsupported(models_error, fetched):
        # Gateways that omit /models: keep the chat probe (or, for image/audio, do not
        # fail the test solely because the list URL is missing).
        models_error = None
        list_known = False
        extras = dict(recommended={}, truncated=False, message_key='')
    else:
        extras = dict(recommended=fetched.recommended, truncated=fetched.truncated, message_key=fetched.message_key)
    if models_error:
        return _failed(models_error, base, hint, models, **extras,
                       http_status=getattr(fetched, 'http_status', 0) or None, network_kind=getattr(fetched, 'network_kind', ''))
    if not (model or '').strip():
        return _failed(UpstreamErrorType.MODEL_NOT_FOUND, base, hint, models, **extras)
    selected = model.strip()
    if purpose in ('cover', 'transcription'):
        # Check authenticated account access, not paid image/audio generation. Never
        # send non-chat models to chat/completions or infer access from a catalog.
        # Bailian's three adapted sync ASR models are omitted from /models but still
        # transcribe, so a successful list fetch is enough for those ids.
        # A missing list endpoint is not that check: do not hard-fail solely for it.
        from backend.core.asr_model_catalog import DASHSCOPE_SYNC
        adapted = purpose == 'transcription' and resolved.provider == 'dashscope' and selected in DASHSCOPE_SYNC
        if selected not in models and not adapted:
            if not list_known:
                return _ok(base, hint, models, **extras)
            return _failed(UpstreamErrorType.MODEL_NOT_FOUND, base, hint, models, **extras)
        return _ok(base, hint, models, **extras)
    # Analysis: a successful list that omits the name is a warning. The chat probe
    # still decides ok/failed. Cover/transcription keep MODEL_NOT_FOUND above.
    warning = ''
    if list_known and not fetched.truncated and advisory and selected not in models:
        warning = MODEL_NOT_LISTED_WARNING
    probe_error = _probe(base, api_key, selected)
    if probe_error:
        return _failed(probe_error, base, hint, models, **extras,
                       http_status=getattr(probe_error, 'http_status', None),
                       network_kind=getattr(probe_error, 'network_kind', ''))
    return _ok(base, hint, models, **extras, warning=warning)


def resolve_fetch_base(connection: ai_models.Connection) -> tuple[str, Optional[ClassifiedUpstreamError]]:
    """Same address rules as ``validate_connection``, without the chat probe."""
    if connection.provider == 'compatible' and connection.base_url:
        normalized = normalize_provider_base_url(connection.base_url)
        if 'console_host' in normalized.warnings:
            return normalized.url, _as_type(UpstreamErrorType.BAD_ENDPOINT)
        return normalized.url, None
    base = ai_models.chat_endpoint(connection, 'unused')['base_url']
    if is_console_host(urlparse(base).hostname or ''):
        return base, _as_type(UpstreamErrorType.BAD_ENDPOINT)
    if connection.provider == 'compatible' and not base:
        return base, _as_type(UpstreamErrorType.BAD_ENDPOINT)
    return base, None


def fetch_list_for_connection(connection: ai_models.Connection, *, http=None) -> AccountModelList:
    """Custom-provider / settings 'fetch list': ``/models`` + preset intersection."""
    resolved = ai_models.resolve_secret(connection, ai_models.for_editing())
    base, pre = resolve_fetch_base(resolved)
    if pre:
        from backend.core.provider_model_fetch import FETCH_LIST_FAILED
        return AccountModelList(
            ok=False,
            source='empty',
            error_type=pre.error_type.value,
            hint_key=pre.hint_key,
            message_key=FETCH_LIST_FAILED,
            base_url_host=_host(base),
        )
    return list_account_models(
        base_url=base,
        api_key=resolved.api_key or '',
        provider=resolved.provider,
        http=http,
    )


# ---------------------------------------------------------------------------
# F2: trial run — real step1 outline prompt + sample SRT, 3× JSON checks
# ---------------------------------------------------------------------------

TRIAL_ATTEMPTS = 3
TRIAL_GAP_SEC = 1.0
TRIAL_TIMEOUT = 90.0
TRIAL_MAX_TOKENS = 2048
# ~30 min CN speech transcript size used for the estimate line.
TRIAL_ESTIMATE_30MIN_CHARS = 10_000
_TRIAL_JSON_SUFFIX = (
    "\n\n【试跑输出约束】请只输出一个 JSON 对象，不要 Markdown 代码块，不要解释。"
    "格式：{\"topics\":[{\"title\":\"话题名\",\"subtopics\":[\"子话题1\",\"子话题2\"]}]}。"
)

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / 'prompts'
_OUTLINE_PROMPT_PATH = Path(__file__).resolve().parents[1] / 'prompt' / '大纲.txt'


def _load_trial_sample(*, language: str = 'zh') -> str:
    name = 'trial_sample_zh.srt' if language != 'en' else 'trial_sample_en.srt'
    path = _PROMPTS_DIR / name
    if not path.is_file():
        # Fallback: tiny inline stub so tests without fixtures still exercise the path.
        return "1\n00:00:00,000 --> 00:00:03,000\n试跑样例字幕。\n"
    return path.read_text(encoding='utf-8')


def _load_outline_prompt() -> str:
    if _OUTLINE_PROMPT_PATH.is_file():
        return _OUTLINE_PROMPT_PATH.read_text(encoding='utf-8')
    return (
        "你是视频大纲分析师。根据输入字幕提取话题大纲。"
        "输入为 JSON：{\"text\": \"...\"}。"
    )


def _srt_plain_text(srt: str) -> str:
    """Strip indices and timestamps; keep dialogue lines for the outline input."""
    lines: list[str] = []
    for raw in srt.splitlines():
        line = raw.strip()
        if not line or line.isdigit():
            continue
        if '-->' in line:
            continue
        lines.append(line)
    return '\n'.join(lines)


def _parse_trial_json(text: str) -> bool:
    """True when the body is parseable JSON with at least one topic title."""
    import json
    import re
    raw = (text or '').strip()
    if not raw:
        return False
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw, flags=re.IGNORECASE).strip()
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return False
    if isinstance(data, list):
        return any(isinstance(item, dict) and isinstance(item.get('title'), str) and item['title'].strip() for item in data)
    if isinstance(data, dict):
        topics = data.get('topics') or data.get('outline') or data.get('outlines')
        if isinstance(topics, list):
            return any(isinstance(item, dict) and isinstance(item.get('title'), str) and item['title'].strip() for item in topics)
        if isinstance(data.get('title'), str) and data['title'].strip():
            return True
    return False


def _is_context_error(status: int | None, body: str) -> bool:
    blob = (body or '').lower()
    if 'context_length' in blob or 'maximum context' in blob or 'context window' in blob:
        return True
    if 'too many tokens' in blob or 'token limit' in blob:
        return True
    return False


def _trial_estimate(avg_ms: int) -> tuple[int, float]:
    """N chunks for ~30 min material; M minutes = avg_ms × N / concurrency / 60000."""
    import math
    try:
        from backend.pipeline.settings import effective_chunk_size
        chunk = max(1000, int(effective_chunk_size()))
    except Exception:  # noqa: BLE001
        chunk = 5000
    try:
        from backend.pipeline.concurrency import workers
        concurrency = max(1, int(workers()))
    except Exception:  # noqa: BLE001
        concurrency = 4
    n = max(1, math.ceil(TRIAL_ESTIMATE_30MIN_CHARS / chunk))
    minutes = round((avg_ms * n / concurrency) / 60_000, 1)
    return n, minutes


def _trial_once(base: str, api_key: str, model: str, full_input: str) -> dict:
    """One chat completion for the trial. Returns timing + classification flags."""
    import time
    import httpx
    from backend.core.llm_providers import guarded_chat_kwargs, http_chat_body, token_param_kwargs

    payload = http_chat_body(token_param_kwargs(model, base, guarded_chat_kwargs(base, {
        'model': model,
        'messages': [{'role': 'user', 'content': full_input}],
        'max_tokens': TRIAL_MAX_TOKENS,
    })))
    payload['stream'] = False
    # Prefer JSON object mode when the gateway understands it; ignore 400 and retry once without.
    payload['response_format'] = {'type': 'json_object'}
    url = base.rstrip('/') + '/chat/completions'
    headers = {'Authorization': 'Bearer ' + (api_key or 'EMPTY'), 'Content-Type': 'application/json'}
    started = time.monotonic()
    try:
        with httpx.Client(timeout=TRIAL_TIMEOUT, trust_env=not is_local_url(base)) as client:
            response = client.post(url, json=payload, headers=headers)
            if response.status_code == 400 and 'response_format' in (response.text or '').lower():
                payload.pop('response_format', None)
                response = client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException:
        return {'ms': int((time.monotonic() - started) * 1000), 'ok_http': False,
                'rate_limited': False, 'context_error': False, 'json_ok': False, 'status': None}
    except httpx.RequestError:
        return {'ms': int((time.monotonic() - started) * 1000), 'ok_http': False,
                'rate_limited': False, 'context_error': False, 'json_ok': False, 'status': None}
    ms = int((time.monotonic() - started) * 1000)
    status = response.status_code
    text = response.text or ''
    rate_limited = status == 429
    context_error = _is_context_error(status, text[:4000])
    if status >= 400:
        return {'ms': ms, 'ok_http': False, 'rate_limited': rate_limited,
                'context_error': context_error, 'json_ok': False, 'status': status}
    content = ''
    try:
        parsed = response.json()
        choices = parsed.get('choices') if isinstance(parsed, dict) else None
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            content = _completion_text(choices[0].get('message'))
    except Exception:  # noqa: BLE001
        content = text
    return {
        'ms': ms,
        'ok_http': True,
        'rate_limited': rate_limited,
        'context_error': context_error,
        'json_ok': _parse_trial_json(content),
        'status': status,
    }


def trial_run(
    base: str,
    api_key: str,
    model: str,
    *,
    language: str = 'zh',
    sleep=None,
) -> dict:
    """Send the sample SRT through the real outline prompt three times (1s apart).

    Returns a dict of trial_* fields suitable for merging onto ``ValidationResult``.
    Does not raise on upstream failure — callers map flags into the API payload.
    """
    import time
    import json as _json
    sleeper = sleep or time.sleep
    srt = _load_trial_sample(language=language)
    plain = _srt_plain_text(srt)
    prompt = _load_outline_prompt() + _TRIAL_JSON_SUFFIX
    # Match LLMProvider._build_full_input compact JSON shape used by step1.
    full_input = f"{prompt}\n\n输入内容：\n{_json.dumps({'text': plain}, ensure_ascii=False)}"
    attempts: list[dict] = []
    for index in range(TRIAL_ATTEMPTS):
        attempts.append(_trial_once(base, api_key, model, full_input))
        if index + 1 < TRIAL_ATTEMPTS:
            sleeper(TRIAL_GAP_SEC)
    latencies = [a['ms'] for a in attempts]
    avg_ms = int(round(sum(latencies) / max(1, len(latencies))))
    context_ok = all(not a['context_error'] and a['ok_http'] for a in attempts)
    rate_limited = any(a['rate_limited'] for a in attempts)
    json_ok = all(a['json_ok'] for a in attempts)
    n, minutes = _trial_estimate(avg_ms)
    passed = bool(context_ok and json_ok and not rate_limited)
    # Rate limit is a warning (⚠), not a hard fail for trial_passed yellow badge —
    # spec: any ✗ shows yellow. Rate ⚠ counts as not fully passed.
    trial_passed = bool(context_ok and json_ok and not rate_limited)
    # If rate limited but JSON+context ok → still "not fully passed" (yellow).
    if context_ok and json_ok and rate_limited:
        trial_passed = False
    if not context_ok or not json_ok:
        trial_passed = False
    return {
        'probe_kind': 'trial',
        'trial_context_ok': context_ok,
        'trial_rate_limited': rate_limited,
        'trial_json_ok': json_ok,
        'trial_avg_ms': avg_ms,
        'trial_estimate_requests': n,
        'trial_estimate_minutes': minutes,
        'trial_passed': trial_passed,
        'attempts': attempts,
    }


def validate_connection_with_probe(
    connection: ai_models.Connection,
    model: str,
    *,
    purpose: Literal['analysis', 'cover', 'transcription'] = 'analysis',
    probe_kind: Literal['quick', 'trial'] = 'quick',
    language: str = 'zh',
) -> ValidationResult:
    """Quick ``_probe`` (default) or F2 trial run after the same address/list checks."""
    result = validate_connection(connection, model, purpose=purpose)
    result.probe_kind = probe_kind
    if probe_kind != 'trial' or purpose != 'analysis':
        return result
    if not result.ok:
        # Address / key already failed — skip the expensive trial.
        result.trial_passed = False
        result.trial_context_ok = False
        result.trial_json_ok = False
        result.trial_rate_limited = False
        return result
    resolved = ai_models.resolve_secret(connection, ai_models.for_editing())
    base = result.normalized_base_url or ai_models.chat_endpoint(resolved, model)['base_url']
    trial = trial_run(base, resolved.api_key or '', model.strip(), language=language)
    result.probe_kind = 'trial'
    result.trial_context_ok = trial['trial_context_ok']
    result.trial_rate_limited = trial['trial_rate_limited']
    result.trial_json_ok = trial['trial_json_ok']
    result.trial_avg_ms = trial['trial_avg_ms']
    result.trial_estimate_requests = trial['trial_estimate_requests']
    result.trial_estimate_minutes = trial['trial_estimate_minutes']
    result.trial_passed = trial['trial_passed']
    # Trial failures do not flip ok/result — save stays allowed (yellow badge only).
    return result
