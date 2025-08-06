"""
切片服务
提供切片相关的业务逻辑操作
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from backend.services.base import BaseService
from backend.repositories.clip_repository import ClipRepository
from backend.models.clip import Clip
from backend.schemas.clip import ClipCreate, ClipUpdate, ClipResponse, ClipListResponse, ClipFilter
from backend.schemas.base import PaginationParams, PaginationResponse


class ClipService(BaseService[Clip, ClipCreate, ClipUpdate, ClipResponse]):
    """Clip service with business logic."""
    
    def __init__(self, db: Session):
        repository = ClipRepository(db)
        super().__init__(repository)
        self.db = db
    
    def create_clip(self, clip_data: ClipCreate) -> Clip:
        """Create a new clip with business logic."""
        data = clip_data.model_dump()
        orm_data = {
            "project_id": data["project_id"],
            "title": data["title"],
            "description": data["description"],
            "start_time": int(data["start_time"]) if data["start_time"] is not None else 0,
            "end_time": int(data["end_time"]) if data["end_time"] is not None else 0,
            "duration": int(data["duration"]) if data["duration"] is not None else 0,
            "score": data.get("score"),
            "clip_metadata": data.get("clip_metadata", {}),
            "tags": data.get("tags", [])
        }
        return self.create(**orm_data)
    
    def update_clip(self, clip_id: str, clip_data: ClipUpdate) -> Optional[Clip]:
        """Update a clip with business logic."""
        update_data = {k: v for k, v in clip_data.model_dump().items() if v is not None}
        if not update_data:
            return self.get(clip_id)
        
        return self.update(clip_id, **update_data)
    
    def get_clips_by_project(self, project_id: str, skip: int = 0, limit: int = 100) -> List[Clip]:
        """Get clips by project ID."""
        return self.repository.find_by(project_id=project_id)
    
    def get_clips_paginated(
        self, 
        pagination: PaginationParams,
        filters: Optional[ClipFilter] = None
    ) -> ClipListResponse:
        """Get paginated clips with filtering."""
        filter_dict = {}
        if filters:
            filter_data = filters.model_dump()
            filter_dict = {k: v for k, v in filter_data.items() if v is not None}
        
        items, pagination_response = self.get_paginated(pagination, filter_dict)
        
        # Convert to response schemas (simplified)
        clip_responses = []
        for clip in items:
            status_obj = getattr(clip, 'status', None)
            status_value = status_obj.value if hasattr(status_obj, 'value') else 'pending'
            
            clip_responses.append(ClipResponse(
                id=str(clip.id),
                project_id=str(clip.project_id),
                title=str(clip.title),
                description=str(clip.description) if clip.description else None,
                start_time=getattr(clip, 'start_time', 0),
                end_time=getattr(clip, 'end_time', 0),
                score=getattr(clip, 'score', None),
                status=status_value,
                tags=getattr(clip, 'tags', []) or [],
                clip_metadata=getattr(clip, 'clip_metadata', {}) or {},
                created_at=getattr(clip, 'created_at', None) if isinstance(getattr(clip, 'created_at', None), (type(None), __import__('datetime').datetime)) else None,
                updated_at=getattr(clip, 'updated_at', None) if isinstance(getattr(clip, 'updated_at', None), (type(None), __import__('datetime').datetime)) else None,
                collection_ids=[]
            ))
        
        return ClipListResponse(
            items=clip_responses,
            pagination=pagination_response
        ) 