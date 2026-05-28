"""
桌面模式主启动文件
使用统一的 app_factory 创建应用，支持端口自动分配
"""
import os
import sys
import logging
import signal
import socket
import threading
import time
import uvicorn
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import FastAPI

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

app_data_dir = Path(os.getenv("AUTOCLIP_APP_DIR", "~/Library/Application Support/AutoClip")).expanduser()
app_data_dir.mkdir(parents=True, exist_ok=True)
(app_data_dir / "logs").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("AUTOCLIP_APP_DIR", str(app_data_dir))
os.environ.setdefault("AUTOCLIP_DATA_DIR", str(app_data_dir))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{app_data_dir / 'autoclip.db'}")
os.environ.setdefault("LOG_FILE", str(app_data_dir / "logs" / "backend.log"))

from backend.app_factory import create_app
from backend.core.desktop_config import (
    get_desktop_config, 
    is_desktop_mode, 
    ensure_desktop_directories
)

class DesktopServiceManager:
    """桌面服务管理器，统一管理FastAPI和Celery服务"""
    
    def __init__(self):
        self.config = get_desktop_config()
        self.app: Optional[FastAPI] = None
        self.celery_app = None
        self.celery_worker = None
        self.server_thread: Optional[threading.Thread] = None
        self.is_running = False
        self.start_time: Optional[float] = None
        self.actual_port: Optional[int] = None
        
        # 确保目录存在
        if not ensure_desktop_directories():
            raise RuntimeError("创建桌面目录失败")

        # 设置日志
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志配置"""
        logging.basicConfig(
            level=getattr(logging, self.config.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.config.paths.data_dir / "logs" / "autoclip.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _create_fastapi_app(self) -> FastAPI:
        """创建FastAPI应用"""
        # 使用统一的 app_factory
        app = create_app(mode="desktop")
        
        # 添加桌面专用路由
        @app.get("/desktop/info")
        async def desktop_info():
            """桌面应用信息"""
            return {
                "app_name": self.config.app_name,
                "app_version": self.config.app_version,
                "data_dir": str(self.config.paths.data_dir),
                "config": self.config.dict()
            }
        
        return app
    
    def _start_celery_worker(self):
        """启动Celery Worker"""
        try:
            from backend.desktop_celery import celery_app
            import subprocess
            import os
            
            self.celery_app = celery_app

            if getattr(sys, "frozen", False):
                def run_worker():
                    celery_app.worker_main([
                        "worker",
                        "--loglevel=" + self.config.log_level.lower(),
                        "--concurrency=1",
                        "--pool=solo",
                    ])

                self.celery_worker_thread = threading.Thread(
                    target=run_worker,
                    daemon=True,
                )
                self.celery_worker_thread.start()
                self.logger.info("✅ Celery Worker 以冻结运行时线程模式启动成功")
                return
            
            # 使用subprocess启动Celery Worker，避免信号处理冲突
            self.celery_worker_process = subprocess.Popen([
                sys.executable, '-m', 'celery', '-A', 'backend.desktop_celery', 'worker',
                '--loglevel=' + self.config.log_level.lower(),
                '--concurrency=' + str(self.config.celery_worker_concurrency),
                '--quiet=False'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**os.environ, "AUTOCLIP_DESKTOP_MODE": "true", "AUTOCLIP_MODE": "desktop"})
            
            self.logger.info("✅ Celery Worker 启动成功")
            
        except Exception as e:
            self.logger.error(f"❌ Celery Worker 启动失败: {e}")
            raise
    
    def _start_fastapi_server(self):
        """启动FastAPI服务器"""
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.config.host, 0))
            server_socket.listen(128)
            self.actual_port = server_socket.getsockname()[1]

            config = uvicorn.Config(
                self.app,
                host=self.config.host,
                port=self.actual_port,
                log_level=self.config.log_level.lower(),
                access_log=False
            )
            server = uvicorn.Server(config)

            # 输出端口信息到 stdout（供 Rust 读取）
            print(f"PORT={self.actual_port}", flush=True)
            print(f"BACKEND_URL=http://{self.config.host}:{self.actual_port}", flush=True)
            
            # 将端口写入文件（备用方案）
            port_file = self.config.paths.data_dir / "backend.port"
            with open(port_file, 'w') as f:
                f.write(str(self.actual_port))
            
            self.logger.info(f"🚀 后端服务启动在端口: {self.actual_port}")
            
            # 运行服务器
            server.run(sockets=[server_socket])
            
        except Exception as e:
            self.logger.error(f"❌ FastAPI 服务器启动失败: {e}")
            print(f"BACKEND_ERROR={e}", flush=True)
            self.is_running = False
            if getattr(self, "celery_worker_process", None):
                self.celery_worker_process.terminate()
                self.celery_worker_process = None
            raise
    
    def start(self):
        """启动所有服务"""
        if self.is_running:
            self.logger.warning("服务已在运行中")
            return
        
        try:
            self.start_time = time.time()
            
            # 创建FastAPI应用
            self.app = self._create_fastapi_app()
            
            # 启动Celery Worker
            self._start_celery_worker()
            
            self.is_running = True

            # 启动FastAPI服务器
            self.server_thread = threading.Thread(
                target=self._start_fastapi_server,
                daemon=True
            )
            self.server_thread.start()
            
            self.logger.info(f"🚀 AutoClip Desktop 服务启动成功")
            self.logger.info(f"🌐 API地址: http://{self.config.host}:<dynamic>")
            
        except Exception as e:
            self.logger.error(f"❌ 服务启动失败: {e}")
            self.stop()
            raise
    
    def stop(self):
        """停止所有服务"""
        if not self.is_running:
            return
        
        try:
            self.logger.info("🛑 正在停止服务...")
            
            # 停止Celery Worker进程
            if hasattr(self, 'celery_worker_process') and self.celery_worker_process:
                try:
                    self.celery_worker_process.terminate()
                    # 等待进程优雅退出
                    try:
                        self.celery_worker_process.wait(timeout=5)
                        self.logger.info("✅ Celery Worker 已停止")
                    except subprocess.TimeoutExpired:
                        self.logger.warning("Celery Worker 未能在5秒内停止，强制终止")
                        self.celery_worker_process.kill()
                        self.celery_worker_process.wait()
                except Exception as e:
                    self.logger.error(f"停止Celery Worker失败: {e}")
                finally:
                    self.celery_worker_process = None

            if hasattr(self, 'celery_worker_thread') and self.celery_worker_thread:
                self.celery_worker_thread = None
            
            # 停止FastAPI服务器 - 使用优雅关闭而不是发送信号
            if self.server_thread and self.server_thread.is_alive():
                # 等待服务器线程自然结束
                self.server_thread.join(timeout=5)
                if self.server_thread.is_alive():
                    self.logger.warning("服务器线程未能在5秒内结束")
            
            self.is_running = False
            self.start_time = None
            self.logger.info("✅ 服务已停止")
            
        except Exception as e:
            self.logger.error(f"❌ 停止服务失败: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        return {
            "is_running": self.is_running,
            "start_time": self.start_time,
            "uptime": time.time() - self.start_time if self.start_time else 0,
            "config": {
                "host": self.config.host,
                "port": self.config.port,
                "debug": self.config.debug_mode,
                "version": self.config.app_version
            }
        }
    
    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            import requests
            port = self.actual_port or self.config.port
            response = requests.get(
                f"http://{self.config.host}:{port}/health",
                timeout=5
            )
            
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "response": response.json(),
                    "port": port
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "port": port
                }
                
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "port": self.actual_port or self.config.port
            }

# 全局服务管理器实例
service_manager = None

def get_service_manager() -> DesktopServiceManager:
    """获取服务管理器实例"""
    global service_manager
    if service_manager is None:
        service_manager = DesktopServiceManager()
    return service_manager

def main():
    """主函数"""
    # 设置桌面模式环境变量
    os.environ["AUTOCLIP_DESKTOP_MODE"] = "true"
    os.environ["AUTOCLIP_MODE"] = "desktop"
    
    # 检查桌面模式
    if not is_desktop_mode():
        print("❌ 此应用仅在桌面模式下运行")
        sys.exit(1)
    
    # 获取服务管理器
    manager = get_service_manager()
    config = manager.config
    
    print(f"🚀 启动 AutoClip Desktop v{config.app_version}")
    print(f"📁 数据目录: {config.paths.data_dir}")
    print(f"🌐 服务地址: http://{config.host}:0 (自动分配端口)")
    
    # 设置信号处理
    def signal_handler(signum, frame):
        print(f"\n🛑 收到停止信号 ({signum})，正在关闭服务...")
        if manager.is_running:
            manager.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # 启动服务
        manager.start()
        
        # 保持主线程运行
        while manager.is_running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 收到中断信号，正在关闭服务...")
        manager.stop()
    except Exception as e:
        print(f"❌ 服务运行失败: {e}")
        manager.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
