"""
B站相关数据库模型
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from .base import Base


class BilibiliAccount(Base):
    """B站账号表"""
    __tablename__ = "bilibili_accounts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), nullable=False, unique=True)
    nickname = Column(String(100))
    cookies = Column(Text)  # 加密存储的cookies
    status = Column(String(20), default="active")  # active/inactive
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    upload_records = relationship("UploadRecord", back_populates="account")


class UploadRecord(Base):
    """投稿记录表"""
    __tablename__ = "upload_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("bilibili_accounts.id"), nullable=False)
    clip_id = Column(String(255))  # 切片ID
    
    # 投稿内容
    title = Column(String(200))
    description = Column(Text)
    tags = Column(Text)  # JSON字符串存储
    partition_id = Column(Integer)  # 分区ID
    
    # 投稿结果
    bvid = Column(String(20))  # 投稿成功后的BV号
    status = Column(String(20), default="pending")  # pending/success/failed
    error_message = Column(Text)  # 错误信息
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    account = relationship("BilibiliAccount", back_populates="upload_records")

