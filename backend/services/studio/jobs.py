import logging
from time import monotonic
from backend.core.sentry_setup import capture_studio_exception, studio_error_code
from copy import deepcopy
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from backend.services.studio import intelligence, store
from backend.services.studio.models import Draft, Preferences, Scene
from backend.services.studio.intelligence import analyze, make_drafts, VisionRequestError
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
    # Keep deduplication and dispatch atomic: another request must not receive
    # a queued job before we know the executor accepted it.
    with store.lock:
        added = store.change(project_id, add)
        if added['job_id'] == job['job_id']:
            try:
                executor.submit(_render, project_id, draft, job['job_id'])
            except Exception as error:
                logger.warning('Studio export dispatch failed: %s', type(error).__name__)
                capture_studio_exception(error, 'dispatch')
                message = '导出任务未能启动，请重试；已有成片已保留'
                def failed(data):
                    next(j for j in data['jobs'] if j['job_id'] == job['job_id']).update(status='failed', error=message)
                store.change(project_id, failed)
                raise ValueError(message) from None
        return {k: v for k, v in added.items() if k not in ('instance', 'snapshot')}

def _render(project_id, draft, job_id):
    started = monotonic()
    def update(**values):
        def mutate(data):
            next(j for j in data['jobs'] if j['job_id'] == job_id).update(values)
        store.change(project_id, mutate)
    try:
        update(status='running', percent=5)
        result = render_draft(project_id, source(project_id), draft, job_id, lambda p: update(percent=p))
        update(status='completed', percent=100, result=result, duration_ms=round((monotonic() - started) * 1000))
        _sync_variant_status(project_id, job_id, 'completed')
    except Exception as error:
        logger.warning('Studio render failed: %s', type(error).__name__)
        capture_studio_exception(error, 'render')
        try:
            message = str(error)[:700]
            update(status='failed', error=message, error_code=studio_error_code(error), duration_ms=round((monotonic() - started) * 1000))
            _sync_variant_status(project_id, job_id, 'failed', message)
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
        capture_studio_exception(error, 'analysis')
        message = str(error)[:700]
        diagnostics = [error.diagnostics()] if isinstance(error, VisionRequestError) else None
        def failed(data):
            data['analysis'] = {'status': 'failed', 'error': message}
            if diagnostics:
                data['analysis']['diagnostics'] = diagnostics
        try:
            store.change(project_id, failed)
            mark_project(project_id, 'completed' if store.read(project_id)['drafts'] else 'failed')
        except FileNotFoundError:
            pass

def download_progress_hook(project_id, min_interval=1.0):
    """把 yt-dlp 的下载百分比写进 analysis.percent。

    以前整段下载只显示「准备素材」，几分钟不动，用户以为卡死。音视频分两个文件下载时
    百分比会回落，只写单调递增的值；最多每秒写一次。
    """
    state = {'at': 0.0, 'percent': -1}
    def hook(d):
        if d.get('status') != 'downloading':
            return
        total = d.get('total_bytes') or d.get('total_bytes_estimate')
        if not total:
            return
        percent = min(99, int((d.get('downloaded_bytes') or 0) * 100 / total))
        now = monotonic()
        if percent <= state['percent'] or now - state['at'] < min_interval:
            return
        state.update(at=now, percent=percent)
        try:
            store.change(project_id, lambda data: data['analysis'].update(percent=percent) if data.get('analysis') else None)
        except FileNotFoundError:
            pass
    return hook

def download(project_id, url, browser):
    import yt_dlp
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    folder = store.directory(project_id) / 'raw'
    folder.mkdir(exist_ok=True)
    options = {'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]', 'outtmpl': str(folder / 'input.%(ext)s'), 'merge_output_format': 'mp4', 'noplaylist': True, 'quiet': True, 'ffmpeg_location': get_ffmpeg_path(), 'socket_timeout': 30, 'retries': 2, 'progress_hooks': [download_progress_hook(project_id)]}
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


def ensure_project_thumbnail(project_id):
    """Local uploads need the same thumbnail initialization as URL imports."""
    from backend.core.database import SessionLocal
    from backend.models.project import Project
    from backend.utils.thumbnail_generator import generate_project_thumbnail
    try:
        with SessionLocal() as db:
            project = db.get(Project, project_id)
            if project is None or project.thumbnail:
                return
        thumbnail = generate_project_thumbnail(project_id, source(project_id))
        if thumbnail:
            with SessionLocal() as db:
                project = db.get(Project, project_id)
                if project is not None and not project.thumbnail:
                    project.thumbnail = thumbnail
                    db.commit()
    except Exception:
        logger.warning('Project thumbnail generation failed', exc_info=True)


def run_content(project_id, video):
    """Run the existing content pipeline in this worker, without a second broker queue."""
    from backend.tasks.processing import process_video_pipeline
    srt = video.parent / 'input.srt'
    result = process_video_pipeline.apply(kwargs={
        'project_id': project_id, 'input_video_path': str(video),
        'input_srt_path': str(srt) if srt.exists() else None,
    }, throw=True).get()
    if not result or not result.get('success'):
        message = (result or {}).get('error') or '内容切片未完成，请检查语音与文字模型设置后重试'
        failure = (result or {}).get('result') or {}
        if failure.get('error_code'):
            from backend.pipeline.failures import PipelineFailure
            raise PipelineFailure(failure.get('stage', ''), message, code=failure['error_code'])
        raise RuntimeError(message)

    clips = result.get('result', {}).get('result', {}).get('titled_clips')
    if not clips:
        raise ValueError('没有提取到可用内容片段，请检查语音/字幕，或修改方案为精彩高光')

    return clips

def _apply_strategy(draft, strategy_id):
    """Materialize platform packaging defaults without reinterpreting content."""
    from backend.services.platform_strategy import platform_strategy
    strategy = platform_strategy(strategy_id)
    value = dict(draft)
    value.update(
        aspect=strategy.aspect,
        layout=strategy.layout if strategy.layout != 'none' else value.get('layout', 'fit'),
        subtitle_style=strategy.subtitle_style,
        title_style=strategy.title_style,
        title_motion=strategy.title_motion,
    )
    if value['title_style'] == 'editorial':
        value['title_template_version'] = max(2, value.get('title_template_version', 1))
    elif value['title_style'] == 'comic':
        value['title_template_version'] = 6
    return Draft.model_validate(value)


def _content_drafts(project_id, plan, video):
    """Create drafts once from the selected content route, before platform derivation."""
    route = plan.get('recommended_analysis', 'subtitle')
    prefs = Preferences.model_validate(plan['preferences'])
    if route == 'subtitle' or prefs.goal == 'content':
        clips = run_content(project_id, video)
        drafts = []
        for clip in clips:
            try:
                from backend.utils.text_processor import TextProcessor
                start = float(clip.get('start_time_seconds')) if clip.get('start_time_seconds') is not None else TextProcessor.time_to_seconds(clip['start_time'])
                end = float(clip.get('end_time_seconds')) if clip.get('end_time_seconds') is not None else TextProcessor.time_to_seconds(clip['end_time'])
                scene = Scene(
                    id=uuid.uuid4().hex,
                    label=str(clip.get('generated_title') or clip.get('outline') or '内容片段')[:120],
                    start=start,
                    end=end,
                )
            except (KeyError, TypeError, ValueError):
                continue
            intelligence.validate_scenes([scene], intelligence._probe(video).get('duration', 0))
            drafts.append(Draft(
                id=uuid.uuid4().hex, title=scene.label, scenes=[scene], origin='auto-content',
                language=prefs.language, aspect=prefs.aspect, layout='crop' if prefs.aspect == 'portrait' else 'fit',
                subtitles=True,
            ).model_dump())
        if not drafts:
            raise ValueError('没有提取到可渲染的内容片段，请检查字幕或重新导入')
        return drafts
    if route != 'visual':
        raise ValueError('没有可用的自动分析路径，请检查模型设置后重试')
    if not intelligence.ready():
        raise ValueError('请先在设置中配置视觉理解模型')
    events, coverage = analyze(video, prefs)
    drafts = make_drafts(events, prefs, plan.get('overrides', {}).get('instruction', ''), source_duration=intelligence._probe(video).get('duration'))
    return drafts, [event.model_dump() for event in events], coverage


def _auto_generate(project_id, plan):
    """Produce and render platform variants after the cheap screening pass."""
    started = monotonic()
    state = store.read(project_id)
    generation = state.get('generation') or {}
    platforms = generation.get('requested_platforms') or []
    branding = generation.get('branding') or {'outro_enabled': True, 'outro_version': 'v1'}
    video = source(project_id)
    skipped = []
    try:
        produced = _content_drafts(project_id, plan, video)
        if isinstance(produced, tuple):
            base_drafts, events, coverage = produced
        else:
            base_drafts, events, coverage = produced, [], None
        variants = []
        derived_drafts = []
        from backend.services.platform_strategy import platform_strategy
        for base in base_drafts:
            for strategy_id in platforms:
                strategy = platform_strategy(strategy_id)
                duration = sum(scene['end'] - scene['start'] for scene in base['scenes'])
                if strategy.duration_policy == 'long' and duration < (strategy.min_recommended_duration_sec or 0):
                    skipped.append({'strategy_id': strategy_id, 'reason': '素材没有足够完整的长内容'})
                    continue
                value = {**base, 'id': uuid.uuid4().hex, 'revision': 1}
                draft = _apply_strategy(value, strategy_id)
                derived_drafts.append(draft.model_dump())
                variant_id = uuid.uuid4().hex
                variants.append({
                    'id': variant_id, 'draft_id': draft.id, 'draft_revision': draft.revision,
                    'strategy_id': strategy_id, 'strategy_version': 1, 'branding': branding,
                    'status': 'queued', 'created_at': store.now(),
                })
        if not variants:
            raise ValueError('所选平台没有可生成的完整内容版本')
        def persist(data):
            data['drafts'].extend({**draft, 'updated_at': store.now()} for draft in derived_drafts)
            if events:
                data['events'] = events
            data['output_variants'].extend(variants)
            data['generation'].update(status='rendering', skipped=skipped, started_at=data['generation'].get('started_at') or store.now())
            data['analysis'] = {'status': 'running', 'phase': 'rendering', 'message': '正在生成可发布成片', 'created_at': store.now()}
        store.change(project_id, persist)
        for variant in variants:
            draft = next(Draft.model_validate(item) for item in derived_drafts if item['id'] == variant['draft_id'])
            job = export(project_id, draft)
            def attach(data, variant_id=variant['id'], job_id=job['job_id']):
                next(item for item in data['output_variants'] if item['id'] == variant_id)['render_job_id'] = job_id
            store.change(project_id, attach)
    except Exception as error:
        capture_studio_exception(error, 'production')
        def fail(data):
            if data.get('generation'):
                data['generation'].update(status='failed', error=str(error)[:700], skipped=skipped)
            data['analysis'] = {'status': 'failed', 'phase': 'production', 'error': str(error)[:700], 'duration_ms': round((monotonic() - started) * 1000)}
        store.change(project_id, fail)
        mark_project(project_id, 'failed')


def _sync_variant_status(project_id, job_id, status, error=None):
    def update(data):
        changed = False
        for variant in data.get('output_variants', []):
            if variant.get('render_job_id') == job_id:
                variant.update(status=status)
                if error:
                    variant['error'] = error
                changed = True
        if not changed:
            return
        variants = data['output_variants']
        if all(item['status'] in ('completed', 'failed') for item in variants):
            completed = [item for item in variants if item['status'] == 'completed']
            outcome = 'completed' if len(completed) == len(variants) else 'partial' if completed else 'failed'
            data['generation'].update(status=outcome, completed_variant_count=len(completed))
            data['analysis'] = {'status': 'completed' if completed else 'failed', 'phase': 'rendering', 'outcome': outcome, 'created_at': store.now()}
    store.change(project_id, update)


def inspect_project(project_id, options, url=None, browser=None):
    """Only ingest and screen. Expensive production requires an explicit confirmation."""
    # Reserve and dispatch together so another request cannot observe an
    # accepted task before submission succeeds. Preserve existing exports/plan.
    with store.lock:
        previous = store.read(project_id)
        if (previous.get('analysis') or {}).get('status') == 'running':
            raise ValueError('当前任务正在运行，请稍后再试')
        state = deepcopy(previous)
        state.setdefault('schema_version', 2)
        state['generation'] = {
            'requested_platforms': list(options.platforms),
            'branding': options.branding.model_dump(),
            'auto_start': options.auto_start,
            'status': 'screening',
            'created_at': store.now(),
        }
        state.setdefault('output_variants', [])
        state['analysis'] = {'status':'running', 'phase':'screening', 'message':'准备素材' if url else '快速判断适合的制作类型', 'instance':store.INSTANCE, 'created_at':store.now()}
        store.write(project_id, state)
        try:
            executor.submit(_inspect, project_id, options, url, browser)
        except Exception as error:
            logger.warning('Studio screening dispatch failed: %s', type(error).__name__)
            capture_studio_exception(error, 'dispatch')
            message = '导入任务未能启动，请重试；原素材与已有成片已保留'
            if not previous.get('analysis'):
                previous['analysis'] = {'status':'failed', 'phase':'screening', 'error':message}
            store.write(project_id, previous)
            raise ValueError(message) from None


def _inspect(project_id, options, url, browser):
    started = monotonic()
    try:
        from backend.services.studio.planning import recommend
        mark_project(project_id, 'processing', awaiting_confirmation=False)
        if url:
            download(project_id, url, browser)
        store.change(project_id, lambda data:(data['analysis'].pop('percent', None), data['analysis'].update(message='快速判断适合的制作类型')))
        plan = recommend(source(project_id), options)
        ensure_project_thumbnail(project_id)
        plan['id'] = uuid.uuid4().hex
        if options.auto_start:
            def start_automatic(data):
                data.update(plan=plan, analysis={'status': 'running', 'phase': 'production', 'message': '正在制作可发布成片', 'instance': store.INSTANCE, 'created_at': store.now()})
                data['generation'].update(status='production', started_at=store.now())
            store.change(project_id, start_automatic)
            mark_project(project_id, 'processing', creative=plan['preferences'], awaiting_confirmation=False, import_staging=False)
            try:
                executor.submit(_auto_generate, project_id, plan)
            except Exception as error:
                capture_studio_exception(error, 'dispatch')
                message = '自动制作任务未能启动，请重试；原素材已保留'
                def fail_automatic(data):
                    data['generation'].update(status='failed', error=message)
                    data['analysis'] = {'status': 'failed', 'phase': 'production', 'error': message}
                store.change(project_id, fail_automatic)
                mark_project(project_id, 'failed')
            return
        def awaiting_confirmation(data):
            data.update(plan=plan, analysis={'status':'awaiting_confirmation', 'created_at':store.now(), 'duration_ms':round((monotonic() - started) * 1000)})
            if data.get('generation'):
                data['generation']['status'] = 'awaiting_confirmation'
        store.change(project_id, awaiting_confirmation)
        mark_project(project_id, 'pending', creative=plan['preferences'], awaiting_confirmation=True)
    except Exception as error:
        logger.warning('Studio screening failed: %s', type(error).__name__)
        capture_studio_exception(error, 'screening')
        try:
            store.change(project_id, lambda data:data.update(analysis={'status':'failed','phase':'screening','error':str(error)[:700], 'error_code':studio_error_code(error), 'duration_ms':round((monotonic() - started) * 1000)}))
            mark_project(project_id, 'failed')
        except FileNotFoundError:
            pass


def confirm_project(project_id, body):
    with store.lock:
        state = store.read(project_id)
        plan = state.get('plan') or {}
        if plan.get('id') != body.plan_id or (state.get('analysis') or {}).get('status') != 'awaiting_confirmation':
            raise store.ConflictError('方案已变化或任务已开始，请刷新后确认')
        route = body.analysis_mode or plan.get('recommended_analysis', 'subtitle')
        if route == 'visual' and body.goals == ['content']:
            raise ValueError('内容切片当前使用字幕分析，请选择字幕模式后确认')
        if route == 'visual':
            from backend.services.studio import intelligence
            if not intelligence.ready():
                raise ValueError('视觉模型不可用，请配置后重新确认；原素材已保留')
        previous = deepcopy(state)
        plan['confirmed_analysis'] = route
        plan['selected_goals'] = body.goals
        plan['confirmed_at'] = store.now()
        # A confirmation override is persisted separately from the AI recommendation.
        plan['confirmed_preferences'] = {**plan['preferences'], 'goal':body.goals[0], **body.model_dump(exclude={'plan_id','goals','analysis_mode'}, exclude_none=True)}
        # Null explicitly restores automatic matching; omitted fields retain
        # import overrides for older clients. Match each output independently.
        aspect = body.aspect if 'aspect' in body.model_fields_set else plan.get('overrides', {}).get('aspect')
        plan['goal_preferences'] = {
            goal: {**plan['confirmed_preferences'], 'goal':goal,
                   'aspect':aspect or ('portrait' if goal == 'promo' else plan.get('aspect', 'original'))}
            for goal in body.goals
        }
        plan['confirmed_preferences'] = plan['goal_preferences'][body.goals[0]].copy()
        state['analysis'] = {'status':'running', 'phase':'production', 'message':'开始制作所选内容', 'instance':store.INSTANCE, 'created_at':store.now()}
        store.write(project_id, state)
        try:
            executor.submit(_produce_selected, project_id, plan)
        except Exception as error:
            logger.warning('Studio production dispatch failed: %s', type(error).__name__)
            capture_studio_exception(error, 'dispatch')
            # No worker accepted this confirmation. Preserve the exact plan and
            # staging state so an explicit retry can use the same plan ID.
            store.write(project_id, previous)
            raise ValueError('制作任务未能启动，请重试确认；原素材与已有成片已保留') from None


def _produce_selected(project_id, plan):
    from backend.services.studio import intelligence
    started = monotonic()
    succeeded_goals, failed_goals, reported = [], [], []
    result_count = 0
    labels = {'content':'内容切片','highlight':'精彩高光','promo':'推广成片'}
    errors = []
    error_codes = []
    diagnostics = []
    visual_error = None
    events = coverage = None
    subtitle_clips = None
    subtitle_error = None
    def stage(message):
        store.change(project_id, lambda data:data['analysis'].update(message=message))
    try:
        mark_project(project_id, 'processing', awaiting_confirmation=False, import_staging=False, creative=plan['confirmed_preferences'])
        video = source(project_id)
        instruction = plan.get('overrides', {}).get('instruction', '')
        for goal in plan['selected_goals']:
            try:
                prefs = Preferences.model_validate(plan.get('goal_preferences', {}).get(goal) or {**plan['confirmed_preferences'], 'goal':goal})
                stage('制作' + labels[goal])
                if goal == 'content' or plan.get('confirmed_analysis', 'subtitle') == 'subtitle':
                    if subtitle_error is not None:
                        raise subtitle_error
                    if subtitle_clips is None:
                        try:
                            subtitle_clips = run_content(project_id, video)
                        except Exception as error:
                            subtitle_error = error
                            raise
                    if goal == 'highlight':
                        from backend.services.studio.subtitle_highlights import make_highlights
                        drafts = make_highlights(subtitle_clips, prefs, intelligence._probe(video).get('duration'))
                        store.change(project_id, lambda data:data['drafts'].extend({**d,'updated_at':store.now()} for d in drafts))
                    if goal == 'promo':
                        from backend.services.studio.subtitle_promo import make_promos
                        drafts = make_promos(project_id, subtitle_clips, prefs, intelligence._probe(video).get('duration'), instruction)
                        store.change(project_id, lambda data:data['drafts'].extend({**d,'updated_at':store.now()} for d in drafts))
                    mark_project(project_id, 'processing')
                    result_count += len(subtitle_clips) if goal == 'content' else len(drafts)
                    succeeded_goals.append(goal)
                    continue
                if plan.get('confirmed_analysis', 'subtitle') != 'visual':
                    raise ValueError('此确认未授权视觉分析；请重新选择处理方式')
                if not intelligence.ready():
                    raise ValueError('请先在设置中配置视觉理解模型')
                if visual_error is not None:
                    raise visual_error
                if events is None:
                    try:
                        events, coverage = analyze(video, prefs, stage, instruction) if instruction else analyze(video, prefs, stage)
                    except Exception as error:
                        # Both visual goals share one attempt, including its failure.
                        # A second paid scan requires a new explicit user confirmation.
                        visual_error = error
                        raise
                    store.change(project_id, lambda data:data.update(events=[e.model_dump() for e in events]))
                drafts = make_drafts(events, prefs, instruction, source_duration=intelligence._probe(video).get('duration'))
                if (video.parent / 'input.srt').exists():
                    for draft in drafts:
                        draft['subtitles'] = True
                store.change(project_id, lambda data:data['drafts'].extend({**d,'updated_at':store.now()} for d in drafts))
                result_count += len(drafts)
                succeeded_goals.append(goal)
            except Exception as error:
                failed_goals.append(goal)
                error_codes.append(studio_error_code(error))
                if all(error is not previous_error for previous_error in reported):
                    capture_studio_exception(error, 'production', analysis_mode=plan.get('confirmed_analysis', 'subtitle'), goal=goal)
                    reported.append(error)
                errors.append(labels[goal] + '：' + str(error)[:500])
                if isinstance(error, VisionRequestError):
                    diagnostics.append({'goal':goal, **error.diagnostics()})
        result = {'status':'failed' if errors else 'completed', 'created_at':store.now(),
                  'outcome':'partial' if errors and succeeded_goals else 'failed' if errors else 'completed',
                  'requested_goals':plan['selected_goals'], 'succeeded_goals':succeeded_goals,
                  'failed_goals':failed_goals, 'result_count':result_count,
                  'duration_ms':round((monotonic() - started) * 1000)}
        if coverage:
            result['coverage'] = coverage
        if diagnostics:
            result['diagnostics'] = diagnostics
        if errors:
            result['error'] = '；'.join(errors)
            result['error_code'] = error_codes[0] if len(set(error_codes)) == 1 else 'multiple'
        store.change(project_id, lambda data:data.update(analysis=result))
        mark_project(project_id, 'failed' if errors else 'completed', studio_draft_count=len(store.read(project_id)['drafts']))
    except Exception as error:
        capture_studio_exception(error, 'production', analysis_mode=plan.get('confirmed_analysis', 'subtitle'))
        try:
            store.change(project_id, lambda data:data.update(analysis={'status':'failed','error':str(error)[:700],
                'error_code':studio_error_code(error), 'outcome':'partial' if succeeded_goals else 'failed', 'requested_goals':plan['selected_goals'],
                'succeeded_goals':succeeded_goals, 'failed_goals':[g for g in plan['selected_goals'] if g not in succeeded_goals],
                'result_count':result_count, 'duration_ms':round((monotonic() - started) * 1000)}))
            mark_project(project_id,'failed')
        except FileNotFoundError:
            pass
