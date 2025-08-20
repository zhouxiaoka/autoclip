"""
项目API路由
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from core.database import get_db
from core.celery_app import celery_app
from services.project_service import ProjectService
from services.processing_service import ProcessingService
from services.websocket_notification_service import WebSocketNotificationService
from tasks.processing import process_video_pipeline
from core.websocket_manager import manager as websocket_manager
from schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse, ProjectFilter,
    ProjectType, ProjectStatus
)
from schemas.task import TaskType
from schemas.base import PaginationParams
from pathlib import Path
import logging
from models.task import TaskType

logger = logging.getLogger(__name__)

router = APIRouter()


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    """Dependency to get project service."""
    return ProjectService(db)


def get_processing_service(db: Session = Depends(get_db)) -> ProcessingService:
    """Dependency to get processing service."""
    return ProcessingService(db)


def get_websocket_service(db: Session = Depends(get_db)) -> WebSocketNotificationService:
    """Dependency to get websocket notification service."""
    return WebSocketNotificationService()


@router.post("/upload", response_model=ProjectResponse)
async def upload_files(
    video_file: UploadFile = File(...),
    srt_file: Optional[UploadFile] = File(None),
    project_name: str = Form(...),
    video_category: Optional[str] = Form(None),
    project_service: ProjectService = Depends(get_project_service),
    processing_service: ProcessingService = Depends(get_processing_service),
    websocket_service: WebSocketNotificationService = Depends(get_websocket_service)
):
    """Upload video file and optionally subtitle file to create a new project. If no subtitle is provided, speech recognition will be used."""
    try:
        # 验证文件类型
        if not video_file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.webm')):
            raise HTTPException(status_code=400, detail="Invalid video file format")
        
        # 如果提供了字幕文件，验证其格式
        if srt_file and not srt_file.filename.lower().endswith('.srt'):
            raise HTTPException(status_code=400, detail="Invalid subtitle file format")
        
        # 创建项目数据
        subtitle_info = f", Subtitle: {srt_file.filename}" if srt_file else " (Will generate subtitle using speech recognition)"
        project_data = ProjectCreate(
            name=project_name,
            description=f"Video: {video_file.filename}{subtitle_info}",
            project_type=ProjectType.KNOWLEDGE,  # 默认类型
            status=ProjectStatus.PENDING,
            source_url=None,
            source_file=video_file.filename,
            settings={
                "video_category": video_category or "knowledge",
                "video_file": video_file.filename,
                "srt_file": srt_file.filename if srt_file else None,
                "auto_generate_subtitle": srt_file is None
            }
        )
        
        # 创建项目
        project = project_service.create_project(project_data)
        
        # 保存文件到项目目录
        project_id = str(project.id)
        from core.path_utils import get_project_raw_directory, ensure_directory_exists
        raw_dir = ensure_directory_exists(get_project_raw_directory(project_id))
        
        logger.info(f"开始保存文件到项目目录: {project_dir}")
        
        # 保存视频文件
        video_path = raw_dir / video_file.filename
        logger.info(f"保存视频文件: {video_path}")
        try:
            with open(video_path, "wb") as f:
                content = await video_file.read()
                f.write(content)
            logger.info(f"视频文件保存成功: {video_path}, 大小: {len(content)} bytes")
        except Exception as e:
            logger.error(f"视频文件保存失败: {e}")
            raise
        
        # 处理字幕文件
        srt_path = None
        if srt_file:
            # 保存用户提供的字幕文件
            srt_path = raw_dir / srt_file.filename
            logger.info(f"保存用户字幕文件: {srt_path}")
            try:
                with open(srt_path, "wb") as f:
                    content = await srt_file.read()
                    f.write(content)
                logger.info(f"用户字幕文件保存成功: {srt_path}, 大小: {len(content)} bytes")
            except Exception as e:
                logger.error(f"用户字幕文件保存失败: {e}")
                raise
        else:
            # 使用语音识别生成字幕文件
            logger.info("未提供字幕文件，开始使用语音识别生成字幕")
            try:
                from shared.utils.speech_recognizer import generate_subtitle_for_video, SpeechRecognitionError
                
                # 生成字幕文件
                srt_path = raw_dir / f"{video_file.filename.rsplit('.', 1)[0]}.srt"
                logger.info(f"开始语音识别，输出路径: {srt_path}")
                
                # 根据视频分类确定语言
                language = "auto"  # 默认自动检测
                if video_category == "business" or video_category == "knowledge":
                    language = "zh"  # 中文内容
                elif video_category == "entertainment":
                    language = "auto"  # 娱乐内容可能是多语言
                
                generated_srt = generate_subtitle_for_video(
                    video_path, 
                    srt_path, 
                    language=language,
                    model="base"  # 使用平衡的模型
                )
                if generated_srt:
                    logger.info(f"语音识别字幕生成成功: {generated_srt}")
                    srt_path = generated_srt
                else:
                    raise SpeechRecognitionError("语音识别返回空结果")
                
            except SpeechRecognitionError as e:
                logger.error(f"语音识别失败: {e}")
                # 更新项目状态为失败
                project_service.update_project_status(project_id, "failed")
                raise HTTPException(
                    status_code=400, 
                    detail=f"语音识别失败: {e}。请手动上传字幕文件或检查语音识别服务配置。"
                )
            except Exception as e:
                logger.error(f"语音识别过程中发生未知错误: {e}")
                project_service.update_project_status(project_id, "failed")
                raise HTTPException(
                    status_code=500, 
                    detail=f"语音识别过程中发生错误: {e}"
                )
        
        logger.info(f"文件保存完成，项目目录: {project_dir}")
        
        # 验证文件是否存在
        if not video_path.exists():
            logger.error(f"视频文件不存在: {video_path}")
            raise HTTPException(status_code=500, detail="视频文件保存失败")
        
        if not srt_path:
            logger.error("字幕文件路径为空")
            raise HTTPException(status_code=500, detail="字幕文件路径生成失败")
        
        if not srt_path.exists():
            logger.error(f"字幕文件不存在: {srt_path}")
            raise HTTPException(status_code=500, detail=f"字幕文件不存在: {srt_path}")
        
        logger.info(f"文件验证成功: video={video_path.exists()}, srt={srt_path.exists()}")
        
        # 自动启动处理流程
        try:
            # 更新项目状态为处理中
            project_service.update_project_status(project_id, "processing")
            
            # 发送WebSocket通知：处理开始
            await websocket_service.send_processing_started(
                project_id=project_id,
                message="开始视频处理流程"
            )
            
            # 提交Celery任务
            logger.info(f"准备提交Celery任务: {project_id}")
            from tasks.processing import process_video_pipeline
            logger.info(f"Celery任务导入成功")
            
            celery_task = process_video_pipeline.delay(
                project_id=project_id,
                input_video_path=str(video_path),
                input_srt_path=str(srt_path)
            )
            logger.info(f"Celery任务已提交: {celery_task.id}")
            
            # 创建处理任务记录
            task_result = processing_service._create_processing_task(
                project_id=project_id,
                task_type=TaskType.VIDEO_PROCESSING
            )
            logger.info(f"处理任务记录已创建: {task_result}")
            
            logger.info(f"项目 {project_id} 处理任务已启动，Celery任务ID: {celery_task.id}")
            
        except Exception as e:
            logger.error(f"启动项目 {project_id} 处理失败: {str(e)}")
            # 即使处理启动失败，也要返回项目创建成功
            # 用户可以通过重试按钮重新启动处理
        
        # 返回项目响应
        return ProjectResponse(
            id=str(project.id),
            name=str(project.name),
            description=str(project.description) if project.description else None,
            project_type=ProjectType(project.project_type) if hasattr(project.project_type, 'value') else ProjectType(project.project_type),
            status=ProjectStatus(project.status) if hasattr(project.status, 'value') else ProjectStatus(project.status),
            source_url=project.project_metadata.get("source_url") if project.project_metadata else None,
            source_file=project.project_metadata.get("source_file") if project.project_metadata else None,
            settings=project.processing_config,
            created_at=project.created_at,
            updated_at=project.updated_at,
            completed_at=project.completed_at,
            total_clips=0,
            total_collections=0,
            total_tasks=0
        )
    except HTTPException:
        # 重新抛出HTTP异常，不要被通用异常处理器捕获
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload files: {str(e)}")


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
            project_type=ProjectType(project.project_type) if hasattr(project.project_type, 'value') else ProjectType(project.project_type),
            status=ProjectStatus(project.status) if hasattr(project.status, 'value') else ProjectStatus(project.status),
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
    project_service: ProjectService = Depends(get_project_service)
):
    """Get a project by ID."""
    try:
        project = project_service.get_project_with_stats(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project
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
        
        # Convert to response using the updated project data
        return ProjectResponse(
            id=str(project_id),
            name=project.name,
            description=project.description,
            project_type=ProjectType(project.project_type.value if hasattr(project.project_type, 'value') else project.project_type),
            status=ProjectStatus(project.status.value if hasattr(project.status, 'value') else project.status),
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
        if project.status not in ["pending", "failed"]:
            raise HTTPException(status_code=400, detail="Project is not in pending or failed status")
        
        # 获取视频和SRT文件路径
        from core.path_utils import get_project_raw_directory
        raw_dir = get_project_raw_directory(project_id)
        
        video_path = None
        srt_path = None
        
        # 从项目配置中获取文件路径
        # 从video_path获取视频路径
        if project.video_path:
            video_path = Path(project.video_path)
        
        # 从processing_config或project_metadata中获取SRT路径
        if project.processing_config and "srt_file" in project.processing_config:
            srt_path = raw_dir / project.processing_config["srt_file"]
        elif project.project_metadata and "subtitle_path" in project.project_metadata:
            srt_path = Path(project.project_metadata["subtitle_path"])
        
        # 如果路径不存在，尝试从raw目录查找
        if not video_path or not video_path.exists():
            video_files = list(raw_dir.glob("*.mp4"))
            if video_files:
                video_path = video_files[0]
        
        if not srt_path or not srt_path.exists():
            srt_files = list(raw_dir.glob("*.srt"))
            if srt_files:
                srt_path = srt_files[0]
        
        # 验证文件存在
        if not video_path or not video_path.exists():
            raise HTTPException(status_code=400, detail=f"Video file not found: {video_path}")
        
        if not srt_path or not srt_path.exists():
            raise HTTPException(status_code=400, detail=f"SRT file not found: {srt_path}")
        
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
            input_srt_path=str(srt_path)
        )
        
        # 创建处理任务记录
        task_result = processing_service._create_processing_task(
            project_id=project_id,
            task_type=TaskType.VIDEO_PROCESSING
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
                project_id=project_id,
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
        if project.status not in ["failed", "completed"]:
            raise HTTPException(status_code=400, detail="Project is not in failed or completed status")
        
        # 重置项目状态
        project_service.update_project_status(project_id, "pending")
        
        # 发送WebSocket通知
        await websocket_service.send_processing_started(
            project_id=project_id,
            message="重新开始处理流程"
        )
        
        # 获取文件路径并重新提交任务
        from core.path_utils import get_project_raw_directory
        raw_dir = get_project_raw_directory(project_id)
        
        video_path = None
        srt_path = None
        
        # 从项目配置中获取文件路径
        # 从video_path获取视频路径
        if project.video_path:
            video_path = Path(project.video_path)
        
        # 从processing_config或project_metadata中获取SRT路径
        if project.processing_config and "srt_file" in project.processing_config:
            srt_path = raw_dir / project.processing_config["srt_file"]
        elif project.project_metadata and "subtitle_path" in project.project_metadata:
            srt_path = Path(project.project_metadata["subtitle_path"])
        
        # 如果路径不存在，尝试从raw目录查找
        if not video_path or not video_path.exists():
            video_files = list(raw_dir.glob("*.mp4"))
            if video_files:
                video_path = video_files[0]
        
        if not srt_path or not srt_path.exists():
            srt_files = list(raw_dir.glob("*.srt"))
            if srt_files:
                srt_path = srt_files[0]
        
        if not video_path or not video_path.exists():
            raise HTTPException(status_code=400, detail=f"Video file not found: {video_path}")
        
        if not srt_path or not srt_path.exists():
            raise HTTPException(status_code=400, detail=f"SRT file not found: {srt_path}")
        
        # 提交Celery任务
        celery_task = process_video_pipeline.delay(
            project_id=project_id,
            input_video_path=str(video_path),
            input_srt_path=str(srt_path)
        )
        
        # 创建新的处理任务记录
        task_result = processing_service._create_processing_task(
            project_id=project_id,
            task_type="video_processing"
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
                project_id=project_id,
                error=str(e),
                step="retry_initialization"
            )
        except:
            pass
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/cancel")
async def cancel_project(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service),
    websocket_service: WebSocketNotificationService = Depends(get_websocket_service)
):
    """Cancel a project processing."""
    try:
        print(f"开始取消项目: {project_id}")
        
        # 获取项目信息
        project = project_service.get(project_id)
        if not project:
            print(f"项目不存在: {project_id}")
            raise HTTPException(status_code=404, detail="Project not found")
        
        print(f"项目状态: {project.status}")
        
        # 检查项目状态
        if project.status not in ["pending", "processing"]:
            print(f"项目状态不允许取消: {project.status}")
            raise HTTPException(status_code=400, detail="Project is not in pending or processing status")
        
        # 取消相关的Celery任务
        if project.tasks:
            print(f"找到 {len(project.tasks)} 个任务需要取消")
            for task in project.tasks:
                if task.celery_task_id:
                    try:
                        print(f"取消Celery任务: {task.celery_task_id}")
                        celery_app.control.revoke(task.celery_task_id, terminate=True)
                    except Exception as e:
                        print(f"取消Celery任务失败: {e}")
                        # 即使Celery取消失败，我们也要更新数据库状态
                        pass
        else:
            print("没有找到需要取消的任务")
        
        # 更新项目状态
        print(f"更新项目状态为cancelled")
        try:
            result = project_service.update_project_status(project_id, "cancelled")
            print(f"更新状态结果: {result}")
            if not result:
                raise Exception("Failed to update project status")
        except Exception as e:
            print(f"更新项目状态失败: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to update project status: {str(e)}")
        
        # 发送WebSocket通知
        try:
            await websocket_service.send_processing_error(
                project_id=project_id,
                error="项目已取消",
                step="cancelled"
            )
        except Exception as e:
            print(f"发送WebSocket通知失败: {e}")
        
        print(f"项目取消成功: {project_id}")
        return {
            "message": "Project cancelled successfully",
            "project_id": project_id,
            "status": "cancelled"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"取消项目时发生错误: {e}")
        print(f"错误类型: {type(e)}")
        import traceback
        print(f"错误堆栈: {traceback.format_exc()}")
        try:
            await websocket_service.send_processing_error(
                project_id=project_id,
                error=str(e),
                step="cancel_error"
            )
        except:
            pass
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/resume")
async def resume_processing(
    project_id: str,
    start_step: str = Form(..., description="Step to resume from (step1_outline, step2_timeline, etc.)"),
    project_service: ProjectService = Depends(get_project_service),
    processing_service: ProcessingService = Depends(get_processing_service),
    websocket_service: WebSocketNotificationService = Depends(get_websocket_service)
):
    """Resume processing from a specific step using Celery task queue."""
    try:
        # 获取项目信息
        project = project_service.get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 检查项目状态
        if project.status not in ["failed", "processing", "pending"]:
            raise HTTPException(status_code=400, detail="Project is not in failed, processing, or pending status")
        
        # 验证步骤名称
        valid_steps = ["step1_outline", "step2_timeline", "step3_scoring", "step4_filtering", "step5_clustering", "step6_video"]
        if start_step not in valid_steps:
            raise HTTPException(status_code=400, detail=f"Invalid step: {start_step}. Valid steps: {valid_steps}")
        
        # 获取文件路径
        from core.path_utils import get_project_raw_directory
        raw_dir = get_project_raw_directory(project_id)
        
        video_path = None
        srt_path = None
        
        if project.processing_config:
            if "video_file" in project.processing_config:
                video_path = raw_dir / project.processing_config["video_file"]
            if "srt_file" in project.processing_config:
                srt_path = raw_dir / project.processing_config["srt_file"]
        
        # 对于从第一步开始的情况，需要验证原始文件
        if start_step == "step1_outline":
            if not video_path or not video_path.exists():
                raise HTTPException(status_code=400, detail=f"Video file not found: {video_path}")
            if not srt_path or not srt_path.exists():
                raise HTTPException(status_code=400, detail=f"SRT file not found: {srt_path}")
        
        # 更新项目状态为处理中
        project_service.update_project_status(project_id, "processing")
        
        # 发送WebSocket通知
        await websocket_service.send_processing_started(
            project_id=project_id,
            message=f"从步骤 {start_step} 恢复处理流程"
        )
        
        # 使用处理服务恢复执行（这会在内部调用Pipeline适配器）
        result = processing_service.resume_processing(
            project_id, 
            start_step, 
            str(srt_path) if srt_path else None
        )
        
        return {
            "message": f"Processing resumed from {start_step} successfully",
            "project_id": project_id,
            "start_step": start_step,
            "task_id": result.get("task_id"),
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        try:
            await websocket_service.send_processing_error(
                project_id=project_id,
                error=str(e),
                step=f"resume_{start_step}"
            )
        except:
            pass
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


@router.get("/{project_id}/video")
async def get_project_video(
    project_id: str,
    project_service: ProjectService = Depends(get_project_service)
):
    """Get the main video file for a project."""
    try:
        from pathlib import Path
        from fastapi.responses import FileResponse
        
        # 构建项目目录路径
        from core.path_utils import get_project_raw_directory
        raw_dir = get_project_raw_directory(project_id)
        
        logger.info(f"查找项目视频: project_id={project_id}")
        logger.info(f"原始文件目录: {raw_dir}")
        logger.info(f"原始文件目录存在: {raw_dir.exists()}")
        
        if not raw_dir.exists():
            logger.error(f"项目原始文件目录不存在: {raw_dir}")
            raise HTTPException(status_code=404, detail="Project raw directory not found")
        
        # 查找视频文件
        video_files = list(raw_dir.glob("*.mp4"))
        logger.info(f"找到的视频文件: {[f.name for f in video_files]}")
        
        if not video_files:
            logger.error(f"项目中没有找到视频文件: {raw_dir}")
            raise HTTPException(status_code=404, detail="No video file found in project")
        
        video_file = video_files[0]  # 使用第一个找到的视频文件
        logger.info(f"选择的视频文件: {video_file}")
        
        # 检查文件是否存在
        if not video_file.exists():
            logger.error(f"视频文件不存在: {video_file}")
            raise HTTPException(status_code=404, detail="Video file not found")
        
        logger.info(f"返回视频文件: {video_file}")
        
        # 返回文件流
        return FileResponse(
            path=str(video_file),
            media_type="video/mp4",
            filename=video_file.name
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目视频时发生错误: {e}")
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
        
        # 构建文件路径
        from core.path_utils import get_project_directory
        project_dir = get_project_directory(project_id)
        file_path = project_dir / filename
        
        logger.info(f"查找项目文件: project_id={project_id}, filename={filename}")
        logger.info(f"文件路径: {file_path}")
        logger.info(f"文件存在: {file_path.exists()}")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # 读取JSON文件
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return data
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
        from models.clip import Clip
        from core.database import SessionLocal
        
        # 获取clip信息
        db = SessionLocal()
        try:
            clip = db.query(Clip).filter(Clip.id == clip_id).first()
            if not clip:
                raise HTTPException(status_code=404, detail=f"Clip not found: {clip_id}")
            
            # 获取original_id
            original_id = clip.clip_metadata.get('id') if clip.clip_metadata else None
            if not original_id:
                # 如果没有id字段，尝试使用chunk_index
                chunk_index = clip.clip_metadata.get('chunk_index') if clip.clip_metadata else None
                if chunk_index is not None:
                    original_id = str(chunk_index + 1)  # chunk_index从0开始，文件ID从1开始
                else:
                    # 从元数据文件中读取id
                    metadata_file = clip.clip_metadata.get('metadata_file') if clip.clip_metadata else None
                    if metadata_file and Path(metadata_file).exists():
                        try:
                            with open(metadata_file, 'r', encoding='utf-8') as f:
                                metadata_data = json.load(f)
                                original_id = metadata_data.get('id')
                        except Exception as e:
                            logger.error(f"读取元数据文件失败: {e}")
                    
                    if not original_id:
                        raise HTTPException(status_code=404, detail=f"Clip id not found in metadata: {clip_id}")
            
        finally:
            db.close()
        
        # 构建视频文件路径
        from core.path_utils import get_clips_directory
        clips_dir = get_clips_directory()
        
        logger.info(f"查找clip视频: clip_id={clip_id}, original_id={original_id}")
        logger.info(f"clips目录: {clips_dir}")
        logger.info(f"clips目录存在: {clips_dir.exists()}")
        
        # 确保路径存在
        if not clips_dir.exists():
            logger.error(f"Clips目录不存在: {clips_dir}")
            raise HTTPException(status_code=404, detail=f"Clips directory not found: {clips_dir}")
        
        # 查找对应的视频文件
        video_files = list(clips_dir.glob(f"{original_id}_*.mp4"))
        logger.info(f"找到的视频文件: {[f.name for f in video_files]}")
        
        if not video_files:
            logger.error(f"没有找到original_id={original_id}的视频文件")
            raise HTTPException(status_code=404, detail=f"Clip video file not found for original_id: {original_id}")
        
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


@router.patch("/{project_id}/collections/{collection_id}/reorder")
async def reorder_project_collection_clips(
    project_id: str,
    collection_id: str,
    clip_ids: List[str],
    project_service: ProjectService = Depends(get_project_service)
):
    """Reorder clips in a collection for a specific project."""
    try:
        from services.collection_service import CollectionService
        from core.database import SessionLocal
        
        db = SessionLocal()
        try:
            collection_service = CollectionService(db)
            
            # 获取合集
            collection = collection_service.get(collection_id)
            if not collection:
                raise HTTPException(status_code=404, detail="Collection not found")
            
            # 验证合集属于指定项目
            if collection.project_id != project_id:
                raise HTTPException(status_code=403, detail="Collection does not belong to the specified project")
            
            # 更新collection_metadata中的clip_ids
            metadata = getattr(collection, 'collection_metadata', {}) or {}
            metadata['clip_ids'] = clip_ids
            
            # 直接更新数据库中的collection_metadata字段
            from sqlalchemy import update
            from models.collection import Collection
            
            stmt = update(Collection).where(Collection.id == collection_id).values(
                collection_metadata=metadata
            )
            db.execute(stmt)
            db.commit()
            
            logger.info(f"合集排序更新成功: project_id={project_id}, collection_id={collection_id}")
            
            return {"message": "Collection clips reordered successfully", "clip_ids": clip_ids}
            
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"合集排序更新失败: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))