"""
合集模型
定义视频合集的基本信息和组织方式
"""

import enum
from typing import Optional, List
from sqlalchemy import Column, String, Integer, ForeignKey, Enum, JSON, DateTime, Text, Table
from sqlalchemy.orm import relationship
from .base import BaseModel

class CollectionStatus(str, enum.Enum):
    """合集状态枚举"""
    CREATED = "created"           # 已创建
    PROCESSING = "processing"     # 处理中
    COMPLETED = "completed"       # 已完成
    ERROR = "error"              # 错误
    DELETED = "deleted"          # 已删除

# 切片和合集的多对多关系表
clip_collection = Table(
    'clip_collection',
    BaseModel.metadata,
    Column('clip_id', String(36), ForeignKey('clips.id', ondelete='CASCADE'), primary_key=True),
    Column('collection_id', String(36), ForeignKey('collections.id', ondelete='CASCADE'), primary_key=True),
    Column('order_index', Integer, nullable=False, default=0, comment="在合集中的顺序")
)

class Collection(BaseModel):
    """合集模型"""
    
    __tablename__ = "collections"
    
    # 基本信息
    name = Column(
        String(255), 
        nullable=False, 
        comment="合集名称"
    )
    description = Column(
        Text, 
        nullable=True, 
        comment="合集描述"
    )
    
    # 状态信息
    status = Column(
        Enum(CollectionStatus), 
        default=CollectionStatus.CREATED,
        nullable=False,
        comment="合集状态"
    )
    
    # 主题信息
    theme = Column(
        String(255), 
        nullable=True, 
        comment="合集主题"
    )
    tags = Column(
        JSON, 
        nullable=True, 
        comment="合集标签"
    )
    
    # 统计信息
    total_duration = Column(
        Integer, 
        nullable=True, 
        comment="合集总时长（秒）"
    )
    clips_count = Column(
        Integer, 
        default=0, 
        comment="切片数量"
    )
    
    # 文件信息
    video_path = Column(
        String(500), 
        nullable=True, 
        comment="合集视频文件路径"
    )
    thumbnail_path = Column(
        String(500), 
        nullable=True, 
        comment="合集缩略图路径"
    )
    
    # 处理信息
    processing_result = Column(
        JSON, 
        nullable=True, 
        comment="处理结果数据"
    )
    
    # 导出信息
    export_path = Column(
        String(500), 
        nullable=True, 
        comment="合集导出文件路径"
    )
    
    # 元数据
    collection_metadata = Column(
        JSON, 
        nullable=True, 
        comment="合集元数据（精简版，完整数据存储在文件系统）"
    )
    
    # 添加计算属性
    @property
    def metadata_file_path(self) -> Optional[str]:
        """获取完整元数据文件路径"""
        if self.collection_metadata and 'metadata_file' in self.collection_metadata:
            return self.collection_metadata['metadata_file']
        return None
    
    @property
    def has_full_content(self) -> bool:
        """是否有完整内容文件"""
        return self.metadata_file_path is not None
    
    @property
    def clip_ids(self) -> List[str]:
        """获取切片ID列表"""
        if self.collection_metadata and 'clip_ids' in self.collection_metadata:
            return self.collection_metadata['clip_ids']
        return []
    
    # 外键关联
    project_id = Column(
        String(36), 
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目ID"
    )
    
    # 关联关系
    project = relationship(
        "Project", 
        back_populates="collections"
    )
    clips = relationship(
        "Clip", 
        secondary=clip_collection,
        back_populates="collections",
        lazy="dynamic"
    )
    
    def __repr__(self):
        return f"<Collection(id={self.id}, name='{self.name}', clips_count={self.clips_count})>"
    
    @property
    def is_processing(self):
        """是否正在处理"""
        return self.status == CollectionStatus.PROCESSING
    
    @property
    def is_completed(self):
        """是否已完成"""
        return self.status == CollectionStatus.COMPLETED
    
    @property
    def has_error(self):
        """是否有错误"""
        return self.status == CollectionStatus.ERROR
    
    def add_clip(self, clip, order_index=None):
        """添加切片到合集"""
        if order_index is None:
            order_index = self.clips_count
        
        # 使用关联表添加切片
        stmt = clip_collection.insert().values(
            clip_id=clip.id,
            collection_id=self.id,
            order_index=order_index
        )
        # 这里需要在数据库会话中执行
        self.clips_count += 1
        return stmt
    
    def remove_clip(self, clip):
        """从合集中移除切片"""
        stmt = clip_collection.delete().where(
            clip_collection.c.clip_id == clip.id,
            clip_collection.c.collection_id == self.id
        )
        current_count = int(self.clips_count) if self.clips_count else 0
        self.clips_count = max(0, current_count - 1)
        return stmt
    
    def calculate_total_duration(self):
        """计算合集总时长"""
        total = 0
        for clip in self.clips:
            if clip.duration:
                total += clip.duration
        self.total_duration = total
        return total