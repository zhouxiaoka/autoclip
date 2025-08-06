"""
WebSocket API路由
处理WebSocket连接和消息
"""

import json
import logging
from typing import Dict, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse

from backend.core.websocket_manager import manager, WebSocketMessage

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """WebSocket连接端点"""
    await manager.connect(websocket, user_id)
    
    try:
        # 发送连接确认消息
        welcome_message = WebSocketMessage.create_system_notification(
            "connection",
            "连接成功",
            f"用户 {user_id} 已成功连接到WebSocket服务",
            "success"
        )
        await manager.send_personal_message(welcome_message, user_id)
        
        # 处理客户端消息
        while True:
            try:
                # 接收客户端消息
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # 处理不同类型的消息
                await handle_client_message(user_id, message)
                
            except WebSocketDisconnect:
                logger.info(f"用户 {user_id} 断开连接")
                break
            except json.JSONDecodeError:
                logger.error(f"用户 {user_id} 发送的消息格式错误")
                error_message = WebSocketMessage.create_error_notification(
                    "message_format_error",
                    "消息格式错误",
                    {"message": "请发送有效的JSON格式消息"}
                )
                await manager.send_personal_message(error_message, user_id)
            except Exception as e:
                logger.error(f"处理用户 {user_id} 消息时出错: {e}")
                error_message = WebSocketMessage.create_error_notification(
                    "processing_error",
                    "消息处理错误",
                    {"error": str(e)}
                )
                await manager.send_personal_message(error_message, user_id)
    
    except WebSocketDisconnect:
        logger.info(f"用户 {user_id} 断开连接")
    finally:
        manager.disconnect(user_id)

async def handle_client_message(user_id: str, message: Dict[str, Any]):
    """处理客户端消息"""
    message_type = message.get("type")
    
    if message_type == "subscribe":
        # 订阅主题
        topic = message.get("topic")
        if topic:
            manager.subscribe_to_topic(user_id, topic)
            response = WebSocketMessage.create_system_notification(
                "subscription",
                "订阅成功",
                f"已成功订阅主题: {topic}",
                "success"
            )
            await manager.send_personal_message(response, user_id)
    
    elif message_type == "unsubscribe":
        # 取消订阅主题
        topic = message.get("topic")
        if topic:
            manager.unsubscribe_from_topic(user_id, topic)
            response = WebSocketMessage.create_system_notification(
                "unsubscription",
                "取消订阅成功",
                f"已取消订阅主题: {topic}",
                "info"
            )
            await manager.send_personal_message(response, user_id)
    
    elif message_type == "ping":
        # 心跳检测
        response = {
            "type": "pong",
            "timestamp": WebSocketMessage.create_system_notification(
                "ping", "", "", "info"
            )["timestamp"]
        }
        await manager.send_personal_message(response, user_id)
    
    elif message_type == "get_status":
        # 获取连接状态
        status = {
            "type": "status",
            "user_id": user_id,
            "connected": user_id in manager.active_connections,
            "subscriptions": list(manager.user_subscriptions.get(user_id, set())),
            "total_connections": manager.get_connection_count(),
            "timestamp": WebSocketMessage.create_system_notification(
                "status", "", "", "info"
            )["timestamp"]
        }
        await manager.send_personal_message(status, user_id)
    
    else:
        # 未知消息类型
        error_message = WebSocketMessage.create_error_notification(
            "unknown_message_type",
            "未知消息类型",
            {"message_type": message_type, "supported_types": ["subscribe", "unsubscribe", "ping", "get_status"]}
        )
        await manager.send_personal_message(error_message, user_id)

@router.get("/ws/status")
async def get_websocket_status():
    """获取WebSocket服务状态"""
    return {
        "status": "running",
        "total_connections": manager.get_connection_count(),
        "topics": {
            topic: manager.get_topic_subscriber_count(topic)
            for topic in manager.topic_subscribers
        }
    }

@router.post("/ws/broadcast")
async def broadcast_message(message: Dict[str, Any]):
    """广播消息给所有连接的用户"""
    try:
        await manager.broadcast(message)
        return {"status": "success", "message": "消息广播成功"}
    except Exception as e:
        logger.error(f"广播消息失败: {e}")
        raise HTTPException(status_code=500, detail=f"广播消息失败: {e}")

@router.post("/ws/broadcast/{topic}")
async def broadcast_to_topic(topic: str, message: Dict[str, Any]):
    """广播消息给特定主题的订阅者"""
    try:
        await manager.broadcast_to_topic(message, topic)
        return {"status": "success", "message": f"消息已广播给主题 {topic} 的订阅者"}
    except Exception as e:
        logger.error(f"广播消息给主题 {topic} 失败: {e}")
        raise HTTPException(status_code=500, detail=f"广播消息失败: {e}")

@router.post("/ws/send/{user_id}")
async def send_to_user(user_id: str, message: Dict[str, Any]):
    """发送消息给特定用户"""
    try:
        await manager.send_personal_message(message, user_id)
        return {"status": "success", "message": f"消息已发送给用户 {user_id}"}
    except Exception as e:
        logger.error(f"发送消息给用户 {user_id} 失败: {e}")
        raise HTTPException(status_code=500, detail=f"发送消息失败: {e}")