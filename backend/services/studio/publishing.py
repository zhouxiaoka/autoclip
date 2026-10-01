"""Expose a completed immutable Studio export to the shared publishing workflow."""
import re
import math
from backend.pipeline.quality import to_srt_time
from backend.services.studio import store

PREFIX = 'studio-'

def output_variant_meta(project_id: str, variant_id: str):
    """Resolve a completed automatic output variant without re-exporting it."""
    data = store.read(project_id)
    variant = next((item for item in data.get('output_variants', []) if item.get('id') == variant_id), None)
    if not variant or variant.get('status') != 'completed' or not variant.get('render_job_id'):
        raise FileNotFoundError('成片版本尚未完成或不存在')
    meta = export_meta(project_id, PREFIX + variant['render_job_id'])
    return {**meta, 'output_variant_id': variant_id, 'strategy_id': variant['strategy_id'], 'branding': variant.get('branding', {}),
            'post': variant.get('post') or {}}


def export_meta(project_id: str, source_id: str):
    job_id = source_id.removeprefix(PREFIX)
    if not source_id.startswith(PREFIX) or not re.fullmatch(r'[a-f0-9]{32}', job_id):
        raise FileNotFoundError('无效的成片引用')
    job = next((j for j in store.read(project_id)['jobs'] if j['job_id'] == job_id), None)
    if not job or job.get('status') != 'completed':
        raise FileNotFoundError('成片尚未完成或不存在，请先导出')
    path = store.directory(project_id) / 'output' / 'studio' / f'{job_id}.mp4'
    if not path.is_file() or not path.stat().st_size:
        raise FileNotFoundError('成片文件已移除，请重新导出')
    from backend.services.publish_export import _probe
    info = _probe(path)
    duration = float(info.get('duration') or 0)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('无法读取成片时长')
    return {'id': source_id, 'title': job['title'], 'generated_title': job['title'],
            'start_time': to_srt_time(0), 'end_time': to_srt_time(duration), 'duration_sec': duration, 'source_type': 'studio',
            'studio_job_id': job_id, 'draft_id': job['draft_id'], 'revision': job['revision'],
            'video_path': str(path), 'width': info.get('width'), 'height': info.get('height'),
            'warnings': (job.get('result') or {}).get('warnings') or []}
