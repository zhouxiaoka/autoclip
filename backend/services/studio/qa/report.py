"""One shadow report. Checkers return a bucket; this module keeps the clock."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from time import monotonic

from backend.core.sentry_setup import capture_studio_exception

logger = logging.getLogger(__name__)

# Loudness reads the whole soundtrack and gets its own 3–5 s. The other checkers stay short.
# The parent process kills the worker at HARD_CAP_S, so this total must finish before that.
PER_CHECKER_S = 1.0
TOTAL_BUDGET_S = 11.5
HARD_CAP_S = 12.0

CHECKERS = ('avsync', 'face', 'loudness', 'jitter', 'ending')

BUCKETS = frozenset({
    'lt40', '40_80', '80_200', 'gt200', 'start_only',
    'none', 'lt10', '10_40', 'gt40',
    'in_target', 'quiet_1_3', 'quiet_gt3', 'loud_1_3', 'loud_gt3', 'peak', 'peak_and_level',
    'calm', 'flash', 'rms', 'flash_and_rms',
    'complete', 'mid_word', 'mid_sentence',
    'timeout', 'budget', 'no_audio', 'no_detector', 'no_words', 'unreadable', 'error',
})


class QaCheckerError(RuntimeError):
    """The checker name only. The original message can hold a path or a caption."""

    def __init__(self, checker: str):
        super().__init__(checker if checker in CHECKERS else 'runner')


@dataclass
class SceneSpan:
    start: float
    end: float
    points: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class Context:
    output: object = None
    source: object = None
    scenes: list[SceneSpan] = field(default_factory=list)
    width: int = 0
    height: int = 0
    strategy_id: str = 'original'
    words: list[dict] | None = None
    captions: bool = False
    title: bool = False
    packaged: bool = False
    title_y: float = 0.12


def _capture(checker: str, error: Exception) -> None:
    logger.warning('QA checker %s failed: %s', checker if checker in CHECKERS else 'runner', type(error).__name__)
    capture_studio_exception(QaCheckerError(checker), 'qa')


def _item(checker: str, outcome: str, bucket: str, duration_ms: int) -> dict:
    if outcome not in ('pass', 'fail', 'skip') or bucket not in BUCKETS:
        outcome, bucket = 'skip', 'error'
    return {
        'checker': checker,
        'outcome': outcome,
        'bucket': bucket,
        'duration_ms': max(0, min(60_000, int(duration_ms))),
    }


def checker_limits(duration_s: float) -> dict[str, float]:
    """Per-checker seconds. Loudness scales with the cut, and never leaves the 3–5 s band."""
    span = duration_s if duration_s > 0 else 1.0
    loud = min(5.0, max(3.0, span * 0.08))
    return {'avsync': 2.5, 'face': 2.0, 'loudness': loud, 'jitter': 2.0, 'ending': 0.4}


def total_budget(limits: dict[str, float]) -> float:
    return min(TOTAL_BUDGET_S, sum(limits.values()) + 0.3)


def skipped_report(bucket: str, duration_ms: int) -> dict:
    """Every checker skipped. Used when the worker is killed or never starts."""
    item_ms = 0 if bucket != 'timeout' else max(0, min(60_000, int(duration_ms)))
    return {
        'schema_version': 1,
        'mode': 'shadow',
        'duration_ms': max(0, min(60_000, int(duration_ms))),
        'checks': [_item(name, 'skip', bucket if bucket in BUCKETS else 'error', item_ms) for name in CHECKERS],
    }


def run_checks(ctx: Context, runners, *, total_s: float = TOTAL_BUDGET_S, per_s: float = PER_CHECKER_S,
               limits: dict | None = None, clock=monotonic) -> dict:
    """Run each checker until the budget is gone. A late checker is recorded as skipped."""
    started = clock()
    deadline = started + total_s
    checks = []
    for name, fn in runners:
        now = clock()
        if deadline - now <= 0.02:
            checks.append(_item(name, 'skip', 'budget', 0))
            continue
        allowance = float((limits or {}).get(name, per_s))
        limit = min(allowance, max(0.05, deadline - now))
        t0 = clock()
        try:
            outcome, bucket = fn(ctx, limit)
        except Exception as error:  # noqa: BLE001 - one checker cannot fail the export
            _capture(name, error)
            outcome, bucket = 'skip', 'error'
        elapsed = clock() - t0
        if outcome != 'skip' and elapsed > limit + 0.05:
            outcome, bucket = 'skip', 'timeout'
        checks.append(_item(name, outcome, bucket, round(elapsed * 1000)))
    return {
        'schema_version': 1,
        'mode': 'shadow',
        'duration_ms': max(0, min(60_000, round((clock() - started) * 1000))),
        'checks': checks,
    }
