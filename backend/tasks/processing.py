"""
视频处理任务
使用Celery处理视频文件
"""

import os
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from celery import shared_task
from core.celery_simple import celery_app
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from services.processing_orchestrator import ProcessingOrchestrator
from services.pipeline_adapter import PipelineAdapter, create_pipeline_adapter_sync
from core.config import get_data_directory
from core.database import SessionLocal
from models.task import Task, TaskStatus, TaskType
from core.progress_manager import get_progress_manager
from services.websocket_notification_service import WebSocketNotificationService

logger = logging.getLogger(__name__)

# 初始化通知服务
notification_service = WebSocketNotificationService()

def run_async_notification(coro):
    """运行异步通知的辅助函数"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

@celery_app.task(bind=True, name='backend.tasks.processing.process_video_pipeline')
def process_video_pipeline(self, project_id: str, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
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
            # 验证项目是否存在
            from models.project import Project
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"项目 {project_id} 不存在")
            
            logger.info(f"验证项目存在: {project_id}")
            
            # 创建任务记录
            task = Task(
                name=f"视频处理流水线",
                description=f"处理项目 {project_id} 的完整视频流水线",
                task_type=TaskType.VIDEO_PROCESSING,
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
            pipeline_adapter = create_pipeline_adapter_sync(db, task.id, project_id)
            
            # 执行Pipeline处理
            result = pipeline_adapter.process_project_sync(project_id, input_video_path, input_srt_path)
            
            # 根据处理结果更新任务状态
            if result.get('status') == 'failed':
                # 处理失败
                task.status = TaskStatus.FAILED
                task.progress = 100
                task.current_step = "处理失败"
                task.result_data = result
                task.error_message = result.get('message', '处理失败')
                db.commit()
                
                # 发送失败通知
                run_async_notification(
                    notification_service.send_processing_error(project_id, task_id, result.get('message', '处理失败'))
                )
                
                logger.error(f"视频流水线处理失败: {project_id}, 错误: {result.get('message')}")
                return {
                    "success": False,
                    "project_id": project_id,
                    "task_id": task_id,
                    "result": result,
                    "message": "视频处理流水线失败"
                }
            else:
                # 处理成功
                task.status = TaskStatus.COMPLETED
                task.progress = 100
                task.current_step = "处理完成"
                task.result_data = result
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