#!/usr/bin/env python3
"""
测试运行脚本 - 运行项目的所有单元测试
"""
import sys
import os
import subprocess
from pathlib import Path

def install_test_dependencies():
    """安装测试依赖"""
    print("🔧 安装测试依赖...")
    
    test_dependencies = [
        "pytest",
        "pytest-cov",
        "pytest-mock",
        "cryptography"
    ]
    
    for dep in test_dependencies:
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", dep], 
                         check=True, capture_output=True)
            print(f"✅ 已安装 {dep}")
        except subprocess.CalledProcessError as e:
            print(f"❌ 安装 {dep} 失败: {e}")
            return False
    
    return True

def run_tests():
    """运行测试"""
    print("🧪 运行单元测试...")
    
    # 设置测试环境变量
    os.environ["AUTO_CLIPS_DEV_MODE"] = "1"
    
    # 运行测试
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/",
            "-v",
            "--tb=short",
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term-missing"
        ], check=True)
        
        print("✅ 所有测试通过!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 测试失败: {e}")
        return False

def run_specific_test(test_file):
    """运行特定测试文件"""
    print(f"🧪 运行测试文件: {test_file}")
    
    os.environ["AUTO_CLIPS_DEV_MODE"] = "1"
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            test_file,
            "-v",
            "--tb=short"
        ], check=True)
        
        print("✅ 测试通过!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 自动切片工具 - 测试运行器")
    print("=" * 50)
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--install-deps":
            if install_test_dependencies():
                print("✅ 依赖安装完成")
            else:
                print("❌ 依赖安装失败")
                sys.exit(1)
            return
        
        elif sys.argv[1] == "--test-file" and len(sys.argv) > 2:
            test_file = sys.argv[2]
            if not Path(test_file).exists():
                print(f"❌ 测试文件不存在: {test_file}")
                sys.exit(1)
            
            if run_specific_test(test_file):
                sys.exit(0)
            else:
                sys.exit(1)
    
    # 默认运行所有测试
    print("📋 测试计划:")
    print("1. 安装测试依赖")
    print("2. 运行配置管理测试")
    print("3. 运行错误处理测试")
    print("4. 生成测试覆盖率报告")
    print()
    
    # 安装依赖
    if not install_test_dependencies():
        print("❌ 无法安装测试依赖，退出")
        sys.exit(1)
    
    # 运行测试
    if run_tests():
        print("\n🎉 测试完成!")
        print("📊 测试覆盖率报告已生成在 htmlcov/ 目录")
        sys.exit(0)
    else:
        print("\n💥 测试失败!")
        sys.exit(1)

if __name__ == "__main__":
    main() 