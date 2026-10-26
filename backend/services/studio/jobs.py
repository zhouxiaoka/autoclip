import json
import logging
import shutil
from time import monotonic, sleep
from backend.core.failure_codes import UserFacingError, sentence, user_visible_error
from backend.core.sentry_setup import capture_studio_exception, studio_error_code, studio_failure_context
from copy import deepcopy
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from backend.core import llm_usage
from backend.services.studio import attempts, audio, intelligence, store
from backend.services.studio.features import flag_enabled, resolve_features
from backend.services.studio.models import Draft, Preferences, Scene
from backend.services.studio.project_completion import sync_project_completion
from backend.services.studio.intelligence import analyze, make_drafts, VisionRequestError
from backend.services.studio.render import render_draft
from backend.services.studio.templates.spec import HTML_TEMPLATE_IDS

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='studio')


def _generation_route(plan):
    route = (plan or {}).get('recommended_analysis') or (plan or {}).get('confirmed_analysis')
    return {'route': route} if route in ('subtitle', 'visual') else {}


def _carried_progress(previous):
    """Keep the project bar when production hands off to rendering.

    The content pipeline stops around the highlight band. Rendering continues,
    so the results page still has a stage and a percent. The ease clock starts
    now; elapsed time on the card uses the generation start, not this clock.
    """
    import time
    out = {'progress_stage': 'EXPORT', 'progress_approximate': True, 'progress_since': int(time.time())}
    carried = previous.get('progress_percent') if isinstance(previous, dict) else None
    if isinstance(carried, (int, float)) and not isinstance(carried, bool):
        out['progress_percent'] = max(0, min(95, int(carried)))
    return out
# Local encodes are CPU-bound: run one at a time on its own worker so screening and
# analysis of other imports never wait behind a render queue.
render_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='studio-render')


def source(project_id):
    from backend.services.publish_export import find_source_video
    return find_source_video(project_id)


def _project_has_subtitle(project_id):
    try:
        video = source(project_id)
        if video is not None and (video.parent / 'input.srt').is_file():
            return True
    except Exception:  # noqa: BLE001 - missing source is just "no subtitle yet"
        pass
    try:
        root = store.directory(project_id)
        return (root / 'input.srt').is_file()
    except Exception:  # noqa: BLE001
        return False

def export(project_id, draft, *, brand_outro=False, _variant_identity=None, html_template=None, html_fallback=None, safe_area='xiaohongshu', requested_template=None):
    from backend.services.output_branding import load_settings
    brand_outro = bool(brand_outro and load_settings().enabled)
    from backend.services.studio.template_choice import recorded_style
    style = recorded_style(html_template, requested_template)
    job = {'job_id': uuid.uuid4().hex, 'status': 'queued', 'percent': 0, 'draft_id': draft.id, 'title': draft.title, 'revision': draft.revision, 'brand_outro': brand_outro, 'created_at': store.now(), 'instance': store.INSTANCE, 'snapshot': draft.model_dump(), **style}
    if html_template in HTML_TEMPLATE_IDS and style['template'] in HTML_TEMPLATE_IDS:
        job['html_template'] = html_template
        job['html_safe_area'] = safe_area
    elif html_fallback == 'rank':
        job['html_fallback'] = 'rank'
        if requested_template in HTML_TEMPLATE_IDS:
            job['requested_template'] = requested_template
    if _variant_identity is not None:
        job['variant_links'] = [list(_variant_identity)]
    def add(data):
        active = next((j for j in data['jobs'] if j['status'] in ('queued', 'running') and j.get('snapshot') == job['snapshot']
                       and j.get('brand_outro', False) == brand_outro), None)
        if active:
            if _variant_identity is not None and list(_variant_identity) not in active.get('variant_links', []):
                active.setdefault('variant_links', []).append(list(_variant_identity))
            return active
        data['jobs'].insert(0, job)
        return job
    # Keep deduplication and dispatch atomic: another request must not receive
    # a queued job before we know the executor accepted it.
    with store.lock:
        added = store.change(project_id, add)
        if added['job_id'] == job['job_id']:
            try:
                render_kwargs = {'brand_outro': brand_outro}
                if job.get('html_template'):
                    render_kwargs['html_template'] = job['html_template']
                    render_kwargs['safe_area'] = job.get('html_safe_area') or 'xiaohongshu'
                elif job.get('html_fallback'):
                    render_kwargs['html_fallback'] = job['html_fallback']
                    if job.get('requested_template'):
                        render_kwargs['requested_template'] = job['requested_template']
                render_executor.submit(
                    _render, project_id, draft, job['job_id'],
                    _io_receipt=('render', job['job_id']), **render_kwargs,
                )
            except Exception as error:
                logger.warning('Studio export dispatch failed: %s', type(error).__name__)
                capture_studio_exception(error, 'dispatch')
                store.mark_worker_error_reported()
                store.remember_submission_rejection(project_id, ('render', job['job_id']), error_code=studio_error_code(error))
                message = '导出任务未能启动，请重试；已有成片已保留'
                code = studio_error_code(error)
                def failed(data):
                    next(j for j in data['jobs'] if j['job_id'] == job['job_id']).update(status='failed', error=message, error_code=code)
                store.change(project_id, failed)
                raise UserFacingError(message) from None
        return {k: v for k, v in added.items() if k not in ('instance', 'snapshot', 'variant_links')}


def _freeze_phase_identity(project_id):
    """a run phase's worker starts from the identity its start record froze, so snapshots
    and Sentry taken before the first model request name that connection (not today's settings)."""
    try:
        data = json.loads((store.directory(project_id) / 'metadata' / 'studio.json').read_text(encoding='utf-8'))
        from backend.core.llm_emit import freeze_phase_identity
        freeze_phase_identity((data.get('analysis') if isinstance(data, dict) else None) or {})
    except Exception:  # noqa: BLE001 - attribution only
        logger.debug('phase identity was not frozen', exc_info=True)


def _tracked(stage):
    """Record model token usage of a studio job (first argument: project id) under `stage`."""
    def wrap(fn):
        from functools import wraps

        @wraps(fn)
        def run(project_id, *args, **kwargs):
            identity = kwargs.pop('_io_receipt', None)
            from backend.core.project_cancellation import ProjectDeleted, bind
            from backend.core import llm_telemetry
            with bind(project_id), store.worker_read_scope(project_id, identity), llm_usage.tracking(project_id), llm_usage.stage(stage), llm_telemetry.track_run():
                if identity and identity[0] == 'analysis':
                    _freeze_phase_identity(project_id)
                try:
                    return fn(project_id, *args, **kwargs)
                except ProjectDeleted:
                    return None  # deleted: the binder removes leftover files; nothing to record
                except PermissionError as error:
                    if store.read_error_needs_report(error):
                        phase = {'visual_analysis': 'analysis', 'ai_cover': 'production'}.get(stage, stage)
                        capture_studio_exception(error, phase)
                    raise
        return run
    return wrap


@_tracked('render')
def _render(project_id, draft, job_id, *, brand_outro=False, html_template=None, html_fallback=None, safe_area='xiaohongshu', requested_template=None):
    from backend.core import project_cancellation
    started = monotonic()
    render_saved = False
    result = None
    qa_scheduled = False

    def update(**values):
        def mutate(data):
            job = next(j for j in data['jobs'] if j['job_id'] == job_id)
            incoming = values.get('status')
            current = job.get('status')
            # A cancel must not be overwritten by the render finishing, and a finished
            # video must not be marked cancelled afterwards.
            if current == 'cancelled' and incoming == 'completed':
                return
            if current == 'completed' and incoming == 'cancelled':
                return
            job.update(values)
        store.change(project_id, mutate)

    def _schedule_qa():
        """Enqueue shadow checks only after the export is already completed."""
        nonlocal qa_scheduled
        if qa_scheduled or not render_saved:
            return
        qa_scheduled = True
        try:
            from backend.services.studio.qa.schedule import schedule_after_render
        except Exception as error:
            logger.warning('QA import failed: %s', type(error).__name__)
            return
        try:
            schedule_after_render(project_id, draft, job_id, result)
        except Exception as error:
            logger.warning('QA schedule failed: %s', type(error).__name__)

    try:
        update(status='running', percent=5)
        features = None
        try:
            features = (store.read(project_id).get('generation') or {}).get('features')
        except Exception:
            features = None
        with llm_usage.timed('render'):
            render_kwargs = {'brand_outro': brand_outro}
            if html_template:
                render_kwargs.update(html_template=html_template, features=features, safe_area=safe_area)
            elif html_fallback:
                render_kwargs.update(html_fallback=html_fallback, features=features)
                if requested_template in HTML_TEMPLATE_IDS:
                    render_kwargs['requested_template'] = requested_template
            result = render_draft(
                project_id, source(project_id), draft, job_id, lambda p: update(percent=p),
                **render_kwargs,
            )
        elapsed = round((monotonic() - started) * 1000)
        if isinstance(result, dict) and result.get('template_render'):
            from backend.services.studio.template_telemetry import host_facts, render_event
            # duration_ms on the event is the overlay's own time. The job record keeps the whole render.
            result = {**result, 'template_render': render_event({**host_facts(), **result['template_render']})}
        update(status='completed', percent=100, result=result, cover_pending=True, duration_ms=elapsed)
        render_saved = True
        try:
            _design_covers(project_id, draft, job_id)
        finally:
            update(cover_pending=False)
        _sync_variant_status(project_id, job_id, 'completed')
        _schedule_qa()
    except project_cancellation.JobStopped:
        with project_cancellation.record_stop():
            try:
                update(status='cancelled', error_code='cancelled', duration_ms=round((monotonic() - started) * 1000))
                _sync_variant_status(project_id, job_id, 'cancelled')
            except (FileNotFoundError, project_cancellation.ProjectDeleted):
                pass
        return
    except Exception as error:
        logger.warning('Studio render failed: %s', type(error).__name__)
        capture_studio_exception(error, 'render')
        store.mark_worker_error_reported()
        if render_saved:
            # Optional cover/index work cannot revoke an already committed video.
            _sync_variant_status(project_id, job_id, 'completed')
            _schedule_qa()
            return
        try:
            message = user_visible_error(error)
            update(status='failed', error=message, error_code=studio_error_code(error), duration_ms=round((monotonic() - started) * 1000))
            _sync_variant_status(project_id, job_id, 'failed', message)
        except FileNotFoundError:
            pass
    finally:
        if render_saved:
            store.mark_render_finished(project_id, job_id)

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



from backend.core.failure_attribution import AttributedError  # noqa: E402
from backend.pipeline.failures import AttributedPipelineFailure as ContentPipelineFailure  # noqa: E402


class ContentRunError(AttributedError, RuntimeError):
    """an uncoded content pipeline failure rebuilt across apply.get, with its snapshot."""


def run_content(project_id, video, platform_min_sec=None, platform_min_label=''):
    """Run the existing content pipeline in this worker, without a second broker queue.

    `platform_min_sec` is forwarded only when a long-form platform was requested, so callers
    that mock the two-argument form keep working for every other platform.
    """
    from backend.tasks.processing import process_video_pipeline
    srt = video.parent / 'input.srt'
    kwargs = {
        'project_id': project_id, 'input_video_path': str(video),
        'input_srt_path': str(srt) if srt.exists() else None,
        'clips_only': True,  # studio renders from the source: no clustering, no per-clip re-encode
    }
    if platform_min_sec:
        kwargs['platform_min_sec'] = platform_min_sec
        kwargs['platform_min_label'] = platform_min_label
    from backend.core.job_budget import bind_clip_job, unbind_clip_job
    token = bind_clip_job()
    try:
        result = process_video_pipeline.apply(kwargs=kwargs, throw=True).get()
    finally:
        unbind_clip_job(token)
    if not result or not result.get('success'):
        message = (result or {}).get('error') or '内容切片未完成，请检查语音与文字模型设置后重试'
        failure = (result or {}).get('result') or {}
        # The original exception does not survive apply().get(): the adapter records the provider
        # HTTP status in the result dict and it is carried back here (RC156 Win QA #1).
        # The original exception does not survive apply().get(): the adapter built the one attribution
        # snapshot while the chain existed and it rides in the dict; it is restored here whole.
        from backend.core.failure_attribution import attributed, restore_attribution
        status = failure.get('http_status')
        code = failure.get('error_code') or ''
        if code or failure.get('stage'):
            error = ContentPipelineFailure(failure.get('stage', ''), message, code=code,
                                           upstream_error_type=failure.get('upstream_error_type') or '')
        else:
            error = ContentRunError(message)
        attributed(error, restore_attribution(failure.get('attribution')), http_status=status)
        if failure.get('upstream_error_type'):
            error.upstream_error_type = failure.get('upstream_error_type')
        raise error

    clips = result.get('result', {}).get('result', {}).get('titled_clips')
    if not clips:
        raise UserFacingError('没有提取到可用内容片段，请检查语音/字幕，或修改方案为精彩高光')

    return clips

def _snapshotted_captions(generation) -> bool:
    """The burn-captions switch frozen when this generation started.

    A project written before the switch has no field and keeps the historical default, on.
    """
    if not isinstance(generation, dict) or 'output_captions' not in generation:
        return True
    return bool(generation['output_captions'])


def _apply_strategy(draft, strategy_id, *, burned_subtitles=False, layout=None, output_captions=True):
    """Materialize platform packaging defaults without reinterpreting content.

    When the source already has subtitles in the picture, do not stack a second track, and
    keep the full frame on vertical outputs so cropping cannot cut the original lines.
    `layout` overrides the strategy default once framing has decided crop vs full frame.
    """
    from backend.services.platform_strategy import platform_strategy
    strategy = platform_strategy(strategy_id)
    value = dict(draft)
    layout = layout or (strategy.layout if strategy.layout != 'none' else value.get('layout', 'fit'))
    if value.get('caption_mask'):
        burned_subtitles = False  # blurred out: our own captions and framing apply
    if burned_subtitles and strategy.aspect == 'portrait' and layout == 'crop':
        layout = 'blur'
    value.update(
        aspect=strategy.aspect,
        layout=layout,
        subtitle_style=strategy.subtitle_style,
        title_style=strategy.title_style,
        title_motion=strategy.title_motion,
    )
    if strategy.template == 'landscape' and strategy_id != 'original' and value.get('language', 'source') == 'source':
        # No template packaging here: the legacy captions and hook are translated at render time
        # (skipped when already in this language), so English YouTube never burns Chinese text.
        value['language'] = strategy.audience_language
    if burned_subtitles:
        value['subtitles'] = False
    if not output_captions:
        # The per-draft editor still flips these flags back on for one clip. Cues stay,
        # so turning captions back on burns the lines that were already written.
        value['subtitles'] = False
        packaging = value.get('packaging')
        if packaging is not None:
            current = packaging.model_dump() if hasattr(packaging, 'model_dump') else dict(packaging)
            value['packaging'] = {**current, 'captions_enabled': False}
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
    with llm_usage.stage('boundaries'), llm_usage.timed('boundaries'):
        return boundaries.refine_clips(rows, clips, call, boundaries.audio_silences(source(project_id)) if audio.has_audio(source(project_id)) else None)


MAX_DRAFT_OVERLAP = 0.5  # share of the shorter clip two content drafts may have in common


def _overlap_share(a, b):
    shared = min(a[1], b[1]) - max(a[0], b[0])
    shorter = min(a[1] - a[0], b[1] - b[0])
    return shared / shorter if shared > 0 and shorter > 0 else 0.0


def _distinct_ranges(picked, bounds):
    """(clip, start, end) without near-duplicate drafts (RC156 Win QA #7).

    Boundary polishing may push two clips onto the same span. Higher-scored clips keep their
    polished range; a lower-scored one falls back to its original pipeline range, and is
    dropped only when that still mostly repeats a kept clip. Original order is preserved.
    """
    order = sorted(range(len(picked)), key=lambda i: _score(picked[i][0]), reverse=True)
    kept = {}
    for i in order:
        clip, original_start, original_end = picked[i]
        for candidate in (tuple(bounds[i]), (original_start, original_end)):
            if all(_overlap_share(candidate, other) <= MAX_DRAFT_OVERLAP for other in kept.values()):
                kept[i] = candidate
                break
        else:
            logger.info('Dropped a content clip that repeats a higher-scored clip')
    return [(picked[i][0], *kept[i]) for i in sorted(kept)]


def _content_drafts(project_id, plan, video, platforms=()):
    """Create drafts once from the selected content route, before platform derivation."""
    route = plan.get('recommended_analysis', 'subtitle')
    prefs = Preferences.model_validate(plan['preferences'])
    if route == 'subtitle' or prefs.goal == 'content':
        from backend.services.platform_strategy import long_form_minimum
        min_sec, label = long_form_minimum(platforms)
        # Pass the minimum only when a long platform asked for it. A two-argument mock
        # still matches every short-platform import.
        clips = run_content(project_id, video, min_sec, label) if min_sec else run_content(project_id, video)
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
        source_duration = float(intelligence._probe(video).get('duration') or 0)
        drafts = []
        for clip, start, end in _distinct_ranges(picked, bounds):
            # Transcript timestamps can run past the final video frame. Keep valid content
            # from that clip, and never let one invalid range discard the whole batch.
            end = min(end, source_duration)
            try:
                scene = Scene(
                    id=uuid.uuid4().hex,
                    label=str(clip.get('generated_title') or clip.get('outline') or '内容片段')[:120],
                    start=start,
                    end=end,
                    evidence=str(clip.get('recommend_reason') or clip.get('recommendation_reason') or '')[:1000],
                )
                intelligence.validate_scenes([scene], source_duration)
            except (KeyError, TypeError, ValueError):
                continue
            drafts.append({**Draft(
                id=uuid.uuid4().hex, title=scene.label, scenes=[scene], origin='auto-content',
                language=prefs.language, aspect=prefs.aspect, layout='crop' if prefs.aspect == 'portrait' else 'fit',
                subtitles=True,
            ).model_dump(), SCORE_KEY: _score(clip)})
        if not drafts:
            raise UserFacingError('没有提取到可渲染的内容片段，请检查字幕或重新导入')
        return drafts
    if route != 'visual':
        raise UserFacingError('没有可用的自动分析路径，请检查模型设置后重试')
    if not intelligence.ready():
        raise UserFacingError('请先在设置中配置视觉理解模型')
    try:
        events, coverage = analyze(video, prefs)
        drafts = make_drafts(events, prefs, plan.get('overrides', {}).get('instruction', ''), source_duration=intelligence._probe(video).get('duration'))
    except ValueError as error:
        # A silent source that the visual route could not cut (RC156 Win QA #19): explain the missing
        # sound and point to an SRT instead of a bare 「没有找到可用镜头」. Model/network errors
        # (VisionRequestError) keep their own message.
        from backend.pipeline import media_precheck
        silent = media_precheck.silent_visual_failure(video, srt_available=(Path(video).parent / 'input.srt').is_file())
        if silent is None:
            raise
        raise silent from error
    return drafts, [event.model_dump() for event in events], coverage


def _source_has_burned_subtitles(project_id, video=None):
    """Detect once per project and cache on the generation; detection failure means 'no'."""
    cached = (store.read(project_id).get('generation') or {}).get('source_has_burned_subtitles')
    if cached is not None:
        return bool(cached)
    try:
        from backend.services.publish_export import _probe
        from backend.services.studio.burned_subtitles import detect
        video = video or source(project_id)
        found, band = detect(video, float(_probe(video).get('duration') or 0))
    except Exception as error:  # noqa: BLE001 - never block output on a heuristic
        logger.warning('Burned subtitle detection failed: %s', type(error).__name__)
        found, band = False, None
    language = _burned_caption_language(video, found, (store.read(project_id).get('source_meta') or {}).get('title', ''))
    if language == 'none':
        found, language = False, None  # the vision model saw no captions: the pixel heuristic was fooled by scene text

    def remember(data):
        if data.get('generation') is not None:
            data['generation']['source_has_burned_subtitles'] = found
            if language:
                data['generation']['burned_caption_language'] = language
            if found and band:
                data['generation']['burned_caption_band'] = list(band)
    store.change(project_id, remember)
    return found


def _caption_mask(project_id, strategy_id):
    """The burned caption band to blur out of this version, or None.

    An English platform must not show the source's Chinese (or other non-English) captions:
    the band is blurred and the version is framed and captioned like a caption-free source.
    """
    from backend.services.platform_strategy import platform_strategy
    generation = store.read(project_id).get('generation') or {}
    band, language = generation.get('burned_caption_band'), generation.get('burned_caption_language')
    if not (generation.get('source_has_burned_subtitles') and band and language and language != 'en'):
        return None
    return list(band) if platform_strategy(strategy_id).audience_language == 'en' else None


BURNED_LANGUAGE_PROMPT = (
    '这几张图是同一个视频画面的底部区域。判断画面上有没有烧录的对白字幕（随说话变化的字幕条），以及它是哪种语言。'
    '台标、角标、logo、产品名、幻灯片或屏幕上的文字都不算字幕。'
    '只返回 JSON：{"language":"zh|en|ja|ko|other|none"}（none 表示没有对白字幕）。'
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
    if not intelligence.source_frame_analysis_allowed():
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
        return language if language in ('zh', 'en', 'ja', 'ko', 'other', 'none') else guess
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


def _speaker_framing(value, video, *, window=None, wait_sec=120, scans=None, cues=None):
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
    result = framing.auto_frame(video, draft, int(info['width']), int(info['height']), window=window, scans=scans[key], cues=cues)
    tracks = {scene['id']: scene for scene in result['scenes']}
    if not any(scene.get('faces') for scene in result['scenes']):
        return None, 'full_frame'
    scenes = [{**scene, 'crop_x': tracks[scene['id']]['crop_x'], 'crop_track': tracks[scene['id']]['crop_track'],
               'framing_source': 'auto', 'framing_adjusted': False} for scene in value['scenes']]
    return scenes, 'speaker'


INTERVIEW_WINDOW = (1080, 810)  # 4:3 speaker window of the interview template


def _project_strategy(project_id, strategy_id):
    """Visual template is a preference; platform language, dimensions and limits stay intact."""
    from dataclasses import replace
    from backend.services.platform_strategy import platform_strategy
    strategy = platform_strategy(strategy_id)
    style = (store.read(project_id).get('generation') or {}).get('portrait_style', 'auto')
    template = {'interview': 'interview_zh', 'podcast': 'podcast_en'}.get(style)
    return replace(strategy, template=template) if template and strategy.aspect == 'portrait' else strategy


def _framing_cues(project_id):
    """Speaker cues for the crop. A missing project is no transcript, and it must not create one."""
    try:
        from backend.core.path_utils import get_projects_directory
        project_dir = get_projects_directory() / str(project_id)
        if not project_dir.is_dir():
            return []
        from backend.services.publish_export import _load_srt_entries
        from backend.services.studio import framing
        return framing.cues_from_entries(_load_srt_entries(project_id))
    except Exception as error:  # noqa: BLE001 - framing still follows the frontal face without a transcript
        logger.warning('Framing cues unavailable: %s', type(error).__name__)
        return []


def _apply_framing(project_id, value, strategy_id, video, burned, cache, portrait_crop=False):
    """Pick true vertical speaker framing when it is safe; otherwise keep the full frame on a backdrop.

    Burned-in captions would be cut by a 9:16 window, so those sources always keep the full frame.
    Tracks depend only on the scenes, so one detection pass is shared by every vertical platform.
    The interview template frames a 4:3 window instead; without a track it shows the whole frame.
    HTML portrait templates cover the full 9:16 frame, so `portrait_crop` frames that window even
    when the platform's classic template is the 4:3 interview. Burned-caption and no-face fallbacks
    stay on the classic layout.
    """
    strategy = _project_strategy(project_id, strategy_id)
    if strategy.aspect != 'portrait':
        return value, None
    interview = strategy.template == 'interview_zh'
    fallback_layout = 'window' if interview else 'blur'
    if burned and _caption_mask(project_id, strategy_id):
        burned = False  # the band is blurred out, so cropping cannot cut captions anyone reads
    if burned:
        plain = [{**scene, 'crop_x': None, 'crop_track': None, 'framing_source': None, 'framing_adjusted': False} for scene in value['scenes']]
        return {**value, 'scenes': plain, 'layout': fallback_layout}, 'full_frame_captions'
    window = None if portrait_crop else (INTERVIEW_WINDOW if interview else None)
    key = (tuple((scene['start'], scene['end']) for scene in value['scenes']), window)
    if 'cues' not in cache:
        cache['cues'] = _framing_cues(project_id)
    if key not in cache:
        try:
            cache[key] = _speaker_framing(value, video, window=window, scans=cache.setdefault('scans', {}), cues=cache['cues'])
        except Exception as error:  # noqa: BLE001 - fall back to the full frame rather than fail output
            logger.warning('Speaker framing failed: %s', type(error).__name__)
            capture_studio_exception(error, 'auto_frame')
            cache[key] = (None, 'full_frame')
    scenes, framing = cache[key]
    if scenes is None:
        # Drop tracks inherited from another platform's framing: they were computed for a different window.
        plain = [{**scene, 'crop_x': None, 'crop_track': None, 'framing_source': None, 'framing_adjusted': False} for scene in value['scenes']]
        return {**value, 'scenes': plain, 'layout': fallback_layout}, framing
    layout = 'crop' if portrait_crop or not interview else 'window'
    return {**value, 'scenes': scenes, 'layout': layout}, framing


def _audience_title(value, strategy_id, post):
    """The version's title in its audience's language: clip titles are written in Chinese."""
    from backend.services.platform_strategy import platform_strategy
    from backend.services.studio.packaging import CJK
    if platform_strategy(strategy_id).audience_language != 'en' or not CJK.search(value.get('title') or ''):
        return value
    from backend.services.studio.packaging import foreign_for
    lines = (value.get('packaging') or {}).get('title_lines') or []
    english = ' '.join(lines) if lines and not any(foreign_for('en', line) for line in lines) else (post or {}).get('title', '')
    if not english or foreign_for('en', english):
        # No English title came back: an English caption line beats the Chinese clip title.
        cues = (value.get('packaging') or {}).get('cues') or []
        english = next((cue['text'] for cue in cues if cue.get('text') and not foreign_for('en', cue['text'])), '') or 'Untitled clip'
    return {**value, 'title': english[:120]}


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
        for variant in targets:
            if variant['id'] in designed:
                request_ai_cover(project_id, variant['id'])


cover_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix='studio-cover')


def request_ai_cover(project_id, variant_id):
    """Share one tracked AI task between automatic covers and requests from the output card."""
    from backend.services import cover
    cfg = cover.load_config()
    if not (cfg.enabled and cfg.configured and cfg.allow_send_frame):
        return None
    job_id = uuid.uuid4().hex

    def claim(data):
        variant = next((item for item in data['output_variants'] if item['id'] == variant_id), None)
        if variant is None:
            raise FileNotFoundError('成片版本不存在')
        active = variant.get('cover_job')
        if active and active['status'] in ('queued', 'running'):
            return active
        variant['cover_job'] = {'job_id': job_id, 'status': 'queued', 'instance': store.INSTANCE}
        return variant['cover_job']

    with store.lock:
        claimed = store.change(project_id, claim)
        if claimed['job_id'] == job_id:
            try:
                cover_executor.submit(_ai_cover_job, project_id, variant_id, job_id, _io_receipt=('cover', variant_id, job_id))
            except Exception as error:  # noqa: BLE001 - preserve the ready video and designed cover
                store.remember_submission_rejection(project_id, ('cover', variant_id, job_id), error_code=studio_error_code(error))
                logger.warning('AI cover dispatch failed: %s', type(error).__name__)
                _update_cover_job(project_id, variant_id, job_id, status='failed', error='AI 封面任务未能启动，请重试')
        return ai_cover_status(project_id, variant_id)


def ai_cover_status(project_id, variant_id):
    variant = next((item for item in store.read(project_id)['output_variants'] if item['id'] == variant_id), None)
    if variant is None or not variant.get('cover_job'):
        raise FileNotFoundError('封面任务不存在')
    return {key: value for key, value in variant['cover_job'].items() if key != 'instance'}


def _update_cover_job(project_id, variant_id, job_id, **values):
    def update(data):
        variant = next(item for item in data['output_variants'] if item['id'] == variant_id)
        job = variant.get('cover_job') or {}
        if job.get('job_id') == job_id:
            job.update(values)
            if values.get('status') == 'completed':
                variant['cover'] = 'ai'
    store.change(project_id, update)


@_tracked('ai_cover')
def _ai_cover_job(project_id, variant_id, job_id):
    from backend.services.studio import publish_kit
    try:
        _update_cover_job(project_id, variant_id, job_id, status='running')
        variant = next(item for item in store.read(project_id).get('output_variants', []) if item['id'] == variant_id)
        with llm_usage.timed('ai_cover'):
            made = publish_kit.ai_cover(project_id, variant['render_job_id'], variant['strategy_id'])
    except Exception as error:  # noqa: BLE001 - the designed cover stays
        store.raise_owned_read_error(error)
        logger.warning('AI cover job failed: %s', type(error).__name__)
        made = False
    _update_cover_job(project_id, variant_id, job_id, **({'status': 'completed'} if made else
                      {'status': 'failed', 'error': 'AI 封面未生成，已保留原封面'}))


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
    _packaging_inputs(project_id, cache)  # load shared inputs once, before the threads
    first = {}
    for strategy_id, value in items:
        strategy = _project_strategy(project_id, strategy_id)
        key = (tuple((scene['start'], scene['end']) for scene in value['scenes']), strategy.template, strategy.audience_language)
        first.setdefault(key, (strategy_id, value))
    map_chunks(lambda item: _apply_packaging(project_id, item[1], item[0], burned, cache), first.values())


def _apply_packaging(project_id, value, strategy_id, burned, cache):
    """Attach template packaging (title, captions, nameplates, tags) for vertical templates.

    One model call per scene set and template; every vertical platform of the same audience
    reuses it. Only the subtitle rows this draft uses are sent.
    """
    strategy = _project_strategy(project_id, strategy_id)
    mask = _caption_mask(project_id, strategy_id) if burned else None
    value = {**{key: item for key, item in value.items() if key != 'caption_mask'}, **({'caption_mask': mask} if mask else {})}
    if mask:
        burned = False
    if strategy.template not in ('interview_zh', 'podcast_en'):
        return {key: item for key, item in value.items() if key != 'packaging'}  # never inherit another template's packaging
    from backend.services.studio import packaging
    _packaging_inputs(project_id, cache)
    key = (tuple((scene['start'], scene['end']) for scene in value['scenes']), strategy.template, strategy.audience_language)
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


def _still_this_run(data, attempt_id, run_id) -> bool:
    """A late failure may write only the run that still owns the generation. A newer attempt is left alone."""
    analysis = data.get('analysis') or {}
    if run_id and analysis.get('run_id') not in (None, run_id):
        return False
    generation = data.get('generation') or {}
    if attempt_id is not None and generation.get('attempt_id') != attempt_id:
        return False
    open_now = attempts.current(data)
    if attempt_id is not None and open_now and open_now.get('attempt_id') != attempt_id:
        return False
    return True


@_tracked('production')
def _auto_generate(project_id, plan):
    """Produce and render platform variants after the cheap screening pass."""
    from backend.core.job_budget import bind_clip_job, unbind_clip_job
    started = monotonic()
    state = store.read(project_id)
    generation = state.get('generation') or {}
    attempt_id = generation.get('attempt_id')
    run_id = (state.get('analysis') or {}).get('run_id')
    platforms = generation.get('requested_platforms') or []
    branding = generation.get('branding') or {'outro_enabled': True, 'outro_version': 'v1'}
    skipped = []
    budget = bind_clip_job()
    try:
        try:
            video = source(project_id)
            derived_drafts, variants, events = _initial_derive(project_id, plan, video, generation, platforms, branding, skipped)

            def persist(data):
                if not _still_this_run(data, attempt_id, run_id):
                    raise store.ConflictError('这次制作已结束')
                data['drafts'].extend({**draft, 'updated_at': store.now()} for draft in derived_drafts)
                if events:
                    data['events'] = events
                attempts.own_outputs(data, variants)  # produced by this run's attempt and its plan
                data['output_variants'].extend(variants)
                data['generation'].update(status='rendering', skipped=skipped, started_at=data['generation'].get('started_at') or store.now(), **_generation_route(data.get('plan')))
                from backend.services.studio.failure_identity import carry_screening
                data['analysis'] = {**store.attempt_identity(data.get('analysis'), data.get('generation')), **carry_screening(data.get('analysis'), data.get('generation')), **_carried_progress(data.get('analysis')), 'status': 'running', 'phase': 'rendering', 'run_id': (data.get('analysis') or {}).get('run_id'), 'message': '正在生成可发布成片', 'instance': store.INSTANCE, 'created_at': store.now()}
            store.change(project_id, persist)
            _dispatch_pending_variants(project_id)
        except Exception as error:
            unbind_clip_job(budget)
            budget = None
            _fail_generation(project_id, error, started, skipped, attempt_id, run_id)
    finally:
        unbind_clip_job(budget)


def _fail_generation(project_id, error, started, skipped, attempt_id=None, run_id=None):
    """The failure branch of a generation run: attribution snapshot, run_id kept, duration_ms, mark_project.
    A round that took over the generation since is left alone."""
    store.raise_owned_read_error(error)
    capture_studio_exception(error, 'production')
    code = studio_error_code(error)
    context = studio_failure_context(error, 'production')
    error_text = user_visible_error(error)
    def fail(data):
        return store.settle_attempt(data, kind='fail', error=error_text, error_code=code, skipped=skipped, context=context, duration_ms=round((monotonic() - started) * 1000), guard=lambda d: _still_this_run(d, attempt_id, run_id))
    if store.change(project_id, fail):
        mark_project(project_id, 'failed')


def _initial_derive(project_id, plan, video, generation, platforms, branding, skipped):
    """The first generation's derive step: content drafts -> platform variants (unchanged loop)."""
    from backend.services.platform_strategy import long_form_minimum, platform_strategy
    min_sec, _label = long_form_minimum(platforms)
    duration = _known_source_duration(video) if min_sec else None
    # A source that cannot hold the long-form minimum never reaches the model when that
    # platform is the whole job. Mixed selections still analyze, then skip only the long version.
    if min_sec and duration is not None and duration < min_sec and _platforms_are_long(platforms):
        _record_long_skips(platforms, (), skipped)
        raise UserFacingError(sentence('no_complete_version'))
    produced = _content_drafts(project_id, plan, video, platforms)
    if isinstance(produced, tuple):
        base_drafts, events, coverage = produced
    else:
        base_drafts, events, coverage = produced, [], None
    if min_sec and duration is not None:
        base_drafts = _ensure_long_coverage(base_drafts, duration, min_sec)
    variants = []
    derived_drafts = []
    burned = _source_has_burned_subtitles(project_id, video)
    framing_cache = {}
    packaging_cache = {}
    # Platform eligibility must precede the score limit: otherwise ten short clips
    # can exclude the only valid YouTube long clip and leave nothing to render.
    limit = _render_limit(generation.get('features'))
    scores = {draft['id']: draft[SCORE_KEY] for draft in base_drafts if SCORE_KEY in draft}
    automatic = {
        strategy_id: _automatic_drafts([base for base in base_drafts
            if _draft_usable(base, platform_strategy(strategy_id))], limit)
        for strategy_id in platforms
    }
    _record_long_skips(platforms, base_drafts, skipped)
    from backend.services.studio.template_choice import html_candidate_ids, selected_template
    chosen = selected_template(generation)
    html_ids = html_candidate_ids(base_drafts) if chosen else set()
    planned = []
    for base in base_drafts:
        source_id = base['id']
        long_only = bool(base.get(LONG_ONLY_KEY))
        base = {key: item for key, item in base.items() if key not in (SCORE_KEY, LONG_ONLY_KEY)}
        for strategy_id in platforms:
            strategy = platform_strategy(strategy_id)
            if long_only and strategy.duration_policy != 'long':
                continue
            if not _eligible_for_platform(base, strategy):
                continue
            value, trimmed = _fit_platform_limit(project_id, {**base, 'id': uuid.uuid4().hex, 'revision': 1}, strategy)
            now = source_id in automatic[strategy_id]
            use_html = bool(chosen) and now and strategy.aspect == 'portrait' and source_id in html_ids
            rank_fallback = bool(chosen) and now and strategy.aspect == 'portrait' and source_id not in html_ids
            framed = None  # on-demand versions are framed and packaged when the user asks (produce_variant)
            if now:
                with llm_usage.timed('framing'):
                    value, framed = _apply_framing(project_id, value, strategy_id, video, burned, framing_cache, use_html)
            planned.append((strategy_id, value, trimmed, framed, now, use_html, rank_fallback, source_id))
    with llm_usage.timed('packaging'):
        _prefetch_packaging(project_id, [(strategy_id, value) for strategy_id, value, _, _, now, _, _, _source in planned if now], burned, packaging_cache)
    with llm_usage.timed('post_copy'):
        posts = _posts_for(project_id, [(strategy_id, value) for strategy_id, value, _, _, now, _, _, _source in planned if now], packaging_cache)
    for strategy_id, value, trimmed, framed, now, use_html, rank_fallback, source_id in planned:
        if now:
            value = _apply_packaging(project_id, value, strategy_id, burned, packaging_cache)
            value = _audience_title(value, strategy_id, posts.get((_content_key(value), strategy_id)))
        layout = 'crop' if use_html and framed != 'full_frame_captions' else (value.get('layout') if framed else None)
        draft = _apply_strategy(value, strategy_id, burned_subtitles=burned, layout=layout, output_captions=_snapshotted_captions(generation))
        derived_drafts.append(draft.model_dump())
        variants.append({
            'id': uuid.uuid4().hex, 'draft_id': draft.id, 'draft_revision': draft.revision,
            'strategy_id': strategy_id, 'strategy_version': 1, 'branding': branding,
            'status': 'queued' if now else 'on_demand', 'created_at': store.now(),
            **({SCORE_KEY: scores[source_id]} if source_id in scores else {}),
            **({'trimmed_to_sec': trimmed} if trimmed else {}),
            **({'framing': framed} if framed else {}),
            **({'post': posts[_content_key(value), strategy_id]} if (_content_key(value), strategy_id) in posts else {}),
            **({'html_template': chosen} if use_html else {}),
            **({'html_fallback': 'rank', 'requested_template': chosen} if rank_fallback else {}),
        })
    _queue_best_first(variants)
    if not variants:
        raise UserFacingError(sentence('no_complete_version'))
    return derived_drafts, variants, events



def append_platform_variants(project_id, platforms, branding):
    """1.5.7 does not append platforms. Refuse before any read of the workspace that could open an attempt,
    freeze input, or schedule work. The route and this function are the only entry points; both stop here.
    Follow-up: 1.5.9."""
    del project_id, platforms, branding
    raise attempts.AppendRejected('这一版还不能追加平台，请新建一个项目', 'append_platform_unavailable')


def _submit_production(project_id, run_id, plan, *, attempt_id=None):
    """Hand a generation run to the worker. A refused hand-off fails THIS run at the dispatch stage.
    The same guard as _fail_generation: a newer attempt that took over the generation is not rewritten."""
    try:
        executor.submit(_auto_generate, project_id, plan, _io_receipt=('analysis', run_id, 'production'))
    except Exception as error:
        store.analysis_handoff_rejected(project_id, run_id)
        store.remember_submission_rejection(project_id, ('analysis', run_id, 'production'), error_code=studio_error_code(error))
        capture_studio_exception(error, 'dispatch')
        message = '自动制作任务未能启动，请重试；原素材已保留'
        code = studio_error_code(error)
        def fail_automatic(data):
            return store.settle_attempt(data, kind='fail', error=message, error_code=code, failure_stage='dispatch', route=_generation_route(plan), run_id=run_id, carry=False, identify=False, guard=lambda d: _still_this_run(d, attempt_id, run_id))
        if store.change(project_id, fail_automatic):
            mark_project(project_id, 'failed')


def export_variant(variants, draft_id: str, *, variant_id: str | None = None, revision: int | None = None, aspect: str | None = None):
    """The output row whose template this draft export should keep.

    Several platform rows can share one draft. A named id wins. Otherwise one
    row, the row at this revision, or the row whose strategy matches the draft
    aspect. Differing templates without an id are not guessed from list order.
    """
    matched = [item for item in variants or [] if isinstance(item, dict) and item.get('draft_id') == draft_id]
    if variant_id:
        named = next((item for item in matched if item.get('id') == variant_id), None)
        if named is not None:
            return named
    if len(matched) <= 1:
        return matched[0] if matched else None
    pool = [item for item in matched if revision is not None and item.get('draft_revision') == revision] or matched
    if len(pool) == 1:
        return pool[0]
    if aspect and aspect != 'original':
        from backend.services.platform_strategy import PLATFORM_STRATEGIES
        sided = []
        for item in pool:
            spec = PLATFORM_STRATEGIES.get(str(item.get('strategy_id') or ''))
            if spec is not None and spec.aspect == aspect:
                sided.append(item)
        if len(sided) == 1:
            return sided[0]
        if sided:
            pool = sided
    styles = {template_export_kwargs(item).get('html_template') for item in pool}
    if len(styles) <= 1:
        return pool[0]
    return None


def template_export_kwargs(variant) -> dict:
    """Template arguments recorded on an automatic variant.

    Production and editor re-export both pass this dict into `export`. Without it, a
    magazine or street clip is rendered with the classic interview title.
    """
    if not isinstance(variant, dict):
        return {}
    from backend.services.studio.overlay_fill import SAFE_AREAS
    if variant.get('html_template'):
        strategy = variant.get('strategy_id')
        return {
            'html_template': variant['html_template'],
            'safe_area': strategy if strategy in SAFE_AREAS else 'xiaohongshu',
        }
    if variant.get('html_fallback'):
        kwargs = {'html_fallback': variant['html_fallback']}
        if variant.get('requested_template') in HTML_TEMPLATE_IDS:
            kwargs['requested_template'] = variant['requested_template']
        return kwargs
    return {}


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
        expected = store.change(project_id, lambda data: store.claim_render(data, store.variant_identity(variant)))
        if expected is None:
            continue
        raw = drafts.get(variant['draft_id'])
        if not raw:
            store.change(project_id, lambda data: store.settle_attempt(data, kind='reject', variant_id=expected[0], expected=expected, error='来源草稿不存在', error_code='missing_resource'))
            continue
        try:
            job = export(
                project_id, Draft.model_validate(raw),
                brand_outro=bool(variant['branding'].get('outro_enabled', True)),
                _variant_identity=expected, **template_export_kwargs(variant),
            )
        except Exception as error:
            store.raise_owned_read_error(error)
            capture_studio_exception(error, 'dispatch')
            code = studio_error_code(error)
            store.change(project_id, lambda data: store.settle_attempt(data, kind='reject', variant_id=expected[0], expected=expected, error='这条成片任务未能启动，请重试；已有成片已保留', error_code=code))
            continue
        store.remember_render_link(project_id, expected, job['job_id'])
        store.change(project_id, lambda data, expected=expected, job_id=job['job_id']: store.bind_render(data, expected, job_id))
    # Failed dispatch prerequisites or a backup-only batch have no render callback to
    # settle them. Queued/running/preparing variants still keep generation open.
    store.change(project_id, lambda data: _finish_generation(data) if data.get('generation') and data.get('output_variants') else None)
    sync_project_completion(project_id)


SCORE_KEY = '_auto_score'
AUTO_RENDER_LIMIT = 10  # clips rendered automatically per import; the rest wait for a click


LONG_ONLY_KEY = '_long_only'
LONG_SKIP_REASON = '素材没有足够完整的长内容'


def _known_source_duration(video):
    """Probed seconds, or None when the container duration cannot be read."""
    try:
        raw = intelligence._probe(video).get('duration')
        return float(raw) if raw else None
    except Exception:
        logger.warning('source duration probe failed', exc_info=True)
        return None


def _platforms_are_long(platforms):
    from backend.services.platform_strategy import platform_strategy
    return bool(platforms) and all(platform_strategy(item).duration_policy == 'long' for item in platforms)


def _record_long_skips(platforms, drafts, skipped):
    """One visible skip per long platform that still has no usable draft."""
    from backend.services.platform_strategy import platform_strategy
    for strategy_id in platforms:
        strategy = platform_strategy(strategy_id)
        if strategy.duration_policy != 'long':
            continue
        if any(_draft_usable(draft, strategy) for draft in drafts):
            continue
        if any(item.get('strategy_id') == strategy_id for item in skipped):
            continue
        skipped.append({'strategy_id': strategy_id, 'reason': LONG_SKIP_REASON})


def _draft_usable(draft, strategy):
    """A span grown only to satisfy a long platform is not offered to the short ones."""
    if draft.get(LONG_ONLY_KEY) and strategy.duration_policy != 'long':
        return False
    return _eligible_for_platform(draft, strategy)


def _grow_span(start, end, min_sec, floor, ceiling):
    """Grow [start, end] to min_sec inside [floor, ceiling], extending the end first."""
    floor, ceiling = float(floor), float(ceiling)
    start = min(max(float(start), floor), ceiling)
    end = min(max(float(end), start), ceiling)
    if ceiling - floor < min_sec:
        return None
    if end - start >= min_sec:
        return start, end
    need = min_sec - (end - start)
    after = ceiling - end
    if after > 0:
        take = min(need, after)
        end += take
        need -= take
    if need > 1e-6:
        before = start - floor
        start -= min(need, max(0.0, before))
    if end - start + 1e-3 < min_sec:
        return None
    if end - start < min_sec:
        end = min(ceiling, start + min_sec)
        if end - start < min_sec:
            start = max(floor, end - min_sec)
        if start < floor or end - start + 1e-3 < min_sec:
            return None
    return start, end


def _pick_long_run(pieces, source_duration, min_sec):
    """Narrowest run of time-adjacent pieces that can reach min_sec inside the source."""
    count = len(pieces)
    for width in range(1, count + 1):
        best = None
        for index in range(0, count - width + 1):
            run = pieces[index:index + width]
            start, end = run[0]['start'], run[-1]['end']
            floor = pieces[index - 1]['end'] if index else 0.0
            ceiling = pieces[index + width]['start'] if index + width < count else source_duration
            fitted = _grow_span(start, end, min_sec, min(floor, start), max(ceiling, end))
            if fitted is None:
                continue
            score = max(item['score'] for item in run)
            if best is None or score > best[0]:
                best = (score, fitted[0], fitted[1], max(run, key=lambda item: item['score']))
        if best is not None:
            return best[1], best[2], best[3]
    return None


def _ensure_long_coverage(drafts, source_duration, min_sec):
    """Append one >= min_sec draft when the source can hold it and none of the picks already do.

    Short drafts stay, so other platforms keep them. The added draft is marked long-only.
    Growth stays inside [0, source_duration]: a short source is left unchanged.
    """
    if not drafts or source_duration is None or source_duration < min_sec:
        return drafts
    if any(not draft.get(LONG_ONLY_KEY) and _draft_duration(draft) >= min_sec for draft in drafts):
        return drafts
    pieces = []
    for index, draft in enumerate(drafts):
        if draft.get(LONG_ONLY_KEY):
            continue
        try:
            score = float(draft.get(SCORE_KEY) or 0)
        except (TypeError, ValueError):
            score = 0.0
        for scene in draft.get('scenes') or []:
            start, end = float(scene.get('start') or 0), float(scene.get('end') or 0)
            end = min(end, float(source_duration))
            start = max(0.0, min(start, end))
            if end - start <= 0:
                continue
            pieces.append({
                'start': start, 'end': end, 'score': score, 'index': index,
                'title': scene.get('label') or draft.get('title') or '内容片段',
                'evidence': scene.get('evidence') or '',
            })
    pieces.sort(key=lambda item: (item['start'], item['end']))
    chosen = _pick_long_run(pieces, float(source_duration), min_sec)
    if chosen is None:
        return drafts
    start, end, piece = chosen
    template = drafts[piece['index']]
    scene = {
        'id': uuid.uuid4().hex,
        'label': str(piece['title'])[:120],
        'start': start,
        'end': end,
        'evidence': str(piece['evidence'])[:1000],
    }
    logger.info('extended a long-form span to %.0fs within a %.0fs source', end - start, source_duration)
    return [*drafts, {
        **template,
        'id': uuid.uuid4().hex,
        'title': scene['label'],
        'scenes': [scene],
        SCORE_KEY: piece['score'],
        LONG_ONLY_KEY: True,
    }]


def _draft_duration(draft):
    return sum(scene['end'] - scene['start'] for scene in draft.get('scenes') or [])


def _eligible_for_platform(draft, strategy):
    duration = _draft_duration(draft)
    return strategy.duration_policy != 'long' or duration >= (strategy.min_recommended_duration_sec or 0)


def _score(clip):
    try:
        return float(clip.get('final_score'))
    except (TypeError, ValueError):
        return 0.0


def _render_limit(features):
    """Automatic cap for one import. The default stays at AUTO_RENDER_LIMIT."""
    return 3 if flag_enabled(features, 'render_top_first') else AUTO_RENDER_LIMIT


def _queue_best_first(variants):
    """Render the highest score first. The score is not stored on the variant."""
    def key(item):
        try:
            score = float(item[SCORE_KEY]) if SCORE_KEY in item else None
        except (TypeError, ValueError):
            score = None
        return (item.get('status') == 'on_demand', score is None, -(score or 0))
    variants.sort(key=key)
    for item in variants:
        item.pop(SCORE_KEY, None)
    return variants


def _automatic_drafts(base_drafts, limit=None):
    """Ids of the drafts rendered without asking: the highest-scored `limit`.

    A two-hour talk yields 30+ clips; rendering all of them up front cost most of the run, while
    people publish a handful. Drafts without a score (visual highlights, at most a few) all render.
    The default cap stays AUTO_RENDER_LIMIT so older callers keep the top ten.
    """
    cap = AUTO_RENDER_LIMIT if limit is None else limit
    scored = [draft for draft in base_drafts if SCORE_KEY in draft]
    if len(scored) <= cap:
        return {draft['id'] for draft in base_drafts}
    top = sorted(scored, key=lambda draft: draft[SCORE_KEY], reverse=True)[:cap]
    return {draft['id'] for draft in top} | {draft['id'] for draft in base_drafts if SCORE_KEY not in draft}


def produce_variant(project_id, variant_id):
    """Frame, package and render one on-demand variant."""
    def start(data):
        item = next((value for value in data.get('output_variants', []) if value['id'] == variant_id), None)
        if not item:
            raise FileNotFoundError('成片版本不存在')
        if item.get('status') != 'on_demand':
            raise UserFacingError('这条成片已经在生成或已完成')
        if not any(draft['id'] == item['draft_id'] for draft in data.get('drafts', [])):
            raise FileNotFoundError('来源草稿不存在')
        return _start_preparing(data, item)
    # One locked change checks and claims: a double click must not prepare (and pay for) it twice.
    attempt_id = store.change(project_id, start)
    _submit_on_demand(project_id, variant_id, attempt_id)
    return next(item for item in store.read(project_id)['output_variants'] if item['id'] == variant_id)


def _start_preparing(data, item):
    # 'preparing' is invisible to _dispatch_pending_variants: rendering the stored draft now would
    # ship it without speaker framing, packaging or captions.
    item.update(status='preparing', instance=store.INSTANCE, preparation_run_id=uuid.uuid4().hex)
    for key in ('error', 'error_code', 'needs_prepare', 'render_job_id', 'render_attempt_id', 'render_dispatch_claimed', 'render_dispatch_instance'):
        item.pop(key, None)
    data['generation'].update(status='rendering')
    return item['preparation_run_id']


def _submit_on_demand(project_id, variant_id, attempt_id):
    try:
        executor.submit(_produce_on_demand, project_id, variant_id, _io_receipt=('preparation', variant_id, attempt_id))
    except Exception as error:
        store.remember_submission_rejection(project_id, ('preparation', variant_id, attempt_id), error_code=studio_error_code(error))
        capture_studio_exception(error, 'dispatch')
        message = '这条成片任务未能启动，请重试；已有成片已保留'
        code = studio_error_code(error)
        def failed(data):
            target = next(item for item in data['output_variants'] if item['id'] == variant_id)
            target.update(status='failed', error=message, error_code=code, needs_prepare=True)
            target.pop('instance', None)
            _finish_generation(data)
        store.change(project_id, failed)
        sync_project_completion(project_id)
        raise UserFacingError(message) from None


@_tracked('production')
def _produce_on_demand(project_id, variant_id):
    from backend.core.job_budget import JobDurationExceeded, bind_clip_job, unbind_clip_job
    budget = bind_clip_job()
    try:
        try:
            state = store.read(project_id)
            variant = next(item for item in state['output_variants'] if item['id'] == variant_id)
            raw = next(item for item in state['drafts'] if item['id'] == variant['draft_id'])
            video = source(project_id)
            burned = _source_has_burned_subtitles(project_id, video)
            strategy_id = variant['strategy_id']
            value, framed = _apply_framing(project_id, raw, strategy_id, video, burned, {})
            value = _apply_packaging(project_id, value, strategy_id, burned, {})
            posts = _posts_for(project_id, [(strategy_id, value)], {})
            value = _audience_title(value, strategy_id, posts.get((_content_key(value), strategy_id)))
            draft = _apply_strategy(value, strategy_id, burned_subtitles=burned, layout=value.get('layout') if framed else None, output_captions=_snapshotted_captions(state.get('generation'))).model_dump()

            def ready(data):
                for index, item in enumerate(data['drafts']):
                    if item['id'] == draft['id']:
                        data['drafts'][index] = {**draft, 'updated_at': store.now()}
                target = next(item for item in data['output_variants'] if item['id'] == variant_id)
                if framed:
                    target['framing'] = framed
                if (_content_key(value), strategy_id) in posts:
                    target['post'] = posts[_content_key(value), strategy_id]
                target['status'] = 'queued'  # ready: only now may a dispatcher render it
                target.pop('instance', None)
            store.change(project_id, ready)
            _dispatch_pending_variants(project_id)
        except Exception as error:
            unbind_clip_job(budget)
            budget = None
            store.raise_owned_read_error(error)  # noqa: BLE001 - the variant shows the failure and can be retried
            logger.warning('On-demand variant failed: %s', type(error).__name__)
            capture_studio_exception(error, 'production')
            code = studio_error_code(error)
            message = str(error) if isinstance(error, JobDurationExceeded) else '这条成片准备失败，请重试'

            def failed(data):
                target = next(item for item in data['output_variants'] if item['id'] == variant_id)
                target.update(status='failed', error=message, error_code=code, needs_prepare=True)
                target.pop('instance', None)
                _finish_generation(data)
            try:
                store.change(project_id, failed)
                sync_project_completion(project_id)
            except Exception:  # noqa: BLE001 - never lose the failure silently inside the executor
                logger.exception('Could not record the on-demand failure')
    finally:
        unbind_clip_job(budget)


def _retry_parent(data, parent_attempt_id):
    """The retry command's checks (one place): parent is a failed/partial v4 attempt with no newer attempt;
    without an explicit parent the latest settled attempt is used when it failed/partial."""
    if not parent_attempt_id:
        settled = [a for a in attempts.receipts(data) if a.get('state') in attempts.TERMINAL]
        latest = max(settled, key=lambda a: a.get('sequence', 0), default=None)
        parent_attempt_id = latest['attempt_id'] if latest and latest['state'] in attempts.RETRYABLE_PARENT else None
    if attempts.current(data) and not attempts.unbound(attempts.current(data)):
        raise attempts.RetryRejected('上一次重试还没结束，请稍后再试')
    return attempts.check_parent(data, parent_attempt_id)


def _variant_attempt(data, retry, variant):
    """「重试这条」 is a new aggregate generation attempt; a second one while it is open joins it (serial)."""
    open_now = attempts.current(data)
    if open_now and open_now['kind'] == 'generation' and open_now.get('trigger') == 'variant_retry':
        receipt = attempts.check_join(data, open_now, (retry or {}).get('parent_attempt_id'), (retry or {}).get('key'))
    else:
        parent = _retry_parent(data, (retry or {}).get('parent_attempt_id'))
        receipt = attempts.open_attempt(data, 'generation', trigger='variant_retry', parent=parent,
                                        run_id=uuid.uuid4().hex, key=(retry or {}).get('key'), now=store.now())
    # the plan and outputs come from the attempt that produced THIS variant, not the retry parent
    attempts.inherit_plan(receipt, data, variant)
    variant['redone_by_attempt'] = receipt['attempt_id']  # this round is judged on what it redid
    data['generation']['attempt_id'] = receipt['attempt_id']
    return receipt


def retry_variant(project_id, variant_id, retry=None):
    state = store.read(project_id)
    if retry is not None and attempts.by_key(state, retry.get('key')):
        return next(item for item in state['output_variants'] if item['id'] == variant_id)
    variant = next((item for item in state.get('output_variants', []) if item['id'] == variant_id), None)
    if not variant:
        raise FileNotFoundError('成片版本不存在')
    if variant.get('status') != 'failed':
        raise UserFacingError('只有失败的成片版本可以重试')
    raw = next((item for item in state.get('drafts', []) if item['id'] == variant['draft_id']), None)
    if not raw:
        raise FileNotFoundError('来源草稿不存在')
    if variant.get('needs_prepare'):
        def prepare(data):
            item = next(value for value in data['output_variants'] if value['id'] == variant_id)
            if item.get('status') != 'failed':
                raise UserFacingError('只有失败的成片版本可以重试')
            receipt = _variant_attempt(data, retry, item)
            data['analysis'] = {**store.attempt_identity(data.get('analysis'), data.get('generation')), **_carried_progress(data.get('analysis')), 'status': 'running', 'phase': 'rendering', 'run_id': receipt['run_id'], 'message': '正在重试成片版本', 'instance': store.INSTANCE, 'created_at': store.now()}
            return _start_preparing(data, item)
        attempt_id = store.change(project_id, prepare)
        _submit_on_demand(project_id, variant_id, attempt_id)
        return next(item for item in store.read(project_id)['output_variants'] if item['id'] == variant_id)
    def update(data):
        item = next(value for value in data['output_variants'] if value['id'] == variant_id)
        if item.get('status') != 'failed':
            raise UserFacingError('只有失败的成片版本可以重试')
        item.update(status='queued', render_attempt_id=uuid.uuid4().hex)
        item.pop('render_dispatch_claimed', None)
        item.pop('render_dispatch_instance', None)
        item.pop('render_job_id', None)
        item.pop('error', None)
        item.pop('error_code', None)
        data['generation'].update(status='rendering')
        receipt = _variant_attempt(data, retry, item)
        data['analysis'] = {**store.attempt_identity(data.get('analysis'), data.get('generation')), **_carried_progress(data.get('analysis')), 'status': 'running', 'phase': 'rendering', 'run_id': receipt['run_id'], 'message': '正在重试成片版本', 'instance': store.INSTANCE, 'created_at': store.now()}
    store.change(project_id, update)
    _dispatch_pending_variants(project_id)
    return next(item for item in store.read(project_id)['output_variants'] if item['id'] == variant_id)


def _sync_variant_status(project_id, job_id, status, error=None):
    def update(data):
        changed = False
        if status in ('completed', 'failed'):
            for job in data.get('jobs', []):
                if job.get('job_id') == job_id and not job.get('finished_at'):
                    job['finished_at'] = store.now()
        for variant in data.get('output_variants', []):
            if variant.get('render_job_id') == job_id:
                current = variant.get('status')
                if current == 'cancelled' and status == 'completed':
                    continue
                if current == 'completed' and status == 'cancelled':
                    continue
                variant.update(status=status)
                if error:
                    variant['error'] = error
                changed = True
        if changed:
            _finish_generation(data)
    store.change(project_id, update)
    sync_project_completion(project_id)


def _finish_generation(data):
    store.settle_attempt(data, kind='finish')


def inspect_project(project_id, options, url=None, browser=None, *, producer=None, features=None, retry=None):
    """Only ingest and screen. Expensive production requires an explicit confirmation.

    ``retry`` ({'parent_attempt_id', 'key'}) is set only by the retry command (``retry_analysis``)."""
    from backend.services.studio import readiness
    readiness.ensure_analysis_usable()
    # Reserve and dispatch together so another request cannot observe an
    # accepted task before submission succeeds. Preserve existing exports/plan.
    with store.lock:
        previous = store.recover(project_id)
        if retry is not None:
            again = attempts.by_key(previous, retry.get('key'))
            if again:  # the same click again: same receipt, nothing dispatched twice
                return again.get('run_id')
            parent = _retry_parent(previous, retry.get('parent_attempt_id'))
        if (previous.get('analysis') or {}).get('status') == 'running':
            raise UserFacingError('当前任务正在运行，请稍后再试')
        state = deepcopy(previous)
        state.setdefault('schema_version', 2)
        from backend.services.output_captions import load_settings as load_output_captions
        from backend.services.studio.template_choice import style_for_request
        style = style_for_request(getattr(options, 'html_template', None), features)
        state['generation'] = {
            'requested_platforms': list(options.platforms),
            'branding': options.branding.model_dump(),
            'output_captions': load_output_captions().enabled,
            'auto_start': options.auto_start,
            'portrait_style': options.portrait_style,
            **({'html_template': options.html_template} if getattr(options, 'html_template', None) else {}),
            **({'recommended_template': options.recommended_template} if getattr(options, 'recommended_template', None) else {}),
            **({'accepted_recommendation': options.html_template == options.recommended_template} if getattr(options, 'recommended_template', None) and getattr(options, 'html_template', None) else {}),
            **style,
            'features': resolve_features(features),
            **({'producer': producer} if producer else {}),
            'status': 'screening',
            'created_at': store.now(),
        }
        state.setdefault('output_variants', [])
        from backend.services.studio.failure_identity import SCREENING_KEY, frozen, phase_identity
        screening = phase_identity('screening')
        state['analysis'] = {**screening, **({SCREENING_KEY: frozen(screening)} if screening else {}), 'status':'running', 'phase':'screening', 'run_id':uuid.uuid4().hex, 'message':'准备素材' if url else '快速判断适合的制作类型', 'instance':store.INSTANCE, 'created_at':store.now()}
        state['generation'].update(store.attempt_identity(state['analysis']), **({SCREENING_KEY: frozen(screening)} if screening else {}))
        # #419: automatic output is one generation attempt from this run; a manual retry opens the production
        # attempt now (bound at confirmation) so its retry_of survives the screening step.
        if options.auto_start or retry is not None:
            receipt = attempts.open_attempt(
                state, 'generation' if options.auto_start else 'production', trigger='retry' if retry is not None else 'initial',
                parent=parent if retry is not None else None, run_id=state['analysis']['run_id'] if options.auto_start else None,
                key=(retry or {}).get('key'), now=store.now())
            if options.auto_start:
                state['generation']['attempt_id'] = receipt['attempt_id']
        store.write(project_id, state)
        try:
            from backend.core.llm_telemetry import emit_asr_readiness_checked
            emit_asr_readiness_checked(has_subtitle=_project_has_subtitle(project_id))
        except Exception:  # noqa: BLE001
            logger.debug('asr_readiness_checked was skipped', exc_info=True)
        if options.auto_start:
            _prepare_speaker_framing(options.platforms)
        try:
            executor.submit(_inspect, project_id, options, url, browser, _io_receipt=('analysis', state['analysis']['run_id'], 'screening'))
        except Exception as error:
            store.remember_submission_rejection(project_id, ('analysis', state['analysis']['run_id'], 'screening'), error_code=studio_error_code(error))
            logger.warning('Studio screening dispatch failed: %s', type(error).__name__)
            capture_studio_exception(error, 'dispatch')
            message = '导入任务未能启动，请重试；原素材与已有成片已保留'
            if not previous.get('analysis'):
                previous['analysis'] = {'status':'failed', 'phase':'screening', 'error':message}
            # This unaccepted reservation must not enter terminal history before rollback.
            store.write(project_id, previous, restore=True)  # rollback is not a transition
            raise UserFacingError(message) from None

        return state['analysis']['run_id']


@_tracked('screening')
def _inspect(project_id, options, url, browser):
    started = monotonic()
    try:
        from backend.services.studio.planning import recommend
        mark_project(project_id, 'processing', awaiting_confirmation=False)
        if url:
            with llm_usage.timed('download'):
                download(project_id, url, browser)
        store.change(project_id, lambda data:(data['analysis'].pop('percent', None), data['analysis'].update(message='快速判断适合的制作类型')))
        plan = recommend(source(project_id), options)
        ensure_project_thumbnail(project_id)
        plan['id'] = uuid.uuid4().hex
        if options.auto_start:
            from backend.services.studio.failure_identity import SCREENING_KEY, phase_identity, screening_identity
            production_identity = phase_identity('production', plan)
            def start_automatic(data):
                run_id = (data.get('analysis') or {}).get('run_id')  # observers match the run across phases
                screening = screening_identity(data.get('analysis'))
                data.update(plan=plan, analysis={**production_identity, **({SCREENING_KEY: screening} if screening else {}), 'status': 'running', 'phase': 'production', 'run_id': run_id, 'message': '正在制作可发布成片', 'instance': store.INSTANCE, 'created_at': store.now()})
                receipt = attempts.current(data)
                if receipt and receipt.get('attempt_id') == (data.get('generation') or {}).get('attempt_id'):
                    attempts.bind_plan(receipt, plan)  # this attempt's own plan
                data['generation'].update(status='production', started_at=store.now(), **_generation_route(plan), **store.attempt_identity(data.get('analysis')))
                return run_id
            run_id = store.change(project_id, start_automatic)
            mark_project(project_id, 'processing', creative=plan['preferences'], awaiting_confirmation=False, import_staging=False)
            attempt_id = (store.read(project_id).get('generation') or {}).get('attempt_id')
            _submit_production(project_id, run_id, plan, attempt_id=attempt_id)
            return
        def awaiting_confirmation(data):
            from backend.services.studio.failure_identity import SCREENING_KEY, screening_identity
            screening = screening_identity(data.get('analysis'))
            data.update(plan=plan, analysis={**screening, **({SCREENING_KEY: screening} if screening else {}), 'status':'awaiting_confirmation', 'created_at':store.now(), 'duration_ms':round((monotonic() - started) * 1000)})
            if data.get('generation'):
                data['generation']['status'] = 'awaiting_confirmation'
        store.change(project_id, awaiting_confirmation)
        mark_project(project_id, 'pending', creative=plan['preferences'], awaiting_confirmation=True)
    except Exception as error:
        store.raise_owned_read_error(error)
        logger.warning('Studio screening failed: %s', type(error).__name__)
        capture_studio_exception(error, 'screening')
        text = user_visible_error(error)
        failure = {'status':'failed','phase':'screening','error':text, 'error_code':studio_error_code(error), 'duration_ms':round((monotonic() - started) * 1000)}
        if getattr(error, 'probe_detail', None):
            failure['probe_detail'] = error.probe_detail
        context = studio_failure_context(error, 'screening')
        try:
            def fail_screening(data):
                from backend.services.studio.failure_identity import SCREENING_KEY, screening_identity
                screening = screening_identity(data.get('analysis'))
                context.update(screening)
                failure.update(context)
                if screening:
                    failure[SCREENING_KEY] = screening
                return store.settle_attempt(data, kind='screen', failure=failure, context=context)
            store.change(project_id, fail_screening)
            mark_project(project_id, 'failed')
        except FileNotFoundError:
            pass


def confirm_project(project_id, body):
    from backend.services.studio import readiness
    readiness.ensure_analysis_usable()
    with store.lock:
        state = store.recover(project_id)
        plan = state.get('plan') or {}
        if plan.get('id') != body.plan_id or (state.get('analysis') or {}).get('status') != 'awaiting_confirmation':
            raise store.ConflictError('方案已变化或任务已开始，请刷新后确认')
        route = body.analysis_mode or plan.get('recommended_analysis', 'subtitle')
        if route == 'visual' and body.goals == ['content']:
            raise UserFacingError('内容切片当前使用字幕分析，请选择字幕模式后确认')
        if route == 'visual':
            from backend.services.studio import intelligence
            if not intelligence.ready():
                raise UserFacingError('视觉模型不可用，请配置后重新确认；原素材已保留')
        if route == 'subtitle' or 'content' in body.goals:
            # Too short / no audio and no SRT: refuse before production spends any model call (RC156 #10/#11).
            # The one preflight on the confirmed subtitle route (#418 rewrite): source first, then the install
            # prompt (coded 422, waiting codes kept as is), before production spends any model call.
            from backend.services.studio import preflight
            video = source(project_id)
            preflight.check(preflight.ResolvedInputs(video, video.parent / 'input.srt', entry='studio', route='subtitle'))
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
        from backend.services.studio.failure_identity import phase_identity
        state['analysis'] = {**phase_identity('production', plan, body.goals), 'status':'running', 'phase':'production', 'run_id':uuid.uuid4().hex, 'message':'开始制作所选内容', 'instance':store.INSTANCE, 'created_at':store.now()}
        # #419: the production attempt is the backend's. A retry command left an unbound one: bind it, else open one.
        pending = attempts.current(state)
        if pending and pending['kind'] == 'production' and not pending.get('run_id'):
            attempts.bind_run(pending, state['analysis']['run_id'])
        else:
            pending = attempts.open_attempt(state, 'production', run_id=state['analysis']['run_id'], now=store.now())
        attempts.bind_plan(pending, plan)  # the confirmed plan is this attempt's own
        store.write(project_id, state)
        try:
            executor.submit(_produce_selected, project_id, plan, _io_receipt=('analysis', state['analysis']['run_id'], 'production'))
        except Exception as error:
            store.remember_submission_rejection(project_id, ('analysis', state['analysis']['run_id'], 'production'), error_code=studio_error_code(error))
            logger.warning('Studio production dispatch failed: %s', type(error).__name__)
            capture_studio_exception(error, 'dispatch')
            # No worker accepted this confirmation. Preserve the exact plan and
            # staging state so an explicit retry can use the same plan ID.
            store.write(project_id, previous, restore=True)  # rollback is not a transition
            raise UserFacingError('制作任务未能启动，请重试确认；原素材与已有成片已保留') from None

        return state['analysis']['run_id']


def _add_confirmed_drafts(data, drafts):
    rows = [{**d, 'updated_at': store.now()} for d in drafts]
    attempts.own_drafts(data, rows)  # owned by this confirmation's attempt
    data['drafts'].extend(rows)


@_tracked('production')
def _produce_selected(project_id, plan):
    from backend.core.job_budget import bind_clip_job, unbind_clip_job
    from backend.services.studio import intelligence
    started = monotonic()
    budget = bind_clip_job()
    succeeded_goals, failed_goals, reported = [], [], []
    result_count = 0
    labels = {'content':'内容切片','highlight':'精彩高光','promo':'推广成片'}
    errors = []
    error_codes = []
    goal_errors = []
    contexts = []  # 1.5.7: failure_stage / http_status / upstream_error_type per failed goal (no text)
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
                        store.change(project_id, lambda data, drafts=drafts: _add_confirmed_drafts(data, drafts))
                    if goal == 'promo':
                        from backend.services.studio.subtitle_promo import make_promos
                        drafts = make_promos(project_id, subtitle_clips, prefs, intelligence._probe(video).get('duration'), instruction)
                        store.change(project_id, lambda data, drafts=drafts: _add_confirmed_drafts(data, drafts))
                    mark_project(project_id, 'processing')
                    result_count += len(subtitle_clips) if goal == 'content' else len(drafts)
                    succeeded_goals.append(goal)
                    continue
                if plan.get('confirmed_analysis', 'subtitle') != 'visual':
                    raise UserFacingError('此确认未授权视觉分析；请重新选择处理方式')
                if not intelligence.ready():
                    raise UserFacingError('请先在设置中配置视觉理解模型')
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
                store.change(project_id, lambda data, drafts=drafts: _add_confirmed_drafts(data, drafts))
                result_count += len(drafts)
                succeeded_goals.append(goal)
            except Exception as error:
                store.raise_owned_read_error(error)
                failed_goals.append(goal)
                error_codes.append(studio_error_code(error))
                goal_errors.append(error)
                contexts.append(studio_failure_context(error, 'production'))
                if all(error is not previous_error for previous_error in reported):
                    capture_studio_exception(error, 'production', analysis_mode=plan.get('confirmed_analysis', 'subtitle'), goal=goal)
                    reported.append(error)
                errors.append(labels[goal] + '：' + user_visible_error(error)[:500])
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
        held = None
        if errors:
            result['error'] = '；'.join(errors)
            # the primary cause is the first product failure, else the first user one; the rest go along.
            # The snapshot written below is that same cause. A secondary goal's request record must not
            # replace the primary's stage or upstream (and a later success still cannot, #397).
            from backend.core.failure_attribution import rank_failures
            ranked = rank_failures([
                {'error_code': code, **context, '_error': goal_error}
                for code, context, goal_error in zip(error_codes, contexts, goal_errors)
            ])
            primary, *others = ranked
            held = primary.pop('_error', None)
            for other in others:
                other.pop('_error', None)
            result.update(primary)
            if others:
                result['secondary_error_codes'] = [f['error_code'] for f in others]
                result['secondary_upstream_error_types'] = [f.get('upstream_error_type') or '' for f in others]
                # page only (not an event field) - which settings row fixes a secondary user cause.
                result['secondary_failure_stages'] = [f.get('failure_stage') or '' for f in others]
        from backend.core.llm_emit import failure_in_hand
        with failure_in_hand(held):
            store.change(project_id, lambda data: store.settle_attempt(data, kind='production', analysis=result))
        mark_project(project_id, 'failed' if errors else 'completed', studio_draft_count=len(store.read(project_id)['drafts']))
    except Exception as error:
        unbind_clip_job(budget)
        budget = None
        store.raise_owned_read_error(error)
        capture_studio_exception(error, 'production', analysis_mode=plan.get('confirmed_analysis', 'subtitle'))
        failure = {'status':'failed','error':user_visible_error(error), 'error_code':studio_error_code(error),
            'outcome':'partial' if succeeded_goals else 'failed', 'requested_goals':plan['selected_goals'],
            'succeeded_goals':succeeded_goals, 'failed_goals':[g for g in plan['selected_goals'] if g not in succeeded_goals],
            'result_count':result_count, 'duration_ms':round((monotonic() - started) * 1000),
            **studio_failure_context(error, 'production')}
        try:
            store.change(project_id, lambda data: store.settle_attempt(data, kind='production', analysis=failure))
            mark_project(project_id,'failed')
        except FileNotFoundError:
            pass
    finally:
        unbind_clip_job(budget)
