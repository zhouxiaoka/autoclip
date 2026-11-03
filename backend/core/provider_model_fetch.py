"""First-party provider ``/models`` client.

Fetches an account model list (pagination, timeout, layered errors), then
intersects it with preset candidates for backfill. Used by settings validation
and the custom-provider fetch-list API.

This is AutoClip code, not a third-party port. Results and telemetry never
include API keys, full URLs, user paths, or provider response text.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from backend.core.llm_providers import is_local_url
from backend.core.llm_telemetry import hostname_of_base_url
from backend.core.upstream_errors import (
    ClassifiedUpstreamError,
    UpstreamErrorType,
    classify_upstream_error,
    hint_key_for,
    is_retryable,
)

MODELS_TIMEOUT_SEC = 15.0
MAX_PAGES = 20
MAX_MODELS = 2000
ANTHROPIC_PAGE_SIZE = 100
GEMINI_PAGE_SIZE = 200
ANTHROPIC_VERSION = "2023-06-01"

OPENAI_COMPAT_PROTOCOLS = frozenset({"openai-completions", "openai-responses", "local"})
SUPPORTED_PROTOCOLS = OPENAI_COMPAT_PROTOCOLS | {"anthropic-messages", "google-generative-ai"}

FETCH_LIST_FAILED = "settings.providers.fetch_list_failed"
FETCH_LIST_UPDATED = "settings.providers.fetch_list_updated"
FETCH_LIST_NO_OVERLAP = "settings.providers.fetch_list_no_overlap"
FETCH_LIST_TRUNCATED = "settings.providers.fetch_list_truncated"

_MODEL_ID = re.compile(r"^[\w.\-:/+]{1,256}$")
_PURPOSES = ("analysis", "vision", "asr", "image")
HttpGet = Callable[..., Any]


@dataclass
class AccountModelList:
    ok: bool
    models: list[str] = field(default_factory=list)
    recommended: dict[str, list[str]] = field(default_factory=dict)
    truncated: bool = False
    source: str = "empty"
    error_type: str = ""
    hint_key: str = ""
    message_key: str = ""
    base_url_host: str = ""
    pages: int = 0
    # Connection-test telemetry only: integer upstream status and a coarse network kind.
    http_status: int = 0
    network_kind: str = ""
    # Live capability from the account list. Only ``multimodal`` is stored: a Text
    # tag never vetoes the name heuristic. Not part of the public API payload.
    capabilities: dict[str, str] = field(default_factory=dict)

    def as_api(self) -> dict:
        return {
            "ok": self.ok,
            "success": self.ok,
            "models": list(self.models),
            "recommended": {key: list(value) for key, value in self.recommended.items()},
            "truncated": self.truncated,
            "source": self.source,
            "error_type": self.error_type,
            "hint_key": self.hint_key,
            "message_key": self.message_key,
            "base_url_host": self.base_url_host,
        }


def _host(base: str) -> str:
    return hostname_of_base_url(base) or "unknown"


def _as_classified(error_type: str | UpstreamErrorType) -> ClassifiedUpstreamError:
    typed = error_type if isinstance(error_type, UpstreamErrorType) else (
        UpstreamErrorType(error_type) if error_type in {item.value for item in UpstreamErrorType} else UpstreamErrorType.UNKNOWN
    )
    return ClassifiedUpstreamError(
        error_type=typed,
        retryable=is_retryable(typed),
        hint_key=hint_key_for(typed),
    )


def _failed(classified: ClassifiedUpstreamError, host: str, *, models: Optional[list[str]] = None, pages: int = 0,
            http_status: int = 0, network_kind: str = "") -> AccountModelList:
    return AccountModelList(
        http_status=http_status if 100 <= int(http_status or 0) <= 599 else 0,
        network_kind=network_kind,
        ok=False,
        models=models or [],
        recommended={purpose: [] for purpose in _PURPOSES},
        source="empty",
        error_type=classified.error_type.value,
        hint_key=classified.hint_key,
        message_key=FETCH_LIST_FAILED,
        base_url_host=host,
        pages=pages,
    )


def _message_key(*, ok: bool, truncated: bool, recommended: Mapping[str, Sequence[str]], had_candidates: bool) -> str:
    if not ok:
        return FETCH_LIST_FAILED
    if truncated:
        return FETCH_LIST_TRUNCATED
    if had_candidates and not any(recommended.values()):
        return FETCH_LIST_NO_OVERLAP
    return FETCH_LIST_UPDATED


def normalize_model_id(raw: Any) -> str:
    name = str(raw or "").removeprefix("models/").strip()
    if not name or not _MODEL_ID.fullmatch(name):
        return ""
    return name


_NON_CHAT_CATEGORIES = frozenset({"image", "video", "audio"})
_VISION_TAGS = frozenset({"vision", "omni"})
_CHAT_TAGS = frozenset({"text", "vision", "omni"})


def capability_from_tags(tags: Any) -> str | None:
    """APIMart ``capability_tags`` may only add vision.

    ``Vision`` or ``Omni`` means multimodal. A ``Text`` tag does not veto the
    name heuristic (Gemini 3.5–3.8, Qwen3.x and Claude are tagged Text and still
    accept images). Unknown or empty tags return None.
    Docs: https://docs.apimart.ai/en/api-reference/texts/models/list
    """
    if not isinstance(tags, Sequence) or isinstance(tags, (str, bytes)):
        return None
    lowered = {str(tag).strip().lower() for tag in tags if str(tag).strip()}
    if lowered & _VISION_TAGS:
        return "multimodal"
    return None


def apimart_listing_entry(item: Any) -> tuple[str, str | None] | None:
    """One APIMart ``/v1/models`` row. None drops image, video, audio, and non-chat tags."""
    if isinstance(item, str):
        name = normalize_model_id(item)
        return (name, None) if name else None
    if not isinstance(item, Mapping):
        return None
    name = normalize_model_id(item.get("id") or item.get("name"))
    if not name:
        return None
    from backend.core.model_catalog import is_non_chat_family
    category = str(item.get("category") or "").strip().lower()
    if category in _NON_CHAT_CATEGORIES or is_non_chat_family(name):
        return None
    tags = item.get("capability_tags")
    capability = capability_from_tags(tags)
    if isinstance(tags, list) and tags and capability is None:
        lowered = {str(tag).strip().lower() for tag in tags if str(tag).strip()}
        if lowered and not (lowered & _CHAT_TAGS):
            return None
    return name, capability


def _page_models(payload: Any, protocol: str, provider: str) -> tuple[list[str], dict[str, str]]:
    if (provider or "").strip().lower() != "apimart":
        return extract_model_ids(payload, protocol=protocol), {}
    ids: list[str] = []
    capabilities: dict[str, str] = {}
    seen: set[str] = set()
    for item in _payload_items(payload, protocol):
        entry = apimart_listing_entry(item)
        if not entry:
            continue
        name, capability = entry
        if name in seen:
            continue
        seen.add(name)
        ids.append(name)
        if capability:
            capabilities[name] = capability
    return ids, capabilities


def _stamp_provider_query(url: str, provider: str) -> str:
    """APIMart publishes category and capability tags only when ``expand=category``."""
    if (provider or "").strip().lower() == "apimart":
        return _with_query(url, expand="category")
    return url


def extract_model_ids(payload: Any, *, protocol: str = "openai-completions") -> list[str]:
    items = _payload_items(payload, protocol)
    ids: list[str] = []
    seen: set[str] = set()
    for item in items:
        name = ""
        if isinstance(item, str):
            name = normalize_model_id(item)
        elif isinstance(item, Mapping):
            name = normalize_model_id(item.get("id") or item.get("name"))
        if name and name not in seen:
            seen.add(name)
            ids.append(name)
    return ids


def intersect_candidates(live_ids: Sequence[str], candidates: Sequence[str]) -> list[str]:
    """Keep preset order; only IDs that appear on the account list."""
    live = set(live_ids)
    out: list[str] = []
    seen: set[str] = set()
    for name in candidates:
        if name in live and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def recommended_by_purpose(provider: str, live_ids: Sequence[str]) -> dict[str, list[str]]:
    from backend.core.provider_presets import get_provider

    preset = get_provider(provider)
    recommended = {purpose: [] for purpose in _PURPOSES}
    if not preset:
        return recommended
    for purpose in _PURPOSES:
        recommended[purpose] = intersect_candidates(live_ids, preset.candidates.get(purpose, ()))
    return recommended


def backfill_model_ids(live_ids: Sequence[str], recommended: Sequence[str]) -> list[str]:
    """Account list is the source of truth; recommended IDs (intersection) come first."""
    live = list(dict.fromkeys(name for name in live_ids if name))
    allowed = set(live)
    head = [name for name in recommended if name in allowed]
    seen = set(head)
    return head + [name for name in live if name not in seen]


def resolve_protocol(provider: str, protocol: Optional[str] = None) -> str:
    if protocol:
        return protocol
    from backend.core.provider_presets import get_provider
    preset = get_provider(provider)
    return preset.protocol if preset else "openai-completions"


def resolve_auth(provider: str, auth: Optional[str] = None) -> str:
    if auth:
        return auth
    from backend.core.provider_presets import get_provider
    preset = get_provider(provider)
    return preset.auth if preset else "api_key"


def _payload_items(payload: Any, protocol: str) -> list[Any]:
    if protocol == "google-generative-ai" and isinstance(payload, Mapping):
        items = payload.get("models")
        return items if isinstance(items, list) else []
    raw = payload.get("data", payload) if isinstance(payload, Mapping) else payload
    if isinstance(raw, list):
        return raw
    if isinstance(raw, Mapping):
        nested = raw.get("data") or raw.get("models")
        return nested if isinstance(nested, list) else []
    return []


def _next_cursor(payload: Any, protocol: str, *, page_ids: Sequence[str]) -> tuple[Optional[str], Optional[str]]:
    """Return ``(kind, cursor)``. kind is after_id / after / page_token."""
    if not isinstance(payload, Mapping):
        return None, None
    if protocol == "google-generative-ai":
        token = payload.get("nextPageToken") or payload.get("next_page_token")
        return ("page_token", str(token)) if token else (None, None)
    if protocol == "anthropic-messages":
        if payload.get("has_more") is True:
            cursor = payload.get("last_id") or payload.get("after_id") or (page_ids[-1] if page_ids else None)
            return ("after_id", str(cursor)) if cursor else ("after_id", None)
        return None, None
    if payload.get("has_more") is True:
        cursor = payload.get("last_id") or payload.get("after_id") or payload.get("after")
        if cursor:
            kind = "after_id" if (payload.get("last_id") or payload.get("after_id")) else "after"
            return kind, str(cursor)
        if page_ids:
            return "after", page_ids[-1]
        return "after", None
    token = payload.get("nextPageToken") or payload.get("next_page_token")
    if token:
        return "page_token", str(token)
    return None, None


def _with_query(url: str, **params: Any) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    for key, value in params.items():
        if value is None:
            query.pop(key, None)
        else:
            query[key] = str(value)
    return urlunparse(parsed._replace(query=urlencode(query)))


def _models_url(base: str, protocol: str) -> str:
    cleaned = (base or "").strip().rstrip("/")
    if protocol == "google-generative-ai":
        if cleaned.endswith("/openai"):
            cleaned = cleaned[: -len("/openai")]
        if cleaned.endswith("/models"):
            return cleaned
        return cleaned + "/models"
    if protocol == "anthropic-messages":
        parsed = urlparse(cleaned)
        if parsed.path in {"", "/"}:
            cleaned = cleaned + "/v1"
    if cleaned.endswith("/models"):
        return cleaned
    return cleaned + "/models"


def _headers(protocol: str, api_key: str, auth: str) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    key = (api_key or "").strip()
    if auth == "none" or not key:
        return headers
    if protocol == "anthropic-messages":
        headers["x-api-key"] = key
        headers["anthropic-version"] = ANTHROPIC_VERSION
        return headers
    if protocol == "google-generative-ai":
        headers["x-goog-api-key"] = key
        return headers
    headers["Authorization"] = "Bearer " + key
    return headers


def _preflight(base: str, protocol: str, auth: str, api_key: str) -> Optional[ClassifiedUpstreamError]:
    from backend.core.provider_endpoint import is_console_host

    if protocol not in SUPPORTED_PROTOCOLS:
        return _as_classified(UpstreamErrorType.BAD_ENDPOINT)
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return _as_classified(UpstreamErrorType.BAD_ENDPOINT)
    if parsed.username or parsed.password:
        return _as_classified(UpstreamErrorType.BAD_ENDPOINT)
    if is_console_host(parsed.hostname):
        return _as_classified(UpstreamErrorType.BAD_ENDPOINT)
    if auth == "api_key" and not (api_key or "").strip() and not is_local_url(base):
        return _as_classified(UpstreamErrorType.INVALID_KEY)
    return None


def _looks_like_html(text: str, content_type: str) -> bool:
    from backend.core.provider_endpoint import looks_like_html
    return "text/html" in content_type or looks_like_html(text)


def _classify_http(status: int, text: str, *, models_path: bool) -> ClassifiedUpstreamError:
    classified = classify_upstream_error(status, text)
    if models_path and status == 404:
        return _as_classified(UpstreamErrorType.BAD_ENDPOINT)
    return classified


def _read_json(response: Any) -> tuple[Any, Optional[ClassifiedUpstreamError]]:
    try:
        payload = response.json()
    except (ValueError, TypeError, json.JSONDecodeError):
        return None, _as_classified(UpstreamErrorType.BAD_ENDPOINT)
    if payload is None or isinstance(payload, (str, int, float, bool)):
        return None, _as_classified(UpstreamErrorType.BAD_ENDPOINT)
    return payload, None


def _is_models_page(payload: Any, protocol: str) -> bool:
    """A live page must carry a list (``data``, ``models``, or a top-level array). ``{}`` is invalid."""
    if isinstance(payload, list):
        return True
    if not isinstance(payload, Mapping):
        return False
    if protocol == "google-generative-ai":
        return isinstance(payload.get("models"), list)
    data = payload.get("data")
    if isinstance(data, list):
        return True
    if isinstance(data, Mapping):
        return isinstance(data.get("data") or data.get("models"), list)
    return isinstance(payload.get("models"), list)


def _default_http_get(url: str, *, headers: Mapping[str, str], timeout: float, trust_env: bool) -> Any:
    import httpx
    with httpx.Client(timeout=timeout, trust_env=trust_env, follow_redirects=False) as client:
        return client.get(url, headers=dict(headers))


def _response_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    return ""


def _content_type(response: Any) -> str:
    headers = getattr(response, "headers", None) or {}
    try:
        return str(headers.get("content-type") or "").lower()
    except Exception:
        return ""


def fetch_provider_models(
    *,
    base_url: str,
    api_key: str = "",
    provider: str = "compatible",
    protocol: Optional[str] = None,
    auth: Optional[str] = None,
    http: Optional[HttpGet] = None,
    timeout: float = MODELS_TIMEOUT_SEC,
) -> AccountModelList:
    """GET ``{base}/models`` with protocol headers, pagination, and layered errors."""
    resolved_protocol = resolve_protocol(provider, protocol)
    resolved_auth = resolve_auth(provider, auth)
    host = _host(base_url)
    preflight = _preflight(base_url, resolved_protocol, resolved_auth, api_key)
    if preflight:
        return _failed(preflight, host)

    getter = http or _default_http_get
    headers = _headers(resolved_protocol, api_key, resolved_auth)
    url = _models_url(base_url, resolved_protocol)
    if resolved_protocol == "anthropic-messages":
        url = _with_query(url, limit=ANTHROPIC_PAGE_SIZE)
    elif resolved_protocol == "google-generative-ai":
        url = _with_query(url, pageSize=GEMINI_PAGE_SIZE)
    url = _stamp_provider_query(url, provider)

    collected: list[str] = []
    capabilities: dict[str, str] = {}
    seen: set[str] = set()
    pages = 0
    truncated = False
    previous_cursor: Optional[tuple[str, str]] = None
    deadline = time.monotonic() + timeout
    remaining = timeout
    trust_env = not is_local_url(base_url)

    while pages < MAX_PAGES:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            if not collected:
                return _failed(classify_upstream_error(None, "", error_name="TimeoutError"), host, pages=pages)
            truncated = True
            break
        pages += 1
        try:
            response = getter(url, headers=headers, timeout=min(timeout, remaining), trust_env=trust_env)
        except Exception as exc:
            name = type(exc).__name__
            if not collected:
                from backend.core.upstream_errors import network_kind_of
                return _failed(classify_upstream_error(None, "", error_name=name), host, pages=pages,
                               network_kind=network_kind_of(exc))
            truncated = True
            break

        status = int(getattr(response, "status_code", 0) or 0)
        if status == 429 or 500 <= status <= 599:
            error_type = UpstreamErrorType.RATE_LIMITED if status == 429 else UpstreamErrorType.UPSTREAM_UNAVAILABLE
            return _failed(_as_classified(error_type), host, pages=pages, http_status=status)
        text = _response_text(response)[:4000]
        content_type = _content_type(response)
        if _looks_like_html(text, content_type):
            classified = classify_upstream_error(status, text)
            if classified.error_type is not UpstreamErrorType.BAD_ENDPOINT:
                classified = _as_classified(UpstreamErrorType.BAD_ENDPOINT)
            return _failed(classified, host, pages=pages, http_status=status)
        if status != 200:
            if status >= 400:
                return _failed(_classify_http(status, text, models_path=True), host, pages=pages, http_status=status)
            return _failed(_as_classified(UpstreamErrorType.BAD_ENDPOINT), host, pages=pages, http_status=status)
        payload, parse_error = _read_json(response)
        if parse_error:
            return _failed(parse_error, host, pages=pages)
        if not _is_models_page(payload, resolved_protocol):
            return _failed(_as_classified(UpstreamErrorType.BAD_ENDPOINT), host, pages=pages)

        page_ids, page_caps = _page_models(payload, resolved_protocol, provider)
        for name in page_ids:
            if name in seen:
                continue
            if len(collected) >= MAX_MODELS:
                truncated = True
                break
            seen.add(name)
            collected.append(name)
            if name in page_caps:
                capabilities[name] = page_caps[name]
        if truncated:
            break

        kind, cursor = _next_cursor(payload, resolved_protocol, page_ids=page_ids)
        if not kind:
            break
        if cursor is None:
            return _failed(_as_classified(UpstreamErrorType.BAD_ENDPOINT), host, pages=pages)
        marker = (kind, cursor)
        if marker == previous_cursor:
            return _failed(_as_classified(UpstreamErrorType.BAD_ENDPOINT), host, pages=pages)
        previous_cursor = marker
        if kind == "page_token":
            url = _with_query(_models_url(base_url, resolved_protocol), pageSize=GEMINI_PAGE_SIZE, pageToken=cursor)
        elif kind == "after_id":
            url = _with_query(_models_url(base_url, resolved_protocol), limit=ANTHROPIC_PAGE_SIZE, after_id=cursor)
        else:
            url = _with_query(_models_url(base_url, resolved_protocol), limit=ANTHROPIC_PAGE_SIZE, after=cursor)
        url = _stamp_provider_query(url, provider)

    if pages >= MAX_PAGES and previous_cursor:
        truncated = True

    recommended = recommended_by_purpose(provider, collected)
    from backend.core.provider_presets import get_provider
    preset = get_provider(provider)
    had_candidates = bool(preset and any(preset.candidates.get(purpose) for purpose in _PURPOSES))
    analysis = recommended.get("analysis") or []
    models = backfill_model_ids(collected, analysis)
    return AccountModelList(
        ok=True,
        models=models,
        recommended=recommended,
        truncated=truncated,
        source="live",
        capabilities=capabilities,
        message_key=_message_key(ok=True, truncated=truncated, recommended=recommended, had_candidates=had_candidates),
        base_url_host=host,
        pages=pages,
    )


def list_account_models(
    *,
    base_url: str,
    api_key: str = "",
    provider: str = "compatible",
    protocol: Optional[str] = None,
    auth: Optional[str] = None,
    http: Optional[HttpGet] = None,
) -> AccountModelList:
    """Public entry: fetch, intersect with preset candidates, backfill order."""
    return fetch_provider_models(
        base_url=base_url,
        api_key=api_key,
        provider=provider,
        protocol=protocol,
        auth=auth,
        http=http,
    )


def get_models(
    base: str,
    api_key: str,
    provider: str = "compatible",
    *,
    http: Optional[HttpGet] = None,
) -> tuple[list[str], Optional[ClassifiedUpstreamError], AccountModelList]:
    """Drop-in for settings validation: ``(ids, error, full_result)``."""
    result = list_account_models(base_url=base, api_key=api_key, provider=provider, http=http)
    if not result.ok:
        classified = _as_classified(result.error_type or UpstreamErrorType.UNKNOWN)
        if result.hint_key:
            classified = ClassifiedUpstreamError(
                error_type=classified.error_type,
                retryable=classified.retryable,
                hint_key=result.hint_key,
            )
        return result.models, classified, result
    return result.models, None, result
