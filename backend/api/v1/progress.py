"""
任务进度查询API
提供实时任务进度查询功能
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from ...core.database import get_db
from ...models.task import Task, TaskStatus
from ...services.progress_update_service import progress_update_service
from datetime import datetime

router = APIRouter()

@router.get("/task/{task_id}")
async def get_task_progress(task_id: str, db: Session = Depends(get_db)):
    """获取指定任务的进度"""
    try:
        # 从数据库获取任务信息
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # 获取实时进度信息
        realtime_progress = progress_update_service.get_task_progress(task_id)
        
        response = {
            'id': task.id,
            'project_id': task.project_id,
            'name': task.name,
            'status': task.status,
            'progress': task.progress,
            'current_step': task.current_step,
            'created_at': task.created_at.isoformat() if task.created_at else None,
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'updated_at': task.updated_at.isoformat() if task.updated_at else None
        }
        
        # 如果有实时进度信息，合并进去
        if realtime_progress:
            response.update({
                'realtime_progress': realtime_progress['progress'],
                'realtime_step': realtime_progress['current_step'],
                'step_details': realtime_progress.get('step_details'),
                'last_update': realtime_progress['updated_at'].isoformat()
            })
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/project/{project_id}")
async def get_project_tasks_progress(project_id: str, db: Session = Depends(get_db)):
    """获取指定项目的所有任务进度"""
    try:
        # 获取项目的所有任务
        tasks = db.query(Task).filter(Task.project_id == project_id).all()
        
        tasks_progress = []
        for task in tasks:
            # 获取实时进度信息
            realtime_progress = progress_update_service.get_task_progress(task.id)
            
            task_info = {
                'id': task.id,
                'name': task.name,
                'status': task.status,
                'progress': task.progress,
                'current_step': task.current_step,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'updated_at': task.updated_at.isoformat() if task.updated_at else None
            }
            
            # 如果有实时进度信息，合并进去
            if realtime_progress:
                task_info.update({
                    'realtime_progress': realtime_progress['progress'],
                    'realtime_step': realtime_progress['current_step'],
                    'step_details': realtime_progress.get('step_details'),
                    'last_update': realtime_progress['updated_at'].isoformat()
                })
            
            tasks_progress.append(task_info)
        
        return {
            'project_id': project_id,
            'tasks': tasks_progress,
            'total_tasks': len(tasks_progress),
            'running_tasks': len([t for t in tasks_progress if t['status'] == 'running']),
            'completed_tasks': len([t for t in tasks_progress if t['status'] == 'completed']),
            'failed_tasks': len([t for t in tasks_progress if t['status'] == 'failed'])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/active")
async def get_active_tasks():
    """获取所有活动任务的进度"""
    try:
        active_tasks = progress_update_service.get_all_active_tasks()
        
        # 转换为前端友好的格式
        formatted_tasks = []
        for task_id, progress_info in active_tasks.items():
            formatted_tasks.append({
                'task_id': task_id,
                'progress': progress_info['progress'],
                'current_step': progress_info['current_step'],
                'step_details': progress_info.get('step_details'),
                'started_at': progress_info['started_at'].isoformat() if progress_info['started_at'] else None,
                'updated_at': progress_info['updated_at'].isoformat() if progress_info['updated_at'] else None
            })
        
        return {
            'active_tasks': formatted_tasks,
            'total_active': len(formatted_tasks)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/summary")
async def get_progress_summary(db: Session = Depends(get_db)):
    """获取进度摘要信息"""
    try:
        # 统计各种状态的任务数量
        total_tasks = db.query(Task).count()
        running_tasks = db.query(Task).filter(Task.status == TaskStatus.RUNNING).count()
        completed_tasks = db.query(Task).filter(Task.status == TaskStatus.COMPLETED).count()
        failed_tasks = db.query(Task).filter(Task.status == TaskStatus.FAILED).count()
        pending_tasks = db.query(Task).filter(Task.status == TaskStatus.PENDING).count()
        
        # 获取活动任务的实时进度
        active_tasks = progress_update_service.get_all_active_tasks()
        
        return {
            'summary': {
                'total_tasks': total_tasks,
                'running_tasks': running_tasks,
                'completed_tasks': completed_tasks,
                'failed_tasks': failed_tasks,
                'pending_tasks': pending_tasks
            },
            'active_tasks_count': len(active_tasks),
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
