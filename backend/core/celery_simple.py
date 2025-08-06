"""
简化的Celery应用配置
跳过自动任务发现，避免循环导入问题
"""

import os
from celery import Celery

# 创建简化的Celery应用
celery_app = Celery('autoclip-simple')

# 基础配置
celery_app.conf.update(
    # 任务序列化格式
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    
    # Redis配置
    broker_url=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    result_backend=os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    
    # 任务配置
    task_always_eager=os.getenv('CELERY_ALWAYS_EAGER', 'False').lower() == 'true',
    task_eager_propagates=True,
    
    # 工作进程配置
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=True,
    
    # 结果配置
    result_expires=3600,
    task_ignore_result=False,
)

# 简单的测试任务
@celery_app.task
def test_task(message="Hello from Celery!"):
    """测试任务"""
    return f"Task completed: {message}"

@celery_app.task
def add(x, y):
    """简单的加法任务"""
    return x + y

if __name__ == '__main__':
    celery_app.start()