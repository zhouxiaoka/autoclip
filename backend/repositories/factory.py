"""
Repository工厂
提供统一的Repository实例化和管理
"""

from typing import Dict, Type
from sqlalchemy.orm import Session
from ..repositories.base import BaseRepository
from ..repositories.project_repository import ProjectRepository
from ..repositories.clip_repository import ClipRepository
from ..repositories.collection_repository import CollectionRepository
from ..repositories.task_repository import TaskRepository

class RepositoryFactory:
    """Repository工厂类"""
    
    def __init__(self, db: Session):
        """
        初始化Repository工厂
        
        Args:
            db: 数据库会话
        """
        self.db = db
        self._repositories: Dict[str, BaseRepository] = {}
    
    def get_project_repository(self) -> ProjectRepository:
        """获取项目Repository"""
        if "project" not in self._repositories:
            self._repositories["project"] = ProjectRepository(self.db)
        return self._repositories["project"]
    
    def get_clip_repository(self) -> ClipRepository:
        """获取切片Repository"""
        if "clip" not in self._repositories:
            self._repositories["clip"] = ClipRepository(self.db)
        return self._repositories["clip"]
    
    def get_collection_repository(self) -> CollectionRepository:
        """获取合集Repository"""
        if "collection" not in self._repositories:
            self._repositories["collection"] = CollectionRepository(self.db)
        return self._repositories["collection"]
    
    def get_task_repository(self) -> TaskRepository:
        """获取任务Repository"""
        if "task" not in self._repositories:
            self._repositories["task"] = TaskRepository(self.db)
        return self._repositories["task"]
    
    def get_repository(self, repository_type: str) -> BaseRepository:
        """
        根据类型获取Repository
        
        Args:
            repository_type: Repository类型
            
        Returns:
            Repository实例
        """
        repository_map = {
            "project": self.get_project_repository,
            "clip": self.get_clip_repository,
            "collection": self.get_collection_repository,
            "task": self.get_task_repository
        }
        
        if repository_type not in repository_map:
            raise ValueError(f"Unknown repository type: {repository_type}")
        
        return repository_map[repository_type]()
    
    def clear_cache(self):
        """清除Repository缓存"""
        self._repositories.clear()
    
    def __enter__(self):
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.clear_cache()

# 全局Repository工厂实例
_repository_factory: RepositoryFactory = None

def get_repository_factory(db: Session) -> RepositoryFactory:
    """
    获取Repository工厂实例
    
    Args:
        db: 数据库会话
        
    Returns:
        Repository工厂实例
    """
    global _repository_factory
    if _repository_factory is None or _repository_factory.db != db:
        _repository_factory = RepositoryFactory(db)
    return _repository_factory

def get_project_repository(db: Session) -> ProjectRepository:
    """
    获取项目Repository
    
    Args:
        db: 数据库会话
        
    Returns:
        项目Repository实例
    """
    return get_repository_factory(db).get_project_repository()

def get_clip_repository(db: Session) -> ClipRepository:
    """
    获取切片Repository
    
    Args:
        db: 数据库会话
        
    Returns:
        切片Repository实例
    """
    return get_repository_factory(db).get_clip_repository()

def get_collection_repository(db: Session) -> CollectionRepository:
    """
    获取合集Repository
    
    Args:
        db: 数据库会话
        
    Returns:
        合集Repository实例
    """
    return get_repository_factory(db).get_collection_repository()

def get_task_repository(db: Session) -> TaskRepository:
    """
    获取任务Repository
    
    Args:
        db: 数据库会话
        
    Returns:
        任务Repository实例
    """
    return get_repository_factory(db).get_task_repository() 