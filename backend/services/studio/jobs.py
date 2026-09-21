import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from backend.services.studio import store
from backend.services.studio.models import Draft, Preferences
from backend.services.studio.intelligence import analyze, make_drafts
from backend.services.studio.render import render_draft

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='studio')


def source(project_id):
    from backend.services.publish_export import find_source_video
    return find_source_video(project_id)

def export(project_id, draft):
    job = {'job_id': uuid.uuid4().hex, 'status': 'queued', 'percent': 0, 'draft_id': draft.id, 'title': draft.title, 'revision': draft.revision, 'created_at': store.now(), 'instance': store.INSTANCE, 'snapshot': draft.model_dump()}
    def add(data):
        active = next((j for j in data['jobs'] if j['status'] in ('queued', 'running') and j.get('snapshot') == job['snapshot']), None)
        if active:
            return active
        if sum(j['status'] in ('queued', 'running') for j in data['jobs']) >= 3:
            raise ValueError('已有 3 个导出任务，请等待完成后再提交')
        data['jobs'].insert(0, job)
        return job
    added = store.change(project_id, add)
    if added['job_id'] == job['job_id']:
        executor.submit(_render, project_id, draft, job['job_id'])
    return {k: v for k, v in added.items() if k not in ('instance', 'snapshot')}

def _render(project_id, draft, job_id):
    def update(**values):
        def mutate(data):
            next(j for j in data['jobs'] if j['job_id'] == job_id).update(values)
        store.change(project_id, mutate)
    try:
        update(status='running', percent=5)
        result = render_draft(project_id, source(project_id), draft, job_id, lambda p: update(percent=p))
        update(status='completed', percent=100, result=result)
    except Exception as error:
        logger.warning('Studio render failed: %s', type(error).__name__)
        try:
            update(status='failed', error=str(error)[:700])
        except FileNotFoundError:
            pass

def analyze_project(project_id, prefs, url=None, browser=None):
    def begin(data):
        if (data.get('analysis') or {}).get('status') == 'running':
            raise ValueError('视觉分析正在运行')
        data['analysis'] = {'status': 'running', 'message': '下载素材' if url else '理解画面', 'instance': store.INSTANCE, 'created_at': store.now()}
    store.change(project_id, begin)
    executor.submit(_analyze, project_id, prefs, url, browser)

def mark_project(project_id, status, **config):
    from backend.core.database import SessionLocal
    from backend.models.project import Project, ProjectStatus
    with SessionLocal() as db:
        p = db.query(Project).filter(Project.id == project_id).first()
        if p:
            p.status = ProjectStatus(status)
            p.processing_config = {**(p.processing_config or {}), **config}
            if status == 'completed':
                from datetime import datetime, timezone
                p.completed_at = datetime.now(timezone.utc)
            db.commit()

def _analyze(project_id, prefs, url, browser):
    try:
        mark_project(project_id, 'processing')
        if url:
            download(project_id, url, browser)
        video = source(project_id)
        def thinking(data):
            data['analysis'].update(message='识别高光与组织成片')
        store.change(project_id, thinking)
        events, coverage = analyze(video, prefs)
        drafts = make_drafts(events, prefs)
        def complete(data):
            data['events'] = [e.model_dump() for e in events]
            data['drafts'].extend({**d, 'updated_at': store.now()} for d in drafts)
            data['analysis'] = {'status': 'completed', 'coverage': coverage, 'created_at': store.now()}
        store.change(project_id, complete)
        mark_project(project_id, 'completed', studio_draft_count=len(store.read(project_id)['drafts']))
    except Exception as error:
        logger.warning('Studio analysis failed: %s', type(error).__name__)
        def failed(data):
            data['analysis'] = {'status': 'failed', 'error': str(error)[:700]}
        try:
            store.change(project_id, failed)
            mark_project(project_id, 'completed' if store.read(project_id)['drafts'] else 'failed')
        except FileNotFoundError:
            pass

def download(project_id, url, browser):
    import yt_dlp
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    folder = store.directory(project_id) / 'raw'
    folder.mkdir(exist_ok=True)
    options = {'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]', 'outtmpl': str(folder / 'input.%(ext)s'), 'merge_output_format': 'mp4', 'noplaylist': True, 'quiet': True, 'ffmpeg_location': get_ffmpeg_path(), 'socket_timeout': 30, 'retries': 2}
    if browser:
        options['cookiesfrombrowser'] = (browser,)
    with yt_dlp.YoutubeDL(options) as downloader:
        downloader.download([url])
    from backend.core.database import SessionLocal
    from backend.models.project import Project
    from backend.utils.thumbnail_generator import generate_project_thumbnail
    video = source(project_id)
    with SessionLocal() as db:
        p = db.query(Project).filter(Project.id == project_id).first()
        if not p:
            raise FileNotFoundError('项目已删除')
        p.video_path = str(video)
        p.thumbnail = generate_project_thumbnail(project_id, video)
        db.commit()
