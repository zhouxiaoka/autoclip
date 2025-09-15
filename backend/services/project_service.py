"""
项目服务
提供项目相关的业务逻辑操作
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import shutil
import logging
from pathlib import Path

from ..services.base import BaseService
from ..repositories.project_repository import ProjectRepository
from ..models.project import Project
from ..models.task import Task
from ..models.clip import Clip
from ..models.collection import Collection
from ..schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse, ProjectFilter
from ..schemas.base import PaginationParams, PaginationResponse
from ..schemas.project import ProjectType, ProjectStatus
from ..schemas.task import TaskStatus

logger = logging.getLogger(__name__)


class ProjectService(BaseService[Project, ProjectCreate, ProjectUpdate, ProjectResponse]):
    """Project service with business logic."""
    
    def __init__(self, db: Session):
        repository = ProjectRepository(db)
        super().__init__(repository)
        self.db = db
    
    def create_project(self, project_data: ProjectCreate) -> Project:
        """Create a new project with business logic."""
        # Convert Pydantic schema to dict for repository
        project_dict = project_data.model_dump()
        
        # Map Pydantic fields to ORM fields
        orm_data = {
            "name": project_dict["name"],
            "description": project_dict.get("description"),
            "project_type": project_dict.get("project_type", "default").value if hasattr(project_dict.get("project_type", "default"), 'value') else project_dict.get("project_type", "default"),  # Map project_type to project_type
            "video_path": project_dict.get("source_file"),  # Map source_file to video_path
            "processing_config": project_dict.get("settings", {}),  # Map settings to processing_config
            "project_metadata": {"source_url": project_dict.get("source_url")}  # Map source_url to metadata
        }
        
        return self.create(**orm_data)
    
    def update_project(self, project_id: str, project_data: ProjectUpdate) -> Optional[Project]:
        """Update a project with business logic."""
        # Filter out None values
        update_data = {k: v for k, v in project_data.model_dump().items() if v is not None}
        if not update_data:
            return self.get(project_id)
        
        # Map schema fields to ORM fields
        orm_data = {}
        for key, value in update_data.items():
            if key == "settings":
                orm_data["processing_config"] = value
            elif key == "processing_config":
                orm_data["processing_config"] = value
            else:
                orm_data[key] = value
        
        return self.update(project_id, **orm_data)
    
    def get_project_with_stats(self, project_id: str) -> Optional[ProjectResponse]:
        """Get project with statistics."""
        project = self.get(project_id)
        if not project:
            return None
        
        # Get actual statistics from database
        from ..models.clip import Clip
        from ..models.collection import Collection
        from ..models.task import Task
        
        total_clips = self.db.query(Clip).filter(Clip.project_id == project_id).count()
        total_collections = self.db.query(Collection).filter(Collection.project_id == project_id).count()
        total_tasks = self.db.query(Task).filter(Task.project_id == project_id).count()
        
        # Convert to response schema
        return ProjectResponse(
            id=str(getattr(project, 'id', '')),
            name=str(getattr(project, 'name', '')),
            description=str(getattr(project, 'description', '')) if getattr(project, 'description', None) is not None else None,
            project_type=ProjectType(getattr(project, 'project_type').value) if hasattr(project, 'project_type') and getattr(project, 'project_type', None) is not None else ProjectType.DEFAULT,
            status=getattr(project, 'status', ProjectStatus.PENDING),
            source_url=project.project_metadata.get("source_url") if getattr(project, 'project_metadata', None) else None,
            source_file=str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,
            video_path=str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,  # 添加video_path字段供前端使用
            thumbnail=getattr(project, 'thumbnail', None),  # 从数据库获取缩略图
            settings=getattr(project, 'processing_config', {}) or {},
            created_at=self._convert_utc_to_local(getattr(project, 'created_at', None)),
            updated_at=self._convert_utc_to_local(getattr(project, 'updated_at', None)),
            completed_at=self._convert_utc_to_local(getattr(project, 'completed_at', None)),
            total_clips=total_clips,
            total_collections=total_collections,
            total_tasks=total_tasks
        )
    
    def get_projects_paginated(
        self, 
        pagination: PaginationParams,
        filters: Optional[ProjectFilter] = None
    ) -> ProjectListResponse:
        """Get paginated projects with filtering."""
        # Convert filters to dict
        filter_dict = {}
        if filters:
            filter_data = filters.model_dump()
            filter_dict = {k: v for k, v in filter_data.items() if v is not None}
        
        items, pagination_response = self.get_paginated(pagination, filter_dict)
        
        # Convert to response schemas
        project_responses = []
        for project in items:
            # Get actual statistics for each project
            from ..models.clip import Clip
            from ..models.collection import Collection
            from ..models.task import Task
            
            project_id = str(project.id)
            total_clips = self.db.query(Clip).filter(Clip.project_id == project_id).count()
            total_collections = self.db.query(Collection).filter(Collection.project_id == project_id).count()
            total_tasks = self.db.query(Task).filter(Task.project_id == project_id).count()
            
            project_responses.append(ProjectResponse(
                id=str(getattr(project, 'id', '')),
                name=str(getattr(project, 'name', '')),
                description=str(getattr(project, 'description', '')) if getattr(project, 'description', None) is not None else None,
                project_type=ProjectType(getattr(project, 'project_type').value) if hasattr(project, 'project_type') and getattr(project, 'project_type', None) is not None else ProjectType.DEFAULT,
                status=ProjectStatus(getattr(project, 'status').value) if hasattr(project, 'status') and getattr(project, 'status', None) is not None else ProjectStatus.PENDING,
                source_url=project.project_metadata.get("source_url") if getattr(project, 'project_metadata', None) else None,
                source_file=str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,
                video_path=str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,  # 添加video_path字段供前端使用
                thumbnail=getattr(project, 'thumbnail', None),  # 从数据库获取缩略图
                settings=getattr(project, 'processing_config', {}) or {},
                created_at=self._convert_utc_to_local(getattr(project, 'created_at', None)),
                updated_at=self._convert_utc_to_local(getattr(project, 'updated_at', None)),
                completed_at=self._convert_utc_to_local(getattr(project, 'completed_at', None)),
                total_clips=total_clips,
                total_collections=total_collections,
                total_tasks=total_tasks
            ))
        
        return ProjectListResponse(
            items=project_responses,
            pagination=pagination_response
        )
    
    def start_project_processing(self, project_id: str) -> bool:
        """Start processing a project."""
        project = self.get(project_id)
        if not project or project.status != "pending":
            return False
        
        # Update status to processing
        self.update(project_id, status="processing")
        return True
    
    def complete_project(self, project_id: str) -> bool:
        """Mark project as completed."""
        project = self.get(project_id)
        if not project:
            return False
        
        # Update status and completion time
        from datetime import datetime
        self.update(project_id, status="completed", completed_at=datetime.utcnow())
        return True
    
    def fail_project(self, project_id: str, error_message: str = None) -> bool:
        """Mark project as failed."""
        project = self.get(project_id)
        if not project:
            return False
        
        # Update status and add error message to settings
        settings = project.settings or {}
        if error_message:
            settings["error_message"] = error_message
        
        self.update(project_id, status="failed", settings=settings)
        return True
    
    def update_project_status(self, project_id: str, status: str) -> bool:
        """Update project status."""
        project = self.get(project_id)
        if not project:
            return False
        
        # Update status
        self.update(project_id, status=status)
        return True
    
    def _convert_utc_to_local(self, dt):
        """将UTC时间转换为本地时间（SQLite存储时丢失了时区信息）"""
        if dt is None:
            return None
        
        from datetime import datetime, timezone
        import pytz
        
        # 由于SQLite存储时丢失了时区信息，我们假设这些时间是UTC时间
        # 将其转换为本地时间
        local_tz = pytz.timezone('Asia/Shanghai')
        utc_time = dt.replace(tzinfo=timezone.utc)
        local_time = utc_time.astimezone(local_tz)
        
        return local_time
    
    def delete_project_with_files(self, project_id: str) -> bool:
        """
        删除项目及其所有相关数据
        
        Args:
            project_id: 项目ID
            
        Returns:
            是否删除成功
        """
        try:
            # 获取项目信息
            project = self.get(project_id)
            if not project:
                logger.warning(f"项目 {project_id} 不存在")
                return False
            
            logger.info(f"开始删除项目 {project_id}: {project.name}")
            
            # 检查是否有正在运行的任务
            running_tasks = self.db.query(Task).filter(
                Task.project_id == project_id,
                Task.status == TaskStatus.RUNNING
            ).count()
            
            if running_tasks > 0:
                logger.warning(f"项目 {project_id} 有 {running_tasks} 个正在运行的任务，无法删除")
                return False
            
            # 开始事务（如果还没有开始的话）
            if not self.db.in_transaction():
                self.db.begin()
            
            try:
                # 1. 删除相关任务
                task_count = self.db.query(Task).filter(Task.project_id == project_id).count()
                if task_count > 0:
                    self.db.query(Task).filter(Task.project_id == project_id).delete()
                    logger.info(f"删除项目 {project_id} 的 {task_count} 个任务")
                
                # 2. 删除相关切片
                clip_count = self.db.query(Clip).filter(Clip.project_id == project_id).count()
                if clip_count > 0:
                    self.db.query(Clip).filter(Clip.project_id == project_id).delete()
                    logger.info(f"删除项目 {project_id} 的 {clip_count} 个切片")
                
                # 3. 删除相关合集
                collection_count = self.db.query(Collection).filter(Collection.project_id == project_id).count()
                if collection_count > 0:
                    self.db.query(Collection).filter(Collection.project_id == project_id).delete()
                    logger.info(f"删除项目 {project_id} 的 {collection_count} 个合集")
                
                # 4. 删除项目记录
                self.db.query(Project).filter(Project.id == project_id).delete()
                logger.info(f"删除项目 {project_id} 记录")
                
                # 5. 提交事务
                self.db.commit()
                
                # 6. 删除项目文件
                self._delete_project_files(project_id)
                
                # 7. 清理进度数据
                self._cleanup_project_progress(project_id)
                
                logger.info(f"项目 {project_id} 删除成功")
                return True
                
            except Exception as e:
                self.db.rollback()
                logger.error(f"删除项目 {project_id} 数据库操作失败: {str(e)}")
                return False
            
        except Exception as e:
            logger.error(f"删除项目 {project_id} 时发生错误: {str(e)}")
            return False
    
    def _delete_project_files(self, project_id: str):
        """
        删除项目相关的文件
        
        Args:
            project_id: 项目ID
        """
        try:
            # 项目目录路径
            project_dir = Path(f"data/projects/{project_id}")
            
            if project_dir.exists():
                logger.info(f"删除项目目录: {project_dir}")
                shutil.rmtree(project_dir)
            else:
                logger.info(f"项目目录不存在: {project_dir}")
            
            # 删除全局输出目录中的相关文件（如果存在）
            # 注意：现在主要使用项目内目录，但保留对全局目录的清理以防遗留文件
            from ..core.path_utils import get_data_directory
            data_dir = get_data_directory()
            global_clips_dir = data_dir / "output" / "clips"
            global_collections_dir = data_dir / "output" / "collections"
            
            # 删除全局输出目录中属于该项目的切片文件
            if global_clips_dir.exists():
                for clip_file in global_clips_dir.glob(f"*_{project_id}*"):
                    try:
                        clip_file.unlink()
                        logger.info(f"删除全局切片文件: {clip_file}")
                    except Exception as e:
                        logger.warning(f"删除全局切片文件失败 {clip_file}: {e}")
            
            # 删除全局输出目录中属于该项目的合集文件
            if global_collections_dir.exists():
                for collection_file in global_collections_dir.glob(f"*_{project_id}*"):
                    try:
                        collection_file.unlink()
                        logger.info(f"删除全局合集文件: {collection_file}")
                    except Exception as e:
                        logger.warning(f"删除全局合集文件失败 {collection_file}: {e}")
            
        except Exception as e:
            logger.error(f"删除项目文件时发生错误: {str(e)}")
            # 不抛出异常，让数据库删除继续进行
    
    def _cleanup_project_progress(self, project_id: str):
        """
        清理项目相关的进度数据
        
        Args:
            project_id: 项目ID
        """
        try:
            # 清理Redis中的进度数据
            try:
                from ..services.simple_progress import clear_progress
                clear_progress(project_id)
                logger.info(f"清理项目 {project_id} 的Redis进度数据")
            except Exception as e:
                logger.warning(f"清理Redis进度数据失败: {e}")
            
            # 清理增强进度服务中的缓存
            try:
                from ..services.enhanced_progress_service import progress_service
                if project_id in progress_service.progress_cache:
                    del progress_service.progress_cache[project_id]
                    logger.info(f"清理项目 {project_id} 的内存进度缓存")
            except Exception as e:
                logger.warning(f"清理内存进度缓存失败: {e}")
            
        except Exception as e:
            logger.error(f"清理项目进度数据失败: {str(e)}")
    
 