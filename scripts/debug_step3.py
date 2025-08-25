#!/usr/bin/env python3
"""
调试步骤3的具体错误
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
backend_path = project_root / "backend"
sys.path.insert(0, str(backend_path))

def debug_step3():
    """调试步骤3"""
    print("开始调试步骤3...")
    
    try:
        # 1. 测试导入
        print("1. 测试导入...")
        from pipeline.step3_scoring import ClipScorer
        print("✓ 导入成功")
        
        # 2. 测试初始化
        print("\n2. 测试初始化...")
        scorer = ClipScorer()
        print("✓ 初始化成功")
        
        # 3. 检查提示词
        print("\n3. 检查提示词...")
        if hasattr(scorer, 'recommendation_prompt'):
            print(f"✓ 提示词存在，长度: {len(scorer.recommendation_prompt)}")
            print(f"  前100字符: {scorer.recommendation_prompt[:100]}...")
        else:
            print("✗ 提示词不存在")
            return False
        
        # 4. 测试方法存在
        print("\n4. 测试方法存在...")
        if hasattr(scorer, 'score_clips'):
            print("✓ score_clips方法存在")
        else:
            print("✗ score_clips方法不存在")
            return False
        
        # 5. 测试配置
        print("\n5. 测试配置...")
        from pipeline.config import PROMPT_FILES
        if 'recommendation' in PROMPT_FILES:
            print(f"✓ recommendation键存在: {PROMPT_FILES['recommendation']}")
            if PROMPT_FILES['recommendation'].exists():
                print("✓ 文件存在")
            else:
                print("✗ 文件不存在")
                return False
        else:
            print("✗ recommendation键不存在")
            return False
        
        # 6. 测试LLM客户端
        print("\n6. 测试LLM客户端...")
        if hasattr(scorer, 'llm_client'):
            print("✓ LLM客户端存在")
        else:
            print("✗ LLM客户端不存在")
            return False
        
        print("\n✓ 所有测试通过！")
        return True
        
    except Exception as e:
        print(f"\n✗ 调试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("步骤3调试工具")
    print("=" * 50)
    
    success = debug_step3()
    
    print("\n" + "=" * 50)
    if success:
        print("✓ 步骤3调试完成，未发现问题")
        return 0
    else:
        print("✗ 步骤3调试发现问题")
        return 1

if __name__ == "__main__":
    sys.exit(main())
