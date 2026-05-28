#!/usr/bin/env python3
"""
下载静态编译的FFmpeg二进制文件
确保用户电脑上无需安装FFmpeg即可使用
"""

import os
import shutil
import subprocess
import platform
import requests
import zipfile
import tarfile
from pathlib import Path

class StaticFFmpegDownloader:
    """静态FFmpeg下载器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.resources_dir = self.project_root / "src-tauri" / "resources"
        self.ffmpeg_dir = self.resources_dir / "ffmpeg-unified"
        
        # 下载URL映射
        self.download_urls = {
            "macos": {
                "url": "https://evermeet.cx/ffmpeg/ffmpeg-6.0.zip",
                "filename": "ffmpeg-6.0.zip",
                "extract_name": "ffmpeg",
                "target_name": "ffmpeg-macos"
            },
            "windows": {
                "url": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
                "filename": "ffmpeg-release-essentials.zip", 
                "extract_name": "ffmpeg-*-essentials/bin/ffmpeg.exe",
                "target_name": "ffmpeg-windows.exe"
            },
            "linux": {
                "url": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
                "filename": "ffmpeg-release-amd64-static.tar.xz",
                "extract_name": "ffmpeg-*-static/ffmpeg",
                "target_name": "ffmpeg-linux"
            }
        }
    
    def log(self, message, level="INFO"):
        """日志输出"""
        print(f"[{level}] {message}")
    
    def download_file(self, url, filename):
        """下载文件"""
        self.log(f"下载: {url}")
        
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            file_path = Path(filename)
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.log(f"下载完成: {filename}")
            return file_path
            
        except Exception as e:
            self.log(f"下载失败: {e}", "ERROR")
            return None
    
    def extract_zip(self, zip_path, extract_name, target_path):
        """解压ZIP文件"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 查找匹配的文件
                for file_info in zip_ref.filelist:
                    if extract_name.replace("*", "") in file_info.filename:
                        if file_info.filename.endswith(extract_name.split("/")[-1]):
                            # 提取文件
                            with zip_ref.open(file_info) as source:
                                with open(target_path, 'wb') as target:
                                    shutil.copyfileobj(source, target)
                            
                            target_path.chmod(0o755)
                            self.log(f"解压完成: {target_path}")
                            return True
            
            self.log(f"未找到匹配文件: {extract_name}", "ERROR")
            return False
            
        except Exception as e:
            self.log(f"解压失败: {e}", "ERROR")
            return False
    
    def extract_tar(self, tar_path, extract_name, target_path):
        """解压TAR文件"""
        try:
            with tarfile.open(tar_path, 'r:xz') as tar_ref:
                # 查找匹配的文件
                for member in tar_ref.getmembers():
                    if extract_name.replace("*", "") in member.name:
                        if member.name.endswith(extract_name.split("/")[-1]):
                            # 提取文件
                            source = tar_ref.extractfile(member)
                            if source:
                                with open(target_path, 'wb') as target:
                                    shutil.copyfileobj(source, target)
                                
                                target_path.chmod(0o755)
                                self.log(f"解压完成: {target_path}")
                                return True
            
            self.log(f"未找到匹配文件: {extract_name}", "ERROR")
            return False
            
        except Exception as e:
            self.log(f"解压失败: {e}", "ERROR")
            return False
    
    def download_ffmpeg(self, platform_name):
        """下载指定平台的FFmpeg"""
        if platform_name not in self.download_urls:
            self.log(f"不支持的平台: {platform_name}", "ERROR")
            return False
        
        config = self.download_urls[platform_name]
        target_path = self.ffmpeg_dir / config["target_name"]
        
        # 如果文件已存在且大小合理，跳过下载
        if target_path.exists() and target_path.stat().st_size > 10 * 1024 * 1024:  # 大于10MB
            self.log(f"FFmpeg已存在: {config['target_name']}")
            return True
        
        # 下载文件
        zip_path = self.download_file(config["url"], config["filename"])
        if not zip_path:
            return False
        
        # 解压文件
        if config["filename"].endswith('.zip'):
            success = self.extract_zip(zip_path, config["extract_name"], target_path)
        else:
            success = self.extract_tar(zip_path, config["extract_name"], target_path)
        
        # 清理临时文件
        zip_path.unlink()
        
        return success
    
    def download_all_platforms(self):
        """下载所有平台的FFmpeg"""
        self.log("开始下载静态FFmpeg...")
        
        # 创建目录
        self.ffmpeg_dir.mkdir(parents=True, exist_ok=True)
        
        success_count = 0
        for platform_name in self.download_urls.keys():
            self.log(f"下载 {platform_name} 平台的FFmpeg...")
            if self.download_ffmpeg(platform_name):
                success_count += 1
        
        self.log(f"下载完成: {success_count}/{len(self.download_urls)} 成功")
        return success_count == len(self.download_urls)
    
    def verify_ffmpeg(self, platform_name):
        """验证FFmpeg文件"""
        if platform_name not in self.download_urls:
            return False
        
        config = self.download_urls[platform_name]
        target_path = self.ffmpeg_dir / config["target_name"]
        
        if not target_path.exists():
            return False
        
        # 检查文件大小
        size_mb = target_path.stat().st_size / (1024 * 1024)
        if size_mb < 10:  # 小于10MB可能不完整
            return False
        
        # 检查依赖
        try:
            if platform_name == "macos":
                result = subprocess.run(
                    ["otool", "-L", str(target_path)],
                    capture_output=True, text=True
                )
                # 检查是否依赖外部库
                output = result.stdout
                external_deps = [line for line in output.split('\n') 
                               if '/opt/homebrew' in line or '/usr/local' in line]
                if external_deps:
                    self.log(f"警告: {platform_name} FFmpeg依赖外部库", "WARNING")
                    for dep in external_deps[:3]:  # 只显示前3个
                        self.log(f"  {dep.strip()}")
            
            # 测试FFmpeg
            result = subprocess.run(
                [str(target_path), "-version"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                self.log(f"✓ {platform_name} FFmpeg验证成功 ({size_mb:.1f}MB)")
                return True
            else:
                self.log(f"✗ {platform_name} FFmpeg验证失败", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"验证异常: {e}", "ERROR")
            return False

def main():
    import sys
    
    downloader = StaticFFmpegDownloader()
    
    if len(sys.argv) > 1:
        platform_name = sys.argv[1]
        if downloader.download_ffmpeg(platform_name):
            downloader.verify_ffmpeg(platform_name)
    else:
        # 下载所有平台
        if downloader.download_all_platforms():
            print("\n📊 验证结果:")
            for platform_name in downloader.download_urls.keys():
                downloader.verify_ffmpeg(platform_name)

if __name__ == "__main__":
    main()
