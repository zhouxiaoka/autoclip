"""
统一的Celery应用配置
根据环境变量选择桌面版或服务端配置
"""

import os

IS_DESKTOP = os.getenv("AUTOCLIP_DESKTOP_MODE") == "1"

if IS_DESKTOP:
    # 仅桌面模式才使用文件系统 broker / sqlite backend 的轻量 Celery
    from .desktop_celery import celery_app  # noqa: F401
else:
    # 服务端/开发常规模式：Redis 或你配置的 broker/backend
    from celery import Celery

    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    backend_url = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

    celery_app = Celery(__name__, broker=broker_url, backend=backend_url)
    celery_app.conf.update(
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='Asia/Shanghai',
        enable_utc=True,
        task_always_eager=False,  # 服务端模式异步执行
        task_eager_propagates=True,
        result_expires=3600,
        task_ignore_result=False,
        task_routes={
            'backend.tasks.processing.*': {'queue': 'processing'},
            'backend.tasks.video.*': {'queue': 'video'},
            'backend.tasks.notification.*': {'queue': 'notification'},
            'backend.tasks.maintenance.*': {'queue': 'maintenance'},
            'backend.tasks.upload.*': {'queue': 'upload'},
        },
    )

# 自动发现任务
celery_app.autodiscover_tasks([
    'backend.tasks.processing',
    'backend.tasks.video', 
    'backend.tasks.notification',
    'backend.tasks.maintenance',
    'backend.tasks.upload'
])

if __name__ == '__main__':
    celery_app.start()

