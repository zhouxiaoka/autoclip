"""
任务提交工具
独立的工具函数，避免循环导入问题
"""

import logging
import os
from typing import Dict, Any, Optional
from ..core.celery_app import celery_app

logger = logging.getLogger(__name__)


def _is_desktop_mode() -> bool:
    return os.getenv("AUTOCLIP_DESKTOP_MODE", "").lower() in {"1", "true", "yes"}


def _run_pipeline_locally(project_id: str, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
    """桌面模式：不经过 Redis/Celery broker，直接在后台线程内同步执行流水线任务。

    桌面安装包里没有 Redis，而生产用的 core.celery_app 走 redis://localhost。
    Celery 任务 process_video_pipeline 本身是「在任务内同步跑完整条流水线」
    （asyncio.run(pipeline_adapter...)），不会再派发子任务，所以可以用 .apply()
    在本地线程里直接跑，进度照常写进数据库的 Task 记录供前端轮询。
    """
    import uuid
    import threading

    task_id = str(uuid.uuid4())

    def run():
        try:
            # 延迟导入，避免循环依赖
            from ..tasks.processing import process_video_pipeline
            process_video_pipeline.apply(
                args=[project_id, input_video_path, input_srt_path],
                task_id=task_id,
            )
            logger.info(f"桌面模式本地流水线执行结束: {project_id}, task_id={task_id}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"桌面模式本地流水线执行失败: {project_id}, 错误: {e}", exc_info=True)

    threading.Thread(target=run, name=f"pipeline-{project_id[:8]}", daemon=True).start()
    logger.info(f"桌面模式：已在本地后台线程启动视频流水线 {project_id}, task_id={task_id}")
    return {
        'success': True,
        'task_id': task_id,
        'status': 'PENDING',
        'message': '视频流水线任务已在本地启动',
    }


def submit_video_pipeline_task(project_id: str, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
    """
    提交视频流水线任务

    Args:
        project_id: 项目ID
        input_video_path: 输入视频路径
        input_srt_path: 输入SRT路径

    Returns:
        任务提交结果
    """
    # 桌面模式没有 Redis，走本地线程执行
    if _is_desktop_mode():
        return _run_pipeline_locally(project_id, input_video_path, input_srt_path)

    try:
        logger.info(f"提交视频流水线任务: {project_id}")
        
        # 直接使用celery_app提交任务
        logger.info(f"准备提交任务到队列...")
        logger.info(f"任务名称: backend.tasks.processing.process_video_pipeline")
        logger.info(f"任务参数: {[project_id, input_video_path, input_srt_path]}")
        
        try:
            celery_task = celery_app.send_task(
                'backend.tasks.processing.process_video_pipeline',
                args=[project_id, input_video_path, input_srt_path]
            )
            
            logger.info(f"视频流水线任务已提交: {celery_task.id}")
            logger.info(f"任务状态: {celery_task.state}")
            
            # 检查任务是否真的提交到队列
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            queue_length = r.llen('processing')
            logger.info(f"Redis队列长度: {queue_length}")
            
        except Exception as e:
            logger.error(f"任务提交过程中出现异常: {e}")
            raise
        
        return {
            'success': True,
            'task_id': celery_task.id,
            'status': 'PENDING',
            'message': '视频流水线任务已提交'
        }
        
    except Exception as e:
        logger.error(f"提交视频流水线任务失败: {project_id}, 错误: {e}")
        return {
            'success': False,
            'error': str(e),
            'message': '任务提交失败'
        }

def submit_single_step_task(project_id: str, step: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    提交单个步骤任务
    
    Args:
        project_id: 项目ID
        step: 步骤名称
        config: 处理配置
        
    Returns:
        任务提交结果
    """
    try:
        logger.info(f"提交单个步骤任务: {project_id}, {step}")
        
        # 直接使用celery_app提交任务
        celery_task = celery_app.send_task(
            'tasks.processing.process_single_step',
            args=[project_id, step, config]
        )
        
        logger.info(f"单个步骤任务已提交: {celery_task.id}")
        
        return {
            'success': True,
            'task_id': celery_task.id,
            'step': step,
            'status': 'PENDING',
            'message': f'步骤 {step} 任务已提交'
        }
        
    except Exception as e:
        logger.error(f"提交单个步骤任务失败: {project_id}, {step}, 错误: {e}")
        return {
            'success': False,
            'error': str(e),
            'message': '任务提交失败'
        }
