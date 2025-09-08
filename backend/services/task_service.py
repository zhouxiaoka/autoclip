"""
任务服务
提供任务相关的业务逻辑操作
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from ..services.base import BaseService
from ..repositories.task_repository import TaskRepository
from ..models.task import Task
from ..schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskListResponse, TaskFilter
from ..schemas.base import PaginationParams, PaginationResponse


class TaskService(BaseService[Task, TaskCreate, TaskUpdate, TaskResponse]):
    """Task service with business logic."""
    
    def __init__(self, db: Session):
        repository = TaskRepository(db)
        super().__init__(repository)
        self.db = db
    
    def create_task(self, task_data: TaskCreate) -> Task:
        """Create a new task with business logic."""
        data = task_data.model_dump()
        orm_data = {
            "name": data["name"],
            "description": data.get("description"),
            "project_id": data["project_id"],
            "task_type": data["task_type"],
            "priority": data.get("priority", 0),
            "task_config": data.get("task_config", {}),
            "result_data": data.get("metadata", {})
        }
        return self.create(**orm_data)
    
    def update_task(self, task_id: str, task_data: TaskUpdate) -> Optional[Task]:
        """Update a task with business logic."""
        update_data = {k: v for k, v in task_data.model_dump().items() if v is not None}
        if not update_data:
            return self.get(task_id)
        
        return self.update(task_id, **update_data)
    
    def get_tasks_by_project(self, project_id: str, skip: int = 0, limit: int = 100) -> List[Task]:
        """Get tasks by project ID."""
        return self.repository.find_by(project_id=project_id)
    
    def update_task_progress(self, task_id: str, progress: float, status: Optional[str] = None, result: Optional[dict] = None) -> Optional[Task]:
        """Update task progress."""
        update_data = {"progress": progress}
        if status is not None:
            update_data["status"] = status
        if result is not None:
            update_data["result"] = result
        
        return self.update(task_id, **update_data)
    
    def get_tasks(self, skip: int = 0, limit: int = 100, status: Optional[str] = None, project_id: Optional[str] = None) -> List[TaskResponse]:
        """Get tasks with filters."""
        filters = {}
        if status:
            filters["status"] = status
        if project_id:
            filters["project_id"] = project_id
        
        tasks = self.repository.find_all(skip=skip, limit=limit, **filters)
        return [self._convert_to_response(task) for task in tasks]
    
    def get_tasks_by_project_id(self, project_id: str) -> List[TaskResponse]:
        """Get tasks by project ID."""
        tasks = self.repository.find_by(project_id=project_id)
        return [self._convert_to_response(task) for task in tasks]
    
    def get_task_by_id(self, task_id: str) -> Optional[TaskResponse]:
        """Get task by ID."""
        task = self.get(task_id)
        return self._convert_to_response(task) if task else None
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        return self.delete(task_id) is not None
    
    def _convert_to_response(self, task: Task) -> TaskResponse:
        """Convert Task model to TaskResponse schema."""
        return TaskResponse(
            id=task.id,
            project_id=task.project_id,
            name=task.name,
            task_type=task.task_type,
            status=task.status,
            progress=task.progress,
            task_config=task.task_config or {},
            result=task.result_data,
            error_message=task.error_message,
            priority=task.priority,
            metadata=task.task_metadata or {},
            created_at=task.created_at,
            updated_at=task.updated_at,
            started_at=task.started_at,
            completed_at=task.completed_at
        ) 