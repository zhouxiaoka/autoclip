"""
任务队列API
提供任务提交、状态查询、取消等接口
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

from core.database import get_db
from services.task_queue_service import TaskQueueService
from schemas.task import TaskCreate, TaskResponse
from schemas.base import SuccessResponse

router = APIRouter(tags=["任务队列"])


@router.post("/submit/video-processing", response_model=SuccessResponse)
async def submit_video_processing_task(
    project_id: str,
    srt_path: str,
    db: Session = Depends(get_db)
):
    """
    提交视频处理任务
    
    Args:
        project_id: 项目ID
        srt_path: SRT文件路径
        db: 数据库会话
        
    Returns:
        任务提交结果
    """
    try:
        task_service = TaskQueueService(db)
        result = task_service.submit_video_processing_task(project_id, srt_path)
        
        return SuccessResponse(
            message="视频处理任务已提交",
            data=result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交任务失败: {str(e)}")


@router.post("/submit/single-step", response_model=SuccessResponse)
async def submit_single_step_task(
    project_id: str,
    step_name: str,
    srt_path: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    提交单个步骤处理任务
    
    Args:
        project_id: 项目ID
        step_name: 步骤名称
        srt_path: SRT文件路径（仅Step1需要）
        db: 数据库会话
        
    Returns:
        任务提交结果
    """
    try:
        task_service = TaskQueueService(db)
        result = task_service.submit_single_step_task(project_id, step_name, srt_path)
        
        return SuccessResponse(
            message=f"步骤 {step_name} 处理任务已提交",
            data=result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交任务失败: {str(e)}")


@router.post("/submit/retry", response_model=SuccessResponse)
async def submit_retry_task(
    project_id: str,
    task_id: str,
    step_name: str,
    srt_path: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    提交重试任务
    
    Args:
        project_id: 项目ID
        task_id: 任务ID
        step_name: 步骤名称
        srt_path: SRT文件路径（仅Step1需要）
        db: 数据库会话
        
    Returns:
        任务提交结果
    """
    try:
        task_service = TaskQueueService(db)
        result = task_service.submit_retry_task(project_id, task_id, step_name, srt_path)
        
        return SuccessResponse(
            message=f"步骤 {step_name} 重试任务已提交",
            data=result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交重试任务失败: {str(e)}")


@router.get("/status/{task_id}", response_model=SuccessResponse)
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    获取任务状态
    
    Args:
        task_id: 任务ID
        db: 数据库会话
        
    Returns:
        任务状态信息
    """
    try:
        task_service = TaskQueueService(db)
        result = task_service.get_task_status(task_id)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        return SuccessResponse(
            message="获取任务状态成功",
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")


@router.get("/project/{project_id}", response_model=SuccessResponse)
async def get_project_tasks(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    获取项目的所有任务
    
    Args:
        project_id: 项目ID
        db: 数据库会话
        
    Returns:
        任务列表
    """
    try:
        task_service = TaskQueueService(db)
        tasks = task_service.get_project_tasks(project_id)
        
        return SuccessResponse(
            message="获取项目任务列表成功",
            data={
                'project_id': project_id,
                'tasks': tasks,
                'total': len(tasks)
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取项目任务失败: {str(e)}")


@router.post("/cancel/{task_id}", response_model=SuccessResponse)
async def cancel_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    取消任务
    
    Args:
        task_id: 任务ID
        db: 数据库会话
        
    Returns:
        取消结果
    """
    try:
        task_service = TaskQueueService(db)
        result = task_service.cancel_task(task_id)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        return SuccessResponse(
            message="任务已取消",
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"取消任务失败: {str(e)}")


@router.post("/submit/video-clips", response_model=SuccessResponse)
async def submit_video_clips_task(
    project_id: str,
    clip_data: List[Dict[str, Any]],
    db: Session = Depends(get_db)
):
    """
    提交视频片段提取任务
    
    Args:
        project_id: 项目ID
        clip_data: 片段数据列表
        db: 数据库会话
        
    Returns:
        任务提交结果
    """
    try:
        task_service = TaskQueueService(db)
        result = task_service.submit_video_clips_task(project_id, clip_data)
        
        return SuccessResponse(
            message=f"视频片段提取任务已提交，共 {len(clip_data)} 个片段",
            data=result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交视频片段提取任务失败: {str(e)}")


@router.post("/submit/collections", response_model=SuccessResponse)
async def submit_collection_generation_task(
    project_id: str,
    collection_data: List[Dict[str, Any]],
    db: Session = Depends(get_db)
):
    """
    提交合集生成任务
    
    Args:
        project_id: 项目ID
        collection_data: 合集数据列表
        db: 数据库会话
        
    Returns:
        任务提交结果
    """
    try:
        task_service = TaskQueueService(db)
        result = task_service.submit_collection_generation_task(project_id, collection_data)
        
        return SuccessResponse(
            message=f"视频合集生成任务已提交，共 {len(collection_data)} 个合集",
            data=result
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交合集生成任务失败: {str(e)}")


@router.get("/queue/status", response_model=SuccessResponse)
async def get_queue_status():
    """
    获取队列状态
    
    Returns:
        队列状态信息
    """
    try:
        from core.celery_app import celery_app
        
        # 获取活跃任务数
        active_tasks = celery_app.control.inspect().active()
        reserved_tasks = celery_app.control.inspect().reserved()
        
        queue_status = {
            'active_tasks': len(active_tasks.get('celery@localhost', [])) if active_tasks else 0,
            'reserved_tasks': len(reserved_tasks.get('celery@localhost', [])) if reserved_tasks else 0,
            'workers': len(celery_app.control.inspect().stats() or {}),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        return SuccessResponse(
            message="获取队列状态成功",
            data=queue_status
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取队列状态失败: {str(e)}")