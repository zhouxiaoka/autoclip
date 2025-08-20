#!/usr/bin/env python3
"""
AutoClip Backend Server Startup Script
解决模块导入问题，确保在正确的Python路径下启动
"""

import os
import sys
import uvicorn
from pathlib import Path

def main():
    # 获取项目根目录
    project_root = Path(__file__).parent.parent
    backend_dir = project_root / "backend"
    
    # 添加backend目录到Python路径
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    
    # 切换到backend目录
    os.chdir(backend_dir)
    
    print("启动AutoClip后端服务...")
    print(f"项目根目录: {project_root}")
    print(f"后端目录: {backend_dir}")
    print(f"当前工作目录: {os.getcwd()}")
    print("服务地址: http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    print("按 Ctrl+C 停止服务")
    
    # 启动服务
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,  # 修改端口避免与其他服务冲突
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main() 