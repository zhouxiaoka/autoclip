"""Atomic project-local JSON storage; no migration of legacy clips/collections."""
import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.core.path_utils import get_projects_directory

lock = threading.RLock()
INSTANCE = uuid.uuid4().hex

class ConflictError(ValueError):
    pass

def now():
    return datetime.now(timezone.utc).isoformat()

def directory(project_id: str) -> Path:
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', project_id):
        raise ValueError('无效项目 ID')
    return get_projects_directory() / project_id

def read(project_id: str, *, recover: bool = True):
    path = directory(project_id) / 'metadata' / 'studio.json'
    if not path.exists():
        return {'schema_version': 2, 'drafts': [], 'events': [], 'jobs': [], 'analysis': None, 'output_variants': []}
    data = json.loads(path.read_text(encoding='utf-8'))
    data.setdefault('schema_version', 1)
    data.setdefault('drafts', [])
    data.setdefault('events', [])
    data.setdefault('jobs', [])
    data.setdefault('output_variants', [])
    if not recover:
        # CLI status commands are observers in another process, not a server restart.
        return data
    interrupted = set()
    for job in data['jobs']:
        if job['status'] in ('queued', 'running') and job.get('instance') != INSTANCE:
            job.update(status='failed', error='服务已重启，请重新导出')
            interrupted.add(job.get('job_id'))
    settle = False
    for variant in data['output_variants']:
        cover_job = variant.get('cover_job') or {}
        if cover_job.get('status') in ('queued', 'running') and cover_job.get('instance') != INSTANCE:
            cover_job.update(status='failed', error='服务已重启，请重新生成封面')
        if variant.get('status') == 'preparing' and variant.get('instance') != INSTANCE:
            variant.update(status='failed', error='服务已重启，请重试这条', needs_prepare=True)
            settle = True
        elif variant.get('status') in ('queued', 'running') and variant.get('render_job_id') in interrupted:
            # The app closed mid-render: the version becomes retryable instead of queued forever.
            variant.update(status='failed', error='服务已重启，请重试这条')
            settle = True
    if settle and data.get('generation'):
        settle_generation(data)
    analysis = data.get('analysis')
    if analysis and analysis['status'] == 'running' and analysis.get('instance') != INSTANCE:
        analysis.update(status='failed', error='服务已重启，请重试分析')
    return data

def settle_generation(data):
    """Settle the generation once every requested (not backup) variant is completed or failed."""
    variants = [item for item in data['output_variants'] if item['status'] != 'on_demand']
    if all(item['status'] in ('completed', 'failed') for item in variants):
        completed = [item for item in variants if item['status'] == 'completed']
        outcome = 'completed' if completed and len(completed) == len(variants) else 'partial' if completed else 'failed'
        if not variants:
            data['generation']['error'] = '没有自动生成的成片，可选择备选片段继续生成'
        elif completed:
            data['generation'].pop('error', None)
        data['generation'].update(status=outcome, completed_variant_count=len(completed), finished_at=now())
        data['analysis'] = {'status': 'completed' if completed else 'failed', 'phase': 'rendering', 'run_id': (data.get('analysis') or {}).get('run_id'), 'outcome': outcome, 'created_at': now()}


def write(project_id, data):
    root = directory(project_id)
    if not root.is_dir():
        raise FileNotFoundError('项目目录不存在')
    path = root / 'metadata' / 'studio.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    # Preserve content-free execution receipts in the same atomic write as business state.
    # Re-screening must not destroy an unobserved production terminal.
    previous = read(project_id) if path.exists() else {}
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
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)

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
