"""
任务模型
定义后台任务的基本信息和执行状态
"""

import enum
from sqlalchemy import Column, String, Integer, Float, ForeignKey, Enum, JSON, DateTime, Text
from sqlalchemy.orm import relationship
from .base import BaseModel, TimestampMixin

class TaskStatus(str, enum.Enum):
    """任务状态枚举"""
    PENDING = "pending"           # 等待中
    RUNNING = "running"           # 运行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 已取消

class TaskType(str, enum.Enum):
    """任务类型枚举"""
    VIDEO_PROCESSING = "video_processing"    # 视频处理
    CLIP_GENERATION = "clip_generation"      # 切片生成
    COLLECTION_CREATION = "collection_creation"  # 合集创建
    EXPORT = "export"                        # 导出
    CLEANUP = "cleanup"                      # 清理

class Task(BaseModel, TimestampMixin):
    """任务模型"""
    
    __tablename__ = "tasks"
    
    # 基本信息
    name = Column(
        String(255), 
        nullable=False, 
        comment="任务名称"
    )
    description = Column(
        Text, 
        nullable=True, 
        comment="任务描述"
    )
    
    # 状态信息
    status = Column(
        Enum(TaskStatus), 
        default=TaskStatus.PENDING,
        nullable=False,
        comment="任务状态"
    )
    task_type = Column(
        Enum(TaskType), 
        nullable=False,
        comment="任务类型"
    )
    
    # 进度信息
    progress = Column(Float, default=0.0, comment="进度百分比")
    current_step = Column(
        String(100), 
        nullable=True, 
        comment="当前步骤"
    )
    total_steps = Column(
        Integer, 
        default=1,
        comment="总步骤数"
    )
    priority = Column(
        Integer, 
        default=0,
        comment="任务优先级"
    )
    
    # 执行信息
    started_at = Column(
        DateTime, 
        nullable=True, 
        comment="开始时间"
    )
    completed_at = Column(
        DateTime, 
        nullable=True, 
        comment="完成时间"
    )
    error_message = Column(
        Text, 
        nullable=True, 
        comment="错误信息"
    )
    
    # Celery任务信息
    celery_task_id = Column(
        String(255), 
        nullable=True, 
        comment="Celery任务ID"
    )
    
    # 配置信息
    task_config = Column(
        JSON, 
        nullable=True, 
        comment="任务配置"
    )
    result_data = Column(
        JSON, 
        nullable=True, 
        comment="结果数据"
    )
    task_metadata = Column(
        JSON, 
        nullable=True, 
        comment="任务元数据"
    )
    
    # 关联关系
    project_id = Column(
        String(36), 
        ForeignKey("projects.id"),
        nullable=False,
        comment="关联项目ID"
    )
    project = relationship(
        "Project", 
        back_populates="tasks"
    )
    
    def __repr__(self):
        return f"<Task(id={self.id}, name='{self.name}', status={self.status})>"
    
    @property
    def is_running(self):
        """是否正在运行"""
        return self.status == TaskStatus.RUNNING
    
    @property
    def is_completed(self):
        """是否已完成"""
        return self.status == TaskStatus.COMPLETED
    
    @property
    def has_error(self):
        """是否有错误"""
        return self.status == TaskStatus.FAILED
    
    @property
    def duration(self):
        """任务持续时间（秒）"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        elif self.started_at:
            return (datetime.utcnow() - self.started_at).total_seconds()
        return 0
    
    def start(self):
        """开始任务"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.progress = 0.0
    
    def complete(self, result_data=None):
        """完成任务"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.progress = 100.0
        if result_data:
            self.result_data = result_data
    
    def fail(self, error_message):
        """任务失败"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
    
    def cancel(self):
        """取消任务"""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.utcnow()
    
    def update_progress(self, progress, current_step=None):
        """更新进度"""
        self.progress = min(100.0, max(0.0, progress))
        if current_step:
            self.current_step = current_step
    
    def is_completed(self):
        """检查是否完成"""
        return self.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
    
    def is_running(self):
        """检查是否运行中"""
        return self.status == TaskStatus.RUNNING
    
    def is_pending(self):
        """检查是否待处理"""
        return self.status == TaskStatus.PENDING
    
    def get_duration(self):
        """获取任务持续时间"""
        if not self.started_at:
            return None
        
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "task_type": self.task_type,
            "status": self.status,
            "project_id": self.project_id,
            "step": self.current_step,
            "total_steps": self.total_steps,
            "progress": self.progress,
            "result": self.result_data,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "config": self.task_config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }