#!/usr/bin/env python3
"""
桌面应用功能测试脚本
"""

import os
import sys
import subprocess
import requests
import time
import json
from pathlib import Path
from typing import Dict, Any, List

class DesktopTester:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.backend_url = "http://127.0.0.1:8000"
        self.test_results: List[Dict[str, Any]] = []
    
    def log_test(self, test_name: str, success: bool, message: str = ""):
        """记录测试结果"""
        result = {
            "test": test_name,
            "success": success,
            "message": message,
            "timestamp": time.time()
        }
        self.test_results.append(result)
        
        status = "✅" if success else "❌"
        print(f"{status} {test_name}: {message}")
    
    def test_file_structure(self):
        """测试文件结构完整性"""
        print("\n📁 测试文件结构...")
        
        required_files = [
            "backend/desktop_main.py",
            "backend/desktop_celery.py",
            "backend/core/desktop_config.py",
            "backend/api/v1/desktop.py",
            "src-tauri/src/lib.rs",
            "src-tauri/src/backend_manager.rs",
            "src-tauri/src/commands.rs",
            "src-tauri/src/tray.rs",
            "src-tauri/tauri.conf.json",
            "src-tauri/Cargo.toml",
            "frontend/src/components/DesktopSettings.tsx",
            "frontend/src/components/OfflineModeIndicator.tsx",
            "scripts/build_backend.py",
            "scripts/build_desktop.py",
            "scripts/dev_desktop.py",
            "scripts/test_desktop.py"
        ]
        
        missing_files = []
        for file_path in required_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                missing_files.append(file_path)
        
        if missing_files:
            self.log_test("文件结构检查", False, f"缺失文件: {', '.join(missing_files)}")
        else:
            self.log_test("文件结构检查", True, f"所有 {len(required_files)} 个文件都存在")
    
    def test_python_dependencies(self):
        """测试Python依赖"""
        print("\n🐍 测试Python依赖...")
        
        required_packages = [
            "fastapi",
            "uvicorn",
            "celery",
            "sqlalchemy",
            "pydantic",
            "psutil",
            "requests"
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            self.log_test("Python依赖检查", False, f"缺失包: {', '.join(missing_packages)}")
        else:
            self.log_test("Python依赖检查", True, f"所有 {len(required_packages)} 个包都已安装")
    
    def test_node_dependencies(self):
        """测试Node.js依赖"""
        print("\n📦 测试Node.js依赖...")
        
        try:
            result = subprocess.run(["node", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.log_test("Node.js检查", True, f"版本: {result.stdout.strip()}")
            else:
                self.log_test("Node.js检查", False, "Node.js未安装或不可用")
                return
        except FileNotFoundError:
            self.log_test("Node.js检查", False, "Node.js未安装")
            return
        
        try:
            result = subprocess.run(["npm", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.log_test("npm检查", True, f"版本: {result.stdout.strip()}")
            else:
                self.log_test("npm检查", False, "npm未安装或不可用")
        except FileNotFoundError:
            self.log_test("npm检查", False, "npm未安装")
    
    def test_rust_environment(self):
        """测试Rust环境"""
        print("\n🦀 测试Rust环境...")
        
        try:
            result = subprocess.run(["rustc", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.log_test("Rust检查", True, f"版本: {result.stdout.strip()}")
            else:
                self.log_test("Rust检查", False, "Rust未安装或不可用")
                return
        except FileNotFoundError:
            self.log_test("Rust检查", False, "Rust未安装")
            return
        
        try:
            result = subprocess.run(["cargo", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.log_test("Cargo检查", True, f"版本: {result.stdout.strip()}")
            else:
                self.log_test("Cargo检查", False, "Cargo未安装或不可用")
        except FileNotFoundError:
            self.log_test("Cargo检查", False, "Cargo未安装")
    
    def test_tauri_config(self):
        """测试Tauri配置"""
        print("\n⚙️ 测试Tauri配置...")
        
        tauri_conf_path = self.project_root / "src-tauri" / "tauri.conf.json"
        if not tauri_conf_path.exists():
            self.log_test("Tauri配置检查", False, "tauri.conf.json不存在")
            return
        
        try:
            with open(tauri_conf_path, 'r') as f:
                config = json.load(f)
            
            # 检查必要配置项
            required_keys = ["package", "build", "tauri"]
            missing_keys = [key for key in required_keys if key not in config]
            
            if missing_keys:
                self.log_test("Tauri配置检查", False, f"缺失配置项: {', '.join(missing_keys)}")
            else:
                self.log_test("Tauri配置检查", True, "配置文件格式正确")
                
        except json.JSONDecodeError as e:
            self.log_test("Tauri配置检查", False, f"JSON格式错误: {e}")
        except Exception as e:
            self.log_test("Tauri配置检查", False, f"读取配置失败: {e}")
    
    def test_cargo_config(self):
        """测试Cargo配置"""
        print("\n📦 测试Cargo配置...")
        
        cargo_toml_path = self.project_root / "src-tauri" / "Cargo.toml"
        if not cargo_toml_path.exists():
            self.log_test("Cargo配置检查", False, "Cargo.toml不存在")
            return
        
        try:
            with open(cargo_toml_path, 'r') as f:
                content = f.read()
            
            # 检查必要依赖
            required_deps = ["tauri", "serde", "tokio", "reqwest"]
            missing_deps = [dep for dep in required_deps if dep not in content]
            
            if missing_deps:
                self.log_test("Cargo配置检查", False, f"缺失依赖: {', '.join(missing_deps)}")
            else:
                self.log_test("Cargo配置检查", True, "依赖配置正确")
                
        except Exception as e:
            self.log_test("Cargo配置检查", False, f"读取配置失败: {e}")
    
    def test_backend_api(self):
        """测试后端API（需要服务运行）"""
        print("\n🔧 测试后端API...")
        
        try:
            # 测试健康检查端点
            response = requests.get(f"{self.backend_url}/health", timeout=5)
            if response.status_code == 200:
                self.log_test("后端健康检查", True, "服务正常运行")
            else:
                self.log_test("后端健康检查", False, f"HTTP {response.status_code}")
                return
        except requests.exceptions.ConnectionError:
            self.log_test("后端健康检查", False, "无法连接到后端服务")
            return
        except Exception as e:
            self.log_test("后端健康检查", False, f"请求失败: {e}")
            return
        
        # 测试桌面API端点
        desktop_endpoints = [
            "/api/v1/desktop/system/info",
            "/api/v1/desktop/service/status",
            "/api/v1/desktop/config"
        ]
        
        for endpoint in desktop_endpoints:
            try:
                response = requests.get(f"{self.backend_url}{endpoint}", timeout=5)
                if response.status_code == 200:
                    self.log_test(f"API端点 {endpoint}", True, "响应正常")
                else:
                    self.log_test(f"API端点 {endpoint}", False, f"HTTP {response.status_code}")
            except Exception as e:
                self.log_test(f"API端点 {endpoint}", False, f"请求失败: {e}")
    
    def test_frontend_build(self):
        """测试前端构建"""
        print("\n🌐 测试前端构建...")
        
        frontend_dir = self.project_root / "frontend"
        if not frontend_dir.exists():
            self.log_test("前端构建测试", False, "frontend目录不存在")
            return
        
        try:
            # 检查package.json
            package_json = frontend_dir / "package.json"
            if not package_json.exists():
                self.log_test("前端构建测试", False, "package.json不存在")
                return
            
            # 尝试构建前端
            result = subprocess.run(
                ["npm", "run", "build"],
                cwd=frontend_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                self.log_test("前端构建测试", True, "构建成功")
            else:
                self.log_test("前端构建测试", False, f"构建失败: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            self.log_test("前端构建测试", False, "构建超时")
        except Exception as e:
            self.log_test("前端构建测试", False, f"构建异常: {e}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🧪 开始桌面应用功能测试...")
        print("=" * 60)
        
        # 基础环境测试
        self.test_file_structure()
        self.test_python_dependencies()
        self.test_node_dependencies()
        self.test_rust_environment()
        self.test_tauri_config()
        self.test_cargo_config()
        
        # 构建测试
        self.test_frontend_build()
        
        # API测试（可选，需要服务运行）
        print("\n⚠️ 注意: 以下测试需要后端服务运行")
        print("如果后端服务未运行，这些测试将失败")
        self.test_backend_api()
        
        # 输出测试结果
        self.print_summary()
    
    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "=" * 60)
        print("📊 测试结果摘要")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests} ✅")
        print(f"失败: {failed_tests} ❌")
        print(f"成功率: {(passed_tests/total_tests*100):.1f}%")
        
        if failed_tests > 0:
            print("\n❌ 失败的测试:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['message']}")
        
        print("\n" + "=" * 60)

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("桌面应用功能测试脚本")
        print("用法: python test_desktop.py")
        print("测试项目:")
        print("  - 文件结构完整性")
        print("  - Python依赖检查")
        print("  - Node.js依赖检查")
        print("  - Rust环境检查")
        print("  - Tauri配置验证")
        print("  - Cargo配置验证")
        print("  - 前端构建测试")
        print("  - 后端API测试（需要服务运行）")
        return 0
    
    tester = DesktopTester()
    tester.run_all_tests()
    
    # 返回失败测试数量作为退出码
    failed_count = sum(1 for result in tester.test_results if not result["success"])
    return min(failed_count, 255)  # 限制退出码范围

if __name__ == "__main__":
    sys.exit(main())
