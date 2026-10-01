import json
import logging
import shutil
from time import monotonic, sleep
from backend.core.sentry_setup import capture_studio_exception, studio_error_code
from copy import deepcopy
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from backend.core import llm_usage
from backend.services.studio import audio, intelligence, store
from backend.services.studio.models import Draft, Preferences, Scene
from backend.services.studio.intelligence import analyze, make_drafts, VisionRequestError
from backend.services.studio.render import render_draft

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='studio')
# Local encodes are CPU-bound: run one at a time on its own worker so screening and
# analysis of other imports never wait behind a render queue.
render_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='studio-render')


def source(project_id):
    from backend.services.publish_export import find_source_video
    return find_source_video(project_id)

def export(project_id, draft, *, brand_outro=False):
    job = {'job_id': uuid.uuid4().hex, 'status': 'queued', 'percent': 0, 'draft_id': draft.id, 'title': draft.title, 'revision': draft.revision, 'brand_outro': brand_outro, 'created_at': store.now(), 'instance': store.INSTANCE, 'snapshot': draft.model_dump()}
    def add(data):
        active = next((j for j in data['jobs'] if j['status'] in ('queued', 'running') and j.get('snapshot') == job['snapshot']), None)
        if active:
            return active
        data['jobs'].insert(0, job)
        return job
    # Keep deduplication and dispatch atomic: another request must not receive
    # a queued job before we know the executor accepted it.
    with store.lock:
        added = store.change(project_id, add)
        if added['job_id'] == job['job_id']:
            try:
                if brand_outro:
                    render_executor.submit(_render, project_id, draft, job['job_id'], brand_outro=True)
                else:
                    render_executor.submit(_render, project_id, draft, job['job_id'])
            except Exception as error:
                logger.warning('Studio export dispatch failed: %s', type(error).__name__)
                capture_studio_exception(error, 'dispatch')
                message = '导出任务未能启动，请重试；已有成片已保留'
                def failed(data):
                    next(j for j in data['jobs'] if j['job_id'] == job['job_id']).update(status='failed', error=message)
                store.change(project_id, failed)
                raise ValueError(message) from None
        return {k: v for k, v in added.items() if k not in ('instance', 'snapshot')}

def _tracked(stage):
    """Record model token usage of a studio job (first argument: project id) under `stage`."""
    def wrap(fn):
        from functools import wraps

        @wraps(fn)
        def run(project_id, *args, **kwargs):
            with llm_usage.tracking(project_id), llm_usage.stage(stage):
                return fn(project_id, *args, **kwargs)
        return run
    return wrap


@_tracked('render')
def _render(project_id, draft, job_id, *, brand_outro=False):
    started = monotonic()
    def update(**values):
        def mutate(data):
            next(j for j in data['jobs'] if j['job_id'] == job_id).update(values)
        store.change(project_id, mutate)
    try:
        update(status='running', percent=5)
        result = render_draft(project_id, source(project_id), draft, job_id, lambda p: update(percent=p), brand_outro=brand_outro)
        update(status='completed', percent=100, result=result, duration_ms=round((monotonic() - started) * 1000))
        _design_covers(project_id, draft, job_id)
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

@_tracked('visual_analysis')
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
    from backend.utils.ffmpeg_utils import get_ffmpeg_path, ytdlp_js_runtimes
    folder = store.directory(project_id) / 'raw'
    folder.mkdir(exist_ok=True)
    options = {'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]', 'outtmpl': str(folder / 'input.%(ext)s'), 'merge_output_format': 'mp4', 'noplaylist': True, 'quiet': True, 'ffmpeg_location': get_ffmpeg_path(), 'socket_timeout': 30, 'retries': 2, 'progress_hooks': [download_progress_hook(project_id)], **ytdlp_js_runtimes()}
    if browser:
        options['cookiesfrombrowser'] = (browser,)
    from backend.utils.download_recovery import download_with_recovery
    download_with_recovery(url, {**options, 'writeinfojson': True})
    # Public listing text only: packaging checks nameplate names against it instead of guessing.
    info_path = folder / 'input.info.json'
    try:
        info = json.loads(info_path.read_text(encoding='utf-8')) if info_path.exists() else {}
    except (OSError, ValueError):
        info = {}
    finally:
        info_path.unlink(missing_ok=True)
    meta = {key: str(info.get(field) or '')[:300] for key, field in (('title', 'title'), ('channel', 'channel'))}
    height = _ensure_source_resolution(url, options, info, folder)
    if height:
        meta['source_height'] = height
    if _fetch_platform_subtitles(url, options, info, folder):
        meta['subtitle_source'] = 'platform'
    store.change(project_id, lambda data: data.update(source_meta=meta))
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


MIN_SOURCE_HEIGHT = 720
# Clients tried when YouTube serves only low-resolution formats to the default one
# (its SABR streaming experiment drops the URLs of every format above 360p for some sessions).
RETRY_CLIENTS = (['web_safari'], ['web_embedded'], ['tv'])


def _video_height(path):
    from backend.services.publish_export import _probe
    try:
        return int(_probe(path).get('height') or 0)
    except Exception:  # noqa: BLE001
        return 0


def _ensure_source_resolution(url, options, info, folder):
    """Re-download with another YouTube client when the file is far below what the video offers.

    A 360p source cropped to 1080×1920 is unusable; the listing usually still offers 1080p.
    Returns the final source height (0 when unknown).
    """
    try:
        current = source_path = next(p for p in folder.glob('input.*') if p.suffix.lower() in ('.mp4', '.mkv', '.webm', '.mov'))
    except StopIteration:
        return 0
    height = _video_height(current)
    offered = max((f.get('height') or 0 for f in info.get('formats') or [] if f.get('vcodec') not in (None, 'none')), default=0)
    want = min(MIN_SOURCE_HEIGHT, offered or MIN_SOURCE_HEIGHT)
    youtube = 'youtube.com' in url or 'youtu.be' in url
    if not youtube or not height or height >= want:
        return height
    from backend.utils.download_recovery import download_with_recovery
    retry = folder / 'retry'
    for client in RETRY_CLIENTS:
        shutil.rmtree(retry, ignore_errors=True)
        retry.mkdir()
        try:
            download_with_recovery(url, {**{k: v for k, v in options.items() if k != 'progress_hooks'},
                                         'outtmpl': str(retry / 'input.%(ext)s'), 'extractor_args': {'youtube': {'player_client': client}}})
            candidate = next(retry.glob('input.*'))
        except Exception as error:  # noqa: BLE001 - keep the file we have
            logger.warning('Re-download with %s failed: %s', client[0], type(error).__name__)
            continue
        better = _video_height(candidate)
        if better > height:
            source_path.unlink(missing_ok=True)
            source_path = folder / candidate.name
            candidate.replace(source_path)
            height = better
        if height >= want:
            break
    shutil.rmtree(retry, ignore_errors=True)
    if height < want:
        logger.warning('Source stays at %sp although %sp is offered', height, offered)
    return height


MIN_PLATFORM_CUES = 20


def _fetch_platform_subtitles(url, options, info, folder):
    """Use the creator's own subtitles in the video's language instead of speech recognition.

    Uploaded subtitles are punctuated and human-checked, and skip ~9 minutes of local Whisper per
    two hours of audio. Automatic captions are not used: they have no punctuation and repeat
    rolling lines, which breaks sentence-based cut points. Any problem keeps speech recognition.
    """
    language = str(info.get('language') or '').lower()
    manual = info.get('subtitles') or {}
    code = next((c for c in manual if language and (c.lower() == language or c.lower().split('-')[0] == language)), None)
    target = folder / 'input.srt'
    if not code or target.exists():
        return False
    try:
        from backend.utils.download_recovery import download_with_recovery
        download_with_recovery(url, {
            **{key: value for key, value in options.items() if key not in ('format', 'merge_output_format', 'progress_hooks')},
            'skip_download': True, 'writesubtitles': True, 'subtitleslangs': [code], 'subtitlesformat': 'srt/best',
            'postprocessors': [{'key': 'FFmpegSubtitlesConvertor', 'format': 'srt'}], 'outtmpl': str(folder / 'platform.%(ext)s'),
        })
        fetched = folder / f'platform.{code}.srt'
        if not fetched.exists() or fetched.read_text(encoding='utf-8', errors='ignore').count('-->') < MIN_PLATFORM_CUES:
            return False
        fetched.replace(target)
        return True
    except Exception as error:  # noqa: BLE001 - speech recognition still works
        logger.warning('Platform subtitles unavailable: %s', type(error).__name__)
        return False
    finally:
        for leftover in folder.glob('platform.*'):
            leftover.unlink(missing_ok=True)


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
        'clips_only': True,  # studio renders from the source: no clustering, no per-clip re-encode
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

def _apply_strategy(draft, strategy_id, *, burned_subtitles=False, layout=None):
    """Materialize platform packaging defaults without reinterpreting content.

    When the source already has subtitles in the picture, do not stack a second track, and
    keep the full frame on vertical outputs so cropping cannot cut the original lines.
    `layout` overrides the strategy default once framing has decided crop vs full frame.
    """
    from backend.services.platform_strategy import platform_strategy
    strategy = platform_strategy(strategy_id)
    value = dict(draft)
    layout = layout or (strategy.layout if strategy.layout != 'none' else value.get('layout', 'fit'))
    if burned_subtitles and strategy.aspect == 'portrait' and layout == 'crop':
        layout = 'blur'
    value.update(
        aspect=strategy.aspect,
        layout=layout,
        subtitle_style=strategy.subtitle_style,
        title_style=strategy.title_style,
        title_motion=strategy.title_motion,
    )
    if burned_subtitles:
        value['subtitles'] = False
    # The template version follows the new title style: a draft derived for one platform (comic, v6)
    # must not carry a version the next platform's style rejects (card only supports v1).
    version = value.get('title_template_version', 1)
    if value['title_style'] == 'editorial':
        value['title_template_version'] = max(2, version if version in (2, 3, 6) else 2)
    elif value['title_style'] == 'comic':
        value['title_template_version'] = 6
    elif value['title_style'] in ('plain', 'impact', 'card'):
        value['title_template_version'] = 1
    elif value['title_style'] in ('pixel', 'frosted') and version not in (3, 6):
        value['title_template_version'] = 6
    elif version in (4, 5):
        value['title_template_version'] = 6
    return Draft.model_validate(value)


def _complete_thought_bounds(project_id, clips):
    """Clip bounds that start and end on complete sentences, and complete thoughts when a text model is set up."""
    from backend.services.studio import boundaries
    try:
        from backend.services.publish_export import _load_srt_entries
        rows = boundaries.rows_from_entries(_load_srt_entries(project_id))
    except Exception:  # noqa: BLE001 - no subtitles: keep the pipeline's bounds
        return clips
    call = None
    try:
        from backend.utils.llm_client import LLMClient
        if LLMClient().llm_manager.get_current_provider_info().get('available'):
            call = intelligence.text_json
    except Exception:  # noqa: BLE001
        call = None
    with llm_usage.stage('boundaries'):
        return boundaries.refine_clips(rows, clips, call, boundaries.audio_silences(source(project_id)) if audio.has_audio(source(project_id)) else None)


def _content_drafts(project_id, plan, video):
    """Create drafts once from the selected content route, before platform derivation."""
    route = plan.get('recommended_analysis', 'subtitle')
    prefs = Preferences.model_validate(plan['preferences'])
    if route == 'subtitle' or prefs.goal == 'content':
        clips = run_content(project_id, video)
        from backend.utils.text_processor import TextProcessor
        picked = []
        for clip in clips:
            try:
                start = float(clip.get('start_time_seconds')) if clip.get('start_time_seconds') is not None else TextProcessor.time_to_seconds(clip['start_time'])
                end = float(clip.get('end_time_seconds')) if clip.get('end_time_seconds') is not None else TextProcessor.time_to_seconds(clip['end_time'])
            except (KeyError, TypeError, ValueError):
                continue
            picked.append((clip, start, end))
        bounds = _complete_thought_bounds(project_id, [(s, e) for _, s, e in picked])
        drafts = []
        for (clip, _, _), (start, end) in zip(picked, bounds):
            try:
                scene = Scene(
                    id=uuid.uuid4().hex,
                    label=str(clip.get('generated_title') or clip.get('outline') or '内容片段')[:120],
                    start=start,
                    end=end,
                )
            except (KeyError, TypeError, ValueError):
                continue
            intelligence.validate_scenes([scene], intelligence._probe(video).get('duration', 0))
            drafts.append({**Draft(
                id=uuid.uuid4().hex, title=scene.label, scenes=[scene], origin='auto-content',
                language=prefs.language, aspect=prefs.aspect, layout='crop' if prefs.aspect == 'portrait' else 'fit',
                subtitles=True,
            ).model_dump(), SCORE_KEY: _score(clip)})
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


def _source_has_burned_subtitles(project_id, video=None):
    """Detect once per project and cache on the generation; detection failure means 'no'."""
    cached = (store.read(project_id).get('generation') or {}).get('source_has_burned_subtitles')
    if cached is not None:
        return bool(cached)
    try:
        from backend.services.publish_export import _probe
        from backend.services.studio.burned_subtitles import has_burned_subtitles
        video = video or source(project_id)
        found = has_burned_subtitles(video, float(_probe(video).get('duration') or 0))
    except Exception as error:  # noqa: BLE001 - never block output on a heuristic
        logger.warning('Burned subtitle detection failed: %s', type(error).__name__)
        found = False
    language = _burned_caption_language(video, found, (store.read(project_id).get('source_meta') or {}).get('title', ''))

    def remember(data):
        if data.get('generation') is not None:
            data['generation']['source_has_burned_subtitles'] = found
            if language:
                data['generation']['burned_caption_language'] = language
    store.change(project_id, remember)
    return found


BURNED_LANGUAGE_PROMPT = (
    '这几张图是同一个视频画面的底部区域，里面有烧录在画面上的字幕。判断字幕文字是哪种语言，'
    '只返回 JSON：{"language":"zh|en|ja|ko|other|none"}（none 表示看不到字幕）。'
)


def _burned_caption_language(video, found, title=''):
    """Language of the captions burned into the picture.

    The speech language is not enough: foreign interviews often carry English captions. The vision
    model reads them when one is set up; otherwise captions are taken to be written for the
    video's own audience, i.e. in the language of its title. None means unknown (packaging then
    assumes the speech language).
    """
    if not found:
        return None
    from backend.services.studio.packaging import source_language
    guess = source_language([title]) if title else None
    guess = guess if guess in ('zh', 'en') else None
    if not intelligence.ready():
        return guess
    import base64
    import subprocess
    import tempfile
    from backend.utils.ffmpeg_utils import get_ffmpeg_path
    try:
        from backend.services.publish_export import _probe
        duration = float(_probe(video).get('duration') or 0)
        with tempfile.TemporaryDirectory(prefix='ac-captions-') as folder:
            frames = []
            for index, at in enumerate((duration * 0.3, duration * 0.5, duration * 0.7)):
                path = Path(folder) / f'{index}.jpg'
                subprocess.run([get_ffmpeg_path(), '-v', 'error', '-ss', f'{at:.2f}', '-i', str(video), '-frames:v', '1',
                                '-vf', 'crop=iw:ih*0.35:0:ih*0.65,scale=960:-2', '-y', str(path)], check=True, capture_output=True, timeout=30)
                frames.append({'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(path.read_bytes()).decode()}})
            from backend.services.studio.vision_settings import effective
            with llm_usage.stage('burned_captions'):
                answer = intelligence.vision_call([{'type': 'text', 'text': BURNED_LANGUAGE_PROMPT}, *frames], {**effective(), 'quick_screening': True})
        language = str((answer or {}).get('language') or '').lower()
        return language if language in ('zh', 'en', 'ja', 'ko', 'other') else guess
    except Exception as error:  # noqa: BLE001 - fall back to the title's language
        logger.warning('Burned caption language unknown: %s', type(error).__name__)
        return guess


def _prepare_speaker_framing(platforms):
    """Start the on-demand face-detection install as soon as a vertical output is requested."""
    from backend.services.platform_strategy import platform_strategy
    if not any(platform_strategy(p).aspect == 'portrait' for p in platforms):
        return
    try:
        from backend.services.studio import framing
        framing.start_install()
    except Exception as error:  # noqa: BLE001 - framing is an enhancement, never a blocker
        logger.warning('Framing install could not start: %s', type(error).__name__)


def _speaker_framing(value, video, *, window=None, wait_sec=120, scans=None):
    """Speaker-following crop tracks for a vertical draft (or the given output window).

    Returns (scenes, framing): `speaker` when faces drive the crop, `full_frame` when the clip has
    nobody to follow, `full_frame_pending` when the detector is not available yet.
    """
    from backend.services.studio import framing
    deadline = monotonic() + wait_sec
    while not framing.is_installed() and framing.get_status().get('status') == 'installing' and monotonic() < deadline:
        sleep(2)
    if not framing.is_installed():
        return None, 'full_frame_pending'
    from backend.services.publish_export import _probe
    info = _probe(video)
    if not info.get('width') or not info.get('height'):
        return None, 'full_frame'
    draft = Draft.model_validate({**value, 'aspect': 'portrait', 'layout': 'crop'})
    # Detection does not depend on the window: one pass serves the interview and podcast crops.
    key = tuple((scene.start, scene.end) for scene in draft.scenes)
    if scans is None or key not in scans:
        detected = framing.scan_speakers(video, draft.scenes)
        if scans is None:
            scans = {}
        scans[key] = detected
    result = framing.auto_frame(video, draft, int(info['width']), int(info['height']), window=window, scans=scans[key])
    tracks = {scene['id']: scene for scene in result['scenes']}
    if not any(scene.get('faces') for scene in result['scenes']):
        return None, 'full_frame'
    scenes = [{**scene, 'crop_x': tracks[scene['id']]['crop_x'], 'crop_track': tracks[scene['id']]['crop_track'],
               'framing_source': 'auto', 'framing_adjusted': False} for scene in value['scenes']]
    return scenes, 'speaker'


INTERVIEW_WINDOW = (1080, 810)  # 4:3 speaker window of the interview template


def _apply_framing(project_id, value, strategy_id, video, burned, cache):
    """Pick true vertical speaker framing when it is safe; otherwise keep the full frame on a backdrop.

    Burned-in captions would be cut by a 9:16 window, so those sources always keep the full frame.
    Tracks depend only on the scenes, so one detection pass is shared by every vertical platform.
    The interview template frames a 4:3 window instead; without a track it shows the whole frame.
    """
    from backend.services.platform_strategy import platform_strategy
    strategy = platform_strategy(strategy_id)
    if strategy.aspect != 'portrait':
        return value, None
    interview = strategy.template == 'interview_zh'
    fallback_layout = 'window' if interview else 'blur'
    if burned:
        plain = [{**scene, 'crop_x': None, 'crop_track': None, 'framing_source': None, 'framing_adjusted': False} for scene in value['scenes']]
        return {**value, 'scenes': plain, 'layout': fallback_layout}, 'full_frame_captions'
    window = INTERVIEW_WINDOW if interview else None
    key = (tuple((scene['start'], scene['end']) for scene in value['scenes']), window)
    if key not in cache:
        try:
            cache[key] = _speaker_framing(value, video, window=window, scans=cache.setdefault('scans', {}))
        except Exception as error:  # noqa: BLE001 - fall back to the full frame rather than fail output
            logger.warning('Speaker framing failed: %s', type(error).__name__)
            capture_studio_exception(error, 'auto_frame')
            cache[key] = (None, 'full_frame')
    scenes, framing = cache[key]
    if scenes is None:
        # Drop tracks inherited from another platform's framing: they were computed for a different window.
        plain = [{**scene, 'crop_x': None, 'crop_track': None, 'framing_source': None, 'framing_adjusted': False} for scene in value['scenes']]
        return {**value, 'scenes': plain, 'layout': fallback_layout}, framing
    return {**value, 'scenes': scenes, 'layout': 'window' if interview else 'crop'}, framing


def _content_key(value):
    return tuple((scene['start'], scene['end']) for scene in value['scenes'])


def _posts_for(project_id, items, cache):
    """{(content key, strategy id): post copy}: one model call per clip covering all its platforms, side by side."""
    from backend.pipeline.concurrency import map_chunks
    from backend.services.studio import packaging, post_copy
    _packaging_inputs(project_id, cache)
    clips = {}
    for strategy_id, value in items:
        clips.setdefault(_content_key(value), (value, []))[1].append(strategy_id)

    def one(entry):
        key, (value, platforms) = entry
        lines = [line['text'] for line in packaging.draft_lines(cache['entries'], value['scenes'])]
        title = ((value.get('packaging') or {}).get('title_lines') and ''.join(value['packaging']['title_lines'])) or value.get('title', '')
        return key, post_copy.build_posts(title, lines, platforms, source=cache.get('names', ''))

    try:
        with llm_usage.stage('post_copy'):
            results = map_chunks(one, clips.items())
    except Exception as error:  # noqa: BLE001 - copy is never a blocker
        logger.warning('Post copy failed: %s', type(error).__name__)
        return {}
    return {(key, platform): post for key, by_platform in results for platform, post in by_platform.items()}


def _design_covers(project_id, draft, job_id):
    """Design the cover of every variant this render belongs to; never fails the render."""
    from backend.services.studio import publish_kit
    state = store.read(project_id)
    targets = [item for item in state.get('output_variants', []) if item.get('render_job_id') == job_id]
    designed = []
    for variant in targets:
        try:
            publish_kit.design_cover(project_id, source(project_id), draft.model_dump() if hasattr(draft, 'model_dump') else draft,
                                     job_id, variant['strategy_id'], (variant.get('post') or {}).get('title', ''))
            designed.append(variant['id'])
        except Exception as error:  # noqa: BLE001 - the video is done; the cover can be redone from the card
            logger.warning('Cover design failed: %s', type(error).__name__)
    if designed:
        def mark(data):
            for item in data.get('output_variants', []):
                if item['id'] in designed and item.get('cover') != 'ai':
                    item['cover'] = 'design'
        store.change(project_id, mark)


def update_post(project_id, variant_id, post):
    """Save the user's edited copy for one variant (limits re-applied)."""
    from backend.services.studio import post_copy
    from backend.services.studio.models import PostCopy
    state = store.read(project_id)
    variant = next((item for item in state.get('output_variants', []) if item['id'] == variant_id), None)
    if not variant:
        raise FileNotFoundError('成片版本不存在')
    rules = post_copy.RULES.get(variant['strategy_id'], post_copy.RULES['original'])
    clean = PostCopy(title=post_copy._fit(post_copy._clean(post.title), rules.title_max) or variant.get('post', {}).get('title', ''),
                     description=post_copy._fit(post_copy._clean(post.description), rules.description_max),
                     tags=post_copy._tags(post.tags, rules)).model_dump()
    store.change(project_id, lambda data: next(item for item in data['output_variants'] if item['id'] == variant_id).update(post=clean))
    return clean


def _packaging_inputs(project_id, cache):
    """Subtitle rows and listing names shared by every packaging call of one batch."""
    if 'entries' not in cache:
        from backend.services.publish_export import _load_srt_entries
        try:
            cache['entries'] = _load_srt_entries(project_id)
        except Exception:  # noqa: BLE001 - no subtitles: packaging falls back to the title only
            cache['entries'] = []
        state = store.read(project_id)
        meta = state.get('source_meta') or {}
        cache['names'] = f"{meta.get('title', '')} {meta.get('channel', '')}"
        cache['burned_language'] = (state.get('generation') or {}).get('burned_caption_language')


def _prefetch_packaging(project_id, items, burned, cache):
    """Run the packaging model calls of a batch side by side (one per distinct content and template).

    Each call waits ~20 s on the model; done one after another they were ~8 minutes for 25 clips.
    """
    from backend.pipeline.concurrency import map_chunks
    from backend.services.platform_strategy import platform_strategy
    _packaging_inputs(project_id, cache)  # load shared inputs once, before the threads
    first = {}
    for strategy_id, value in items:
        key = (tuple((scene['start'], scene['end']) for scene in value['scenes']), platform_strategy(strategy_id).template)
        first.setdefault(key, (strategy_id, value))
    map_chunks(lambda item: _apply_packaging(project_id, item[1], item[0], burned, cache), first.values())


def _apply_packaging(project_id, value, strategy_id, burned, cache):
    """Attach template packaging (title, captions, nameplates, tags) for vertical templates.

    One model call per scene set and template; every vertical platform of the same audience
    reuses it. Only the subtitle rows this draft uses are sent.
    """
    from backend.services.platform_strategy import platform_strategy
    strategy = platform_strategy(strategy_id)
    if strategy.template not in ('interview_zh', 'podcast_en'):
        return {key: item for key, item in value.items() if key != 'packaging'}  # never inherit another template's packaging
    from backend.services.studio import packaging
    _packaging_inputs(project_id, cache)
    key = (tuple((scene['start'], scene['end']) for scene in value['scenes']), strategy.template)
    if key not in cache:
        lines = packaging.draft_lines(cache['entries'], value['scenes'])
        used = cache.setdefault('palettes', [])
        with llm_usage.stage('packaging'):
            cache[key] = packaging.build_packaging(value, lines, strategy, burned=burned, burned_language=cache.get('burned_language'),
                                                   known_names=cache['names'],
                                                   avoid_palettes=tuple(used[-2:]))
        if cache[key].get('palette'):
            used.append(cache[key]['palette'])
    return {**value, 'packaging': cache[key]}


def _fit_platform_limit(project_id, value, strategy):
    """Trim a draft to the platform's hard length limit at the last subtitle sentence end.

    Only strategies with a real platform cap (YouTube Shorts) set `max_duration_sec`; every
    other platform keeps the complete moment. Returns (draft, trimmed_to_seconds_or_None).
    """
    limit = strategy.max_duration_sec
    scenes = value.get('scenes', [])
    if not limit or sum(s['end'] - s['start'] for s in scenes) <= limit:
        return value, None
    try:
        from backend.services.publish_export import _load_srt_entries, to_seconds
        ends = sorted(to_seconds(e['end_time']) for e in _load_srt_entries(project_id) if e.get('end_time'))
    except Exception:  # noqa: BLE001 - no subtitles: fall back to an exact cut
        ends = []
    remaining, kept = float(limit), []
    for scene in scenes:
        length = scene['end'] - scene['start']
        if length <= remaining:
            kept.append(scene)
            remaining -= length
            continue
        target = scene['start'] + remaining
        boundary = [end for end in ends if scene['start'] + 1 < end <= target]
        kept.append({**scene, 'end': max(boundary) if boundary else target})
        break
    return {**value, 'scenes': kept}, limit


@_tracked('production')
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
        burned = _source_has_burned_subtitles(project_id, video)
        framing_cache = {}
        packaging_cache = {}
        automatic = _automatic_drafts(base_drafts)
        planned = []
        for base in base_drafts:
            base = {key: item for key, item in base.items() if key != SCORE_KEY}
            for strategy_id in platforms:
                strategy = platform_strategy(strategy_id)
                duration = sum(scene['end'] - scene['start'] for scene in base['scenes'])
                if strategy.duration_policy == 'long' and duration < (strategy.min_recommended_duration_sec or 0):
                    skipped.append({'strategy_id': strategy_id, 'reason': '素材没有足够完整的长内容'})
                    continue
                value, trimmed = _fit_platform_limit(project_id, {**base, 'id': uuid.uuid4().hex, 'revision': 1}, strategy)
                now = base['id'] in automatic
                framed = None  # on-demand versions are framed and packaged when the user asks (produce_variant)
                if now:
                    value, framed = _apply_framing(project_id, value, strategy_id, video, burned, framing_cache)
                planned.append((strategy_id, value, trimmed, framed, now))
        _prefetch_packaging(project_id, [(strategy_id, value) for strategy_id, value, _, _, now in planned if now], burned, packaging_cache)
        posts = _posts_for(project_id, [(strategy_id, value) for strategy_id, value, _, _, now in planned if now], packaging_cache)
        for strategy_id, value, trimmed, framed, now in planned:
            if now:
                value = _apply_packaging(project_id, value, strategy_id, burned, packaging_cache)
            draft = _apply_strategy(value, strategy_id, burned_subtitles=burned, layout=value.get('layout') if framed else None)
            derived_drafts.append(draft.model_dump())
            variants.append({
                'id': uuid.uuid4().hex, 'draft_id': draft.id, 'draft_revision': draft.revision,
                'strategy_id': strategy_id, 'strategy_version': 1, 'branding': branding,
                'status': 'queued' if now else 'on_demand', 'created_at': store.now(),
                **({'trimmed_to_sec': trimmed} if trimmed else {}),
                **({'framing': framed} if framed else {}),
                **({'post': posts[_content_key(value), strategy_id]} if (_content_key(value), strategy_id) in posts else {}),
            })
        if not variants:
            raise ValueError('所选平台没有可生成的完整内容版本')
        def persist(data):
            data['drafts'].extend({**draft, 'updated_at': store.now()} for draft in derived_drafts)
            if events:
                data['events'] = events
            data['output_variants'].extend(variants)
            data['generation'].update(status='rendering', skipped=skipped, started_at=data['generation'].get('started_at') or store.now())
            data['analysis'] = {'status': 'running', 'phase': 'rendering', 'run_id': (data.get('analysis') or {}).get('run_id'), 'message': '正在生成可发布成片', 'instance': store.INSTANCE, 'created_at': store.now()}
        store.change(project_id, persist)
        _dispatch_pending_variants(project_id)
    except Exception as error:
        capture_studio_exception(error, 'production')
        def fail(data):
            if data.get('generation'):
                data['generation'].update(status='failed', error=str(error)[:700], skipped=skipped, finished_at=store.now())
            data['analysis'] = {'status': 'failed', 'phase': 'production', 'run_id': (data.get('analysis') or {}).get('run_id'), 'error': str(error)[:700], 'duration_ms': round((monotonic() - started) * 1000)}
        store.change(project_id, fail)
        mark_project(project_id, 'failed')


def append_platform_variants(project_id, platforms, branding):
    """Derive only new platform versions from saved drafts; never reanalyze source media."""
    state = store.read(project_id)
    if not (state.get('generation') or {}).get('auto_start'):
        raise ValueError('这个项目尚未使用自动生成流程')
    from backend.services.platform_strategy import normalize_platform_ids, platform_strategy
    selected = normalize_platform_ids(platforms)
    draft_by_id = {draft['id']: draft for draft in state.get('drafts', [])}
    existing = {
        (item['strategy_id'], tuple((scene['start'], scene['end']) for scene in draft_by_id.get(item['draft_id'], {}).get('scenes', [])))
        for item in state.get('output_variants', [])
    }
    # A moment rendered automatically on one platform renders automatically on the new one too;
    # moments left on demand stay on demand.
    automatic = {
        tuple((scene['start'], scene['end']) for scene in draft_by_id.get(item['draft_id'], {}).get('scenes', []))
        for item in state.get('output_variants', []) if item.get('status') != 'on_demand'
    }
    seen_scenes, variants, derived = set(), [], []
    burned = _source_has_burned_subtitles(project_id)
    video = source(project_id)
    framing_cache = {}
    packaging_cache = {}
    for base in state.get('drafts', []):
        signature = tuple((scene['start'], scene['end']) for scene in base.get('scenes', []))
        if not signature or signature in seen_scenes:
            continue
        seen_scenes.add(signature)
        for strategy_id in selected:
            if (strategy_id, signature) in existing:
                continue
            strategy = platform_strategy(strategy_id)
            duration = sum(end - start for start, end in signature)
            if strategy.duration_policy == 'long' and duration < (strategy.min_recommended_duration_sec or 0):
                continue
            value, trimmed = _fit_platform_limit(project_id, {**base, 'id': uuid.uuid4().hex, 'revision': 1}, strategy)
            now = signature in automatic
            framed = None
            if now:
                value, framed = _apply_framing(project_id, value, strategy_id, video, burned, framing_cache)
                value = _apply_packaging(project_id, value, strategy_id, burned, packaging_cache)
            draft = _apply_strategy(value, strategy_id, burned_subtitles=burned, layout=value.get('layout') if framed else None)
            derived.append(draft.model_dump())
            variants.append({
                'id': uuid.uuid4().hex, 'draft_id': draft.id, 'draft_revision': 1,
                'strategy_id': strategy_id, 'strategy_version': 1, 'branding': branding,
                'status': 'queued' if now else 'on_demand', 'created_at': store.now(),
                **({'trimmed_to_sec': trimmed} if trimmed else {}),
                **({'framing': framed} if framed else {}),
            })
    if not variants:
        raise ValueError('没有可追加的平台版本；已存在或素材不满足所选平台要求')
    def persist(data):
        data['drafts'].extend({**draft, 'updated_at': store.now()} for draft in derived)
        data['output_variants'].extend(variants)
        data['generation'].update(status='rendering')
        data['analysis'] = {'status': 'running', 'phase': 'rendering', 'message': '正在追加平台版本', 'instance': store.INSTANCE, 'created_at': store.now()}
    store.change(project_id, persist)
    _dispatch_pending_variants(project_id)
    return variants


def _dispatch_pending_variants(project_id):
    """Queue a render for every automatic variant that does not have one yet.

    There is no per-project cap on how many variants get produced: the source decides the
    count, and `render_executor` encodes them one at a time. Re-running is safe because
    `export` deduplicates identical draft snapshots and attached variants are skipped.
    """
    state = store.read(project_id)
    pending = [item for item in state.get('output_variants', []) if item.get('status') == 'queued' and not item.get('render_job_id')]
    drafts = {draft['id']: draft for draft in state.get('drafts', [])}
    for variant in pending:
        raw = drafts.get(variant['draft_id'])
        if not raw:
            store.change(project_id, lambda data, variant_id=variant['id']: next(item for item in data['output_variants'] if item['id'] == variant_id).update(status='failed', error='来源草稿不存在'))
            continue
        job = export(project_id, Draft.model_validate(raw), brand_outro=bool(variant['branding'].get('outro_enabled', True)))
        store.change(project_id, lambda data, variant_id=variant['id'], job_id=job['job_id']: next(item for item in data['output_variants'] if item['id'] == variant_id).update(render_job_id=job_id))


SCORE_KEY = '_auto_score'
AUTO_RENDER_LIMIT = 10  # clips rendered automatically per import; the rest wait for a click


def _score(clip):
    try:
        return float(clip.get('final_score'))
    except (TypeError, ValueError):
        return 0.0


def _automatic_drafts(base_drafts):
    """Ids of the drafts rendered without asking: the highest-scored AUTO_RENDER_LIMIT.

    A two-hour talk yields 30+ clips; rendering all of them up front cost most of the run, while
    people publish a handful. Drafts without a score (visual highlights, at most a few) all render.
    """
    scored = [draft for draft in base_drafts if SCORE_KEY in draft]
    if len(scored) <= AUTO_RENDER_LIMIT:
        return {draft['id'] for draft in base_drafts}
    top = sorted(scored, key=lambda draft: draft[SCORE_KEY], reverse=True)[:AUTO_RENDER_LIMIT]
    return {draft['id'] for draft in top} | {draft['id'] for draft in base_drafts if SCORE_KEY not in draft}


def produce_variant(project_id, variant_id):
    """Frame, package and render one on-demand variant."""
    state = store.read(project_id)
    variant = next((item for item in state.get('output_variants', []) if item['id'] == variant_id), None)
    if not variant:
        raise FileNotFoundError('成片版本不存在')
    if variant.get('status') != 'on_demand':
        raise ValueError('这条成片已经在生成或已完成')
    if not any(item['id'] == variant['draft_id'] for item in state.get('drafts', [])):
        raise FileNotFoundError('来源草稿不存在')

    def start(data):
        item = next(value for value in data['output_variants'] if value['id'] == variant_id)
        item.update(status='queued')
        data['generation'].update(status='rendering')
    store.change(project_id, start)
    executor.submit(_produce_on_demand, project_id, variant_id)
    return next(item for item in store.read(project_id)['output_variants'] if item['id'] == variant_id)


@_tracked('production')
def _produce_on_demand(project_id, variant_id):
    try:
        state = store.read(project_id)
        variant = next(item for item in state['output_variants'] if item['id'] == variant_id)
        raw = next(item for item in state['drafts'] if item['id'] == variant['draft_id'])
        video = source(project_id)
        burned = _source_has_burned_subtitles(project_id, video)
        strategy_id = variant['strategy_id']
        value, framed = _apply_framing(project_id, raw, strategy_id, video, burned, {})
        value = _apply_packaging(project_id, value, strategy_id, burned, {})
        draft = _apply_strategy(value, strategy_id, burned_subtitles=burned, layout=value.get('layout') if framed else None).model_dump()
        posts = _posts_for(project_id, [(strategy_id, value)], {})

        def ready(data):
            for index, item in enumerate(data['drafts']):
                if item['id'] == draft['id']:
                    data['drafts'][index] = {**draft, 'updated_at': store.now()}
            target = next(item for item in data['output_variants'] if item['id'] == variant_id)
            if framed:
                target['framing'] = framed
            if (_content_key(value), strategy_id) in posts:
                target['post'] = posts[_content_key(value), strategy_id]
        store.change(project_id, ready)
        _dispatch_pending_variants(project_id)
    except Exception as error:  # noqa: BLE001 - the variant shows the failure and can be retried
        logger.warning('On-demand variant failed: %s', type(error).__name__)
        capture_studio_exception(error, 'production')
        store.change(project_id, lambda data: next(item for item in data['output_variants'] if item['id'] == variant_id).update(
            status='failed', error='这条成片准备失败，请重试'))


def retry_variant(project_id, variant_id):
    state = store.read(project_id)
    variant = next((item for item in state.get('output_variants', []) if item['id'] == variant_id), None)
    if not variant:
        raise FileNotFoundError('成片版本不存在')
    if variant.get('status') != 'failed':
        raise ValueError('只有失败的成片版本可以重试')
    raw = next((item for item in state.get('drafts', []) if item['id'] == variant['draft_id']), None)
    if not raw:
        raise FileNotFoundError('来源草稿不存在')
    def update(data):
        item = next(value for value in data['output_variants'] if value['id'] == variant_id)
        item.update(status='queued')
        item.pop('render_job_id', None)
        item.pop('error', None)
        data['generation'].update(status='rendering')
        data['analysis'] = {'status': 'running', 'phase': 'rendering', 'message': '正在重试成片版本', 'instance': store.INSTANCE, 'created_at': store.now()}
    store.change(project_id, update)
    _dispatch_pending_variants(project_id)
    return next(item for item in store.read(project_id)['output_variants'] if item['id'] == variant_id)


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
        variants = [item for item in data['output_variants'] if item['status'] != 'on_demand']
        if all(item['status'] in ('completed', 'failed') for item in variants):
            completed = [item for item in variants if item['status'] == 'completed']
            outcome = 'completed' if len(completed) == len(variants) else 'partial' if completed else 'failed'
            data['generation'].update(status=outcome, completed_variant_count=len(completed), finished_at=store.now())
            data['analysis'] = {'status': 'completed' if completed else 'failed', 'phase': 'rendering', 'run_id': (data.get('analysis') or {}).get('run_id'), 'outcome': outcome, 'created_at': store.now()}
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
        state['analysis'] = {'status':'running', 'phase':'screening', 'run_id':uuid.uuid4().hex, 'message':'准备素材' if url else '快速判断适合的制作类型', 'instance':store.INSTANCE, 'created_at':store.now()}
        store.write(project_id, state)
        if options.auto_start:
            _prepare_speaker_framing(options.platforms)
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

        return state['analysis']['run_id']


@_tracked('screening')
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
                run_id = (data.get('analysis') or {}).get('run_id')  # observers match the run across phases
                data.update(plan=plan, analysis={'status': 'running', 'phase': 'production', 'run_id': run_id, 'message': '正在制作可发布成片', 'instance': store.INSTANCE, 'created_at': store.now()})
                data['generation'].update(status='production', started_at=store.now())
            store.change(project_id, start_automatic)
            mark_project(project_id, 'processing', creative=plan['preferences'], awaiting_confirmation=False, import_staging=False)
            try:
                executor.submit(_auto_generate, project_id, plan)
            except Exception as error:
                capture_studio_exception(error, 'dispatch')
                message = '自动制作任务未能启动，请重试；原素材已保留'
                def fail_automatic(data):
                    data['generation'].update(status='failed', error=message, finished_at=store.now())
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
        state['analysis'] = {'status':'running', 'phase':'production', 'run_id':uuid.uuid4().hex, 'message':'开始制作所选内容', 'instance':store.INSTANCE, 'created_at':store.now()}
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

        return state['analysis']['run_id']


@_tracked('production')
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
