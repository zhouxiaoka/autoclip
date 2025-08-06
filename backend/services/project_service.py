"""
项目服务
提供项目相关的业务逻辑操作
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from services.base import BaseService
from repositories.project_repository import ProjectRepository
from models.project import Project
from schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse, ProjectFilter
from schemas.base import PaginationParams, PaginationResponse
from schemas.project import ProjectType, ProjectStatus


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
            "project_type": project_dict.get("project_type", "default"),  # Map project_type to project_type
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
        
        # Convert to response schema (simplified for now)
        return ProjectResponse(
            id=str(getattr(project, 'id', '')),
            name=str(getattr(project, 'name', '')),
            description=str(getattr(project, 'description', '')) if getattr(project, 'description', None) is not None else None,
            project_type=ProjectType(getattr(project, 'project_type').value) if hasattr(project, 'project_type') and getattr(project, 'project_type', None) is not None else ProjectType.DEFAULT,
            status=ProjectStatus(getattr(project, 'status').value) if hasattr(project, 'status') and getattr(project, 'status', None) is not None else ProjectStatus.PENDING,
            source_url=project.project_metadata.get("source_url") if getattr(project, 'project_metadata', None) else None,
            source_file=str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,
            settings=getattr(project, 'processing_config', {}) or {},
            created_at=getattr(project, 'created_at', None) if isinstance(getattr(project, 'created_at', None), (type(None), __import__('datetime').datetime)) else None,
            updated_at=getattr(project, 'updated_at', None) if isinstance(getattr(project, 'updated_at', None), (type(None), __import__('datetime').datetime)) else None,
            completed_at=getattr(project, 'completed_at', None) if isinstance(getattr(project, 'completed_at', None), (type(None), __import__('datetime').datetime)) else None,
            total_clips=0,
            total_collections=0,
            total_tasks=0
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
            project_responses.append(ProjectResponse(
                id=str(getattr(project, 'id', '')),
                name=str(getattr(project, 'name', '')),
                description=str(getattr(project, 'description', '')) if getattr(project, 'description', None) is not None else None,
                project_type=ProjectType(getattr(project, 'project_type').value) if hasattr(project, 'project_type') and getattr(project, 'project_type', None) is not None else ProjectType.DEFAULT,
                status=ProjectStatus(getattr(project, 'status').value) if hasattr(project, 'status') and getattr(project, 'status', None) is not None else ProjectStatus.PENDING,
                source_url=project.project_metadata.get("source_url") if getattr(project, 'project_metadata', None) else None,
                source_file=str(getattr(project, 'video_path', '')) if getattr(project, 'video_path', None) is not None else None,
                settings=getattr(project, 'processing_config', {}) or {},
                created_at=getattr(project, 'created_at', None) if isinstance(getattr(project, 'created_at', None), (type(None), __import__('datetime').datetime)) else None,
                updated_at=getattr(project, 'updated_at', None) if isinstance(getattr(project, 'updated_at', None), (type(None), __import__('datetime').datetime)) else None,
                completed_at=getattr(project, 'completed_at', None) if isinstance(getattr(project, 'completed_at', None), (type(None), __import__('datetime').datetime)) else None,
                total_clips=0,
                total_collections=0,
                total_tasks=0
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