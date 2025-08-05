"""WebSocket API路由
处理WebSocket连接和实时通信
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from typing import Optional

from core.websocket_manager import manager
from core.database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])

@router.websocket("/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket连接端点
    
    Args:
        websocket: WebSocket连接对象
        user_id: 用户ID
    """
    await manager.connect(websocket, user_id)
    
    try:
        while True:
            # 接收客户端消息
            data = await websocket.receive_json()
            
            # 处理不同类型的消息
            message_type = data.get("type")
            
            if message_type == "subscribe":
                # 订阅主题
                topic = data.get("topic")
                if topic:
                    manager.subscribe_to_topic(user_id, topic)
                    await websocket.send_json({
                        "type": "subscription_confirmed",
                        "topic": topic,
                        "message": f"已订阅主题: {topic}"
                    })
                    
            elif message_type == "unsubscribe":
                # 取消订阅主题
                topic = data.get("topic")
                if topic:
                    manager.unsubscribe_from_topic(user_id, topic)
                    await websocket.send_json({
                        "type": "unsubscription_confirmed",
                        "topic": topic,
                        "message": f"已取消订阅主题: {topic}"
                    })
                    
            elif message_type == "ping":
                # 心跳检测
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": data.get("timestamp")
                })
                
            elif message_type == "get_status":
                # 获取连接状态
                await websocket.send_json({
                    "type": "status",
                    "user_id": user_id,
                    "connection_count": manager.get_connection_count(),
                    "subscribed_topics": list(manager.user_subscriptions.get(user_id, set()))
                })
                
            else:
                logger.warning(f"未知消息类型: {message_type}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"未知消息类型: {message_type}"
                })
                
    except WebSocketDisconnect:
        logger.info(f"用户 {user_id} 断开WebSocket连接")
        manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket连接错误: {str(e)}")
        manager.disconnect(user_id)

@router.get("/status")
async def get_websocket_status():
    """获取WebSocket服务状态"""
    return {
        "active_connections": manager.get_connection_count(),
        "topics": {
            topic: manager.get_topic_subscriber_count(topic)
            for topic in manager.topic_subscribers.keys()
        }
    }

@router.post("/broadcast")
async def broadcast_message(message: dict):
    """广播消息到所有连接
    
    Args:
        message: 要广播的消息
    """
    try:
        await manager.broadcast(message)
        return {
            "success": True,
            "message": "消息已广播",
            "recipients": manager.get_connection_count()
        }
    except Exception as e:
        logger.error(f"广播消息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"广播失败: {str(e)}")

@router.post("/broadcast/{topic}")
async def broadcast_to_topic(topic: str, message: dict):
    """广播消息到特定主题
    
    Args:
        topic: 主题名称
        message: 要广播的消息
    """
    try:
        await manager.broadcast_to_topic(message, topic)
        return {
            "success": True,
            "message": f"消息已广播到主题: {topic}",
            "recipients": manager.get_topic_subscriber_count(topic)
        }
    except Exception as e:
        logger.error(f"广播消息到主题失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"广播失败: {str(e)}")

@router.post("/send/{user_id}")
async def send_personal_message(user_id: str, message: dict):
    """发送个人消息
    
    Args:
        user_id: 目标用户ID
        message: 要发送的消息
    """
    try:
        await manager.send_personal_message(message, user_id)
        return {
            "success": True,
            "message": f"消息已发送给用户: {user_id}"
        }
    except Exception as e:
        logger.error(f"发送个人消息失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"发送失败: {str(e)}")