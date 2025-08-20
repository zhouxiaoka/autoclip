"""
切片模型
定义视频切片的基本信息和状态
"""

import enum
from typing import Optional
from sqlalchemy import Column, String, Integer, Float, ForeignKey, Enum, JSON, DateTime, Text
from sqlalchemy.orm import relationship
from .base import BaseModel

class ClipStatus(str, enum.Enum):
    """切片状态枚举"""
    PENDING = "pending"           # 待处理
    PROCESSING = "processing"     # 处理中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"            # 失败

class Clip(BaseModel):
    """切片模型"""
    
    __tablename__ = "clips"
    
    # 基本信息
    title = Column(
        String(255), 
        nullable=False, 
        comment="切片标题"
    )
    description = Column(
        Text, 
        nullable=True, 
        comment="切片描述"
    )
    
    # 状态信息
    status = Column(
        Enum(ClipStatus), 
        default=ClipStatus.PENDING,
        nullable=False,
        comment="切片状态"
    )
    
    # 时间信息
    start_time = Column(
        Integer, 
        nullable=False, 
        comment="开始时间（秒）"
    )
    end_time = Column(
        Integer, 
        nullable=False, 
        comment="结束时间（秒）"
    )
    duration = Column(
        Integer, 
        nullable=False, 
        comment="切片时长（秒）"
    )
    
    # 评分信息
    score = Column(
        Float, 
        nullable=True, 
        comment="切片评分"
    )
    recommendation_reason = Column(
        Text, 
        nullable=True, 
        comment="推荐理由"
    )
    
    # 文件信息
    video_path = Column(
        String(500), 
        nullable=True, 
        comment="切片视频文件路径"
    )
    thumbnail_path = Column(
        String(500), 
        nullable=True, 
        comment="缩略图文件路径"
    )
    
    # 处理信息
    processing_step = Column(
        Integer, 
        nullable=True, 
        comment="处理步骤（1-6）"
    )
    
    # 标签和元数据
    tags = Column(
        JSON, 
        nullable=True, 
        comment="切片标签"
    )
    clip_metadata = Column(
        JSON, 
        nullable=True, 
        comment="切片元数据（精简版，完整数据存储在文件系统）"
    )
    
    # 添加计算属性
    @property
    def metadata_file_path(self) -> Optional[str]:
        """获取完整元数据文件路径"""
        if self.clip_metadata and 'metadata_file' in self.clip_metadata:
            return self.clip_metadata['metadata_file']
        return None
    
    @property
    def has_full_content(self) -> bool:
        """是否有完整内容文件"""
        return self.metadata_file_path is not None
    
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
        back_populates="clips"
    )
    collections = relationship(
        "Collection", 
        secondary="clip_collection",
        back_populates="clips"
    )
    
    def __repr__(self):
        return f"<Clip(id={self.id}, title='{self.title}', duration={self.duration}s)>"
    
    @property
    def is_processing(self):
        """是否正在处理"""
        return self.status == ClipStatus.PROCESSING
    
    @property
    def is_completed(self):
        """是否已完成"""
        return self.status == ClipStatus.COMPLETED
    
    @property
    def has_error(self):
        """是否有错误"""
        return self.status == ClipStatus.FAILED
    
    def get_time_range(self) -> str:
        """获取时间范围字符串"""
        try:
            start_time = int(self.start_time) if self.start_time else 0
            end_time = int(self.end_time) if self.end_time else 0
            start_min, start_sec = divmod(start_time, 60)
            end_min, end_sec = divmod(end_time, 60)
            return f"{start_min:02d}:{start_sec:02d} - {end_min:02d}:{end_sec:02d}"
        except (TypeError, ValueError):
            return "00:00 - 00:00"
    
    def calculate_duration(self):
        """计算切片时长"""
        self.duration = self.end_time - self.start_time
        return self.duration