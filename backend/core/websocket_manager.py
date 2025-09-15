"""
WebSocket连接管理器
管理WebSocket连接和消息广播
"""

import json
import logging
import asyncio
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime

logger = logging.getLogger(__name__)

class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        # 存储所有活跃连接
        self.active_connections: Dict[str, WebSocket] = {}
        # 存储用户订阅的主题
        self.user_subscriptions: Dict[str, Set[str]] = {}
        # 存储主题订阅者
        self.topic_subscribers: Dict[str, Set[str]] = {}
        # 发送队列和任务
        self.send_queues: Dict[str, asyncio.Queue] = {}
        self.send_tasks: Dict[str, asyncio.Task] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """建立WebSocket连接"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.user_subscriptions[user_id] = set()
        
        # 创建发送队列和任务
        self.send_queues[user_id] = asyncio.Queue()
        self.send_tasks[user_id] = asyncio.create_task(
            self._send_worker(user_id)
        )
        
        logger.info(f"用户 {user_id} 已连接")
    
    async def disconnect(self, user_id: str):
        """断开WebSocket连接"""
        # 停止发送任务
        if user_id in self.send_tasks:
            task = self.send_tasks[user_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            del self.send_tasks[user_id]
        
        # 清理队列
        if user_id in self.send_queues:
            del self.send_queues[user_id]
        
        # 清理连接
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if user_id in self.user_subscriptions:
            del self.user_subscriptions[user_id]
        
        # 从所有主题中移除用户
        for topic in self.topic_subscribers:
            self.topic_subscribers[topic].discard(user_id)
        
        logger.info(f"用户 {user_id} 已断开连接")
    
    async def _send_worker(self, user_id: str):
        """发送工作器 - 从队列中取消息并发送"""
        try:
            while True:
                message = await self.send_queues[user_id].get()
                if message is None:  # 停止信号
                    break
                
                if user_id in self.active_connections:
                    try:
                        await self.active_connections[user_id].send_text(json.dumps(message))
                    except Exception as e:
                        logger.error(f"发送消息给用户 {user_id} 失败: {e}")
                        break
                
                self.send_queues[user_id].task_done()
        except asyncio.CancelledError:
            logger.debug(f"用户 {user_id} 发送工作器已取消")
        except Exception as e:
            logger.error(f"用户 {user_id} 发送工作器异常: {e}")

    async def send_personal_message(self, message: Dict[str, Any], user_id: str):
        """发送个人消息 - 队列化发送"""
        if user_id in self.send_queues:
            try:
                await self.send_queues[user_id].put(message)
            except Exception as e:
                logger.error(f"将消息加入队列失败 {user_id}: {e}")
                await self.disconnect(user_id)
    
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有连接"""
        disconnected_users = []
        for user_id in list(self.active_connections.keys()):
            try:
                await self.send_personal_message(message, user_id)
            except Exception as e:
                logger.error(f"广播消息给用户 {user_id} 失败: {e}")
                disconnected_users.append(user_id)
        
        # 清理断开的连接
        for user_id in disconnected_users:
            self.disconnect(user_id)
    
    async def broadcast_to_topic(self, message: Dict[str, Any], topic: str):
        """广播消息给特定主题的订阅者"""
        if topic not in self.topic_subscribers:
            return
        
        disconnected_users = []
        for user_id in list(self.topic_subscribers[topic]):
            if user_id in self.active_connections:
                try:
                    await self.send_personal_message(message, user_id)
                except Exception as e:
                    logger.error(f"发送主题消息给用户 {user_id} 失败: {e}")
                    disconnected_users.append(user_id)
        
        # 清理断开的连接
        for user_id in disconnected_users:
            self.disconnect(user_id)
    
    def subscribe_to_topic(self, user_id: str, topic: str):
        """用户订阅主题"""
        if user_id not in self.user_subscriptions:
            self.user_subscriptions[user_id] = set()
        
        self.user_subscriptions[user_id].add(topic)
        
        if topic not in self.topic_subscribers:
            self.topic_subscribers[topic] = set()
        
        self.topic_subscribers[topic].add(user_id)
        logger.info(f"用户 {user_id} 订阅主题 {topic}")
    
    def unsubscribe_from_topic(self, user_id: str, topic: str):
        """用户取消订阅主题"""
        if user_id in self.user_subscriptions:
            self.user_subscriptions[user_id].discard(topic)
        
        if topic in self.topic_subscribers:
            self.topic_subscribers[topic].discard(user_id)
        
        logger.info(f"用户 {user_id} 取消订阅主题 {topic}")
    
    def get_connection_count(self) -> int:
        """获取当前连接数"""
        return len(self.active_connections)
    
    def get_topic_subscriber_count(self, topic: str) -> int:
        """获取主题订阅者数量"""
        return len(self.topic_subscribers.get(topic, set()))

# 全局连接管理器实例
manager = ConnectionManager()

class WebSocketMessage:
    """WebSocket消息工具类"""
    
    @staticmethod
    def create_task_update(task_id: str, status: str, progress: Optional[int] = None, 
                          message: Optional[str] = None, error: Optional[str] = None) -> Dict[str, Any]:
        """创建任务更新消息"""
        return {
            "type": "task_update",
            "task_id": task_id,
            "status": status,
            "progress": progress,
            "message": message,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_system_notification(notification_type: str, title: str, message: str, 
                                 level: str = "info") -> Dict[str, Any]:
        """创建系统通知消息"""
        return {
            "type": "system_notification",
            "notification_type": notification_type,
            "title": title,
            "message": message,
            "level": level,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_project_update(project_id: str, status: str, progress: Optional[int] = None,
                            message: Optional[str] = None) -> Dict[str, Any]:
        """创建项目更新消息"""
        return {
            "type": "project_update",
            "project_id": project_id,
            "status": status,
            "progress": progress,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    @staticmethod
    def create_error_notification(error_type: str, error_message: str, 
                                details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """创建错误通知消息"""
        return {
            "type": "error_notification",
            "error_type": error_type,
            "error_message": error_message,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        } 