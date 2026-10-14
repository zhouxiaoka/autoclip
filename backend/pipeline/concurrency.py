"""Run the pipeline's independent per-chunk model calls side by side.

Steps 1–4 call the text model once per transcript chunk. The calls do not depend on each other
and mostly wait on the network, so a small pool cuts a 2 h video's analysis several-fold.
Results keep chunk order. Local models (Ollama, LM Studio …) share this machine: sequential.
`AUTOCLIP_LLM_CONCURRENCY` overrides the pool size (1–8).

A process-wide limiter halves itself after a 429 so later chunks (and later steps) back off
together. One chunk raising does not cancel its siblings: every submitted item finishes, then
the first error is re-raised.
"""
from __future__ import annotations

import os
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, TypeVar

T = TypeVar('T')
CLOUD_WORKERS = 4

_lock = threading.Condition()
_limit: int | None = None
_in_use = 0


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


def effective_workers() -> int:
    configured = workers()
    with _lock:
        if _limit is None:
            return configured
        return max(1, min(configured, _limit))


def note_rate_limited() -> None:
    """Halve in-flight concurrency after a 429, never below 1."""
    configured = workers()
    with _lock:
        global _limit
        current = _limit if _limit is not None else configured
        _limit = max(1, current // 2)
        _lock.notify_all()


def reset_limiter() -> None:
    """Call at the start of a project so a previous 429 does not starve the next run."""
    global _limit
    with _lock:
        _limit = None
        _lock.notify_all()


def _acquire() -> None:
    global _in_use
    configured = workers()
    with _lock:
        while True:
            allowed = configured if _limit is None else max(1, min(configured, _limit))
            if _in_use < allowed:
                _in_use += 1
                return
            _lock.wait()


def _release() -> None:
    global _in_use
    with _lock:
        _in_use = max(0, _in_use - 1)
        _lock.notify_all()


def map_chunks(fn: Callable[[Any], T], items: Iterable[Any]) -> list[T]:
    """`[fn(item) for item in items]`, run on a small pool; usage tracking follows each call."""
    items = list(items)
    count = min(effective_workers(), len(items))
    if count <= 1:
        return [fn(item) for item in items]
    from backend.core.llm_usage import run_in_context
    wrapped = run_in_context(fn)
    results: list[T | None] = [None] * len(items)
    errors: list[BaseException | None] = [None] * len(items)

    def run(index: int, item: Any) -> None:
        _acquire()
        try:
            results[index] = wrapped(item)
        except Exception as error:  # noqa: BLE001 - wait for siblings, then re-raise
            errors[index] = error
        finally:
            _release()

    with ThreadPoolExecutor(max_workers=count, thread_name_prefix='llm-chunk') as pool:
        pending = [pool.submit(run, index, item) for index, item in enumerate(items)]
        wait(pending, return_when=ALL_COMPLETED)
    first = next((error for error in errors if error is not None), None)
    if first is not None:
        raise first
    return [item for item in results]  # type: ignore[misc]
