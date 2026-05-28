#!/usr/bin/env python3
"""
安装包体积检查脚本
用于检查 Tauri 构建产物的体积，确保不超过预设阈值
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

class BundleSizeChecker:
    def __init__(self, project_root: Path, max_size_mb: int = 500):
        self.project_root = project_root
        self.max_size_mb = max_size_mb
        self.max_size_bytes = max_size_mb * 1024 * 1024
        
        # Tauri 构建产物路径
        self.bundle_paths = [
            project_root / "src-tauri" / "target" / "release" / "bundle",
            project_root / "dist",
            project_root / "build"
        ]
    
    def log(self, message: str, color: str = Colors.NC):
        """打印带颜色的日志"""
        print(f"{color}{message}{Colors.NC}")
    
    def get_file_size(self, file_path: Path) -> int:
        """获取文件大小（字节）"""
        try:
            return file_path.stat().st_size
        except (OSError, FileNotFoundError):
            return 0
    
    def get_dir_size(self, dir_path: Path) -> int:
        """获取目录总大小（字节）"""
        total_size = 0
        try:
            for item in dir_path.rglob('*'):
                if item.is_file():
                    total_size += self.get_file_size(item)
        except (OSError, FileNotFoundError):
            pass
        return total_size
    
    def format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    
    def find_bundle_files(self) -> List[Tuple[Path, int]]:
        """查找所有构建产物文件"""
        bundle_files = []
        
        for bundle_path in self.bundle_paths:
            if bundle_path.exists():
                if bundle_path.is_file():
                    size = self.get_file_size(bundle_path)
                    bundle_files.append((bundle_path, size))
                elif bundle_path.is_dir():
                    # 查找常见的安装包文件
                    for pattern in ["*.dmg", "*.pkg", "*.deb", "*.rpm", "*.msi", "*.exe", "*.app"]:
                        for file_path in bundle_path.rglob(pattern):
                            if file_path.is_file():
                                size = self.get_file_size(file_path)
                                bundle_files.append((file_path, size))
        
        return bundle_files
    
    def check_resource_size(self) -> Dict[str, int]:
        """检查资源文件大小"""
        resources_path = self.project_root / "src-tauri" / "resources"
        resource_sizes = {}
        
        if not resources_path.exists():
            return resource_sizes
        
        for item in resources_path.rglob('*'):
            if item.is_file():
                size = self.get_file_size(item)
                relative_path = item.relative_to(resources_path)
                resource_sizes[str(relative_path)] = size
        
        return resource_sizes
    
    def run_check(self, verbose: bool = False) -> bool:
        """运行体积检查"""
        self.log("🔍 开始检查安装包体积", Colors.YELLOW)
        self.log(f"最大允许体积: {self.format_size(self.max_size_bytes)}", Colors.YELLOW)
        self.log("")
        
        # 检查构建产物
        bundle_files = self.find_bundle_files()
        
        if not bundle_files:
            self.log("⚠️  未找到构建产物文件", Colors.YELLOW)
            self.log("请确保已经运行过构建命令", Colors.YELLOW)
            return True
        
        total_size = 0
        oversized_files = []
        
        self.log("📦 构建产物文件:", Colors.BLUE)
        for file_path, size in bundle_files:
            total_size += size
            size_str = self.format_size(size)
            
            if size > self.max_size_bytes:
                oversized_files.append((file_path, size))
                self.log(f"  ❌ {file_path.name}: {size_str} (超过限制)", Colors.RED)
            else:
                self.log(f"  ✅ {file_path.name}: {size_str}", Colors.GREEN)
        
        self.log("")
        self.log(f"📊 总大小: {self.format_size(total_size)}", Colors.YELLOW)
        
        # 检查资源文件
        if verbose:
            self.log("")
            self.log("📁 资源文件详情:", Colors.BLUE)
            resource_sizes = self.check_resource_size()
            
            # 按大小排序
            sorted_resources = sorted(resource_sizes.items(), key=lambda x: x[1], reverse=True)
            
            for relative_path, size in sorted_resources:
                size_str = self.format_size(size)
                self.log(f"  {relative_path}: {size_str}")
        
        # 检查结果
        if oversized_files:
            self.log("")
            self.log("❌ 体积检查失败！", Colors.RED)
            self.log("以下文件超过体积限制:", Colors.RED)
            for file_path, size in oversized_files:
                size_str = self.format_size(size)
                self.log(f"  - {file_path.name}: {size_str}", Colors.RED)
            return False
        elif total_size > self.max_size_bytes:
            self.log("")
            self.log("❌ 体积检查失败！", Colors.RED)
            self.log(f"总大小 {self.format_size(total_size)} 超过限制 {self.format_size(self.max_size_bytes)}", Colors.RED)
            return False
        else:
            self.log("")
            self.log("✅ 体积检查通过！", Colors.GREEN)
            return True

def main():
    parser = argparse.ArgumentParser(description='安装包体积检查脚本')
    parser.add_argument('-m', '--max-size', type=int, default=500, help='最大允许体积（MB，默认: 500）')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    parser.add_argument('--project-root', type=str, help='项目根目录路径')
    
    args = parser.parse_args()
    
    # 确定项目根目录
    if args.project_root:
        project_root = Path(args.project_root)
    else:
        # 从脚本位置推断项目根目录
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
    
    if not project_root.exists():
        print(f"错误: 项目根目录不存在: {project_root}")
        sys.exit(1)
    
    # 创建检查器并运行检查
    checker = BundleSizeChecker(project_root, args.max_size)
    success = checker.run_check(args.verbose)
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
