"""Run one isolated studio import to completion (or expected refusal)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from backend.core.llm_telemetry import sanitize_upstream_error_type
from backend.core.upstream_errors import classify_upstream_error, is_retryable

from .backend import DesktopBackend
from .cost import usage_tokens
from .diagnose import from_backend_log, from_workspace, merge_diagnosis
from .http_util import HttpError, get_json, post_multipart
from .mask import redact
from .mock_openai import MockServer
from .settings import write_data_dir


def billable_calls_before_failure(data_dir: Path, project_id: str) -> int | None:
    """Paid calls in the project's ledger. #373: a missing ledger file or an unparsable line is unknown (None),
    never 0; only a complete, readable ledger is a count."""
    path = data_dir / 'projects' / project_id / 'metadata' / 'llm_usage.jsonl'
    if not path.is_file():
        return None
    count = 0
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            return None
        if not isinstance(row, dict):
            return None
        if row.get('kind') == 'timing':
            continue
        count += 1
    return count


def project_ids(data_dir: Path) -> frozenset[str] | None:
    """Ids of the projects on disk; None when the listing cannot be read (then nothing is proven)."""
    root = data_dir / 'projects'
    try:
        return frozenset(entry.name for entry in root.iterdir() if entry.is_dir()) if root.exists() else frozenset()
    except OSError:
        return None


def import_rejected_count(refused_code: str | None, before: frozenset[str] | None,
                          after: frozenset[str] | None) -> tuple[int | None, str | None]:
    """#369: 0 paid calls only when BOTH hold: the import answered a coded source_* 422, and the project list is
    the same set of ids before and after (compared by id, not by count). Otherwise unknown."""
    if refused_code and before is not None and after is not None and before == after:
        return 0, 'import_rejected'
    return None, None


billable_calls = billable_calls_before_failure


def usage_rows(data_dir: Path, project_id: str) -> list[dict[str, Any]]:
    path = data_dir / 'projects' / project_id / 'metadata' / 'llm_usage.jsonl'
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding='utf-8').splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def classify_case_error(error: str | None, error_code: str | None) -> str | None:
    blob = ' '.join(part for part in (error or '', error_code or '') if part)
    if not blob:
        return None
    classified = classify_upstream_error(None, blob)
    return sanitize_upstream_error_type(classified.error_type.value)


def _observed_upstream_error_type(server: MockServer | None, since: int) -> str | None:
    if server is None:
        return None
    for event in server.state.snapshot()['events'][since:]:
        value = sanitize_upstream_error_type(event.get('upstream_error_type'))
        if value:
            return value
    return None


def _workspace(base_url: str, project_id: str) -> dict[str, Any]:
    return get_json(f'{base_url}/api/v1/studio/{project_id}', timeout=20)


def _terminal(workspace: dict[str, Any]) -> bool:
    generation = workspace.get('generation') or {}
    analysis = workspace.get('analysis') or {}
    g_status = generation.get('status')
    a_status = analysis.get('status')
    if g_status in {'completed', 'partial', 'failed'}:
        return True
    if a_status in {'failed', 'completed'} and g_status not in {'screening', 'production', 'rendering', 'running'}:
        return True
    return False


def poll_workspace(base_url: str, project_id: str, timeout: float) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        try:
            last = _workspace(base_url, project_id)
        except Exception:  # noqa: BLE001 - backend may bounce during kill
            time.sleep(1)
            continue
        if _terminal(last):
            return last
        time.sleep(1.5)
    last['poll_timeout'] = True
    return last


def import_project(base_url: str, fixture: dict[str, Any]) -> str:
    files = {'video': Path(fixture['video'])}
    if fixture.get('srt'):
        files['subtitle'] = Path(fixture['srt'])
    payload = post_multipart(
        f'{base_url}/api/v1/studio/import',
        {
            'goal': 'content',
            'language': 'source',
            'aspect': 'original',
            'platforms': 'original',
            'auto_start': True,
            'brand_outro_enabled': False,
            'html_template': 'classic',
            'name': fixture.get('label') or fixture['id'],
        },
        files,
        timeout=90,
    )
    project_id = payload.get('project_id')
    if not project_id:
        raise RuntimeError(f'import did not return project_id: {payload}')
    return str(project_id)


def paid_calls(seen: int | None, ledger: int | None) -> int | None:
    """#353: the larger of the observer count and the project ledger; None when neither exists (never 0)."""
    known = [value for value in (seen, ledger) if value is not None]
    return max(known) if known else None


def observed_chat_calls(observer: MockServer | None, events_before: int) -> int | None:
    """Chat-completion requests the mock provider saw since ``events_before``; None without an observer."""
    if observer is None:
        return None
    events = observer.state.snapshot()['events'][events_before:]
    return sum(1 for event in events if 'chat/completions' in str(event.get('path') or ''))


def refusal_workspace(expect: str, exc: HttpError) -> dict[str, Any] | None:
    """#418: the one preflight refuses a bad source at import with a coded 422 (no project, no state). Only a
    should-block case may read that as its result (failed at INGEST with that code); any other case keeps the error."""
    if expect != 'block':
        return None
    refused = import_refusal_code(exc)
    if refused is None:
        return None
    return {'generation': {'status': 'failed', 'error_code': refused, 'failure_stage': 'INGEST'}, 'analysis': {}}


def import_refusal_code(exc: HttpError) -> str | None:
    """The source code of a coded 422 import refusal (``detail.code``), else None."""
    if getattr(exc, 'status', None) != 422:
        return None
    try:
        body = json.loads(exc.body or '{}')
    except ValueError:
        return None
    detail = body.get('detail') if isinstance(body, dict) else None
    code = detail.get('code') if isinstance(detail, dict) else None
    return code if isinstance(code, str) and code.startswith('source_') else None


def evaluate_case(
    expect: str,
    workspace: dict[str, Any],
    billable_calls_before_failure: int | None,
    block_code: str | None = None,
    *,
    expected_upstream_error_type: str | None = None,
    observed_upstream_error_type: str | None = None,
) -> dict[str, Any]:
    generation = workspace.get('generation') or {}
    analysis = workspace.get('analysis') or {}
    error_code = generation.get('error_code') or analysis.get('error_code')
    status = generation.get('status') or analysis.get('status')
    variants = [row for row in (workspace.get('output_variants') or []) if isinstance(row, dict)]
    completed = [row for row in variants if row.get('status') == 'completed']
    if expect == 'succeed':
        passed = status == 'completed' and bool(completed) and not workspace.get('poll_timeout')
        reason = None if passed else f'status={status} completed_variants={len(completed)} code={error_code}'
        if passed and expected_upstream_error_type:
            expected = sanitize_upstream_error_type(expected_upstream_error_type)
            observed = sanitize_upstream_error_type(observed_upstream_error_type)
            if expected is None or not is_retryable(expected):
                passed = False
                reason = (
                    f'expected_upstream_error_type={expected_upstream_error_type} '
                    'is not a retryable UpstreamErrorType'
                )
            elif observed is not None and observed != expected:
                passed = False
                reason = f'upstream_error_type={observed} expected={expected}'
        return {'passed': passed, 'reason': reason}
    if expect == 'block':
        before_start = (generation.get('failure_stage') in (None, 'screening', 'ingest', 'INGEST')
                        or analysis.get('phase') == 'screening'
                        or error_code in {'source_too_short', 'source_no_audio'})
        code_ok = error_code == block_code if block_code else error_code in {'source_too_short', 'source_no_audio'}
        passed = status == 'failed' and code_ok and before_start and billable_calls_before_failure == 0
        reason = None
        if not passed:
            reason = (
                f'status={status} code={error_code} '
                f'billable_calls_before_failure={billable_calls_before_failure} '
                f'phase={analysis.get("phase")}'
            )
        return {'passed': passed, 'reason': reason}
    if expect == 'service_restarted':
        passed = error_code == 'service_restarted'
        return {
            'passed': passed,
            'reason': None if passed else f'expected service_restarted, got {error_code} status={status}',
        }
    return {'passed': False, 'reason': f'unknown expect {expect}'}


def run_case(
    *,
    case_id: str,
    label: str,
    expect: str,
    fixture: dict[str, Any],
    data_dir: Path,
    connection: dict[str, str],
    python: str,
    timeout: float,
    extras: list[str] | None = None,
    kill_after_request: MockServer | None = None,
    restart_after_kill: bool = False,
    expected_upstream_error_type: str | None = None,
    mock_server: MockServer | None = None,
) -> dict[str, Any]:
    write_data_dir(
        data_dir,
        base_url=connection['base_url'],
        api_key=connection['api_key'],
        provider=connection['provider'],
        model=connection['model'],
    )
    backend = DesktopBackend(data_dir, python=python)
    project_id = ''
    workspace: dict[str, Any] = {}
    error = None
    started = time.monotonic()
    observer = mock_server or kill_after_request
    events_before = len(observer.state.snapshot()['events']) if observer is not None else 0
    ids_before = None
    refused_code = None
    try:
        base_url = backend.start()
        ids_before = project_ids(data_dir)
        project_id = import_project(base_url, fixture)
        if kill_after_request is not None:
            deadline = time.time() + min(45, timeout)
            while time.time() < deadline:
                snap = kill_after_request.state.snapshot()
                if len(snap['events']) > events_before:
                    break
                time.sleep(0.4)
            backend.kill()
            if restart_after_kill:
                backend = DesktopBackend(data_dir, python=python)
                base_url = backend.start()
                workspace = poll_workspace(base_url, project_id, timeout=min(60, timeout))
            else:
                workspace = {'generation': {'status': 'unknown'}, 'analysis': {}}
        else:
            workspace = poll_workspace(base_url, project_id, timeout)
    except HttpError as exc:
        refused = refusal_workspace(expect, exc)
        if refused is not None:
            workspace = refused
            refused_code = refused['generation']['error_code']
        else:
            error = f'{type(exc).__name__}: {exc}'
            if getattr(exc, 'body', None):
                error += f' body={exc.body[:400]}'
    except (RuntimeError, TimeoutError, OSError) as exc:
        error = f'{type(exc).__name__}: {exc}'
        if getattr(exc, 'body', None):
            error += f' body={exc.body[:400]}'
    finally:
        backend.stop()
    # #353: paid calls are counted, never inferred from "no project": the request observer (mock suites) counts
    # every chat request since this case started; otherwise the project's ledger; with neither it is unknown.
    seen = observed_chat_calls(observer, events_before)
    ledger = billable_calls_before_failure(data_dir, project_id) if project_id else None
    rejected, rejected_source = import_rejected_count(refused_code, ids_before, project_ids(data_dir)) if not project_id else (None, None)
    if refused_code is not None and rejected is None:
        # #369 (live and mock alike): a refused import that cannot be proven project-free is unknown, even when
        # the observer saw no chat call.
        billable, count_source = None, None
    else:
        billable = paid_calls(seen, ledger if ledger is not None else rejected)
        count_source = (rejected_source if rejected is not None and billable == 0 else
                        'observer' if seen is not None and billable == seen else
                        'ledger' if ledger is not None else None) if billable is not None else None
    prompt_tokens, completion_tokens = (0, 0)
    if project_id:
        prompt_tokens, completion_tokens = usage_tokens(usage_rows(data_dir, project_id))
    observed = _observed_upstream_error_type(observer, events_before)
    error_code = (workspace.get('generation') or {}).get('error_code') or (workspace.get('analysis') or {}).get('error_code')
    diagnosis = merge_diagnosis(from_workspace(workspace), from_backend_log(backend.log_path))
    error_class = (
        observed
        or diagnosis.get('error_class')
        or classify_case_error(error, error_code)
    )
    http_status = diagnosis.get('http_status')
    judged = evaluate_case(
        expect,
        workspace,
        billable,
        fixture.get('block_code'),
        expected_upstream_error_type=expected_upstream_error_type,
        observed_upstream_error_type=observed,
    )
    if error and expect != 'service_restarted':
        judged = {'passed': False, 'reason': error}
    result = {
        'id': case_id,
        'label': label,
        'expect': expect,
        'project_id': project_id,
        'passed': judged['passed'],
        'reason': judged.get('reason'),
        'billable_calls_before_failure': billable,
        'billable_calls': billable,
        'count_source': count_source,
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'duration_ms': int((time.monotonic() - started) * 1000),
        'expected_upstream_error_type': expected_upstream_error_type,
        'upstream_error_type': observed,
        'error_class': error_class,
        'http_status': http_status,
        'log_excerpt': diagnosis.get('log_excerpt'),
        'error_code': error_code,
        'status': (workspace.get('generation') or {}).get('status') or (workspace.get('analysis') or {}).get('status'),
        'failure_stage': (workspace.get('generation') or {}).get('failure_stage'),
        'phase': (workspace.get('analysis') or {}).get('phase'),
        'completed_variants': sum(1 for row in (workspace.get('output_variants') or []) if row.get('status') == 'completed'),
        'error': error,
        'provider': connection.get('provider'),
        'model': connection.get('model'),
    }
    return redact(result, extras)
