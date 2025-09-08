"""
B站相关Schema
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


class BilibiliAccountCreate(BaseModel):
    """创建B站账号"""
    username: str = Field(default="qr_login", description="用户名")
    password: str = Field(default="", description="密码")
    nickname: Optional[str] = Field(None, description="昵称")
    cookie_content: str = Field(..., description="cookie文件内容")


class BilibiliAccountResponse(BaseModel):
    """B站账号响应"""
    id: UUID
    username: str
    nickname: Optional[str]
    status: str
    is_default: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class QRLoginRequest(BaseModel):
    """二维码登录请求"""
    nickname: Optional[str] = Field(None, description="昵称")


class QRLoginResponse(BaseModel):
    """二维码登录响应"""
    session_id: str
    status: str
    message: str


class UploadRequest(BaseModel):
    """投稿请求"""
    clip_ids: List[str] = Field(..., description="要投稿的切片ID列表")
    account_id: UUID = Field(..., description="使用的账号ID")
    title: str = Field(..., description="标题")
    description: str = Field(..., description="描述")
    tags: List[str] = Field(default=[], description="标签列表")
    partition_id: int = Field(..., description="分区ID")
    sub_partition_id: Optional[int] = Field(None, description="子分区ID（可选）")


class UploadRecordResponse(BaseModel):
    """投稿记录响应"""
    id: UUID
    project_id: UUID
    account_id: UUID
    clip_id: str
    title: str
    description: str
    tags: str
    partition_id: int
    bvid: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UploadStatusResponse(BaseModel):
    """投稿状态响应"""
    id: UUID
    status: str
    bvid: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True
