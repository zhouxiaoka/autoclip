"""Verdict for one report: should-succeed ≥95%, should-block 100% with billable_calls_before_failure=0.

Live suites are fail-closed: any provider failure, missing/empty/unparsable report,
or fewer results than the planned matrix turns the named provider-e2e check RED.
The rolling window is an additional bar once the sample is large enough — it must
not hide a failed provider in an under-sampled run.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.llm_telemetry import sanitize_upstream_error_type
from backend.core.upstream_errors import is_retryable

from . import ROLLING_MIN_SAMPLE, ROLLING_WINDOW_RUNS, SUCCESS_RATE_THRESHOLD
from .library import rolling_window


class VerdictError(ValueError):
    pass


_BROKEN_STATUSES = frozenset({'missing', 'empty', 'unparsable'})


def _cases(report: dict[str, Any], *expects: str) -> list[dict[str, Any]]:
    return [row for row in report.get('cases') or [] if row.get('expect') in expects]


def _injected(row: dict[str, Any]) -> bool:
    return bool(row.get('expected_upstream_error_type')) or row.get('expect') in {
        'service_restarted', 'fault',
    }


def billable_calls_before_failure(row: dict[str, Any]) -> int | None:
    """The row's paid-call count, or None when it is missing or not a non-negative integer (#373: "oops", 0.9,
    True are not counts and never pass as 0)."""
    value = row.get('billable_calls_before_failure')
    if value is None:
        value = row.get('billable_calls')
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


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


def _live_like(report: dict[str, Any]) -> bool:
    if report.get('suite') == 'live':
        return True
    return (
        report.get('suite') == 'combined'
        and bool(report.get('mode') or report.get('case_records') or report.get('planned'))
    )


def pair_key(row: dict[str, Any]) -> tuple[str, str]:
    provider = str(row.get('provider_id') or row.get('provider') or '').strip()
    clip = str(row.get('clip_id') or '').strip()
    if provider and clip:
        return provider, clip
    ident = str(row.get('id') or '')
    if ident.startswith('mock:') or ':' not in ident:
        return provider, clip or ident
    left, right = ident.split(':', 1)
    return left, right


def planned_pairs(report: dict[str, Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in report.get('planned') or []:
        if not isinstance(row, dict):
            continue
        key = pair_key(row)
        if not (key[0] and key[1]) or key in seen:
            continue
        seen.add(key)
        pairs.append(key)
    if pairs:
        return pairs
    mode = report.get('mode')
    if mode in {'nightly', 'prerelease', 'verify', 'api88'}:
        from .matrix import assignments
        week = report.get('iso_week')
        for item in assignments(str(mode), week=None if week is None else int(week)):
            key = (str(item['provider_id']), str(item['clip_id']))
            if key not in seen:
                seen.add(key)
                pairs.append(key)
    return pairs


def completeness(report: dict[str, Any]) -> dict[str, Any]:
    if report.get('status') in {'skipped', 'budget_blocked'} | _BROKEN_STATUSES:
        return {'ok': True, 'missing': [], 'expected_n': 0, 'actual_n': 0}
    expected = planned_pairs(report)
    seen: set[tuple[str, str]] = set()
    for row in report.get('cases') or []:
        key = pair_key(row)
        if key[0] and key[1]:
            seen.add(key)
    missing = [f'{provider}:{clip}' for provider, clip in expected if (provider, clip) not in seen]
    return {
        'ok': not missing,
        'missing': missing,
        'expected_n': len(expected),
        'actual_n': len(seen),
    }


def provider_failure_reasons(report: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in report.get('cases') or []:
        if row.get('aborted') or row.get('passed') is not False:
            continue
        provider, _clip = pair_key(row)
        grouped.setdefault(provider or str(row.get('id') or 'unknown'), []).append(row)
    for provider, rows in grouped.items():
        sample = rows[0]
        error_class = sample.get('error_class') or sample.get('upstream_error_type') or 'unknown'
        status = sample.get('http_status')
        status_bit = f' http_status={status}' if status is not None else ''
        reasons.append(
            f'provider failure: {provider} {len(rows)} case(s) failed '
            f'error_class={error_class}{status_bit}'
        )
    for item in report.get('providers') or []:
        ident = str(item.get('id') or 'unknown')
        try:
            succeed_n = int(item.get('should_succeed_n') or 0)
            succeed_ok = int(item.get('should_succeed_passed') or 0)
            block_n = int(item.get('should_block_n') or 0)
            block_ok = int(item.get('should_block_passed') or 0)
        except (TypeError, ValueError):
            continue
        if succeed_n and succeed_ok < succeed_n:
            reasons.append(f'provider failure: {ident} succeed {succeed_ok}/{succeed_n}')
        if block_n and block_ok < block_n:
            reasons.append(f'provider failure: {ident} block {block_ok}/{block_n}')
    return list(dict.fromkeys(reasons))


def _suite_hint(path: Path) -> str:
    name = path.as_posix().lower()
    if 'live' in name:
        return 'live'
    if 'mock' in name:
        return 'mock'
    return 'unknown'


def load_report_file(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding='utf-8')
    except OSError:
        return {
            'suite': _suite_hint(path),
            'status': 'missing',
            'reason': f'missing report: {path.name}',
            'cases': [],
        }
    if not text.strip():
        return {
            'suite': _suite_hint(path),
            'status': 'empty',
            'reason': f'empty report: {path.name}',
            'cases': [],
        }
    try:
        payload = json.loads(text)
    except ValueError:
        return {
            'suite': _suite_hint(path),
            'status': 'unparsable',
            'reason': f'unparsable report: {path.name}',
            'cases': [],
        }
    if not isinstance(payload, dict):
        return {
            'suite': _suite_hint(path),
            'status': 'unparsable',
            'reason': f'unparsable report: {path.name}',
            'cases': [],
        }
    if payload.get('suite') in {None, ''} and _suite_hint(path) != 'unknown':
        payload = {**payload, 'suite': _suite_hint(path)}
    return payload


def load_reports(paths: list[Path], *, expect_live: bool = False) -> list[dict[str, Any]]:
    reports = [load_report_file(path) for path in paths]
    if expect_live and not any(item.get('suite') == 'live' for item in reports):
        reports.append({
            'suite': 'live',
            'status': 'missing',
            'reason': 'missing live report',
            'cases': [],
        })
    return reports


def judge_suite(report: dict[str, Any], *, library: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if report.get('status') in _BROKEN_STATUSES:
        reason = report.get('reason') or f"{report.get('status')} report"
        return {
            'passed': False,
            'skipped': False,
            'reason': reason,
            'should_succeed_rate': None,
            'should_block_rate': None,
            'reasons': [reason],
        }
    if report.get('status') == 'budget_blocked':
        return {
            'passed': False,
            'skipped': False,
            'reason': report.get('reason') or 'monthly live budget cap reached',
            'should_succeed_rate': None,
            'should_block_rate': None,
            'reasons': [report.get('reason') or 'monthly live budget cap reached'],
        }
    if report.get('status') == 'skipped':
        return {
            'passed': True,
            'skipped': True,
            'reason': report.get('reason') or 'suite skipped',
            'should_succeed_rate': None,
            'should_block_rate': None,
        }
    all_cases = [row for row in report.get('cases') or [] if not row.get('aborted')]
    succeed = [row for row in _cases({'cases': all_cases}, 'succeed') if not _injected(row)]
    blocked = _cases({'cases': all_cases}, 'block')
    faults = [row for row in all_cases if _injected(row)]
    succeed_rate = success_rate(succeed)
    block_ok = all(row.get('passed') for row in blocked) if blocked else True
    # #353: a should-block row passes only with a counted zero; an unknown count (None) is not zero.
    billable_ok = all(billable_calls_before_failure(row) == 0 for row in blocked)
    fault_ok = all(row.get('passed') and _fault_contract_ok(row) for row in faults) if faults else True
    window = report.get('window')
    live_like = _live_like(report)
    if live_like:
        records = list(library or [])
        records.extend(report.get('case_records') or [])
        if window is None:
            window = rolling_window(
                records,
                window_runs=ROLLING_WINDOW_RUNS,
                min_sample=ROLLING_MIN_SAMPLE,
                threshold=SUCCESS_RATE_THRESHOLD,
            )
        succeed_ok = bool(window.get('passed', True))
    else:
        succeed_ok = succeed_rate >= SUCCESS_RATE_THRESHOLD
    complete = completeness(report) if live_like else {'ok': True, 'missing': []}
    failures = provider_failure_reasons(report) if live_like else []
    passed = (
        succeed_ok
        and complete.get('ok', True)
        and not failures
        and block_ok and billable_ok and fault_ok
        and all(row.get('passed') is True or row.get('passed') is False for row in succeed + blocked + faults)
    )
    reasons = []
    if not live_like and succeed and succeed_rate < SUCCESS_RATE_THRESHOLD:
        reasons.append(f'should-succeed {succeed_rate:.1%} < {SUCCESS_RATE_THRESHOLD:.0%}')
    if live_like and window and window.get('enforced') and not window.get('passed'):
        reasons.append(
            f"live rolling-window {window.get('success_rate', 0):.1%} < {SUCCESS_RATE_THRESHOLD:.0%} "
            f"over {window.get('should_succeed_n', 0)} cases"
        )
    if live_like and not complete.get('ok', True):
        missing = ', '.join(complete.get('missing') or []) or 'unknown pairs'
        reasons.append(
            f"incomplete live results: expected {complete.get('expected_n', 0)}, "
            f"got {complete.get('actual_n', 0)}; missing {missing}"
        )
    reasons.extend(failures)
    if blocked and not block_ok:
        reasons.append('should-block case failed')
    if blocked and not billable_ok:
        reasons.append('should-block billable_calls_before_failure != 0')
    if faults and not fault_ok:
        reasons.append('fault injection did not match the expected UpstreamErrorType or outcome')
    history = report.get('history') or window or {}
    history_note = None
    if history.get('note'):
        history_note = history['note']
    elif history.get('available') and history.get('cumulative_success_rate') is not None:
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
        'window': window,
        'completeness': complete,
    }


def judge_reports(
    reports: list[dict[str, Any]],
    *,
    library: list[dict[str, Any]] | None = None,
    expect_live: bool = False,
) -> dict[str, Any]:
    payload = list(reports)
    if expect_live and not any(item and item.get('suite') == 'live' for item in payload):
        payload.append({
            'suite': 'live',
            'status': 'missing',
            'reason': 'missing live report',
            'cases': [],
        })
    suites = [judge_suite(report, library=library) for report in payload if report]
    blocking = [suite for suite in suites if not suite.get('skipped')]
    passed = all(suite['passed'] for suite in blocking) if blocking else False
    if not payload:
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
        'expect_live': expect_live,
    }


def require_pass(
    reports: list[dict[str, Any]],
    *,
    library: list[dict[str, Any]] | None = None,
    expect_live: bool = False,
) -> dict[str, Any]:
    verdict = judge_reports(reports, library=library, expect_live=expect_live)
    if not verdict['passed']:
        raise VerdictError('; '.join(verdict['reasons']) or 'provider-e2e gate failed')
    return verdict
