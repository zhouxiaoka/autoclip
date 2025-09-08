"""
WebSocket通知服务
提供实时通知功能
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from ..core.websocket_manager import manager, WebSocketMessage

logger = logging.getLogger(__name__)

class WebSocketNotificationService:
    """WebSocket通知服务"""
    
    @staticmethod
    async def send_task_update(task_id: str, status: str, progress: Optional[int] = None,
                              message: Optional[str] = None, error: Optional[str] = None):
        """发送任务更新通知"""
        try:
            notification = WebSocketMessage.create_task_update(
                task_id=task_id,
                status=status,
                progress=progress,
                message=message,
                error=error
            )
            
            # 广播给所有连接的用户
            await manager.broadcast(notification)
            
            # 同时发送给特定任务主题的订阅者
            topic = f"task_{task_id}"
            await manager.broadcast_to_topic(notification, topic)
            
            logger.info(f"任务更新通知已发送: {task_id} - {status}")
            
        except Exception as e:
            logger.error(f"发送任务更新通知失败: {e}")
    
    @staticmethod
    async def send_project_update(project_id: str, status: str, progress: Optional[int] = None,
                                message: Optional[str] = None):
        """发送项目更新通知"""
        try:
            notification = WebSocketMessage.create_project_update(
                project_id=project_id,
                status=status,
                progress=progress,
                message=message
            )
            
            # 广播给所有连接的用户
            await manager.broadcast(notification)
            
            # 同时发送给特定项目主题的订阅者
            topic = f"project_{project_id}"
            await manager.broadcast_to_topic(notification, topic)
            
            logger.info(f"项目更新通知已发送: {project_id} - {status}")
            
        except Exception as e:
            logger.error(f"发送项目更新通知失败: {e}")
    
    @staticmethod
    async def send_system_notification(notification_type: str, title: str, message: str,
                                     level: str = "info"):
        """发送系统通知"""
        try:
            notification = WebSocketMessage.create_system_notification(
                notification_type=notification_type,
                title=title,
                message=message,
                level=level
            )
            
            # 广播给所有连接的用户
            await manager.broadcast(notification)
            
            logger.info(f"系统通知已发送: {title} - {message}")
            
        except Exception as e:
            logger.error(f"发送系统通知失败: {e}")
    
    @staticmethod
    async def send_error_notification(error_type: str, error_message: str,
                                    details: Optional[Dict[str, Any]] = None):
        """发送错误通知"""
        try:
            notification = WebSocketMessage.create_error_notification(
                error_type=error_type,
                error_message=error_message,
                details=details
            )
            
            # 广播给所有连接的用户
            await manager.broadcast(notification)
            
            logger.error(f"错误通知已发送: {error_type} - {error_message}")
            
        except Exception as e:
            logger.error(f"发送错误通知失败: {e}")
    
    @staticmethod
    async def send_processing_start(project_id: str, task_id: str):
        """发送处理开始通知"""
        try:
            notification = WebSocketMessage.create_task_update(
                task_id=task_id,
                status="running",
                progress=0,
                message="开始处理项目"
            )
            
            # 广播给所有连接的用户
            await manager.broadcast(notification)
            
            # 同时发送给特定项目主题的订阅者
            topic = f"project_{project_id}"
            await manager.broadcast_to_topic(notification, topic)
            
            logger.info(f"处理开始通知已发送: {project_id} - {task_id}")
            
        except Exception as e:
            logger.error(f"发送处理开始通知失败: {e}")
    
    @staticmethod
    async def send_processing_progress(project_id: str, task_id: str, progress: int, message: str, 
                                     current_step: int = 0, total_steps: int = 6, step_name: str = ""):
        """发送处理进度通知"""
        try:
            notification = WebSocketMessage.create_task_update(
                task_id=task_id,
                status="running",
                progress=progress,
                message=message
            )
            
            # 广播给所有连接的用户
            await manager.broadcast(notification)
            
            # 同时发送给特定项目主题的订阅者
            topic = f"project_{project_id}"
            await manager.broadcast_to_topic(notification, topic)
            
            logger.info(f"处理进度通知已发送: {project_id} - {task_id} - {progress}%")
            
        except Exception as e:
            logger.error(f"发送处理进度通知失败: {e}")
    
    @staticmethod
    async def send_processing_complete(project_id: str, task_id: str, result: dict):
        """发送处理完成通知"""
        try:
            notification = WebSocketMessage.create_task_update(
                task_id=task_id,
                status="completed",
                progress=100,
                message="项目处理完成"
            )
            
            # 广播给所有连接的用户
            await manager.broadcast(notification)
            
            # 同时发送给特定项目主题的订阅者
            topic = f"project_{project_id}"
            await manager.broadcast_to_topic(notification, topic)
            
            logger.info(f"处理完成通知已发送: {project_id} - {task_id}")
            
        except Exception as e:
            logger.error(f"发送处理完成通知失败: {e}")
    
    @staticmethod
    async def send_processing_error(project_id: str, task_id: str, error_message: str):
        """发送处理错误通知"""
        try:
            notification = WebSocketMessage.create_task_update(
                task_id=task_id,
                status="failed",
                progress=0,
                error=error_message
            )
            
            # 广播给所有连接的用户
            await manager.broadcast(notification)
            
            # 同时发送给特定项目主题的订阅者
            topic = f"project_{project_id}"
            await manager.broadcast_to_topic(notification, topic)
            
            logger.info(f"处理错误通知已发送: {project_id} - {task_id} - {error_message}")
            
        except Exception as e:
            logger.error(f"发送处理错误通知失败: {e}")
    
    @staticmethod
    async def send_processing_started(project_id: str, message: str = "开始视频处理流程"):
        """发送处理开始通知（别名方法）"""
        await WebSocketNotificationService.send_project_update(
            project_id=project_id,
            status="processing",
            progress=0,
            message=message
        )

# 全局通知服务实例
notification_service = WebSocketNotificationService()