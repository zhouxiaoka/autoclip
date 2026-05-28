"""
示例项目API
用于首次运行向导创建示例项目
"""

import json
import os
from pathlib import Path
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.desktop_config import get_desktop_config, DesktopConfig
from backend.models.project import Project
from backend.models.clip import Clip
from backend.models.collection import Collection
from backend.repositories.project_repository import ProjectRepository
from backend.repositories.clip_repository import ClipRepository
from backend.repositories.collection_repository import CollectionRepository
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def check_desktop_mode():
    """检查是否在桌面模式下运行"""
    if not os.getenv("AUTOCLIP_DESKTOP_MODE"):
        raise HTTPException(status_code=403, detail="此功能仅在桌面模式下可用")

@router.post("/example-project/create")
async def create_example_project(
    db: Session = Depends(get_db),
    config: DesktopConfig = Depends(get_desktop_config)
):
    """创建示例项目"""
    check_desktop_mode()
    
    try:
        # 检查是否已存在示例项目
        project_repo = ProjectRepository(db)
        existing_project = project_repo.get_by_name("AutoClip 示例项目")
        if existing_project:
            return {
                "success": True,
                "message": "示例项目已存在",
                "project_id": existing_project.id
            }
        
        # 读取示例项目数据
        example_data_path = Path(__file__).parent.parent.parent.parent / "data" / "example_project.json"
        if not example_data_path.exists():
            raise HTTPException(status_code=404, detail="示例项目数据文件不存在")
        
        with open(example_data_path, 'r', encoding='utf-8') as f:
            example_data = json.load(f)
        
        # 创建示例项目
        project_data = example_data["project"]
        project = Project(
            id=project_data["id"],
            name=project_data["name"],
            description=project_data["description"],
            video_path=project_data["video_path"],
            srt_path=project_data["srt_path"],
            status=project_data["status"],
            processing_config={
                "chunk_size": 5000,
                "min_score_threshold": 0.7,
                "max_clips": 5,
                "model": "qwen-plus"
            }
        )
        
        created_project = project_repo.create(project)
        
        # 创建示例片段
        clip_repo = ClipRepository(db)
        for clip_data in example_data["clips"]:
            clip = Clip(
                id=clip_data["id"],
                project_id=created_project.id,
                title=clip_data["title"],
                start_time=clip_data["start_time"],
                end_time=clip_data["end_time"],
                score=clip_data["score"],
                reason=clip_data["reason"],
                content=clip_data["content"],
                status="completed"
            )
            clip_repo.create(clip)
        
        # 创建示例合集
        collection_repo = CollectionRepository(db)
        for collection_data in example_data["collections"]:
            collection = Collection(
                id=collection_data["id"],
                project_id=created_project.id,
                title=collection_data["title"],
                description=collection_data["description"],
                clips=collection_data["clips"],
                duration=collection_data["duration"],
                status="completed"
            )
            collection_repo.create(collection)
        
        logger.info(f"示例项目创建成功: {created_project.id}")
        
        return {
            "success": True,
            "message": "示例项目创建成功",
            "project_id": created_project.id,
            "project": {
                "id": created_project.id,
                "name": created_project.name,
                "description": created_project.description,
                "status": created_project.status,
                "clips_count": len(example_data["clips"]),
                "collections_count": len(example_data["collections"])
            }
        }
        
    except Exception as e:
        logger.error(f"创建示例项目失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建示例项目失败: {str(e)}")

@router.get("/example-project/info")
async def get_example_project_info():
    """获取示例项目信息"""
    check_desktop_mode()
    
    try:
        # 读取示例项目数据
        example_data_path = Path(__file__).parent.parent.parent.parent / "data" / "example_project.json"
        if not example_data_path.exists():
            raise HTTPException(status_code=404, detail="示例项目数据文件不存在")
        
        with open(example_data_path, 'r', encoding='utf-8') as f:
            example_data = json.load(f)
        
        return {
            "success": True,
            "project_info": {
                "name": example_data["project"]["name"],
                "description": example_data["project"]["description"],
                "clips_count": len(example_data["clips"]),
                "collections_count": len(example_data["collections"]),
                "total_duration": sum(clip["end_time"] - clip["start_time"] for clip in example_data["clips"])
            }
        }
        
    except Exception as e:
        logger.error(f"获取示例项目信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取示例项目信息失败: {str(e)}")

@router.delete("/example-project")
async def delete_example_project(
    db: Session = Depends(get_db)
):
    """删除示例项目"""
    check_desktop_mode()
    
    try:
        project_repo = ProjectRepository(db)
        example_project = project_repo.get_by_name("AutoClip 示例项目")
        
        if not example_project:
            return {
                "success": True,
                "message": "示例项目不存在"
            }
        
        # 删除相关数据
        clip_repo = ClipRepository(db)
        collection_repo = CollectionRepository(db)
        
        # 删除片段
        clips = clip_repo.get_by_project_id(example_project.id)
        for clip in clips:
            clip_repo.delete(clip.id)
        
        # 删除合集
        collections = collection_repo.get_by_project_id(example_project.id)
        for collection in collections:
            collection_repo.delete(collection.id)
        
        # 删除项目
        project_repo.delete(example_project.id)
        
        logger.info(f"示例项目删除成功: {example_project.id}")
        
        return {
            "success": True,
            "message": "示例项目删除成功"
        }
        
    except Exception as e:
        logger.error(f"删除示例项目失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除示例项目失败: {str(e)}")
