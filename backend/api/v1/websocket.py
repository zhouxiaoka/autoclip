"""
WebSocket API路由
"""

import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...core.websocket_manager import manager, WebSocketMessage
from ...services.websocket_notification_service import WebSocketNotificationService
from ...services.websocket_gateway_service import websocket_gateway_service

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
        
        # 处理客户端消息 - 保持保活循环
        while True:
            try:
                # 接收客户端消息
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # 处理不同类型的消息
                await handle_client_message(user_id, message)
                
            except WebSocketDisconnect:
                logger.info(f"用户 {user_id} 主动断开连接")
                break
            except json.JSONDecodeError:
                logger.error(f"用户 {user_id} 发送的消息格式错误")
                try:
                    error_message = WebSocketMessage.create_error_notification(
                        "message_format_error",
                        "消息格式错误",
                        {"message": "请发送有效的JSON格式消息"}
                    )
                    await manager.send_personal_message(error_message, user_id)
                except:
                    # 如果发送失败，说明连接已断开，直接退出
                    break
            except Exception as e:
                logger.error(f"处理用户 {user_id} 消息时出错: {e}")
                try:
                    error_message = WebSocketMessage.create_error_notification(
                        "processing_error",
                        "消息处理错误",
                        {"error": str(e)}
                    )
                    await manager.send_personal_message(error_message, user_id)
                except:
                    # 如果发送失败，说明连接已断开，直接退出
                    break
    
    except WebSocketDisconnect:
        logger.info(f"用户 {user_id} 断开连接")
    except Exception as e:
        logger.error(f"WebSocket连接异常: {e}")
    finally:
        # 按顺序清理：先取消订阅，再断开连接
        try:
            await websocket_gateway_service.unsubscribe_user_from_all_tasks(user_id)
        except Exception as e:
            logger.error(f"清理用户订阅失败: {e}")
        
        try:
            await manager.disconnect(user_id)
        except Exception as e:
            logger.error(f"断开用户连接失败: {e}")

async def handle_client_message(user_id: str, message: Dict[str, Any]):
    """处理客户端消息"""
    message_type = message.get("type")
    
    if message_type == "sync_subscriptions":
        # 新的幂等订阅方式
        project_ids = message.get("project_ids", [])
        # 直接传入项目ID，让网关服务内部进行规范化
        channels = set(project_ids)
        
        stats = await websocket_gateway_service.sync_user_subscriptions(user_id, channels)
        
        response = WebSocketMessage.create_system_notification(
            "subscription_sync",
            "订阅同步完成",
            f"新增 {stats['added']} / 移除 {stats['removed']} / 未变 {stats['unchanged']}",
            "success"
        )
        await manager.send_personal_message(response, user_id)
        
    elif message_type == "subscribe":
        # 订阅主题（兼容旧版本）
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
    
    elif message_type == "subscribe_task":
        # 订阅任务进度（新版本）
        task_id = message.get("task_id")
        if task_id:
            success = await websocket_gateway_service.subscribe_user_to_task(user_id, task_id)
            if success:
                response = WebSocketMessage.create_system_notification(
                    "task_subscription",
                    "任务订阅成功",
                    f"已成功订阅任务 {task_id} 的进度更新",
                    "success"
                )
            else:
                response = WebSocketMessage.create_error_notification(
                    "task_subscription_failed",
                    "任务订阅失败",
                    {"task_id": task_id}
                )
            await manager.send_personal_message(response, user_id)
    
    elif message_type == "unsubscribe":
        # 取消订阅主题（兼容旧版本）
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
    
    elif message_type == "unsubscribe_task":
        # 取消订阅任务进度（新版本）
        task_id = message.get("task_id")
        if task_id:
            success = await websocket_gateway_service.unsubscribe_user_from_task(user_id, task_id)
            if success:
                response = WebSocketMessage.create_system_notification(
                    "task_unsubscription",
                    "任务取消订阅成功",
                    f"已取消订阅任务 {task_id} 的进度更新",
                    "info"
                )
            else:
                response = WebSocketMessage.create_error_notification(
                    "task_unsubscription_failed",
                    "任务取消订阅失败",
                    {"task_id": task_id}
                )
            await manager.send_personal_message(response, user_id)
    
    elif message_type == "subscribe_many":
        # 批量订阅任务
        task_ids = message.get("channels", [])
        if task_ids:
            results = await websocket_gateway_service.subscribe_user_to_many_tasks(user_id, task_ids)
            response = WebSocketMessage.create_system_notification(
                "batch_subscription",
                "批量订阅完成",
                f"新增订阅: {len(results['added'])}, 已存在: {len(results['already_subscribed'])}",
                "success"
            )
            await manager.send_personal_message(response, user_id)
    
    elif message_type == "unsubscribe_many":
        # 批量取消订阅任务
        task_ids = message.get("channels", [])
        if task_ids:
            results = await websocket_gateway_service.unsubscribe_user_from_many_tasks(user_id, task_ids)
            response = WebSocketMessage.create_system_notification(
                "batch_unsubscription",
                "批量取消订阅完成",
                f"移除订阅: {len(results['removed'])}, 未订阅: {len(results['not_subscribed'])}",
                "success"
            )
            await manager.send_personal_message(response, user_id)
    
    elif message_type == "sync_subscriptions":
        # 同步订阅集对齐
        task_ids = message.get("channels", [])
        results = await websocket_gateway_service.sync_user_subscriptions(user_id, task_ids)
        response = WebSocketMessage.create_system_notification(
            "subscription_sync",
            "订阅集同步完成",
            f"新增: {len(results['added'])}, 移除: {len(results['removed'])}, 未变: {len(results['unchanged'])}",
            "success"
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
        logger.debug(f"用户 {user_id} 心跳检测 - 已回复pong")
    
    elif message_type == "get_status":
        # 获取连接状态
        gateway_status = await websocket_gateway_service.get_subscription_status(user_id)
        status = {
            "type": "status",
            "user_id": user_id,
            "connected": user_id in manager.active_connections,
            "subscriptions": list(manager.user_subscriptions.get(user_id, set())),
            "task_subscriptions": gateway_status["subscribed_tasks"],
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
            {"message_type": message_type, "supported_types": ["subscribe", "subscribe_task", "unsubscribe", "unsubscribe_task", "ping", "get_status"]}
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