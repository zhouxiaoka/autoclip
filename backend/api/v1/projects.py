"""
项目API路由
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.services.project_service import ProjectService
from backend.services.processing_service import ProcessingService
from backend.services.websocket_notification_service import WebSocketNotificationService
from backend.tasks.processing import process_video_pipeline
from backend.core.websocket_manager import manager as websocket_manager
from backend.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse, ProjectFilter,
    ProjectType, ProjectStatus
)
from backend.schemas.base import PaginationParams
from pathlib import Path

logger = logging.getLogger(__name__)
router = APIRouter()


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    """Dependency to get project service."""
    return ProjectService(db)


def get_processing_service(db: Session = Depends(get_db)) -> ProcessingService:
    """Dependency to get processing service."""
    return ProcessingService(db)


def get_websocket_service():
    """Dependency to get websocket notification service."""
    return WebSocketNotificationService


@router.post("/upload", response_model=ProjectResponse)
async def upload_files(
    video_file: UploadFile = File(...),
    srt_file: Optional[UploadFile] = File(None),
    project_name: str = Form(...),
    video_category: Optional[str] = Form(None),
    project_service: ProjectService = Depends(get_project_service)
):
    """Upload video file and optional subtitle file to create a new project. If no subtitle is provided, Whisper will automatically generate one."""
    try:
        # 验证视频文件类型
        if not video_file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            raise HTTPException(status_code=400, detail="Invalid video file format")
        
        # 验证字幕文件类型（如果提供）
        if srt_file and not srt_file.filename.lower().endswith('.srt'):
            raise HTTPException(status_code=400, detail="Invalid subtitle file format")
        
        # 创建项目数据
        subtitle_info = srt_file.filename if srt_file else "Whisper自动生成"
        project_data = ProjectCreate(
            name=project_name,
            description=f"Video: {video_file.filename}, Subtitle: {subtitle_info}",
            project_type=ProjectType.KNOWLEDGE,  # 默认类型
            status=ProjectStatus.PENDING,
            source_url=None,
            source_file=video_file.filename,
            settings={
                "video_category": video_category or "knowledge",
                "video_file": video_file.filename,
                "srt_file": subtitle_info
            }
        )
        
        # 创建项目
        project = project_service.create_project(project_data)
        
        # 保存文件到项目目录
        project_id = str(project.id)
        from ...core.path_utils import get_project_raw_directory
        raw_dir = get_project_raw_directory(project_id)
        
        # 保存视频文件
        video_path = raw_dir / "input.mp4"
        with open(video_path, "wb") as f:
            content = await video_file.read()
            f.write(content)
        
        # 更新项目的视频路径
        project.video_path = str(video_path)
        project_service.db.commit()
        
        # 立即生成缩略图（同步处理）
        try:
            from ...utils.thumbnail_generator import generate_project_thumbnail
            logger.info(f"开始为项目 {project_id} 生成缩略图...")
            thumbnail_data = generate_project_thumbnail(project_id, video_path)
            if thumbnail_data:
                project.thumbnail = thumbnail_data
                project_service.db.commit()
                logger.info(f"项目 {project_id} 缩略图生成并保存成功")
            else:
                logger.warning(f"项目 {project_id} 缩略图生成失败")
        except Exception as e:
            logger.error(f"生成项目缩略图时发生错误: {e}")
            # 缩略图生成失败不影响主流程，会在异步任务中重试
        
        # 处理字幕文件（如果用户提供了）
        srt_path = None
        if srt_file:
            # 用户提供了字幕文件
            srt_path = raw_dir / "input.srt"
            with open(srt_path, "wb") as f:
                content = await srt_file.read()
                f.write(content)
            logger.info(f"用户提供的字幕文件已保存: {srt_path}")
        
        # 启动异步处理任务
        try:
            from ...tasks.import_processing import process_import_task
            
            # 提交异步任务
            celery_task = process_import_task.delay(
                project_id=project_id,
                video_path=str(video_path),
                srt_file_path=str(srt_path) if srt_path else None
            )
            
            logger.info(f"项目 {project_id} 异步处理任务已启动，Celery任务ID: {celery_task.id}")
            
        except Exception as e:
            logger.error(f"启动项目 {project_id} 异步处理失败: {str(e)}")
            # 即使异步任务启动失败，也要返回项目创建成功
            # 用户可以通过重试按钮重新启动处理
        
        # 返回项目响应
        response_data = {
            "id": str(project.id),
            "name": str(project.name),
            "description": str(project.description) if project.description else None,
            "project_type": ProjectType(project.project_type.value),
            "status": ProjectStatus(project.status.value),
            "source_url": project.project_metadata.get("source_url") if project.project_metadata else None,
            "source_file": str(project.video_path) if project.video_path else None,
            "video_path": str(video_path),  # 添加video_path字段
            "settings": {
                "video_category": video_category or "knowledge",
                "video_file": video_file.filename,
                "srt_file": subtitle_info
            },  # 只包含可序列化的数据
            "created_at": project.created_at,
            "updated_at": project.updated_at,
            "completed_at": project.completed_at,
            "total_clips": 0,
            "total_collections": 0,
            "total_tasks": 0
        }
        
        # 缩略图将在异步任务中生成
        response_data["thumbnail"] = None
        
        return ProjectResponse(**response_data)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/", response_model=ProjectResponse)
async def create_project(
    project_data: ProjectCreate,
    project_service: ProjectService = Depends(get_project_service)
):
    """Create a new project."""
    try:
        project = project_service.create_project(project_data)
        # Convert to response (simplified for now)
        return ProjectResponse(
            id=str(project.id),  # Use actual project ID
            name=str(project.name),
            description=str(project.description) if project.description else None,
            project_type=ProjectType(project.project_type.value),
            status=ProjectStatus(project.status.value),
            source_url=project.project_metadata.get("source_url") if project.project_metadata else None,
            source_file=str(project.video_path) if project.video_path else None,
            settings=project.processing_config or {},
            created_at=project.created_at,
            updated_at=project.updated_at,
            completed_at=project.completed_at,
            total_clips=0,
            total_collections=0,
            total_tasks=0
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=ProjectListResponse)
async def get_projects(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    status: Optional[str] = Query(None, description="Filter by status"),
    project_type: Optional[str] = Query(None, description="Filter by project type"),
    search: Optional[str] = Query(None, description="Search in name and description"),
    project_service: ProjectService = Depends(get_project_service)
):
    """Get paginated projects with optional filtering."""
    try:
        pagination = PaginationParams(page=page, size=size)
        
        filters = None
        if status or project_type or search:
            filters = ProjectFilter(
                status=status,
                project_type=project_type,
                search=search
            )
        
        return project_service.get_projects_paginated(pagination, filters)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    include_clips: bool = Query(False, description="是否包含切片数据"),
    include_collections: bool = Query(False, description="是否包含合集数据"),
    project_service: ProjectService = Depends(get_project_service)
):
    """Get a project by ID."""
    try:
        project = project_service.get_project_with_stats(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 如果需要包含clips和collections数据，则加载它们
        clips_data = None
        collections_data = None
        
        if include_clips or include_collections:
            from ...services.clip_service import ClipService
            from ...services.collection_service import CollectionService
            from ...core.database import get_db
            
            # 获取数据库会话
            db = next(get_db())
            
            if include_clips:
                clip_service = ClipService(db)
                clips = clip_service.get_multi(filters={"project_id": project_id})
                # 转换为字典格式
                clips_data = [clip.to_dict() if hasattr(clip, 'to_dict') else clip.__dict__ for clip in clips]
            
            if include_collections:
                collection_service = CollectionService(db)
                collections = collection_service.get_multi(filters={"project_id": project_id})
                # 转换为字典格式
                collections_data = [collection.to_dict() if hasattr(collection, 'to_dict') else collection.__dict__ for collection in collections]
        
        # 创建包含clips和collections的响应数据
        response_data = project.model_dump() if hasattr(project, 'model_dump') else project.__dict__
        if clips_data is not None:
            response_data['clips'] = clips_data
        if collections_data is not None:
            response_data['collections'] = collections_data
        
        # 返回更新后的响应
        return ProjectResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_data: ProjectUpdate,
    project_service: ProjectService = Depends(get_project_service)
):
    """Update a project."""
    try:
        project = project_service.update_project(project_id, project_data)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Convert to response (simplified)
        return ProjectResponse(
            id=str(project_id),  # Keep as string for UUID
            name=project_data.name or "Updated Project",
            description=project_data.description,
            project_type=ProjectType.DEFAULT,  # Use enum
            status=ProjectStatus.PENDING,  # Use enum
            source_url=None,
            source_file=None,
            settings=project_data.settings or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            completed_at=None,
            total_clips=0,
            total_collections=0,
            total_tasks=0
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Delete a project and all its related files."""
    try:
        success = project_service.delete_project_with_files(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"message": "Project and all related files deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sync-all-data")
async def sync_all_projects_data(
    db: Session = Depends(get_db)
):
    """同步所有项目的数据到数据库"""
    try:
        from ...services.data_sync_service import DataSyncService
        from ...core.config import get_data_directory
        
        data_dir = get_data_directory()
        sync_service = DataSyncService(db)
        
        result = sync_service.sync_all_projects_from_filesystem(data_dir)
        
        return {
            "message": "数据同步完成",
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据同步失败: {str(e)}")


@router.post("/{project_id}/sync-data")
async def sync_project_data(
    project_id: str,
    db: Session = Depends(get_db)
):
    """同步指定项目的数据到数据库"""
    try:
        from ...services.data_sync_service import DataSyncService
        from ...core.path_utils import get_project_directory
        
        project_dir = get_project_directory(project_id)
        if not project_dir.exists():
            raise HTTPException(status_code=404, detail="项目目录不存在")
        
        sync_service = DataSyncService(db)
        result = sync_service.sync_project_from_filesystem(project_id, project_dir)
        
        if result.get("success"):
            return {
                "message": "项目数据同步成功",
                "result": result
            }
        else:
            raise HTTPException(status_code=500, detail=f"数据同步失败: {result.get('error')}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据同步失败: {str(e)}")


@router.post("/{project_id}/process")
async def start_processing(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
    processing_service: ProcessingService = Depends(get_processing_service),
    websocket_service: WebSocketNotificationService = Depends(get_websocket_service)
):
    """Start processing a project using Celery task queue."""
    try:
        # 获取项目信息
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 检查项目状态
        if project.status.value not in ["pending", "failed"]:
            raise HTTPException(status_code=400, detail="Project is not in pending or failed status")
        
        # 获取视频和SRT文件路径
        video_path = project.video_path
        srt_path = None
        
        # 从processing_config中获取SRT文件路径
        if project.processing_config and "subtitle_path" in project.processing_config:
            srt_path = project.processing_config["subtitle_path"]
        
        # 验证视频文件存在
        if not video_path or not Path(video_path).exists():
            raise HTTPException(status_code=400, detail=f"Video file not found: {video_path}")
        
        # 如果没有SRT文件路径，尝试自动查找
        if not srt_path:
            video_dir = Path(video_path).parent
            srt_file = video_dir / "input.srt"
            if srt_file.exists():
                srt_path = str(srt_file)
            else:
                # SRT文件是可选的，如果没有找到，设置为None
                srt_path = None
        elif not Path(srt_path).exists():
            # 如果指定的SRT文件不存在，尝试自动查找
            video_dir = Path(video_path).parent
            srt_file = video_dir / "input.srt"
            if srt_file.exists():
                srt_path = str(srt_file)
            else:
                srt_path = None
        
        # 更新项目状态为处理中
        project_service.update_project_status(project_id, "processing")
        
        # 发送WebSocket通知：处理开始
        await websocket_service.send_processing_started(
            project_id=project_id,
            message="开始视频处理流程"
        )
        
        # 提交Celery任务
        celery_task = process_video_pipeline.delay(
            project_id=project_id,
            input_video_path=str(video_path),
            input_srt_path=str(srt_path) if srt_path else None
        )
        
        # 创建处理任务记录
        task_result = processing_service._create_processing_task(
            project_id=project_id,
            task_type="VIDEO_PROCESSING"
        )
        
        return {
            "message": "Processing started successfully",
            "project_id": project_id,
            "task_id": task_result.id,
            "celery_task_id": celery_task.id,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # 发送错误通知
        try:
            await websocket_service.send_processing_error(
                project_id=int(project_id),
                error=str(e),
                step="initialization"
            )
        except:
            pass
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/retry")
async def retry_processing(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
    processing_service: ProcessingService = Depends(get_processing_service),
    websocket_service: WebSocketNotificationService = Depends(get_websocket_service)
):
    """Retry processing a project from the beginning."""
    try:
        # 获取项目信息
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 检查项目状态 - 允许失败、完成、处理中和等待中状态重试
        if project.status.value not in ["failed", "completed", "processing", "pending"]:
            raise HTTPException(status_code=400, detail="Project is not in failed, completed, processing, or pending status")
        
        # 重置项目状态
        project_service.update_project_status(project_id, "pending")
        
        # 发送WebSocket通知 - 已禁用WebSocket通知
        # await websocket_service.send_processing_started(
        #     project_id=int(project_id),
        #     message="重新开始处理流程"
        # )
        
        # 获取文件路径并重新提交任务
        from ...core.path_utils import get_project_raw_directory
        raw_dir = get_project_raw_directory(project_id)
        video_path = raw_dir / "input.mp4"  # 使用标准的input.mp4文件名
        srt_path = raw_dir / "input.srt"    # 使用标准的input.srt文件名
        
        # 检查视频文件是否存在，如果不存在则尝试重新下载
        if not video_path.exists():
            logger.warning(f"视频文件不存在: {video_path}，尝试重新下载")
            
            # 检查项目元数据中是否有源URL
            if hasattr(project, 'project_metadata') and project.project_metadata:
                source_url = project.project_metadata.get('source_url')
                if source_url:
                    logger.info(f"发现源URL: {source_url}，开始重新下载")
                    
                    # 根据URL类型选择下载方式
                    if 'bilibili.com' in source_url:
                        # B站视频重新下载
                        from .bilibili import process_download_task, BilibiliDownloadRequest, BilibiliDownloadTask, download_tasks
                        import uuid
                        
                        # 创建下载请求
                        download_request = BilibiliDownloadRequest(
                            url=source_url,
                            project_name=project.name,
                            video_category=project.project_metadata.get('category', 'general')
                        )
                        
                        # 生成新的任务ID
                        download_task_id = str(uuid.uuid4())
                        
                        # 创建任务记录
                        task = BilibiliDownloadTask(
                            id=download_task_id,
                            url=source_url,
                            project_name=project.name,
                            video_category=project.project_metadata.get('category', 'general'),
                            status="pending",
                            progress=0.0,
                            project_id=project_id,
                            created_at=str(uuid.uuid1().time),
                            updated_at=str(uuid.uuid1().time)
                        )
                        
                        # 存储任务
                        download_tasks[download_task_id] = task
                        
                        # 异步启动下载任务
                        from .async_task_manager import task_manager
                        await task_manager.create_safe_task(
                            f"bilibili_redownload_{download_task_id}",
                            process_download_task,
                            download_task_id,
                            download_request,
                            project_id
                        )
                        
                        return {
                            "message": "视频文件不存在，已开始重新下载B站视频",
                            "project_id": project_id,
                            "download_task_id": download_task_id,
                            "source_url": source_url
                        }
                    elif 'youtube.com' in source_url or 'youtu.be' in source_url:
                        # YouTube视频重新下载
                        from .youtube import process_youtube_download_task, YouTubeDownloadRequest
                        import uuid
                        
                        # 创建下载请求
                        download_request = YouTubeDownloadRequest(
                            url=source_url,
                            project_name=project.name,
                            video_category=project.project_metadata.get('category', 'general')
                        )
                        
                        # 生成新的任务ID
                        download_task_id = str(uuid.uuid4())
                        
                        # 异步启动下载任务
                        from .async_task_manager import task_manager
                        await task_manager.create_safe_task(
                            f"youtube_redownload_{download_task_id}",
                            process_youtube_download_task,
                            download_task_id,
                            download_request,
                            project_id
                        )
                        
                        return {
                            "message": "视频文件不存在，已开始重新下载YouTube视频",
                            "project_id": project_id,
                            "download_task_id": download_task_id,
                            "source_url": source_url
                        }
                    else:
                        raise HTTPException(status_code=400, detail=f"不支持的视频源: {source_url}")
                else:
                    raise HTTPException(status_code=400, detail=f"视频文件不存在且没有源URL: {video_path}")
            else:
                raise HTTPException(status_code=400, detail=f"视频文件不存在且没有项目元数据: {video_path}")
        
        # 字幕文件是可选的
        srt_path_str = str(srt_path) if srt_path.exists() else None
        
        # 提交Celery任务 - 使用字符串类型的project_id
        celery_task = process_video_pipeline.delay(
            project_id=project_id,
            input_video_path=str(video_path),
            input_srt_path=srt_path_str
        )
        
        # 创建新的处理任务记录
        from ...models.task import TaskType
        task_result = processing_service._create_processing_task(
            project_id=project_id,
            task_type=TaskType.VIDEO_PROCESSING
        )
        
        # 更新任务的Celery任务ID
        task_result.celery_task_id = celery_task.id
        processing_service.db.commit()
        
        return {
            "message": "Processing retry started successfully",
            "project_id": project_id,
            "task_id": task_result.id,
            "celery_task_id": celery_task.id,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # 发送错误通知 - 已禁用WebSocket通知
        # try:
        #     await websocket_service.send_processing_error(
        #         project_id=int(project_id),
        #         error=str(e),
        #         step="retry_initialization"
        #     )
        # except:
        #     pass
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/resume")
async def resume_processing(
    project_id: str,
    start_step: str = Form(..., description="Step to resume from (step1_outline, step2_timeline, etc.)"),
    project_service: ProjectService = Depends(get_project_service),
    processing_service: ProcessingService = Depends(get_processing_service)
):
    """Resume processing from a specific step."""
    try:
        # 获取项目信息
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 检查项目状态
        if project.status.value not in ["failed", "processing", "pending"]:
            raise HTTPException(status_code=400, detail="Project is not in failed, processing, or pending status")
        
        # 获取SRT文件路径（如果需要）
        srt_path = None
        if start_step == "step1_outline":
            if project.processing_config and "srt_file" in project.processing_config:
                from pathlib import Path
                project_root = Path(__file__).parent.parent.parent / "data" / "projects" / project_id
                srt_path = project_root / "raw" / project.processing_config["srt_file"]
            
            if not srt_path or not srt_path.exists():
                raise HTTPException(status_code=400, detail=f"SRT file not found: {srt_path}")
        
        # 调用处理服务恢复执行
        result = processing_service.resume_processing(project_id, start_step, srt_path)
        
        return {
            "message": f"Processing resumed from {start_step} successfully",
            "project_id": project_id,
            "start_step": start_step,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/status")
async def get_processing_status(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
    processing_service: ProcessingService = Depends(get_processing_service)
):
    """Get processing status of a project."""
    try:
        # 获取项目信息
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 获取最新的任务
        tasks = project.tasks if hasattr(project, 'tasks') else []
        latest_task = None
        if tasks:
            latest_task = max(tasks, key=lambda t: t.created_at) if hasattr(tasks[0], 'created_at') else tasks[0]
        
        if not latest_task:
            return {
                "status": "pending",
                "current_step": 0,
                "total_steps": 6,
                "step_name": "等待开始",
                "progress": 0,
                "error_message": None
            }
        
        # 获取处理状态
        status = processing_service.get_processing_status(project_id, str(latest_task.id))
        
        return status
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}/logs")
async def get_project_logs(
    project_id: str,
    lines: int = Query(50, ge=1, le=1000, description="Number of log lines to return"),
    project_service: ProjectService = Depends(get_project_service)
):
    """Get project logs."""
    try:
        # 模拟日志数据，实际应该从日志服务获取
        return {
            "logs": [
                {
                    "timestamp": "2025-08-01T13:30:00.000Z",
                    "module": "processing",
                    "level": "INFO",
                    "message": "开始处理项目"
                },
                {
                    "timestamp": "2025-08-01T13:30:05.000Z",
                    "module": "processing",
                    "level": "INFO",
                    "message": "Step 1: 提取大纲完成"
                },
                {
                    "timestamp": "2025-08-01T13:30:10.000Z",
                    "module": "processing",
                    "level": "INFO",
                    "message": "Step 2: 时间定位完成"
                },
                {
                    "timestamp": "2025-08-01T13:30:15.000Z",
                    "module": "processing",
                    "level": "INFO",
                    "message": "Step 3: 内容评分进行中..."
                }
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 


@router.get("/{project_id}/import-status")
async def get_import_status(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """获取项目导入状态"""
    try:
        # 获取项目信息
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 检查是否有正在进行的导入任务
        from ...core.celery_app import celery_app
        
        # 这里可以添加更复杂的任务状态检查逻辑
        # 目前简单返回项目状态
        return {
            "project_id": project_id,
            "status": project.status.value,
            "message": "导入状态正常"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取导入状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取导入状态失败: {str(e)}")


@router.post("/{project_id}/generate-thumbnail")
async def generate_project_thumbnail(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """为项目生成缩略图"""
    try:
        # 获取项目信息
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 检查是否有视频文件
        if not project.video_path:
            raise HTTPException(status_code=400, detail="Project has no video file")
        
        # 检查视频文件是否存在
        video_path = Path(project.video_path)
        if not video_path.exists():
            raise HTTPException(status_code=400, detail="Video file not found")
        
        # 生成缩略图
        from ...utils.thumbnail_generator import generate_project_thumbnail
        thumbnail_data = generate_project_thumbnail(project_id, video_path)
        
        if thumbnail_data:
            # 保存缩略图到数据库
            project.thumbnail = thumbnail_data
            project_service.db.commit()
            
            return {
                "success": True,
                "thumbnail": thumbnail_data,
                "message": "缩略图生成并保存成功"
            }
        else:
            raise HTTPException(status_code=500, detail="缩略图生成失败")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成项目缩略图失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成缩略图失败: {str(e)}")


@router.get("/{project_id}/files/{filename}")
async def get_project_file(
    project_id: str,
    filename: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Get a project file by filename."""
    try:
        from pathlib import Path
        import json
        from fastapi.responses import FileResponse
        
        # 构建文件路径 - 使用正确的项目目录路径
        from ...core.path_utils import get_project_directory
        project_root = get_project_directory(project_id)
        
        # 尝试多个可能的路径
        possible_paths = [
            project_root / "raw" / filename,  # 原始文件
            project_root / "metadata" / filename,  # 元数据文件
            project_root / filename,  # 直接在项目根目录
        ]
        
        file_path = None
        for path in possible_paths:
            if path.exists():
                file_path = path
                break
        
        if not file_path:
            raise HTTPException(status_code=404, detail="File not found")
        
        # 根据文件类型返回不同响应
        if filename.endswith('.json'):
            # JSON文件返回数据
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        else:
            # 其他文件（如视频）返回文件流
            media_type = "video/mp4" if filename.endswith('.mp4') else "application/octet-stream"
            return FileResponse(
                path=str(file_path),
                filename=filename,
                media_type=media_type,
                headers={
                    "Accept-Ranges": "bytes",  # 支持范围请求，便于视频播放
                    "Cache-Control": "public, max-age=3600"  # 缓存1小时
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 


@router.get("/{project_id}/clips/{clip_id}")
async def get_project_clip(
    project_id: str,
    clip_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Get a specific clip video file for a project."""
    try:
        from pathlib import Path
        import os
        
        # 构建视频文件路径 - 使用正确的项目目录路径
        from ...core.path_utils import get_project_directory
        project_dir = get_project_directory(project_id)
        clips_dir = project_dir / "output" / "clips"
        
        # 确保路径存在
        if not clips_dir.exists():
            raise HTTPException(status_code=404, detail=f"Clips directory not found: {clips_dir}")
        
        # 查找对应的视频文件
        # 首先尝试通过clip_id查找
        video_files = list(clips_dir.glob(f"{clip_id}_*.mp4"))
        
        # 如果没找到，尝试查找所有mp4文件，然后通过数据库匹配
        if not video_files:
            from ...models.clip import Clip
            clip = project_service.db.query(Clip).filter(Clip.id == clip_id).first()
            if clip and clip.video_path:
                video_file_path = Path(clip.video_path)
                if video_file_path.exists():
                    video_file = video_file_path
                else:
                    raise HTTPException(status_code=404, detail=f"Clip video file not found for clip_id: {clip_id}")
            else:
                raise HTTPException(status_code=404, detail=f"Clip not found in database: {clip_id}")
        else:
            video_file = video_files[0]
        
        # 检查文件是否存在
        if not video_file.exists():
            raise HTTPException(status_code=404, detail="Clip video file not found")
        
        # 返回文件流
        from fastapi.responses import FileResponse
        return FileResponse(
            path=str(video_file),
            media_type="video/mp4",
            filename=video_file.name
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sync-all")
async def sync_all_projects_from_filesystem(
    db: Session = Depends(get_db)
):
    """从文件系统同步所有项目数据到数据库"""
    try:
        from backend.services.data_sync_service import DataSyncService
        from backend.core.config import get_data_directory
        
        # 获取数据目录
        data_dir = get_data_directory()
        
        # 创建数据同步服务
        sync_service = DataSyncService(db)
        
        # 同步所有项目
        result = sync_service.sync_all_projects_from_filesystem(data_dir)
        
        return {
            "success": result.get("success", False),
            "message": "数据同步完成",
            "synced_projects": result.get("synced_projects", []),
            "failed_projects": result.get("failed_projects", []),
            "total_synced": len(result.get("synced_projects", [])),
            "total_failed": len(result.get("failed_projects", []))
        }
        
    except Exception as e:
        logger.error(f"同步所有项目数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.patch("/{project_id}/collections/{collection_id}/reorder")
async def reorder_collection_clips(
    project_id: str,
    collection_id: str,
    clip_ids: List[str],
    db: Session = Depends(get_db)
):
    """重新排序合集中的切片"""
    try:
        from backend.services.collection_service import CollectionService
        
        # 创建合集服务
        collection_service = CollectionService(db)
        
        # 获取合集
        collection = collection_service.get(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        # 验证合集属于指定项目
        if str(collection.project_id) != project_id:
            raise HTTPException(status_code=400, detail="Collection does not belong to the specified project")
        
        # 更新collection_metadata中的clip_ids
        metadata = getattr(collection, 'collection_metadata', {}) or {}
        metadata['clip_ids'] = clip_ids
        
        # 直接更新数据库中的collection_metadata字段
        from sqlalchemy import update
        from backend.models.collection import Collection
        
        stmt = update(Collection).where(Collection.id == collection_id).values(
            collection_metadata=metadata
        )
        collection_service.db.execute(stmt)
        collection_service.db.commit()
        
        return {
            "message": "Collection clips reordered successfully",
            "clip_ids": clip_ids
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新排序合集 {collection_id} 切片失败: {e}")
        raise HTTPException(status_code=500, detail=f"重新排序失败: {str(e)}")


@router.post("/sync/{project_id}")
async def sync_project_from_filesystem(
    project_id: str,
    db: Session = Depends(get_db)
):
    """从文件系统同步指定项目数据到数据库"""
    try:
        from backend.services.data_sync_service import DataSyncService
        from backend.core.config import get_data_directory
        
        # 获取数据目录
        data_dir = get_data_directory()
        project_dir = data_dir / "projects" / project_id
        
        if not project_dir.exists():
            raise HTTPException(status_code=404, detail=f"项目目录不存在: {project_id}")
        
        # 创建数据同步服务
        sync_service = DataSyncService(db)
        
        # 同步项目数据
        result = sync_service.sync_project_from_filesystem(project_id, project_dir)
        
        return {
            "success": result.get("success", False),
            "project_id": project_id,
            "clips_synced": result.get("clips_synced", 0),
            "collections_synced": result.get("collections_synced", 0),
            "message": f"项目 {project_id} 同步完成"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"同步项目 {project_id} 数据失败: {e}")
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.post("/{project_id}/collections/{collection_id}/generate")
async def generate_collection_video(
    project_id: str,
    collection_id: str,
    db: Session = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service)
):
    """生成合集视频"""
    try:
        from ...models.collection import Collection
        from ...models.clip import Clip
        from ...utils.video_processor import VideoProcessor
        from ...core.path_utils import get_project_directory
        from pathlib import Path
        import json
        
        # 验证项目是否存在
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 获取合集记录
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(status_code=404, detail="合集不存在")
        
        # 验证合集属于该项目
        if str(collection.project_id) != project_id:
            raise HTTPException(status_code=400, detail="合集不属于指定项目")
        
        # 获取合集的切片ID列表
        metadata = getattr(collection, 'collection_metadata', {}) or {}
        clip_ids = metadata.get('clip_ids', [])
        
        if not clip_ids:
            raise HTTPException(status_code=400, detail="合集没有包含任何切片")
        
        # 获取切片信息，并按照clip_ids的顺序排列
        clips_dict = {clip.id: clip for clip in db.query(Clip).filter(Clip.id.in_(clip_ids)).all()}
        if len(clips_dict) != len(clip_ids):
            raise HTTPException(status_code=400, detail="部分切片不存在")
        
        # 按照用户调整的顺序获取clips
        ordered_clips = [clips_dict[clip_id] for clip_id in clip_ids if clip_id in clips_dict]
        
        # 获取项目目录
        project_dir = get_project_directory(project_id)
        collections_dir = project_dir / "output" / "collections"
        collections_dir.mkdir(parents=True, exist_ok=True)
        
        # 准备切片视频文件路径，按照用户调整的顺序
        clips_dir = project_dir / "output" / "clips"
        clip_video_paths = []
        
        for clip in ordered_clips:
            if clip.video_path and Path(clip.video_path).exists():
                clip_video_paths.append(Path(clip.video_path))
            else:
                # 尝试在clips目录中查找
                possible_paths = [
                    clips_dir / f"{clip.id}_*.mp4",
                    clips_dir / f"clip_{clip.id}.mp4",
                    clips_dir / f"{clip.id}.mp4"
                ]
                
                found = False
                for pattern in possible_paths:
                    if pattern.name.endswith('*'):
                        # 处理通配符
                        matches = list(clips_dir.glob(pattern.name))
                        if matches:
                            clip_video_paths.append(matches[0])
                            found = True
                            break
                    else:
                        if pattern.exists():
                            clip_video_paths.append(pattern)
                            found = True
                            break
                
                if not found:
                    raise HTTPException(status_code=404, detail=f"切片视频文件不存在: {clip.id}")
        
        # 生成合集视频文件名 - 使用合集标题作为文件名
        collection_name = collection.name or f"collection_{collection_id}"
        # 使用VideoProcessor的sanitize_filename方法清理文件名
        from ...utils.video_processor import VideoProcessor
        safe_name = VideoProcessor.sanitize_filename(collection_name)
        output_filename = f"{safe_name}.mp4"
        output_path = collections_dir / output_filename
        
        # 使用VideoProcessor创建合集
        video_processor = VideoProcessor(
            clips_dir=str(clips_dir),
            collections_dir=str(collections_dir)
        )
        success = video_processor.create_collection(clip_video_paths, output_path)
        
        if not success:
            raise HTTPException(status_code=500, detail="合集视频生成失败")
        
        # 生成合集封面
        thumbnail_path = None
        try:
            thumbnail_filename = f"{collection_id}_{safe_name}_thumbnail.jpg"
            thumbnail_path = collections_dir / thumbnail_filename
            
            # 从视频中提取封面（第5秒的帧）
            thumbnail_success = video_processor.extract_thumbnail(output_path, thumbnail_path, time_offset=5)
            if thumbnail_success:
                collection.thumbnail_path = str(thumbnail_path)
                logger.info(f"合集封面生成成功: {thumbnail_path}")
            else:
                logger.warning(f"合集封面生成失败: {collection_id}")
        except Exception as e:
            logger.error(f"生成合集封面时出错: {e}")
        
        # 更新合集的export_path
        collection.export_path = str(output_path)
        db.commit()
        
        return {
            "success": True,
            "message": "合集视频生成成功",
            "collection_id": collection_id,
            "output_path": str(output_path),
            "filename": output_filename
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成合集视频失败: {e}")
        raise HTTPException(status_code=500, detail=f"生成合集视频失败: {str(e)}")


@router.get("/{project_id}/download")
async def download_project_file(
    project_id: str,
    clip_id: Optional[str] = Query(None, description="下载指定切片"),
    collection_id: Optional[str] = Query(None, description="下载指定合集"),
    db: Session = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service)
):
    """下载项目文件（切片或合集）"""
    try:
        from fastapi.responses import FileResponse
        from pathlib import Path
        
        # 验证项目是否存在
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        if collection_id:
            # 下载合集视频
            from ...models.collection import Collection
            collection = db.query(Collection).filter(Collection.id == collection_id).first()
            if not collection:
                raise HTTPException(status_code=404, detail="合集不存在")
            
            if not collection.export_path:
                raise HTTPException(status_code=404, detail="合集视频文件不存在")
            
            file_path = Path(collection.export_path)
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="合集视频文件不存在")
            
            # 生成下载文件名
            collection_name = collection.name or f"collection_{collection_id}"
            from ...utils.video_processor import VideoProcessor
            safe_name = VideoProcessor.sanitize_filename(collection_name)
            filename = f"{safe_name}.mp4"
            
            # 对文件名进行URL编码
            import urllib.parse
            encoded_filename = urllib.parse.quote(filename.encode('utf-8'))
            
            return FileResponse(
                path=str(file_path),
                filename=filename,
                media_type="video/mp4",
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
                }
            )
        
        elif clip_id:
            # 下载切片视频
            from ...models.clip import Clip
            clip = db.query(Clip).filter(Clip.id == clip_id).first()
            if not clip:
                raise HTTPException(status_code=404, detail="切片不存在")
            
            if not clip.video_path:
                raise HTTPException(status_code=404, detail="切片视频文件不存在")
            
            file_path = Path(clip.video_path)
            if not file_path.exists():
                raise HTTPException(status_code=404, detail="切片视频文件不存在")
            
            # 生成下载文件名
            clip_title = clip.title or f"clip_{clip_id}"
            from ...utils.video_processor import VideoProcessor
            safe_name = VideoProcessor.sanitize_filename(clip_title)
            filename = f"{safe_name}.mp4"
            
            # 对文件名进行URL编码
            import urllib.parse
            encoded_filename = urllib.parse.quote(filename.encode('utf-8'))
            
            return FileResponse(
                path=str(file_path),
                filename=filename,
                media_type="video/mp4",
                headers={
                    "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
                }
            )
        
        else:
            raise HTTPException(status_code=400, detail="必须指定clip_id或collection_id")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载文件失败: {str(e)}")


@router.get("/{project_id}/collections/{collection_id}/thumbnail")
async def get_collection_thumbnail(
    project_id: str,
    collection_id: str,
    db: Session = Depends(get_db),
    project_service: ProjectService = Depends(get_project_service)
):
    """获取合集封面图片"""
    try:
        from fastapi.responses import FileResponse
        from pathlib import Path
        
        # 验证项目是否存在
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 获取合集记录
        from ...models.collection import Collection
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(status_code=404, detail="合集不存在")
        
        # 验证合集属于该项目
        if str(collection.project_id) != project_id:
            raise HTTPException(status_code=400, detail="合集不属于指定项目")
        
        # 检查是否有封面
        if not collection.thumbnail_path:
            raise HTTPException(status_code=404, detail="合集封面不存在")
        
        thumbnail_path = Path(collection.thumbnail_path)
        if not thumbnail_path.exists():
            raise HTTPException(status_code=404, detail="合集封面文件不存在")
        
        return FileResponse(
            path=str(thumbnail_path),
            media_type="image/jpeg",
            headers={
                "Cache-Control": "public, max-age=3600"  # 缓存1小时
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取合集封面失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取合集封面失败: {str(e)}")