"""
任务队列管理服务
管理Celery任务的提交、监控和状态查询
"""

import logging
from typing import Dict, Any, Optional, List
from celery.result import AsyncResult
from sqlalchemy.orm import Session

from core.celery_app import celery_app
from core.database import SessionLocal
from models.task import Task, TaskStatus, TaskType
from repositories.task_repository import TaskRepository
from tasks.processing import process_video_pipeline, process_single_step, retry_processing_step
from tasks.video import extract_video_clips, generate_video_collections, optimize_video_quality
from tasks.notification import send_processing_notification, send_error_notification, send_completion_notification
from tasks.maintenance import cleanup_expired_tasks, health_check, backup_project_data

logger = logging.getLogger(__name__)


class TaskQueueService:
    """任务队列管理服务"""
    
    def __init__(self, db: Session):
        self.db = db
        self.task_repo = TaskRepository(db)
    
    def submit_video_processing_task(self, project_id: str, srt_path: str) -> Dict[str, Any]:
        """
        提交视频处理任务
        
        Args:
            project_id: 项目ID
            srt_path: SRT文件路径
            
        Returns:
            任务提交结果
        """
        logger.info(f"提交视频处理任务: {project_id}")
        
        try:
            # 创建并保存任务记录
            task = self.task_repo.create(
                project_id=project_id,
                name="视频流水线处理",
                description=f"处理项目 {project_id} 的视频流水线",
                task_type=TaskType.VIDEO_PROCESSING,
                status=TaskStatus.PENDING,
                priority=1
            )
            
            # 提交Celery任务
            celery_task = process_video_pipeline.delay(project_id, srt_path)
            
            # 更新任务记录
            task.celery_task_id = celery_task.id
            self.db.commit()
            
            logger.info(f"视频处理任务已提交: {task.id}, Celery任务ID: {celery_task.id}")
            
            return {
                'success': True,
                'task_id': task.id,
                'celery_task_id': celery_task.id,
                'status': 'PENDING',
                'message': '视频处理任务已提交'
            }
            
        except Exception as e:
            logger.error(f"提交视频处理任务失败: {project_id}, 错误: {e}")
            raise
    
    def submit_single_step_task(self, project_id: str, step_name: str, srt_path: Optional[str] = None) -> Dict[str, Any]:
        """
        提交单个步骤处理任务
        
        Args:
            project_id: 项目ID
            step_name: 步骤名称
            srt_path: SRT文件路径（仅Step1需要）
            
        Returns:
            任务提交结果
        """
        logger.info(f"提交单个步骤任务: {project_id}, {step_name}")
        
        try:
            # 创建并保存任务记录
            task = self.task_repo.create(
                project_id=project_id,
                name=f"步骤处理: {step_name}",
                description=f"处理项目 {project_id} 的步骤 {step_name}",
                task_type=TaskType.VIDEO_PROCESSING,
                status=TaskStatus.PENDING,
                priority=2
            )
            
            # 提交Celery任务
            celery_task = process_single_step.delay(project_id, step_name, srt_path)
            
            # 更新任务记录
            task.celery_task_id = celery_task.id
            self.db.commit()
            
            logger.info(f"单个步骤任务已提交: {task.id}, Celery任务ID: {celery_task.id}")
            
            return {
                'success': True,
                'task_id': task.id,
                'celery_task_id': celery_task.id,
                'step': step_name,
                'status': 'PENDING',
                'message': f'步骤 {step_name} 处理任务已提交'
            }
            
        except Exception as e:
            logger.error(f"提交单个步骤任务失败: {project_id}, {step_name}, 错误: {e}")
            raise
    
    def submit_retry_task(self, project_id: str, task_id: str, step_name: str, srt_path: Optional[str] = None) -> Dict[str, Any]:
        """
        提交重试任务
        
        Args:
            project_id: 项目ID
            task_id: 任务ID
            step_name: 步骤名称
            srt_path: SRT文件路径（仅Step1需要）
            
        Returns:
            任务提交结果
        """
        logger.info(f"提交重试任务: {project_id}, {task_id}, {step_name}")
        
        try:
            # 创建并保存任务记录
            task = self.task_repo.create(
                project_id=project_id,
                name=f"重试步骤: {step_name}",
                description=f"重试项目 {project_id} 的步骤 {step_name}",
                task_type=TaskType.VIDEO_PROCESSING,
                status=TaskStatus.PENDING,
                priority=3
            )
            
            # 提交Celery任务
            celery_task = retry_processing_step.delay(project_id, task_id, step_name, srt_path)
            
            # 更新任务记录
            task.celery_task_id = celery_task.id
            self.db.commit()
            
            logger.info(f"重试任务已提交: {task.id}, Celery任务ID: {celery_task.id}")
            
            return {
                'success': True,
                'task_id': task.id,
                'celery_task_id': celery_task.id,
                'original_task_id': task_id,
                'step': step_name,
                'status': 'PENDING',
                'message': f'步骤 {step_name} 重试任务已提交'
            }
            
        except Exception as e:
            logger.error(f"提交重试任务失败: {project_id}, {task_id}, {step_name}, 错误: {e}")
            raise
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息
        """
        try:
            # 获取数据库任务记录
            task = self.task_repo.get_by_id(task_id)
            if not task:
                return {'error': '任务不存在'}
            
            # 获取Celery任务状态
            celery_status = {}
            if task.celery_task_id:
                celery_result = AsyncResult(task.celery_task_id, app=celery_app)
                celery_status = {
                    'celery_task_id': task.celery_task_id,
                    'celery_status': celery_result.status,
                    'celery_result': celery_result.result if celery_result.ready() else None,
                    'celery_info': celery_result.info if hasattr(celery_result, 'info') else None
                }
            
            return {
                'task_id': task.id,
                'project_id': task.project_id,
                'name': task.name,
                'status': task.status.value,
                'task_type': task.task_type.value,
                'progress': task.progress,
                'error_message': task.error_message,
                'result': task.result_data,
                'created_at': task.created_at.isoformat(),
                'updated_at': task.updated_at.isoformat(),
                'celery_status': celery_status
            }
            
        except Exception as e:
            logger.error(f"获取任务状态失败: {task_id}, 错误: {e}")
            return {'error': f'获取任务状态失败: {e}'}
    
    def get_project_tasks(self, project_id: str) -> List[Dict[str, Any]]:
        """
        获取项目的所有任务
        
        Args:
            project_id: 项目ID
            
        Returns:
            任务列表
        """
        try:
            tasks = self.task_repo.get_by_project(project_id)
            return [
                {
                    'task_id': task.id,
                    'name': task.name,
                    'status': task.status.value,
                    'task_type': task.task_type.value,
                    'progress': task.progress,
                    'created_at': task.created_at.isoformat(),
                    'updated_at': task.updated_at.isoformat()
                }
                for task in tasks
            ]
            
        except Exception as e:
            logger.error(f"获取项目任务失败: {project_id}, 错误: {e}")
            return []
    
    def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            取消结果
        """
        try:
            task = self.task_repo.get_by_id(task_id)
            if not task:
                return {'error': '任务不存在'}
            
            # 取消Celery任务
            if task.celery_task_id:
                celery_result = AsyncResult(task.celery_task_id, app=celery_app)
                celery_result.revoke(terminate=True)
            
            # 更新任务状态
            task.status = TaskStatus.CANCELLED
            self.db.commit()
            
            logger.info(f"任务已取消: {task_id}")
            return {
                'success': True,
                'task_id': task_id,
                'status': 'CANCELLED',
                'message': '任务已取消'
            }
            
        except Exception as e:
            logger.error(f"取消任务失败: {task_id}, 错误: {e}")
            return {'error': f'取消任务失败: {e}'}
    
    def submit_video_clips_task(self, project_id: str, clip_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        提交视频片段提取任务
        
        Args:
            project_id: 项目ID
            clip_data: 片段数据
            
        Returns:
            任务提交结果
        """
        logger.info(f"提交视频片段提取任务: {project_id}")
        
        try:
            # 创建并保存任务记录
            task = self.task_repo.create(
                project_id=project_id,
                name="视频片段提取",
                description=f"提取项目 {project_id} 的视频片段",
                task_type=TaskType.VIDEO_PROCESSING,
                status=TaskStatus.PENDING,
                priority=2
            )
            
            # 提交Celery任务
            celery_task = extract_video_clips.delay(project_id, clip_data)
            
            # 更新任务记录
            task.celery_task_id = celery_task.id
            self.db.commit()
            
            logger.info(f"视频片段提取任务已提交: {task.id}, Celery任务ID: {celery_task.id}")
            
            return {
                'success': True,
                'task_id': task.id,
                'celery_task_id': celery_task.id,
                'clip_count': len(clip_data),
                'status': 'PENDING',
                'message': f'视频片段提取任务已提交，共 {len(clip_data)} 个片段'
            }
            
        except Exception as e:
            logger.error(f"提交视频片段提取任务失败: {project_id}, 错误: {e}")
            raise
    
    def submit_collection_generation_task(self, project_id: str, collection_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        提交合集生成任务
        
        Args:
            project_id: 项目ID
            collection_data: 合集数据
            
        Returns:
            任务提交结果
        """
        logger.info(f"提交合集生成任务: {project_id}")
        
        try:
            # 创建并保存任务记录
            task = self.task_repo.create(
                project_id=project_id,
                name="视频合集生成",
                description=f"生成项目 {project_id} 的视频合集",
                task_type=TaskType.VIDEO_PROCESSING,
                status=TaskStatus.PENDING,
                priority=2
            )
            
            # 提交Celery任务
            celery_task = generate_video_collections.delay(project_id, collection_data)
            
            # 更新任务记录
            task.celery_task_id = celery_task.id
            self.db.commit()
            
            logger.info(f"合集生成任务已提交: {task.id}, Celery任务ID: {celery_task.id}")
            
            return {
                'success': True,
                'task_id': task.id,
                'celery_task_id': celery_task.id,
                'collection_count': len(collection_data),
                'status': 'PENDING',
                'message': f'视频合集生成任务已提交，共 {len(collection_data)} 个合集'
            }
            
        except Exception as e:
            logger.error(f"提交合集生成任务失败: {project_id}, 错误: {e}")
            raise 