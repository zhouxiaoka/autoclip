"""
切片API路由
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from core.database import get_db
from services.clip_service import ClipService
from schemas.clip import ClipCreate, ClipUpdate, ClipResponse, ClipListResponse, ClipStatus
from schemas.base import PaginationParams

router = APIRouter()


def get_clip_service(db: Session = Depends(get_db)) -> ClipService:
    """Dependency to get clip service."""
    return ClipService(db)


@router.post("/", response_model=ClipResponse)
async def create_clip(
    clip_data: ClipCreate,
    clip_service: ClipService = Depends(get_clip_service)
):
    """Create a new clip."""
    try:
        clip = clip_service.create_clip(clip_data)
        # Convert to response schema
        status_obj = getattr(clip, 'status', None)
        status_value = status_obj.value if hasattr(status_obj, 'value') else 'pending'
        
        return ClipResponse(
            id=str(getattr(clip, 'id', '')),
            project_id=str(getattr(clip, 'project_id', '')),
            title=str(getattr(clip, 'title', '')),
            description=str(getattr(clip, 'description', '')) if getattr(clip, 'description', None) else None,
            start_time=getattr(clip, 'start_time', 0),
            end_time=getattr(clip, 'end_time', 0),
            duration=getattr(clip, 'duration', 0),
            score=getattr(clip, 'score', None),
            status=status_value,
            tags=getattr(clip, 'tags', []) or [],
            clip_metadata=getattr(clip, 'clip_metadata', {}) or {},
            created_at=getattr(clip, 'created_at', None) if isinstance(getattr(clip, 'created_at', None), (type(None), __import__('datetime').datetime)) else None,
            updated_at=getattr(clip, 'updated_at', None) if isinstance(getattr(clip, 'updated_at', None), (type(None), __import__('datetime').datetime)) else None,
            collection_ids=[]
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=ClipListResponse)
async def get_clips(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    status: Optional[ClipStatus] = Query(None, description="Filter by status"),
    clip_service: ClipService = Depends(get_clip_service)
):
    """Get paginated clips with optional filtering."""
    try:
        pagination = PaginationParams(page=page, size=size)
        
        filters = None
        if project_id or status:
            filters = ClipFilter(
                project_id=project_id,
                status=status
            )
        
        return clip_service.get_clips_paginated(pagination, filters)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{clip_id}", response_model=ClipResponse)
async def get_clip(
    clip_id: str,
    clip_service: ClipService = Depends(get_clip_service)
):
    """Get a clip by ID."""
    try:
        clip = clip_service.get(clip_id)
        if not clip:
            raise HTTPException(status_code=404, detail="Clip not found")
        return clip
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{clip_id}", response_model=ClipResponse)
async def update_clip(
    clip_id: str,
    clip_data: ClipUpdate,
    clip_service: ClipService = Depends(get_clip_service)
):
    """Update a clip."""
    try:
        clip = clip_service.update_clip(clip_id, clip_data)
        if not clip:
            raise HTTPException(status_code=404, detail="Clip not found")
        return clip
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{clip_id}")
async def delete_clip(
    clip_id: str,
    clip_service: ClipService = Depends(get_clip_service)
):
    """Delete a clip."""
    try:
        success = clip_service.delete(clip_id)
        if not success:
            raise HTTPException(status_code=404, detail="Clip not found")
        return {"message": "Clip deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))