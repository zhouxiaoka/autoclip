"""
Celery应用配置
任务队列配置和初始化
"""

import os
from celery import Celery
from celery.schedules import crontab
from pathlib import Path

# 设置默认配置模块
# os.environ.setdefault('CELERY_CONFIG_MODULE', 'backend.core.celery_app')

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
    worker_concurrency = 1  # 强制设置并发数为1，防止重复处理
    
    # 任务路由
    task_routes = {
        'backend.tasks.processing.*': {'queue': 'processing'},
        'backend.tasks.video.*': {'queue': 'video'},
        'backend.tasks.notification.*': {'queue': 'notification'},
        'backend.tasks.upload.*': {'queue': 'upload'},  # 添加upload任务路由
        'backend.tasks.import_processing.*': {'queue': 'processing'},  # 导入任务路由
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


def _is_desktop_mode() -> bool:
    return os.getenv("AUTOCLIP_DESKTOP_MODE", "").lower() in {"1", "true", "yes"}


class _LocalAsyncResult:
    """轻量级 AsyncResult 替身，桌面模式本地线程执行时返回。"""

    def __init__(self, task_id: str):
        self.id = task_id
        self.task_id = task_id
        self.state = "PENDING"

    def get(self, *args, **kwargs):
        return None

    def ready(self) -> bool:
        return False


class DesktopAwareTask(celery_app.Task):
    """桌面安装包里没有 Redis broker，生产 core.celery_app 又指向 redis://localhost。

    所有端点都用 `task.delay(...)` / `apply_async(...)` 派发任务，默认会把任务塞进
    Redis 队列 —— 桌面模式下没人消费，于是永远卡在 0%「初始化中」。

    这里在桌面模式下把 apply_async 改成「在后台守护线程里同步执行 apply()」：
    不依赖任何 broker，立即返回，进度照常写库供前端轮询。生产模式行为不变。
    """

    def apply_async(self, args=None, kwargs=None, task_id=None, **options):
        if _is_desktop_mode():
            import threading
            import uuid

            tid = task_id or str(uuid.uuid4())
            call_args = list(args) if args else []
            call_kwargs = dict(kwargs) if kwargs else {}

            def _run():
                try:
                    self.apply(args=call_args, kwargs=call_kwargs, task_id=tid)
                except Exception as exc:  # noqa: BLE001
                    import logging
                    logging.getLogger(__name__).error(
                        f"桌面模式本地执行任务失败 {self.name} ({tid}): {exc}", exc_info=True
                    )

            threading.Thread(target=_run, name=f"task-{self.name}", daemon=True).start()
            return _LocalAsyncResult(tid)

        return super().apply_async(args=args, kwargs=kwargs, task_id=task_id, **options)


# 桌面模式下让所有 @celery_app.task 使用上面的本地执行基类
celery_app.Task = DesktopAwareTask

# 自动发现任务
celery_app.autodiscover_tasks([
    'backend.tasks.processing',
    'backend.tasks.video', 
    'backend.tasks.notification',
    'backend.tasks.maintenance',
    'backend.tasks.import_processing'  # 添加导入处理任务
])

if __name__ == '__main__':
    celery_app.start()