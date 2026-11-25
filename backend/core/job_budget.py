"""Wall-clock cap for one clip / generation job.

A single provider read may wait 600s and the SDK may retry it once. The manager
can retry that whole attempt again, and a job makes several calls. Without a
cap the Studio screen stays on 「正在制作可发布成片」. One production tracked
job and one render tracked job each get this budget, so boundaries, burned
captions, post copy, packaging and render model calls share it with the content
pipeline. Local Whisper and ffmpeg / HTML template encode are paused: they are
CPU work, not a slow provider, and must not consume the cap. Whisper's
own wall-clock cap lives in ``speech_recognizer`` (C2), not in a second
ContextVar here.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

from backend.core.failure_codes import sentence

# One read is 600s. 20 minutes covers that read plus its SDK retry, then stops
# the next manager retry instead of stacking hours of 600s waits.
CLIP_JOB_BUDGET_SEC = 20 * 60
# Local models (Ollama / LM Studio) have ~15m p50 on consumer Windows GPUs/CPUs;
# give them a wider wall-clock cap so healthy local runs are not cut short mid-analysis.
LOCAL_CLIP_JOB_BUDGET_SEC = 45 * 60


class JobDurationExceeded(Exception):
    """The clip/generation job used its wall-clock budget. Not a single-request timeout."""

    def __init__(self) -> None:
        super().__init__(sentence("job_budget"))


class _Budget:
    def __init__(self, seconds: float, started: float) -> None:
        self.seconds = seconds
        self.started = started
        self.paused_at: Optional[float] = None
        self.pause_depth = 0

    def remaining(self) -> float:
        end = self.paused_at if self.paused_at is not None else time.monotonic()
        return self.seconds - (end - self.started)


_current: ContextVar[Optional[_Budget]] = ContextVar("autoclip_clip_job_budget", default=None)


def _is_local_analysis_provider() -> bool:
    try:
        from backend.core.llm_providers import is_local_url
        from backend.services import ai_model_settings as ai
        settings = ai.load()
        binding = getattr(settings, "analysis", None)
        if binding and getattr(binding, "connection_id", None):
            conn = next((c for c in (getattr(settings, "connections", None) or ()) if getattr(c, "id", None) == binding.connection_id), None)
            if conn is not None:
                provider = (getattr(conn, "provider", None) or "").strip().lower()
                if provider in {"ollama", "lmstudio"}:
                    return True
                return is_local_url(getattr(conn, "base_url", None) or "")
    except Exception:  # noqa: BLE001
        pass
    try:
        from backend.core.llm_manager import get_llm_manager
        from backend.core.local_presets import is_local_model
        return bool(is_local_model(get_llm_manager().settings))
    except Exception:  # noqa: BLE001
        return False


def clip_job_budget_seconds(*, local: bool = False) -> float:
    default = float(LOCAL_CLIP_JOB_BUDGET_SEC if local else CLIP_JOB_BUDGET_SEC)
    env_names = ("AUTOCLIP_LOCAL_CLIP_JOB_BUDGET_SEC", "AUTOCLIP_CLIP_JOB_BUDGET_SEC") if local else ("AUTOCLIP_CLIP_JOB_BUDGET_SEC",)
    for name in env_names:
        raw = os.getenv(name)
        if not raw:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if value > 0:
            return value
    return default


def clip_job_active() -> bool:
    return _current.get() is not None


def budget_expired() -> bool:
    budget = _current.get()
    return budget is not None and budget.remaining() <= 0


def ensure_clip_job_budget() -> None:
    """Raise when this job has already used its wall-clock budget. No-op outside a job."""
    if budget_expired():
        raise JobDurationExceeded()


def clip_job_read_timeout(default: float) -> float:
    """Shorten one provider read so it cannot run past the budget. Unchanged outside a job."""
    budget = _current.get()
    if budget is None or budget.pause_depth:
        return default
    left = budget.remaining()
    if left <= 0:
        raise JobDurationExceeded()
    return min(float(default), left)


def bind_clip_job(seconds: Optional[float] = None):
    """Start the budget if this task does not already have one. Nested binds are no-ops."""
    if _current.get() is not None:
        return None
    limit = clip_job_budget_seconds(local=_is_local_analysis_provider()) if seconds is None else seconds
    return _current.set(_Budget(float(limit), time.monotonic()))


def unbind_clip_job(token) -> None:
    if token is not None:
        _current.reset(token)


@contextmanager
def bound_clip_job(seconds: Optional[float] = None) -> Iterator[None]:
    token = bind_clip_job(seconds)
    try:
        yield
    finally:
        unbind_clip_job(token)


@contextmanager
def clip_step_budget(seconds: float, *, reserve_seconds: float = 0) -> Iterator[None]:
    """A tighter deadline for an optional step, without resetting the parent clock.

    Stream readers/watchdogs inherit this deadline. After the context restores
    the job budget, callers must check it before treating a step timeout as a
    fallback: expiration of the whole job is still terminal.
    """
    ensure_clip_job_budget()
    parent = _current.get()
    limit = min(float(seconds), max(0, parent.remaining() - reserve_seconds)) if parent is not None else float(seconds)
    token = _current.set(_Budget(limit, time.monotonic()))
    try:
        yield
    finally:
        _current.reset(token)


@contextmanager
def pause_clip_job_budget() -> Iterator[None]:
    """Freeze the provider/clip-job clock.

    Time inside this block does not consume the production or render budget.
    Local Whisper's own wall-clock cap lives in ``speech_recognizer`` (C2):
    about 3× the audio duration, or ``config.timeout`` when that is set.
    Model download uses this pause (so it still does not spend the provider
    budget) but is not on that Whisper transcribe clock.
    """
    budget = _current.get()
    if budget is None:
        yield
        return
    outermost = budget.pause_depth == 0
    if outermost:
        budget.paused_at = time.monotonic()
    budget.pause_depth += 1
    try:
        yield
    finally:
        budget.pause_depth -= 1
        if outermost:
            budget.started += time.monotonic() - (budget.paused_at or time.monotonic())
            budget.paused_at = None


@contextmanager
def suspend_clip_job_budget() -> Iterator[None]:
    """Hide the budget while a failure is written down.

    ``store.change`` stops a job that has already used its cap. The write that
    records that stop has to run with the cap out of the way, then the cap
    comes back for whoever bound it.
    """
    token = _current.set(None)
    try:
        yield
    finally:
        _current.reset(token)


def promote_if_budget_spent(error: BaseException) -> None:
    """A transport timeout that lands after the cap is the cap, not another retry."""
    if isinstance(error, JobDurationExceeded) or budget_expired():
        raise JobDurationExceeded() from None
