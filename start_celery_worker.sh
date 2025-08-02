#!/bin/bash

# 设置Python路径
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 启动Celery worker
cd backend
celery -A backend.core.celery_app worker --loglevel=info --concurrency=1 