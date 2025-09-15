#!/usr/bin/env python3
"""
安装多模型提供商依赖脚本
"""
import subprocess
import sys
import os

def install_package(package):
    """安装Python包"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ 成功安装 {package}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 安装 {package} 失败: {e}")
        return False

def main():
    """主函数"""
    print("🚀 开始安装多模型提供商依赖...")
    
    # 需要安装的包
    packages = [
        "openai>=1.0.0",           # OpenAI
        "google-generativeai>=0.3.0",  # Google Gemini
        "requests>=2.25.0",        # 硅基流动 (HTTP请求)
        "dashscope>=1.10.0",       # 阿里通义千问 (如果还没有安装)
    ]
    
    success_count = 0
    total_count = len(packages)
    
    for package in packages:
        if install_package(package):
            success_count += 1
    
    print(f"\n📊 安装结果: {success_count}/{total_count} 个包安装成功")
    
    if success_count == total_count:
        print("🎉 所有依赖安装完成！现在可以使用多模型提供商功能了。")
        print("\n📝 使用说明:")
        print("1. 启动系统: python backend/main.py")
        print("2. 访问设置页面配置API密钥")
        print("3. 选择您喜欢的AI模型提供商")
        print("4. 开始使用AI自动切片功能")
    else:
        print("⚠️  部分依赖安装失败，请检查网络连接或手动安装失败的包。")
        print("手动安装命令:")
        for package in packages:
            print(f"  pip install {package}")

if __name__ == "__main__":
    main()
