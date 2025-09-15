"""
合集服务
提供合集相关的业务逻辑操作
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.services.base import BaseService
from backend.repositories.collection_repository import CollectionRepository
from backend.models.collection import Collection
from backend.schemas.collection import CollectionCreate, CollectionUpdate, CollectionResponse, CollectionListResponse, CollectionFilter
from backend.schemas.base import PaginationParams, PaginationResponse


class CollectionService(BaseService[Collection, CollectionCreate, CollectionUpdate, CollectionResponse]):
    """Collection service with business logic."""
    
    def __init__(self, db: Session):
        repository = CollectionRepository(db)
        super().__init__(repository)
        self.db = db
    
    def create_collection(self, collection_data: CollectionCreate) -> Collection:
        """Create a new collection with business logic."""
        collection_dict = collection_data.model_dump()
        return self.create(**collection_dict)
    
    def update_collection(self, collection_id: str, collection_data: CollectionUpdate) -> Optional[Collection]:
        """Update a collection with business logic."""
        update_data = {k: v for k, v in collection_data.model_dump().items() if v is not None}
        if not update_data:
            return self.get(collection_id)
        
        return self.update(collection_id, **update_data)
    
    def get_collections_by_project(self, project_id: str, skip: int = 0, limit: int = 100) -> List[Collection]:
        """Get collections by project ID."""
        return self.repository.find_by(project_id=project_id)
    
    def get_collections_paginated(
        self, 
        pagination: PaginationParams,
        filters: Optional[CollectionFilter] = None
    ) -> CollectionListResponse:
        """Get paginated collections with filtering."""
        # Convert filters to dict
        filter_dict = {}
        if filters:
            filter_data = filters.model_dump()
            filter_dict = {k: v for k, v in filter_data.items() if v is not None}
        
        items, pagination_response = self.get_paginated(pagination, filter_dict)
        
        # Convert to response schemas
        collection_responses = []
        for collection in items:
            # 获取clip_ids
            clip_ids = []
            metadata = getattr(collection, 'collection_metadata', {}) or {}
            if metadata and 'clip_ids' in metadata:
                # 直接使用metadata中的clip_ids，它们已经是UUID格式
                clip_ids = metadata['clip_ids']
            
            collection_responses.append(CollectionResponse(
                id=str(getattr(collection, 'id', '')),
                project_id=str(getattr(collection, 'project_id', '')),
                name=str(getattr(collection, 'name', '')),
                description=str(getattr(collection, 'description', '')) if getattr(collection, 'description', None) else None,
                theme=getattr(collection, 'theme', None),
                status=getattr(collection, 'status', 'created').value if hasattr(getattr(collection, 'status', 'created'), 'value') else str(getattr(collection, 'status', 'created')),
                tags=getattr(collection, 'tags', []) or [],
                metadata=getattr(collection, 'collection_metadata', {}) or {},
                video_path=getattr(collection, 'video_path', None),
                created_at=getattr(collection, 'created_at', None),
                updated_at=getattr(collection, 'updated_at', None),
                total_clips=getattr(collection, 'clips_count', 0) or 0,
                clip_ids=clip_ids
            ))
        
        return CollectionListResponse(
            items=collection_responses,
            pagination=pagination_response
        ) 