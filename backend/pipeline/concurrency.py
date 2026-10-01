"""Run the pipeline's independent per-chunk model calls side by side.

Steps 1–4 call the text model once per transcript chunk. The calls do not depend on each other
and mostly wait on the network, so a small pool cuts a 2 h video's analysis several-fold.
Results keep chunk order. Local models (Ollama, LM Studio …) share this machine: sequential.
`AUTOCLIP_LLM_CONCURRENCY` overrides the pool size (1–8).
"""
from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypeVar

T = TypeVar('T')
CLOUD_WORKERS = 4


def workers() -> int:
    configured = os.getenv('AUTOCLIP_LLM_CONCURRENCY', '').strip()
    if configured:
        try:
            return max(1, min(8, int(configured)))
        except ValueError:
            pass
    try:
        from backend.core.llm_manager import get_llm_manager
        settings = get_llm_manager().settings
        base = str(settings.get('openai_base_url') or '')
        if settings.get('llm_provider_preset') or 'localhost' in base or '127.0.0.1' in base:
            return 1
    except Exception:  # noqa: BLE001 - unknown provider: stay conservative but parallel
        pass
    return CLOUD_WORKERS


def map_chunks(fn: Callable[[Any], T], items: Iterable[Any]) -> list[T]:
    """`[fn(item) for item in items]`, run on a small pool; usage tracking follows each call."""
    items = list(items)
    count = min(workers(), len(items))
    if count <= 1:
        return [fn(item) for item in items]
    from backend.core.llm_usage import run_in_context
    with ThreadPoolExecutor(max_workers=count, thread_name_prefix='llm-chunk') as pool:
        return list(pool.map(run_in_context(fn), items))
