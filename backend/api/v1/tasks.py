"""
任务管理API路由
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.models.task import Task
from backend.schemas.task import TaskResponse, TaskCreate, TaskUpdate
from backend.services.task_service import TaskService
from backend.services.task_queue_service import TaskQueueService

router = APIRouter()

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
        raise HTTPException(status_code=500, detail=f"获取任务列表失败: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"获取项目任务失败: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"获取任务详情失败: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"更新任务失败: {str(e)}")

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
        raise HTTPException(status_code=500, detail=f"删除任务失败: {str(e)}")

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
        
        # 提交到任务队列
        queue_service = TaskQueueService()
        result = queue_service.submit_task(task)
        
        return {"message": "任务已提交到队列", "task_id": task_id, "celery_task_id": result.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"提交任务失败: {str(e)}")

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
        
        # 提交到任务队列
        queue_service = TaskQueueService()
        result = queue_service.submit_task(task)
        
        return {"message": "任务已重新提交", "task_id": task_id, "celery_task_id": result.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重试任务失败: {str(e)}")

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
            "message": task.message,
            "error": task.error,
            "updated_at": task.updated_at
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取任务状态失败: {str(e)}")

