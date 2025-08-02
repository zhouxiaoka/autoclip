#!/usr/bin/env python3
"""
Celery任务测试脚本
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.celery_app import celery_app
from tasks.processing import process_video_pipeline, process_single_step
from tasks.maintenance import health_check

def test_celery_tasks():
    """测试Celery任务"""
    print("🧪 开始测试Celery任务...")
    
    # 设置测试环境变量
    os.environ['DASHSCOPE_API_KEY'] = 'test_api_key'
    
    try:
        # 测试健康检查任务
        print("1. 测试健康检查任务...")
        result = health_check.delay()
        print(f"   结果: {result.get()}")
        
        # 测试视频处理任务（使用测试SRT文件）
        print("2. 测试视频处理任务...")
        srt_path = Path(__file__).parent / "test.srt"
        result = process_video_pipeline.delay("test_project", str(srt_path))
        print(f"   结果: {result.get()}")
        
        # 测试单个步骤任务
        print("3. 测试单个步骤任务...")
        result = process_single_step.delay("test_project", "step1_outline", str(srt_path))
        print(f"   结果: {result.get()}")
        
        print("✅ 所有Celery任务测试通过!")
        
    except Exception as e:
        print(f"❌ Celery任务测试失败: {e}")
        raise

if __name__ == "__main__":
    test_celery_tasks() 