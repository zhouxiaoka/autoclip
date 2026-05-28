#!/usr/bin/env python3
"""
构建完整的桌面应用 - 桌面版
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def main():
    print("🚀 开始构建桌面应用...")
    
    # 设置路径
    project_root = Path(__file__).parent.parent
    frontend_dir = project_root / "frontend"
    src_tauri_dir = project_root / "src-tauri"
    
    # 检查必要工具
    print("🔍 检查构建环境...")
    
    # 检查Node.js
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        print(f"✅ Node.js版本: {result.stdout.strip()}")
    except FileNotFoundError:
        print("❌ Node.js未安装")
        return 1
    
    # 检查npm
    try:
        result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
        print(f"✅ npm版本: {result.stdout.strip()}")
    except FileNotFoundError:
        print("❌ npm未安装")
        return 1
    
    # 检查Rust
    try:
        result = subprocess.run(["rustc", "--version"], capture_output=True, text=True)
        print(f"✅ Rust版本: {result.stdout.strip()}")
    except FileNotFoundError:
        print("❌ Rust未安装")
        return 1
    
    # 检查Tauri CLI
    try:
        result = subprocess.run(["tauri", "--version"], capture_output=True, text=True)
        print(f"✅ Tauri CLI版本: {result.stdout.strip()}")
    except FileNotFoundError:
        print("❌ Tauri CLI未安装，正在安装...")
        try:
            subprocess.run(["npm", "install", "-g", "@tauri-apps/cli"], check=True)
            print("✅ Tauri CLI安装成功")
        except subprocess.CalledProcessError as e:
            print(f"❌ Tauri CLI安装失败: {e}")
            return 1
    
    # 1. 构建后端
    print("\n🔧 构建后端...")
    try:
        result = subprocess.run([sys.executable, "scripts/build_backend.py"], 
                              check=True, cwd=project_root)
        print("✅ 后端构建成功")
    except subprocess.CalledProcessError as e:
        print(f"❌ 后端构建失败: {e}")
        return 1
    
    # 2. 安装前端依赖
    print("\n📦 安装前端依赖...")
    try:
        subprocess.run(["npm", "install"], check=True, cwd=frontend_dir)
        print("✅ 前端依赖安装成功")
    except subprocess.CalledProcessError as e:
        print(f"❌ 前端依赖安装失败: {e}")
        return 1
    
    # 3. 构建前端
    print("\n📦 构建前端...")
    try:
        subprocess.run(["npm", "run", "build"], check=True, cwd=frontend_dir)
        print("✅ 前端构建成功")
    except subprocess.CalledProcessError as e:
        print(f"❌ 前端构建失败: {e}")
        return 1
    
    # 4. 构建Tauri应用
    print("\n🦀 构建Tauri应用...")
    try:
        subprocess.run(["tauri", "build"], check=True, cwd=src_tauri_dir)
        print("✅ Tauri应用构建成功")
    except subprocess.CalledProcessError as e:
        print(f"❌ Tauri应用构建失败: {e}")
        return 1
    
    print("\n🎉 桌面应用构建完成！")
    
    # 显示构建结果
    bundle_dir = src_tauri_dir / "target" / "release" / "bundle"
    if bundle_dir.exists():
        print(f"📁 安装包位置: {bundle_dir}")
        
        # 列出可用的安装包
        for item in bundle_dir.iterdir():
            if item.is_dir():
                print(f"  📦 {item.name}/")
                for file in item.iterdir():
                    if file.is_file():
                        size = file.stat().st_size / (1024 * 1024)  # MB
                        print(f"    📄 {file.name} ({size:.1f} MB)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())