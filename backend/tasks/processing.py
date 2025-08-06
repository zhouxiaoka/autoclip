"""视频处理Celery任务
包含WebSocket实时通知和Pipeline适配器集成
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional
from celery import current_task
from pathlib import Path

from backend.core.celery_app import celery_app
from backend.services.websocket_notification_service import notification_service
from backend.services.processing_service import ProcessingService
from backend.services.pipeline_adapter import create_pipeline_adapter_sync
from backend.core.database import SessionLocal
from backend.core.progress_manager import get_progress_manager
from backend.models.project import Project, ProjectStatus
from backend.models.task import Task, TaskStatus

logger = logging.getLogger(__name__)

def run_async_notification(coro):
    """运行异步通知的辅助函数"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

@celery_app.task(bind=True, name='backend.tasks.processing.process_video_pipeline')
def process_video_pipeline(self, project_id: int, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
    """
    处理视频流水线任务 - 使用Pipeline适配器
    
    Args:
        project_id: 项目ID
        input_video_path: 输入视频路径
        input_srt_path: 输入SRT路径
        
    Returns:
        处理结果
    """
    task_id = self.request.id
    logger.info(f"开始处理视频流水线: {project_id}, 任务ID: {task_id}")
    
    try:
        # 创建数据库会话
        db = SessionLocal()
        
        try:
            # 创建任务记录
            task = Task(
                name=f"视频处理流水线",
                description=f"处理项目 {project_id} 的完整视频流水线",
                type="pipeline",
                project_id=project_id,
                celery_task_id=task_id,
                status=TaskStatus.RUNNING,
                progress=0,
                current_step="初始化",
                total_steps=6
            )
            db.add(task)
            db.commit()
            db.refresh(task)  # 确保获取到task.id
            
            # 发送开始通知
            run_async_notification(
                notification_service.send_processing_start(project_id, task_id)
            )
            
            # 获取进度管理器
            progress_manager = get_progress_manager(db)
            
            # 创建Pipeline适配器，传入task.id以启用进度管理
            pipeline_adapter = create_pipeline_adapter_sync(db, task.id)
            
            # 执行Pipeline处理
            result = pipeline_adapter.process_project_sync(project_id, input_video_path, input_srt_path)
            
            # 更新任务状态为完成
            task.status = TaskStatus.COMPLETED
            task.progress = 100
            task.current_step = "处理完成"
            task.result = result
            db.commit()
            
            # 发送完成通知
            run_async_notification(
                notification_service.send_processing_complete(project_id, task_id, result)
            )
            
            logger.info(f"视频流水线处理完成: {project_id}")
            return {
                "success": True,
                "project_id": project_id,
                "task_id": task_id,
                "result": result,
                "message": "视频处理流水线完成"
            }
            
        finally:
            db.close()
            
    except Exception as e:
        error_msg = f"视频流水线处理失败: {str(e)}"
        logger.error(error_msg)
        
        # 更新任务状态为失败
        try:
            db = SessionLocal()
            task = db.query(Task).filter(Task.celery_task_id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = error_msg
                db.commit()
            db.close()
        except Exception as db_error:
            logger.error(f"更新任务状态失败: {str(db_error)}")
        
        # 发送错误通知
        run_async_notification(
            notification_service.send_processing_error(project_id, task_id, error_msg)
        )
        
        raise

@celery_app.task(bind=True, name='backend.tasks.processing.process_single_step')
def process_single_step(self, project_id: str, step: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理单个步骤任务
    
    Args:
        project_id: 项目ID
        step: 步骤名称
        config: 处理配置
        
    Returns:
        处理结果
    """
    task_id = self.request.id
    logger.info(f"开始处理单个步骤: {project_id}, 步骤: {step}, 任务ID: {task_id}")
    
    try:
        # 发送开始通知
        run_async_notification(
            notification_service.send_processing_start(project_id, task_id)
        )
        
        # 创建数据库会话
        db = SessionLocal()
        
        try:
            # 创建处理服务
            processing_service = ProcessingService(db)
            
            # 根据步骤类型执行不同的处理
            if step == "outline":
                run_async_notification(
                    notification_service.send_processing_progress(project_id, task_id, 50, "生成大纲")
                )
                result = processing_service.generate_outline(project_id, config)
                
            elif step == "timeline":
                run_async_notification(
                    notification_service.send_processing_progress(project_id, task_id, 50, "提取时间轴")
                )
                result = processing_service.extract_timeline(project_id, config)
                
            elif step == "titles":
                run_async_notification(
                    notification_service.send_processing_progress(project_id, task_id, 50, "生成标题")
                )
                result = processing_service.generate_titles(project_id, config)
                
            elif step == "clips":
                run_async_notification(
                    notification_service.send_processing_progress(project_id, task_id, 50, "视频切片")
                )
                result = processing_service.extract_clips(project_id, config)
                
            elif step == "collections":
                run_async_notification(
                    notification_service.send_processing_progress(project_id, task_id, 50, "生成合集")
                )
                result = processing_service.generate_collections(project_id, config)
                
            else:
                raise Exception(f"未知的步骤类型: {step}")
            
            if not result.get("success"):
                raise Exception(f"步骤 {step} 处理失败: {result.get('error')}")
            
            # 发送完成通知
            run_async_notification(
                notification_service.send_processing_complete(project_id, task_id, result)
            )
            
            logger.info(f"单个步骤处理完成: {project_id}, 步骤: {step}")
            return result
            
        finally:
            db.close()
            
    except Exception as e:
        error_msg = f"单个步骤处理失败: {str(e)}"
        logger.error(error_msg)
        
        # 发送错误通知
        run_async_notification(
            notification_service.send_processing_error(project_id, task_id, error_msg)
        )
        
        raise

@celery_app.task(bind=True, name='backend.tasks.processing.retry_processing_step')
def retry_processing_step(self, project_id: str, step: str, config: Dict[str, Any], 
                         original_task_id: str) -> Dict[str, Any]:
    """
    重试处理步骤任务
    
    Args:
        project_id: 项目ID
        step: 步骤名称
        config: 处理配置
        original_task_id: 原始任务ID
        
    Returns:
        处理结果
    """
    task_id = self.request.id
    logger.info(f"开始重试处理步骤: {project_id}, 步骤: {step}, 任务ID: {task_id}")
    
    try:
        # 发送开始通知
        run_async_notification(
            notification_service.send_processing_start(project_id, task_id)
        )
        
        # 发送重试通知
        run_async_notification(
            notification_service.send_system_notification(
                "retry_started",
                "重试开始",
                f"正在重试步骤: {step}",
                "warning"
            )
        )
        
        # 调用单个步骤处理
        result = process_single_step.apply_async(
            args=[project_id, step, config],
            task_id=task_id
        ).get()
        
        # 发送重试成功通知
        run_async_notification(
            notification_service.send_system_notification(
                "retry_success",
                "重试成功",
                f"步骤 {step} 重试成功",
                "success"
            )
        )
        
        return result
        
    except Exception as e:
        error_msg = f"重试处理步骤失败: {str(e)}"
        logger.error(error_msg)
        
        # 发送重试失败通知
        run_async_notification(
            notification_service.send_error_notification(
                "retry_failed",
                f"步骤 {step} 重试失败",
                {"project_id": project_id, "step": step, "error": str(e)}
            )
        )
        
        raise