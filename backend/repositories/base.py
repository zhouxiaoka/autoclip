"""
基础Repository类
提供通用的数据访问操作
"""

from typing import TypeVar, Generic, Optional, List, Dict, Any, Type
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from models.base import BaseModel

# 定义泛型类型
ModelType = TypeVar("ModelType", bound=BaseModel)

class BaseRepository(Generic[ModelType]):
    """
    基础Repository类，提供通用的CRUD操作
    
    Generic[ModelType]: 泛型类型，ModelType必须是BaseModel的子类
    """
    
    def __init__(self, model: Type[ModelType], db: Session):
        """
        初始化Repository
        
        Args:
            model: 模型类
            db: 数据库会话
        """
        self.model = model
        self.db = db
    
    def create(self, **kwargs) -> ModelType:
        """
        创建记录
        
        Args:
            **kwargs: 模型字段和值
            
        Returns:
            创建的模型实例
        """
        instance = self.model(**kwargs)
        self.db.add(instance)
        self.db.commit()
        self.db.refresh(instance)
        return instance
    
    def get_by_id(self, id: str) -> Optional[ModelType]:
        """
        根据ID获取记录
        
        Args:
            id: 记录ID
            
        Returns:
            模型实例或None
        """
        return self.db.query(self.model).filter(self.model.id == id).first()
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """
        获取所有记录
        
        Args:
            skip: 跳过的记录数
            limit: 返回的记录数限制
            
        Returns:
            模型实例列表
        """
        return self.db.query(self.model).offset(skip).limit(limit).all()
    
    def update(self, id: str, **kwargs) -> Optional[ModelType]:
        """
        更新记录
        
        Args:
            id: 记录ID
            **kwargs: 要更新的字段和值
            
        Returns:
            更新后的模型实例或None
        """
        instance = self.get_by_id(id)
        if instance:
            for field, value in kwargs.items():
                if hasattr(instance, field):
                    setattr(instance, field, value)
            self.db.commit()
            self.db.refresh(instance)
        return instance
    
    def delete(self, id: str) -> bool:
        """
        删除记录
        
        Args:
            id: 记录ID
            
        Returns:
            是否删除成功
        """
        instance = self.get_by_id(id)
        if instance:
            self.db.delete(instance)
            self.db.commit()
            return True
        return False
    
    def count(self) -> int:
        """
        获取记录总数
        
        Returns:
            记录总数
        """
        return self.db.query(self.model).count()
    
    def exists(self, id: str) -> bool:
        """
        检查记录是否存在
        
        Args:
            id: 记录ID
            
        Returns:
            是否存在
        """
        return self.db.query(self.model).filter(self.model.id == id).first() is not None
    
    def find_by(self, **kwargs) -> List[ModelType]:
        """
        根据条件查找记录
        
        Args:
            **kwargs: 查询条件
            
        Returns:
            匹配的模型实例列表
        """
        filters = []
        for field, value in kwargs.items():
            if hasattr(self.model, field):
                filters.append(getattr(self.model, field) == value)
        
        if filters:
            return self.db.query(self.model).filter(and_(*filters)).all()
        return []
    
    def find_one_by(self, **kwargs) -> Optional[ModelType]:
        """
        根据条件查找单条记录
        
        Args:
            **kwargs: 查询条件
            
        Returns:
            匹配的模型实例或None
        """
        filters = []
        for field, value in kwargs.items():
            if hasattr(self.model, field):
                filters.append(getattr(self.model, field) == value)
        
        if filters:
            return self.db.query(self.model).filter(and_(*filters)).first()
        return None
    
    def find_by_condition(self, condition) -> List[ModelType]:
        """
        根据自定义条件查找记录
        
        Args:
            condition: SQLAlchemy查询条件
            
        Returns:
            匹配的模型实例列表
        """
        return self.db.query(self.model).filter(condition).all()
    
    def find_one_by_condition(self, condition) -> Optional[ModelType]:
        """
        根据自定义条件查找单条记录
        
        Args:
            condition: SQLAlchemy查询条件
            
        Returns:
            匹配的模型实例或None
        """
        return self.db.query(self.model).filter(condition).first()
    
    def bulk_create(self, instances: List[Dict[str, Any]]) -> List[ModelType]:
        """
        批量创建记录
        
        Args:
            instances: 要创建的实例数据列表
            
        Returns:
            创建的模型实例列表
        """
        created_instances = []
        for instance_data in instances:
            instance = self.model(**instance_data)
            self.db.add(instance)
            created_instances.append(instance)
        
        self.db.commit()
        
        # 刷新所有实例
        for instance in created_instances:
            self.db.refresh(instance)
        
        return created_instances
    
    def bulk_update(self, instances: List[ModelType]) -> List[ModelType]:
        """
        批量更新记录
        
        Args:
            instances: 要更新的实例列表
            
        Returns:
            更新后的模型实例列表
        """
        for instance in instances:
            self.db.merge(instance)
        
        self.db.commit()
        return instances
    
    def bulk_delete(self, ids: List[str]) -> int:
        """
        批量删除记录
        
        Args:
            ids: 要删除的记录ID列表
            
        Returns:
            删除的记录数
        """
        deleted_count = self.db.query(self.model).filter(
            self.model.id.in_(ids)
        ).delete(synchronize_session=False)
        
        self.db.commit()
        return deleted_count