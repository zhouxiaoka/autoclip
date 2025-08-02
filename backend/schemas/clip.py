"""
Clip-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field

from .base import BaseSchema, PaginationResponse


class ClipStatus(str, Enum):
    """Clip status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ClipCreate(BaseSchema):
    """Schema for creating a new clip."""
    project_id: str = Field(..., description="Project ID")
    title: str = Field(..., min_length=1, max_length=200, description="Clip title")
    description: str = Field(..., description="Clip description")
    start_time: int = Field(..., ge=0, description="Start time in seconds")
    end_time: int = Field(..., ge=0, description="End time in seconds")
    duration: int = Field(..., ge=0, description="Clip duration in seconds")
    score: Optional[float] = Field(default=None, ge=0, le=10, description="Clip score")
    tags: Optional[List[str]] = Field(default_factory=list, description="Clip tags")
    clip_metadata: Optional[dict] = Field(default_factory=dict, description="Additional metadata")


class ClipUpdate(BaseSchema):
    """Schema for updating a clip."""
    title: Optional[str] = Field(default=None, min_length=1, max_length=200, description="Clip title")
    description: Optional[str] = Field(default=None, description="Clip description")
    start_time: Optional[float] = Field(default=None, ge=0, description="Start time in seconds")
    end_time: Optional[float] = Field(default=None, ge=0, description="End time in seconds")
    score: Optional[float] = Field(default=None, ge=0, le=10, description="Clip score")
    status: Optional[ClipStatus] = Field(default=None, description="Clip status")
    tags: Optional[List[str]] = Field(default=None, description="Clip tags")
    clip_metadata: Optional[dict] = Field(default=None, description="Additional metadata")


class ClipResponse(BaseSchema):
    """Schema for clip response."""
    id: str = Field(description="Clip ID")
    project_id: str = Field(description="Project ID")
    title: str = Field(description="Clip title")
    description: str = Field(description="Clip description")
    start_time: Optional[float] = Field(description="Start time in seconds")
    end_time: Optional[float] = Field(description="End time in seconds")
    duration: Optional[int] = Field(description="Clip duration in seconds")
    score: Optional[float] = Field(description="Clip score")
    status: ClipStatus = Field(description="Clip status")
    tags: List[str] = Field(description="Clip tags")
    clip_metadata: dict = Field(description="Additional metadata")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    
    # Related data
    collection_ids: List[str] = Field(default_factory=list, description="Collection IDs this clip belongs to")


class ClipListResponse(BaseSchema):
    """Schema for clip list response."""
    items: List[ClipResponse] = Field(description="List of clips")
    pagination: PaginationResponse = Field(description="Pagination information")


class ClipFilter(BaseSchema):
    """Schema for clip filtering."""
    project_id: Optional[str] = Field(default=None, description="Filter by project ID")
    status: Optional[ClipStatus] = Field(default=None, description="Filter by status")
    min_score: Optional[float] = Field(default=None, ge=0, description="Minimum score")
    max_score: Optional[float] = Field(default=None, le=10, description="Maximum score")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags")
    search: Optional[str] = Field(default=None, description="Search in title and content")