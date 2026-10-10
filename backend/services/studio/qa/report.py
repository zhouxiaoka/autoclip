"""One shadow report. Checkers return a bucket; this module keeps the clock."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from time import monotonic

from backend.core.sentry_setup import capture_studio_exception

logger = logging.getLogger(__name__)

# A render may wait this long in total. One slow checker is skipped, not fatal.
PER_CHECKER_S = 1.0
TOTAL_BUDGET_S = 3.0

CHECKERS = ('avsync', 'face', 'loudness', 'jitter', 'ending')

BUCKETS = frozenset({
    'lt40', '40_80', '80_200', 'gt200',
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


def run_checks(ctx: Context, runners, *, total_s: float = TOTAL_BUDGET_S, per_s: float = PER_CHECKER_S,
               clock=monotonic) -> dict:
    """Run each checker until the budget is gone. A late checker is recorded as skipped."""
    started = clock()
    deadline = started + total_s
    checks = []
    for name, fn in runners:
        now = clock()
        if deadline - now <= 0.02:
            checks.append(_item(name, 'skip', 'budget', 0))
            continue
        limit = min(per_s, max(0.05, deadline - now))
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
