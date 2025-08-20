#!/bin/bash

# 设置Python路径
export PYTHONPATH=.:$PYTHONPATH

# 激活虚拟环境
source venv/bin/activate

# 启动Celery worker (在项目根目录运行)
celery -A backend.core.celery_simple worker --loglevel=info --concurrency=1