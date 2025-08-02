#!/usr/bin/env python3
"""
AutoClip Backend Server Startup Script
确保在正确的目录下启动FastAPI服务
"""

import os
import sys
import subprocess
import uvicorn
from pathlib import Path

def main():
    # 确保在backend目录下运行
    backend_dir = Path(__file__).parent
    if os.getcwd() != str(backend_dir):
        print(f"切换到backend目录: {backend_dir}")
        os.chdir(backend_dir)
    
    print("启动AutoClip后端服务...")
    print(f"当前工作目录: {os.getcwd()}")
    print("服务地址: http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    print("按 Ctrl+C 停止服务")
    
    # 启动服务
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

if __name__ == "__main__":
    main() 