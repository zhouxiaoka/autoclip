"""
Task-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, List, Any
from enum import Enum
from pydantic import BaseModel, Field

from .base import BaseSchema, PaginationResponse


class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Task type enumeration."""
    VIDEO_PROCESSING = "video_processing"
    CLIP_GENERATION = "clip_generation"
    COLLECTION_CREATION = "collection_creation"
    EXPORT = "export"
    CLEANUP = "cleanup"


class TaskCreate(BaseSchema):
    """Schema for creating a new task."""
    name: str = Field(..., description="Task name")
    description: Optional[str] = Field(default=None, description="Task description")
    project_id: str = Field(..., description="Project ID")
    task_type: TaskType = Field(..., description="Task type")
    task_config: Optional[dict] = Field(default_factory=dict, description="Task configuration")
    priority: Optional[int] = Field(default=0, description="Task priority")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional metadata")


class TaskUpdate(BaseSchema):
    """Schema for updating a task."""
    status: Optional[TaskStatus] = Field(default=None, description="Task status")
    progress: Optional[float] = Field(default=None, ge=0, le=100, description="Task progress percentage")
    result: Optional[dict] = Field(default=None, description="Task result")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    task_config: Optional[dict] = Field(default=None, description="Task configuration")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata")


class TaskResponse(BaseSchema):
    """Schema for task response."""
    id: str = Field(description="Task ID")
    project_id: str = Field(description="Project ID")
    name: str = Field(description="Task name")
    task_type: TaskType = Field(description="Task type")
    status: TaskStatus = Field(description="Task status")
    progress: float = Field(default=0, description="Task progress percentage")
    task_config: Optional[dict] = Field(default_factory=dict, description="Task configuration")
    result: Optional[dict] = Field(default=None, description="Task result")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    priority: int = Field(default=0, description="Task priority")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")


class TaskListResponse(BaseSchema):
    """Schema for task list response."""
    items: List[TaskResponse] = Field(description="List of tasks")
    pagination: PaginationResponse = Field(description="Pagination information")


class TaskFilter(BaseSchema):
    """Schema for task filtering."""
    project_id: Optional[str] = Field(default=None, description="Filter by project ID")
    task_type: Optional[TaskType] = Field(default=None, description="Filter by task type")
    status: Optional[TaskStatus] = Field(default=None, description="Filter by status")
    min_priority: Optional[int] = Field(default=None, description="Minimum priority")
    max_priority: Optional[int] = Field(default=None, description="Maximum priority")


class TaskProgress(BaseSchema):
    """Schema for task progress update."""
    task_id: int = Field(description="Task ID")
    progress: float = Field(..., ge=0, le=100, description="Progress percentage")
    status: Optional[TaskStatus] = Field(default=None, description="Task status")
    message: Optional[str] = Field(default=None, description="Progress message")
    result: Optional[dict] = Field(default=None, description="Partial result")