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

# The only user-facing sentence for this failure. No topic counts, no retry essay.
WEAK_LOCAL_TIMELINE_REASON = "当前本地模型无法返回可用时间线"


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


def empty_interval_hint(report: dict, chunks: list) -> str:
    """Hint before the shared 「尚未进入评分」 sentence.

    A known-weak local model does not use this hint: the failure is the one
    short sentence in ``failures.timeline_failure_from_report``. Cache replay
    and every other model keep their existing next step.
    """
    if any(isinstance(chunk, dict) and chunk.get("source") == "cache" for chunk in chunks):
        return "本次回放了项目中的模型缓存，未重新请求模型；请重新导入素材创建新项目再试。"
    return "请换用能稳定返回结构化时间线的模型后重试；本地模型需支持当前字幕长度。"
