#!/bin/bash

# 设置Python路径
export PYTHONPATH=.:$PYTHONPATH

# 激活虚拟环境
source venv/bin/activate

# 启动Celery worker (在backend目录运行)
cd backend
celery -A core.celery_app worker --loglevel=info --concurrency=1