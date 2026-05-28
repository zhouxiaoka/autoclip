"""
任务管理API路由
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.models.task import Task
from backend.schemas.task import TaskResponse, TaskCreate, TaskUpdate
from backend.services.task_service import TaskService
from backend.services.task_queue_service import TaskQueueService

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_task_config_value(task, key: str, default=None):
    config = task.task_config or {}
    return config.get(key, default)

@router.get("/", response_model=List[TaskResponse])
async def get_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None),
    project_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """获取任务列表"""
    try:
        task_service = TaskService(db)
        tasks = task_service.get_tasks(
            skip=skip,
            limit=limit,
            status=status,
            project_id=project_id
        )
        return tasks
    except Exception as e:
        logger.exception("获取任务列表失败")
        raise HTTPException(status_code=500, detail="获取任务列表失败，请稍后重试")

@router.get("/project/{project_id}", response_model=List[TaskResponse])
async def get_project_tasks(
    project_id: str,
    db: Session = Depends(get_db)
):
    """获取指定项目的任务列表"""
    try:
        task_service = TaskService(db)
        tasks = task_service.get_tasks_by_project_id(project_id)
        return tasks
    except Exception as e:
        logger.exception("获取项目任务失败: %s", project_id)
        raise HTTPException(status_code=500, detail="获取项目任务失败，请稍后重试")

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """获取单个任务详情"""
    try:
        task_service = TaskService(db)
        task = task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取任务详情失败: %s", task_id)
        raise HTTPException(status_code=500, detail="获取任务详情失败，请稍后重试")

@router.post("/", response_model=TaskResponse)
async def create_task(
    task_data: TaskCreate,
    db: Session = Depends(get_db)
):
    """创建新任务"""
    try:
        task_service = TaskService(db)
        task = task_service.create_task(task_data)
        return task
    except Exception as e:
        logger.exception("创建任务失败")
        raise HTTPException(status_code=500, detail="创建任务失败，请稍后重试")

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_data: TaskUpdate,
    db: Session = Depends(get_db)
):
    """更新任务"""
    try:
        task_service = TaskService(db)
        task = task_service.update_task(task_id, task_data)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("更新任务失败: %s", task_id)
        raise HTTPException(status_code=500, detail="更新任务失败，请稍后重试")

@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """删除任务"""
    try:
        task_service = TaskService(db)
        success = task_service.delete_task(task_id)
        if not success:
            raise HTTPException(status_code=404, detail="任务不存在")
        return {"message": "任务删除成功"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("删除任务失败: %s", task_id)
        raise HTTPException(status_code=500, detail="删除任务失败，请稍后重试")

@router.post("/{task_id}/submit")
async def submit_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """提交任务到队列"""
    try:
        task_service = TaskService(db)
        task = task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        queue_service = TaskQueueService(db)
        task_type = str(task.task_type.value if hasattr(task.task_type, "value") else task.task_type)

        if task_type == "video_processing":
            input_video_path = _get_task_config_value(task, "input_video_path")
            input_srt_path = _get_task_config_value(task, "input_srt_path")
            if not input_video_path:
                raise HTTPException(status_code=400, detail="任务缺少 input_video_path 配置")
            result = queue_service.submit_video_processing_task(
                project_id=task.project_id,
                input_video_path=input_video_path,
                input_srt_path=input_srt_path,
            )
        elif task_type == "clip_generation":
            clip_data = _get_task_config_value(task, "clip_data", [])
            result = queue_service.submit_video_clips_task(task.project_id, clip_data)
        elif task_type == "collection_creation":
            collection_data = _get_task_config_value(task, "collection_data", [])
            result = queue_service.submit_collection_generation_task(task.project_id, collection_data)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的任务类型: {task_type}")
        
        return {
            "message": "任务已提交到队列",
            "task_id": task_id,
            "queue_task_id": result.get("task_id"),
            "celery_task_id": result.get("celery_task_id"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("提交任务失败: %s", task_id)
        raise HTTPException(status_code=500, detail="提交任务失败，请稍后重试")

@router.post("/{task_id}/retry")
async def retry_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """重试失败的任务"""
    try:
        task_service = TaskService(db)
        task = task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 重置任务状态并重新提交
        task_service.update_task(task_id, TaskUpdate(status="pending", progress=0))
        
        queue_service = TaskQueueService(db)
        task_type = str(task.task_type.value if hasattr(task.task_type, "value") else task.task_type)

        if task_type == "video_processing":
            input_video_path = _get_task_config_value(task, "input_video_path")
            input_srt_path = _get_task_config_value(task, "input_srt_path")
            if not input_video_path:
                raise HTTPException(status_code=400, detail="任务缺少 input_video_path 配置")
            result = queue_service.submit_video_processing_task(
                project_id=task.project_id,
                input_video_path=input_video_path,
                input_srt_path=input_srt_path,
            )
        elif task_type == "clip_generation":
            clip_data = _get_task_config_value(task, "clip_data", [])
            result = queue_service.submit_video_clips_task(task.project_id, clip_data)
        elif task_type == "collection_creation":
            collection_data = _get_task_config_value(task, "collection_data", [])
            result = queue_service.submit_collection_generation_task(task.project_id, collection_data)
        else:
            raise HTTPException(status_code=400, detail=f"不支持的任务类型: {task_type}")
        
        return {
            "message": "任务已重新提交",
            "task_id": task_id,
            "queue_task_id": result.get("task_id"),
            "celery_task_id": result.get("celery_task_id"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("重试任务失败: %s", task_id)
        raise HTTPException(status_code=500, detail="重试任务失败，请稍后重试")

@router.get("/{task_id}/status")
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db)
):
    """获取任务状态"""
    try:
        task_service = TaskService(db)
        task = task_service.get_task_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        return {
            "task_id": task_id,
            "status": task.status,
            "progress": task.progress,
            "message": task.name,
            "error": task.error_message,
            "updated_at": task.updated_at
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("获取任务状态失败: %s", task_id)
        raise HTTPException(status_code=500, detail="获取任务状态失败，请稍后重试")

