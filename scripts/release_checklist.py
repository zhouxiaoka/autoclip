#!/usr/bin/env python3
"""
发布检查清单脚本
在发布前运行，确保所有检查项都通过
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

class ReleaseChecker:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.checks: List[Tuple[str, callable]] = []
        self.results: List[Tuple[str, bool, str]] = []
    
    def log(self, message: str, color: str = Colors.NC):
        """打印带颜色的日志"""
        print(f"{color}{message}{Colors.NC}")
    
    def add_check(self, name: str, check_func: callable):
        """添加检查项"""
        self.checks.append((name, check_func))
    
    def run_command(self, command: List[str], cwd: Path = None) -> Tuple[bool, str]:
        """运行命令并返回结果"""
        try:
            result = subprocess.run(
                command,
                cwd=cwd or self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            return result.returncode == 0, result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return False, "命令执行超时"
        except Exception as e:
            return False, str(e)
    
    def check_frontend_build(self) -> Tuple[bool, str]:
        """检查前端构建"""
        self.log("检查前端构建...", Colors.BLUE)
        
        # 检查 dist 目录是否存在
        dist_dir = self.project_root / "frontend" / "dist"
        if not dist_dir.exists():
            return False, "前端 dist 目录不存在，请先运行 npm run build"
        
        # 检查关键文件
        index_file = dist_dir / "index.html"
        if not index_file.exists():
            return False, "index.html 文件不存在"
        
        return True, "前端构建正常"
    
    def check_backend_code(self) -> Tuple[bool, str]:
        """检查后端代码"""
        self.log("检查后端代码...", Colors.BLUE)
        
        # 检查关键文件
        key_files = [
            "backend/app_factory.py",
            "backend/desktop_main.py",
            "backend/main.py"
        ]
        
        for file_path in key_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                return False, f"关键文件不存在: {file_path}"
        
        return True, "后端代码检查通过"
    
    def check_resources(self) -> Tuple[bool, str]:
        """检查资源文件"""
        self.log("检查资源文件...", Colors.BLUE)
        
        resources_dir = self.project_root / "src-tauri" / "resources"
        if not resources_dir.exists():
            return False, "资源目录不存在"
        
        # 检查关键资源
        key_resources = [
            "backend",
            "requirements.txt"
        ]
        
        for resource in key_resources:
            resource_path = resources_dir / resource
            if not resource_path.exists():
                return False, f"关键资源不存在: {resource}"
        
        return True, "资源文件检查通过"
    
    def check_bundle_size(self) -> Tuple[bool, str]:
        """检查安装包体积"""
        self.log("检查安装包体积...", Colors.BLUE)
        
        success, output = self.run_command([
            sys.executable, "scripts/check_bundle_size.py", "--max-size", "500"
        ])
        
        return success, output
    
    def check_api_smoke_test(self) -> Tuple[bool, str]:
        """运行 API 烟雾测试"""
        self.log("运行 API 烟雾测试...", Colors.BLUE)
        
        # 启动后端服务
        backend_process = subprocess.Popen([
            sys.executable, "-m", "backend.desktop_main"
        ], cwd=self.project_root / "backend", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        try:
            # 等待后端启动
            time.sleep(10)
            
            # 运行烟雾测试
            success, output = self.run_command([
                sys.executable, "scripts/smoke_api.py", "http://127.0.0.1:8000", "-t", "30"
            ])
            
            return success, output
            
        finally:
            # 清理后端进程
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()
    
    def check_git_status(self) -> Tuple[bool, str]:
        """检查 Git 状态"""
        self.log("检查 Git 状态...", Colors.BLUE)
        
        # 检查是否有未提交的更改
        success, output = self.run_command(["git", "status", "--porcelain"])
        if not success:
            return False, "无法获取 Git 状态"
        
        if output.strip():
            return False, "存在未提交的更改，请先提交所有更改"
        
        return True, "Git 状态正常"
    
    def check_dependencies(self) -> Tuple[bool, str]:
        """检查依赖项"""
        self.log("检查依赖项...", Colors.BLUE)
        
        # 检查前端依赖
        frontend_dir = self.project_root / "frontend"
        if not (frontend_dir / "node_modules").exists():
            return False, "前端依赖未安装，请运行 npm install"
        
        # 检查 Python 依赖
        try:
            import fastapi
            import uvicorn
            import tauri
        except ImportError as e:
            return False, f"Python 依赖缺失: {e}"
        
        return True, "依赖项检查通过"
    
    def run_all_checks(self) -> bool:
        """运行所有检查"""
        self.log("🚀 开始发布前检查", Colors.YELLOW)
        self.log("=" * 50, Colors.YELLOW)
        
        # 添加所有检查项
        self.add_check("Git 状态", self.check_git_status)
        self.add_check("依赖项", self.check_dependencies)
        self.add_check("后端代码", self.check_backend_code)
        self.add_check("前端构建", self.check_frontend_build)
        self.add_check("资源文件", self.check_resources)
        self.add_check("安装包体积", self.check_bundle_size)
        self.add_check("API 烟雾测试", self.check_api_smoke_test)
        
        # 运行所有检查
        all_passed = True
        
        for name, check_func in self.checks:
            self.log(f"\n📋 {name}", Colors.BLUE)
            try:
                success, message = check_func()
                self.results.append((name, success, message))
                
                if success:
                    self.log(f"✅ {message}", Colors.GREEN)
                else:
                    self.log(f"❌ {message}", Colors.RED)
                    all_passed = False
                    
            except Exception as e:
                self.log(f"❌ 检查失败: {e}", Colors.RED)
                self.results.append((name, False, str(e)))
                all_passed = False
        
        # 打印总结
        self.log("\n" + "=" * 50, Colors.YELLOW)
        self.log("📊 检查结果总结", Colors.YELLOW)
        
        passed_count = sum(1 for _, success, _ in self.results if success)
        total_count = len(self.results)
        
        self.log(f"总检查项: {total_count}", Colors.YELLOW)
        self.log(f"通过: {passed_count}", Colors.GREEN)
        self.log(f"失败: {total_count - passed_count}", Colors.RED)
        
        if all_passed:
            self.log("\n🎉 所有检查通过！可以发布", Colors.GREEN)
        else:
            self.log("\n💥 存在检查失败项，请修复后再发布", Colors.RED)
            self.log("\n失败的检查项:", Colors.RED)
            for name, success, message in self.results:
                if not success:
                    self.log(f"  - {name}: {message}", Colors.RED)
        
        return all_passed

def main():
    parser = argparse.ArgumentParser(description='发布检查清单脚本')
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
    checker = ReleaseChecker(project_root)
    success = checker.run_all_checks()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
