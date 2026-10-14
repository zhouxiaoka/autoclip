"""Verdict for one report: should-succeed ≥95%, should-block 100% with 0 billable calls."""
from __future__ import annotations

from typing import Any

from . import SUCCESS_RATE_THRESHOLD


class VerdictError(ValueError):
    pass


def _cases(report: dict[str, Any], *expects: str) -> list[dict[str, Any]]:
    return [row for row in report.get('cases') or [] if row.get('expect') in expects]


def success_rate(cases: list[dict[str, Any]]) -> float:
    if not cases:
        return 1.0
    return sum(1 for row in cases if row.get('passed')) / len(cases)


def judge_suite(report: dict[str, Any]) -> dict[str, Any]:
    if report.get('status') == 'skipped':
        return {
            'passed': True,
            'skipped': True,
            'reason': report.get('reason') or 'suite skipped',
            'should_succeed_rate': None,
            'should_block_rate': None,
        }
    succeed = _cases(report, 'succeed')
    blocked = _cases(report, 'block')
    faults = _cases(report, 'service_restarted', 'fault')
    # Fault cases that expect a successful pipeline after injection use expect=succeed
    # and already sit in `succeed`. Kill uses expect=service_restarted.
    succeed_rate = success_rate(succeed)
    block_ok = all(row.get('passed') for row in blocked) if blocked else True
    billable_ok = all((row.get('billable_calls') or 0) == 0 for row in blocked)
    fault_ok = all(row.get('passed') for row in faults) if faults else True
    passed = (
        succeed_rate >= SUCCESS_RATE_THRESHOLD
        and block_ok and billable_ok and fault_ok
        and all(row.get('passed') is True or row.get('passed') is False for row in succeed + blocked + faults)
    )
    reasons = []
    if succeed and succeed_rate < SUCCESS_RATE_THRESHOLD:
        reasons.append(f'should-succeed {succeed_rate:.1%} < {SUCCESS_RATE_THRESHOLD:.0%}')
    if blocked and not block_ok:
        reasons.append('should-block case failed')
    if blocked and not billable_ok:
        reasons.append('should-block made a billable call')
    if faults and not fault_ok:
        reasons.append('fault injection did not match the expected outcome')
    history = report.get('history') or {}
    history_note = None
    if history.get('available') and history.get('cumulative_success_rate') is not None:
        if history['cumulative_success_rate'] < SUCCESS_RATE_THRESHOLD:
            history_note = (
                f"recent-7 cumulative {history['cumulative_success_rate']:.1%} < {SUCCESS_RATE_THRESHOLD:.0%} "
                '(informational until nightly history is retained)'
            )
    return {
        'passed': passed,
        'skipped': False,
        'should_succeed_rate': succeed_rate,
        'should_succeed_n': len(succeed),
        'should_block_n': len(blocked),
        'should_block_passed': block_ok and billable_ok,
        'fault_n': len(faults),
        'fault_passed': fault_ok,
        'reasons': reasons,
        'history_note': history_note,
    }


def judge_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    suites = [judge_suite(report) for report in reports if report]
    blocking = [suite for suite in suites if not suite.get('skipped')]
    passed = all(suite['passed'] for suite in blocking) if blocking else False
    if not reports:
        passed = False
        reasons = ['no reports']
    else:
        reasons = [reason for suite in blocking for reason in suite.get('reasons') or []]
        if not blocking and all(suite.get('skipped') for suite in suites):
            passed = False
            reasons = ['every suite was skipped']
    return {
        'passed': passed,
        'suites': suites,
        'reasons': reasons,
    }


def require_pass(reports: list[dict[str, Any]]) -> dict[str, Any]:
    verdict = judge_reports(reports)
    if not verdict['passed']:
        raise VerdictError('; '.join(verdict['reasons']) or 'provider-e2e gate failed')
    return verdict
