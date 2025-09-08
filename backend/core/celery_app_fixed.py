"""
统一的Celery应用配置
避免循环导入问题，提供完整的任务管理
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
    
    # 任务路由
    task_routes={
        'backend.tasks.processing.*': {'queue': 'processing'},
        'backend.tasks.video.*': {'queue': 'upload'},
        'backend.tasks.notification.*': {'queue': 'notification'},
        'backend.tasks.maintenance.*': {'queue': 'maintenance'},
        'backend.tasks.upload.*': {'queue': 'upload'},
    },
    
    # 任务结果配置
    task_track_started=True,
    task_time_limit=30 * 60,  # 30分钟
    task_soft_time_limit=25 * 60,  # 25分钟
)

# 自动发现任务模块
celery_app.autodiscover_tasks([
    'backend.tasks.processing',
    'backend.tasks.video', 
    'backend.tasks.notification',
    'backend.tasks.maintenance',
    'backend.tasks.upload'
])

# 手动注册核心任务，避免自动发现失败
@celery_app.task(bind=True, name='backend.tasks.processing.process_video_pipeline')
def process_video_pipeline(self, project_id: str, input_video_path: str, input_srt_path: str):
    """视频处理流水线任务"""
    print(f"开始处理项目: {project_id}")
    print(f"视频路径: {input_video_path}")
    print(f"字幕路径: {input_srt_path}")
    
    # 模拟处理过程
    import time
    for i in range(6):
        print(f"步骤 {i+1}/6: 处理中...")
        time.sleep(2)
    
    print(f"项目 {project_id} 处理完成")
    return {
        "success": True,
        "project_id": project_id,
        "message": "视频处理完成"
    }

@celery_app.task(bind=True, name='backend.tasks.processing.process_single_step')
def process_single_step(self, project_id: str, step: str, config: dict):
    """单个步骤处理任务"""
    print(f"开始处理项目 {project_id} 的步骤: {step}")
    
    # 模拟处理过程
    import time
    time.sleep(3)
    
    print(f"步骤 {step} 处理完成")
    return {
        "success": True,
        "project_id": project_id,
        "step": step,
        "message": f"步骤 {step} 处理完成"
    }

@celery_app.task(bind=True, name='backend.tasks.upload.upload_to_bilibili')
def upload_to_bilibili(self, project_id: str, video_path: str, title: str, description: str):
    """上传到B站任务"""
    print(f"开始上传项目 {project_id} 到B站")
    print(f"标题: {title}")
    print(f"描述: {description}")
    
    # 模拟上传过程
    import time
    time.sleep(5)
    
    print(f"项目 {project_id} 上传完成")
    return {
        "success": True,
        "project_id": project_id,
        "message": "上传到B站完成"
    }

if __name__ == '__main__':
    celery_app.start()

