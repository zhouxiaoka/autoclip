#!/usr/bin/env python3
"""
完整的桌面应用构建脚本
包含前端构建、后端打包、Tauri应用构建
"""

import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path
from typing import Dict, List, Optional

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_DIR = PROJECT_ROOT / "backend"
TAURI_DIR = PROJECT_ROOT / "src-tauri"
RESOURCES_DIR = TAURI_DIR / "resources"

class DesktopAppBuilder:
    """桌面应用构建器"""
    
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.frontend_dir = FRONTEND_DIR
        self.backend_dir = BACKEND_DIR
        self.tauri_dir = TAURI_DIR
        self.resources_dir = RESOURCES_DIR
        
        # 平台信息
        self.current_os = platform.system().lower()
        self.current_arch = platform.machine().lower()
        
        # 构建配置
        self.build_config = {
            "frontend": {
                "build_command": ["npm", "run", "build"],
                "output_dir": FRONTEND_DIR / "dist"
            },
            "backend": {
                "build_command": ["python3", "-m", "PyInstaller", "--onefile"],
                "output_dir": self.resources_dir
            },
            "tauri": {
                "build_command": ["tauri", "build"],
                "output_dir": TAURI_DIR / "target" / "release" / "bundle"
            }
        }
    
    def log(self, message: str, level: str = "INFO"):
        """日志输出"""
        print(f"[{level}] {message}")
    
    def check_dependencies(self) -> bool:
        """检查构建依赖"""
        self.log("检查构建依赖...")
        
        # 检查Node.js和npm
        if not shutil.which("node"):
            self.log("Node.js 未找到", "ERROR")
            return False
        
        if not shutil.which("npm"):
            self.log("npm 未找到", "ERROR")
            return False
        
        # 检查Python
        if not shutil.which("python3"):
            self.log("Python3 未找到", "ERROR")
            return False
        
        # 检查PyInstaller
        try:
            import PyInstaller
            self.log(f"PyInstaller 版本: {PyInstaller.__version__}")
        except ImportError:
            self.log("PyInstaller 未安装", "ERROR")
            return False
        
        # 检查Tauri CLI
        if not shutil.which("tauri"):
            self.log("Tauri CLI 未找到", "ERROR")
            return False
        
        # 检查Rust
        if not shutil.which("cargo"):
            self.log("Rust/Cargo 未找到", "ERROR")
            return False
        
        self.log("所有依赖检查通过")
        return True
    
    def build_frontend(self) -> bool:
        """构建前端"""
        self.log("构建前端...")
        
        try:
            # 安装依赖
            self.log("安装前端依赖...")
            install_result = subprocess.run(
                ["npm", "install"],
                cwd=self.frontend_dir,
                capture_output=True,
                text=True
            )
            
            if install_result.returncode != 0:
                self.log(f"前端依赖安装失败: {install_result.stderr}", "ERROR")
                return False
            
            # 构建前端
            self.log("构建前端应用...")
            build_result = subprocess.run(
                ["npm", "run", "build"],
                cwd=self.frontend_dir,
                capture_output=True,
                text=True
            )
            
            if build_result.returncode != 0:
                self.log(f"前端构建失败: {build_result.stderr}", "ERROR")
                return False
            
            # 检查构建输出
            dist_dir = self.frontend_dir / "dist"
            if not dist_dir.exists():
                self.log("前端构建输出目录不存在", "ERROR")
                return False
            
            self.log("前端构建成功")
            return True
            
        except Exception as e:
            self.log(f"前端构建异常: {e}", "ERROR")
            return False
    
    def build_backend(self) -> bool:
        """构建后端"""
        self.log("构建后端...")
        
        try:
            # 设置环境变量
            env = os.environ.copy()
            env["AUTOCLIP_DESKTOP_MODE"] = "1"
            env["AUTOCLIP_MODE"] = "desktop"
            
            # 清理旧的构建产物
            self.log("清理旧的构建产物...")
            if (self.resources_dir / "autoclip-backend").exists():
                (self.resources_dir / "autoclip-backend").unlink()
            
            # 构建后端二进制文件 - 使用虚拟环境Python
            venv_python = str(self.project_root / "venv" / "bin" / "python")
            build_cmd = [
                venv_python, "-m", "PyInstaller",
                "--onefile",
                "--name", "autoclip-backend",
                "--distpath", str(self.resources_dir),
                "--workpath", str(self.project_root / "build" / "pyinstaller"),
                "--specpath", str(self.project_root / "build" / "specs"),
                "--clean",
                "--noconfirm",
                "--add-data", f"{self.backend_dir}/core:core",
                "--add-data", f"{self.backend_dir}/api:api",
                "--add-data", f"{self.backend_dir}/models:models",
                "--add-data", f"{self.backend_dir}/services:services",
                "--add-data", f"{self.backend_dir}/repositories:repositories",
                "--add-data", f"{self.backend_dir}/schemas:schemas",
                "--add-data", f"{self.backend_dir}/utils:utils",
                "--add-data", f"{self.backend_dir}/tasks:tasks",
                "--add-data", f"{self.backend_dir}/pipeline:pipeline",
                "--add-data", f"{self.backend_dir}/prompt:prompt",
                "--add-data", f"{self.project_root}/data:data",
                str(self.backend_dir / "desktop_main.py")
            ]
            
            self.log("执行后端构建...")
            build_result = subprocess.run(
                build_cmd,
                cwd=self.project_root,
                env=env,
                capture_output=True,
                text=True
            )
            
            if build_result.returncode != 0:
                self.log(f"后端构建失败: {build_result.stderr}", "ERROR")
                return False
            
            # 检查构建输出
            backend_binary = self.resources_dir / "autoclip-backend"
            if not backend_binary.exists():
                self.log("后端二进制文件未生成", "ERROR")
                return False
            
            # 设置执行权限
            backend_binary.chmod(0o755)
            
            self.log("后端构建成功")
            return True
            
        except Exception as e:
            self.log(f"后端构建异常: {e}", "ERROR")
            return False
    
    def build_tauri_app(self) -> bool:
        """构建Tauri应用"""
        self.log("构建Tauri应用...")
        
        try:
            # 构建Tauri应用
            build_result = subprocess.run(
                ["tauri", "build"],
                cwd=self.tauri_dir,
                capture_output=True,
                text=True
            )
            
            if build_result.returncode != 0:
                self.log(f"Tauri构建失败: {build_result.stderr}", "ERROR")
                return False
            
            # 检查构建输出
            bundle_dir = self.tauri_dir / "target" / "release" / "bundle"
            if not bundle_dir.exists():
                self.log("Tauri构建输出目录不存在", "ERROR")
                return False
            
            self.log("Tauri应用构建成功")
            return True
            
        except Exception as e:
            self.log(f"Tauri构建异常: {e}", "ERROR")
            return False
    
    def verify_build(self) -> bool:
        """验证构建结果"""
        self.log("验证构建结果...")
        
        # 检查前端构建
        frontend_dist = self.frontend_dir / "dist"
        if not frontend_dist.exists():
            self.log("前端构建输出不存在", "ERROR")
            return False
        
        # 检查后端构建
        backend_binary = self.resources_dir / "autoclip-backend"
        if not backend_binary.exists():
            self.log("后端二进制文件不存在", "ERROR")
            return False
        
        # 检查Tauri构建
        bundle_dir = self.tauri_dir / "target" / "release" / "bundle"
        if not bundle_dir.exists():
            self.log("Tauri构建输出不存在", "ERROR")
            return False
        
        # 检查安装包
        if self.current_os == "darwin":
            app_bundle = bundle_dir / "macos" / "AutoClip Desktop.app"
            if not app_bundle.exists():
                self.log("macOS应用包不存在", "ERROR")
                return False
        
        self.log("构建验证通过")
        return True
    
    def build(self) -> bool:
        """执行完整构建"""
        self.log("开始完整桌面应用构建...")
        
        # 检查依赖
        if not self.check_dependencies():
            return False
        
        # 构建前端
        if not self.build_frontend():
            return False
        
        # 构建后端
        if not self.build_backend():
            return False
        
        # 构建Tauri应用
        if not self.build_tauri_app():
            return False
        
        # 验证构建
        if not self.verify_build():
            return False
        
        self.log("完整桌面应用构建完成！")
        return True

def main():
    """主函数"""
    builder = DesktopAppBuilder()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "frontend":
            success = builder.build_frontend()
            sys.exit(0 if success else 1)
        elif command == "backend":
            success = builder.build_backend()
            sys.exit(0 if success else 1)
        elif command == "tauri":
            success = builder.build_tauri_app()
            sys.exit(0 if success else 1)
        elif command == "verify":
            success = builder.verify_build()
            sys.exit(0 if success else 1)
        else:
            print("未知命令:", command)
            sys.exit(1)
    else:
        # 默认执行完整构建
        success = builder.build()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()