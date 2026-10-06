"""Atomic project-local JSON storage; no migration of legacy clips/collections."""
import json
import logging
import os
import re
import threading
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from time import sleep
from pathlib import Path

from backend.core.path_utils import get_projects_directory

lock = threading.RLock()
INSTANCE = uuid.uuid4().hex

logger = logging.getLogger(__name__)
IO_FAILURE_MESSAGE = '无法保存项目状态，请检查磁盘空间和目录权限后重试；原素材与已有成片已保留'
# Content-free terminal patches, scoped to the exact project path. A worker
# must remain retryable even when persisting its failure is also denied.
_io_failures = {}
_read_failures = {}
_pending_links = {}
_worker = ContextVar('studio_metadata_worker', default=None)


@contextmanager
def worker_read_scope(project_id, identity):
    """Only accepted workers can leave a content-free read-failure receipt."""
    if identity is None:
        yield
        return
    path = directory(project_id) / 'metadata' / 'studio.json'
    receipt = {'identity': identity, 'pending': {}, 'denied': False}
    token = _worker.set((path, receipt))
    try:
        try:
            yield
        except PermissionError as error:
            if error is not receipt.get('read_error'):
                raise
    finally:
        _worker.reset(token)
        if receipt['denied'] or receipt.get('cover_finished_instance'):
            with lock:
                receipt.pop('read_error', None)
                _read_failures.setdefault(path, []).append(receipt)


def mark_render_finished(project_id, job_id):
    # An accepted render has left its optional cover step. If that terminal
    # write was denied, its own receipt releases the fence when reading recovers.
    scope = _worker.get()
    if scope and scope[0] == directory(project_id) / 'metadata' / 'studio.json' and scope[1]['identity'] == ('render', job_id):
        scope[1]['cover_finished_instance'] = INSTANCE


def _apply_finished_covers(path, data):
    changed = False
    for receipt in _read_failures.get(path, []):
        identity = receipt['identity']
        instance = receipt.get('cover_finished_instance')
        if identity[0] != 'render' or not instance:
            continue
        job = next((row for row in data['jobs'] if row['job_id'] == identity[1]), None)
        if job and job.get('status') == 'completed' and job.get('instance') == instance and job.get('cover_pending'):
            job['cover_pending'] = False
            changed = True
    return changed


def owned_read_error(error):
    scope = _worker.get()
    return bool(scope and error is scope[1].get('read_error'))


def mark_worker_error_reported():
    scope = _worker.get()
    if scope:
        scope[1]['reported'] = True


def read_error_needs_report(error):
    scope = _worker.get()
    return owned_read_error(error) and not scope[1].get('reported')


def raise_owned_read_error(error):
    scope = _worker.get()
    if scope and error is scope[1].get('read_error'):
        raise error


def analysis_handoff_rejected(project_id, run_id):
    scope = _worker.get()
    if scope and scope[0] == directory(project_id) / 'metadata' / 'studio.json':
        receipt = scope[1]
        if receipt['identity'] == ('analysis', run_id, 'screening'):
            receipt['identity'] = ('analysis', run_id, 'production')


def variant_identity(variant):
    return tuple(variant.get(key) for key in
                 ('id', 'draft_id', 'draft_revision', 'preparation_run_id', 'render_attempt_id'))


def claim_render(data, expected):
    variant = next((row for row in data['output_variants'] if row['id'] == expected[0]), None)
    if not variant or variant_identity(variant) != expected or variant.get('status') != 'queued' or variant.get('render_job_id') or variant.get('render_dispatch_claimed'):
        return None
    variant.setdefault('render_attempt_id', uuid.uuid4().hex)
    variant['render_dispatch_claimed'] = True
    variant['render_dispatch_instance'] = INSTANCE
    return variant_identity(variant)


def _reflect_render(variant, job):
    if variant.get('status') not in ('preparing', 'queued', 'running') or job.get('status') not in ('completed', 'failed'):
        return False
    if job['status'] == 'completed' and job.get('cover_pending') and job.get('instance') == INSTANCE:
        return False
    variant['status'] = job['status']
    if job['status'] == 'failed':
        variant.update(error=job.get('error', IO_FAILURE_MESSAGE), error_code=job.get('error_code', 'unexpected'))
    else:
        variant.pop('error', None)
        variant.pop('error_code', None)
    return True


def bind_render(data, expected, job_id):
    """Bind only this accepted attempt and reflect a worker that finished first."""
    variant = next((row for row in data['output_variants'] if row['id'] == expected[0]), None)
    job = next((row for row in data['jobs'] if row['job_id'] == job_id), None)
    if not variant or not job or variant_identity(variant) != expected:
        return False
    if variant.get('render_job_id') not in (None, job_id):
        return False
    if variant.get('status') not in ('queued', 'running', 'preparing'):
        return False
    changed = variant.get('render_job_id') != job_id
    variant['render_job_id'] = job_id
    variant.pop('render_dispatch_claimed', None)
    variant.pop('render_dispatch_instance', None)
    return _reflect_render(variant, job) or changed


def _apply_saved_render_links(data):
    changed = False
    for job in data['jobs']:
        links = job.get('variant_links', [])
        if not isinstance(links, list):
            continue
        for expected in links:
            if not isinstance(expected, (list, tuple)) or len(expected) != 5:
                continue
            changed = bind_render(data, tuple(expected), job['job_id']) or changed
    return changed


def remember_render_link(project_id, expected, job_id):
    # export has really accepted this job; a later read/bind denial must not lose
    # its link or let an old dispatcher bind over a newer retry.
    with lock:
        path = directory(project_id) / 'metadata' / 'studio.json'
        _pending_links.setdefault(path, {})[expected] = job_id


def has_pending_receipts(project_id):
    path = directory(project_id) / 'metadata' / 'studio.json'
    return bool(_read_failures.get(path) or _pending_links.get(path) or _io_failures.get(path))


def _observe_worker_write(path, previous, data):
    scope = _worker.get()
    if not scope or scope[0] != path:
        return
    receipt = scope[1]
    identity = receipt['identity']
    old_ids = {row['id'] for row in previous.get('output_variants', [])}
    for row in data['output_variants']:
        if row.get('status') != 'queued' or row.get('render_job_id'):
            continue
        own_preparation = identity[0] == 'preparation' and row['id'] == identity[1] and row.get('preparation_run_id') == identity[2]
        own_analysis = identity[0] == 'analysis' and (data.get('analysis') or {}).get('run_id') == identity[1]
        if own_preparation or (own_analysis and (row['id'] not in old_ids or row['id'] in receipt['pending'])):
            receipt['pending'][row['id']] = variant_identity(row)


def _apply_read_receipts(path, data):
    changed = _apply_finished_covers(path, data)
    settle = False
    for expected, job_id in _pending_links.get(path, {}).items():
        linked = bind_render(data, expected, job_id)
        changed = changed or linked
        settle = settle or linked
    for receipt in _read_failures.get(path, []):
        identity = receipt['identity']
        kind = identity[0]
        message = receipt.get('message', IO_FAILURE_MESSAGE)
        code = receipt.get('error_code', 'unexpected')
        if kind == 'render':
            job = next((row for row in data['jobs'] if row['job_id'] == identity[1]), None)
            if job and job.get('status') in ('queued', 'running'):
                job.update(status='failed', error=message, error_code=code)
                changed = True
            if job:
                for row in data['output_variants']:
                    if row.get('render_job_id') == identity[1] and _reflect_render(row, job):
                        changed = settle = True
        elif kind == 'cover':
            variant = next((row for row in data['output_variants'] if row['id'] == identity[1]), {})
            cover = variant.get('cover_job') or {}
            if cover.get('job_id') == identity[2] and cover.get('status') in ('queued', 'running'):
                cover.update(status='failed', error=message, error_code=code)
                changed = True
        elif kind == 'analysis':
            analysis = data.get('analysis') or {}
            if analysis.get('run_id') == identity[1] and analysis.get('phase') == identity[2] and analysis.get('status') == 'running':
                analysis.update(status='failed', error=message, error_code=code)
                generation = data.get('generation') or {}
                if generation.get('status') in ('screening', 'production'):
                    generation.update(status='failed', error=message, error_code=code, finished_at=now())
                changed = True
        elif kind == 'preparation':
            variant = next((row for row in data['output_variants'] if row['id'] == identity[1]), {})
            if variant.get('preparation_run_id') == identity[2] and variant.get('status') == 'preparing':
                variant.update(status='failed', error=message, error_code=code, needs_prepare=True)
                changed = settle = True
        for expected in receipt['pending'].values():
            variant = next((row for row in data['output_variants'] if row['id'] == expected[0]), {})
            if variant_identity(variant) == expected and variant.get('status') == 'queued' and not variant.get('render_job_id'):
                variant.update(status='failed', error=message, error_code=code)
                changed = settle = True
    if settle and data.get('generation'):
        settle_generation(data)
    return changed


def remember_submission_rejection(project_id, identity, *, error_code='unexpected'):
    """A persisted reservation exists, but submit explicitly accepted no worker."""
    with lock:
        path = directory(project_id) / 'metadata' / 'studio.json'
        kind = identity[0]
        message = {'render': '导出任务未能启动，请重试；已有成片已保留',
                   'preparation': '这条成片任务未能启动，请重试；已有成片已保留',
                   'cover': 'AI 封面任务未能启动，请重试'}.get(kind, '分析或制作任务未能启动，请重试；原素材与已有成片已保留')
        _read_failures.setdefault(path, []).append({'identity': identity, 'pending': {}, 'rejected': True, 'message': message, 'error_code': error_code})


def _changed_active_ids(previous, attempted, key, id_key, active):
    latest = {row[id_key]: row for row in attempted.get(key, []) if row.get(id_key)}
    return {row[id_key] for row in previous.get(key, [])
            if row.get(id_key) in latest and row != latest[row[id_key]]
            and (row.get('status') in active or latest[row[id_key]].get('status') in active)}


def _remember_io_failure(path, previous, attempted):
    failed_jobs = _changed_active_ids(previous, attempted, 'jobs', 'job_id', {'queued', 'running'})
    failed_variants = _changed_active_ids(previous, attempted, 'output_variants', 'id', {'queued', 'running', 'preparing'})
    latest_variants = {row['id']: row for row in attempted.get('output_variants', []) if row.get('id')}
    failed_covers = set()
    for variant in previous.get('output_variants', []):
        cover = variant.get('cover_job') or {}
        current = latest_variants.get(variant.get('id'), {}).get('cover_job') or {}
        if variant.get('id') and cover.get('status') in ('queued', 'running') and cover != current:
            failed_covers.add((variant['id'], cover.get('job_id')))
    analysis = previous.get('analysis') or {}
    failed_analysis = analysis.get('status') == 'running' and analysis != (attempted.get('analysis') or {})
    if not (failed_jobs or failed_variants or failed_covers or failed_analysis):
        return  # An unaccepted new operation must not create a phantom job.
    patch = _io_failures.setdefault(path, {'jobs': set(), 'variants': set(), 'covers': set(), 'at': now()})
    patch['jobs'].update(failed_jobs)
    patch['variants'].update(failed_variants)
    patch['covers'].update(failed_covers)
    if failed_analysis:
        patch['analysis_run_id'] = analysis.get('run_id')


def _apply_io_failure(path, data):
    patch = _io_failures.get(path)
    if not patch:
        return False
    changed = False
    for job in data['jobs']:
        if job['job_id'] in patch['jobs'] and job.get('status') in ('queued', 'running'):
            job.update(status='failed', error=IO_FAILURE_MESSAGE, error_code='unexpected')
            changed = True
    settle = False
    for variant in data['output_variants']:
        cover = variant.get('cover_job') or {}
        if (variant.get('id'), cover.get('job_id')) in patch['covers'] and cover.get('status') in ('queued', 'running'):
            cover.update(status='failed', error=IO_FAILURE_MESSAGE, error_code='unexpected')
            changed = True
        linked_job = next((job for job in data['jobs'] if job['job_id'] == variant.get('render_job_id') and (job['job_id'] in patch['jobs'] or variant.get('id') in patch['variants'])), None)
        if linked_job and _reflect_render(variant, linked_job):
            changed = settle = True
        if (variant.get('id') in patch['variants'] or variant.get('render_job_id') in patch['jobs']) and variant.get('status') in ('queued', 'running', 'preparing'):
            preparing = variant.get('status') == 'preparing'
            variant.update(status='failed', error=IO_FAILURE_MESSAGE, error_code='unexpected')
            if preparing:
                variant['needs_prepare'] = True
            changed = settle = True
    if settle and data.get('generation'):
        settle_generation(data)
        if data['generation']['status'] in ('completed', 'partial', 'failed'):
            data['generation']['finished_at'] = patch['at']
            data['analysis']['created_at'] = patch['at']
            if data['analysis']['status'] == 'failed':
                data['analysis']['error'] = IO_FAILURE_MESSAGE
    analysis = data.get('analysis') or {}
    if 'analysis_run_id' in patch and analysis.get('status') == 'running' and analysis.get('run_id') == patch['analysis_run_id']:
        analysis.update(status='failed', error=IO_FAILURE_MESSAGE, error_code='unexpected')
        generation = data.get('generation') or {}
        if generation.get('status') in ('screening', 'production', 'rendering'):
            generation.update(status='failed', error=IO_FAILURE_MESSAGE, error_code='unexpected', finished_at=patch['at'])
        changed = True
    return changed


def _serialized(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        with lock:
            return fn(*args, **kwargs)
    return run


def _replace_state(temporary, destination):
    # Windows readers (including external observers/virus scanners) can briefly
    # deny atomic replacement. Retry the same complete snapshot, never mutate twice.
    delays = (.02, .05, .1, .2)
    for attempt in range(len(delays) + 1):
        try:
            os.replace(temporary, destination)
            return
        except PermissionError as error:
            if getattr(error, 'winerror', None) not in (5, 32, 33) or attempt == len(delays):
                raise
            sleep(delays[attempt])

class ConflictError(ValueError):
    pass

def now():
    return datetime.now(timezone.utc).isoformat()

def directory(project_id: str) -> Path:
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', project_id):
        raise ValueError('无效项目 ID')
    return get_projects_directory() / project_id

@_serialized
def read(project_id: str, *, recover: bool = True):
    path = directory(project_id) / 'metadata' / 'studio.json'
    if not path.exists():
        _io_failures.pop(path, None)
        _read_failures.pop(path, None)
        _pending_links.pop(path, None)
        return {'schema_version': 2, 'drafts': [], 'events': [], 'jobs': [], 'analysis': None, 'output_variants': []}
    try:
        contents = path.read_text(encoding='utf-8')
    except PermissionError as error:
        scope = _worker.get()
        if scope and scope[0] == path:
            scope[1]['denied'] = True
            scope[1]['read_error'] = error
        raise
    data = json.loads(contents)
    data.setdefault('schema_version', 1)
    data.setdefault('drafts', [])
    data.setdefault('events', [])
    data.setdefault('jobs', [])
    data.setdefault('output_variants', [])
    if not recover:
        # CLI status commands are observers in another process, not a server restart.
        return data
    interrupted = set()
    cover_finished = _apply_finished_covers(path, data)
    for job in data['jobs']:
        if job['status'] == 'completed' and job.get('cover_pending') and job.get('instance') != INSTANCE:
            # Restarted optional work cannot revoke a video already committed.
            job['cover_pending'] = False
            cover_finished = True
        if job['status'] in ('queued', 'running') and job.get('instance') != INSTANCE:
            job.update(status='failed', error='服务已重启，请重新导出')
            interrupted.add(job.get('job_id'))
    linked = _apply_saved_render_links(data)
    abandoned_claim = False
    settle = linked
    for variant in data['output_variants']:
        cover_job = variant.get('cover_job') or {}
        if cover_job.get('status') in ('queued', 'running') and cover_job.get('instance') != INSTANCE:
            cover_job.update(status='failed', error='服务已重启，请重新生成封面')
        if variant.get('status') == 'queued' and not variant.get('render_job_id') and variant.get('render_dispatch_claimed') and variant.get('render_dispatch_instance') != INSTANCE:
            variant.update(status='failed', error='服务已重启，请重试这条')
            variant.pop('render_dispatch_claimed', None)
            variant.pop('render_dispatch_instance', None)
            abandoned_claim = True
            settle = True
        elif variant.get('status') == 'preparing' and variant.get('instance') != INSTANCE:
            variant.update(status='failed', error='服务已重启，请重试这条', needs_prepare=True)
            settle = True
        elif variant.get('status') in ('queued', 'running') and variant.get('render_job_id') in interrupted:
            # The app closed mid-render: the version becomes retryable instead of queued forever.
            variant.update(status='failed', error='服务已重启，请重试这条')
            settle = True
    if settle and data.get('generation'):
        settle_generation(data)
    patched = _apply_io_failure(path, data) or linked or abandoned_claim or cover_finished
    patched = _apply_read_receipts(path, data) or patched
    analysis = data.get('analysis')
    if analysis and analysis['status'] == 'running' and analysis.get('instance') != INSTANCE:
        analysis.update(status='failed', error='服务已重启，请重试分析')
    if patched:
        try:
            write(project_id, data, _recover_previous=False)
        except OSError:
            logger.warning('Studio terminal receipt persistence deferred')
        else:
            _read_failures.pop(path, None)
            _pending_links.pop(path, None)
    else:
        # Stale receipts cannot affect later attempts or already saved terminals.
        _read_failures.pop(path, None)
        _pending_links.pop(path, None)
    return data

def settle_generation(data):
    """Settle the generation once every requested (not backup) variant is completed or failed."""
    variants = [item for item in data['output_variants'] if item['status'] != 'on_demand']
    if all(item['status'] in ('completed', 'failed') for item in variants):
        completed = [item for item in variants if item['status'] == 'completed']
        outcome = 'completed' if completed and len(completed) == len(variants) else 'partial' if completed else 'failed'
        from backend.core.sentry_setup import STUDIO_ERROR_CODES
        jobs = {job['job_id']: job for job in data.get('jobs', [])}
        codes = set()
        for item in variants:
            if item['status'] == 'failed':
                code = item.get('error_code') or jobs.get(item.get('render_job_id'), {}).get('error_code')
                codes.add(code if isinstance(code, str) and code in STUDIO_ERROR_CODES else 'unexpected')
        if not variants:
            codes.add('validation')
        code = 'multiple' if len(codes) > 1 else next(iter(codes), None)
        if code:
            data['generation']['error_code'] = code
            data['generation']['failure_stage'] = 'render'
        else:
            data['generation'].pop('error_code', None)
            data['generation'].pop('failure_stage', None)
        if not variants:
            data['generation']['error'] = '没有自动生成的成片，可选择备选片段继续生成'
        elif completed:
            data['generation'].pop('error', None)
        data['generation'].update(status=outcome, completed_variant_count=len(completed), finished_at=now())
        data['analysis'] = {'status': 'completed' if completed else 'failed', 'phase': 'rendering', 'run_id': (data.get('analysis') or {}).get('run_id'), 'outcome': outcome, 'created_at': now(), **({'error_code': code} if code else {})}


@_serialized
def write(project_id, data, *, _recover_previous=True):
    root = directory(project_id)
    if not root.is_dir():
        raise FileNotFoundError('项目目录不存在')
    path = root / 'metadata' / 'studio.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    # Preserve content-free execution receipts in the same atomic write as business state.
    # Re-screening must not destroy an unobserved production terminal.
    previous = read(project_id, recover=_recover_previous) if path.exists() else {}
    _apply_read_receipts(path, data)
    analysis = data.get('analysis') or {}
    prior = previous.get('analysis') or {}
    if analysis.get('status') in ('awaiting_confirmation', 'completed', 'failed') and not analysis.get('run_id') and prior.get('run_id'):
        analysis['run_id'] = prior['run_id']
        analysis.setdefault('phase', prior.get('phase'))
    history = list(previous.get('analysis_history', []))
    for terminal, state in ((prior, previous), (analysis, data)):
        if terminal.get('run_id') and terminal.get('status') in ('awaiting_confirmation', 'completed', 'failed'):
            key = terminal['run_id']
            if not any(row['run_id'] == key for row in history):
                plan = state.get('plan') or {}
                summary = {k: terminal[k] for k in ('status', 'phase', 'outcome', 'duration_ms', 'error_code', 'requested_goals', 'succeeded_goals', 'failed_goals', 'result_count', 'run_id') if k in terminal}
                plan_summary = {k: plan[k] for k in ('id', 'mode', 'confirmed_analysis', 'recommended_analysis') if k in plan}
                subtitle_status = (plan.get('local_evidence') or {}).get('subtitle_status')
                if subtitle_status:
                    plan_summary['local_evidence'] = {'subtitle_status': subtitle_status}
                history.append({'run_id': key, 'finished_at': now(), 'plan': plan_summary, 'analysis': summary})
    data['analysis_history'] = history[-100:]
    tmp = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        _replace_state(tmp, path)
        _observe_worker_write(path, previous, data)
        _io_failures.pop(path, None)
    except OSError:
        _remember_io_failure(path, previous, data)
        raise
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            logger.warning('Could not remove interrupted project-state temporary file')

def change(project_id, mutate):
    with lock:
        data = read(project_id)
        result = mutate(data)
        write(project_id, data)
        return result

def save_draft(project_id, draft, *, create=False):
    def mutate(data):
        existing = next((d for d in data['drafts'] if d['id'] == draft.id), None)
        if create and existing:
            raise ConflictError('草稿已存在')
        if not create and not existing:
            raise FileNotFoundError('草稿不存在')
        if existing and existing['revision'] != draft.revision:
            raise ConflictError('草稿已在另一窗口修改，请重新加载后再保存')
        value = draft.model_dump()
        value.update(revision=existing['revision'] + 1 if existing else 1, updated_at=now())
        data['drafts'] = [d for d in data['drafts'] if d['id'] != draft.id] + [value]
        return value
    return change(project_id, mutate)


def duplicate_draft(project_id, request):
    """Fork the submitted editing snapshot without changing its saved parent or jobs."""
    from backend.services.studio.models import Draft
    def mutate(data):
        parent = next((d for d in data['drafts'] if d['id'] == request.draft.id), None)
        if parent is None:
            raise FileNotFoundError('来源草稿不存在')
        if request.draft.revision > parent['revision']:
            raise ConflictError('来源版本无效，请重新加载后再试')
        value = request.draft.model_dump()
        value.update(id=uuid.uuid4().hex, title=request.title, language=request.language,
                     revision=1, updated_at=now(), origin=parent.get('origin', 'manual'),
                     parent_draft_id=parent['id'], parent_revision=request.draft.revision)
        result = Draft.model_validate(value).model_dump()
        data['drafts'].append(result)
        return result
    return change(project_id, mutate)


def open_legacy_editor(project_id, draft, source_key, *, reuse_existing):
    """Resume the linked edit atomically; explicit new drafts never replace that link."""
    def mutate(data):
        links = data.get('legacy_editors', {})
        if reuse_existing:
            linked = next((d for d in data['drafts'] if d['id'] == links.get(source_key)), None)
            if linked is not None:
                return linked
        result = draft.model_dump()
        result.update(revision=1, updated_at=now())
        data['drafts'].append(result)
        if reuse_existing:
            data.setdefault('legacy_editors', {})[source_key] = result['id']
        return result
    return change(project_id, mutate)
