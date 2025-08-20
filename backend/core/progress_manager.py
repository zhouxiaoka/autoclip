"""进度管理器
统一处理任务进度更新和状态同步
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from sqlalchemy.orm import Session

from models.task import Task
from models.project import Project
from services.websocket_notification_service import WebSocketNotificationService
from core.websocket_manager import manager as websocket_manager

logger = logging.getLogger(__name__)


class ProgressManager:
    """进度管理器，负责任务进度更新和状态同步"""
    
    def __init__(self, db: Session):
        self.db = db
        self.websocket_service = WebSocketNotificationService()
        self._callbacks: Dict[str, Callable] = {}
    
    def register_callback(self, callback_id: str, callback: Callable):
        """注册进度回调函数
        
        Args:
            callback_id: 回调ID
            callback: 回调函数
        """
        self._callbacks[callback_id] = callback
        logger.debug(f"注册进度回调: {callback_id}")
    
    def unregister_callback(self, callback_id: str):
        """注销进度回调函数
        
        Args:
            callback_id: 回调ID
        """
        if callback_id in self._callbacks:
            del self._callbacks[callback_id]
            logger.debug(f"注销进度回调: {callback_id}")
    
    async def update_task_progress(
        self,
        task_id: str,  # 改为str类型，因为Task.id是UUID字符串
        current_step: int,
        total_steps: int,
        step_name: str,
        progress: float,
        message: Optional[str] = None,
        step_result: Optional[Dict[str, Any]] = None
    ):
        """更新任务进度
        
        Args:
            task_id: 任务ID
            current_step: 当前步骤
            total_steps: 总步骤数
            step_name: 步骤名称
            progress: 进度百分比 (0-100)
            message: 进度消息
            step_result: 步骤结果数据
        """
        try:
            # 更新数据库中的任务状态
            task = self.db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"任务 {task_id} 不存在")
                return
            
            # 更新任务字段
            task.current_step = current_step
            task.total_steps = total_steps
            task.progress = progress
            task.updated_at = datetime.utcnow()
            
            # 如果有步骤结果，更新到任务结果中
            if step_result:
                if not task.result:
                    task.result = {}
                task.result[f"step_{current_step}"] = step_result
            
            # 如果进度达到100%，标记为完成
            if progress >= 100:
                task.status = "completed"
                task.completed_at = datetime.utcnow()
                
                # 同时更新项目状态
                project = self.db.query(Project).filter(Project.id == task.project_id).first()
                if project:
                    project.status = "completed"
                    project.completed_at = datetime.utcnow()
            
            self.db.commit()
            
            # 发送WebSocket通知
            await self.websocket_service.send_processing_progress(
                project_id=task.project_id,
                current_step=current_step,
                total_steps=total_steps,
                step_name=step_name,
                progress=progress,
                message=message or f"正在执行步骤 {current_step}/{total_steps}: {step_name}"
            )
            
            # 发送任务更新通知
            await self.websocket_service.send_task_update(
                task_id=task_id,
                project_id=task.project_id,
                status=task.status,
                progress=progress,
                message=message or f"步骤 {current_step}: {step_name}"
            )
            
            # 调用注册的回调函数
            for callback_id, callback in self._callbacks.items():
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback({
                            'task_id': task_id,
                            'project_id': task.project_id,
                            'current_step': current_step,
                            'total_steps': total_steps,
                            'step_name': step_name,
                            'progress': progress,
                            'message': message,
                            'step_result': step_result
                        })
                    else:
                        callback({
                            'task_id': task_id,
                            'project_id': task.project_id,
                            'current_step': current_step,
                            'total_steps': total_steps,
                            'step_name': step_name,
                            'progress': progress,
                            'message': message,
                            'step_result': step_result
                        })
                except Exception as e:
                    logger.error(f"执行进度回调 {callback_id} 失败: {str(e)}")
            
            logger.info(f"任务 {task_id} 进度更新: {current_step}/{total_steps} ({progress}%) - {step_name}")
            
        except Exception as e:
            logger.error(f"更新任务进度失败: {str(e)}")
            self.db.rollback()
            raise
    
    async def update_task_error(
        self,
        task_id: int,
        error_message: str,
        current_step: Optional[int] = None,
        step_name: Optional[str] = None
    ):
        """更新任务错误状态
        
        Args:
            task_id: 任务ID
            error_message: 错误消息
            current_step: 出错的步骤
            step_name: 步骤名称
        """
        try:
            # 更新数据库中的任务状态
            task = self.db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"任务 {task_id} 不存在")
                return
            
            # 更新任务状态为失败
            task.status = "failed"
            task.error_message = error_message
            task.updated_at = datetime.utcnow()
            
            if current_step is not None:
                task.current_step = current_step
            
            # 同时更新项目状态
            project = self.db.query(Project).filter(Project.id == task.project_id).first()
            if project:
                project.status = "failed"
            
            self.db.commit()
            
            # 发送WebSocket错误通知
            await self.websocket_service.send_processing_error(
                project_id=task.project_id,
                error=error_message,
                step=step_name or f"step_{current_step}" if current_step else "unknown"
            )
            
            # 发送任务更新通知
            await self.websocket_service.send_task_update(
                task_id=task_id,
                project_id=task.project_id,
                status="failed",
                progress=task.progress,
                message=f"任务失败: {error_message}"
            )
            
            logger.error(f"任务 {task_id} 执行失败: {error_message}")
            
        except Exception as e:
            logger.error(f"更新任务错误状态失败: {str(e)}")
            self.db.rollback()
            raise
    
    async def update_project_status(
        self,
        project_id: int,
        status: str,
        message: Optional[str] = None
    ):
        """更新项目状态
        
        Args:
            project_id: 项目ID
            status: 项目状态
            message: 状态消息
        """
        try:
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                logger.error(f"项目 {project_id} 不存在")
                return
            
            old_status = project.status
            project.status = status
            project.updated_at = datetime.utcnow()
            
            if status == "completed":
                project.completed_at = datetime.utcnow()
            
            self.db.commit()
            
            # 发送WebSocket项目更新通知
            await self.websocket_service.send_project_update(
                project_id=project_id,
                status=status,
                message=message or f"项目状态从 {old_status} 更新为 {status}"
            )
            
            logger.info(f"项目 {project_id} 状态更新: {old_status} -> {status}")
            
        except Exception as e:
            logger.error(f"更新项目状态失败: {str(e)}")
            self.db.rollback()
            raise
    
    def create_progress_callback(self, task_id: int) -> Callable:
        """创建进度回调函数
        
        Args:
            task_id: 任务ID
            
        Returns:
            进度回调函数
        """
        async def progress_callback(
            current_step: int,
            total_steps: int,
            step_name: str,
            progress: float,
            message: Optional[str] = None,
            step_result: Optional[Dict[str, Any]] = None
        ):
            await self.update_task_progress(
                task_id=task_id,
                current_step=current_step,
                total_steps=total_steps,
                step_name=step_name,
                progress=progress,
                message=message,
                step_result=step_result
            )
        
        return progress_callback
    
    def create_error_callback(self, task_id: int) -> Callable:
        """创建错误回调函数
        
        Args:
            task_id: 任务ID
            
        Returns:
            错误回调函数
        """
        async def error_callback(
            error_message: str,
            current_step: Optional[int] = None,
            step_name: Optional[str] = None
        ):
            await self.update_task_error(
                task_id=task_id,
                error_message=error_message,
                current_step=current_step,
                step_name=step_name
            )
        
        return error_callback
    
    async def sync_task_status(self, task_id: int):
        """同步任务状态
        
        Args:
            task_id: 任务ID
        """
        try:
            task = self.db.query(Task).filter(Task.id == task_id).first()
            if not task:
                logger.error(f"任务 {task_id} 不存在")
                return
            
            # 检查Celery任务状态
            if task.celery_task_id:
                from celery.result import AsyncResult
                from core.celery_app import celery_app
                
                try:
                    celery_result = AsyncResult(task.celery_task_id, app=celery_app)
                    celery_status = celery_result.status
                    
                    # 根据Celery状态更新任务状态
                    if celery_status == "SUCCESS" and task.status != "completed":
                        task.status = "completed"
                        task.completed_at = datetime.utcnow()
                        task.progress = 100
                    elif celery_status == "FAILURE" and task.status != "failed":
                        task.status = "failed"
                        task.error_message = str(celery_result.info) if celery_result.info else "Unknown error"
                    elif celery_status == "REVOKED" and task.status != "cancelled":
                        task.status = "cancelled"
                        task.error_message = "Task was cancelled"
                    
                    self.db.commit()
                    
                    # 发送状态同步通知
                    await self.websocket_service.send_task_update(
                        task_id=task_id,
                        project_id=task.project_id,
                        status=task.status,
                        progress=task.progress,
                        message=f"任务状态已同步: {task.status}"
                    )
                    
                except Exception as e:
                    logger.error(f"检查Celery任务状态失败: {str(e)}")
            
        except Exception as e:
            logger.error(f"同步任务状态失败: {str(e)}")
            self.db.rollback()


# 全局进度管理器实例
_progress_managers: Dict[str, ProgressManager] = {}


def get_progress_manager(db: Session) -> ProgressManager:
    """获取进度管理器实例
    
    Args:
        db: 数据库会话
        
    Returns:
        进度管理器实例
    """
    # 使用数据库会话的ID作为键，确保每个会话有独立的管理器
    session_id = str(id(db))
    
    if session_id not in _progress_managers:
        _progress_managers[session_id] = ProgressManager(db)
    
    return _progress_managers[session_id]


def cleanup_progress_managers():
    """清理不再使用的进度管理器"""
    global _progress_managers
    _progress_managers.clear()
    logger.info("已清理所有进度管理器实例")