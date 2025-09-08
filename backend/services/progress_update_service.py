"""
任务进度更新服务
提供实时进度更新功能
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from ..core.database import SessionLocal
from ..models.task import Task, TaskStatus
from ..core.websocket_manager import manager as websocket_manager

logger = logging.getLogger(__name__)

class ProgressUpdateService:
    """任务进度更新服务"""
    
    def __init__(self):
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
    
    async def update_task_progress(
        self, 
        task_id: str, 
        progress: float, 
        current_step: str = None,
        step_details: str = None
    ):
        """更新任务进度"""
        try:
            # 更新数据库中的任务进度
            db = SessionLocal()
            try:
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.progress = progress
                    if current_step:
                        task.current_step = current_step
                    task.updated_at = datetime.utcnow()
                    db.commit()
                    
                    # 记录到活动任务中
                    self.active_tasks[task_id] = {
                        'progress': progress,
                        'current_step': current_step,
                        'step_details': step_details,
                        'updated_at': datetime.utcnow()
                    }
                    
                    logger.info(f"任务 {task_id} 进度更新: {progress}% - {current_step}")
                    
                    # 通过WebSocket发送进度更新
                    await self.broadcast_progress_update(task)
                else:
                    logger.warning(f"任务 {task_id} 不存在")
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"更新任务进度失败: {e}")
    
    async def broadcast_progress_update(self, task: Task):
        """广播进度更新到前端"""
        try:
            # 构建进度更新消息
            progress_message = {
                'type': 'task_progress_update',
                'task_id': task.id,
                'project_id': task.project_id,
                'progress': task.progress,
                'current_step': task.current_step,
                'status': task.status,
                'updated_at': task.updated_at.isoformat() if task.updated_at else None
            }
            
            # 发送到所有连接的客户端
            await websocket_manager.broadcast(progress_message)
            logger.debug(f"进度更新已广播: {progress_message}")
            
        except Exception as e:
            logger.error(f"广播进度更新失败: {e}")
    
    async def start_progress_monitoring(self, task_id: str):
        """开始监控任务进度"""
        try:
            db = SessionLocal()
            try:
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    # 标记任务为运行中
                    task.status = TaskStatus.RUNNING
                    task.started_at = datetime.utcnow()
                    db.commit()
                    
                    # 添加到活动任务列表
                    self.active_tasks[task_id] = {
                        'progress': 0.0,
                        'current_step': '初始化',
                        'step_details': '开始处理任务',
                        'started_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                    
                    logger.info(f"开始监控任务进度: {task_id}")
                    
                    # 发送任务开始通知
                    await self.broadcast_progress_update(task)
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"开始进度监控失败: {e}")
    
    async def complete_task(self, task_id: str, result: Dict[str, Any] = None, error: str = None):
        """完成任务"""
        try:
            db = SessionLocal()
            try:
                task = db.query(Task).filter(Task.id == task_id).first()
                if task:
                    if error:
                        task.status = TaskStatus.FAILED
                        task.error_message = error
                    else:
                        task.status = TaskStatus.COMPLETED
                        task.progress = 100.0
                        task.current_step = '完成'
                    
                    task.completed_at = datetime.utcnow()
                    task.updated_at = datetime.utcnow()
                    db.commit()
                    
                    # 从活动任务列表中移除
                    if task_id in self.active_tasks:
                        del self.active_tasks[task_id]
                    
                    logger.info(f"任务完成: {task_id}, 状态: {task.status}")
                    
                    # 发送任务完成通知
                    await self.broadcast_progress_update(task)
                    
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"完成任务失败: {e}")
    
    def get_task_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务进度"""
        return self.active_tasks.get(task_id)
    
    def get_all_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有活动任务"""
        return self.active_tasks.copy()

# 全局实例
progress_update_service = ProgressUpdateService()
