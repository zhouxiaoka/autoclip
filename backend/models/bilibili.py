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
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True)
    nickname = Column(String(100))
    cookies = Column(Text)  # 加密存储的cookies
    status = Column(String(20), default="active")  # active/inactive/banned
    is_default = Column(Boolean, default=False)
    
    # 账号信息
    uid = Column(String(50))  # B站用户ID
    level = Column(Integer, default=0)  # 用户等级
    is_vip = Column(Boolean, default=False)  # 是否VIP
    can_upload = Column(Boolean, default=True)  # 是否可以投稿
    
    # 使用统计
    last_used_at = Column(DateTime)  # 最后使用时间
    upload_count = Column(Integer, default=0)  # 上传次数
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    upload_records = relationship("BilibiliUploadRecord", back_populates="account")


class BilibiliUploadRecord(Base):
    """B站投稿记录表"""
    __tablename__ = "bilibili_upload_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(100), unique=True, index=True)  # 任务队列ID
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    account_id = Column(Integer, ForeignKey("bilibili_accounts.id"), nullable=False)
    clip_id = Column(String(255))  # 切片ID
    
    # 投稿内容
    title = Column(String(200), nullable=False)
    description = Column(Text)
    tags = Column(Text)  # JSON字符串存储
    partition_id = Column(Integer, default=17)  # 分区ID，默认单机游戏
    video_path = Column(String(500))  # 视频文件路径
    
    # 投稿结果
    bv_id = Column(String(20))  # 投稿成功后的BV号
    av_id = Column(String(20))  # AV号
    status = Column(String(20), default="pending")  # pending/processing/completed/failed
    error_message = Column(Text)  # 错误信息
    
    # 上传进度和统计
    progress = Column(Integer, default=0)  # 上传进度 0-100
    file_size = Column(Integer)  # 文件大小（字节）
    upload_duration = Column(Integer)  # 上传耗时（秒）
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    account = relationship("BilibiliAccount", back_populates="upload_records")

# 为了向后兼容，保留旧的类名
UploadRecord = BilibiliUploadRecord

