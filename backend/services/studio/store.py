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

from backend.core.failure_codes import UserFacingError, sentence
from backend.core.path_utils import get_projects_directory

from backend.core.file_lock import LOCK_TIMEOUT_CODE, LOCK_TIMEOUT_MESSAGE, LockTimeout, ProcessLock  # noqa: E402


def _lock_path():
    # Outside projects/: project listings must never see it.
    return Path(get_projects_directory()).parent / '.studio-store.lock'


# every project writer AND the shutdown-marker scan->delete hold this lock; it also
# excludes CLI/MCP child processes writing the same data directory (file lock with a timeout).
lock = ProcessLock(_lock_path)
_deferred_terminals = threading.local()
from backend.core.launch_token import instance_id as _shell_instance_id  # noqa: E402
INSTANCE = _shell_instance_id() or uuid.uuid4().hex  # shell-assigned when launched by the desktop app

logger = logging.getLogger(__name__)
IO_FAILURE_MESSAGE = '无法保存项目状态，请检查磁盘空间和目录权限后重试；原素材与已有成片已保留'
# A worker owned by a previous process can never finish (RC156 Win QA #13). The project
# must end failed with a readable reason, retryable through the existing analyze path.
RESTART_MESSAGE = sentence('service_restarted')
RESTART_CODE = 'service_restarted'
# Content-free terminal patches, scoped to the exact project path. A worker
# must remain retryable even when persisting its failure is also denied.
_io_failures = {}
_read_failures = {}
_pending_links = {}
_worker = ContextVar('studio_metadata_worker', default=None)
_receipt_mutex = threading.Lock()


def _append_receipt(path, receipt):
    # every append, read and clear of _read_failures holds _receipt_mutex.
    with _receipt_mutex:
        _read_failures.setdefault(path, []).append(receipt)


def _receipts(path):
    with _receipt_mutex:
        return list(_read_failures.get(path, []))


def _drop_receipts(path, handled):
    """drop only the receipts this read handled; one appended meanwhile stays."""
    ids = {id(receipt) for receipt in handled}
    with _receipt_mutex:
        left = [receipt for receipt in _read_failures.get(path, []) if id(receipt) not in ids]
        if left:
            _read_failures[path] = left
        else:
            _read_failures.pop(path, None)


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
        except LockTimeout:
            # the worker could not even write its failure. Leave a receipt WITHOUT the store
            # lock (it is what timed out); the next read fails the job instead of leaving it queued.
            _append_receipt(path, {'identity': identity, 'pending': {},
                                   'message': LOCK_TIMEOUT_MESSAGE, 'error_code': LOCK_TIMEOUT_CODE})
            raise
    finally:
        _worker.reset(token)
        if receipt['denied'] or receipt.get('cover_finished_instance'):
            with lock:
                receipt.pop('read_error', None)
                _append_receipt(path, receipt)


def mark_render_finished(project_id, job_id):
    # An accepted render has left its optional cover step. If that terminal
    # write was denied, its own receipt releases the fence when reading recovers.
    scope = _worker.get()
    if scope and scope[0] == directory(project_id) / 'metadata' / 'studio.json' and scope[1]['identity'] == ('render', job_id):
        scope[1]['cover_finished_instance'] = INSTANCE


def _apply_finished_covers(path, data):
    changed = False
    for receipt in _receipts(path):
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
    return bool(_receipts(path) or _pending_links.get(path) or _io_failures.get(path))


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


def _apply_read_receipts(path, data, receipts=None):
    changed = _apply_finished_covers(path, data)
    settle = False
    receipt_failed = False  # a render/preparation receipt failed something
    for expected, job_id in _pending_links.get(path, {}).items():
        linked = bind_render(data, expected, job_id)
        changed = changed or linked
        settle = settle or linked
    for receipt in (_receipts(path) if receipts is None else receipts):
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
                        changed = settle = receipt_failed = True
        elif kind == 'cover':
            variant = next((row for row in data['output_variants'] if row['id'] == identity[1]), {})
            cover = variant.get('cover_job') or {}
            if cover.get('job_id') == identity[2] and cover.get('status') in ('queued', 'running'):
                cover.update(status='failed', error=message, error_code=code)
                changed = True
        elif kind == 'analysis':
            analysis = data.get('analysis') or {}
            if analysis.get('run_id') == identity[1] and analysis.get('phase') == identity[2] and analysis.get('status') == 'running':
                # A refused submit never entered the phase: the stage is dispatch (the worker did not start).
                stage = 'dispatch' if receipt.get('rejected') else (identity[2] if identity[2] in ('screening', 'production') else 'other')
                analysis.update(status='failed', error=message, error_code=code)
                # the worker never got to write its failure; a receipt is a LOCAL failure, written
                # as the one snapshot (start identity kept, no upstream status).
                write_attribution(analysis, build_attribution(local=True, start_identity=analysis, failure_stage=stage))
                generation = data.get('generation') or {}
                if generation.get('status') in ('screening', 'production'):
                    generation.update(status='failed', error=message, error_code=code, finished_at=now())
                    write_attribution(generation, build_attribution(local=True, start_identity=generation, failure_stage=stage))
                changed = True
        elif kind == 'preparation':
            variant = next((row for row in data['output_variants'] if row['id'] == identity[1]), {})
            if variant.get('preparation_run_id') == identity[2] and variant.get('status') == 'preparing':
                variant.update(status='failed', error=message, error_code=code, needs_prepare=True)
                changed = settle = receipt_failed = True
        for expected in receipt['pending'].values():
            variant = next((row for row in data['output_variants'] if row['id'] == expected[0]), {})
            if variant_identity(variant) == expected and variant.get('status') == 'queued' and not variant.get('render_job_id'):
                variant.update(status='failed', error=message, error_code=code)
                changed = settle = receipt_failed = True
    if settle and data.get('generation'):
        generation = data['generation']
        was_failed = is_failed_terminal(generation)
        settle_generation(data)
        if receipt_failed and not was_failed and is_failed_terminal(generation):
            # a render/preparation that could not write its failure is a LOCAL failure of the
            # generation too, written as the one snapshot (start identity kept, no upstream status).
            for record in (generation, data.get('analysis')):  # settle wrote both terminals
                if isinstance(record, dict) and is_failed_terminal(record):
                    write_attribution(record, build_attribution(local=True, start_identity={'failure_stage': 'render', **record}))
    return changed


def remember_submission_rejection(project_id, identity, *, error_code='unexpected'):
    """A persisted reservation exists, but submit explicitly accepted no worker."""
    with lock:
        path = directory(project_id) / 'metadata' / 'studio.json'
        kind = identity[0]
        message = {'render': '导出任务未能启动，请重试；已有成片已保留',
                   'preparation': '这条成片任务未能启动，请重试；已有成片已保留',
                   'cover': 'AI 封面任务未能启动，请重试'}.get(kind, '分析或制作任务未能启动，请重试；原素材与已有成片已保留')
        _append_receipt(path, {'identity': identity, 'pending': {}, 'rejected': True, 'message': message, 'error_code': error_code})


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
        stage = analysis.get('phase') if analysis.get('phase') in ('screening', 'production') else 'render' if analysis.get('phase') == 'rendering' else 'other'
        analysis.update(status='failed', error=IO_FAILURE_MESSAGE, error_code='unexpected', failure_stage=stage)
        generation = data.get('generation') or {}
        if generation.get('status') in ('screening', 'production', 'rendering'):
            generation.update(status='failed', error=IO_FAILURE_MESSAGE, error_code='unexpected', finished_at=patch['at'], failure_stage=stage)
        changed = True
    return changed


def _serialized(fn):
    @wraps(fn)
    def run(*args, **kwargs):
        with lock:
            return fn(*args, **kwargs)
    return run


def _defer_terminals(pending):
    """Queue success-rate payloads while the store lock is held. The outermost release sends them."""
    if not pending:
        return
    queued = getattr(_deferred_terminals, 'events', None)
    if queued is None:
        _deferred_terminals.events = queued = []
    queued.extend(pending)


def _deliver_deferred_terminals():
    pending = getattr(_deferred_terminals, 'events', None)
    if not pending:
        return
    _deferred_terminals.events = None
    _post_deferred_terminals(pending)


def _post_deferred_terminals(pending):
    from backend.services.studio.terminal_outbox import accept
    accept(pending)


lock.after_release = _deliver_deferred_terminals


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
        raise UserFacingError('无效项目 ID')
    return get_projects_directory() / project_id

@_serialized
def read(project_id: str):
    path = directory(project_id) / 'metadata' / 'studio.json'
    if not path.exists():
        _io_failures.pop(path, None)
        _drop_receipts(path, _receipts(path))
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
    # every record that carries an attribution is read through export_attribution
    # legacy half identities, local records with an upstream status, failure fields on a success are
    # cleaned in what this read returns. The read itself never writes this back.
    for name in ('analysis', 'generation'):
        project_attribution(data.get(name))
    for row in data.get('analysis_history') or []:
        if isinstance(row, dict):
            project_attribution(row.get('analysis'))
    return data


@_serialized
def recover(project_id: str):
    path = directory(project_id) / 'metadata' / 'studio.json'
    data = read(project_id)
    if not path.exists() or producer_alive(data.get('generation')):
        return data  # a live CLI / MCP producer owns its run
    interrupted = set()
    prior_analysis = data.get('analysis') if isinstance(data.get('analysis'), dict) else None
    dead_instance = prior_analysis.get('instance') if _stale_analysis(prior_analysis) else None
    cover_finished = _apply_finished_covers(path, data)
    for job in data['jobs']:
        if job['status'] == 'completed' and job.get('cover_pending') and job.get('instance') != INSTANCE:
            job['cover_pending'] = False
            cover_finished = True
        if job['status'] in ('queued', 'running') and job.get('instance') != INSTANCE:
            job.update(status='failed', error=RESTART_MESSAGE, error_code=RESTART_CODE)
            interrupted.add(job.get('job_id'))
    linked = _apply_saved_render_links(data)
    abandoned_claim = False
    settle = linked
    for variant in data['output_variants']:
        cover_job = variant.get('cover_job') or {}
        if cover_job.get('status') in ('queued', 'running') and cover_job.get('instance') != INSTANCE:
            cover_job.update(status='failed', error=RESTART_MESSAGE)
            settle = True
        if variant.get('status') == 'queued' and not variant.get('render_job_id') and variant.get('render_dispatch_claimed') and variant.get('render_dispatch_instance') != INSTANCE:
            variant.update(status='failed', error=RESTART_MESSAGE, error_code=RESTART_CODE)
            variant.pop('render_dispatch_claimed', None)
            variant.pop('render_dispatch_instance', None)
            abandoned_claim = True
            settle = True
        elif variant.get('status') == 'preparing' and variant.get('instance') != INSTANCE:
            variant.update(status='failed', error=RESTART_MESSAGE, error_code=RESTART_CODE, needs_prepare=True)
            settle = True
        elif variant.get('status') in ('queued', 'running') and variant.get('render_job_id') in interrupted:
            variant.update(status='failed', error=RESTART_MESSAGE, error_code=RESTART_CODE)
            settle = True
    if settle and data.get('generation'):
        settle_generation(data)
        _record_restart_shutdown_kind(data, dead_instance)
    patched = _apply_io_failure(path, data) or linked or abandoned_claim or cover_finished or settle or bool(interrupted)
    handled = _receipts(path)
    patched = _apply_read_receipts(path, data, handled) or patched
    patched = _recover_interrupted_run(data) or patched
    analysis = data.get('analysis')
    if isinstance(analysis, dict) and analysis.get('status') == 'running' and not analysis.get('instance'):
        stage = analysis.get('phase') if analysis.get('phase') in ('screening', 'production') else 'other'
        analysis.update(status='failed', error=RESTART_MESSAGE, error_code=RESTART_CODE, failure_stage=stage, shutdown_kind='unknown')
    if patched:
        try:
            write(project_id, data)
        except OSError:
            logger.warning('Studio terminal receipt persistence deferred')
        else:
            _drop_receipts(path, handled)
            _pending_links.pop(path, None)
            if dead_instance:
                from backend.services.studio.shutdown_marker import release
                release(dead_instance)
    else:
        _drop_receipts(path, handled)
        _pending_links.pop(path, None)
    return data

def _instances_referenced(data):
    """Dead instances whose shutdown record this project's unrecovered state still needs."""
    out = set()
    analysis = data.get('analysis') if isinstance(data.get('analysis'), dict) else {}
    if analysis.get('status') == 'running' and analysis.get('instance'):
        out.add(analysis['instance'])
    for job in data.get('jobs') or []:
        if isinstance(job, dict) and job.get('status') in ('queued', 'running') and job.get('instance'):
            out.add(job['instance'])
    for variant in data.get('output_variants') or []:
        if not isinstance(variant, dict):
            continue
        if variant.get('status') == 'preparing' and variant.get('instance'):
            out.add(variant['instance'])
        if variant.get('status') == 'queued' and variant.get('render_dispatch_instance'):
            out.add(variant['render_dispatch_instance'])
    return out


def _references_instance(data, instance):
    return instance in _instances_referenced(data)


REFS_NAME = 'instance_refs.json'


def _refs_path(project_id):
    return directory(project_id) / 'metadata' / REFS_NAME


def _fsync_file(path):
    """the bytes of a file we are about to publish are on disk. Windows fsync
    (_commit) needs a writable descriptor, so open it read-write."""
    fd = os.open(path, os.O_RDWR | getattr(os, 'O_BINARY', 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_dir(directory):
    """/ a rename inside ``directory`` survives power loss (POSIX; Windows has no
    directory fsync). Returns False when durability is unknown; callers must not shrink protection."""
    if os.name == 'nt':
        return True
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return False
    try:
        os.fsync(fd)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


def _publish(path, text, encoding):
    """Write ``text`` to a temporary sibling, fsync it, atomically replace ``path``, fsync the dir."""
    tmp = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
    try:
        tmp.write_text(text, encoding=encoding)
        _fsync_file(tmp)
        _replace_state(tmp, path)
        if not _fsync_dir(path.parent):
            logger.warning('Ledger directory durability unknown')
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _ledger_content(path):
    try:
        return _read_refs(path)
    except (OSError, ValueError):
        return None


def _set_refs(path, refs):
    """Make the ledger hold exactly ``refs``. Skips only when the ledger on disk ALREADY holds them
    (compare the ledger's real content, never 'references unchanged'). Never deletes it."""
    refs = set(refs)
    if _ledger_content(path) == refs:
        return True
    try:
        _publish(path, json.dumps(sorted(refs)), 'ascii')
        return True
    except OSError:
        logger.warning('Could not update the instance reference ledger')
        return False


def _write_refs(state_path, data, previous):
    """/ the project -> instance reference ledger next to studio.json, written as a
    two-step commit around the studio.json replace:

    1. before: ledger := old ledger ∪ refs(previous) ∪ refs(new) - every reference either version of
       studio.json can hold is protected while the replace is in flight;
    2. after: ``commit_refs`` shrinks it to refs(new) once studio.json is durable; on failure
       ``rollback_refs`` sets it back to what the surviving studio.json needs.

    Returns the context ``commit_refs`` / ``rollback_refs`` take."""
    path = state_path.with_name(REFS_NAME)
    old = _ledger_content(path) or set()
    before = _instances_referenced(previous) if isinstance(previous, dict) else set()
    after = _instances_referenced(data)
    if not _set_refs(path, old | before | after):
        # prepare failed -> studio.json must not be committed (it could reference an
        # instance the ledger does not protect).
        raise LedgerPrepareError('instance reference ledger prepare failed')
    return path, old | before, after


class LedgerPrepareError(OSError):
    """the reference ledger could not be widened before a studio.json replace."""


def commit_refs(context):
    path, _surviving, after = context
    _set_refs(path, after)


def rollback_refs(context):
    path, surviving, _after = context
    _set_refs(path, surviving)


def _read_refs(path):
    value = json.loads(path.read_text(encoding='ascii'))
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError('invalid ledger')
    return set(value)


def reference_index():
    """See ``_reference_index``. the scan holds ``store.lock`` (every writer holds it too)."""
    with lock:
        return _reference_index()


def _reference_index():
    """/#198: ONE scan of every project -> the set of dead instances still referenced.

    A project contributes the references in its studio.json AND in its ledger (``instance_refs.json``).
    A project whose studio.json and ledger both cannot be read cannot be recovered either, so it
    protects nothing: a long-broken file never pins records, and pruning stays bounded at ``_KEEP``."""
    referenced = set()
    for path in get_projects_directory().glob('*/metadata/studio.json'):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                referenced |= _instances_referenced(data)
        except (OSError, ValueError):
            pass
        try:
            referenced |= _read_refs(path.with_name(REFS_NAME))
        except (OSError, ValueError):
            pass
    return frozenset(referenced)


def index_protects(index, instance):
    return instance in index


def producer_alive(generation):
    """A CLI / MCP producer process (quick_output_runner) that is still running owns the run."""
    producer = generation.get('producer') if isinstance(generation, dict) else None
    if not isinstance(producer, dict) or not isinstance(producer.get('pid'), int):
        return False
    if producer.get('pid') == os.getpid():
        return False  # this process: INSTANCE decides
    try:
        import psutil
        created = psutil.Process(producer['pid']).create_time()
    except Exception as error:  # noqa: BLE001 - NoSuchProcess / AccessDenied / missing psutil
        return type(error).__name__ == 'AccessDenied'  # inaccessible is not proof it stopped
    return abs(created - float(producer.get('created_at') or 0)) <= .01


def _stale_analysis(analysis):
    # Every running analysis records its owning process; one without an owner is not
    # provably abandoned and keeps the previous in-memory-only handling below.
    return (isinstance(analysis, dict) and analysis.get('status') == 'running'
            and bool(analysis.get('instance')) and analysis.get('instance') != INSTANCE)


def interrupted_run(data):
    """True when a previous process left this project mid-run. recover() persists that terminal; read() does not."""
    generation = data.get('generation') if isinstance(data, dict) else None
    analysis = data.get('analysis') if isinstance(data, dict) else None
    if producer_alive(generation):
        return False
    if _stale_analysis(analysis):
        return True
    # Long-video kill (RC156 #13 case 3 / c3-long): analysis may already look failed
    # (previous in-memory recovery) while generation is still in production and the
    # project index stays processing forever across restarts.
    if (isinstance(generation, dict) and generation.get('status') in ('screening', 'production')
            and generation.get('auto_start')
            and not (isinstance(analysis, dict) and analysis.get('status') == 'running'
                     and analysis.get('instance') == INSTANCE)):
        return True
    # A finished screening/production always replaces the running analysis, so only a
    # render whose last variant settled without settling the generation is left here.
    if not isinstance(generation, dict) or generation.get('status') != 'rendering' or not generation.get('auto_start'):
        return False
    if isinstance(analysis, dict) and analysis.get('status') == 'running' and analysis.get('instance') == INSTANCE:
        return False  # owned by this process: still running
    variants = [row for row in data.get('output_variants') or [] if isinstance(row, dict) and row.get('status') != 'on_demand']
    return bool(variants) and all(row.get('status') in ('completed', 'failed') for row in variants)


from backend.services.studio.failure_identity import IDENTITY_KEYS as ATTEMPT_IDENTITY_KEYS  # noqa: E402
from backend.services.studio.failure_identity import frozen as attempt_identity  # noqa: E402,F401 - one rule
from backend.services.studio.failure_identity import carry_screening  # noqa: E402


def _record_restart_shutdown_kind(data, instance):
    """/ a render settled because of a restart records how the previous process ended."""
    generation = data.get('generation') if isinstance(data.get('generation'), dict) else None
    if not instance or not generation or generation.get('status') == 'rendering':
        return
    variants = [v for v in data.get('output_variants') or [] if isinstance(v, dict)]
    if generation.get('error_code') == RESTART_CODE or any(v.get('error_code') == RESTART_CODE for v in variants):
        from backend.services.studio.shutdown_marker import shutdown_kind
        kind = shutdown_kind(instance)
        generation['shutdown_kind'] = kind
        if isinstance(data.get('analysis'), dict):
            data['analysis']['shutdown_kind'] = kind


def _recover_interrupted_run(data):
    """Close a screening/production/rendering run whose worker died with the previous process.

    Before RC156 #13 only the analysis flag flipped (in memory, never persisted), so the
    generation stayed in production and the project index showed processing (or completed)
    with no reason forever.
    """
    if not interrupted_run(data):
        return False
    analysis = data.get('analysis') if isinstance(data.get('analysis'), dict) else None
    from backend.services.studio.shutdown_marker import shutdown_kind
    kind = shutdown_kind((analysis or {}).get('instance'))
    generation = data.get('generation') if isinstance(data.get('generation'), dict) else None
    variants = [row for row in data.get('output_variants') or [] if isinstance(row, dict) and row.get('status') != 'on_demand']
    if generation and generation.get('status') == 'rendering' and variants:
        if _stale_analysis(analysis):
            for variant in variants:
                # Created but never handed to a render worker before the process ended.
                if variant.get('status') == 'queued' and not variant.get('render_job_id'):
                    variant.update(status='failed', error=RESTART_MESSAGE, error_code=RESTART_CODE)
        settle_generation(data)
        if generation.get('status') != 'rendering':
            _record_restart_shutdown_kind(data, (analysis or {}).get('instance'))
            return True
    if generation and generation.get('status') in ('screening', 'production', 'rendering') and not (generation['status'] == 'rendering' and variants):
        owned = isinstance(analysis, dict) and analysis.get('status') == 'running' and analysis.get('instance') == INSTANCE
        if owned:
            return False
        stage = generation['status']
        identity = attempt_identity(analysis, generation)
        generation.update(status='failed', error=RESTART_MESSAGE, error_code=RESTART_CODE, failure_stage=stage, finished_at=now(), shutdown_kind=kind, **identity)
        data['analysis'] = {'status': 'failed', 'phase': stage, 'run_id': (analysis or {}).get('run_id'),
                            'error': RESTART_MESSAGE, 'error_code': RESTART_CODE, 'outcome': 'failed', 'created_at': now(),
                            'failure_stage': stage, 'shutdown_kind': kind, **identity, **carry_screening(analysis, generation)}
        return True
    if analysis and _stale_analysis(analysis):
        # Manual (confirmation) flows and visual analysis persist the same catalog sentence.
        for key in ('message', 'percent', 'instance'):
            analysis.pop(key, None)
        phase = analysis.get('phase')
        stage = phase if phase in ('screening', 'production') else 'render' if phase == 'rendering' else 'other'
        analysis.update(status='failed', error=RESTART_MESSAGE, error_code=RESTART_CODE, failure_stage=stage, shutdown_kind=kind)
        return True
    return False


def settle_generation(data):
    """Settle the generation once every requested (not backup) variant is completed or failed.
    Judged only on this round's outputs (attempts.round_outputs, the same scope as the receipt): the current
    attempt's outputs plus those a variant retry redid. An older round's failure neither taints nor completes
    this round. No attempt record -> the whole workspace. An attempt that stamped nothing is not settled here."""
    from backend.services.studio import attempts
    scope = attempts.round_outputs(data)
    if scope == []:
        return  # this attempt stamped nothing; do not record it completed from other rounds
    pool = data['output_variants'] if scope is None else scope
    variants = [item for item in pool if item['status'] != 'on_demand']
    if all(item['status'] in ('completed', 'failed') for item in variants):
        completed = [item for item in variants if item['status'] == 'completed']
        outcome = 'completed' if completed and len(completed) == len(variants) else 'partial' if completed else 'failed'
        from backend.core.failure_codes import sentry_codes
        jobs = {job['job_id']: job for job in data.get('jobs', [])}
        # one primary cause via failure_attribution (PM rule), no 'multiple' (it entered the denominator).
        from backend.core.failure_attribution import rank_failures
        failures = []
        for item in variants:
            if item['status'] == 'failed':
                job = jobs.get(item.get('render_job_id'), {})
                code = item.get('error_code') or job.get('error_code')
                upstream = item.get('upstream_error_type') or job.get('upstream_error_type')
                failures.append({'error_code': code if isinstance(code, str) and code in sentry_codes() else 'unexpected',
                                 **({'upstream_error_type': upstream} if isinstance(upstream, str) and upstream else {})})
        if not variants:
            failures.append({'error_code': 'validation'})
        ranked = rank_failures(failures)
        code = ranked[0]['error_code'] if ranked else None
        secondary = {}
        if len(ranked) > 1:
            secondary = {'secondary_error_codes': [f['error_code'] for f in ranked[1:]],
                         'secondary_upstream_error_types': [f.get('upstream_error_type') or '' for f in ranked[1:]],
                         'secondary_failure_stages': ['render'] * (len(ranked) - 1)}
        for key in ('upstream_error_type', 'secondary_error_codes', 'secondary_upstream_error_types', 'secondary_failure_stages'):
            data['generation'].pop(key, None)
        if ranked and ranked[0].get('upstream_error_type'):
            data['generation']['upstream_error_type'] = ranked[0]['upstream_error_type']
        data['generation'].update(secondary)
        if code:
            data['generation']['error_code'] = code
            data['generation']['failure_stage'] = 'render'
        else:
            data['generation'].pop('error_code', None)
            data['generation'].pop('failure_stage', None)
        if not variants:
            data['generation']['error'] = '没有自动生成的成片，可选择备选片段继续生成'
        elif code == RESTART_CODE:
            # Killed mid-render (RC156 #13 case 4b, #30): the project index needs a reason, also when some
            # videos were already saved (partial), otherwise the project fails with no reason and no code.
            data['generation']['error'] = RESTART_MESSAGE
        elif completed:
            data['generation'].pop('error', None)
        elif not data['generation'].get('error'):
            reasons = [item.get('error') or jobs.get(item.get('render_job_id'), {}).get('error') for item in variants]
            reason = next((text for text in reasons if isinstance(text, str) and text), None)
            if reason:
                data['generation']['error'] = reason
        # failures outside this round (an older round's, not redone) - the results page can say
        # "this re-run succeeded, N still to redo" from this number; no separate tally.
        ids = {id(item) for item in variants}
        outside = sum(1 for item in data['output_variants'] if id(item) not in ids and item.get('status') == 'failed')
        data['generation'].update(status=outcome, completed_variant_count=len(completed), finished_at=now(), not_redone_failed_count=outside)
        error = data['generation'].get('error') if outcome == 'failed' else None
        identity = attempt_identity(data.get('analysis'), data['generation'])
        data['generation'].update(identity)
        screening = carry_screening(data.get('analysis'), data['generation'])  
        upstream = data['generation'].get('upstream_error_type')
        data['analysis'] = {**identity, **screening, 'status': 'completed' if completed else 'failed', 'phase': 'rendering', 'run_id': (data.get('analysis') or {}).get('run_id'), 'outcome': outcome, 'created_at': now(), **({'error_code': code, 'failure_stage': 'render'} if code else {}), **({'upstream_error_type': upstream} if upstream else {}), **secondary, **({'error': error} if error else {})}


def settle_attempt(data, kind='finish', previous=None, **kw):
    """The only attempt-terminal writer. A second call does not rewrite a terminal. ``seal`` queues the success-rate event."""
    from backend.services.studio import attempts
    if kind == 'seal':
        return attempts.note_settled_terminals(data, previous)
    if kw.get('guard') and not kw['guard'](data):
        return False
    generation = data.get('generation') if isinstance(data.get('generation'), dict) else None
    terminal = bool(generation and generation.get('status') in attempts.TERMINAL)
    if kind == 'finish':
        return (not generation or generation.get('status') not in ('completed', 'failed')) and (settle_generation(data) or True)
    if kind == 'reject':
        target = next((item for item in data.get('output_variants') or [] if item.get('id') == kw.get('variant_id')), None)
        expected = kw.get('expected')
        if not target or target.get('status') != 'queued' or target.get('render_job_id') or (expected is not None and variant_identity(target) != expected):
            return False
        target.update(status='failed', error=kw.get('error'), error_code=kw.get('error_code'))
        target.pop('render_dispatch_claimed', None); target.pop('render_dispatch_instance', None)
        if not terminal:
            settle_generation(data)
        return True
    if kind == 'screen':
        analysis = data.get('analysis') if isinstance(data.get('analysis'), dict) else {}
        if analysis.get('status') == 'failed' and (not generation or not generation.get('auto_start') or terminal):
            return False
        data['analysis'] = kw['failure']
        if generation and generation.get('auto_start') and not terminal:
            generation.update(status='failed', error=kw['failure'].get('error'), error_code=kw['failure'].get('error_code'), finished_at=now(), **(kw.get('context') or {}))
        return True
    if kind == 'production':
        current = data.get('analysis') if isinstance(data.get('analysis'), dict) else {}
        if current.get('phase') in ('production', 'rendering') and current.get('status') in ('completed', 'failed', 'partial'):
            return False
        data['analysis'] = {**attempt_identity(current, generation), **kw['analysis']}
        return True
    if kind != 'fail' or terminal:
        return False
    context = {**(kw.get('context') or {}), **(attempt_identity(data.get('analysis'), generation) if kw.get('identify', True) else {})}
    extra = {**(kw.get('route') or {}), **({} if kw.get('skipped') is None else {'skipped': kw['skipped']}), **({} if not kw.get('failure_stage') else {'failure_stage': kw['failure_stage']})}
    if generation:
        generation.update(status='failed', error=kw.get('error'), error_code=kw.get('error_code'), finished_at=now(), **{**context, **extra})
    screening = carry_screening(data.get('analysis'), generation) if kw.get('carry', True) else {}
    data['analysis'] = {**( {} if kw.get('identify', True) else attempt_identity(data.get('analysis'), generation)), 'status': 'failed', 'phase': kw.get('phase') or 'production', 'run_id': kw['run_id'] if 'run_id' in kw else (data.get('analysis') or {}).get('run_id'), 'error': kw.get('error'), 'error_code': kw.get('error_code'), **({} if kw.get('duration_ms') is None else {'duration_ms': kw['duration_ms']}), **({} if not kw.get('failure_stage') else {'failure_stage': kw['failure_stage']}), **context, **screening}
    return True


@_serialized
def write(project_id, data, *, restore=False):
    """``restore=True`` ``data`` is a state read earlier, written back as is to undo a
    reservation nobody accepted (a rejected dispatch). It is not a state transition: no attribution
    snapshot is stamped and every record keeps the attribution group it carries."""
    from backend.core.project_cancellation import checkpoint
    checkpoint(project_id)
    root = directory(project_id)
    if not root.is_dir():
        raise FileNotFoundError('项目目录不存在')
    path = root / 'metadata' / 'studio.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    # Preserve content-free execution receipts in the same atomic write as business state.
    # Re-screening must not destroy an unobserved production terminal.
    previous = read(project_id) if path.exists() else {}
    _apply_read_receipts(path, data)
    _ensure_failure_identity(data)
    usage_checkpoint = _attach_run_telemetry(data, project_id, previous, restore=restore)
    analysis = data.get('analysis') or {}
    prior = previous.get('analysis') or {}
    if analysis.get('status') in ('awaiting_confirmation', 'completed', 'failed') and not analysis.get('run_id') and prior.get('run_id'):
        analysis['run_id'] = prior['run_id']
        analysis.setdefault('phase', prior.get('phase'))
    # settle only after the terminal identity (run_id/phase) and the run telemetry are complete - the
    # worker's terminal write inherits run_id/phase above. The one place a receipt settles (same atomic write).
    from backend.services.studio import attempts
    attempts.reconcile(data, now())
    pending = settle_attempt(data, kind='seal', previous=previous) if not restore else []
    history = list(previous.get('analysis_history', []))
    for terminal, state in ((prior, previous), (analysis, data)):
        if terminal.get('run_id') and terminal.get('status') in ('awaiting_confirmation', 'completed', 'failed'):
            key = terminal['run_id']
            if not any(row['run_id'] == key for row in history):
                plan = state.get('plan') or {}
                summary = {k: terminal[k] for k in ('status', 'phase', 'outcome', 'duration_ms', 'error_code', 'requested_goals', 'succeeded_goals', 'failed_goals', 'result_count', 'run_id', 'screening_identity', 'shutdown_kind', 'secondary_error_codes', 'secondary_upstream_error_types', 'secondary_failure_stages') if k in terminal}
                summary.update(export_attribution(terminal))  # / THE serializer (stage/status/upstream)
                plan_summary = {k: plan[k] for k in ('id', 'mode', 'confirmed_analysis', 'recommended_analysis', 'degrade_reason') if k in plan}
                subtitle_status = (plan.get('local_evidence') or {}).get('subtitle_status')
                if subtitle_status:
                    plan_summary['local_evidence'] = {'subtitle_status': subtitle_status}
                history.append({'run_id': key, 'finished_at': now(), 'plan': plan_summary, 'analysis': summary})
    data['analysis_history'] = history[-100:]
    tmp = path.with_suffix('.' + uuid.uuid4().hex + '.tmp')
    refs = None
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        _fsync_file(tmp)  
        refs = _write_refs(path, data, previous if path.exists() else None)
        _replace_state(tmp, path)
        if _fsync_dir(path.parent):
            commit_refs(refs)  # release only after studio.json is durable
        else:
            # replaced but durability unknown -> keep the union until a durable write.
            logger.warning('Project state directory durability unknown; reference ledger kept')
        if usage_checkpoint is not None:
            usage_checkpoint[0].update(usage_checkpoint[1])
        _observe_worker_write(path, previous, data)
        _io_failures.pop(path, None)
        _defer_terminals(pending)  # send after the outermost lock release, never while this write holds it
    except OSError:
        if refs is not None:
            rollback_refs(refs)  # the surviving studio.json keeps its references protected
        _remember_io_failure(path, previous, data)
        raise
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            logger.warning('Could not remove interrupted project-state temporary file')

def _ensure_failure_identity(data):
    """failed/partial records always carry a known error_code and failure_stage."""
    from backend.core.llm_telemetry import FAILURE_STAGES, normalize_failure_stage
    from backend.core.failure_codes import stored_codes
    valid = stored_codes()
    generation = data.get('generation') if isinstance(data.get('generation'), dict) else None
    analysis = data.get('analysis') if isinstance(data.get('analysis'), dict) else None
    hint = None
    if analysis:
        hint = normalize_failure_stage(analysis.get('failure_stage') or analysis.get('phase'))
    if not hint and generation:
        hint = normalize_failure_stage(generation.get('failure_stage') or generation.get('status'))
    default = hint or 'production'

    def fill(record):
        if not isinstance(record, dict) or record.get('status') not in ('failed', 'partial'):
            return
        code = record.get('error_code')
        if not (isinstance(code, str) and code in valid):
            record['error_code'] = 'unexpected'
        if record.get('failure_stage') not in FAILURE_STAGES:
            record['failure_stage'] = normalize_failure_stage(
                record.get('failure_stage') or record.get('phase') or default
            ) or default

    fill(generation)
    fill(analysis)


from backend.core.failure_attribution import (  # noqa: E402 - - the one attribution rule
    ATTRIBUTION_FIELDS, FAILURE_FIELDS, IDENTITY_FIELDS, build_attribution,
    SNAPSHOT_FIELDS, export_attribution, has_snapshot, is_failed_terminal, project_attribution,
    write_attribution)


def _paired(record):
    return all(isinstance(record.get(k), str) and record[k] for k in ATTEMPT_IDENTITY_KEYS)


def _apply_attribution(record, failed, newly_failed, prior=None):
    """the store only writes the snapshot it is given, replaced whole; it never infers
    "the same failure" from run_id/error_code or any other field value. a snapshot is stamped
    only on a record that became failed IN THIS WRITE (``newly_failed``: the state transition, see
    ``_attach_run_telemetry``); an error in hand during an unrelated write never touches it.

    - newly failed, with an error in hand: the snapshot of THAT error replaces the group (an error that
      carries a boundary snapshot gets it back unchanged; otherwise THE factory builds it from the error,
      the phase identity, the job's own failure stage and, for local, the attempt's start identity);
    - newly failed with no error in hand (a receipt that already wrote its own snapshot): the group the
      record carries stays exactly as it is;
    - failed before this write and still the same attempt the STORED group (``prior``) is
      carried forward whole, even when the writer rebuilt the record dict (no inference: copied as is);
    - not failed: failure fields go; the identity recorded at attempt start stays, else the phase one."""
    from backend.core.llm_emit import attribution_snapshot, failure_now
    if failed:
        if not newly_failed:
            if has_snapshot(prior):
                for key in SNAPSHOT_FIELDS:
                    record.pop(key, None)
                record.update({k: prior[k] for k in SNAPSHOT_FIELDS if k in prior})
            return
        if failure_now() is None:
            return
        snap = attribution_snapshot(start_identity=record)  # the job's own stage rides on the record
        if snap is not None:
            write_attribution(record, snap)
        return
    for key in FAILURE_FIELDS:
        record.pop(key, None)
    if _paired(record):
        return
    for key in IDENTITY_FIELDS:
        record.pop(key, None)
    snap = attribution_snapshot()
    if snap is not None and snap.provider:
        record.update({k: v for k, v in export_attribution(snap).items() if k in IDENTITY_FIELDS})
        record['attribution_source'] = snap.attribution_source


def _attach_run_telemetry(data, project_id, previous, *, restore=False):
    try:
        from backend.core.llm_emit import run_usage_checkpoint
        from backend.core.llm_telemetry import run_snapshot
        snapshot = run_snapshot(project_id)
        checkpoint = run_usage_checkpoint()
    except Exception:  # noqa: BLE001 - telemetry cannot block a state write
        return
    if not snapshot:
        return
    usage_keys = {'llm_calls', 'prompt_tokens', 'completion_tokens', 'reasoning_tokens', 'degrade_count', 'retry_count'}
    persisted = {}
    for name in ('generation', 'analysis'):
        record = data.get(name)
        if not isinstance(record, dict):
            continue
        prior = previous.get(name) or {}
        identity_key = 'created_at' if name == 'generation' else 'run_id'
        identity = record.get(identity_key)
        if name == 'generation' and not identity:
            identity = (data.get('analysis') or {}).get('run_id')
            prior_identity = (previous.get('analysis') or {}).get('run_id')
        else:
            prior_identity = prior.get(identity_key)
        usage_id = (project_id, name, identity)
        counted = checkpoint.get(usage_id, {}) if checkpoint is not None else {}
        failed = bool(is_failed_terminal(record))
        # the transition, judged inside this one serialized write against the record as stored
        # non-failed -> failed, or a failed record of ANOTHER attempt (run identity changed). Status and
        # identity only; never error_code (no "same failure" inference, ).
        newly_failed = failed and not (is_failed_terminal(prior) and prior_identity == identity)
        if not restore:  # a rollback write is not a transition; its records keep their groups
            _apply_attribution(record, failed, newly_failed, prior)
        for key, value in snapshot.items():
            if value is None or key in ATTRIBUTION_FIELDS or key == 'attribution_source':
                continue
            if key == 'billable_calls_before_failure':
                if failed and record.get(key) in (None, ''):
                    record[key] = value
                continue
            if key in usage_keys and checkpoint is not None and identity:
                base = (prior.get(key) or 0) if prior_identity == identity else 0
                record[key] = base + value - counted.get(key, 0)
            elif key == 'retry_count' and not snapshot.get('llm_calls') and prior_identity == identity:
                record[key] = prior.get(key) or value
            else:
                record[key] = value
        if not failed:
            record.pop('billable_calls_before_failure', None)
        persisted[usage_id] = {key: snapshot[key] for key in usage_keys if key in snapshot}
    return (checkpoint, persisted) if checkpoint is not None else None


def change(project_id, mutate):
    from backend.core.project_cancellation import checkpoint
    checkpoint(project_id)  # deleted mid-run: stop before mutating a state that no longer exists
    with lock:
        data = recover(project_id)  # repair at the explicit write, not during read
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
