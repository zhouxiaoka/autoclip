#!/usr/bin/env python3
"""
WebSocket实时通知演示
展示WebSocket连接和实时通知功能
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

from core.celery_app import celery_app
from tasks.processing import process_video_pipeline, process_single_step
from services.websocket_notification_service import notification_service

def demo_websocket_notifications():
    """演示WebSocket实时通知功能"""
    print("🎯 AutoClip WebSocket 实时通知演示")
    print("=" * 50)
    
    # 设置测试环境变量
    os.environ['DASHSCOPE_API_KEY'] = 'test_api_key'
    
    try:
        # 1. 演示系统通知
        print("1. 📢 系统通知演示")
        print("   发送系统通知...")
        
        async def send_system_notifications():
            await notification_service.send_system_notification(
                "demo_start",
                "演示开始",
                "WebSocket实时通知演示已开始",
                "info"
            )
            
            await notification_service.send_system_notification(
                "demo_progress",
                "演示进度",
                "正在演示实时通知功能",
                "success"
            )
        
        asyncio.run(send_system_notifications())
        print("   ✅ 系统通知已发送")
        
        # 2. 演示任务更新通知
        print("\n2. 📈 任务更新通知演示")
        print("   发送任务更新通知...")
        
        async def send_task_updates():
            # 模拟任务开始
            await notification_service.send_task_update(
                task_id="demo-task-001",
                status="started",
                progress=0,
                message="演示任务已开始"
            )
            
            # 模拟任务进度
            for i in range(1, 6):
                progress = i * 20
                await notification_service.send_task_update(
                    task_id="demo-task-001",
                    status="processing",
                    progress=progress,
                    message=f"演示任务进度: {progress}%"
                )
                await asyncio.sleep(1)  # 模拟处理时间
            
            # 模拟任务完成
            await notification_service.send_task_update(
                task_id="demo-task-001",
                status="completed",
                progress=100,
                message="演示任务已完成"
            )
        
        asyncio.run(send_task_updates())
        print("   ✅ 任务更新通知已发送")
        
        # 3. 演示项目更新通知
        print("\n3. 📋 项目更新通知演示")
        print("   发送项目更新通知...")
        
        async def send_project_updates():
            project_id = "demo-project-001"
            
            # 模拟项目开始
            await notification_service.send_project_update(
                project_id=project_id,
                status="processing",
                progress=0,
                message="演示项目已开始处理"
            )
            
            # 模拟项目进度
            for i in range(1, 6):
                progress = i * 20
                await notification_service.send_project_update(
                    project_id=project_id,
                    status="processing",
                    progress=progress,
                    message=f"演示项目进度: {progress}%"
                )
                await asyncio.sleep(1)  # 模拟处理时间
            
            # 模拟项目完成
            await notification_service.send_project_update(
                project_id=project_id,
                status="completed",
                progress=100,
                message="演示项目已完成"
            )
        
        asyncio.run(send_project_updates())
        print("   ✅ 项目更新通知已发送")
        
        # 4. 演示错误通知
        print("\n4. ⚠️  错误通知演示")
        print("   发送错误通知...")
        
        async def send_error_notifications():
            await notification_service.send_error_notification(
                "demo_error",
                "演示错误通知",
                {"error_code": "DEMO_001", "details": "这是一个演示错误"}
            )
            
            await notification_service.send_error_notification(
                "processing_error",
                "处理错误",
                {"project_id": "demo-project-001", "step": "outline", "error": "大纲生成失败"}
            )
        
        asyncio.run(send_error_notifications())
        print("   ✅ 错误通知已发送")
        
        # 5. 演示Celery任务集成
        print("\n5. 🔄 Celery任务集成演示")
        print("   提交带WebSocket通知的Celery任务...")
        
        # 模拟配置
        config = {
            "project_id": "demo-celery-project",
            "video_path": "demo_video.mp4",
            "srt_path": "demo_subtitle.srt",
            "output_dir": "output",
            "llm_config": {
                "api_key": "test_api_key",
                "model": "qwen-turbo"
            }
        }
        
        # 提交任务（不等待结果）
        task = process_single_step.delay("demo-celery-project", "outline", config)
        print(f"   🚀 Celery任务已提交，ID: {task.id}")
        print(f"   📈 任务状态: {task.status}")
        
        # 6. 演示完成
        print("\n6. 🎉 演示完成")
        print("   ✅ WebSocket实时通知功能演示完成")
        print("   💡 提示：")
        print("      - 前端可以通过WebSocket连接接收实时通知")
        print("      - 支持任务进度、项目状态、系统通知等")
        print("      - Celery任务会自动发送WebSocket通知")
        print("      - 可以订阅特定主题接收定向通知")
        
        return True
        
    except Exception as e:
        print(f"❌ 演示失败: {e}")
        return False

if __name__ == "__main__":
    success = demo_websocket_notifications()
    exit(0 if success else 1) 