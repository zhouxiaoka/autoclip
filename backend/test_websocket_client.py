#!/usr/bin/env python3
"""
WebSocket客户端测试脚本
用于测试WebSocket连接和消息接收
"""

import asyncio
import websockets
import json
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebSocketClient:
    """WebSocket客户端"""
    
    def __init__(self, user_id: str, uri: str = "ws://localhost:8000/api/v1/ws/"):
        self.user_id = user_id
        self.uri = f"{uri}{user_id}"
        self.websocket = None
        self.connected = False
    
    async def connect(self):
        """连接到WebSocket服务器"""
        try:
            self.websocket = await websockets.connect(self.uri)
            self.connected = True
            logger.info(f"用户 {self.user_id} 已连接到WebSocket服务器")
            return True
        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            logger.info(f"用户 {self.user_id} 已断开连接")
    
    async def send_message(self, message: dict):
        """发送消息"""
        if not self.connected:
            logger.error("未连接到服务器")
            return False
        
        try:
            await self.websocket.send(json.dumps(message))
            logger.info(f"发送消息: {message}")
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False
    
    async def subscribe_to_topic(self, topic: str):
        """订阅主题"""
        message = {
            "type": "subscribe",
            "topic": topic
        }
        return await self.send_message(message)
    
    async def unsubscribe_from_topic(self, topic: str):
        """取消订阅主题"""
        message = {
            "type": "unsubscribe",
            "topic": topic
        }
        return await self.send_message(message)
    
    async def ping(self):
        """发送心跳"""
        message = {
            "type": "ping"
        }
        return await self.send_message(message)
    
    async def get_status(self):
        """获取连接状态"""
        message = {
            "type": "get_status"
        }
        return await self.send_message(message)
    
    async def listen_for_messages(self, duration: int = 30):
        """监听消息"""
        if not self.connected:
            logger.error("未连接到服务器")
            return
        
        logger.info(f"开始监听消息，持续 {duration} 秒...")
        start_time = datetime.now()
        
        try:
            while self.connected:
                try:
                    # 设置超时
                    message = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=1.0
                    )
                    
                    # 解析消息
                    data = json.loads(message)
                    await self.handle_message(data)
                    
                    # 检查是否超时
                    if (datetime.now() - start_time).seconds >= duration:
                        logger.info("监听时间已到，停止监听")
                        break
                        
                except asyncio.TimeoutError:
                    # 超时继续监听
                    continue
                except Exception as e:
                    logger.error(f"接收消息失败: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"监听消息时出错: {e}")
    
    async def handle_message(self, data: dict):
        """处理接收到的消息"""
        message_type = data.get("type", "unknown")
        timestamp = data.get("timestamp", "")
        
        print(f"\n📨 收到消息 [{timestamp}]:")
        print(f"   类型: {message_type}")
        
        if message_type == "task_update":
            task_id = data.get("task_id", "")
            status = data.get("status", "")
            progress = data.get("progress", 0)
            message = data.get("message", "")
            print(f"   📋 任务: {task_id}")
            print(f"   📈 状态: {status}")
            print(f"   📊 进度: {progress}%")
            print(f"   💬 消息: {message}")
            
        elif message_type == "project_update":
            project_id = data.get("project_id", "")
            status = data.get("status", "")
            progress = data.get("progress", 0)
            message = data.get("message", "")
            print(f"   📁 项目: {project_id}")
            print(f"   📈 状态: {status}")
            print(f"   📊 进度: {progress}%")
            print(f"   💬 消息: {message}")
            
        elif message_type == "system_notification":
            title = data.get("title", "")
            message = data.get("message", "")
            level = data.get("level", "info")
            print(f"   📢 标题: {title}")
            print(f"   💬 消息: {message}")
            print(f"   🎯 级别: {level}")
            
        elif message_type == "error_notification":
            error_type = data.get("error_type", "")
            error_message = data.get("error_message", "")
            print(f"   ⚠️  错误类型: {error_type}")
            print(f"   💬 错误消息: {error_message}")
            
        elif message_type == "pong":
            print(f"   🏓 心跳响应")
            
        elif message_type == "status":
            connected = data.get("connected", False)
            subscriptions = data.get("subscriptions", [])
            total_connections = data.get("total_connections", 0)
            print(f"   🔗 连接状态: {'已连接' if connected else '未连接'}")
            print(f"   📋 订阅主题: {subscriptions}")
            print(f"   👥 总连接数: {total_connections}")
            
        else:
            print(f"   📄 原始数据: {data}")

async def demo_websocket_client():
    """演示WebSocket客户端功能"""
    print("🎯 WebSocket客户端演示")
    print("=" * 50)
    
    # 创建客户端
    client = WebSocketClient("demo-user-001")
    
    try:
        # 1. 连接到服务器
        print("1. 🔗 连接到WebSocket服务器...")
        if not await client.connect():
            print("   ❌ 连接失败")
            return False
        print("   ✅ 连接成功")
        
        # 2. 获取连接状态
        print("\n2. 📊 获取连接状态...")
        await client.get_status()
        await asyncio.sleep(1)
        
        # 3. 订阅主题
        print("\n3. 📋 订阅主题...")
        topics = ["task_demo-task-001", "project_demo-project-001", "system"]
        for topic in topics:
            await client.subscribe_to_topic(topic)
            await asyncio.sleep(0.5)
        
        # 4. 发送心跳
        print("\n4. 🏓 发送心跳...")
        await client.ping()
        await asyncio.sleep(1)
        
        # 5. 监听消息
        print("\n5. 📨 开始监听消息...")
        print("   💡 提示：现在可以运行 demo_websocket.py 来发送测试消息")
        print("   ⏰ 监听将持续30秒...")
        
        # 创建监听任务
        listen_task = asyncio.create_task(client.listen_for_messages(30))
        
        # 等待监听完成
        await listen_task
        
        # 6. 取消订阅
        print("\n6. 📋 取消订阅...")
        for topic in topics:
            await client.unsubscribe_from_topic(topic)
            await asyncio.sleep(0.5)
        
        # 7. 断开连接
        print("\n7. 🔌 断开连接...")
        await client.disconnect()
        
        print("\n🎉 WebSocket客户端演示完成!")
        return True
        
    except Exception as e:
        print(f"❌ 演示失败: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(demo_websocket_client())
    exit(0 if success else 1) 