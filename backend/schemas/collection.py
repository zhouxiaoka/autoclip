"""
Collection-related Pydantic schemas.
"""

from datetime import datetime
from typing import Optional, List, Any
from enum import Enum
from pydantic import BaseModel, Field

from .base import BaseSchema, PaginationResponse


class CollectionStatus(str, Enum):
    """Collection status enumeration."""
    CREATED = "created"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"
    DELETED = "deleted"


class CollectionCreate(BaseSchema):
    """Schema for creating a new collection."""
    project_id: str = Field(..., description="Project ID")
    name: str = Field(..., min_length=1, max_length=200, description="Collection name")
    description: Optional[str] = Field(default=None, max_length=1000, description="Collection description")
    theme: Optional[str] = Field(default=None, max_length=100, description="Collection theme")
    tags: Optional[List[str]] = Field(default_factory=list, description="Collection tags")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional metadata")


class CollectionUpdate(BaseSchema):
    """Schema for updating a collection."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200, description="Collection name")
    description: Optional[str] = Field(default=None, max_length=1000, description="Collection description")
    theme: Optional[str] = Field(default=None, max_length=100, description="Collection theme")
    status: Optional[CollectionStatus] = Field(default=None, description="Collection status")
    tags: Optional[List[str]] = Field(default=None, description="Collection tags")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata")


class CollectionResponse(BaseSchema):
    """Schema for collection response."""
    id: str = Field(description="Collection ID")
    project_id: str = Field(description="Project ID")
    name: str = Field(description="Collection name")
    description: Optional[str] = Field(description="Collection description")
    theme: Optional[str] = Field(description="Collection theme")
    status: CollectionStatus = Field(description="Collection status")
    tags: List[str] = Field(description="Collection tags")
    metadata: dict = Field(description="Additional metadata")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    
    # Statistics
    total_clips: int = Field(default=0, description="Total number of clips in collection")
    
    # Clip IDs for frontend compatibility
    clip_ids: List[str] = Field(default_factory=list, description="List of clip IDs in this collection")


class CollectionListResponse(BaseSchema):
    """Schema for collection list response."""
    items: List[CollectionResponse] = Field(description="List of collections")
    pagination: PaginationResponse = Field(description="Pagination information")


class CollectionWithClipsResponse(CollectionResponse):
    """Schema for collection response with clips."""
    clips: List[Any] = Field(description="Clips in this collection")


class CollectionFilter(BaseSchema):
    """Schema for collection filtering."""
    project_id: Optional[str] = Field(default=None, description="Filter by project ID")
    status: Optional[CollectionStatus] = Field(default=None, description="Filter by status")
    theme: Optional[str] = Field(default=None, description="Filter by theme")
    tags: Optional[List[str]] = Field(default=None, description="Filter by tags")
    search: Optional[str] = Field(default=None, description="Search in name and description")