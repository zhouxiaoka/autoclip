"""Model token usage per project and stage, so the cost of one video can be measured.

`tracking(project_id)` binds a sink for the current context (one studio run); `stage(name)` names
the step. `llm_manager.call` and the studio vision call record every response into the bound
sink, appended to <project>/metadata/llm_usage.jsonl. Without a sink nothing is recorded.
Providers that do not report tokens get an estimate from characters (`estimated: true`).
"""
from __future__ import annotations

import contextvars
import json
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_sink: contextvars.ContextVar[Path | None] = contextvars.ContextVar('llm_usage_sink', default=None)
_stage: contextvars.ContextVar[str] = contextvars.ContextVar('llm_usage_stage', default='other')
_lock = threading.Lock()
FILE = 'llm_usage.jsonl'


def usage_path(project_id: str) -> Path:
    from backend.core.path_utils import get_project_directory
    return get_project_directory(project_id) / 'metadata' / FILE


@contextmanager
def tracking(project_id: str):
    token = _sink.set(usage_path(project_id))
    try:
        yield
    finally:
        _sink.reset(token)


@contextmanager
def stage(name: str):
    token = _stage.set(name)
    try:
        yield
    finally:
        _stage.reset(token)


def set_stage(name: str) -> None:
    """Name the step for the rest of a sequential run (the pipeline steps)."""
    _stage.set(name)


def _estimate(chars: int) -> int:
    # Mixed Chinese/English transcripts: about 1.5 characters per token on Qwen/GPT tokenizers.
    return round(chars / 1.5)


def record(model: str | None, usage: dict[str, Any] | None, *, prompt_chars: int, completion_chars: int, kind: str = 'text',
           images: int = 0) -> None:
    path = _sink.get()
    if path is None:
        return
    usage = usage or {}
    prompt = usage.get('prompt_tokens', usage.get('input_tokens'))
    completion = usage.get('completion_tokens', usage.get('output_tokens'))
    estimated = prompt is None or completion is None
    row = {'at': round(time.time(), 1), 'stage': _stage.get(), 'kind': kind, 'model': model or '',
           'prompt_tokens': int(prompt) if prompt is not None else _estimate(prompt_chars),
           'completion_tokens': int(completion) if completion is not None else _estimate(completion_chars),
           'prompt_chars': prompt_chars, 'completion_chars': completion_chars, 'images': images, 'estimated': estimated}
    try:
        with _lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + '\n')
    except OSError:
        pass  # accounting never blocks output


def summary(project_id: str) -> dict[str, Any]:
    """Calls and tokens per stage plus totals for one project."""
    stages: dict[str, dict[str, Any]] = {}
    try:
        lines = usage_path(project_id).read_text(encoding='utf-8').splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get('kind') == 'timing':
            continue
        item = stages.setdefault(row.get('stage', 'other'), {'calls': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'estimated_calls': 0})
        item['calls'] += 1
        item['prompt_tokens'] += row.get('prompt_tokens') or 0
        item['completion_tokens'] += row.get('completion_tokens') or 0
        item['estimated_calls'] += bool(row.get('estimated'))
    total = {key: sum(item[key] for item in stages.values()) for key in ('calls', 'prompt_tokens', 'completion_tokens', 'estimated_calls')}
    return {'stages': stages, 'total': total}


def run_in_context(fn):
    """Wrap `fn` so a worker thread records into the caller's sink and stage."""
    context = contextvars.copy_context()
    return lambda *args, **kwargs: context.copy().run(fn, *args, **kwargs)


@contextmanager
def timed(stage_name: str):
    """Record how long a step took (wall seconds) next to its token usage, for cost/time reports."""
    started = time.monotonic()
    try:
        yield
    finally:
        path = _sink.get()
        if path is not None:
            row = {'at': round(time.time(), 1), 'kind': 'timing', 'stage': stage_name, 'seconds': round(time.monotonic() - started, 2)}
            try:
                with _lock:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with path.open('a', encoding='utf-8') as handle:
                        handle.write(json.dumps(row) + '\n')
            except OSError:
                pass


def timings(project_id: str) -> dict[str, float]:
    """Total wall seconds per timed stage of one project."""
    out: dict[str, float] = {}
    try:
        lines = usage_path(project_id).read_text(encoding='utf-8').splitlines()
    except OSError:
        return out
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get('kind') == 'timing':
            out[row['stage']] = round(out.get(row['stage'], 0) + float(row.get('seconds') or 0), 2)
    return out
