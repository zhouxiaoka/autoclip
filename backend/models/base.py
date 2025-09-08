"""
基础模型定义
包含所有模型的基类和混入类
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, MetaData
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID

# 创建MetaData实例，确保表不会重复定义
metadata = MetaData()

# 创建基础类
Base = declarative_base(metadata=metadata)

def get_utc_now():
    """获取当前UTC时间"""
    return datetime.now(timezone.utc)

class TimestampMixin:
    """时间戳混入类，为模型添加创建和更新时间"""
    
    created_at = Column(
        DateTime(timezone=True), 
        default=get_utc_now, 
        nullable=False,
        comment="创建时间"
    )
    updated_at = Column(
        DateTime(timezone=True), 
        default=get_utc_now, 
        onupdate=get_utc_now, 
        nullable=False,
        comment="更新时间"
    )

def generate_uuid():
    """生成UUID字符串"""
    return str(uuid.uuid4())

class BaseModel(Base, TimestampMixin):
    """基础模型类，包含通用字段"""
    
    __abstract__ = True
    
    id = Column(
        String(36), 
        primary_key=True, 
        default=generate_uuid,
        index=True,
        comment="主键ID"
    )
    
    def __repr__(self):
        """模型的字符串表示"""
        return f"<{self.__class__.__name__}(id={self.id})>"
    
    def to_dict(self):
        """转换为字典"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update_from_dict(self, data: dict):
        """从字典更新模型"""
        for key, value in data.items():
            if hasattr(self, key) and key != 'id':
                setattr(self, key, value)
        return self 