"""
分片上传工具
支持大文件的分片上传和合并
"""

import os
import hashlib
import shutil
import asyncio
import aiofiles
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class UploadStatus(Enum):
    """上传状态"""
    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ChunkInfo:
    """分片信息"""
    chunk_number: int
    chunk_size: int
    total_chunks: int
    file_hash: str
    chunk_hash: str
    upload_id: str
    created_at: datetime
    status: UploadStatus = UploadStatus.PENDING


@dataclass
class UploadSession:
    """上传会话"""
    upload_id: str
    filename: str
    file_size: int
    chunk_size: int
    total_chunks: int
    file_hash: str
    created_at: datetime
    status: UploadStatus = UploadStatus.PENDING
    uploaded_chunks: List[int] = None
    temp_dir: str = None
    
    def __post_init__(self):
        if self.uploaded_chunks is None:
            self.uploaded_chunks = []
        if self.temp_dir is None:
            self.temp_dir = f"/tmp/uploads/{self.upload_id}"


class ChunkedUploadManager:
    """分片上传管理器"""
    
    def __init__(self, base_dir: str = "/tmp/uploads", max_file_size: int = 2 * 1024 * 1024 * 1024):
        self.base_dir = Path(base_dir)
        self.max_file_size = max_file_size
        self.active_sessions: Dict[str, UploadSession] = {}
        self.chunk_info_cache: Dict[str, List[ChunkInfo]] = {}
        
        # 确保基础目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_upload_id(self, filename: str, file_size: int) -> str:
        """生成上传ID"""
        timestamp = datetime.now().isoformat()
        content = f"{filename}_{file_size}_{timestamp}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _calculate_chunk_hash(self, chunk_data: bytes) -> str:
        """计算分片哈希值"""
        return hashlib.md5(chunk_data).hexdigest()
    
    def _validate_file_size(self, file_size: int) -> bool:
        """验证文件大小"""
        return file_size <= self.max_file_size
    
    def _validate_file_type(self, filename: str) -> bool:
        """验证文件类型"""
        allowed_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv', '.srt', '.vtt', '.ass', '.ssa']
        return any(filename.lower().endswith(ext) for ext in allowed_extensions)
    
    async def create_upload_session(
        self, 
        filename: str, 
        file_size: int, 
        file_hash: str,
        chunk_size: int = 2 * 1024 * 1024  # 2MB
    ) -> UploadSession:
        """创建上传会话"""
        
        # 验证文件大小
        if not self._validate_file_size(file_size):
            raise ValueError(f"文件大小超过限制: {file_size} > {self.max_file_size}")
        
        # 验证文件类型
        if not self._validate_file_type(filename):
            raise ValueError(f"不支持的文件类型: {filename}")
        
        # 生成上传ID
        upload_id = self._generate_upload_id(filename, file_size)
        
        # 计算总分片数
        total_chunks = (file_size + chunk_size - 1) // chunk_size
        
        # 创建上传会话
        session = UploadSession(
            upload_id=upload_id,
            filename=filename,
            file_size=file_size,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            file_hash=file_hash,
            created_at=datetime.now()
        )
        
        # 创建临时目录
        session.temp_dir = str(self.base_dir / upload_id)
        Path(session.temp_dir).mkdir(parents=True, exist_ok=True)
        
        # 保存会话
        self.active_sessions[upload_id] = session
        
        logger.info(f"创建上传会话: {upload_id}, 文件: {filename}, 大小: {file_size}, 分片数: {total_chunks}")
        
        return session
    
    async def upload_chunk(
        self, 
        upload_id: str, 
        chunk_number: int, 
        chunk_data: bytes,
        chunk_hash: str
    ) -> bool:
        """上传分片"""
        
        # 获取上传会话
        session = self.active_sessions.get(upload_id)
        if not session:
            raise ValueError(f"上传会话不存在: {upload_id}")
        
        # 验证分片号
        if chunk_number < 0 or chunk_number >= session.total_chunks:
            raise ValueError(f"无效的分片号: {chunk_number}")
        
        # 验证分片大小
        expected_size = session.chunk_size
        if chunk_number == session.total_chunks - 1:  # 最后一个分片
            expected_size = session.file_size - (session.total_chunks - 1) * session.chunk_size
        
        if len(chunk_data) != expected_size:
            raise ValueError(f"分片大小不匹配: 期望 {expected_size}, 实际 {len(chunk_data)}")
        
        # 验证分片哈希
        calculated_hash = self._calculate_chunk_hash(chunk_data)
        if calculated_hash != chunk_hash:
            raise ValueError(f"分片哈希不匹配: 期望 {chunk_hash}, 实际 {calculated_hash}")
        
        # 保存分片
        chunk_path = Path(session.temp_dir) / f"chunk_{chunk_number:06d}"
        
        async with aiofiles.open(chunk_path, 'wb') as f:
            await f.write(chunk_data)
        
        # 更新会话状态
        if chunk_number not in session.uploaded_chunks:
            session.uploaded_chunks.append(chunk_number)
        
        # 检查是否所有分片都已上传
        if len(session.uploaded_chunks) == session.total_chunks:
            session.status = UploadStatus.COMPLETED
        
        logger.info(f"上传分片成功: {upload_id}, 分片: {chunk_number}, 进度: {len(session.uploaded_chunks)}/{session.total_chunks}")
        
        return True
    
    async def merge_chunks(self, upload_id: str, output_path: str) -> bool:
        """合并分片"""
        
        # 获取上传会话
        session = self.active_sessions.get(upload_id)
        if not session:
            raise ValueError(f"上传会话不存在: {upload_id}")
        
        # 检查是否所有分片都已上传
        if len(session.uploaded_chunks) != session.total_chunks:
            raise ValueError(f"分片上传未完成: {len(session.uploaded_chunks)}/{session.total_chunks}")
        
        # 确保输出目录存在
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 合并分片
        logger.info(f"开始合并分片: {upload_id}")
        
        with open(output_path, 'wb') as output_file:
            for chunk_number in range(session.total_chunks):
                chunk_path = Path(session.temp_dir) / f"chunk_{chunk_number:06d}"
                
                if not chunk_path.exists():
                    raise FileNotFoundError(f"分片文件不存在: {chunk_path}")
                
                with open(chunk_path, 'rb') as chunk_file:
                    shutil.copyfileobj(chunk_file, output_file)
        
        # 验证合并后的文件
        if output_path.stat().st_size != session.file_size:
            raise ValueError(f"合并后文件大小不匹配: 期望 {session.file_size}, 实际 {output_path.stat().st_size}")
        
        # 验证文件哈希
        merged_hash = self._calculate_file_hash(str(output_path))
        if merged_hash != session.file_hash:
            raise ValueError(f"合并后文件哈希不匹配: 期望 {session.file_hash}, 实际 {merged_hash}")
        
        logger.info(f"分片合并完成: {upload_id}, 输出: {output_path}")
        
        return True
    
    async def cleanup_session(self, upload_id: str) -> bool:
        """清理上传会话"""
        
        # 获取上传会话
        session = self.active_sessions.get(upload_id)
        if not session:
            return False
        
        # 删除临时目录
        temp_dir = Path(session.temp_dir)
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        
        # 从活跃会话中移除
        del self.active_sessions[upload_id]
        
        logger.info(f"清理上传会话: {upload_id}")
        
        return True
    
    def get_upload_progress(self, upload_id: str) -> Dict[str, Any]:
        """获取上传进度"""
        
        session = self.active_sessions.get(upload_id)
        if not session:
            return {"error": "上传会话不存在"}
        
        progress = len(session.uploaded_chunks) / session.total_chunks * 100
        
        return {
            "upload_id": upload_id,
            "filename": session.filename,
            "file_size": session.file_size,
            "total_chunks": session.total_chunks,
            "uploaded_chunks": len(session.uploaded_chunks),
            "progress": round(progress, 2),
            "status": session.status.value,
            "created_at": session.created_at.isoformat()
        }
    
    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """获取所有活跃会话"""
        
        sessions = []
        for session in self.active_sessions.values():
            progress = len(session.uploaded_chunks) / session.total_chunks * 100
            sessions.append({
                "upload_id": session.upload_id,
                "filename": session.filename,
                "file_size": session.file_size,
                "total_chunks": session.total_chunks,
                "uploaded_chunks": len(session.uploaded_chunks),
                "progress": round(progress, 2),
                "status": session.status.value,
                "created_at": session.created_at.isoformat()
            })
        
        return sessions
    
    async def cancel_upload(self, upload_id: str) -> bool:
        """取消上传"""
        
        session = self.active_sessions.get(upload_id)
        if not session:
            return False
        
        # 更新状态
        session.status = UploadStatus.CANCELLED
        
        # 清理临时文件
        await self.cleanup_session(upload_id)
        
        logger.info(f"取消上传: {upload_id}")
        
        return True
    
    def cleanup_expired_sessions(self, max_age_hours: int = 24) -> int:
        """清理过期会话"""
        
        from datetime import timedelta
        
        expired_sessions = []
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        for upload_id, session in self.active_sessions.items():
            if session.created_at < cutoff_time:
                expired_sessions.append(upload_id)
        
        # 清理过期会话
        for upload_id in expired_sessions:
            asyncio.create_task(self.cleanup_session(upload_id))
        
        logger.info(f"清理过期会话: {len(expired_sessions)} 个")
        
        return len(expired_sessions)


# 全局分片上传管理器实例
chunked_upload_manager = ChunkedUploadManager()
