#!/usr/bin/env python3
"""
安装包优化脚本
移除不必要的跨平台二进制文件，减小安装包体积
"""

import os
import shutil
import platform
from pathlib import Path

def get_current_platform():
    """获取当前平台信息"""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == "darwin":
        if machine == "arm64":
            return "macos-arm64"
        else:
            return "macos-x64"
    elif system == "windows":
        return "windows-x64"
    elif system == "linux":
        return "linux-x64"
    else:
        return "unknown"

def optimize_bundle():
    """优化安装包"""
    print("🔧 开始优化安装包...")
    
    # 获取当前平台
    current_platform = get_current_platform()
    print(f"📱 当前平台: {current_platform}")
    
    # 资源目录
    resources_dir = Path("src-tauri/resources")
    if not resources_dir.exists():
        print("❌ 资源目录不存在")
        return False
    
    # 备份原始文件
    backup_dir = Path("backup_resources")
    if backup_dir.exists():
        shutil.rmtree(backup_dir)
    shutil.copytree(resources_dir, backup_dir)
    print("💾 已备份原始资源文件")
    
    # 优化后端二进制文件
    print("🗂️ 优化后端二进制文件...")
    backend_files = {
        "macos-arm64": "autoclip-backend-macos-arm64",
        "macos-x64": "autoclip-backend-macos-x64", 
        "windows-x64": "autoclip-backend-windows-x64.exe",
        "linux-x64": "autoclip-backend-linux-x64"
    }
    
    # 只保留当前平台的后端二进制文件
    for platform_name, filename in backend_files.items():
        file_path = resources_dir / filename
        if platform_name != current_platform and file_path.exists():
            file_path.unlink()
            print(f"🗑️ 删除: {filename}")
        elif platform_name == current_platform and file_path.exists():
            print(f"✅ 保留: {filename}")
    
    # 优化FFmpeg文件
    print("🎬 优化FFmpeg文件...")
    ffmpeg_dir = resources_dir / "ffmpeg-unified"
    if ffmpeg_dir.exists():
        ffmpeg_files = {
            "macos": "ffmpeg-macos",
            "windows": "ffmpeg-windows.exe",
            "linux": "ffmpeg-linux"
        }
        
        # 只保留当前平台的FFmpeg
        for platform_name, filename in ffmpeg_files.items():
            file_path = ffmpeg_dir / filename
            if platform_name != current_platform.split("-")[0] and file_path.exists():
                file_path.unlink()
                print(f"🗑️ 删除: {filename}")
            elif platform_name == current_platform.split("-")[0] and file_path.exists():
                print(f"✅ 保留: {filename}")
    
    # 检查优化结果
    print("\n📊 优化结果:")
    total_size = 0
    for item in resources_dir.rglob("*"):
        if item.is_file():
            size = item.stat().st_size
            total_size += size
            size_mb = size / (1024 * 1024)
            if size_mb > 1:  # 只显示大于1MB的文件
                print(f"  {item.relative_to(resources_dir)}: {size_mb:.1f}MB")
    
    total_mb = total_size / (1024 * 1024)
    print(f"\n📦 总大小: {total_mb:.1f}MB")
    
    return True

def restore_backup():
    """恢复备份"""
    backup_dir = Path("backup_resources")
    resources_dir = Path("src-tauri/resources")
    
    if backup_dir.exists():
        if resources_dir.exists():
            shutil.rmtree(resources_dir)
        shutil.move(backup_dir, resources_dir)
        print("🔄 已恢复原始资源文件")
        return True
    else:
        print("❌ 备份文件不存在")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        restore_backup()
    else:
        optimize_bundle()
