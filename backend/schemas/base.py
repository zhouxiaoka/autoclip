"""
Base schemas for common response patterns.
"""

from datetime import datetime
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PaginationParams(BaseSchema):
    """Pagination parameters for list endpoints."""
    page: int = Field(default=1, ge=1, description="Page number")
    size: int = Field(default=20, ge=1, le=100, description="Page size")
    skip: Optional[int] = Field(default=None, description="Skip records")


class PaginationResponse(BaseSchema):
    """Pagination response metadata."""
    page: int = Field(description="Current page number")
    size: int = Field(description="Page size")
    total: int = Field(description="Total number of records")
    pages: int = Field(description="Total number of pages")
    has_next: bool = Field(description="Whether there is a next page")
    has_prev: bool = Field(description="Whether there is a previous page")


class ErrorResponse(BaseSchema):
    """Standard error response format."""
    error: str = Field(description="Error message")
    detail: Optional[str] = Field(default=None, description="Detailed error information")
    code: Optional[str] = Field(default=None, description="Error code")


class SuccessResponse(BaseSchema):
    """Standard success response format."""
    message: str = Field(description="Success message")
    data: Optional[Any] = Field(default=None, description="Response data")


class HealthResponse(BaseSchema):
    """Health check response."""
    status: str = Field(description="Service status")
    timestamp: datetime = Field(description="Current timestamp")
    version: Optional[str] = Field(default=None, description="API version") 