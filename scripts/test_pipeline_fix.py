#!/usr/bin/env python3
"""
测试流水线修复后的功能
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(backend_path))

def test_pipeline_imports():
    """测试流水线模块导入"""
    print("测试流水线模块导入...")
    
    try:
        from pipeline.step1_outline import OutlineExtractor
        from pipeline.step2_timeline import TimelineExtractor
        from pipeline.step3_scoring import ClipScorer
        from pipeline.step4_title import TitleGenerator
        from pipeline.step5_clustering import ClusteringEngine
        from pipeline.step6_video import VideoGenerator
        print("✓ 所有流水线步骤导入成功")
        return True
    except Exception as e:
        print(f"✗ 流水线模块导入失败: {e}")
        return False

def test_pipeline_adapter():
    """测试Pipeline适配器"""
    print("\n测试Pipeline适配器...")
    
    try:
        from services.pipeline_adapter import PipelineAdapter
        from core.database import SessionLocal
        
        # 创建数据库会话
        db = SessionLocal()
        
        # 创建适配器
        adapter = PipelineAdapter(db, task_id="test-task", project_id="test-project")
        print("✓ Pipeline适配器创建成功")
        
        db.close()
        return True
    except Exception as e:
        print(f"✗ Pipeline适配器测试失败: {e}")
        return False

def test_websocket_service():
    """测试WebSocket通知服务"""
    print("\n测试WebSocket通知服务...")
    
    try:
        from services.websocket_notification_service import WebSocketNotificationService
        
        # 测试方法签名
        service = WebSocketNotificationService()
        print("✓ WebSocket通知服务创建成功")
        return True
    except Exception as e:
        print(f"✗ WebSocket通知服务测试失败: {e}")
        return False

def test_progress_manager():
    """测试进度管理器"""
    print("\n测试进度管理器...")
    
    try:
        from core.progress_manager import ProgressManager
        from core.database import SessionLocal
        
        # 创建数据库会话
        db = SessionLocal()
        
        # 创建进度管理器
        progress_manager = ProgressManager(db)
        print("✓ 进度管理器创建成功")
        
        db.close()
        return True
    except Exception as e:
        print(f"✗ 进度管理器测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始测试流水线修复...")
    print("=" * 50)
    
    tests = [
        test_pipeline_imports,
        test_pipeline_adapter,
        test_websocket_service,
        test_progress_manager
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("✓ 所有测试通过！流水线修复成功")
        return 0
    else:
        print("✗ 部分测试失败，需要进一步修复")
        return 1

if __name__ == "__main__":
    sys.exit(main())
