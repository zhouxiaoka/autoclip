"""Wall-clock cap for one clip / generation job.

A single provider read may wait 600s and the SDK may retry it once. The manager
can retry that whole attempt again, and a job makes several calls. Without a
cap the Studio screen stays on 「正在制作可发布成片」. This budget is the total
time for one production job. Local Whisper is paused: it is CPU work, not a
slow provider, and a long transcribe must not consume the cap.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

# One read is 600s. 20 minutes covers that read plus its SDK retry, then stops
# the next manager retry instead of stacking hours of 600s waits.
CLIP_JOB_BUDGET_SEC = 20 * 60

_MESSAGE = "这次制作已超过时间上限，已停止。请重试；服务商一直很慢时可以换一个更快的模型。"


class JobDurationExceeded(Exception):
    """The clip/generation job used its wall-clock budget. Not a single-request timeout."""

    def __init__(self) -> None:
        super().__init__(_MESSAGE)


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


def clip_job_budget_seconds() -> float:
    raw = os.getenv("AUTOCLIP_CLIP_JOB_BUDGET_SEC")
    if not raw:
        return float(CLIP_JOB_BUDGET_SEC)
    try:
        value = float(raw)
    except ValueError:
        return float(CLIP_JOB_BUDGET_SEC)
    return value if value > 0 else float(CLIP_JOB_BUDGET_SEC)


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
    limit = clip_job_budget_seconds() if seconds is None else seconds
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
def pause_clip_job_budget() -> Iterator[None]:
    """Freeze the clock. Local Whisper must not spend the provider budget."""
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


def promote_if_budget_spent(error: BaseException) -> None:
    """A transport timeout that lands after the cap is the cap, not another retry."""
    if isinstance(error, JobDurationExceeded) or budget_expired():
        raise JobDurationExceeded() from None
