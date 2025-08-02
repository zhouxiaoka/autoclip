#!/usr/bin/env python3
"""
测试WebSocket通知的防重复和节流功能
"""

import asyncio
import json
import websockets
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_notification_throttling():
    """测试通知防重复和节流功能"""
    
    uri = "ws://localhost:8000/api/v1/ws/test-user"
    
    try:
        async with websockets.connect(uri) as websocket:
            logger.info("✅ 已连接到WebSocket服务器")
            
            # 1. 发送连接成功消息
            welcome_message = {
                "type": "system_notification",
                "notification_type": "connection",
                "title": "连接成功",
                "message": "测试用户已连接",
                "level": "success",
                "timestamp": datetime.utcnow().isoformat()
            }
            await websocket.send(json.dumps(welcome_message))
            logger.info("📢 发送连接成功通知")
            
            # 2. 快速发送多个相同的任务进度消息（应该被节流）
            for i in range(5):
                progress_message = {
                    "type": "task_update",
                    "task_id": "test-task-001",
                    "status": "processing",
                    "progress": 20,
                    "message": "正在处理...",
                    "timestamp": datetime.utcnow().isoformat()
                }
                await websocket.send(json.dumps(progress_message))
                logger.info(f"📊 发送任务进度消息 {i+1}/5")
                await asyncio.sleep(0.5)  # 快速发送
            
            # 3. 发送任务完成消息（应该显示通知）
            complete_message = {
                "type": "task_update",
                "task_id": "test-task-001",
                "status": "completed",
                "progress": 100,
                "message": "任务已完成",
                "timestamp": datetime.utcnow().isoformat()
            }
            await websocket.send(json.dumps(complete_message))
            logger.info("✅ 发送任务完成消息")
            
            # 4. 再次发送相同的完成消息（应该被防重复）
            await websocket.send(json.dumps(complete_message))
            logger.info("🔄 重复发送任务完成消息（应该被忽略）")
            
            # 5. 等待一段时间后发送另一个完成消息（应该被节流）
            await asyncio.sleep(1)
            another_complete = {
                "type": "task_update",
                "task_id": "test-task-002",
                "status": "completed",
                "progress": 100,
                "message": "另一个任务已完成",
                "timestamp": datetime.utcnow().isoformat()
            }
            await websocket.send(json.dumps(another_complete))
            logger.info("✅ 发送另一个任务完成消息")
            
            # 6. 发送错误消息
            error_message = {
                "type": "error_notification",
                "error_type": "test_error",
                "error_message": "这是一个测试错误",
                "details": {"test": True},
                "timestamp": datetime.utcnow().isoformat()
            }
            await websocket.send(json.dumps(error_message))
            logger.info("❌ 发送错误消息")
            
            logger.info("🎉 测试完成！")
            logger.info("💡 前端应该只显示少量重要通知，而不是疯狂弹窗")
            
    except Exception as e:
        logger.error(f"测试失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_notification_throttling()) 