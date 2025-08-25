#!/usr/bin/env python3
"""
测试步骤3修复
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(backend_path))

def test_step3_import():
    """测试步骤3导入"""
    print("测试步骤3导入...")
    
    try:
        from pipeline.step3_scoring import ClipScorer
        print("✓ 步骤3导入成功")
        return True
    except Exception as e:
        print(f"✗ 步骤3导入失败: {e}")
        return False

def test_step3_config():
    """测试步骤3配置"""
    print("\n测试步骤3配置...")
    
    try:
        from pipeline.config import PROMPT_FILES
        
        # 检查recommendation键是否存在
        if 'recommendation' in PROMPT_FILES:
            print("✓ recommendation键存在")
            print(f"  路径: {PROMPT_FILES['recommendation']}")
            
            # 检查文件是否存在
            if PROMPT_FILES['recommendation'].exists():
                print("✓ 推荐理由文件存在")
                return True
            else:
                print("✗ 推荐理由文件不存在")
                return False
        else:
            print("✗ recommendation键不存在")
            return False
            
    except Exception as e:
        print(f"✗ 步骤3配置测试失败: {e}")
        return False

def test_step3_initialization():
    """测试步骤3初始化"""
    print("\n测试步骤3初始化...")
    
    try:
        from pipeline.step3_scoring import ClipScorer
        
        # 创建实例
        scorer = ClipScorer()
        print("✓ 步骤3实例创建成功")
        
        # 检查提示词是否加载
        if hasattr(scorer, 'recommendation_prompt') and scorer.recommendation_prompt:
            print("✓ 推荐理由提示词加载成功")
            print(f"  提示词长度: {len(scorer.recommendation_prompt)} 字符")
            return True
        else:
            print("✗ 推荐理由提示词加载失败")
            return False
            
    except Exception as e:
        print(f"✗ 步骤3初始化失败: {e}")
        return False

def test_websocket_fix():
    """测试WebSocket修复"""
    print("\n测试WebSocket修复...")
    
    try:
        from services.websocket_notification_service import WebSocketNotificationService
        
        # 测试方法签名
        service = WebSocketNotificationService()
        
        # 检查send_task_update方法
        import inspect
        sig = inspect.signature(service.send_task_update)
        params = list(sig.parameters.keys())
        
        if 'project_id' not in params:
            print("✓ send_task_update方法不包含project_id参数")
            return True
        else:
            print("✗ send_task_update方法仍然包含project_id参数")
            return False
            
    except Exception as e:
        print(f"✗ WebSocket修复测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始测试步骤3修复...")
    print("=" * 50)
    
    tests = [
        test_step3_import,
        test_step3_config,
        test_step3_initialization,
        test_websocket_fix
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("✓ 所有测试通过！步骤3修复成功")
        return 0
    else:
        print("✗ 部分测试失败，需要进一步修复")
        return 1

if __name__ == "__main__":
    sys.exit(main())
