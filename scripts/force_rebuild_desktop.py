#!/usr/bin/env python3
"""
强制重新构建桌面应用 - 确保包含最新修复
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def main():
    print("🚀 强制重新构建桌面应用...")
    
    # 设置路径
    project_root = Path(__file__).parent.parent
    backend_dir = project_root / "backend"
    resources_dir = project_root / "src-tauri" / "resources"
    venv_path = project_root / "venv"
    
    # 1. 彻底清理所有构建产物
    print("🧹 彻底清理所有构建产物...")
    
    # 清理后端构建产物
    for path in [
        backend_dir / "dist",
        backend_dir / "build",
        backend_dir / "*.spec",
        resources_dir / "autoclip-backend",
        resources_dir / "autoclip-backend-macos-arm64",
        project_root / "build",
    ]:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
                print(f"  ✓ 删除目录: {path}")
            else:
                path.unlink()
                print(f"  ✓ 删除文件: {path}")
    
    # 清理前端构建产物
    frontend_dir = project_root / "frontend"
    if (frontend_dir / "dist").exists():
        shutil.rmtree(frontend_dir / "dist")
        print("  ✓ 删除前端构建产物")
    
    # 清理Tauri构建产物
    tauri_dir = project_root / "src-tauri"
    if (tauri_dir / "target").exists():
        shutil.rmtree(tauri_dir / "target")
        print("  ✓ 删除Tauri构建产物")
    
    # 2. 检查虚拟环境
    if not venv_path.exists():
        print("❌ 虚拟环境不存在，请先创建虚拟环境")
        return 1
    
    # 3. 安装/更新依赖
    print("📦 安装/更新Python依赖...")
    try:
        pip_path = venv_path / "bin" / "pip"
        subprocess.run([str(pip_path), "install", "-r", "requirements.txt"], 
                      check=True, cwd=project_root)
        subprocess.run([str(pip_path), "install", "pyinstaller"], check=True)
        print("✅ Python依赖安装成功")
    except subprocess.CalledProcessError as e:
        print(f"❌ Python依赖安装失败: {e}")
        return 1
    
    # 4. 构建后端
    print("🔧 构建后端...")
    try:
        result = subprocess.run([sys.executable, "scripts/build_backend.py"], 
                              check=True, cwd=project_root)
        print("✅ 后端构建成功")
    except subprocess.CalledProcessError as e:
        print(f"❌ 后端构建失败: {e}")
        return 1
    
    # 5. 验证后端构建
    backend_binary = resources_dir / "autoclip-backend"
    if not backend_binary.exists():
        print("❌ 后端二进制文件未生成")
        return 1
    
    # 检查文件时间戳
    import time
    current_time = time.time()
    file_time = backend_binary.stat().st_mtime
    if current_time - file_time > 60:  # 如果文件超过1分钟前创建
        print("⚠️  警告: 后端二进制文件可能是旧的")
    
    print(f"✅ 后端二进制文件生成成功: {backend_binary}")
    print(f"   文件大小: {backend_binary.stat().st_size / (1024*1024):.1f} MB")
    print(f"   创建时间: {time.ctime(file_time)}")
    
    # 6. 安装前端依赖
    print("📦 安装前端依赖...")
    try:
        subprocess.run(["npm", "install"], check=True, cwd=frontend_dir)
        print("✅ 前端依赖安装成功")
    except subprocess.CalledProcessError as e:
        print(f"❌ 前端依赖安装失败: {e}")
        return 1
    
    # 7. 构建前端
    print("📦 构建前端...")
    try:
        subprocess.run(["npm", "run", "build"], check=True, cwd=frontend_dir)
        print("✅ 前端构建成功")
    except subprocess.CalledProcessError as e:
        print(f"❌ 前端构建失败: {e}")
        return 1
    
    # 8. 构建Tauri应用
    print("🦀 构建Tauri应用...")
    try:
        subprocess.run(["tauri", "build"], check=True, cwd=tauri_dir)
        print("✅ Tauri应用构建成功")
    except subprocess.CalledProcessError as e:
        print(f"❌ Tauri应用构建失败: {e}")
        return 1
    
    print("\n🎉 强制重新构建完成！")
    
    # 显示构建结果
    bundle_dir = tauri_dir / "target" / "release" / "bundle"
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