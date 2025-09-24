#!/bin/bash

# Docker容器启动脚本
# 专门为Docker环境设计，解决权限和配置问题

set -euo pipefail

# 设置环境变量
export PYTHONPATH=/app
export PYTHONUNBUFFERED=1

# 确保数据目录存在且有正确权限
mkdir -p /app/data/projects /app/data/uploads /app/data/temp /app/data/output /app/logs

# 如果数据目录为空，创建必要的文件
if [[ ! -f /app/data/autoclip.db ]]; then
    echo "初始化数据库..."
    python -c "
import sys
sys.path.insert(0, '/app')
from backend.core.database import engine, Base
from backend.models import project, task, clip, collection, bilibili
try:
    Base.metadata.create_all(bind=engine)
    print('数据库初始化成功')
except Exception as e:
    print(f'数据库初始化失败: {e}')
    sys.exit(1)
"
fi

# 检查Redis连接
echo "检查Redis连接..."
python -c "
import os
import redis
try:
    redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')
    r = redis.Redis.from_url(redis_url, decode_responses=True)
    r.ping()
    print(f'Redis连接成功: {redis_url}')
except Exception as e:
    print(f'Redis连接失败: {e}')
    print('将使用SQLite作为备选存储')
"

# 启动应用
echo "启动AutoClip应用..."
exec "$@"