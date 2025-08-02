"""
通知任务
处理各种通知和消息推送
"""

import logging
from typing import Dict, Any, Optional
from celery import current_task
from datetime import datetime

from backend.core.celery_app import celery_app
from backend.core.database import SessionLocal
from backend.models.task import Task, TaskStatus
from backend.repositories.task_repository import TaskRepository

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='backend.tasks.notification.send_processing_notification')
def send_processing_notification(self, project_id: str, task_id: str, message: str, notification_type: str = 'info') -> Dict[str, Any]:
    """
    发送处理通知
    
    Args:
        project_id: 项目ID
        task_id: 任务ID
        message: 通知消息
        notification_type: 通知类型 (info, warning, error, success)
        
    Returns:
        通知结果
    """
    logger.info(f"发送处理通知: {project_id}, {task_id}, {notification_type}")
    
    try:
        # 创建数据库会话
        db = SessionLocal()
        
        try:
            # 这里可以集成实际的通知系统
            # 例如：WebSocket、邮件、短信等
            
            # 模拟通知发送
            notification_data = {
                'project_id': project_id,
                'task_id': task_id,
                'message': message,
                'type': notification_type,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"通知已发送: {notification_data}")
            
            return {
                'success': True,
                'project_id': project_id,
                'task_id': task_id,
                'notification': notification_data,
                'message': '通知发送成功'
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"通知发送失败: {project_id}, {task_id}, 错误: {e}")
        raise


@celery_app.task(bind=True, name='backend.tasks.notification.send_error_notification')
def send_error_notification(self, project_id: str, task_id: str, error_message: str, error_details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    发送错误通知
    
    Args:
        project_id: 项目ID
        task_id: 任务ID
        error_message: 错误消息
        error_details: 错误详情
        
    Returns:
        通知结果
    """
    logger.error(f"发送错误通知: {project_id}, {task_id}, {error_message}")
    
    try:
        # 创建数据库会话
        db = SessionLocal()
        
        try:
            # 更新任务状态
            task_repo = TaskRepository(db)
            task = task_repo.get_by_id(task_id)
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = error_message
                db.commit()
            
            # 发送错误通知
            notification_data = {
                'project_id': project_id,
                'task_id': task_id,
                'type': 'error',
                'message': error_message,
                'details': error_details,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.error(f"错误通知已发送: {notification_data}")
            
            return {
                'success': True,
                'project_id': project_id,
                'task_id': task_id,
                'notification': notification_data,
                'message': '错误通知发送成功'
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"错误通知发送失败: {project_id}, {task_id}, 错误: {e}")
        raise


@celery_app.task(bind=True, name='backend.tasks.notification.send_completion_notification')
def send_completion_notification(self, project_id: str, task_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """
    发送完成通知
    
    Args:
        project_id: 项目ID
        task_id: 任务ID
        result: 处理结果
        
    Returns:
        通知结果
    """
    logger.info(f"发送完成通知: {project_id}, {task_id}")
    
    try:
        # 创建数据库会话
        db = SessionLocal()
        
        try:
            # 更新任务状态
            task_repo = TaskRepository(db)
            task = task_repo.get_by_id(task_id)
            if task:
                task.status = TaskStatus.COMPLETED
                task.result = result
                db.commit()
            
            # 发送完成通知
            notification_data = {
                'project_id': project_id,
                'task_id': task_id,
                'type': 'success',
                'message': '处理完成',
                'result': result,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            logger.info(f"完成通知已发送: {notification_data}")
            
            return {
                'success': True,
                'project_id': project_id,
                'task_id': task_id,
                'notification': notification_data,
                'message': '完成通知发送成功'
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"完成通知发送失败: {project_id}, {task_id}, 错误: {e}")
        raise