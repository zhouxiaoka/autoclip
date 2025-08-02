"""
Pydantic schemas for data validation and serialization.
Separate from SQLAlchemy models to avoid type annotation conflicts.
"""

from .base import BaseSchema
from .project import ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
from .clip import ClipCreate, ClipUpdate, ClipResponse, ClipListResponse
from .collection import CollectionCreate, CollectionUpdate, CollectionResponse, CollectionListResponse
from .task import TaskCreate, TaskUpdate, TaskResponse, TaskListResponse

__all__ = [
    "BaseSchema",
    "ProjectCreate", "ProjectUpdate", "ProjectResponse", "ProjectListResponse",
    "ClipCreate", "ClipUpdate", "ClipResponse", "ClipListResponse", 
    "CollectionCreate", "CollectionUpdate", "CollectionResponse", "CollectionListResponse",
    "TaskCreate", "TaskUpdate", "TaskResponse", "TaskListResponse"
]