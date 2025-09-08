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
    srt_file: UploadFile = File(...),
    project_name: str = Form(...),
    video_category: Optional[str] = Form(None),
    project_service: ProjectService = Depends(get_project_service)
):
    """Upload video and subtitle files to create a new project."""
    try:
        # 验证文件类型
        if not video_file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            raise HTTPException(status_code=400, detail="Invalid video file format")
        
        if not srt_file.filename.lower().endswith('.srt'):
            raise HTTPException(status_code=400, detail="Invalid subtitle file format")
        
        # 创建项目数据
        project_data = ProjectCreate(
            name=project_name,
            description=f"Video: {video_file.filename}, Subtitle: {srt_file.filename}",
            project_type=ProjectType.KNOWLEDGE,  # 默认类型
            status=ProjectStatus.PENDING,
            source_url=None,
            source_file=video_file.filename,
            settings={
                "video_category": video_category or "knowledge",
                "video_file": video_file.filename,
                "srt_file": srt_file.filename
            }
        )
        
        # 创建项目
        project = project_service.create_project(project_data)
        
        # 保存文件到项目目录
        project_id = str(project.id)
        project_dir = Path(__file__).parent.parent.parent / "data" / "projects" / project_id
        raw_dir = project_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存视频文件
        video_path = raw_dir / video_file.filename
        with open(video_path, "wb") as f:
            content = await video_file.read()
            f.write(content)
        
        # 保存字幕文件
        srt_path = raw_dir / srt_file.filename
        with open(srt_path, "wb") as f:
            content = await srt_file.read()
            f.write(content)
        
        # 自动启动处理流程
        try:
            # 更新项目状态为处理中
            project_service.update_project_status(str(project.id), "processing")
            
            # 发送WebSocket通知：处理开始
            from backend.services.websocket_notification_service import WebSocketNotificationService
            websocket_service = WebSocketNotificationService()
            await websocket_service.send_processing_started(
                project_id=str(project.id),
                task_id="temp_task_id",
                message="开始视频处理流程"
            )
            
            # 提交Celery任务
            from backend.utils.task_submission_utils import submit_video_pipeline_task
            task_result = submit_video_pipeline_task(
                project_id=str(project.id),
                input_video_path=str(video_path),
                input_srt_path=str(srt_path)
            )
            
            if not task_result['success']:
                logger.error(f"Celery任务提交失败: {task_result['error']}")
                # 即使任务提交失败，也要返回项目创建成功
                # 用户可以通过重试按钮重新启动处理
            else:
                logger.info(f"项目 {project.id} 处理任务已启动，Celery任务ID: {task_result['task_id']}")
            
        except Exception as e:
            logger.error(f"启动项目 {project.id} 处理失败: {str(e)}")
            # 即使处理启动失败，也要返回项目创建成功
            # 用户可以通过重试按钮重新启动处理
        
        # 返回项目响应
        return ProjectResponse(
            id=str(project.id),
            name=str(project.name),
            description=str(project.description) if project.description else None,
            project_type=ProjectType(project.project_type.value),
            status=ProjectStatus(project.status.value),
            source_url=project.project_metadata.get("source_url") if project.project_metadata else None,
            source_file=str(project.video_path) if project.video_path else None,
            video_path=str(video_path),  # 添加video_path字段
            settings={
                "video_category": video_category or "knowledge",
                "video_file": video_file.filename,
                "srt_file": srt_file.filename
            },  # 只包含可序列化的数据
            created_at=project.created_at,
            updated_at=project.updated_at,
            completed_at=project.completed_at,
            total_clips=0,
            total_collections=0,
            total_tasks=0
        )
        
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
    """Delete a project."""
    try:
        success = project_service.delete(project_id)
        if not success:
            raise HTTPException(status_code=404, detail="Project not found")
        return {"message": "Project deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
        
        # 从settings中获取SRT文件路径
        if project.settings and "subtitle_path" in project.settings:
            srt_path = project.settings["subtitle_path"]
        
        # 验证文件存在
        if not video_path or not Path(video_path).exists():
            raise HTTPException(status_code=400, detail=f"Video file not found: {video_path}")
        
        if not srt_path or not Path(srt_path).exists():
            raise HTTPException(status_code=400, detail=f"SRT file not found: {srt_path}")
        
        # 更新项目状态为处理中
        project_service.update_project_status(project_id, "processing")
        
        # 发送WebSocket通知：处理开始
        await websocket_service.send_processing_started(
            project_id=int(project_id),
            message="开始视频处理流程"
        )
        
        # 提交Celery任务
        celery_task = process_video_pipeline.delay(
            project_id=int(project_id),
            input_video_path=str(video_path),
            input_srt_path=str(srt_path)
        )
        
        # 创建处理任务记录
        task_result = processing_service._create_processing_task(
            project_id=int(project_id),
            task_type="video_pipeline",
            celery_task_id=celery_task.id
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
        
        # 检查项目状态
        if project.status.value not in ["failed", "completed"]:
            raise HTTPException(status_code=400, detail="Project is not in failed or completed status")
        
        # 重置项目状态
        project_service.update_project_status(project_id, "pending")
        
        # 发送WebSocket通知
        await websocket_service.send_processing_started(
            project_id=int(project_id),
            message="重新开始处理流程"
        )
        
        # 获取文件路径并重新提交任务
        project_root = Path(__file__).parent.parent.parent / "data" / "projects" / project_id
        
        video_path = None
        srt_path = None
        
        if project.processing_config:
            if "video_file" in project.processing_config:
                video_path = project_root / "raw" / project.processing_config["video_file"]
            if "srt_file" in project.processing_config:
                srt_path = project_root / "raw" / project.processing_config["srt_file"]
        
        if not video_path or not video_path.exists():
            raise HTTPException(status_code=400, detail=f"Video file not found: {video_path}")
        
        if not srt_path or not srt_path.exists():
            raise HTTPException(status_code=400, detail=f"SRT file not found: {srt_path}")
        
        # 提交Celery任务
        celery_task = process_video_pipeline.delay(
            project_id=int(project_id),
            input_video_path=str(video_path),
            input_srt_path=str(srt_path)
        )
        
        # 创建新的处理任务记录
        task_result = processing_service._create_processing_task(
            project_id=int(project_id),
            task_type="video_pipeline_retry",
            celery_task_id=celery_task.id
        )
        
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
        try:
            await websocket_service.send_processing_error(
                project_id=int(project_id),
                error=str(e),
                step="retry_initialization"
            )
        except:
            pass
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
        
        # 构建文件路径
        from ...core.config import get_data_directory
        data_dir = get_data_directory()
        project_root = data_dir / "projects" / project_id
        
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
        
        # 构建视频文件路径
        project_root = Path(__file__).parent.parent.parent.parent
        clips_dir = project_root / "output" / "clips"
        
        # 确保路径存在
        if not clips_dir.exists():
            raise HTTPException(status_code=404, detail=f"Clips directory not found: {clips_dir}")
        
        # 查找对应的视频文件
        video_files = list(clips_dir.glob(f"{clip_id}_*.mp4"))
        if not video_files:
            raise HTTPException(status_code=404, detail=f"Clip video file not found for clip_id: {clip_id}")
        
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