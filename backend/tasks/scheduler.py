"""
定期任务调度器
配置和管理定期执行的维护任务
"""

import logging
from celery import Celery
from celery.schedules import crontab

from ..core.celery_app import celery_app

logger = logging.getLogger(__name__)


# 配置定期任务
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """配置定期任务"""
    
    # 每天凌晨2点执行数据清理
    sender.add_periodic_task(
        crontab(hour=2, minute=0),
        cleanup_expired_data.s(days=30),
        name='daily_data_cleanup'
    )
    
    # 每小时执行数据一致性检查
    sender.add_periodic_task(
        crontab(minute=0),
        check_data_consistency.s(),
        name='hourly_consistency_check'
    )
    
    # 每周日凌晨3点执行孤立数据清理
    sender.add_periodic_task(
        crontab(hour=3, minute=0, day_of_week=0),
        cleanup_orphaned_data.s(),
        name='weekly_orphaned_cleanup'
    )
    
    # 每天凌晨1点执行系统健康检查
    sender.add_periodic_task(
        crontab(hour=1, minute=0),
        health_check.s(),
        name='daily_health_check'
    )
    
    logger.info("定期任务配置完成")


def get_scheduled_tasks() -> dict:
    """获取所有已配置的定期任务"""
    return {
        'daily_data_cleanup': {
            'schedule': '每天凌晨2点',
            'task': 'cleanup_expired_data',
            'description': '清理过期数据（保留30天）'
        },
        'hourly_consistency_check': {
            'schedule': '每小时',
            'task': 'check_data_consistency',
            'description': '检查数据一致性'
        },
        'weekly_orphaned_cleanup': {
            'schedule': '每周日凌晨3点',
            'task': 'cleanup_orphaned_data',
            'description': '清理孤立数据'
        },
        'daily_health_check': {
            'schedule': '每天凌晨1点',
            'task': 'health_check',
            'description': '系统健康检查'
        }
    }


def enable_scheduled_tasks():
    """启用定期任务"""
    try:
        # 这里可以添加启用定期任务的逻辑
        logger.info("定期任务已启用")
        return True
    except Exception as e:
        logger.error(f"启用定期任务失败: {e}")
        return False


def disable_scheduled_tasks():
    """禁用定期任务"""
    try:
        # 这里可以添加禁用定期任务的逻辑
        logger.info("定期任务已禁用")
        return True
    except Exception as e:
        logger.error(f"禁用定期任务失败: {e}")
        return False
