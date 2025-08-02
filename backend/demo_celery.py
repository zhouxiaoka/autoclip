#!/usr/bin/env python3
"""
Celery功能演示
展示任务队列的基本功能
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.celery_app import celery_app
from tasks.maintenance import health_check
from tasks.notification import send_processing_notification

def demo_celery_features():
    """演示Celery功能"""
    print("🎯 AutoClip Celery 任务队列演示")
    print("=" * 50)
    
    # 设置测试环境变量
    os.environ['DASHSCOPE_API_KEY'] = 'test_api_key'
    
    try:
        # 1. 演示健康检查任务
        print("1. 🏥 系统健康检查任务")
        print("   提交健康检查任务...")
        health_task = health_check.delay()
        result = health_task.get()
        print(f"   ✅ 任务完成，状态: {result['status']}")
        print(f"   📊 检查项目: {list(result['checks'].keys())}")
        
        # 2. 演示通知任务（不等待结果）
        print("\n2. 📢 通知任务")
        print("   提交处理通知任务...")
        notification_task = send_processing_notification.delay(
            "demo_project", 
            "demo_task", 
            "演示任务已开始处理", 
            "info"
        )
        print(f"   🚀 通知任务提交成功，ID: {notification_task.id}")
        print(f"   📈 通知任务状态: {notification_task.status}")
        
        # 3. 演示任务状态查询
        print("\n3. 📈 任务状态查询")
        print(f"   健康检查任务ID: {health_task.id}")
        print(f"   通知任务ID: {notification_task.id}")
        print(f"   健康检查任务状态: {health_task.status}")
        print(f"   通知任务状态: {notification_task.status}")
        
        # 4. 演示任务结果（只查询健康检查结果）
        print("\n4. 📋 任务结果")
        print(f"   健康检查结果: {health_task.result}")
        print(f"   通知任务ID: {notification_task.id} (异步执行中)")
        
        print("\n🎉 Celery任务队列演示完成!")
        print("✅ 所有功能正常工作")
        print("💡 提示：查看Worker终端窗口可以看到通知任务的执行日志")
        
        return True
        
    except Exception as e:
        print(f"❌ 演示失败: {e}")
        return False

if __name__ == "__main__":
    success = demo_celery_features()
    exit(0 if success else 1) 