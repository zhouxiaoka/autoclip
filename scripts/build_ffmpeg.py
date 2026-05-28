#!/usr/bin/env python3
"""
构建FFmpeg静态二进制文件 - 跨平台支持
"""

import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path

def get_platform_info():
    """获取当前平台信息"""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == "darwin":
        if machine in ["arm64", "aarch64"]:
            return "macos-arm64"
        else:
            return "macos-x64"
    elif system == "windows":
        return "windows-x64"
    elif system == "linux":
        return "linux-x64"
    else:
        raise ValueError(f"不支持的平台: {system} {machine}")

def download_ffmpeg_binary(platform_name, target_dir):
    """下载预编译的FFmpeg二进制文件"""
    print(f"📥 下载 {platform_name} 平台的FFmpeg...")
    
    # FFmpeg官方预编译二进制下载链接
    urls = {
        "macos-arm64": "https://evermeet.cx/ffmpeg/ffmpeg-6.1.1.zip",
        "macos-x64": "https://evermeet.cx/ffmpeg/ffmpeg-6.1.1.zip", 
        "windows-x64": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        "linux-x64": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    }
    
    if platform_name not in urls:
        raise ValueError(f"不支持的平台: {platform_name}")
    
    url = urls[platform_name]
    
    # 创建临时目录
    temp_dir = Path("temp_ffmpeg")
    temp_dir.mkdir(exist_ok=True)
    
    try:
        # 下载文件
        if platform_name.startswith("windows"):
            zip_file = temp_dir / "ffmpeg.zip"
        elif platform_name.startswith("linux"):
            tar_file = temp_dir / "ffmpeg.tar.xz"
        else:  # macOS
            zip_file = temp_dir / "ffmpeg.zip"
        
        # 使用curl下载
        if platform_name.startswith("linux"):
            subprocess.run(["curl", "-L", "-o", str(tar_file), url], check=True)
        else:
            subprocess.run(["curl", "-L", "-o", str(zip_file), url], check=True)
        
        # 解压文件
        if platform_name.startswith("windows"):
            subprocess.run(["unzip", "-q", str(zip_file), "-d", str(temp_dir)], check=True)
            # 查找ffmpeg.exe
            for root, dirs, files in os.walk(temp_dir):
                if "ffmpeg.exe" in files:
                    ffmpeg_path = Path(root) / "ffmpeg.exe"
                    break
        elif platform_name.startswith("linux"):
            subprocess.run(["tar", "-xf", str(tar_file), "-C", str(temp_dir)], check=True)
            # 查找ffmpeg
            for root, dirs, files in os.walk(temp_dir):
                if "ffmpeg" in files and not files[files.index("ffmpeg")].endswith(".md"):
                    ffmpeg_path = Path(root) / "ffmpeg"
                    break
        else:  # macOS
            subprocess.run(["unzip", "-q", str(zip_file), "-d", str(temp_dir)], check=True)
            # 查找ffmpeg
            for root, dirs, files in os.walk(temp_dir):
                if "ffmpeg" in files:
                    ffmpeg_path = Path(root) / "ffmpeg"
                    break
        
        # 复制到目标目录
        target_ffmpeg = target_dir / "ffmpeg"
        shutil.copy2(ffmpeg_path, target_ffmpeg)
        
        # 设置执行权限（非Windows）
        if not platform_name.startswith("windows"):
            os.chmod(target_ffmpeg, 0o755)
        
        print(f"✅ FFmpeg下载完成: {target_ffmpeg}")
        return target_ffmpeg
        
    finally:
        # 清理临时文件
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

def build_all_platforms():
    """构建所有平台的FFmpeg"""
    print("🚀 开始构建跨平台FFmpeg...")
    
    project_root = Path(__file__).parent.parent
    resources_dir = project_root / "src-tauri" / "resources" / "ffmpeg"
    
    # 确保目录存在
    resources_dir.mkdir(parents=True, exist_ok=True)
    
    platforms = ["macos-arm64", "macos-x64", "windows-x64", "linux-x64"]
    
    for platform_name in platforms:
        platform_dir = resources_dir / platform_name
        platform_dir.mkdir(exist_ok=True)
        
        try:
            download_ffmpeg_binary(platform_name, platform_dir)
            print(f"✅ {platform_name} 平台FFmpeg构建完成")
        except Exception as e:
            print(f"❌ {platform_name} 平台FFmpeg构建失败: {e}")
            continue
    
    print("🎉 跨平台FFmpeg构建完成！")
    
    # 显示构建结果
    for platform_name in platforms:
        platform_dir = resources_dir / platform_name
        ffmpeg_path = platform_dir / "ffmpeg"
        if ffmpeg_path.exists():
            size = ffmpeg_path.stat().st_size / (1024 * 1024)  # MB
            print(f"  📦 {platform_name}: {ffmpeg_path} ({size:.1f} MB)")

def build_current_platform():
    """构建当前平台的FFmpeg"""
    print("🚀 开始构建当前平台FFmpeg...")
    
    project_root = Path(__file__).parent.parent
    resources_dir = project_root / "src-tauri" / "resources" / "ffmpeg"
    
    # 确保目录存在
    resources_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        platform_name = get_platform_info()
        platform_dir = resources_dir / platform_name
        platform_dir.mkdir(exist_ok=True)
        
        download_ffmpeg_binary(platform_name, platform_dir)
        print(f"✅ 当前平台 {platform_name} FFmpeg构建完成")
        
    except Exception as e:
        print(f"❌ FFmpeg构建失败: {e}")
        return 1
    
    return 0

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        build_all_platforms()
    else:
        return build_current_platform()

if __name__ == "__main__":
    sys.exit(main())
