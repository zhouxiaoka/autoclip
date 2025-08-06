"""
Project-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field

from .base import BaseSchema, PaginationResponse


class ProjectStatus(str, Enum):
    """Project status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProjectType(str, Enum):
    """Project type enumeration."""
    DEFAULT = "default"
    KNOWLEDGE = "knowledge"
    BUSINESS = "business"
    OPINION = "opinion"
    EXPERIENCE = "experience"
    SPEECH = "speech"
    CONTENT_REVIEW = "content_review"
    ENTERTAINMENT = "entertainment"


class ProjectCreate(BaseSchema):
    """Schema for creating a new project."""
    name: str = Field(..., min_length=1, max_length=200, description="Project name")
    description: Optional[str] = Field(default=None, max_length=1000, description="Project description")
    project_type: ProjectType = Field(..., description="Project type")
    source_url: Optional[str] = Field(default=None, description="Source URL")
    source_file: Optional[str] = Field(default=None, description="Source file path")
    settings: Optional[dict] = Field(default_factory=dict, description="Project settings")


class ProjectUpdate(BaseSchema):
    """Schema for updating a project."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200, description="Project name")
    description: Optional[str] = Field(default=None, max_length=1000, description="Project description")
    status: Optional[ProjectStatus] = Field(default=None, description="Project status")
    settings: Optional[dict] = Field(default=None, description="Project settings")
    processing_config: Optional[dict] = Field(default=None, description="Processing configuration")


class ProjectResponse(BaseSchema):
    """Schema for project response."""
    id: str = Field(description="Project ID")
    name: str = Field(description="Project name")
    description: Optional[str] = Field(description="Project description")
    project_type: ProjectType = Field(description="Project type")
    status: ProjectStatus = Field(description="Project status")
    source_url: Optional[str] = Field(description="Source URL")
    source_file: Optional[str] = Field(description="Source file path")
    settings: dict = Field(description="Project settings")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    completed_at: Optional[datetime] = Field(description="Completion timestamp")
    
    # Statistics
    total_clips: int = Field(default=0, description="Total number of clips")
    total_collections: int = Field(default=0, description="Total number of collections")
    total_tasks: int = Field(default=0, description="Total number of tasks")


class ProjectListResponse(BaseSchema):
    """Schema for project list response."""
    items: List[ProjectResponse] = Field(description="List of projects")
    pagination: PaginationResponse = Field(description="Pagination information")


class ProjectFilter(BaseSchema):
    """Schema for project filtering."""
    status: Optional[ProjectStatus] = Field(default=None, description="Filter by status")
    project_type: Optional[ProjectType] = Field(default=None, description="Filter by project type")
    search: Optional[str] = Field(default=None, description="Search in name and description")