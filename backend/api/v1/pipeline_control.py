"""
流水线控制API
提供手动启动、停止和查询流水线状态的功能
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from ...core.database import get_db
from ...models.project import Project, ProjectStatus
from ...models.task import Task, TaskStatus
from ...services.auto_pipeline_service import auto_pipeline_service
from ...services.progress_update_service import progress_update_service
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/start/{project_id}")
async def start_pipeline(
    project_id: str, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """手动启动项目流水线"""
    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 检查项目状态
        if project.status == ProjectStatus.PROCESSING:
            return {"status": "skipped", "message": "项目已在处理中"}
        
        if project.status == ProjectStatus.COMPLETED:
            return {"status": "skipped", "message": "项目已完成"}
        
        # 检查是否有运行中的任务
        running_task = db.query(Task).filter(
            Task.project_id == project_id,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
        ).first()
        
        if running_task and running_task.status == TaskStatus.RUNNING:
            return {"status": "skipped", "message": "项目已有运行中的任务"}
        
        # 在后台启动流水线
        background_tasks.add_task(
            auto_pipeline_service.auto_start_pipeline,
            project_id
        )
        
        return {
            "status": "started",
            "message": "流水线启动任务已提交",
            "project_id": project_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动流水线失败: {str(e)}")

@router.post("/stop/{project_id}")
async def stop_pipeline(project_id: str, db: Session = Depends(get_db)):
    """停止项目流水线"""
    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 查找运行中的任务
        running_tasks = db.query(Task).filter(
            Task.project_id == project_id,
            Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
        ).all()
        
        if not running_tasks:
            return {"status": "skipped", "message": "没有运行中的任务"}
        
        # 停止所有运行中的任务
        stopped_count = 0
        for task in running_tasks:
            task.status = TaskStatus.CANCELLED
            task.updated_at = datetime.utcnow()
            
            # 通过进度更新服务通知任务停止
            try:
                await progress_update_service.complete_task(
                    task_id=task.id,
                    error="任务被手动停止"
                )
            except Exception as e:
                logger.warning(f"通知任务停止失败: {e}")
            
            stopped_count += 1
        
        # 更新项目状态
        project.status = ProjectStatus.PENDING
        project.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "status": "stopped",
            "message": f"已停止 {stopped_count} 个任务",
            "project_id": project_id,
            "stopped_tasks": stopped_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"停止流水线失败: {str(e)}")

@router.post("/restart/{project_id}")
async def restart_pipeline(
    project_id: str, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """重启项目流水线"""
    try:
        # 先停止现有流水线
        stop_result = await stop_pipeline(project_id, db)
        
        # 等待一下确保停止完成
        import time
        time.sleep(2)
        
        # 重新启动流水线
        start_result = await start_pipeline(project_id, background_tasks, db)
        
        return {
            "status": "restarted",
            "message": "流水线已重启",
            "project_id": project_id,
            "stop_result": stop_result,
            "start_result": start_result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重启流水线失败: {str(e)}")

@router.get("/status/{project_id}")
async def get_pipeline_status(project_id: str, db: Session = Depends(get_db)):
    """获取项目流水线状态"""
    try:
        # 检查项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # 获取项目任务
        tasks = db.query(Task).filter(Task.project_id == project_id).all()
        
        # 获取实时进度信息
        task_statuses = []
        for task in tasks:
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
            
            if realtime_progress:
                task_info.update({
                    'realtime_progress': realtime_progress['progress'],
                    'realtime_step': realtime_progress['current_step'],
                    'step_details': realtime_progress.get('step_details')
                })
            
            task_statuses.append(task_info)
        
        return {
            'project_id': project_id,
            'project_status': project.status,
            'tasks': task_statuses,
            'total_tasks': len(tasks),
            'running_tasks': len([t for t in tasks if t.status in [TaskStatus.PENDING, TaskStatus.RUNNING]]),
            'completed_tasks': len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
            'failed_tasks': len([t for t in tasks if t.status == TaskStatus.FAILED])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取流水线状态失败: {str(e)}")

@router.get("/overview")
async def get_pipeline_overview(db: Session = Depends(get_db)):
    """获取所有流水线概览"""
    try:
        # 获取所有项目
        projects = db.query(Project).all()
        
        overview = {
            'total_projects': len(projects),
            'processing_projects': 0,
            'completed_projects': 0,
            'failed_projects': 0,
            'pending_projects': 0,
            'project_details': []
        }
        
        for project in projects:
            # 获取项目任务统计
            tasks = db.query(Task).filter(Task.project_id == project.id).all()
            
            project_info = {
                'id': project.id,
                'name': project.name,
                'status': project.status,
                'total_tasks': len(tasks),
                'running_tasks': len([t for t in tasks if t.status in [TaskStatus.PENDING, TaskStatus.RUNNING]]),
                'completed_tasks': len([t for t in tasks if t.status == TaskStatus.COMPLETED]),
                'failed_tasks': len([t for t in tasks if t.status == TaskStatus.FAILED])
            }
            
            overview['project_details'].append(project_info)
            
            # 统计项目状态
            if project.status == ProjectStatus.PROCESSING:
                overview['processing_projects'] += 1
            elif project.status == ProjectStatus.COMPLETED:
                overview['completed_projects'] += 1
            elif project.status == ProjectStatus.FAILED:
                overview['failed_projects'] += 1
            elif project.status == ProjectStatus.PENDING:
                overview['pending_projects'] += 1
        
        # 获取自动化服务状态
        auto_service_status = auto_pipeline_service.get_processing_status()
        overview['auto_service'] = auto_service_status
        
        return overview
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取流水线概览失败: {str(e)}")

@router.post("/auto-start-all")
async def auto_start_all_pending_pipelines(background_tasks: BackgroundTasks):
    """自动启动所有等待中的流水线"""
    try:
        # 在后台启动所有等待中的项目
        background_tasks.add_task(
            auto_pipeline_service.auto_start_all_pending_pipelines
        )
        
        return {
            "status": "started",
            "message": "自动启动所有等待中流水线的任务已提交"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"自动启动失败: {str(e)}")
