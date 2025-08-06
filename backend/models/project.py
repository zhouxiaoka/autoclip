"""
项目模型
定义项目的基本信息和状态
"""

import enum
from sqlalchemy import Column, String, Text, JSON, Enum, Integer, DateTime
from sqlalchemy.orm import relationship
from .base import BaseModel

class ProjectStatus(str, enum.Enum):
    """项目状态枚举"""
    PENDING = "pending"           # 等待中
    PROCESSING = "processing"     # 处理中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"            # 失败

class ProjectType(str, enum.Enum):
    """项目类型枚举"""
    DEFAULT = "default"           # 默认
    KNOWLEDGE = "knowledge"       # 知识科普
    BUSINESS = "business"         # 商业财经
    OPINION = "opinion"          # 观点评论
    EXPERIENCE = "experience"    # 经验分享
    SPEECH = "speech"            # 演讲脱口秀
    CONTENT_REVIEW = "content_review"  # 内容解说
    ENTERTAINMENT = "entertainment"    # 娱乐内容

class Project(BaseModel):
    """项目模型"""
    
    __tablename__ = "projects"
    
    # 基本信息
    name = Column(
        String(255), 
        nullable=False, 
        comment="项目名称"
    )
    description = Column(
        Text, 
        nullable=True, 
        comment="项目描述"
    )
    
    # 状态信息
    status = Column(
        Enum(ProjectStatus), 
        default=ProjectStatus.PENDING,
        nullable=False,
        comment="项目状态"
    )
    
    # 项目类型
    project_type = Column(
        Enum(ProjectType), 
        default=ProjectType.DEFAULT,
        nullable=False,
        comment="项目类型"
    )
    video_path = Column(
        String(500), 
        nullable=True, 
        comment="视频文件路径"
    )
    video_duration = Column(
        Integer, 
        nullable=True, 
        comment="视频时长（秒）"
    )
    
    # 处理配置
    processing_config = Column(
        JSON, 
        nullable=True, 
        comment="处理配置参数"
    )
    
    # 元数据
    project_metadata = Column(
        JSON, 
        nullable=True, 
        comment="项目元数据"
    )
    
    # 完成时间
    completed_at = Column(
        DateTime, 
        nullable=True, 
        comment="项目完成时间"
    )
    
    # 关联关系
    clips = relationship(
        "Clip", 
        back_populates="project",
        cascade="all, delete-orphan"
    )
    collections = relationship(
        "Collection", 
        back_populates="project",
        cascade="all, delete-orphan"
    )
    tasks = relationship(
        "Task", 
        back_populates="project",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}', status={self.status})>"
    
    @property
    def clips_count(self):
        """获取切片数量"""
        return len(self.clips) if self.clips else 0
    
    @property
    def collections_count(self):
        """获取合集数量"""
        return len(self.collections) if self.collections else 0
    
    @property
    def is_processing(self):
        """是否正在处理"""
        return self.status == ProjectStatus.PROCESSING
    
    @property
    def is_completed(self):
        """是否已完成"""
        return self.status == ProjectStatus.COMPLETED
    
    @property
    def has_error(self):
        """是否有错误"""
        return self.status == ProjectStatus.FAILED