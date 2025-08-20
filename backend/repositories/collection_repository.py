"""
合集Repository
提供合集相关的数据访问操作
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func
from pathlib import Path
from .base import BaseRepository
from models.collection import Collection, CollectionStatus

class CollectionRepository(BaseRepository[Collection]):
    """合集Repository类"""
    
    def __init__(self, db: Session):
        super().__init__(Collection, db)
    
    def get_by_project(self, project_id: str) -> List[Collection]:
        """
        获取项目的所有合集
        
        Args:
            project_id: 项目ID
            
        Returns:
            合集列表
        """
        return self.find_by(project_id=project_id)
    
    def get_by_status(self, status: CollectionStatus) -> List[Collection]:
        """
        根据状态获取合集列表
        
        Args:
            status: 合集状态
            
        Returns:
            合集列表
        """
        return self.find_by(status=status)
    
    def get_by_project_and_status(self, project_id: str, status: CollectionStatus) -> List[Collection]:
        """
        根据项目和状态获取合集列表
        
        Args:
            project_id: 项目ID
            status: 合集状态
            
        Returns:
            合集列表
        """
        return self.find_by(project_id=project_id, status=status)
    
    def get_by_theme(self, project_id: str, theme: str) -> List[Collection]:
        """
        根据主题获取合集列表
        
        Args:
            project_id: 项目ID
            theme: 主题
            
        Returns:
            合集列表
        """
        return self.find_by(project_id=project_id, theme=theme)
    
    def get_completed_collections(self, project_id: str) -> List[Collection]:
        """
        获取已完成的合集
        
        Args:
            project_id: 项目ID
            
        Returns:
            已完成的合集列表
        """
        return self.find_by(project_id=project_id, status=CollectionStatus.COMPLETED)
    
    def search_collections(self, project_id: str, keyword: str) -> List[Collection]:
        """
        搜索合集
        
        Args:
            project_id: 项目ID
            keyword: 搜索关键词
            
        Returns:
            匹配的合集列表
        """
        return self.db.query(self.model).filter(
            self.model.project_id == project_id,
            (self.model.name.contains(keyword) | 
             self.model.description.contains(keyword) |
             self.model.theme.contains(keyword))
        ).all()
    
    def get_collections_by_clips_count(self, project_id: str, min_clips: int = 1) -> List[Collection]:
        """
        根据切片数量获取合集
        
        Args:
            project_id: 项目ID
            min_clips: 最少切片数量
            
        Returns:
            合集列表
        """
        return self.db.query(self.model).filter(
            self.model.project_id == project_id,
            self.model.clips_count >= min_clips
        ).order_by(desc(self.model.clips_count)).all()
    
    def create_collection(self, collection_data: Dict[str, Any]) -> Collection:
        """创建合集记录（分离存储模式）"""
        from services.storage_service import StorageService
        import uuid
        
        # 生成合集ID（如果没有提供）
        if "id" not in collection_data:
            collection_data["id"] = str(uuid.uuid4())
        
        # 1. 保存合集文件到文件系统
        storage_service = StorageService(collection_data["project_id"])
        export_path = storage_service.save_collection_file(collection_data, collection_data["id"])
        
        # 2. 保存完整数据到文件系统
        metadata_path = storage_service.save_metadata(collection_data, f"collection_{collection_data['id']}")
        
        # 3. 保存元数据到数据库（只存储路径引用）
        collection = Collection(
            id=collection_data["id"],
            project_id=collection_data["project_id"],
            name=collection_data["name"],
            description=collection_data.get("description"),
            theme=collection_data.get("theme"),
            tags=collection_data.get("tags"),
            total_duration=collection_data.get("total_duration"),
            clips_count=collection_data.get("clips_count", 0),
            export_path=export_path,  # 只存储路径
            collection_metadata={
                'metadata_file': metadata_path,  # 完整数据文件路径
                'clip_ids': collection_data.get('clip_ids', []),
                'collection_type': collection_data.get('collection_type', 'ai_recommended'),
                'collection_id': collection_data["id"],
                'created_at': collection_data.get("created_at")
            }
        )
        
        self.db.add(collection)
        self.db.commit()
        return collection
    
    def get_collection_file(self, collection_id: str) -> Optional[Path]:
        """获取合集文件路径"""
        collection = self.get_by_id(collection_id)
        if collection and collection.export_path:
            return Path(collection.export_path)
        return None
    
    def get_collection_content(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """获取合集完整内容"""
        collection = self.get_by_id(collection_id)
        if not collection:
            return None
        
        # 从文件系统获取完整数据
        if collection.collection_metadata and 'metadata_file' in collection.collection_metadata:
            from services.storage_service import StorageService
            storage_service = StorageService(collection.project_id)
            return storage_service.get_file_content(collection.collection_metadata['metadata_file'])
        
        return None
    
    def get_collections_by_duration_range(self, project_id: str, min_duration: int, max_duration: int) -> List[Collection]:
        """
        根据时长范围获取合集
        
        Args:
            project_id: 项目ID
            min_duration: 最小时长（秒）
            max_duration: 最大时长（秒）
            
        Returns:
            合集列表
        """
        return self.db.query(self.model).filter(
            self.model.project_id == project_id,
            self.model.total_duration >= min_duration,
            self.model.total_duration <= max_duration
        ).order_by(asc(self.model.total_duration)).all()
    
    def get_collections_statistics(self, project_id: str) -> dict:
        """
        获取合集统计信息
        
        Args:
            project_id: 项目ID
            
        Returns:
            统计信息字典
        """
        total_collections = self.db.query(self.model).filter(
            self.model.project_id == project_id
        ).count()
        
        completed_collections = self.db.query(self.model).filter(
            self.model.project_id == project_id,
            self.model.status == CollectionStatus.COMPLETED
        ).count()
        
        avg_clips_count = self.db.query(func.avg(self.model.clips_count)).filter(
            self.model.project_id == project_id
        ).scalar()
        
        total_duration = self.db.query(func.sum(self.model.total_duration)).filter(
            self.model.project_id == project_id
        ).scalar()
        
        return {
            "total": total_collections,
            "completed": completed_collections,
            "avg_clips_count": float(avg_clips_count) if avg_clips_count else 0.0,
            "total_duration": int(total_duration) if total_duration else 0,
            "completion_rate": (completed_collections / total_collections * 100) if total_collections > 0 else 0
        }
    
    def update_collection_status(self, collection_id: str, status: CollectionStatus) -> Optional[Collection]:
        """
        更新合集状态
        
        Args:
            collection_id: 合集ID
            status: 新状态
            
        Returns:
            更新后的合集实例或None
        """
        return self.update(collection_id, status=status)
    
    def update_collection_clips_count(self, collection_id: str, clips_count: int) -> Optional[Collection]:
        """
        更新合集切片数量
        
        Args:
            collection_id: 合集ID
            clips_count: 切片数量
            
        Returns:
            更新后的合集实例或None
        """
        return self.update(collection_id, clips_count=clips_count)
    
    def update_collection_duration(self, collection_id: str, total_duration: int) -> Optional[Collection]:
        """
        更新合集总时长
        
        Args:
            collection_id: 合集ID
            total_duration: 总时长（秒）
            
        Returns:
            更新后的合集实例或None
        """
        return self.update(collection_id, total_duration=total_duration)
    
    def get_collections_with_clips(self, project_id: str) -> List[Collection]:
        """
        获取包含切片的合集详情
        
        Args:
            project_id: 项目ID
            
        Returns:
            合集列表
        """
        return self.db.query(self.model).filter(
            self.model.project_id == project_id
        ).all()
    
    def get_collection_by_theme_and_size(self, project_id: str, theme: str, target_size: int = 5) -> Optional[Collection]:
        """
        根据主题和目标大小获取合集
        
        Args:
            project_id: 项目ID
            theme: 主题
            target_size: 目标大小
            
        Returns:
            合集实例或None
        """
        return self.db.query(self.model).filter(
            self.model.project_id == project_id,
            self.model.theme == theme,
            self.model.clips_count == target_size
        ).first()