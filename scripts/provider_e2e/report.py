"""Write the e2e summary artifact (JSON + Markdown). No secrets."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION, SUCCESS_RATE_THRESHOLD
from .judge import judge_suite
from .mask import redact


def write_report(path: Path, report: dict[str, Any], extras: list[str] | None = None) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = redact({**report, 'schema_version': SCHEMA_VERSION}, extras)
    path.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    markdown = path.with_suffix('.md')
    markdown.write_text(render_markdown(clean), encoding='utf-8')
    return clean


def render_markdown(report: dict[str, Any]) -> str:
    verdict = judge_suite(report)
    lines = [
        f"# Provider e2e — {report.get('suite', 'unknown')}",
        '',
        f"- 判定: {'通过' if verdict['passed'] else '未通过' if not verdict.get('skipped') else '跳过'}",
        f"- 提交: `{report.get('commit') or 'unknown'}`",
        f"- 应成功: {verdict.get('should_succeed_n', 0)} 条，成功率 "
        f"{_pct(verdict.get('should_succeed_rate'))}（门槛 {SUCCESS_RATE_THRESHOLD:.0%}）",
        f"- 应拦下: {verdict.get('should_block_n', 0)} 条，"
        f"{'全部在开始前拦下且 billable_calls_before_failure = 0' if verdict.get('should_block_passed') else '未满足 100% 拦截'}",
        f"- 故障注入: {verdict.get('fault_n', 0)} 条，"
        f"{'按预期 UpstreamErrorType 退避或续跑' if verdict.get('fault_passed') else '未按预期'}",
    ]
    if report.get('mode'):
        lines.append(f"- live 模式: `{report['mode']}`")
    if report.get('iso_week') is not None:
        lines.append(f"- ISO 周: {report['iso_week']}")
    budget = report.get('budget') or {}
    if budget:
        lines.append(
            f"- 预算: 本月已估 ¥{budget.get('spent_cny', 0):.2f} + 本轮估 ¥{budget.get('estimate_cny', 0):.2f}"
            f" / 月上限 ¥{budget.get('cap_cny', 0):.0f}；本轮实际 ¥{report.get('spent_cny', 0):.2f}"
        )
    if report.get('reason'):
        lines.append(f"- 说明: {report['reason']}")
    if verdict.get('history_note'):
        lines.append(f"- 滚动窗口: {verdict['history_note']}")
    for reason in verdict.get('reasons') or []:
        lines.append(f"- 失败原因: {reason}")
    skipped = report.get('skipped_providers') or []
    if skipped:
        lines.append('- 跳过的真实服务商: ' + ', '.join(
            f"{item.get('id')}（{item.get('reason')}）" for item in skipped
        ))
    for item in report.get('providers') or []:
        cost = item.get('spent_cny')
        cost_bit = f"，估 ¥{cost:.2f}" if isinstance(cost, (int, float)) else ''
        lines.append(
            f"- {item.get('label') or item.get('id')}: 模型 `{item.get('model')}` "
            f"（{item.get('model_source') or 'default'}） "
            f"{item.get('should_succeed_passed')}/{item.get('should_succeed_n')} 应成功，"
            f"{item.get('should_block_passed')}/{item.get('should_block_n')} 应拦下"
            f"{cost_bit}"
        )
    lines += [
        '',
        '| 用例 | 期望 | 结果 | 错误码 | error_class | HTTP | billable | 估费 |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |',
    ]
    for row in report.get('cases') or []:
        billed = row.get('billable_calls_before_failure')
        if billed is None:
            billed = row.get('billable_calls', 0)
        outcome = '中止' if row.get('aborted') else ('通过' if row.get('passed') else '失败')
        cost = row.get('estimated_cost_cny')
        cost_text = f'{cost:.2f}' if isinstance(cost, (int, float)) else '—'
        lines.append(
            f"| {row.get('label') or row.get('id')} | {row.get('expect')} | "
            f"{outcome} | {row.get('error_code') or '—'} | "
            f"{row.get('error_class') or row.get('upstream_error_type') or row.get('expected_upstream_error_type') or '—'} | "
            f"{row.get('http_status') or '—'} | "
            f"{billed} | {cost_text} |"
        )
    lines.append('')
    return '\n'.join(lines) + '\n'


def _pct(value: float | None) -> str:
    if value is None:
        return '—'
    return f'{value:.1%}'


def merge_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    cases = []
    skipped = []
    for report in reports:
        cases.extend(report.get('cases') or [])
        skipped.extend(report.get('skipped_providers') or [])
        if report.get('status') == 'skipped' and report.get('suite') == 'live':
            skipped.append({'id': 'live', 'reason': report.get('reason') or 'live suite skipped'})
    live = next((report for report in reports if report.get('suite') == 'live'), None)
    merged = {
        'schema_version': SCHEMA_VERSION,
        'suite': 'combined' if len(reports) > 1 else (reports[0].get('suite') if reports else 'combined'),
        'commit': next((report.get('commit') for report in reports if report.get('commit')), None),
        'cases': cases,
        'skipped_providers': skipped,
        'parts': [{'suite': report.get('suite'), 'status': report.get('status')} for report in reports],
    }
    if live:
        for key in (
            'mode', 'iso_week', 'budget', 'providers', 'window', 'spent_cny',
            'run_id', 'case_records', 'planned',
        ):
            if live.get(key) is not None:
                merged[key] = live[key]
    return merged
