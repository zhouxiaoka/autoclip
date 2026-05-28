#!/usr/bin/env python3
"""
桌面应用开发环境管理脚本
"""

import os
import sys
import subprocess
import signal
import time
import json
from pathlib import Path
from typing import Dict, Any

class DesktopDevManager:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.backend_dir = self.project_root / "backend"
        self.frontend_dir = self.project_root / "frontend"
        self.src_tauri_dir = self.project_root / "src-tauri"
        self.pid_file = self.project_root / "dev_processes.json"
        self.processes: Dict[str, int] = {}
        
    def load_processes(self):
        """加载进程信息"""
        if self.pid_file.exists():
            try:
                with open(self.pid_file, 'r') as f:
                    self.processes = json.load(f)
            except Exception as e:
                print(f"⚠️ 加载进程信息失败: {e}")
                self.processes = {}
    
    def save_processes(self):
        """保存进程信息"""
        try:
            with open(self.pid_file, 'w') as f:
                json.dump(self.processes, f, indent=2)
        except Exception as e:
            print(f"⚠️ 保存进程信息失败: {e}")
    
    def start_backend(self):
        """启动后端服务"""
        print("🚀 启动后端服务...")
        
        # 设置环境变量
        env = os.environ.copy()
        env["AUTOCLIP_DESKTOP_MODE"] = "true"
        env["AUTOCLIP_MODE"] = "desktop"
        
        try:
            # 启动后端
            process = subprocess.Popen(
                [sys.executable, "desktop_main.py"],
                cwd=self.backend_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.processes["backend"] = process.pid
            self.save_processes()
            
            print(f"✅ 后端服务已启动 (PID: {process.pid})")
            print(f"🌐 服务地址: http://127.0.0.1:8000")
            
            return True
            
        except Exception as e:
            print(f"❌ 启动后端服务失败: {e}")
            return False
    
    def start_frontend(self):
        """启动前端开发服务器"""
        print("🚀 启动前端开发服务器...")
        
        try:
            # 启动前端开发服务器
            process = subprocess.Popen(
                ["npm", "run", "dev"],
                cwd=self.frontend_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.processes["frontend"] = process.pid
            self.save_processes()
            
            print(f"✅ 前端开发服务器已启动 (PID: {process.pid})")
            print(f"🌐 前端地址: http://localhost:5173")
            
            return True
            
        except Exception as e:
            print(f"❌ 启动前端开发服务器失败: {e}")
            return False
    
    def start_tauri(self):
        """启动Tauri开发模式"""
        print("🚀 启动Tauri开发模式...")
        
        try:
            # 启动Tauri开发模式
            process = subprocess.Popen(
                ["npm", "run", "tauri:dev"],
                cwd=self.src_tauri_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.processes["tauri"] = process.pid
            self.save_processes()
            
            print(f"✅ Tauri开发模式已启动 (PID: {process.pid})")
            
            return True
            
        except Exception as e:
            print(f"❌ 启动Tauri开发模式失败: {e}")
            return False
    
    def stop_process(self, name: str):
        """停止指定进程"""
        if name not in self.processes:
            print(f"⚠️ 进程 {name} 未运行")
            return
        
        pid = self.processes[name]
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"✅ 进程 {name} 已停止 (PID: {pid})")
            del self.processes[name]
            self.save_processes()
        except ProcessLookupError:
            print(f"⚠️ 进程 {name} (PID: {pid}) 不存在")
            del self.processes[name]
            self.save_processes()
        except Exception as e:
            print(f"❌ 停止进程 {name} 失败: {e}")
    
    def stop_all(self):
        """停止所有进程"""
        print("🛑 停止所有开发进程...")
        
        for name in list(self.processes.keys()):
            self.stop_process(name)
        
        # 清理PID文件
        if self.pid_file.exists():
            self.pid_file.unlink()
        
        print("✅ 所有进程已停止")
    
    def status(self):
        """显示服务状态"""
        print("📊 开发环境状态:")
        print("-" * 50)
        
        if not self.processes:
            print("❌ 没有运行中的进程")
            return
        
        for name, pid in self.processes.items():
            try:
                os.kill(pid, 0)  # 检查进程是否存在
                print(f"✅ {name}: 运行中 (PID: {pid})")
            except ProcessLookupError:
                print(f"❌ {name}: 已停止 (PID: {pid})")
                del self.processes[name]
        
        self.save_processes()
        
        # 检查服务健康状态
        print("\n🔍 服务健康检查:")
        try:
            import requests
            response = requests.get("http://127.0.0.1:8000/health", timeout=5)
            if response.status_code == 200:
                print("✅ 后端服务健康")
            else:
                print("⚠️ 后端服务响应异常")
        except Exception as e:
            print(f"❌ 后端服务不可用: {e}")
    
    def install_dependencies(self):
        """安装依赖"""
        print("📦 安装依赖...")
        
        # 安装Python依赖
        print("安装Python依赖...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                          check=True, cwd=self.project_root)
            print("✅ Python依赖安装成功")
        except subprocess.CalledProcessError as e:
            print(f"❌ Python依赖安装失败: {e}")
            return False
        
        # 安装前端依赖
        print("安装前端依赖...")
        try:
            subprocess.run(["npm", "install"], check=True, cwd=self.frontend_dir)
            print("✅ 前端依赖安装成功")
        except subprocess.CalledProcessError as e:
            print(f"❌ 前端依赖安装失败: {e}")
            return False
        
        return True

def main():
    if len(sys.argv) < 2:
        print("用法: python dev_desktop.py <command>")
        print("命令:")
        print("  start     - 启动开发环境")
        print("  stop      - 停止开发环境")
        print("  restart   - 重启开发环境")
        print("  status    - 显示状态")
        print("  install   - 安装依赖")
        return 1
    
    manager = DesktopDevManager()
    manager.load_processes()
    
    command = sys.argv[1].lower()
    
    if command == "start":
        print("🚀 启动桌面应用开发环境...")
        
        # 安装依赖
        if not manager.install_dependencies():
            return 1
        
        # 启动服务
        success = True
        success &= manager.start_backend()
        time.sleep(2)  # 等待后端启动
        success &= manager.start_frontend()
        time.sleep(2)  # 等待前端启动
        success &= manager.start_tauri()
        
        if success:
            print("\n🎉 开发环境启动成功！")
            print("📱 桌面应用将自动打开")
            print("🌐 前端开发服务器: http://localhost:5173")
            print("🔧 后端API服务: http://127.0.0.1:8000")
        else:
            print("\n❌ 开发环境启动失败")
            return 1
    
    elif command == "stop":
        manager.stop_all()
    
    elif command == "restart":
        print("🔄 重启开发环境...")
        manager.stop_all()
        time.sleep(2)
        return main()  # 递归调用start
    
    elif command == "status":
        manager.status()
    
    elif command == "install":
        if not manager.install_dependencies():
            return 1
        print("✅ 依赖安装完成")
    
    else:
        print(f"❌ 未知命令: {command}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
