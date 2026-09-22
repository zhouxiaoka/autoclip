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
        def stage(message):
            store.change(project_id, lambda data: data['analysis'].update(message=message))
        instruction = getattr(prefs, 'instruction', '')
        from backend.services.studio import intelligence
        if not intelligence.ready():
            raise ValueError('此方案需要视觉模型，请在设置中配置后重试；原素材已保留')
        events, coverage = analyze(video, prefs, stage, instruction) if instruction else analyze(video, prefs, stage)
        stage('组织推广开头与成片草稿' if prefs.goal == 'promo' else '整理高光成片草稿')
        drafts = make_drafts(events, prefs, instruction, source_duration=intelligence._probe(video).get('duration'))
        if (video.parent / 'input.srt').exists():
            for draft in drafts:
                draft['subtitles'] = True
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


def run_content(project_id, video):
    """Run the existing content pipeline in this worker, without a second broker queue."""
    from backend.tasks.processing import process_video_pipeline
    srt = video.parent / 'input.srt'
    result = process_video_pipeline.apply(kwargs={
        'project_id': project_id, 'input_video_path': str(video),
        'input_srt_path': str(srt) if srt.exists() else None,
    }, throw=True).get()
    if not result or not result.get('success'):
        raise RuntimeError((result or {}).get('error') or '内容切片未完成，请检查语音与文字模型设置后重试')

    if not result.get('result', {}).get('result', {}).get('titled_clips'):
        raise ValueError('没有提取到可用内容片段，请检查语音/字幕，或修改方案为精彩高光')


def inspect_project(project_id, options, url=None, browser=None):
    """Only ingest and screen. Expensive production requires an explicit confirmation."""
    def begin(data):
        if (data.get('analysis') or {}).get('status') == 'running':
            raise ValueError('当前任务正在运行，请稍后再试')
        data['analysis'] = {'status':'running', 'phase':'screening', 'message':'准备素材' if url else '快速判断适合的制作类型', 'instance':store.INSTANCE, 'created_at':store.now()}
    store.change(project_id, begin)
    executor.submit(_inspect, project_id, options, url, browser)


def _inspect(project_id, options, url, browser):
    try:
        from backend.services.studio.planning import recommend
        mark_project(project_id, 'processing', awaiting_confirmation=False)
        if url:
            download(project_id, url, browser)
        store.change(project_id, lambda data:data['analysis'].update(message='快速判断适合的制作类型'))
        plan = recommend(source(project_id), options)
        plan['id'] = uuid.uuid4().hex
        store.change(project_id, lambda data:data.update(plan=plan, analysis={'status':'awaiting_confirmation', 'created_at':store.now()}))
        mark_project(project_id, 'pending', creative=plan['preferences'], awaiting_confirmation=True)
    except Exception as error:
        logger.warning('Studio screening failed: %s', type(error).__name__)
        try:
            store.change(project_id, lambda data:data.update(analysis={'status':'failed','phase':'screening','error':str(error)[:700]}))
            mark_project(project_id, 'failed')
        except FileNotFoundError:
            pass


def confirm_project(project_id, body):
    with store.lock:
        state = store.read(project_id)
        plan = state.get('plan') or {}
        if plan.get('id') != body.plan_id or (state.get('analysis') or {}).get('status') != 'awaiting_confirmation':
            raise store.ConflictError('方案已变化或任务已开始，请刷新后确认')
        plan['selected_goals'] = body.goals
        plan['confirmed_at'] = store.now()
        # A confirmation override is persisted separately from the AI recommendation.
        plan['confirmed_preferences'] = {**plan['preferences'], 'goal':body.goals[0], **body.model_dump(exclude={'plan_id','goals'}, exclude_none=True)}
        state['analysis'] = {'status':'running', 'phase':'production', 'message':'开始制作所选内容', 'instance':store.INSTANCE, 'created_at':store.now()}
        store.write(project_id, state)
        mark_project(project_id, 'processing', awaiting_confirmation=False, import_staging=False, creative=plan['confirmed_preferences'])
        executor.submit(_produce_selected, project_id, plan)


def _produce_selected(project_id, plan):
    from backend.services.studio import intelligence
    labels = {'content':'内容切片','highlight':'精彩高光','promo':'推广成片'}
    errors = []
    events = coverage = None
    def stage(message):
        store.change(project_id, lambda data:data['analysis'].update(message=message))
    try:
        video = source(project_id)
        instruction = plan.get('overrides', {}).get('instruction', '')
        for goal in plan['selected_goals']:
            try:
                prefs = Preferences.model_validate({**plan['confirmed_preferences'], 'goal':goal})
                stage('制作' + labels[goal])
                if goal == 'content':
                    run_content(project_id, video)
                    mark_project(project_id, 'processing')
                    continue
                if not intelligence.ready():
                    raise ValueError('请先在设置中配置视觉理解模型')
                if events is None:
                    events, coverage = analyze(video, prefs, stage, instruction) if instruction else analyze(video, prefs, stage)
                    store.change(project_id, lambda data:data.update(events=[e.model_dump() for e in events]))
                drafts = make_drafts(events, prefs, instruction, source_duration=intelligence._probe(video).get('duration'))
                if (video.parent / 'input.srt').exists():
                    for draft in drafts:
                        draft['subtitles'] = True
                store.change(project_id, lambda data:data['drafts'].extend({**d,'updated_at':store.now()} for d in drafts))
            except Exception as error:
                errors.append(labels[goal] + '：' + str(error)[:500])
        result = {'status':'failed' if errors else 'completed', 'created_at':store.now()}
        if coverage:
            result['coverage'] = coverage
        if errors:
            result['error'] = '；'.join(errors)
        store.change(project_id, lambda data:data.update(analysis=result))
        mark_project(project_id, 'failed' if errors else 'completed', studio_draft_count=len(store.read(project_id)['drafts']))
    except Exception as error:
        try:
            store.change(project_id, lambda data:data.update(analysis={'status':'failed','error':str(error)[:700]}))
            mark_project(project_id,'failed')
        except FileNotFoundError:
            pass
