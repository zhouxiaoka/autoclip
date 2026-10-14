"""Verdict for one report: should-succeed ≥95%, should-block 100% with billable_calls_before_failure=0."""
from __future__ import annotations

from typing import Any

from backend.core.llm_telemetry import sanitize_upstream_error_type
from backend.core.upstream_errors import is_retryable

from . import SUCCESS_RATE_THRESHOLD


class VerdictError(ValueError):
    pass


def _cases(report: dict[str, Any], *expects: str) -> list[dict[str, Any]]:
    return [row for row in report.get('cases') or [] if row.get('expect') in expects]


def _injected(row: dict[str, Any]) -> bool:
    return bool(row.get('expected_upstream_error_type')) or row.get('expect') in {
        'service_restarted', 'fault',
    }


def billable_calls_before_failure(row: dict[str, Any]) -> int:
    value = row.get('billable_calls_before_failure')
    if value is None:
        value = row.get('billable_calls')
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def success_rate(cases: list[dict[str, Any]]) -> float:
    if not cases:
        return 1.0
    return sum(1 for row in cases if row.get('passed')) / len(cases)


def _fault_contract_ok(row: dict[str, Any]) -> bool:
    expected = sanitize_upstream_error_type(row.get('expected_upstream_error_type'))
    observed = sanitize_upstream_error_type(
        row.get('upstream_error_type') or row.get('observed_upstream_error_type')
    )
    if row.get('expect') == 'succeed':
        if expected is None or not is_retryable(expected):
            return False
        if observed is not None and observed != expected:
            return False
        return True
    return True


def judge_suite(report: dict[str, Any]) -> dict[str, Any]:
    if report.get('status') == 'skipped':
        return {
            'passed': True,
            'skipped': True,
            'reason': report.get('reason') or 'suite skipped',
            'should_succeed_rate': None,
            'should_block_rate': None,
        }
    all_cases = [row for row in report.get('cases') or []]
    succeed = [row for row in _cases(report, 'succeed') if not _injected(row)]
    blocked = _cases(report, 'block')
    faults = [row for row in all_cases if _injected(row)]
    succeed_rate = success_rate(succeed)
    block_ok = all(row.get('passed') for row in blocked) if blocked else True
    billable_ok = all(billable_calls_before_failure(row) == 0 for row in blocked)
    fault_ok = all(row.get('passed') and _fault_contract_ok(row) for row in faults) if faults else True
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
        reasons.append('should-block billable_calls_before_failure != 0')
    if faults and not fault_ok:
        reasons.append('fault injection did not match the expected UpstreamErrorType or outcome')
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
