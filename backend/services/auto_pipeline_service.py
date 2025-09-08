"""
自动化流水线启动服务
当新项目创建后自动启动视频处理流水线
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from backend.core.database import SessionLocal
from backend.models.project import Project, ProjectStatus
from backend.models.task import Task, TaskStatus
from backend.services.progress_update_service import progress_update_service
# from backend.services.pipeline_adapter import PipelineAdapter  # 临时注释，文件不存在
from backend.utils.task_submission_utils import submit_video_pipeline_task

logger = logging.getLogger(__name__)

class AutoPipelineService:
    """自动化流水线启动服务"""
    
    def __init__(self):
        self.processing_projects = set()
    
    async def auto_start_pipeline(self, project_id: str) -> Dict[str, Any]:
        """
        自动启动项目流水线处理
        
        Args:
            project_id: 项目ID
            
        Returns:
            启动结果
        """
        try:
            logger.info(f"自动启动项目流水线: {project_id}")
            
            # 检查项目是否已经在处理中
            if project_id in self.processing_projects:
                logger.warning(f"项目 {project_id} 已在处理中，跳过")
                return {"status": "skipped", "message": "项目已在处理中"}
            
            # 标记项目为处理中
            self.processing_projects.add(project_id)
            
            # 获取项目信息
            db = SessionLocal()
            try:
                project = db.query(Project).filter(Project.id == project_id).first()
                if not project:
                    raise ValueError(f"项目 {project_id} 不存在")
                
                # 检查项目状态
                if project.status != ProjectStatus.PENDING:
                    logger.info(f"项目 {project_id} 状态为 {project.status}，跳过自动启动")
                    return {"status": "skipped", "message": f"项目状态为 {project.status}"}
                
                # 检查项目文件
                if not project.video_path:
                    raise ValueError(f"项目 {project_id} 没有视频文件")
                
                # 查找字幕文件
                srt_file = self._find_srt_file(project_id)
                if not srt_file:
                    logger.warning(f"项目 {project_id} 没有找到字幕文件，将尝试自动生成")
                
                # 检查是否已有正在运行的任务
                existing_task = db.query(Task).filter(
                    Task.project_id == project_id,
                    Task.name == "自动视频处理流水线",
                    Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
                ).first()
                
                if existing_task:
                    # 使用现有任务
                    task = existing_task
                    logger.info(f"使用现有任务: {task.id}")
                else:
                    # 创建新任务记录
                    task = self._create_processing_task(db, project_id)
                    if not task:
                        raise ValueError("创建任务记录失败")
                
                # 更新项目状态
                project.status = ProjectStatus.PROCESSING
                project.updated_at = datetime.utcnow()
                db.commit()
                
                logger.info(f"项目 {project_id} 状态已更新为处理中")
                
                # 启动进度监控
                await progress_update_service.start_progress_monitoring(task.id)
                
                # 提交Celery任务
                logger.info(f"准备提交Celery任务: {project_id}")
                
                # 查找项目文件路径
                from ..core.config import get_data_directory
                data_dir = get_data_directory()
                project_dir = Path(data_dir) / "projects" / project_id
                input_video_path = str(project_dir / "raw" / "input.mp4")
                input_srt_path = str(project_dir / "raw" / "input.srt")
                
                # 检查文件是否存在
                if not Path(input_video_path).exists():
                    raise ValueError(f"视频文件不存在: {input_video_path}")
                
                logger.info(f"视频文件: {input_video_path}")
                logger.info(f"字幕文件: {input_srt_path if Path(input_srt_path).exists() else '不存在'}")
                
                # 提交Celery任务
                task_result = submit_video_pipeline_task(project_id, input_video_path, input_srt_path)
                logger.info(f"Celery任务提交结果: {task_result}")
                
                if task_result.get('success'):
                    celery_task_id = task_result['task_id']
                    logger.info(f"Celery任务已提交: {celery_task_id}")
                    
                    # 更新任务记录
                    task.celery_task_id = celery_task_id
                    task.status = TaskStatus.RUNNING
                    task.started_at = datetime.utcnow()
                    db.commit()
                    
                    result = {
                        "status": "started",
                        "message": "流水线处理已启动",
                        "project_id": project_id,
                        "task_id": task.id,
                        "celery_task_id": celery_task_id
                    }
                else:
                    error_msg = task_result.get('error', '未知错误')
                    raise ValueError(f"提交Celery任务失败: {error_msg}")
                
                return result
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"自动启动流水线失败: {e}")
            # 移除处理中标记
            self.processing_projects.discard(project_id)
            
            # 更新项目状态为失败
            await self._mark_project_failed(project_id, str(e))
            
            return {"status": "failed", "message": f"启动失败: {str(e)}"}
    
    def _find_srt_file(self, project_id: str) -> Optional[str]:
        """查找项目的字幕文件"""
        try:
            from ..core.path_utils import get_project_directory
            project_dir = get_project_directory(project_id)
            
            # 查找可能的字幕文件
            srt_files = list(project_dir.glob("**/*.srt"))
            if srt_files:
                return str(srt_files[0])
            
            # 查找原始目录
            raw_dir = project_dir / "raw"
            if raw_dir.exists():
                srt_files = list(raw_dir.glob("*.srt"))
                if srt_files:
                    return str(srt_files[0])
            
            return None
            
        except Exception as e:
            logger.warning(f"查找字幕文件失败: {e}")
            return None
    
    def _create_processing_task(self, db: Session, project_id: str) -> Optional[Task]:
        """创建处理任务记录"""
        try:
            task = Task(
                project_id=project_id,
                name="自动视频处理流水线",
                task_type="video_processing",
                status=TaskStatus.PENDING,
                progress=0.0,
                current_step="初始化",
                priority=0,
                metadata={
                    "auto_started": True,
                    "started_at": datetime.utcnow().isoformat()
                }
            )
            
            db.add(task)
            db.commit()
            db.refresh(task)
            
            logger.info(f"创建处理任务: {task.id}")
            return task
            
        except Exception as e:
            logger.error(f"创建任务记录失败: {e}")
            db.rollback()
            return None
    
    async def _mark_project_failed(self, project_id: str, error_message: str):
        """标记项目为失败状态"""
        try:
            db = SessionLocal()
            try:
                project = db.query(Project).filter(Project.id == project_id).first()
                if project:
                    project.status = ProjectStatus.FAILED
                    project.updated_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"项目 {project_id} 已标记为失败")
                    
                    # 从处理中项目集合中移除
                    self.processing_projects.discard(project_id)
                    logger.info(f"项目 {project_id} 已从处理中集合移除")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"标记项目失败状态时出错: {e}")
    
    async def check_and_restart_failed_pipelines(self):
        """检查并重启失败的流水线"""
        try:
            db = SessionLocal()
            try:
                # 查找失败的项目
                failed_projects = db.query(Project).filter(
                    Project.status == ProjectStatus.FAILED
                ).all()
                
                for project in failed_projects:
                    logger.info(f"检查失败项目: {project.id}")
                    
                    # 检查是否有未完成的任务
                    incomplete_tasks = db.query(Task).filter(
                        Task.project_id == project.id,
                        Task.status.in_([TaskStatus.PENDING, TaskStatus.RUNNING])
                    ).all()
                    
                    if not incomplete_tasks:
                        logger.info(f"项目 {project.id} 没有未完成任务，尝试重启")
                        await self.auto_start_pipeline(project.id)
                    else:
                        logger.info(f"项目 {project.id} 仍有未完成任务，跳过重启")
                        
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"检查失败流水线时出错: {e}")
    
    async def auto_start_all_pending_pipelines(self):
        """自动启动所有等待中的流水线"""
        try:
            db = SessionLocal()
            try:
                # 查找所有等待中的项目
                pending_projects = db.query(Project).filter(
                    Project.status == ProjectStatus.PENDING
                ).all()
                
                logger.info(f"找到 {len(pending_projects)} 个等待中的项目")
                
                for project in pending_projects:
                    try:
                        logger.info(f"自动启动项目流水线: {project.id}")
                        result = await self.auto_start_pipeline(project.id)
                        logger.info(f"项目 {project.id} 启动结果: {result}")
                        
                        # 避免同时启动太多项目
                        await asyncio.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"自动启动项目 {project.id} 失败: {e}")
                        continue
                        
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"自动启动所有等待中流水线时出错: {e}")
    
    def get_processing_status(self) -> Dict[str, Any]:
        """获取处理状态"""
        return {
            "processing_projects": list(self.processing_projects),
            "total_processing": len(self.processing_projects)
        }

# 全局实例
auto_pipeline_service = AutoPipelineService()
