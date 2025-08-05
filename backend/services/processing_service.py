"""
处理服务
使用三件套框架：配置管理器、适配器、编排器
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from models.task import Task, TaskStatus, TaskType
from repositories.task_repository import TaskRepository
from services.config_manager import ProjectConfigManager, ProcessingStep
from services.pipeline_adapter import PipelineAdapter
from services.processing_orchestrator import ProcessingOrchestrator
from services.processing_context import ProcessingContext
from services.exceptions import ServiceError, ProcessingError, TaskError, ProjectError, handle_service_error
from services.concurrency_manager import with_concurrency_control

logger = logging.getLogger(__name__)


class ProcessingService:
    """处理服务，使用三件套框架"""
    
    def __init__(self, db: Session):
        self.db = db
        self.task_repo = TaskRepository(db)
    
    @handle_service_error
    @with_concurrency_control()
    def start_processing(self, project_id: str, srt_path: Path) -> Dict[str, Any]:
        """
        开始处理项目
        
        Args:
            project_id: 项目ID
            srt_path: SRT文件路径
            
        Returns:
            处理结果
        """
        logger.info(f"开始处理项目: {project_id}")
        
        # 创建处理上下文
        context = ProcessingContext(project_id, "temp_task_id", self.db)
        context.set_srt_path(srt_path)
        context.mark_initialized()
        
        # 创建处理任务
        task = self._create_processing_task(project_id)
        context.task_id = str(task.id)
        
        # 初始化编排器
        orchestrator = ProcessingOrchestrator(project_id, str(task.id), self.db)
        
        # 执行完整流水线
        result = orchestrator.execute_pipeline(srt_path)
        
        context.mark_completed()
        
        # 更新项目状态为已完成
        try:
            from models.project import Project, ProjectStatus
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = ProjectStatus.COMPLETED
                self.db.commit()
                logger.info(f"项目状态已更新为已完成: {project_id}")
        except Exception as e:
            logger.warning(f"更新项目状态失败: {e}")
        
        return {
            "success": True,
            "task_id": task.id,
            "project_id": project_id,
            "result": result,
            "context": context.get_context_summary()
        }
    
    @handle_service_error
    @with_concurrency_control()
    def execute_single_step(self, project_id: str, step: ProcessingStep, 
                           srt_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        执行单个步骤
        
        Args:
            project_id: 项目ID
            step: 处理步骤
            srt_path: SRT文件路径（仅Step1需要）
            
        Returns:
            执行结果
        """
        logger.info(f"执行步骤: {step.value}")
        
        # 创建处理上下文
        context = ProcessingContext(project_id, "temp_task_id", self.db)
        if srt_path:
            context.set_srt_path(srt_path)
        context.mark_initialized()
        
        # 创建任务
        task = self._create_processing_task(project_id, task_type=TaskType.VIDEO_PROCESSING)
        context.task_id = str(task.id)
        
        # 初始化编排器
        orchestrator = ProcessingOrchestrator(project_id, str(task.id), self.db)
        
        # 执行步骤
        kwargs = {}
        if step == ProcessingStep.STEP1_OUTLINE and srt_path:
            kwargs['srt_path'] = srt_path
        
        result = orchestrator.execute_step(step, **kwargs)
        
        context.mark_completed()
        
        return {
            "success": True,
            "task_id": task.id,
            "step": step.value,
            "result": result,
            "context": context.get_context_summary()
        }
    
    @handle_service_error
    def get_processing_status(self, project_id: str, task_id: str) -> Dict[str, Any]:
        """
        获取处理状态
        
        Args:
            project_id: 项目ID
            task_id: 任务ID
            
        Returns:
            处理状态
        """
        orchestrator = ProcessingOrchestrator(project_id, task_id, self.db)
        return orchestrator.get_pipeline_status()
    
    @handle_service_error
    @with_concurrency_control()
    def retry_step(self, project_id: str, task_id: str, step: ProcessingStep,
                   srt_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        重试步骤
        
        Args:
            project_id: 项目ID
            task_id: 任务ID
            step: 处理步骤
            srt_path: SRT文件路径（仅Step1需要）
            
        Returns:
            重试结果
        """
        logger.info(f"重试步骤: {step.value}")
        
        # 创建处理上下文
        context = ProcessingContext(project_id, task_id, self.db)
        if srt_path:
            context.set_srt_path(srt_path)
        context.mark_initialized()
        
        orchestrator = ProcessingOrchestrator(project_id, task_id, self.db)
        
        kwargs = {}
        if step == ProcessingStep.STEP1_OUTLINE and srt_path:
            kwargs['srt_path'] = srt_path
        
        result = orchestrator.retry_step(step, **kwargs)
        
        context.mark_completed()
        
        return {
            "success": True,
            "step": step.value,
            "result": result,
            "context": context.get_context_summary()
        }

    @handle_service_error
    @with_concurrency_control()
    def resume_processing(self, project_id: str, start_step: str, 
                         srt_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        从指定步骤恢复处理
        
        Args:
            project_id: 项目ID
            start_step: 开始步骤名称
            srt_path: SRT文件路径（仅Step1需要）
            
        Returns:
            恢复处理结果
        """
        logger.info(f"从步骤 {start_step} 恢复处理项目: {project_id}")
        
        # 创建处理上下文
        context = ProcessingContext(project_id, "temp_task_id", self.db)
        if srt_path:
            context.set_srt_path(srt_path)
        context.mark_initialized()
        
        # 创建处理任务
        task = self._create_processing_task(project_id)
        context.task_id = str(task.id)
        
        # 初始化编排器
        orchestrator = ProcessingOrchestrator(project_id, str(task.id), self.db)
        
        # 映射步骤名称到ProcessingStep枚举
        step_mapping = {
            "step1_outline": ProcessingStep.STEP1_OUTLINE,
            "step2_timeline": ProcessingStep.STEP2_TIMELINE,
            "step3_scoring": ProcessingStep.STEP3_SCORING,
            "step4_title": ProcessingStep.STEP4_TITLE,
            "step5_clustering": ProcessingStep.STEP5_CLUSTERING,
            "step6_video": ProcessingStep.STEP6_VIDEO
        }
        
        if start_step not in step_mapping:
            raise ValueError(f"无效的步骤名称: {start_step}")
        
        processing_step = step_mapping[start_step]
        
        # 从指定步骤恢复执行
        result = orchestrator.resume_from_step(processing_step, srt_path)
        
        context.mark_completed()
        
        # 更新项目状态为已完成
        try:
            from models.project import Project, ProjectStatus
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = ProjectStatus.COMPLETED
                self.db.commit()
                logger.info(f"项目状态已更新为已完成: {project_id}")
        except Exception as e:
            logger.warning(f"更新项目状态失败: {e}")
        
        return {
            "success": True,
            "task_id": task.id,
            "project_id": project_id,
            "start_step": start_step,
            "result": result,
            "context": context.get_context_summary()
        }
    
    @handle_service_error
    def get_project_config(self, project_id: str) -> Dict[str, Any]:
        """
        获取项目配置
        
        Args:
            project_id: 项目ID
            
        Returns:
            项目配置
        """
        config_manager = ProjectConfigManager(project_id)
        return config_manager.export_config()
    
    @handle_service_error
    def update_project_config(self, project_id: str, config_updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新项目配置
        
        Args:
            project_id: 项目ID
            config_updates: 配置更新
            
        Returns:
            更新结果
        """
        config_manager = ProjectConfigManager(project_id)
        
        # 更新处理参数
        if "processing_params" in config_updates:
            config_manager.update_processing_params(**config_updates["processing_params"])
        
        # 更新LLM配置
        if "llm_config" in config_updates:
            config_manager.update_llm_config(**config_updates["llm_config"])
        
        # 更新步骤配置
        if "steps" in config_updates:
            for step_name, step_config in config_updates["steps"].items():
                config_manager.update_step_config(step_name, **step_config)
        
        return {
            "success": True,
            "message": "配置更新成功"
        }
    
    @handle_service_error
    def validate_project_setup(self, project_id: str) -> Dict[str, Any]:
        """
        验证项目设置
        
        Args:
            project_id: 项目ID
            
        Returns:
            验证结果
        """
        adapter = PipelineAdapter(project_id)
        errors = adapter.validate_pipeline_prerequisites()
        
        if errors:
            return {
                "valid": False,
                "errors": errors
            }
        
        return {
            "valid": True,
            "message": "项目设置验证通过"
        }
    
    def _create_processing_task(self, project_id: str, task_type: TaskType = TaskType.VIDEO_PROCESSING) -> Task:
        """创建处理任务"""
        task_data = {
            "name": f"视频处理任务 - {project_id}",
            "description": f"处理项目 {project_id} 的视频内容",
            "project_id": project_id,
            "task_type": task_type,
            "status": TaskStatus.PENDING,
            "progress": 0.0,
            "metadata": {
                "project_id": project_id,
                "task_type": task_type.value
            }
        }
        
        return self.task_repo.create(**task_data)