"""
任务服务
提供任务相关的业务逻辑操作
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from services.base import BaseService
from repositories.task_repository import TaskRepository
from models.task import Task
from schemas.task import TaskCreate, TaskUpdate, TaskResponse, TaskListResponse, TaskFilter
from schemas.base import PaginationParams, PaginationResponse


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