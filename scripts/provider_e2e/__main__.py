"""CLI: python -m provider_e2e --suite mock --out DIR"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from backend.core.upstream_errors import is_retryable

from . import SCHEMA_VERSION
from .backend import ROOT
from .cost import MONTHLY_BUDGET_CNY, actual_case_cny, provider_cap_cny, run_cap_cny
from .fixtures import generate_all
from .harness import run_case
from .judge import VerdictError, load_reports, require_pass
from .library import (
    budget_check,
    case_from_result,
    fetch_github_artifacts,
    load_jsonl,
    load_library,
    open_budget_issue,
    rolling_window,
    try_push_branch,
    write_cases,
    write_step_summary,
)
from .mask import redact
from .matrix import (
    LIVE_MODES,
    MOCK_PROVIDER,
    assets,
    assignments,
    current_iso_week,
    faults,
    live_providers,
    resolve_mode,
)
from .mock_openai import base_url, start, stop
from .report import merge_reports, write_report
from .settings import live_ready


def _commit() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def _run_id(env: dict[str, str]) -> str:
    return (env.get('GITHUB_RUN_ID') or env.get('PROVIDER_E2E_RUN_ID') or 'local').strip() or 'local'


def _aborted_row(assignment: dict, reason: str, info: dict[str, str]) -> dict:
    return {
        'id': f"{assignment['provider_id']}:{assignment['clip_id']}",
        'label': f"{assignment['provider'].get('label')} / {assignment['asset'].get('label')}",
        'expect': assignment['expect'],
        'passed': None,
        'aborted': True,
        'abort_reason': reason,
        'provider_id': assignment['provider_id'],
        'clip_id': assignment['clip_id'],
        'model': info.get('model'),
        'provider': info.get('provider'),
        'billable_calls_before_failure': 0,
        'billable_calls': 0,
        'estimated_cost_cny': 0.0,
        'prompt_tokens': 0,
        'completion_tokens': 0,
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
                mock_server=server,  # #353: the request observer counts paid calls, also when no project exists
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
        'history': {
            'available': False,
            'runs_considered': 1,
            'cumulative_success_rate': rate,
            'note': 'mock 只判定当次；live 才走滚动窗口',
        },
    }
    write_report(out / 'report.json', report, extras)
    return report


def run_live(
    out: Path,
    python: str,
    timeout: float,
    env: dict[str, str],
    extras: list[str],
    *,
    mode: str | None = None,
    library_dir: Path | None = None,
    week: int | None = None,
) -> dict:
    mode = mode or resolve_mode(env)
    week = current_iso_week() if week is None else int(week)
    run_id = _run_id(env)
    commit = _commit()
    library = load_library(library_dir)
    ready_map: dict[str, tuple[dict, dict]] = {}
    skipped = []
    for provider in live_providers():
        info = live_ready(provider, env)
        if info['ready']:
            ready_map[provider['id']] = (provider, info)
            extras.append(info['api_key'])
        else:
            skipped.append({'id': provider['id'], 'reason': info['reason']})
    planned = []
    for item in assignments(mode, week=week):
        row = dict(item)
        ready = ready_map.get(item['provider_id'])
        if ready:
            row['model'] = ready[1]['model']
        planned.append(row)
    runnable = [item for item in planned if item['provider_id'] in ready_map]
    if not runnable:
        report = {
            'schema_version': SCHEMA_VERSION,
            'suite': 'live',
            'mode': mode,
            'iso_week': week,
            'status': 'skipped',
            'reason': 'provider-e2e environment secrets are not configured',
            'commit': commit,
            'run_id': run_id,
            'cases': [],
            'case_records': [],
            'skipped_providers': skipped or [{'id': item['id'], 'reason': 'secret unset'} for item in live_providers()],
        }
        write_report(out / 'report.json', report, extras)
        write_cases(out / 'cases.jsonl', [])
        return report
    budget = budget_check(library, runnable)
    if budget['blocked']:
        write_step_summary(out / 'budget.md', [
            '## Provider e2e budget',
            '',
            budget['reason'] or 'monthly live budget cap reached',
            '',
            'Live cases were not started. Mock is unaffected.',
        ])
        issue = open_budget_issue(env, budget)
        report = {
            'schema_version': SCHEMA_VERSION,
            'suite': 'live',
            'mode': mode,
            'iso_week': week,
            'status': 'budget_blocked',
            'reason': budget['reason'],
            'commit': commit,
            'run_id': run_id,
            'cases': [],
            'case_records': [],
            'budget': budget,
            'alert': issue,
            'skipped_providers': skipped,
        }
        write_report(out / 'report.json', report, extras)
        write_cases(out / 'cases.jsonl', [])
        return report
    needed_ids = {item['clip_id'] for item in runnable}
    generated = {item['id']: item for item in generate_all(
        [spec for spec in assets() if spec['id'] in needed_ids],
        out / 'fixtures',
    )}
    cases = []
    records = []
    run_spent = 0.0
    aborted: dict[str, str] = {}
    per_provider_spent: dict[str, float] = {}
    run_limit = run_cap_cny(mode)
    provider_limit = provider_cap_cny(mode)
    for item in planned:
        provider_id = item['provider_id']
        ready = ready_map.get(provider_id)
        if ready is None:
            continue
        provider, info = ready
        if provider_id in aborted:
            row = _aborted_row(item, aborted[provider_id], info)
            cases.append(row)
            continue
        if run_spent >= run_limit:
            aborted[provider_id] = 'run_cap'
            row = _aborted_row(item, 'run_cap', info)
            cases.append(row)
            continue
        row = run_case(
            case_id=f"{provider_id}:{item['clip_id']}",
            label=f"{provider['label']} / {item['asset']['label']}",
            expect=item['expect'],
            fixture=generated[item['clip_id']],
            data_dir=out / 'runs' / f"{provider_id}-{item['clip_id']}",
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
        row['provider_id'] = provider_id
        row['clip_id'] = item['clip_id']
        row['model_source'] = info.get('model_source')
        row['role'] = item.get('role')
        cost = actual_case_cny(
            info['model'],
            int(row.get('prompt_tokens') or 0),
            int(row.get('completion_tokens') or 0),
            item['expect'],
            passed=row.get('passed'),
        )
        row['estimated_cost_cny'] = cost
        run_spent = round(run_spent + cost, 4)
        per_provider_spent[provider_id] = round(per_provider_spent.get(provider_id, 0) + cost, 4)
        error_class = row.get('error_class') or row.get('upstream_error_type')
        hard = (not row.get('passed')) and not (error_class and is_retryable(error_class))
        if hard:
            aborted[provider_id] = 'hard_failure'
            row['abort_remaining'] = 'hard_failure'
        elif per_provider_spent[provider_id] >= provider_limit:
            aborted[provider_id] = 'provider_cap'
            row['abort_remaining'] = 'provider_cap'
        elif run_spent >= run_limit:
            aborted[provider_id] = 'run_cap'
            row['abort_remaining'] = 'run_cap'
        cases.append(row)
        records.append(case_from_result(
            row,
            run_id=run_id,
            commit=commit,
            mode=mode,
            iso_week=week,
            provider_id=provider_id,
            clip_id=item['clip_id'],
            model_source=info.get('model_source'),
            base_url_host=info['base_url'],
        ))
    window = rolling_window(library + records)
    summaries = []
    for provider, info in ready_map.values():
        rows = [row for row in cases if row.get('provider_id') == provider['id'] and not row.get('aborted')]
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
            'spent_cny': per_provider_spent.get(provider['id'], 0.0),
            'aborted': aborted.get(provider['id']),
        })
    report = {
        'schema_version': SCHEMA_VERSION,
        'suite': 'live',
        'mode': mode,
        'iso_week': week,
        'status': 'completed',
        'commit': commit,
        'run_id': run_id,
        'cases': cases,
        'planned': [
            {
                'provider_id': item['provider_id'],
                'clip_id': item['clip_id'],
                'expect': item['expect'],
                'role': item.get('role'),
            }
            for item in planned if item['provider_id'] in ready_map
        ],
        'case_records': records,
        'skipped_providers': skipped,
        'providers': summaries,
        'budget': budget,
        'spent_cny': run_spent,
        'window': window,
        'history': window,
    }
    write_report(out / 'report.json', report, extras)
    write_cases(out / 'cases.jsonl', records)
    if library_dir is not None:
        write_cases(library_dir / f'run-{run_id}.jsonl', records)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='AutoClip provider e2e release gate')
    parser.add_argument('--suite', choices=('mock', 'live', 'all', 'judge', 'fetch-library', 'archive'), default='mock')
    parser.add_argument('--out', type=Path, default=Path('artifacts/provider-e2e'))
    parser.add_argument('--timeout', type=float, default=420)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--report', type=Path, action='append', default=[])
    parser.add_argument('--mode', choices=('auto',) + LIVE_MODES, default='auto')
    parser.add_argument('--library-dir', type=Path, default=None)
    parser.add_argument('--iso-week', type=int, default=None)
    parser.add_argument(
        '--expect-live',
        action='store_true',
        help='Fail closed if the live report is missing, empty, unparsable, incomplete, or has a provider failure',
    )
    args = parser.parse_args(argv)
    extras = [value for key, value in os.environ.items()
              if value and key.upper().endswith(('_API_KEY', '_TOKEN'))]
    env = dict(os.environ)
    try:
        if args.suite == 'fetch-library':
            dest = args.library_dir or args.out / 'library'
            count = fetch_github_artifacts(dest, env)
            print(f'provider-e2e: fetched {count} case-library artifacts')
            return 0
        if args.suite == 'archive':
            dest = args.library_dir or args.out
            rows = []
            for path in (args.out / 'cases.jsonl', dest / 'cases.jsonl'):
                if path.is_file():
                    rows = load_jsonl(path)
                    break
            result = try_push_branch(rows, env)
            print(f"provider-e2e: archive {result}")
            return 0 if result.get('pushed') or result.get('reason') in {'nothing to commit', 'missing token, repo, or rows'} else 1
        if args.suite == 'judge':
            reports = load_reports(args.report, expect_live=args.expect_live)
            library = load_library(args.library_dir)
            merged = merge_reports(reports)
            write_report(args.out / 'report.json', merged, extras)
            require_pass(reports, library=library, expect_live=args.expect_live)
            return 0
        mode = None if args.mode == 'auto' else args.mode
        if args.suite in {'mock', 'all'}:
            mock_report = run_mock(args.out / 'mock', args.python, args.timeout, extras)
        else:
            mock_report = None
        if args.suite in {'live', 'all'}:
            live_report = run_live(
                args.out / 'live',
                args.python,
                args.timeout,
                env,
                extras,
                mode=mode,
                library_dir=args.library_dir,
                week=args.iso_week,
            )
        else:
            live_report = None
        reports = [item for item in (mock_report, live_report) if item]
        if live_report is not None:
            live_cases = args.out / 'live' / 'cases.jsonl'
            if live_cases.is_file():
                write_cases(args.out / 'cases.jsonl', load_jsonl(live_cases))
        payload = reports[0] if len(reports) == 1 else merge_reports(reports)
        write_report(args.out / 'report.json', payload, extras)
        if args.suite == 'live' and live_report and live_report.get('status') == 'skipped':
            return 0
        require_pass(reports, library=load_library(args.library_dir))
        return 0
    except VerdictError as error:
        print(f'provider-e2e: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
