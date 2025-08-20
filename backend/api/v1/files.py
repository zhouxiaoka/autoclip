"""
文件管理API
提供文件上传、下载和访问功能
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import shutil
import uuid

from core.database import get_db
from services.storage_service import StorageService
from models.project import Project
from models.clip import Clip
from models.collection import Collection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["文件管理"])

@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    project_id: str = Query(..., description="项目ID"),
    db: Session = Depends(get_db)
):
    """
    上传文件（优化存储模式）
    
    - 保存文件到文件系统
    - 更新数据库中的文件路径
    - 不存储文件内容到数据库
    """
    try:
        # 验证项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 初始化存储服务
        storage_service = StorageService(project_id)
        
        uploaded_files = []
        
        for file in files:
            # 生成唯一文件名
            file_id = str(uuid.uuid4())
            file_extension = Path(file.filename).suffix if file.filename else ""
            safe_filename = f"{file_id}{file_extension}"
            
            # 确定文件类型
            file_type = "raw"  # 默认为原始文件
            if file.filename:
                if file.filename.lower().endswith(('.srt', '.vtt')):
                    file_type = "subtitle"
                elif file.filename.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                    file_type = "video"
            
            # 保存文件到文件系统
            file_path = Path(f"/tmp/{safe_filename}")
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # 使用存储服务保存文件
            saved_path = storage_service.save_file(file_path, safe_filename, file_type)
            
            # 更新项目数据库记录
            if file_type == "video":
                project.video_path = saved_path
            elif file_type == "subtitle":
                project.subtitle_path = saved_path
            
            # 清理临时文件
            file_path.unlink()
            
            uploaded_files.append({
                "original_name": file.filename,
                "saved_path": saved_path,
                "file_type": file_type,
                "file_size": file.size
            })
        
        # 提交数据库更改
        db.commit()
        
        logger.info(f"项目 {project_id} 上传了 {len(uploaded_files)} 个文件")
        
        return {
            "success": True,
            "project_id": project_id,
            "uploaded_files": uploaded_files,
            "message": f"成功上传 {len(uploaded_files)} 个文件"
        }
        
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")

@router.get("/clips/{clip_id}/content")
async def get_clip_content(
    clip_id: str,
    db: Session = Depends(get_db)
):
    """
    获取切片完整内容
    
    - 从数据库获取元数据
    - 从文件系统获取完整数据
    """
    try:
        # 获取切片记录
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise HTTPException(status_code=404, detail="切片不存在")
        
        # 从文件系统获取完整内容
        from repositories.clip_repository import ClipRepository
        clip_repo = ClipRepository(db)
        content = clip_repo.get_clip_content(clip_id)
        
        if not content:
            raise HTTPException(status_code=404, detail="切片内容不存在")
        
        return {
            "clip_id": clip_id,
            "content": content,
            "metadata": {
                "title": clip.title,
                "duration": clip.duration,
                "score": clip.score,
                "video_path": clip.video_path
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取切片内容失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取切片内容失败: {str(e)}")

@router.get("/collections/{collection_id}/content")
async def get_collection_content(
    collection_id: str,
    db: Session = Depends(get_db)
):
    """
    获取合集完整内容
    
    - 从数据库获取元数据
    - 从文件系统获取完整数据
    """
    try:
        # 获取合集记录
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(status_code=404, detail="合集不存在")
        
        # 从文件系统获取完整内容
        from repositories.collection_repository import CollectionRepository
        collection_repo = CollectionRepository(db)
        content = collection_repo.get_collection_content(collection_id)
        
        if not content:
            raise HTTPException(status_code=404, detail="合集内容不存在")
        
        return {
            "collection_id": collection_id,
            "content": content,
            "metadata": {
                "name": collection.name,
                "description": collection.description,
                "clips_count": collection.clips_count,
                "export_path": collection.export_path
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取合集内容失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取合集内容失败: {str(e)}")

@router.get("/clips/{clip_id}/download")
async def download_clip_file(
    clip_id: str,
    db: Session = Depends(get_db)
):
    """
    下载切片文件
    
    - 从数据库获取文件路径
    - 返回文件流
    """
    try:
        # 获取切片记录
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise HTTPException(status_code=404, detail="切片不存在")
        
        if not clip.video_path:
            raise HTTPException(status_code=404, detail="切片文件不存在")
        
        file_path = Path(clip.video_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="切片文件不存在")
        
        return FileResponse(
            path=str(file_path),
            filename=f"clip_{clip_id}.mp4",
            media_type="video/mp4"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载切片文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载切片文件失败: {str(e)}")

@router.get("/collections/{collection_id}/download")
async def download_collection_file(
    collection_id: str,
    db: Session = Depends(get_db)
):
    """
    下载合集文件
    
    - 从数据库获取文件路径
    - 返回文件流
    """
    try:
        # 获取合集记录
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            raise HTTPException(status_code=404, detail="合集不存在")
        
        if not collection.export_path:
            raise HTTPException(status_code=404, detail="合集文件不存在")
        
        file_path = Path(collection.export_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="合集文件不存在")
        
        return FileResponse(
            path=str(file_path),
            filename=f"collection_{collection_id}.mp4",
            media_type="video/mp4"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载合集文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"下载合集文件失败: {str(e)}")

@router.get("/projects/{project_id}/storage-info")
async def get_project_storage_info(
    project_id: str,
    db: Session = Depends(get_db)
):
    """
    获取项目存储信息
    
    - 统计文件数量和大小
    - 显示存储使用情况
    """
    try:
        # 验证项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 获取存储信息
        storage_service = StorageService(project_id)
        storage_info = storage_service.get_project_storage_info()
        
        return {
            "project_id": project_id,
            "storage_info": storage_info,
            "file_paths": {
                "video_path": project.video_path,
                "subtitle_path": project.subtitle_path
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取项目存储信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取项目存储信息失败: {str(e)}")

@router.delete("/projects/{project_id}/cleanup")
async def cleanup_project_files(
    project_id: str,
    keep_days: int = Query(30, description="保留天数"),
    db: Session = Depends(get_db)
):
    """
    清理项目旧文件
    
    - 清理超过指定天数的临时文件
    - 释放存储空间
    """
    try:
        # 验证项目是否存在
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 清理旧文件
        storage_service = StorageService(project_id)
        storage_service.cleanup_old_files(project_id, keep_days)
        
        return {
            "success": True,
            "project_id": project_id,
            "keep_days": keep_days,
            "message": f"项目 {project_id} 旧文件清理完成"
        }
        
    except Exception as e:
        logger.error(f"清理项目文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理项目文件失败: {str(e)}")
