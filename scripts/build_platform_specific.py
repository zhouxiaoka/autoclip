#!/usr/bin/env python3
"""
平台特定构建脚本
根据目标平台自动选择需要的二进制文件，避免包含不必要的跨平台文件
"""

import os
import shutil
import platform
import subprocess
from pathlib import Path

class PlatformSpecificBuilder:
    """平台特定构建器"""
    
    def __init__(self, target_platform=None):
        self.project_root = Path(__file__).parent.parent
        self.resources_dir = self.project_root / "src-tauri" / "resources"
        self.target_platform = target_platform or self._detect_platform()
        
        # 平台映射
        self.platform_mapping = {
            "macos-arm64": {
                "backend": "autoclip-backend-macos-arm64",
                "ffmpeg": "ffmpeg-macos",
                "tauri_target": "aarch64-apple-darwin"
            },
            "macos-x64": {
                "backend": "autoclip-backend-macos-x64", 
                "ffmpeg": "ffmpeg-macos",
                "tauri_target": "x86_64-apple-darwin"
            },
            "windows-x64": {
                "backend": "autoclip-backend-windows-x64.exe",
                "ffmpeg": "ffmpeg-windows.exe", 
                "tauri_target": "x86_64-pc-windows-msvc"
            },
            "linux-x64": {
                "backend": "autoclip-backend-linux-x64",
                "ffmpeg": "ffmpeg-linux",
                "tauri_target": "x86_64-unknown-linux-gnu"
            }
        }
    
    def _detect_platform(self):
        """检测当前平台"""
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        if system == "darwin":
            return "macos-arm64" if machine == "arm64" else "macos-x64"
        elif system == "windows":
            return "windows-x64"
        elif system == "linux":
            return "linux-x64"
        else:
            return "unknown"
    
    def log(self, message, level="INFO"):
        """日志输出"""
        print(f"[{level}] {message}")
    
    def prepare_platform_resources(self):
        """准备平台特定的资源文件"""
        self.log(f"准备 {self.target_platform} 平台的资源文件...")
        
        if self.target_platform not in self.platform_mapping:
            self.log(f"不支持的平台: {self.target_platform}", "ERROR")
            return False
        
        platform_config = self.platform_mapping[self.target_platform]
        
        # 创建资源目录
        self.resources_dir.mkdir(parents=True, exist_ok=True)
        
        # 清理旧文件
        for item in self.resources_dir.iterdir():
            if item.is_file() and item.name.startswith("autoclip-backend"):
                item.unlink()
                self.log(f"删除旧文件: {item.name}")
        
        # 准备后端二进制文件
        backend_name = platform_config["backend"]
        backend_path = self.resources_dir / backend_name
        
        # 如果文件不存在，创建占位符
        if not backend_path.exists():
            backend_path.touch()
            self.log(f"创建占位符: {backend_name}")
        
        # 准备FFmpeg
        ffmpeg_dir = self.resources_dir / "ffmpeg-unified"
        ffmpeg_dir.mkdir(exist_ok=True)
        
        ffmpeg_name = platform_config["ffmpeg"]
        ffmpeg_path = ffmpeg_dir / ffmpeg_name
        
        # 尝试从系统获取FFmpeg
        if self._copy_system_ffmpeg(ffmpeg_path):
            self.log(f"复制系统FFmpeg: {ffmpeg_name}")
        else:
            # 创建占位符
            ffmpeg_path.touch()
            self.log(f"创建FFmpeg占位符: {ffmpeg_name}")
        
        # 设置执行权限
        if self.target_platform.startswith("macos") or self.target_platform.startswith("linux"):
            backend_path.chmod(0o755)
            ffmpeg_path.chmod(0o755)
        
        return True
    
    def _copy_system_ffmpeg(self, target_path):
        """从系统复制FFmpeg"""
        try:
            # 查找系统FFmpeg
            ffmpeg_path = shutil.which("ffmpeg")
            if ffmpeg_path:
                shutil.copy2(ffmpeg_path, target_path)
                return True
        except Exception as e:
            self.log(f"复制系统FFmpeg失败: {e}", "WARNING")
        return False
    
    def update_tauri_config(self):
        """更新Tauri配置文件"""
        self.log("更新Tauri配置文件...")
        
        config_path = self.project_root / "src-tauri" / "tauri.conf.json"
        if not config_path.exists():
            self.log("Tauri配置文件不存在", "ERROR")
            return False
        
        platform_config = self.platform_mapping[self.target_platform]
        
        # 读取配置文件
        import json
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 更新资源列表
        config["bundle"]["resources"] = [
            f"resources/{platform_config['backend']}",
            "resources/ffmpeg-unified"
        ]
        
        # 写回配置文件
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        self.log("Tauri配置文件已更新")
        return True
    
    def build(self):
        """执行构建"""
        self.log(f"开始构建 {self.target_platform} 平台版本...")
        
        # 准备资源文件
        if not self.prepare_platform_resources():
            return False
        
        # 更新配置文件
        if not self.update_tauri_config():
            return False
        
        # 构建应用
        self.log("开始构建Tauri应用...")
        try:
            result = subprocess.run(
                ["tauri", "build"],
                cwd=self.project_root / "src-tauri",
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.log("构建成功！")
                return True
            else:
                self.log(f"构建失败: {result.stderr}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"构建异常: {e}", "ERROR")
            return False
    
    def show_build_info(self):
        """显示构建信息"""
        platform_config = self.platform_mapping[self.target_platform]
        
        print(f"\n📱 目标平台: {self.target_platform}")
        print(f"🔧 后端二进制: {platform_config['backend']}")
        print(f"🎬 FFmpeg: {platform_config['ffmpeg']}")
        print(f"🎯 Tauri目标: {platform_config['tauri_target']}")
        
        # 检查文件大小
        backend_path = self.resources_dir / platform_config['backend']
        ffmpeg_path = self.resources_dir / "ffmpeg-unified" / platform_config['ffmpeg']
        
        if backend_path.exists():
            size_mb = backend_path.stat().st_size / (1024 * 1024)
            print(f"📦 后端大小: {size_mb:.1f}MB")
        
        if ffmpeg_path.exists():
            size_mb = ffmpeg_path.stat().st_size / (1024 * 1024)
            print(f"🎬 FFmpeg大小: {size_mb:.1f}MB")

def main():
    import sys
    
    target_platform = None
    if len(sys.argv) > 1:
        target_platform = sys.argv[1]
    
    builder = PlatformSpecificBuilder(target_platform)
    builder.show_build_info()
    
    if builder.build():
        print("\n🎉 构建完成！")
        
        # 显示构建结果
        bundle_dir = builder.project_root / "src-tauri" / "target" / "release" / "bundle"
        if bundle_dir.exists():
            print(f"\n📁 构建产物位置: {bundle_dir}")
            
            # 查找安装包
            for item in bundle_dir.rglob("*.dmg"):
                size_mb = item.stat().st_size / (1024 * 1024)
                print(f"📦 DMG安装包: {item.name} ({size_mb:.1f}MB)")
            
            for item in bundle_dir.rglob("*.exe"):
                size_mb = item.stat().st_size / (1024 * 1024)
                print(f"📦 EXE安装包: {item.name} ({size_mb:.1f}MB)")
            
            for item in bundle_dir.rglob("*.AppImage"):
                size_mb = item.stat().st_size / (1024 * 1024)
                print(f"📦 AppImage: {item.name} ({size_mb:.1f}MB)")
    else:
        print("\n❌ 构建失败！")
        sys.exit(1)

if __name__ == "__main__":
    main()
