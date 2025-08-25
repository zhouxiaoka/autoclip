#!/usr/bin/env python3
"""
测试所有步骤的方法调用修复
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(backend_path))

def test_step1_methods():
    """测试步骤1方法"""
    print("测试步骤1方法...")
    
    try:
        from pipeline.step1_outline import OutlineExtractor
        
        extractor = OutlineExtractor()
        print("✓ 步骤1实例创建成功")
        
        # 检查方法是否存在
        if hasattr(extractor, 'extract_outline'):
            print("✓ extract_outline方法存在")
            return True
        else:
            print("✗ extract_outline方法不存在")
            return False
            
    except Exception as e:
        print(f"✗ 步骤1测试失败: {e}")
        return False

def test_step2_methods():
    """测试步骤2方法"""
    print("\n测试步骤2方法...")
    
    try:
        from pipeline.step2_timeline import TimelineExtractor
        
        extractor = TimelineExtractor()
        print("✓ 步骤2实例创建成功")
        
        # 检查方法是否存在
        if hasattr(extractor, 'extract_timeline'):
            print("✓ extract_timeline方法存在")
            return True
        else:
            print("✗ extract_timeline方法不存在")
            return False
            
    except Exception as e:
        print(f"✗ 步骤2测试失败: {e}")
        return False

def test_step3_methods():
    """测试步骤3方法"""
    print("\n测试步骤3方法...")
    
    try:
        from pipeline.step3_scoring import ClipScorer
        
        scorer = ClipScorer()
        print("✓ 步骤3实例创建成功")
        
        # 检查方法是否存在
        if hasattr(scorer, 'score_clips'):
            print("✓ score_clips方法存在")
            return True
        else:
            print("✗ score_clips方法不存在")
            return False
            
    except Exception as e:
        print(f"✗ 步骤3测试失败: {e}")
        return False

def test_step4_methods():
    """测试步骤4方法"""
    print("\n测试步骤4方法...")
    
    try:
        from pipeline.step4_title import TitleGenerator
        
        generator = TitleGenerator()
        print("✓ 步骤4实例创建成功")
        
        # 检查方法是否存在
        if hasattr(generator, 'generate_titles'):
            print("✓ generate_titles方法存在")
            return True
        else:
            print("✗ generate_titles方法不存在")
            return False
            
    except Exception as e:
        print(f"✗ 步骤4测试失败: {e}")
        return False

def test_step5_methods():
    """测试步骤5方法"""
    print("\n测试步骤5方法...")
    
    try:
        from pipeline.step5_clustering import ClusteringEngine
        
        clusterer = ClusteringEngine()
        print("✓ 步骤5实例创建成功")
        
        # 检查方法是否存在
        if hasattr(clusterer, 'cluster_clips'):
            print("✓ cluster_clips方法存在")
            return True
        else:
            print("✗ cluster_clips方法不存在")
            return False
            
    except Exception as e:
        print(f"✗ 步骤5测试失败: {e}")
        return False

def test_step6_methods():
    """测试步骤6方法"""
    print("\n测试步骤6方法...")
    
    try:
        from pipeline.step6_video import VideoGenerator
        
        generator = VideoGenerator()
        print("✓ 步骤6实例创建成功")
        
        # 检查方法是否存在
        methods_to_check = ['generate_clips', 'generate_collections', 'save_clip_metadata', 'save_collection_metadata']
        all_methods_exist = True
        
        for method in methods_to_check:
            if hasattr(generator, method):
                print(f"✓ {method}方法存在")
            else:
                print(f"✗ {method}方法不存在")
                all_methods_exist = False
        
        return all_methods_exist
            
    except Exception as e:
        print(f"✗ 步骤6测试失败: {e}")
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

def main():
    """主测试函数"""
    print("开始测试所有步骤的方法调用修复...")
    print("=" * 60)
    
    tests = [
        test_step1_methods,
        test_step2_methods,
        test_step3_methods,
        test_step4_methods,
        test_step5_methods,
        test_step6_methods,
        test_pipeline_adapter
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("✓ 所有测试通过！所有步骤的方法调用修复成功")
        return 0
    else:
        print("✗ 部分测试失败，需要进一步修复")
        return 1

if __name__ == "__main__":
    sys.exit(main())
