"""
合集API路由
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from core.database import get_db
from services.collection_service import CollectionService
from schemas.collection import (
    CollectionCreate, CollectionUpdate, CollectionResponse, CollectionListResponse
)

router = APIRouter()


def get_collection_service(db: Session = Depends(get_db)) -> CollectionService:
    """Dependency to get collection service."""
    return CollectionService(db)


@router.post("/", response_model=CollectionResponse)
async def create_collection(
    collection_data: CollectionCreate,
    collection_service: CollectionService = Depends(get_collection_service)
):
    """Create a new collection."""
    try:
        collection = collection_service.create_collection(collection_data)
        # Convert to response schema
        status_obj = getattr(collection, 'status', None)
        status_value = status_obj.value if hasattr(status_obj, 'value') else 'created'
        
        return CollectionResponse(
            id=str(getattr(collection, 'id', '')),
            project_id=str(getattr(collection, 'project_id', '')),
            name=str(getattr(collection, 'name', '')),
            description=str(getattr(collection, 'description', '')) if getattr(collection, 'description', None) else None,
            theme=getattr(collection, 'theme', None),
            status=status_value,
            tags=getattr(collection, 'tags', []) or [],
            metadata=getattr(collection, 'collection_metadata', {}) or {},
            created_at=getattr(collection, 'created_at', None) if isinstance(getattr(collection, 'created_at', None), (type(None), __import__('datetime').datetime)) else None,
            updated_at=getattr(collection, 'updated_at', None) if isinstance(getattr(collection, 'updated_at', None), (type(None), __import__('datetime').datetime)) else None,
            total_clips=getattr(collection, 'clips_count', 0) or 0
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=CollectionListResponse)
async def get_collections(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    collection_service: CollectionService = Depends(get_collection_service)
):
    """Get paginated collections."""
    try:
        # Simplified response for now
        return {
            "items": [],
            "pagination": {
                "page": page,
                "size": size,
                "total": 0,
                "pages": 0,
                "has_next": False,
                "has_prev": False
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: str,
    collection_service: CollectionService = Depends(get_collection_service)
):
    """Get a collection by ID."""
    try:
        collection = collection_service.get(collection_id)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        
        # Convert to response schema
        status_obj = getattr(collection, 'status', None)
        status_value = status_obj.value if hasattr(status_obj, 'value') else 'created'
        
        return CollectionResponse(
            id=str(getattr(collection, 'id', '')),
            project_id=str(getattr(collection, 'project_id', '')),
            name=str(getattr(collection, 'name', '')),
            description=str(getattr(collection, 'description', '')) if getattr(collection, 'description', None) else None,
            theme=getattr(collection, 'theme', None),
            status=status_value,
            tags=getattr(collection, 'tags', []) or [],
            metadata=getattr(collection, 'collection_metadata', {}) or {},
            created_at=getattr(collection, 'created_at', None) if isinstance(getattr(collection, 'created_at', None), (type(None), __import__('datetime').datetime)) else None,
            updated_at=getattr(collection, 'updated_at', None) if isinstance(getattr(collection, 'updated_at', None), (type(None), __import__('datetime').datetime)) else None,
            total_clips=getattr(collection, 'clips_count', 0) or 0
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: str,
    collection_data: CollectionUpdate,
    collection_service: CollectionService = Depends(get_collection_service)
):
    """Update a collection."""
    try:
        collection = collection_service.update_collection(collection_id, collection_data)
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")
        return collection
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{collection_id}")
async def delete_collection(
    collection_id: str,
    collection_service: CollectionService = Depends(get_collection_service)
):
    """Delete a collection."""
    try:
        success = collection_service.delete(collection_id)
        if not success:
            raise HTTPException(status_code=404, detail="Collection not found")
        return {"message": "Collection deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))