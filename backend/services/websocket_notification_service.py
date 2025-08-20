"""
WebSocket通知服务
提供实时通知功能
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from core.websocket_manager import manager, WebSocketMessage

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
        await WebSocketNotificationService.send_task_update(
            task_id=task_id,
            status="started",
            progress=0,
            message="视频处理已开始"
        )
        
        await WebSocketNotificationService.send_project_update(
            project_id=project_id,
            status="processing",
            progress=0,
            message="项目处理已开始"
        )
    
    @staticmethod
    async def send_processing_progress(project_id: str, task_id: str, progress: int, step: str):
        """发送处理进度通知"""
        await WebSocketNotificationService.send_task_update(
            task_id=task_id,
            status="processing",
            progress=progress,
            message=f"正在执行: {step}"
        )
        
        await WebSocketNotificationService.send_project_update(
            project_id=project_id,
            status="processing",
            progress=progress,
            message=f"处理进度: {progress}% - {step}"
        )
    
    @staticmethod
    async def send_processing_complete(project_id: str, task_id: str, result: Dict[str, Any]):
        """发送处理完成通知"""
        await WebSocketNotificationService.send_task_update(
            task_id=task_id,
            status="completed",
            progress=100,
            message="视频处理已完成"
        )
        
        await WebSocketNotificationService.send_project_update(
            project_id=project_id,
            status="completed",
            progress=100,
            message="项目处理已完成"
        )
        
        await WebSocketNotificationService.send_system_notification(
            "processing_complete",
            "处理完成",
            f"项目 {project_id} 的视频处理已完成",
            "success"
        )
    
    @staticmethod
    async def send_processing_error(project_id: str, task_id: str, error: str):
        """发送处理错误通知"""
        await WebSocketNotificationService.send_task_update(
            task_id=task_id,
            status="failed",
            error=error
        )
        
        await WebSocketNotificationService.send_project_update(
            project_id=project_id,
            status="failed",
            message=f"处理失败: {error}"
        )
        
        await WebSocketNotificationService.send_error_notification(
            "processing_error",
            f"项目 {project_id} 处理失败",
            {"project_id": project_id, "task_id": task_id, "error": error}
        )
    
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