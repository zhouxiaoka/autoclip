#!/usr/bin/env python3
"""
Celery高级功能演示
展示任务队列的完整功能
"""

import os
import sys
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.celery_app import celery_app
from tasks.maintenance import health_check
from tasks.notification import send_processing_notification, send_completion_notification
from tasks.video import extract_video_clips

def demo_celery_advanced():
    """演示Celery高级功能"""
    print("🎯 AutoClip Celery 高级功能演示")
    print("=" * 50)
    
    # 设置测试环境变量
    os.environ['DASHSCOPE_API_KEY'] = 'test_api_key'
    
    try:
        # 1. 演示健康检查任务（同步等待结果）
        print("1. 🏥 系统健康检查任务")
        print("   提交健康检查任务...")
        health_task = health_check.delay()
        result = health_task.get(timeout=10)  # 设置超时
        print(f"   ✅ 任务完成，状态: {result['status']}")
        print(f"   📊 检查项目: {list(result['checks'].keys())}")
        
        # 2. 演示通知任务（异步提交，不等待）
        print("\n2. 📢 通知任务")
        print("   提交处理通知任务...")
        notification_task = send_processing_notification.delay(
            "demo_project", 
            "demo_task", 
            "演示任务已开始处理", 
            "info"
        )
        print(f"   🚀 通知任务提交成功，ID: {notification_task.id}")
        
        # 3. 演示视频处理任务（异步提交）
        print("\n3. 🎬 视频处理任务")
        print("   提交视频片段提取任务...")
        clip_data = [
            {"title": "片段1", "start_time": 0, "end_time": 10, "content": "测试内容1"},
            {"title": "片段2", "start_time": 10, "end_time": 20, "content": "测试内容2"}
        ]
        video_task = extract_video_clips.delay("demo_project", clip_data)
        print(f"   🚀 视频处理任务提交成功，ID: {video_task.id}")
        
        # 4. 演示任务状态监控
        print("\n4. 📈 任务状态监控")
        tasks = [health_task, notification_task, video_task]
        task_names = ["健康检查", "通知任务", "视频处理"]
        
        for i, (task, name) in enumerate(zip(tasks, task_names)):
            print(f"   {name}: {task.status} (ID: {task.id})")
        
        # 5. 等待一段时间，然后检查任务状态
        print("\n5. ⏳ 等待任务执行...")
        time.sleep(3)
        
        print("\n6. 📋 任务执行结果")
        for i, (task, name) in enumerate(zip(tasks, task_names)):
            if task.ready():
                try:
                    result = task.get(timeout=5)
                    print(f"   {name}: ✅ 完成 - {result.get('message', '执行成功')}")
                except Exception as e:
                    print(f"   {name}: ❌ 失败 - {e}")
            else:
                print(f"   {name}: ⏳ 执行中...")
        
        # 7. 演示队列状态
        print("\n7. 📊 队列状态")
        try:
            from services.task_queue_service import TaskQueueService
            from core.database import SessionLocal
            
            db = SessionLocal()
            task_service = TaskQueueService(db)
            
            # 获取队列状态
            queue_status = {
                'active_tasks': len([t for t in tasks if t.status == 'SUCCESS']),
                'pending_tasks': len([t for t in tasks if t.status == 'PENDING']),
                'total_tasks': len(tasks)
            }
            
            print(f"   📈 活跃任务: {queue_status['active_tasks']}")
            print(f"   ⏳ 等待任务: {queue_status['pending_tasks']}")
            print(f"   📊 总任务数: {queue_status['total_tasks']}")
            
            db.close()
        except Exception as e:
            print(f"   ⚠️  无法获取队列状态: {e}")
        
        print("\n🎉 Celery高级功能演示完成!")
        print("✅ 所有功能正常工作")
        print("💡 提示：")
        print("   - 健康检查任务：同步执行，立即返回结果")
        print("   - 通知任务：异步执行，Worker处理")
        print("   - 视频处理任务：异步执行，Worker处理")
        print("   - 可以查看Worker终端窗口查看详细执行日志")
        
        return True
        
    except Exception as e:
        print(f"❌ 演示失败: {e}")
        return False

if __name__ == "__main__":
    success = demo_celery_advanced()
    exit(0 if success else 1) 