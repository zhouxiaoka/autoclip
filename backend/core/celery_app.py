"""
Celery应用配置
任务队列配置和初始化
"""

import os
from celery import Celery
from celery.schedules import crontab
from pathlib import Path

# 设置默认Django设置模块
os.environ.setdefault('CELERY_CONFIG_MODULE', 'backend.core.celery_config')

# 创建Celery应用
celery_app = Celery('autoclip')

# 配置Celery
class CeleryConfig:
    """Celery配置类"""
    
    # 任务序列化格式
    task_serializer = 'json'
    accept_content = ['json']
    result_serializer = 'json'
    timezone = 'Asia/Shanghai'
    enable_utc = True
    
    # Redis配置
    broker_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    result_backend = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # 任务配置
    task_always_eager = os.getenv('CELERY_ALWAYS_EAGER', 'False').lower() == 'true'  # 生产环境异步执行
    task_eager_propagates = True
    
    # 工作进程配置
    worker_prefetch_multiplier = 1
    worker_max_tasks_per_child = 1000
    worker_disable_rate_limits = True
    
    # 任务路由
    task_routes = {
        'backend.tasks.processing.*': {'queue': 'processing'},
        'backend.tasks.video.*': {'queue': 'video'},
        'backend.tasks.notification.*': {'queue': 'notification'},
    }
    
    # 定时任务配置
    beat_schedule = {
        'cleanup-expired-tasks': {
            'task': 'backend.tasks.maintenance.cleanup_expired_tasks',
            'schedule': crontab(hour=2, minute=0),  # 每天凌晨2点
        },
        'health-check': {
            'task': 'backend.tasks.maintenance.health_check',
            'schedule': crontab(minute='*/5'),  # 每5分钟
        },
    }
    
    # 结果配置
    result_expires = 3600  # 1小时
    task_ignore_result = False
    
    # 日志配置
    worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
    worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] [%(task_name)s(%(task_id)s)] %(message)s'

# 应用配置
celery_app.config_from_object(CeleryConfig)

# 自动发现任务
celery_app.autodiscover_tasks([
    'backend.tasks.processing',
    'backend.tasks.video', 
    'backend.tasks.notification',
    'backend.tasks.maintenance'
])

if __name__ == '__main__':
    celery_app.start()