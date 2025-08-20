"""
简化的Celery配置
"""

import os
from celery import Celery

# 创建Celery应用
celery_app = Celery('autoclip')

# 基本配置
celery_app.conf.update(
    # 序列化格式
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    
    # Redis配置
    broker_url='redis://localhost:6379/0',
    result_backend='redis://localhost:6379/0',
    
    # 时区
    timezone='Asia/Shanghai',
    enable_utc=True,
    
    # 任务配置
    task_always_eager=False,
    task_eager_propagates=True,
    
    # 工作进程配置
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=True,
    
    # 结果配置
    result_expires=3600,
    task_ignore_result=False,
)

# 自动发现任务
celery_app.autodiscover_tasks([
    'backend.tasks.processing',
    'backend.tasks.video', 
    'backend.tasks.notification',
    'backend.tasks.maintenance'
])

if __name__ == '__main__':
    celery_app.start()