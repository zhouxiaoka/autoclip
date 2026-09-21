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

def read(project_id: str):
    path = directory(project_id) / 'metadata' / 'studio.json'
    if not path.exists():
        return {'drafts': [], 'events': [], 'jobs': [], 'analysis': None}
    data = json.loads(path.read_text(encoding='utf-8'))
    for job in data['jobs']:
        if job['status'] in ('queued', 'running') and job.get('instance') != INSTANCE:
            job.update(status='failed', error='服务已重启，请重新导出')
    analysis = data.get('analysis')
    if analysis and analysis['status'] == 'running' and analysis.get('instance') != INSTANCE:
        analysis.update(status='failed', error='服务已重启，请重试分析')
    return data

def write(project_id, data):
    root = directory(project_id)
    if not root.is_dir():
        raise FileNotFoundError('项目目录不存在')
    path = root / 'metadata' / 'studio.json'
    path.parent.mkdir(parents=True, exist_ok=True)
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
