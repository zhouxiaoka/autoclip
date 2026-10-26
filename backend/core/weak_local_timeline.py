"""Guidance for known-weak local timeline models (#428).

Ollama ``qwen2.5:7b`` and similar small local chat models often return topics
without usable time ranges. This module only decides when to say so. It does
not change prompts, schemas, or retry budgets, and it does not claim those
models can produce a timeline.
"""
from __future__ import annotations

import re

LOCAL_TIMELINE_PROVIDERS = frozenset({"ollama", "lmstudio"})
# Explicit parameter size wins. 7B/8B is the class that fails structured intervals.
_MAX_WEAK_BILLIONS = 8.0
_SIZE = re.compile(r"(?:^|[^0-9a-z])(\d+(?:\.\d+)?)b(?:[^0-9a-z]|$)")
# Small chat names that often omit a ``:7b`` tag. A size token still wins.
_SMALL_ALIASES = ("phi3", "phi-3", "phi4-mini", "phi-4-mini", "tinyllama", "smollm")
_NOT_TIMELINE = ("embed", "whisper", "rerank")

# Substring the Studio failure card uses to offer model settings. Keep it in both hints.
WEAK_LOCAL_TIMELINE_MARKER = "经常无法返回可用的时间线"


def _clean(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def is_known_weak_local_timeline_model(provider, model, base_url=None) -> bool:
    """True for a small local chat model used as the Studio timeline model.

    Cloud providers stay false even when the id looks small. A local 14B/32B
    model stays false: this is not a claim that every local model fails.
    """
    name = _clean(model).lower()
    if not name or any(token in name for token in _NOT_TIMELINE):
        return False
    preset = _clean(provider).lower()
    local = preset in LOCAL_TIMELINE_PROVIDERS
    if not local and preset in {"compatible", "openai", "other"}:
        from backend.core.llm_providers import is_local_url
        local = is_local_url(base_url if isinstance(base_url, str) else None)
    if not local:
        return False
    sizes = [float(match) for match in _SIZE.findall(name)]
    if sizes:
        return sizes[-1] <= _MAX_WEAK_BILLIONS
    return any(alias in name for alias in _SMALL_ALIASES)


def note_weak_local_timeline(report: dict, info) -> None:
    """Stamp the extraction report when this run's model is known-weak and local.

    Provider, model id and base URL stay out of the report. The flag is enough
    for the failure sentence and is safe to keep next to the chunk counts.
    """
    if not isinstance(report, dict) or not isinstance(info, dict):
        return
    if is_known_weak_local_timeline_model(info.get("provider"), info.get("model"), info.get("base_url")):
        report["weak_local_timeline"] = True


def _retries_spent(chunks: list) -> bool:
    """The per-chunk JSON loop finished its budget (first try + two retries)."""
    from backend.core.result_retry import MAX_ATTEMPTS

    replies = [
        chunk for chunk in chunks
        if isinstance(chunk, dict) and chunk.get("source") != "cache"
        and chunk.get("outcome") in {"invalid_response", "no_valid_ranges", "empty_response"}
    ]
    if not replies:
        return False

    def attempts(chunk: dict) -> int:
        try:
            return int(chunk.get("attempts") or 0)
        except (TypeError, ValueError):
            return 0

    return all(attempts(chunk) >= MAX_ATTEMPTS for chunk in replies)


def empty_interval_hint(report: dict, chunks: list) -> str:
    """Hint before the shared 「尚未进入评分」 sentence.

    Cache replay keeps its own next step. A known-weak local model says the
    model often cannot return a timeline and, once the chunk budget is gone,
    that automatic retries already finished. Other models keep the generic hint.
    """
    if any(chunk.get("source") == "cache" for chunk in chunks):
        return "本次回放了项目中的模型缓存，未重新请求模型；请重新导入素材创建新项目再试。"
    if report.get("weak_local_timeline"):
        spent = "，自动重试已经用完" if _retries_spent(chunks) else ""
        return (
            f"这个模型{WEAK_LOCAL_TIMELINE_MARKER}{spent}。"
            "请改用云端模型，或更大、能返回结构化时间区间的模型。"
        )
    return "请换用能稳定返回结构化时间线的模型后重试；本地模型需支持当前字幕长度。"
