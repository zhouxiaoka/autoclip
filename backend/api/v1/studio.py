"""Unified creative workspace. Legacy projects are adapted, never overwritten."""
import uuid
from pathlib import Path
from typing import Optional, Literal
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.models.project import Project
from backend.models.clip import Clip
from backend.schemas.project import ProjectCreate, ProjectType
from backend.services.project_service import ProjectService
from backend.services.studio import store, jobs, intelligence
from backend.services.studio.models import Draft, CreateDraft, DuplicateDraft, ExportDraftRequest, RewriteRequest, Preferences, Language, Scene

router = APIRouter()


def project_or_404(project_id: str, db: Session):
    call(store.directory, project_id)
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(404, '项目不存在')
    return project

def call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except store.ConflictError as error:
        raise HTTPException(409, str(error)) from None
    except FileNotFoundError as error:
        raise HTTPException(404, str(error)) from None
    except ValueError as error:
        raise HTTPException(422, str(error)) from None

def validate_draft(project_id, draft):
    duration = intelligence._probe(jobs.source(project_id)).get('duration', 0)
    intelligence.validate_scenes(draft.scenes, duration)

@router.get('/capabilities')
def capabilities():
    return {'visual_analysis': intelligence.ready(), 'visual_model': intelligence.visual_config()[2], 'languages': ['source', 'zh', 'en', 'ja']}

from backend.services.studio import vision_settings

@router.get('/vision-settings')
def get_vision_settings():
    return vision_settings.public()

@router.put('/vision-settings')
def save_vision_settings(body: vision_settings.VisionSettingsInput):
    return call(vision_settings.save, body)

@router.post('/vision-settings/test')
def test_vision_settings(body: vision_settings.VisionSettingsInput):
    try:
        return vision_settings.test(body)
    except Exception:
        raise HTTPException(502, '视觉连接测试失败，请检查接口地址、密钥和模型是否支持图片输入') from None

@router.post('/import')
async def import_visual(
    goal: Literal['highlight', 'promo'] = Form(...),
    language: Language = Form('source'),
    aspect: Literal['original', 'portrait', 'landscape'] = Form('portrait'),
    duration: int = Form(30, ge=10, le=120),
    name: str = Form('游戏成片', max_length=200),
    url: Optional[str] = Form(None),
    browser: Optional[Literal['chrome', 'edge', 'firefox', 'safari']] = Form(None),
    video: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    if not intelligence.ready():
        raise HTTPException(409, '请先配置视觉模型 API，再使用精彩高光或推广成片')
    if bool(url) == bool(video):
        raise HTTPException(422, '请提供一个视频链接或文件')
    if url:
        parsed = urlparse(url)
        host = (parsed.hostname or '').lower()
        if parsed.scheme != 'https' or parsed.username or parsed.password or not any(host == d or host.endswith('.' + d) for d in ('youtube.com', 'youtu.be', 'bilibili.com', 'b23.tv')):
            raise HTTPException(422, '仅支持 HTTPS 的 B 站或 YouTube 视频链接')
    ext = Path(video.filename or '').suffix.lower() if video else '.mp4'
    if ext not in ('.mp4', '.mov', '.mkv', '.webm', '.avi'):
        raise HTTPException(422, '不支持的视频格式')
    first_chunk = await video.read(1024 * 1024) if video else None
    if video and not first_chunk:
        await video.close()
        raise HTTPException(422, '视频文件为空，请重新选择')
    prefs = Preferences(goal=goal, language=language, aspect=aspect, duration=duration)
    project = ProjectService(db).create_project(ProjectCreate(name=name.strip() or '游戏成片', project_type=ProjectType.ENTERTAINMENT, source_url=url, settings={'creative': prefs.model_dump(), 'creative_browser': browser}))
    pid = str(project.id)
    raw = store.directory(pid) / 'raw'
    raw.mkdir(parents=True, exist_ok=True)
    try:
        if video:
            path = raw / ('input' + ext)
            with path.open('wb') as target:
                target.write(first_chunk)
                while chunk := await video.read(1024 * 1024):
                    target.write(chunk)
            project.video_path = str(path)
            db.commit()
        call(jobs.analyze_project, pid, prefs, url, browser)
    except Exception:
        project.status = 'failed'
        db.commit()
        raise
    finally:
        if video:
            await video.close()
    return {'project_id': pid}

@router.get('/{project_id}')
def workspace(project_id: str, db: Session = Depends(get_db)):
    project_or_404(project_id, db)
    data = call(store.read, project_id)
    return {**data, 'jobs': [{k: v for k, v in j.items() if k not in ('instance', 'snapshot')} for j in data['jobs']]}

@router.get('/{project_id}/source')
def source_video(project_id: str, db: Session = Depends(get_db)):
    project_or_404(project_id, db)
    path = call(jobs.source, project_id)
    return FileResponse(path)

@router.get('/{project_id}/candidates')
def candidates(project_id: str, db: Session = Depends(get_db)):
    """Only offer ranges from this project's actual source video."""
    project_or_404(project_id, db)
    info = call(intelligence._probe, call(jobs.source, project_id))
    duration = info.get('duration', 0)
    rows = []
    skipped = 0
    raw_events = call(store.read, project_id)['events']
    raw_clips = db.query(Clip).filter(Clip.project_id == project_id).order_by(Clip.start_time).all()
    sources = [('visual', e) for e in raw_events]
    sources.extend(('legacy', {'id': str(c.id), 'label': c.title[:120], 'start': c.start_time,
                              'end': c.end_time, 'evidence': (c.recommendation_reason or '')[:1000]}) for c in raw_clips)
    for kind, raw in sources:
        try:
            scene = Scene.model_validate(raw)
            intelligence.validate_scenes([scene], duration)
        except ValueError:
            skipped += 1
            continue
        rows.append({**scene.model_dump(), 'id': f'{kind}-{scene.id}', 'kind': kind})
    return {'duration': duration, 'candidates': rows,
            'warnings': [f'{skipped} 个片段时间无效，已从候选中排除'] if skipped else []}

@router.post('/{project_id}/analyze')
def analyze_again(project_id: str, db: Session = Depends(get_db)):
    project = project_or_404(project_id, db)
    prefs = Preferences.model_validate((project.processing_config or {}).get('creative', {}))
    if prefs.goal == 'content':
        raise HTTPException(422, '内容项目请继续使用原有切片流程')
    if not intelligence.ready():
        raise HTTPException(409, '视觉模型尚未配置')
    url = None
    try:
        jobs.source(project_id)
    except FileNotFoundError:
        url = (project.project_metadata or {}).get('source_url')
        if not url:
            raise HTTPException(404, '原素材不存在，请重新导入')
    call(jobs.analyze_project, project_id, prefs, url, (project.processing_config or {}).get('creative_browser'))
    return {'ok': True}

@router.post('/{project_id}/drafts')
def create_draft(project_id: str, body: CreateDraft, db: Session = Depends(get_db)):
    project_or_404(project_id, db)
    clips = db.query(Clip).filter(Clip.project_id == project_id, Clip.id.in_(body.clip_ids)).all()
    by_id = {str(c.id): c for c in clips}
    if any(cid not in by_id for cid in body.clip_ids):
        raise HTTPException(404, '所选片段不属于当前项目')
    scenes = [Scene(id=uuid.uuid4().hex, label=by_id[cid].title, start=by_id[cid].start_time, end=by_id[cid].end_time) for cid in body.clip_ids]
    draft = Draft(id=uuid.uuid4().hex, title=body.title, scenes=scenes, origin='legacy')
    call(validate_draft, project_id, draft)
    store.directory(project_id).mkdir(parents=True, exist_ok=True)
    return call(store.save_draft, project_id, draft, create=True)

@router.post('/{project_id}/events/{event_id}/draft')
def event_draft(project_id: str, event_id: str, db: Session = Depends(get_db)):
    project = project_or_404(project_id, db)
    prefs = Preferences.model_validate((project.processing_config or {}).get('creative', {}))
    event = next((e for e in store.read(project_id)['events'] if e['id'] == event_id), None)
    if not event:
        raise HTTPException(404, '片段不存在')
    draft = Draft(id=uuid.uuid4().hex, title=event['label'], scenes=[Scene.model_validate(event)], aspect=prefs.aspect, language=prefs.language, subtitles=False, origin='visual-highlight')
    call(validate_draft, project_id, draft)
    return call(store.save_draft, project_id, draft, create=True)

@router.put('/{project_id}/drafts/{draft_id}')
def save(project_id: str, draft_id: str, body: Draft, db: Session = Depends(get_db)):
    project_or_404(project_id, db)
    if draft_id != body.id:
        raise HTTPException(422, '草稿 ID 不匹配')
    call(validate_draft, project_id, body)
    return call(store.save_draft, project_id, body)

@router.post('/{project_id}/drafts/{draft_id}/duplicate')
def duplicate(project_id: str, draft_id: str, body: DuplicateDraft, db: Session = Depends(get_db)):
    project = project_or_404(project_id, db)
    if draft_id != body.draft.id:
        raise HTTPException(422, '来源草稿 ID 不匹配')
    call(validate_draft, project_id, body.draft)
    result = call(store.duplicate_draft, project_id, body)
    project.processing_config = {**(project.processing_config or {}), 'studio_draft_count': len(store.read(project_id)['drafts'])}
    db.commit()
    return result

@router.post('/{project_id}/rewrite')
def rewrite(project_id: str, body: RewriteRequest, db: Session = Depends(get_db)):
    project_or_404(project_id, db)
    if not any(d['id'] == body.draft.id for d in store.read(project_id)['drafts']):
        raise HTTPException(404, '草稿不存在')
    try:
        result = intelligence.text_json('你是剪辑文案编辑。按用户要求优化 title 和 hook，保持事实；依据仅限原文与镜头证据。不能声称已修改镜头、声音或视频，也不能承诺投放效果。返回 {"title":"...","hook":"..."}。', {'instruction': body.instruction, 'language': body.draft.language, 'title': body.draft.title, 'hook': body.draft.hook, 'scenes': [s.model_dump() for s in body.draft.scenes]})
        candidate = Draft.model_validate({**body.draft.model_dump(), 'title': result['title'], 'hook': result['hook']})
    except Exception:
        raise HTTPException(502, '生成文案失败，请检查模型设置后重试；原稿未改动') from None
    return candidate

@router.post('/{project_id}/drafts/{draft_id}/export')
def export(project_id: str, draft_id: str, body: ExportDraftRequest | None = None, db: Session = Depends(get_db)):
    project_or_404(project_id, db)
    raw = next((d for d in store.read(project_id)['drafts'] if d['id'] == draft_id), None)
    if not raw:
        raise HTTPException(404, '草稿不存在')
    if body and body.revision != raw['revision']:
        raise HTTPException(409, '草稿已在另一窗口更新，请重新加载后再导出')
    draft = Draft.model_validate(raw)
    call(validate_draft, project_id, draft)
    return call(jobs.export, project_id, draft)

@router.get('/{project_id}/exports/{job_id}/video')
def rendered_video(project_id: str, job_id: str, download: bool = False, db: Session = Depends(get_db)):
    project_or_404(project_id, db)
    job = next((j for j in store.read(project_id)['jobs'] if j['job_id'] == job_id), None)
    if not job:
        raise HTTPException(404, '导出不存在')
    if job['status'] != 'completed':
        raise HTTPException(409, '导出尚未完成')
    path = store.directory(project_id) / 'output' / 'studio' / f'{job_id}.mp4'
    if not path.is_file():
        raise HTTPException(404, '导出文件已移除')
    return FileResponse(path, media_type='video/mp4', filename=path.name if download else None)
