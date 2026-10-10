"""Run the five checkers in a child process. Stdin is the payload, stdout is the report.

The parent stores the report and can kill this process group when the hard cap
expires. This module does not write studio.json and does not import the scheduler.
"""
from __future__ import annotations

import json
import sys


def main() -> None:
    from backend.services.studio.qa.record import RUNNERS, context_from_payload
    from backend.services.studio.qa.report import checker_limits, run_checks, total_budget
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise SystemExit(1)
    ctx = context_from_payload(payload)
    raw_limits = payload.get('limits') if isinstance(payload.get('limits'), dict) else {}
    limits = {}
    for name, value in raw_limits.items():
        try:
            limits[name] = float(value)
        except (TypeError, ValueError):
            continue
    if not limits:
        limits = checker_limits(1.0)
    report = run_checks(ctx, RUNNERS, total_s=total_budget(limits), limits=limits)
    json.dump(report, sys.stdout, ensure_ascii=False, allow_nan=False)
    sys.stdout.write('\n')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit(1) from None
