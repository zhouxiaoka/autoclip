"""Expose a completed immutable Studio export to the shared publishing workflow."""
from backend.core.failure_codes import UserFacingError
import re
import math
from backend.pipeline.quality import to_srt_time
from backend.services.studio import store

PREFIX = 'studio-'

def export_post(job):
    return job.get('post') or {'title': job['title'], 'description': (job.get('snapshot') or {}).get('hook') or '', 'tags': []}


def export_cover_file(project_id, job):
    result = job.get('result') or {}
    slot = 'douyin' if (result.get('height') or 0) > (result.get('width') or 0) else 'bilibili'
    from backend.services.cover_brief import stored_path
    root = store.directory(project_id) / 'output' / 'covers' / (PREFIX + job['job_id'])
    return stored_path(root / (slot + '.json'), root / (slot + '.jpg'))


def public_job(project_id, job):
    public = {k: v for k, v in job.items() if k not in ('instance', 'snapshot')}
    if job.get('status') == 'completed' and re.fullmatch(r'[a-f0-9]{32}', job['job_id']):
        public['post'] = export_post(job)
        try:
            public['cover_revision'] = str(export_cover_file(project_id, job).stat().st_mtime_ns)
        except FileNotFoundError:
            pass
    return public


def completed_job(state, job_id):
    if not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise FileNotFoundError('无效的成片引用')
    job = next((j for j in state['jobs'] if j['job_id'] == job_id), None)
    if not job or job.get('status') != 'completed':
        raise FileNotFoundError('成片尚未完成或不存在，请先导出')
    return job


def save_export_post(project_id, job_id, post):
    def save(state):
        job = completed_job(state, job_id)
        if not post.title.strip():
            raise ValueError('标题不能为空')
        job['post'] = post.model_dump()
        return job['post']
    return store.change(project_id, save)


def output_variant_meta(project_id: str, variant_id: str):
    """Resolve a completed automatic output variant without re-exporting it."""
    data = store.read(project_id)
    variant = next((item for item in data.get('output_variants', []) if item.get('id') == variant_id), None)
    if not variant or variant.get('status') != 'completed' or not variant.get('render_job_id'):
        raise FileNotFoundError('成片版本尚未完成或不存在')
    meta = export_meta(project_id, PREFIX + variant['render_job_id'])
    return {**meta, 'output_variant_id': variant_id, 'strategy_id': variant['strategy_id'], 'branding': variant.get('branding', {}),
            'post': variant.get('post') or {}}


def cover_source_frame(project_id, job_id, revision, trace=None, *, context=None, exclude_time=None):
    """Select an original frame inside an exported scene, before captions, padding and overlays."""
    from backend.services.publish_export import find_source_video
    from backend.services.studio import cover_design as cd

    job = completed_job(store.read(project_id), job_id)
    draft = job.get("snapshot") or {}
    scenes = draft.get("scenes") or []
    if not scenes:
        raise FileNotFoundError("成片没有来源片段")
    video = find_source_video(project_id)
    from backend.services.studio.publish_kit import cover_scene

    scene, rows = cover_scene(project_id, scenes, (context or {}).get("title", ""), revision)
    if trace is not None:
        trace.update(asset_id="raw/input", evidence=rows)
    frame, centre, _ = cd.pick_frame(video, scene, rows, draft.get("packaging") or {},
                                      local_revision=revision, trace=trace, context=context, exclude_time=exclude_time)
    return frame, centre if centre is not None else scene.get('crop_x')


def export_meta(project_id: str, source_id: str):
    job_id = source_id.removeprefix(PREFIX)
    if not source_id.startswith(PREFIX):
        raise FileNotFoundError('无效的成片引用')
    job = completed_job(store.read(project_id), job_id)
    path = store.directory(project_id) / 'output' / 'studio' / f'{job_id}.mp4'
    if not path.is_file() or not path.stat().st_size:
        raise FileNotFoundError('成片文件已移除，请重新导出')
    from backend.services.publish_export import _probe
    info = _probe(path)
    duration = float(info.get('duration') or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise UserFacingError('无法读取成片时长')
    return {'id': source_id, 'title': job['title'], 'generated_title': job['title'],
            'start_time': to_srt_time(0), 'end_time': to_srt_time(duration), 'duration_sec': duration, 'source_type': 'studio',
            'studio_job_id': job_id, 'draft_id': job['draft_id'], 'revision': job['revision'],
            'video_path': str(path), 'width': info.get('width'), 'height': info.get('height'),
            'warnings': (job.get('result') or {}).get('warnings') or []}
