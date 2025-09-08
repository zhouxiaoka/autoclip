"""
基础服务类
提供通用的业务逻辑操作
"""

from typing import Generic, TypeVar, Type, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from ..repositories.base import BaseRepository, ModelType as RepoModelType
from ..schemas.base import BaseSchema, PaginationParams, PaginationResponse


CreateSchemaType = TypeVar("CreateSchemaType")
UpdateSchemaType = TypeVar("UpdateSchemaType")
ResponseSchemaType = TypeVar("ResponseSchemaType")


class BaseService(Generic[RepoModelType, CreateSchemaType, UpdateSchemaType, ResponseSchemaType]):
    """Base service class with common CRUD operations."""
    
    def __init__(self, repository: BaseRepository[RepoModelType]):
        self.repository = repository
    
    def get(self, id: str) -> Optional[RepoModelType]:
        """Get a single record by ID."""
        return self.repository.get_by_id(id)
    
    def get_multi(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RepoModelType]:
        """Get multiple records with optional filtering."""
        if filters:
            return self.repository.find_by(**filters)
        return self.repository.get_all(skip=skip, limit=limit)
    
    def create(self, **kwargs) -> RepoModelType:
        """Create a new record."""
        return self.repository.create(**kwargs)
    
    def update(self, id: str, **kwargs) -> Optional[RepoModelType]:
        """Update an existing record."""
        return self.repository.update(id, **kwargs)
    
    def delete(self, id: str) -> bool:
        """Delete a record by ID."""
        return self.repository.delete(id)
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filtering."""
        if filters:
            return len(self.repository.find_by(**filters))
        return self.repository.count()
    
    def exists(self, id: str) -> bool:
        """Check if a record exists by ID."""
        return self.repository.exists(id)
    
    def get_paginated(
        self,
        pagination: PaginationParams,
        filters: Optional[Dict[str, Any]] = None
    ) -> tuple[List[RepoModelType], PaginationResponse]:
        """Get paginated results."""
        skip = (pagination.page - 1) * pagination.size
        limit = pagination.size
        
        items = self.get_multi(skip=skip, limit=limit, filters=filters)
        total = self.count(filters)
        
        pages = (total + pagination.size - 1) // pagination.size
        has_next = pagination.page < pages
        has_prev = pagination.page > 1
        
        pagination_response = PaginationResponse(
            page=pagination.page,
            size=pagination.size,
            total=total,
            pages=pages,
            has_next=has_next,
            has_prev=has_prev
        )
        
        return items, pagination_response