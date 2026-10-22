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
from typing import Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

_lock = threading.Lock()
# (provider, host, key digest, saved model) -> substitute id
_remembered: dict[tuple[str, str, str, str], str] = {}


def clear_remembered_models() -> None:
    with _lock:
        _remembered.clear()


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


def remembered_model(provider: str, base_url: str, api_key: str, saved_model: str) -> Optional[str]:
    saved = (saved_model or "").strip()
    with _lock:
        found = _remembered.get(_slot(provider, base_url, api_key, saved))
    if found and found != saved:
        return found
    return None


def remember_model(provider: str, base_url: str, api_key: str, saved_model: str, substitute: str) -> None:
    saved = (saved_model or "").strip()
    alt = (substitute or "").strip()
    if not saved or not alt or alt == saved:
        return
    with _lock:
        _remembered[_slot(provider, base_url, api_key, saved)] = alt


def _listed_vision_ready(name: str, capabilities: Optional[Mapping[str, str]]) -> bool:
    """Vision/Omni tags add vision. A Text tag never vetoes the name heuristic."""
    from backend.core.model_catalog import is_image_model, is_non_chat_family, supports_vision

    if is_image_model(name) or is_non_chat_family(name):
        return False
    listed = (capabilities or {}).get(name)
    if listed == "multimodal":
        return True
    return supports_vision(name)


def pick_available_vision_model(
    provider: str,
    live_ids: Sequence[str],
    *,
    exclude: Sequence[str] = (),
    capabilities: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """First live vision model. Preset vision order, then the account list order.

    Preset ids are only an ordering hint among ids the account still lists.
    A Vision/Omni tag marks that id ready. A Text tag does not remove it.
    """
    from backend.core.provider_model_fetch import recommended_by_purpose

    skipped = {(name or "").strip() for name in exclude if (name or "").strip()}
    live = [name for name in live_ids if name and name not in skipped]
    recommended = recommended_by_purpose(provider, live).get("vision") or []
    for name in recommended:
        if _listed_vision_ready(name, capabilities):
            return name
    for name in live:
        if _listed_vision_ready(name, capabilities):
            return name
    return None


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
    from backend.core.provider_model_fetch import list_account_models

    try:
        listed = list_account_models(
            base_url=base_url,
            api_key=api_key,
            provider=provider or "compatible",
            http=http,
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
