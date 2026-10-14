"""CLI: python -m provider_e2e --suite mock --out DIR"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from . import SCHEMA_VERSION
from .backend import ROOT
from .fixtures import generate_all
from .harness import run_case
from .judge import VerdictError, require_pass
from .mask import redact
from .matrix import MOCK_PROVIDER, assets, faults, live_providers
from .mock_openai import base_url, start, stop
from .report import merge_reports, write_report
from .settings import live_ready


def _commit() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def _history(path: Path | None, current_rate: float) -> dict:
    if path is None or not path.is_dir():
        return {
            'available': False,
            'runs_considered': 1,
            'cumulative_success_rate': current_rate,
            'note': '无历史夜间回归样本；仅判定当次成功率',
        }
    rates = [current_rate]
    for item in sorted(path.glob('**/report.json'))[-6:]:
        try:
            payload = json.loads(item.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        succeed = [row for row in payload.get('cases') or [] if row.get('expect') == 'succeed']
        if succeed:
            rates.append(sum(1 for row in succeed if row.get('passed')) / len(succeed))
    return {
        'available': len(rates) > 1,
        'runs_considered': len(rates),
        'cumulative_success_rate': sum(rates) / len(rates),
        'note': '当次门槛为硬门槛；近 7 次累计仅作参考，直到 nightly 产物被保留',
    }


def run_mock(out: Path, python: str, timeout: float, extras: list[str]) -> dict:
    fixtures_dir = out / 'fixtures'
    generated = {item['id']: item for item in generate_all(assets(), fixtures_dir)}
    success_fixture = generated['talk_zh']
    server, root = start()
    cases = []
    try:
        for spec in assets():
            fixture = generated[spec['id']]
            data_dir = out / 'runs' / f"mock-{spec['id']}"
            cases.append(run_case(
                case_id=f"mock:{spec['id']}",
                label=f"mock / {spec['label']}",
                expect=spec['expect'],
                fixture=fixture,
                data_dir=data_dir,
                connection={
                    'base_url': base_url(root),
                    'api_key': MOCK_PROVIDER['api_key'],
                    'provider': MOCK_PROVIDER['provider'],
                    'model': MOCK_PROVIDER['model'],
                },
                python=python,
                timeout=timeout,
                extras=extras,
            ))
        for fault in faults():
            data_dir = out / 'runs' / f"mock-fault-{fault['id']}"
            kill = fault['fault'] == 'kill'
            cases.append(run_case(
                case_id=f"mock:{fault['id']}",
                label=f"mock / {fault['label']}",
                expect=fault['expect'],
                fixture=success_fixture,
                data_dir=data_dir,
                connection={
                    'base_url': base_url(root, 'slow' if kill else fault['fault']),
                    'api_key': MOCK_PROVIDER['api_key'],
                    'provider': MOCK_PROVIDER['provider'],
                    'model': MOCK_PROVIDER['model'],
                },
                python=python,
                timeout=timeout if not kill else min(timeout, 90),
                extras=extras,
                kill_after_request=server if kill else None,
                restart_after_kill=kill,
                expected_upstream_error_type=fault.get('upstream_error_type'),
                mock_server=server,
            ))
        snapshot = server.state.snapshot()
    finally:
        stop(server)
    succeed = [
        row for row in cases
        if row.get('expect') == 'succeed' and not row.get('expected_upstream_error_type')
    ]
    rate = sum(1 for row in succeed if row.get('passed')) / len(succeed) if succeed else 1.0
    report = {
        'schema_version': SCHEMA_VERSION,
        'suite': 'mock',
        'status': 'completed',
        'commit': _commit(),
        'cases': cases,
        'mock': redact(snapshot, extras),
        'history': _history(None, rate),
    }
    write_report(out / 'report.json', report, extras)
    return report


def run_live(out: Path, python: str, timeout: float, env: dict[str, str], extras: list[str]) -> dict:
    ready_rows = []
    skipped = []
    for provider in live_providers():
        info = live_ready(provider, env)
        if info['ready']:
            ready_rows.append((provider, info))
            extras.append(info['api_key'])
        else:
            skipped.append({'id': provider['id'], 'reason': info['reason']})
    if not ready_rows:
        report = {
            'schema_version': SCHEMA_VERSION,
            'suite': 'live',
            'status': 'skipped',
            'reason': 'provider-e2e environment secrets are not configured',
            'commit': _commit(),
            'cases': [],
            'skipped_providers': skipped or [{'id': item['id'], 'reason': 'secret unset'} for item in live_providers()],
        }
        write_report(out / 'report.json', report, extras)
        return report
    generated = {item['id']: item for item in generate_all(assets(), out / 'fixtures')}
    cases = []
    for provider, info in ready_rows:
        for spec in assets():
            row = run_case(
                case_id=f"{provider['id']}:{spec['id']}",
                label=f"{provider['label']} / {spec['label']}",
                expect=spec['expect'],
                fixture=generated[spec['id']],
                data_dir=out / 'runs' / f"{provider['id']}-{spec['id']}",
                connection={
                    'base_url': info['base_url'],
                    'api_key': info['api_key'],
                    'provider': info['provider'],
                    'model': info['model'],
                },
                python=python,
                timeout=timeout,
                extras=extras,
            )
            row['provider_id'] = provider['id']
            row['model_source'] = info.get('model_source')
            cases.append(row)
    succeed = [
        row for row in cases
        if row.get('expect') == 'succeed' and not row.get('expected_upstream_error_type')
    ]
    rate = sum(1 for row in succeed if row.get('passed')) / len(succeed) if succeed else 1.0
    summaries = []
    for provider, info in ready_rows:
        rows = [row for row in cases if row.get('provider_id') == provider['id']]
        win = [row for row in rows if row.get('expect') == 'succeed']
        blocked = [row for row in rows if row.get('expect') == 'block']
        summaries.append({
            'id': provider['id'],
            'label': provider['label'],
            'model': info['model'],
            'model_source': info.get('model_source'),
            'base_url_host': info['base_url'].split('://', 1)[-1].split('/', 1)[0],
            'should_succeed_n': len(win),
            'should_succeed_passed': sum(1 for row in win if row.get('passed')),
            'should_block_n': len(blocked),
            'should_block_passed': sum(1 for row in blocked if row.get('passed')),
        })
    report = {
        'schema_version': SCHEMA_VERSION,
        'suite': 'live',
        'status': 'completed',
        'commit': _commit(),
        'cases': cases,
        'skipped_providers': skipped,
        'providers': summaries,
        'history': _history(None, rate),
    }
    write_report(out / 'report.json', report, extras)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='AutoClip provider e2e release gate')
    parser.add_argument('--suite', choices=('mock', 'live', 'all', 'judge'), default='mock')
    parser.add_argument('--out', type=Path, default=Path('artifacts/provider-e2e'))
    parser.add_argument('--timeout', type=float, default=420)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--report', type=Path, action='append', default=[])
    args = parser.parse_args(argv)
    extras = [value for key, value in os.environ.items()
              if value and key.upper().endswith(('_API_KEY', '_TOKEN'))]
    try:
        if args.suite == 'judge':
            reports = [json.loads(path.read_text(encoding='utf-8')) for path in args.report]
            merged = merge_reports(reports)
            write_report(args.out / 'report.json', merged, extras)
            require_pass(reports)
            return 0
        if args.suite in {'mock', 'all'}:
            mock_report = run_mock(args.out / 'mock', args.python, args.timeout, extras)
        else:
            mock_report = None
        if args.suite in {'live', 'all'}:
            live_report = run_live(args.out / 'live', args.python, args.timeout, dict(os.environ), extras)
        else:
            live_report = None
        reports = [item for item in (mock_report, live_report) if item]
        write_report(args.out / 'report.json', merge_reports(reports), extras)
        if args.suite == 'live' and live_report and live_report.get('status') == 'skipped':
            return 0
        require_pass(reports)
        return 0
    except VerdictError as error:
        print(f'provider-e2e: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
