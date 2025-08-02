#!/usr/bin/env python3
"""
前后端联调测试脚本
测试WebSocket连接和消息发送
"""

import os
import sys
import asyncio
import json
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.websocket_notification_service import notification_service

async def test_frontend_integration():
    """测试前后端联调"""
    print("🎯 前后端联调测试")
    print("=" * 50)
    
    try:
        # 1. 发送连接成功通知
        print("1. 📢 发送连接成功通知...")
        await notification_service.send_system_notification(
            "frontend_connected",
            "前端连接成功",
            "前端已成功连接到WebSocket服务",
            "success"
        )
        print("   ✅ 连接通知已发送")
        
        # 2. 模拟任务开始
        print("\n2. 📋 模拟任务开始...")
        await notification_service.send_task_update(
            task_id="test-task-001",
            status="started",
            progress=0,
            message="测试任务已开始"
        )
        print("   ✅ 任务开始通知已发送")
        
        # 3. 模拟任务进度
        print("\n3. 📈 模拟任务进度...")
        for i in range(1, 6):
            progress = i * 20
            await notification_service.send_task_update(
                task_id="test-task-001",
                status="processing",
                progress=progress,
                message=f"测试任务进度: {progress}%"
            )
            print(f"   📊 进度 {progress}% 已发送")
            await asyncio.sleep(2)  # 等待2秒
        
        # 4. 模拟任务完成
        print("\n4. ✅ 模拟任务完成...")
        await notification_service.send_task_update(
            task_id="test-task-001",
            status="completed",
            progress=100,
            message="测试任务已完成"
        )
        print("   ✅ 任务完成通知已发送")
        
        # 5. 发送系统通知
        print("\n5. 📢 发送系统通知...")
        await notification_service.send_system_notification(
            "test_complete",
            "测试完成",
            "前后端联调测试已完成",
            "success"
        )
        print("   ✅ 系统通知已发送")
        
        print("\n🎉 前后端联调测试完成!")
        print("💡 提示：")
        print("   - 前端应该能看到实时通知")
        print("   - 任务进度应该实时更新")
        print("   - WebSocket连接状态应该正常")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_frontend_integration())
    exit(0 if success else 1) 