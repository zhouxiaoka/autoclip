"""Same-provider preset candidate fallback (1.5.8 R1).

Thin helpers for ``LLMManager.call_with_retry``. Classification stays in
``upstream_errors``. This module does not persist settings, does not switch
providers, and does not emit telemetry fields.
"""
from __future__ import annotations

import contextvars
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping, Optional

from backend.core.upstream_errors import http_error_parts

CHUNK_CALL_CAP = 6
MAX_CANDIDATES = 3
MODEL_SOURCE_PRESET = "preset"
MODEL_SOURCE_USER = "user"

# Q1: fixed rank, no latency probing. ``recommended`` is the catalog name for sponsors.
GROUP_ORDER = ("sponsor", "popular", "other")
_GROUP_RANK = {
    "sponsor": 0,
    "recommended": 0,
    "popular": 1,
    "cloud": 1,
    "other": 2,
    "more": 2,
    "local": 2,
    "compatible": 2,
}

# Q15: only these frequency codes degrade. Quota codes never do.
FREQUENCY_LIMIT_CODES = frozenset({
    "limit_requests",
    "rate_limit_exceeded",
})
QUOTA_CODES = frozenset({
    "insufficient_quota", "insufficient_user_quota", "insufficient_balance",
    "billing_not_active", "billing_quota_exceeded", "quota_exceeded",
    "allocationquota", "allocationquota_freetieronly", "throttling_allocationquota",
})

# First-party fallback when P12's loader is not on this branch. Same-provider only.
PROVIDER_GROUPS: dict[str, str] = {
    "api88": "sponsor",
    "infistar": "sponsor",
    "dashscope": "popular",
    "openai": "popular",
    "gemini": "popular",
    "deepseek": "popular",
    "seed": "popular",
    "kimi": "popular",
    "glm": "popular",
    "grok": "popular",
    "siliconflow": "popular",
}
FALLBACK_CANDIDATES: dict[str, tuple[str, ...]] = {
    "dashscope": ("qwen3.8-flash", "qwen3.8-max", "qwen-vl-plus", "qwen-plus"),
    "openai": ("gpt-5-mini", "gpt-4o-mini"),
    "gemini": ("gemini-3.8-flash", "gemini-2.5-flash"),
    "deepseek": ("deepseek-flash",),
    "seed": ("doubao-seed-2-1-lite-260915",),
    "kimi": ("kimi-k2.6", "kimi-k3"),
    "glm": ("glm-5.3",),
    "grok": ("grok-4.6",),
}

_TOKEN = re.compile(r"[\s.\-]+")


@dataclass
class _ChunkBudget:
    used: int = 0
    last_error: BaseException | None = None


_chunk_budget: contextvars.ContextVar[_ChunkBudget | None] = contextvars.ContextVar(
    "llm_chunk_call_budget", default=None,
)


def resolve_model_source(settings: Mapping[str, Any] | None, assignment: Any = None) -> str:
    """P3 field. Missing / unknown → ``user`` so hand-picked and old files never degrade."""
    for raw in (
        getattr(assignment, "model_source", None),
        getattr(assignment, "source", None),
        (settings or {}).get("model_source"),
        (settings or {}).get("source"),
    ):
        if isinstance(raw, str) and raw.strip().lower() in {MODEL_SOURCE_PRESET, MODEL_SOURCE_USER}:
            return raw.strip().lower()
    return MODEL_SOURCE_USER


def routing_provider_id(settings: Mapping[str, Any] | None) -> str:
    data = settings or {}
    for key in ("connection_provider", "cloud_preset", "llm_provider_preset", "llm_provider"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return ""


def provider_group(provider: str) -> str:
    key = (provider or "").strip().lower()
    try:
        from backend.core.provider_presets import get_provider
        preset = get_provider(key)
        if preset is not None:
            return _canonical_group(preset.group)
    except ImportError:
        pass
    return _canonical_group(PROVIDER_GROUPS.get(key, "other"))


def _canonical_group(group: str | None) -> str:
    rank = _GROUP_RANK.get((group or "").strip().lower())
    if rank == 0:
        return "sponsor"
    if rank == 1:
        return "popular"
    return "other"


def order_candidates(entries: Iterable[tuple[str, str]]) -> list[str]:
    """Stable sort: sponsor → popular → other. No latency field is consulted."""
    decorated: list[tuple[int, int, str]] = []
    for index, (name, group) in enumerate(entries):
        model = (name or "").strip()
        if not model:
            continue
        decorated.append((_GROUP_RANK.get((group or "").strip().lower(), 2), index, model))
    seen: set[str] = set()
    ordered: list[str] = []
    for _rank, _index, model in sorted(decorated, key=lambda item: (item[0], item[1])):
        if model in seen:
            continue
        seen.add(model)
        ordered.append(model)
    return ordered


def catalog_candidates(provider: str, purpose: str = "analysis") -> tuple[str, ...]:
    key = (provider or "").strip().lower()
    if not key:
        return ()
    try:
        from backend.core.provider_presets import candidates_for
        found = candidates_for(key, purpose)
        if found:
            return tuple(item.strip() for item in found if isinstance(item, str) and item.strip())
    except ImportError:
        pass
    return FALLBACK_CANDIDATES.get(key, ())


def same_provider_candidates(
    provider: str,
    current: str | None,
    *,
    purpose: str = "analysis",
) -> tuple[str, ...]:
    """Current model first, then the rest of this provider's list. Never another provider."""
    current_name = (current or "").strip()
    catalog = catalog_candidates(provider, purpose)
    group = provider_group(provider)
    rest = order_candidates((name, group) for name in catalog if name != current_name)
    if current_name:
        names = [current_name, *rest]
    else:
        names = rest
    return tuple(names[:MAX_CANDIDATES])


def candidates_for_call(settings: Mapping[str, Any] | None, assignment: Any = None) -> tuple[str | None, ...]:
    data = settings or {}
    current = (data.get("model_name") or "").strip() or None
    if resolve_model_source(data, assignment) != MODEL_SOURCE_PRESET:
        return (current,)
    provider = routing_provider_id(data)
    found = same_provider_candidates(provider, current)
    return found if found else (current,)


def should_degrade_to_next(error: BaseException) -> bool:
    """True only for frequency limits. Quota / other types stay on the chosen model."""
    tokens = error_code_tokens(error)
    if tokens & QUOTA_CODES:
        return False
    if tokens & FREQUENCY_LIMIT_CODES:
        return True
    return False


def error_code_tokens(error: BaseException) -> frozenset[str]:
    tokens: set[str] = set()
    raw = getattr(error, "code", None)
    if isinstance(raw, str) and not str(raw).isdigit():
        tokens.add(_norm_token(raw))
    _status, body = http_error_parts(error)
    tokens.update(_walk_codes(body))
    return frozenset(token for token in tokens if token)


def _walk_codes(body: Any) -> set[str]:
    tokens: set[str] = set()
    if not isinstance(body, dict):
        return tokens
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    for raw in (
        body.get("code"), body.get("type"), body.get("reason"),
        error.get("code"), error.get("type"), error.get("reason"),
    ):
        if isinstance(raw, str) and raw.strip() and not raw.strip().isdigit():
            tokens.add(_norm_token(raw))
    return tokens


def _norm_token(value: str) -> str:
    return _TOKEN.sub("_", (value or "").strip().lower()).strip("_")


@contextmanager
def chunk_call_budget() -> Iterator[_ChunkBudget]:
    budget = _ChunkBudget()
    token = _chunk_budget.set(budget)
    try:
        yield budget
    finally:
        _chunk_budget.reset(token)


def consume_chunk_call() -> bool:
    """Count one billed ``call()``. ``True`` = allowed. No active budget → unlimited."""
    budget = _chunk_budget.get()
    if budget is None:
        return True
    if budget.used >= CHUNK_CALL_CAP:
        return False
    budget.used += 1
    return True


def remember_chunk_error(error: BaseException) -> None:
    budget = _chunk_budget.get()
    if budget is not None:
        budget.last_error = error


def chunk_calls_used() -> int:
    budget = _chunk_budget.get()
    return 0 if budget is None else budget.used


def chunk_last_error() -> Optional[BaseException]:
    budget = _chunk_budget.get()
    return None if budget is None else budget.last_error
