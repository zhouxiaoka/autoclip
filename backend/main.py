"""FastAPI应用入口点 - Web模式"""

import logging
from backend.app_factory import create_app

# 创建应用实例
app = create_app(mode="web")

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import uvicorn
    import sys
    
    # 默认端口
    port = 8000
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                try:
                    port = int(sys.argv[i + 1])
                except ValueError:
                    logger.error(f"无效的端口号: {sys.argv[i + 1]}")
                    port = 8000
    
    # 默认只听本机；Docker / 局域网访问显式设 AUTOCLIP_HOST=0.0.0.0（Dockerfile 的 CMD 自带 --host）
    import os
    host = os.getenv("AUTOCLIP_HOST", "127.0.0.1")
    logger.info(f"启动服务器，地址: {host}:{port}")
    uvicorn.run(app, host=host, port=port)