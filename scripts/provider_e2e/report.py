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
        f"{'全部在开始前拦下且 0 次付费调用' if verdict.get('should_block_passed') else '未满足 100% 拦截'}",
        f"- 故障注入: {verdict.get('fault_n', 0)} 条，"
        f"{'按预期' if verdict.get('fault_passed') else '未按预期'}",
    ]
    if report.get('reason'):
        lines.append(f"- 说明: {report['reason']}")
    if verdict.get('history_note'):
        lines.append(f"- 近 7 次: {verdict['history_note']}")
    skipped = report.get('skipped_providers') or []
    if skipped:
        lines.append('- 跳过的真实服务商: ' + ', '.join(
            f"{item.get('id')}（{item.get('reason')}）" for item in skipped
        ))
    lines += ['', '| 用例 | 期望 | 结果 | 错误码 | 付费调用 | 说明 |', '| --- | --- | --- | --- | --- | --- |']
    for row in report.get('cases') or []:
        lines.append(
            f"| {row.get('label') or row.get('id')} | {row.get('expect')} | "
            f"{'通过' if row.get('passed') else '失败'} | {row.get('error_code') or '—'} | "
            f"{row.get('billable_calls', 0)} | {(row.get('reason') or '—').replace('|', '/')} |"
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
    return {
        'schema_version': SCHEMA_VERSION,
        'suite': 'combined',
        'commit': next((report.get('commit') for report in reports if report.get('commit')), None),
        'cases': cases,
        'skipped_providers': skipped,
        'parts': [{'suite': report.get('suite'), 'status': report.get('status')} for report in reports],
    }
