"""
优化存储服务 - 解决双重存储问题
数据库只存储元数据，文件系统存储实际文件
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from ..core.config import get_data_directory
from ..models.project import Project
from ..models.clip import Clip
from ..models.collection import Collection

logger = logging.getLogger(__name__)


class OptimizedStorageService:
    """优化存储服务 - 数据库存储元数据，文件系统存储实际文件"""
    
    def __init__(self, db: Session, project_id: str):
        self.db = db
        self.project_id = project_id
        self.data_dir = get_data_directory()
        self.project_dir = self.data_dir / "projects" / project_id
        
        # 确保项目目录结构存在
        self._ensure_project_structure()
    
    def _ensure_project_structure(self):
        """确保项目目录结构存在"""
        directories = [
            self.project_dir / "raw",           # 原始文件
            self.project_dir / "processing",    # 处理中间文件
            self.project_dir / "output" / "clips",      # 切片文件
            self.project_dir / "output" / "collections" # 合集文件
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    # ==================== 项目文件管理 ====================
    
    def save_project_file(self, file_path: Path, file_type: str = "video") -> str:
        """保存项目文件到文件系统，返回相对路径"""
        try:
            if file_type == "video":
                target_dir = self.project_dir / "raw"
                target_name = f"input_video{file_path.suffix}"
            elif file_type == "subtitle":
                target_dir = self.project_dir / "raw"
                target_name = f"input_subtitle{file_path.suffix}"
            else:
                target_dir = self.project_dir / "raw"
                target_name = file_path.name
            
            target_path = target_dir / target_name
            shutil.copy2(file_path, target_path)
            
            # 返回相对路径，用于存储在数据库中
            relative_path = f"projects/{self.project_id}/raw/{target_name}"
            logger.info(f"项目文件已保存: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"保存项目文件失败: {e}")
            raise
    
    def get_project_file_path(self, relative_path: str) -> Path:
        """根据相对路径获取完整文件路径"""
        return self.data_dir / relative_path
    
    # ==================== 切片文件管理 ====================
    
    def save_clip_file(self, clip_data: Dict[str, Any], clip_id: str) -> str:
        """保存切片文件到文件系统，返回相对路径"""
        try:
            # 这里应该包含实际的切片文件保存逻辑
            # 暂时返回模拟路径
            clip_file = f"clip_{clip_id}.mp4"
            target_path = self.project_dir / "output" / "clips" / clip_file
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建模拟文件（实际应该保存真实的切片文件）
            target_path.touch()
            
            # 返回相对路径
            relative_path = f"projects/{self.project_id}/output/clips/{clip_file}"
            logger.info(f"切片文件已保存: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"保存切片文件失败: {e}")
            raise
    
    def save_clip_metadata(self, clip_data: Dict[str, Any], clip_id: str) -> Clip:
        """保存切片元数据到数据库"""
        try:
            # 创建切片记录，只存储元数据
            clip = Clip(
                id=clip_id,
                project_id=self.project_id,
                title=clip_data.get('title', ''),
                description=clip_data.get('description', ''),
                start_time=clip_data.get('start_time', 0),
                end_time=clip_data.get('end_time', 0),
                duration=clip_data.get('duration', 0),
                score=clip_data.get('score', 0.0),
                recommendation_reason=clip_data.get('recommendation_reason', ''),
                video_path=self.save_clip_file(clip_data, clip_id),  # 存储相对路径
                thumbnail_path=clip_data.get('thumbnail_path', ''),
                processing_step=clip_data.get('processing_step', 6),
                tags=clip_data.get('tags', []),
                clip_metadata=clip_data.get('metadata', {})  # 存储精简元数据
            )
            
            self.db.add(clip)
            self.db.commit()
            self.db.refresh(clip)
            
            logger.info(f"切片元数据已保存到数据库: {clip_id}")
            return clip
            
        except Exception as e:
            logger.error(f"保存切片元数据失败: {e}")
            self.db.rollback()
            raise
    
    # ==================== 合集文件管理 ====================
    
    def save_collection_file(self, collection_data: Dict[str, Any], collection_id: str) -> str:
        """保存合集文件到文件系统，返回相对路径"""
        try:
            # 这里应该包含实际的合集文件保存逻辑
            # 暂时返回模拟路径
            collection_file = f"collection_{collection_id}.mp4"
            target_path = self.project_dir / "output" / "collections" / collection_file
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建模拟文件（实际应该保存真实的合集文件）
            target_path.touch()
            
            # 返回相对路径
            relative_path = f"projects/{self.project_id}/output/collections/{collection_file}"
            logger.info(f"合集文件已保存: {relative_path}")
            return relative_path
            
        except Exception as e:
            logger.error(f"保存合集文件失败: {e}")
            raise
    
    def save_collection_metadata(self, collection_data: Dict[str, Any], collection_id: str) -> Collection:
        """保存合集元数据到数据库"""
        try:
            # 创建合集记录，只存储元数据
            collection = Collection(
                id=collection_id,
                project_id=self.project_id,
                name=collection_data.get('name', ''),
                description=collection_data.get('description', ''),
                clip_ids=collection_data.get('clip_ids', []),
                video_path=self.save_collection_file(collection_data, collection_id),  # 存储相对路径
                thumbnail_path=collection_data.get('thumbnail_path', ''),
                tags=collection_data.get('tags', []),
                collection_metadata=collection_data.get('metadata', {})  # 存储精简元数据
            )
            
            self.db.add(collection)
            self.db.commit()
            self.db.refresh(collection)
            
            logger.info(f"合集元数据已保存到数据库: {collection_id}")
            return collection
            
        except Exception as e:
            logger.error(f"保存合集元数据失败: {e}")
            self.db.rollback()
            raise
    
    # ==================== 处理中间文件管理 ====================
    
    def save_processing_metadata(self, metadata: Dict[str, Any], step: str) -> str:
        """保存处理中间元数据到文件系统"""
        try:
            metadata_file = self.project_dir / "processing" / f"{step}.json"
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            logger.info(f"处理元数据已保存: {metadata_file}")
            return str(metadata_file)
            
        except Exception as e:
            logger.error(f"保存处理元数据失败: {e}")
            raise
    
    def get_processing_metadata(self, step: str) -> Optional[Dict[str, Any]]:
        """获取处理中间元数据"""
        try:
            metadata_file = self.project_dir / "processing" / f"{step}.json"
            
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
            
        except Exception as e:
            logger.error(f"获取处理元数据失败: {e}")
            return None
    
    # ==================== 数据查询方法 ====================
    
    def get_project_clips(self) -> List[Clip]:
        """获取项目的所有切片（从数据库）"""
        return self.db.query(Clip).filter(Clip.project_id == self.project_id).all()
    
    def get_project_collections(self) -> List[Collection]:
        """获取项目的所有合集（从数据库）"""
        return self.db.query(Collection).filter(Collection.project_id == self.project_id).all()
    
    def get_clip_file_path(self, clip: Clip) -> Path:
        """获取切片的完整文件路径"""
        if clip.video_path:
            return self.data_dir / clip.video_path
        return None
    
    def get_collection_file_path(self, collection: Collection) -> Path:
        """获取合集的完整文件路径"""
        if collection.video_path:
            return self.data_dir / collection.video_path
        return None
    
    # ==================== 清理方法 ====================
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        temp_dir = self.data_dir / "temp"
        if temp_dir.exists():
            for temp_file in temp_dir.iterdir():
                if temp_file.is_file():
                    temp_file.unlink()
                    logger.info(f"清理临时文件: {temp_file}")
    
    def cleanup_old_files(self, keep_days: int = 30):
        """清理旧文件"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=keep_days)
            
            # 清理旧的临时文件
            temp_dir = self.data_dir / "temp"
            if temp_dir.exists():
                for temp_file in temp_dir.iterdir():
                    if temp_file.is_file() and temp_file.stat().st_mtime < cutoff_date.timestamp():
                        temp_file.unlink()
                        logger.info(f"清理旧临时文件: {temp_file}")
            
            logger.info(f"清理完成，保留 {keep_days} 天内的文件")
            
        except Exception as e:
            logger.error(f"清理旧文件失败: {e}")
    
    # ==================== 数据迁移方法 ====================
    
    def migrate_from_old_storage(self, old_project_dir: Path) -> Dict[str, Any]:
        """从旧存储格式迁移数据"""
        try:
            logger.info(f"开始迁移项目数据: {self.project_id}")
            
            migrated_files = []
            migrated_metadata = []
            
            # 迁移原始文件
            if (old_project_dir / "raw").exists():
                for file_path in (old_project_dir / "raw").iterdir():
                    if file_path.is_file():
                        relative_path = self.save_project_file(file_path)
                        migrated_files.append(relative_path)
            
            # 迁移处理元数据
            if (old_project_dir / "processing").exists():
                for metadata_file in (old_project_dir / "processing").iterdir():
                    if metadata_file.suffix == '.json':
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        
                        step_name = metadata_file.stem
                        self.save_processing_metadata(metadata, step_name)
                        migrated_metadata.append(step_name)
            
            # 迁移输出文件
            if (old_project_dir / "output").exists():
                # 迁移切片文件
                clips_dir = old_project_dir / "output" / "clips"
                if clips_dir.exists():
                    for clip_file in clips_dir.iterdir():
                        if clip_file.is_file():
                            target_path = self.project_dir / "output" / "clips" / clip_file.name
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(clip_file, target_path)
                            migrated_files.append(f"projects/{self.project_id}/output/clips/{clip_file.name}")
                
                # 迁移合集文件
                collections_dir = old_project_dir / "output" / "collections"
                if collections_dir.exists():
                    for collection_file in collections_dir.iterdir():
                        if collection_file.is_file():
                            target_path = self.project_dir / "output" / "collections" / collection_file.name
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(collection_file, target_path)
                            migrated_files.append(f"projects/{self.project_id}/output/collections/{collection_file.name}")
            
            logger.info(f"数据迁移完成: {len(migrated_files)} 个文件, {len(migrated_metadata)} 个元数据")
            
            return {
                "success": True,
                "migrated_files": migrated_files,
                "migrated_metadata": migrated_metadata
            }
            
        except Exception as e:
            logger.error(f"数据迁移失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
