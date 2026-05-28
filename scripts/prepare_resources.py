#!/usr/bin/env python3
"""
资源准备脚本 - 只打包当前平台所需的文件
避免将三平台 ffmpeg 和大量不必要文件打入安装包
"""

import os
import sys
import shutil
import platform
from pathlib import Path

def get_platform_name():
    """获取当前平台名称"""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    else:
        raise ValueError(f"不支持的平台: {system}")

def prepare_resources():
    """准备打包资源"""
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    tauri_resources = project_root / "src-tauri" / "resources"
    
    print(f"项目根目录: {project_root}")
    print(f"Tauri 资源目录: {tauri_resources}")
    
    # 清理旧的资源文件（保留 ffmpeg-unified）
    if tauri_resources.exists():
        print("清理旧的资源文件...")
        # 先备份 ffmpeg-unified 目录
        ffmpeg_unified_backup = None
        ffmpeg_unified_dir = tauri_resources / "ffmpeg-unified"
        if ffmpeg_unified_dir.exists():
            ffmpeg_unified_backup = project_root / "temp_ffmpeg_unified"
            if ffmpeg_unified_backup.exists():
                shutil.rmtree(ffmpeg_unified_backup)
            shutil.move(str(ffmpeg_unified_dir), str(ffmpeg_unified_backup))
        
        shutil.rmtree(tauri_resources)
        
        # 恢复 ffmpeg-unified 目录
        if ffmpeg_unified_backup and ffmpeg_unified_backup.exists():
            tauri_resources.mkdir(parents=True, exist_ok=True)
            shutil.move(str(ffmpeg_unified_backup), str(ffmpeg_unified_dir))
    
    # 创建资源目录
    tauri_resources.mkdir(parents=True, exist_ok=True)
    
    # 获取当前平台
    current_platform = get_platform_name()
    print(f"当前平台: {current_platform}")
    
    # 不复制后端二进制文件（太大，改用 Python 源代码）
    # 桌面端将在运行时创建 Python 环境
    print("ℹ 跳过后端二进制文件（体积过大），将使用 Python 源代码")
    
    # 只复制当前平台的 ffmpeg
    ffmpeg_source_dir = project_root / "src-tauri" / "resources" / "ffmpeg-unified"
    if ffmpeg_source_dir.exists():
        # 创建 ffmpeg 目录
        ffmpeg_dest_dir = tauri_resources / "ffmpeg"
        ffmpeg_dest_dir.mkdir(exist_ok=True)
        
        # 根据平台选择对应的 ffmpeg 文件
        platform_files = {
            "macos": "ffmpeg-macos",
            "windows": "ffmpeg-windows.exe", 
            "linux": "ffmpeg-linux"
        }
        
        if current_platform in platform_files:
            source_file = ffmpeg_source_dir / platform_files[current_platform]
            if source_file.exists():
                dest_file = ffmpeg_dest_dir / "ffmpeg"
                shutil.copy2(source_file, dest_file)
                # 设置执行权限
                os.chmod(dest_file, 0o755)
                print(f"✓ 复制 {current_platform} ffmpeg")
            else:
                print(f"⚠ {current_platform} 平台的 ffmpeg 文件不存在: {source_file}")
        else:
            print(f"⚠ 不支持的平台: {current_platform}")
    else:
        print("⚠ ffmpeg 源目录不存在")
    
    # 复制后端 Python 源代码（排除不必要文件）
    backend_source = project_root / "backend"
    if backend_source.exists():
        backend_dest = tauri_resources / "backend"
        backend_dest.mkdir(exist_ok=True)
        
        # 要排除的目录和文件
        exclude_dirs = {
            '__pycache__', '.mypy_cache', '.ruff_cache', '.pytest_cache',
            'tests', 'data', 'logs', 'temp', 'uploads', 'whisper_models'
        }
        exclude_files = {'.pyc', '.pyo', '.pyd', '.log', '.pid', '.rdb'}
        
        def should_exclude(path):
            if path.name in exclude_dirs:
                return True
            if path.suffix in exclude_files:
                return True
            return False
        
        def copy_backend_files(source, dest):
            for item in source.iterdir():
                if should_exclude(item):
                    continue
                
                dest_item = dest / item.name
                if item.is_dir():
                    dest_item.mkdir(exist_ok=True)
                    copy_backend_files(item, dest_item)
                else:
                    shutil.copy2(item, dest_item)
        
        copy_backend_files(backend_source, backend_dest)
        print("✓ 复制后端 Python 源代码")
        
        # 复制 requirements.txt
        requirements_file = project_root / "requirements.txt"
        if requirements_file.exists():
            shutil.copy2(requirements_file, tauri_resources / "requirements.txt")
            print("✓ 复制 requirements.txt")
    else:
        print("⚠ 后端源代码目录不存在")
    
    # 复制 uv（Python 包管理器）
    uv_source = project_root / "uv"
    if uv_source.exists():
        shutil.copy2(uv_source, tauri_resources / "uv")
        os.chmod(tauri_resources / "uv", 0o755)
        print("✓ 复制 uv")
    else:
        print("⚠ uv 文件不存在，将使用系统 Python")
    
    print(f"\n资源准备完成！")
    print(f"资源目录大小: {get_dir_size(tauri_resources):.2f} MB")
    
    # 列出最终的文件结构
    print("\n最终资源文件结构:")
    for root, dirs, files in os.walk(tauri_resources):
        level = root.replace(str(tauri_resources), '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            file_path = Path(root) / file
            size = file_path.stat().st_size / (1024 * 1024)  # MB
            print(f"{subindent}{file} ({size:.2f} MB)")

def get_dir_size(path):
    """获取目录大小（MB）"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
    return total_size / (1024 * 1024)  # 转换为 MB

if __name__ == "__main__":
    try:
        prepare_resources()
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)
