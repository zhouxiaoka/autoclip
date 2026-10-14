"""Append-only sanitized live case records. No keys, transcripts, or full URLs."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import CASE_SCHEMA_VERSION, ROLLING_MIN_SAMPLE, ROLLING_WINDOW_RUNS, SUCCESS_RATE_THRESHOLD
from .cost import MONTHLY_BUDGET_CNY, estimate_plan_cny
from .mask import redact

CASE_FIELDS = (
    'schema_version',
    'run_id',
    'commit',
    'mode',
    'recorded_at',
    'iso_week',
    'provider',
    'clip_id',
    'model',
    'model_source',
    'passed',
    'expect',
    'error_class',
    'http_status',
    'error_code',
    'duration_ms',
    'estimated_cost_cny',
    'prompt_tokens',
    'completion_tokens',
    'billable_calls',
    'base_url_host',
    'aborted',
    'abort_reason',
)

LIBRARY_BRANCH = 'provider-e2e-cases'


def host_only(url: str | None) -> str:
    raw = (url or '').strip()
    if '://' in raw:
        raw = raw.split('://', 1)[1]
    return raw.split('/', 1)[0].split('?', 1)[0]


def sanitize_case(row: dict[str, Any]) -> dict[str, Any]:
    clean = {key: row.get(key) for key in CASE_FIELDS}
    clean['schema_version'] = CASE_SCHEMA_VERSION
    clean['base_url_host'] = host_only(str(clean.get('base_url_host') or ''))
    if clean.get('passed') is not None:
        clean['passed'] = bool(clean['passed'])
    clean['aborted'] = bool(clean.get('aborted'))
    if clean.get('http_status') is not None:
        try:
            clean['http_status'] = int(clean['http_status'])
        except (TypeError, ValueError):
            clean['http_status'] = None
    for key in ('duration_ms', 'prompt_tokens', 'completion_tokens', 'billable_calls', 'iso_week'):
        try:
            clean[key] = int(clean.get(key) or 0)
        except (TypeError, ValueError):
            clean[key] = 0
    try:
        clean['estimated_cost_cny'] = round(float(clean.get('estimated_cost_cny') or 0), 4)
    except (TypeError, ValueError):
        clean['estimated_cost_cny'] = 0.0
    return redact(clean)


def case_from_result(
    result: dict[str, Any],
    *,
    run_id: str,
    commit: str,
    mode: str,
    iso_week: int,
    provider_id: str,
    clip_id: str,
    model_source: str | None,
    base_url_host: str,
) -> dict[str, Any]:
    return sanitize_case({
        'run_id': run_id,
        'commit': commit,
        'mode': mode,
        'recorded_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'iso_week': iso_week,
        'provider': provider_id,
        'clip_id': clip_id,
        'model': result.get('model'),
        'model_source': model_source,
        'passed': result.get('passed'),
        'expect': result.get('expect'),
        'error_class': result.get('error_class') or result.get('upstream_error_type'),
        'http_status': result.get('http_status'),
        'error_code': result.get('error_code'),
        'duration_ms': result.get('duration_ms') or 0,
        'estimated_cost_cny': result.get('estimated_cost_cny') or 0,
        'prompt_tokens': result.get('prompt_tokens') or 0,
        'completion_tokens': result.get('completion_tokens') or 0,
        'billable_calls': result.get('billable_calls_before_failure') or result.get('billable_calls') or 0,
        'base_url_host': base_url_host,
        'aborted': result.get('aborted'),
        'abort_reason': result.get('abort_reason'),
    })


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if isinstance(payload, dict):
            rows.append(sanitize_case(payload))
    return rows


def load_library(directory: Path | None) -> list[dict[str, Any]]:
    if directory is None or not directory.exists():
        return []
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    paths = sorted(directory.rglob('*.jsonl'))
    paths += sorted(path for path in directory.rglob('cases.json') if path not in paths)
    for path in paths:
        if path.name == 'cases.json':
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            candidates = payload if isinstance(payload, list) else payload.get('cases') or []
            parsed = [sanitize_case(item) for item in candidates if isinstance(item, dict)]
        else:
            parsed = load_jsonl(path)
        for item in parsed:
            key = (item.get('run_id'), item.get('provider'), item.get('clip_id'), item.get('recorded_at'))
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)
    return rows


def write_cases(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = [sanitize_case(row) for row in rows]
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in clean), encoding='utf-8')
    path.with_suffix('.json').write_text(
        json.dumps({'schema_version': CASE_SCHEMA_VERSION, 'cases': clean}, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )


def month_key(stamp: str | None, now: datetime | None = None) -> str:
    if stamp:
        return str(stamp)[:7]
    moment = now or datetime.now(timezone.utc)
    return moment.strftime('%Y-%m')


def month_spend_cny(rows: list[dict[str, Any]], *, now: datetime | None = None) -> float:
    key = month_key(None, now)
    total = 0.0
    for row in rows:
        if month_key(str(row.get('recorded_at') or '')) != key:
            continue
        try:
            total += float(row.get('estimated_cost_cny') or 0)
        except (TypeError, ValueError):
            continue
    return round(total, 4)


def budget_check(
    rows: list[dict[str, Any]],
    plan: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    cap: float = MONTHLY_BUDGET_CNY,
) -> dict[str, Any]:
    spent = month_spend_cny(rows, now=now)
    estimate = estimate_plan_cny(plan)
    projected = round(spent + estimate, 4)
    blocked = projected > cap
    return {
        'spent_cny': spent,
        'estimate_cny': estimate,
        'projected_cny': projected,
        'cap_cny': cap,
        'blocked': blocked,
        'reason': (
            f'monthly live budget {projected:.2f} CNY would exceed ¥{cap:.0f} '
            f'(spent {spent:.2f} + estimate {estimate:.2f})'
            if blocked else None
        ),
    }


def _succeed_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row for row in rows
        if row.get('expect') == 'succeed' and not row.get('aborted') and row.get('passed') is not None
    ]


def rolling_window(
    rows: list[dict[str, Any]],
    *,
    window_runs: int = ROLLING_WINDOW_RUNS,
    min_sample: int = ROLLING_MIN_SAMPLE,
    threshold: float = SUCCESS_RATE_THRESHOLD,
) -> dict[str, Any]:
    by_run: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for row in rows:
        run_id = str(row.get('run_id') or '')
        if not run_id:
            continue
        if run_id not in by_run:
            by_run[run_id] = []
            order.append(run_id)
        by_run[run_id].append(row)
    selected_ids = order[-window_runs:]
    selected = [row for run_id in selected_ids for row in by_run[run_id]]
    succeed = _succeed_rows(selected)
    n = len(succeed)
    passed_n = sum(1 for row in succeed if row.get('passed'))
    rate = (passed_n / n) if n else 1.0
    enforced = n >= min_sample
    return {
        'available': bool(selected_ids),
        'runs_considered': len(selected_ids),
        'run_ids': selected_ids,
        'should_succeed_n': n,
        'should_succeed_passed': passed_n,
        'success_rate': rate,
        'min_sample': min_sample,
        'enforced': enforced,
        'passed': (rate >= threshold) if enforced else True,
        'note': (
            f'rolling {len(selected_ids)} runs / {n} succeed cases = {rate:.1%}'
            + (f' (enforced ≥{threshold:.0%})' if enforced else f' (informational until {min_sample} succeed cases)')
        ),
    }


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(sanitize_case(row), ensure_ascii=False) + '\n')


def _github_json(url: str, token: str, *, binary: bool = False) -> Any:
    request = Request(url, headers={
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'autoclip-provider-e2e',
    })
    with urlopen(request, timeout=30) as response:
        data = response.read()
    if binary:
        return data
    return json.loads(data.decode('utf-8'))


def fetch_github_artifacts(dest: Path, env: dict[str, str], *, limit: int = 8) -> int:
    token = (env.get('GITHUB_TOKEN') or env.get('GH_TOKEN') or '').strip()
    repo = (env.get('GITHUB_REPOSITORY') or '').strip()
    if not token or not repo:
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    try:
        payload = _github_json(
            f'https://api.github.com/repos/{repo}/actions/artifacts?name=provider-e2e-cases&per_page={limit}',
            token,
        )
    except (HTTPError, URLError, TimeoutError, ValueError):
        return 0
    written = 0
    for artifact in payload.get('artifacts') or []:
        if artifact.get('expired') or not artifact.get('archive_download_url'):
            continue
        ident = artifact.get('id')
        try:
            blob = _github_json(artifact['archive_download_url'], token, binary=True)
        except (HTTPError, URLError, TimeoutError, ValueError):
            continue
        zip_path = dest / f'artifact-{ident}.zip'
        zip_path.write_bytes(blob)
        try:
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(dest / f'artifact-{ident}')
        except zipfile.BadZipFile:
            continue
        written += 1
    return written


def try_push_branch(rows: list[dict[str, Any]], env: dict[str, str]) -> dict[str, Any]:
    token = (env.get('GITHUB_TOKEN') or env.get('GH_TOKEN') or '').strip()
    repo = (env.get('GITHUB_REPOSITORY') or '').strip()
    run_id = str(env.get('GITHUB_RUN_ID') or 'local')
    if not token or not repo or not rows:
        return {'pushed': False, 'reason': 'missing token, repo, or rows'}
    work = Path(tempfile.mkdtemp(prefix='provider-e2e-cases-'))
    remote = f'https://github.com/{repo}.git'
    extra = f'http.extraheader=AUTHORIZATION: bearer {token}'
    clone = subprocess.run(
        ['git', '-c', extra, 'clone', '--depth=1', '--branch', LIBRARY_BRANCH, remote, str(work / 'repo')],
        capture_output=True, text=True, timeout=60,
    )
    repo_dir = work / 'repo'
    if clone.returncode != 0:
        repo_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'init', '-b', LIBRARY_BRANCH], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(['git', 'remote', 'add', 'origin', remote], cwd=repo_dir, check=True, capture_output=True)
        (repo_dir / 'README.md').write_text(
            '# provider-e2e case library\n\n'
            'Append-only sanitized live records. Do not merge this branch into main.\n',
            encoding='utf-8',
        )
    append_jsonl(repo_dir / 'cases.jsonl', rows)
    subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'],
                   cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(['git', 'add', '-A'], cwd=repo_dir, capture_output=True)
    commit = subprocess.run(
        ['git', 'commit', '-m', f'chore: append provider-e2e cases from run {run_id}'],
        cwd=repo_dir, capture_output=True, text=True,
    )
    if commit.returncode != 0:
        return {'pushed': False, 'reason': 'nothing to commit'}
    push = subprocess.run(
        ['git', '-c', extra, 'push', '-u', 'origin', LIBRARY_BRANCH],
        cwd=repo_dir, capture_output=True, text=True, timeout=60,
    )
    if push.returncode != 0:
        return {'pushed': False, 'reason': 'push rejected'}
    return {'pushed': True, 'branch': LIBRARY_BRANCH, 'run_id': run_id}


def open_budget_issue(env: dict[str, str], budget: dict[str, Any]) -> dict[str, Any]:
    token = (env.get('GITHUB_TOKEN') or env.get('GH_TOKEN') or '').strip()
    repo = (env.get('GITHUB_REPOSITORY') or '').strip()
    if not token or not repo:
        return {'opened': False, 'reason': 'missing token or repo'}
    title = f"[provider-e2e] monthly live budget cap ¥{budget['cap_cny']:.0f} reached"
    try:
        existing = _github_json(
            f'https://api.github.com/search/issues?q=repo:{repo}+is:issue+is:open+{title.replace(" ", "+")}',
            token,
        )
        if existing.get('total_count'):
            return {'opened': False, 'reason': 'already open'}
    except (HTTPError, URLError, TimeoutError, ValueError):
        pass
    body = (
        'Live provider-e2e skipped itself because the hard monthly cap would be exceeded.\n\n'
        f"- spent this month (estimated): ¥{budget['spent_cny']:.2f}\n"
        f"- this run estimate: ¥{budget['estimate_cny']:.2f}\n"
        f"- projected: ¥{budget['projected_cny']:.2f}\n"
        f"- cap: ¥{budget['cap_cny']:.0f}\n\n"
        'No keys or user content are included. Raise vendor dashboard limits only if you intend to spend more; '
        'the workflow cap stays at ¥300 until someone changes the constant in review.\n'
    )
    request = Request(
        f'https://api.github.com/repos/{repo}/issues',
        data=json.dumps({'title': title, 'body': body}).encode(),
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'autoclip-provider-e2e',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return {'opened': False, 'reason': type(exc).__name__}
    return {'opened': True, 'number': payload.get('number')}


def write_step_summary(path: Path, lines: list[str]) -> None:
    target = Path(os.environ['GITHUB_STEP_SUMMARY']) if os.environ.get('GITHUB_STEP_SUMMARY') else path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('a', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
