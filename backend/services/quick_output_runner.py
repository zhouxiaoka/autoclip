"""CLI and MCP access to the same Studio production pipeline as the desktop application."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse

from backend import __version__


def start(source: str, platforms: list[str], *, name: str | None = None, srt_path: str | None = None,
          instruction: str = '', browser: str | None = None, portrait_style: str = 'auto') -> str:
    from backend.core.database import SessionLocal, create_tables
    from backend.schemas.project import ProjectCreate
    from backend.services.project_service import ProjectService
    from backend.services.local_runner import RunRequest, prepare_project
    from backend.services.studio import jobs, store
    from backend.services.studio.models import ImportOptions

    options = ImportOptions(auto_start=True, platforms=platforms, instruction=instruction, portrait_style=portrait_style)
    parsed = urlparse(source)
    url = None
    if parsed.scheme in ('http', 'https'):
        host = (parsed.hostname or '').lower()
        if parsed.scheme != 'https' or parsed.username or parsed.password or not any(
                host == domain or host.endswith('.' + domain) for domain in ('youtube.com', 'youtu.be', 'bilibili.com', 'b23.tv')):
            raise ValueError('仅支持 HTTPS 的 B 站或 YouTube 视频链接')
        url = source
    else:
        video = Path(source).expanduser().resolve()
        if not video.is_file():
            raise FileNotFoundError(f'视频不存在: {video}')
        if video.suffix.lower() not in ('.mp4', '.mov', '.mkv', '.webm', '.avi'):
            raise ValueError('不支持的视频格式')
    subtitle = Path(srt_path).expanduser().resolve() if srt_path else None
    if subtitle and (not subtitle.is_file() or not 0 < subtitle.stat().st_size <= 2 * 1024 * 1024):
        raise ValueError('字幕文件不存在、为空或超过 2 MB')
    if browser not in (None, 'chrome', 'edge', 'firefox', 'safari'):
        raise ValueError('不支持的浏览器')
    create_tables()
    with SessionLocal() as db:
        project = ProjectService(db).create_project(ProjectCreate(
            name=name or (video.stem if not url else 'Quick output'), project_type='default', source_url=url,
            settings={'smart_import': options.model_dump(), 'import_staging': True, 'creative_browser': browser}))
        project_id = str(project.id)
        if url:
            raw = store.directory(project_id) / 'raw'
            raw.mkdir(parents=True, exist_ok=True)
            if subtitle:
                import shutil
                shutil.copy2(subtitle, raw / 'input.srt')
        else:
            target = prepare_project(RunRequest(video=video, srt=subtitle, name=project.name,
                                                project_id=project_id, register_db=False))
            project.video_path = str(target)
            db.commit()
    import psutil
    producer = {'pid': os.getpid(), 'created_at': psutil.Process().create_time()}
    jobs.inspect_project(project_id, options, url, browser, producer=producer)
    return project_id


def status(project_id: str, *, export_kits: bool = False) -> dict:
    from backend.services.studio import store, publish_kit
    from backend.services.platform_strategy import platform_strategy
    state = store.read(project_id, recover=False)
    generation = state.get('generation')
    if not generation:
        raise FileNotFoundError('一键出片项目不存在')
    phase = generation['status']
    outcome = phase if phase in ('completed', 'partial', 'failed') else 'running'
    error = generation.get('error')
    producer_stopped = False
    if outcome == 'running' and generation.get('producer'):
        import psutil
        producer = generation['producer']
        try:
            producer_stopped = abs(psutil.Process(producer['pid']).create_time() - producer['created_at']) > .01
        except psutil.NoSuchProcess:
            producer_stopped = True
        except psutil.AccessDenied:
            pass  # An inaccessible process is not proof that it has stopped.
    root = store.directory(project_id)
    jobs = {job['job_id']: job for job in state['jobs']}
    outputs = []
    for variant in state.get('output_variants', []):
        row = {key: variant[key] for key in ('id', 'strategy_id', 'status', 'error', 'post', 'cover', 'cover_job') if key in variant}
        if row.get('cover_job'):
            row['cover_job'] = {key: value for key, value in row['cover_job'].items() if key != 'instance'}
            if producer_stopped and row['cover_job'].get('status') in ('queued', 'running'):
                row['cover_job'].update(status='failed', error='制作进程已退出，请重新生成封面')
        if producer_stopped and row.get('status') in ('queued', 'running', 'preparing'):
            row.update(status='failed', error='制作进程已退出，请重试')
        job = jobs.get(variant.get('render_job_id'), {})
        video = root / 'output' / 'studio' / f"{job.get('job_id')}.mp4"
        if variant['status'] == 'completed' and job.get('status') == 'completed' and video.is_file():
            row['video_path'] = str(video)
            row['result'] = job.get('result')
            cover, _ = publish_kit.cover_file(project_id, job['job_id'], variant['strategy_id'])
            row['cover_path'] = str(cover) if cover else None
            if export_kits:
                post = variant.get('post') or {'title': (job.get('result') or {}).get('title', '')}
                fingerprint = json.dumps([post, video.stat().st_mtime_ns, video.stat().st_size,
                                          cover.stat().st_mtime_ns if cover else None], sort_keys=True, ensure_ascii=False)
                key = hashlib.sha256(fingerprint.encode()).hexdigest()[:16]
                kit = video.parent / 'publish-kits' / f"{variant['id']}-{key}.zip"
                if not kit.exists():
                    kit.parent.mkdir(exist_ok=True)
                    strategy = platform_strategy(variant['strategy_id'])
                    temporary, _ = publish_kit.kit_file(video, cover, post, strategy.label, english=strategy.audience_language == 'en')
                    try:
                        os.replace(temporary, kit)
                    finally:
                        temporary.unlink(missing_ok=True)
                row['kit_path'] = str(kit)
        outputs.append(row)
    if producer_stopped:
        outcome = 'partial' if any(row.get('video_path') for row in outputs) else 'failed'
        phase = 'interrupted'
        error = '制作进程已退出；已完成的视频仍可下载，请保持 CLI / MCP 进程运行至完成后再关闭'
    return {'version': __version__, 'project_id': project_id, 'status': outcome, 'phase': phase,
            'error': error, 'outputs': outputs,
            'analysis': {key: (state.get('analysis') or {}).get(key) for key in ('phase', 'message', 'percent', 'error')},
            'project_dir': str(root)}


def wait(project_id: str, *, timeout: float = 7200, interval: float = 1) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        result = status(project_id)
        covers_pending = any((row.get('cover_job') or {}).get('status') in ('queued', 'running') for row in result['outputs'])
        if result['status'] in ('completed', 'partial', 'failed') and not covers_pending:
            return status(project_id, export_kits=result['status'] != 'failed')
        if time.monotonic() >= deadline:
            return {**result, 'timed_out': True}
        time.sleep(interval)
