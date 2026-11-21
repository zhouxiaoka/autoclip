"""Substitute a model id the provider no longer offers.

The account's live ``/models`` list is the source of truth. Preset candidates
are only an ordering hint. A substitute is remembered for this process so the
next call does not repeat the same 404. Nothing is written to settings.

Logs name model ids only. Keys, URLs, and response bodies are never logged.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from typing import Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

_lock = threading.Lock()
# (purpose, provider, host, key digest, saved model) -> substitute id
_remembered: dict[tuple[str, str, str, str, str], str] = {}
# purpose + saved id -> {purpose, saved_model, replacement}. Model ids only.
_notices: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
# Successful account lists, 60s. A timeout is not stored.
_LIST_TTL_S = 60.0
_lists: dict[tuple[str, str, str], tuple[float, object]] = {}


def clear_remembered_models() -> None:
    with _lock:
        _remembered.clear()
        _notices.clear()
        _lists.clear()


def _digest(api_key: str) -> str:
    return hashlib.sha256((api_key or "").encode()).hexdigest()[:16]


def _host(base_url: str) -> str:
    from backend.core.llm_telemetry import hostname_of_base_url
    return hostname_of_base_url(base_url) or ""


def provider_for_endpoint(config: Mapping) -> str:
    """Catalog slug for the endpoint actually being called. ``compatible`` if unknown."""
    identity = config.get("identity")
    if isinstance(identity, Mapping):
        provider = str(identity.get("provider") or "").strip().lower()
        if provider and provider != "other":
            return provider
    from backend.core.llm_providers import is_dashscope_endpoint
    if is_dashscope_endpoint(str(config.get("base_url") or "")):
        return "dashscope"
    return "compatible"


def _slot(provider: str, base_url: str, api_key: str, saved_model: str) -> tuple[str, str, str, str]:
    return (
        (provider or "compatible").strip().lower(),
        _host(base_url),
        _digest(api_key),
        (saved_model or "").strip(),
    )


def remembered_model(provider: str, base_url: str, api_key: str, saved_model: str, *, purpose: str = "vision") -> Optional[str]:
    saved = (saved_model or "").strip()
    with _lock:
        found = _remembered.get((purpose, *_slot(provider, base_url, api_key, saved)))
    if found and found != saved:
        return found
    return None


def remember_model(
    provider: str, base_url: str, api_key: str, saved_model: str, substitute: str, *, purpose: str = "",
) -> None:
    saved = (saved_model or "").strip()
    alt = (substitute or "").strip()
    if not saved or not alt or alt == saved:
        return
    with _lock:
        _remembered[(purpose or "vision", *_slot(provider, base_url, api_key, saved))] = alt
        if purpose in {"analysis", "vision", "ocr"}:
            _notices[(purpose, *_slot(provider, base_url, api_key, saved))] = {
                "purpose": purpose, "saved_model": saved, "replacement": alt,
            }


def substitution_notice(purpose: str, provider: str, base_url: str, api_key: str, saved_model: str):
    """Only show a substitution observed for the selected account and purpose."""
    with _lock:
        notice = _notices.get((purpose, *_slot(provider, base_url, api_key, saved_model)))
        return dict(notice) if notice else None


def _cached_account_list(*, base_url: str, api_key: str, provider: str, http):
    """One successful ``/models`` read per account for a minute. Failures are not cached."""
    from backend.core.provider_model_fetch import list_account_models

    key = (
        (provider or "compatible").strip().lower(),
        _host(base_url),
        _digest(api_key),
    )
    now = time.monotonic()
    with _lock:
        hit = _lists.get(key)
        if hit is not None and now - hit[0] < _LIST_TTL_S:
            return hit[1]
    listed = list_account_models(
        base_url=base_url,
        api_key=api_key,
        provider=provider or "compatible",
        http=http,
    )
    if getattr(listed, "ok", False):
        with _lock:
            _lists[key] = (time.monotonic(), listed)
    return listed


def _pick_listed_model(provider, live_ids, exclude, capabilities, purpose):
    from backend.core.model_catalog import is_image_model, is_non_chat_family
    from backend.core.model_registry import listed_chat_capabilities
    from backend.core.provider_model_fetch import recommended_by_purpose

    skipped = set(exclude)
    live = [name for name in live_ids if name and name not in skipped and not is_image_model(name)
            and not is_non_chat_family(name)]
    evidence = dict(capabilities or {})
    missing = [name for name in live if name not in evidence]
    if missing:
        evidence.update(listed_chat_capabilities(provider, missing))
    preferred = recommended_by_purpose(provider, live).get(purpose) or []
    allowed = {'multimodal'} if purpose == 'vision' else {'multimodal', 'text', 'chat'}
    return next((name for name in (*preferred, *live) if evidence.get(name) in allowed), None)


def pick_available_analysis_model(
    provider: str,
    live_ids: Sequence[str],
    *,
    exclude: Sequence[str] = (),
    capabilities: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    return _pick_listed_model(provider, live_ids, exclude, capabilities, "analysis")


def analysis_catalog(*, identity: Optional[Mapping] = None, base_url: str = "", named: Sequence[str] = ()) -> str:
    """Catalog slug for a text call. Identity wins; otherwise a named preset on this route.

    ``API_MODEL_NAME`` jobs have no saved connection identity. The cloud preset
    (or the provider the route already resolved) still selects analysis candidates.
    """
    slug = provider_for_endpoint({"identity": identity or {}, "base_url": base_url})
    if slug != "compatible":
        return slug
    from backend.core.provider_presets import get_provider
    for raw in named:
        name = str(raw or "").strip().lower()
        if name and name != "other" and get_provider(name):
            return name
    return slug


def resolve_available_analysis_model(
    *,
    base_url: str,
    api_key: str,
    provider: str,
    failed_model: str,
    exclude: Sequence[str] = (),
    http=None,
) -> Optional[str]:
    """One live-list lookup for a text call. ``None`` when no other chat model is listed."""
    from backend.core.llm_telemetry import sanitize_model

    try:
        listed = _cached_account_list(
            base_url=base_url, api_key=api_key, provider=provider, http=http,
        )
    except Exception:  # noqa: BLE001 — a list failure must not replace the original model error
        logger.info("text model list unavailable; not substituting")
        return None
    if not listed.ok:
        logger.info("text model list unavailable (%s)", listed.error_type or "unknown")
        return None
    alt = pick_available_analysis_model(
        provider,
        listed.models,
        exclude=(*(exclude or ()), failed_model),
        capabilities=listed.capabilities,
    )
    if not alt:
        return None
    logger.info(
        "text model %s is not offered; using %s from the account list",
        sanitize_model(failed_model) or "model",
        sanitize_model(alt) or "model",
    )
    return alt


def pick_available_vision_model(
    provider: str,
    live_ids: Sequence[str],
    *,
    exclude: Sequence[str] = (),
    capabilities: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    return _pick_listed_model(provider, live_ids, exclude, capabilities, "vision")


def resolve_available_model(
    *,
    base_url: str,
    api_key: str,
    provider: str,
    failed_model: str,
    exclude: Sequence[str] = (),
    http=None,
) -> Optional[str]:
    """One live-list lookup. ``None`` when the list cannot be read or has no other vision model."""
    from backend.core.llm_telemetry import sanitize_model

    try:
        listed = _cached_account_list(
            base_url=base_url, api_key=api_key, provider=provider, http=http,
        )
    except Exception:  # noqa: BLE001 — a list failure must not replace the original model error
        logger.info("vision model list unavailable; not substituting")
        return None
    if not listed.ok:
        logger.info("vision model list unavailable (%s)", listed.error_type or "unknown")
        return None
    alt = pick_available_vision_model(
        provider,
        listed.models,
        exclude=(*(exclude or ()), failed_model),
        capabilities=listed.capabilities,
    )
    if not alt:
        return None
    logger.info(
        "vision model %s is not offered; using %s from the account list",
        sanitize_model(failed_model) or "model",
        sanitize_model(alt) or "model",
    )
    return alt
