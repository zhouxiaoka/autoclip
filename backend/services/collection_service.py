"""
合集服务
提供合集相关的业务逻辑
"""

import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from pathlib import Path
import json

from services.base import BaseService
from repositories.collection_repository import CollectionRepository
from models.collection import Collection
from schemas.collection import CollectionCreate, CollectionUpdate, CollectionResponse, CollectionListResponse, CollectionFilter
from schemas.base import PaginationParams, PaginationResponse
from models.project import Project
from models.clip import Clip

logger = logging.getLogger(__name__)


class CollectionService(BaseService[Collection, CollectionCreate, CollectionUpdate, CollectionResponse]):
    """Collection service with business logic and Pipeline integration."""
    
    def __init__(self, db: Session):
        repository = CollectionRepository(db)
        super().__init__(repository)
        self.db = db
    
    def create_collection(self, collection_data: CollectionCreate) -> Collection:
        """Create a new collection with business logic."""
        collection_dict = collection_data.model_dump()
        return self.create(**collection_dict)
    
    def update_collection(self, collection_id: str, collection_data: CollectionUpdate) -> Optional[Collection]:
        """Update a collection with business logic."""
        update_data = {k: v for k, v in collection_data.model_dump().items() if v is not None}
        if not update_data:
            return self.get(collection_id)
        
        return self.update(collection_id, **update_data)
    
    def get_collections_by_project(self, project_id: str, skip: int = 0, limit: int = 100) -> List[Collection]:
        """Get collections by project ID."""
        return self.repository.find_by(project_id=project_id)
    
    def get_collections_paginated(
        self, 
        pagination: PaginationParams,
        filters: Optional[CollectionFilter] = None
    ) -> CollectionListResponse:
        """Get paginated collections with filtering."""
        filter_dict = {}
        if filters:
            filter_data = filters.model_dump()
            filter_dict = {k: v for k, v in filter_data.items() if v is not None}
        
        items, pagination_response = self.get_paginated(pagination, filter_dict)
        
        # Convert to response schemas
        collection_responses = []
        for collection in items:
            status_obj = getattr(collection, 'status', None)
            status_value = status_obj.value if hasattr(status_obj, 'value') else 'created'
            
            # 获取clip_ids
            clip_ids = []
            metadata = getattr(collection, 'collection_metadata', {}) or {}
            if metadata and 'clip_ids' in metadata:
                clip_ids = metadata['clip_ids']
            
            collection_responses.append(CollectionResponse(
                id=str(collection.id),
                project_id=str(collection.project_id),
                name=str(collection.name),
                description=str(collection.description) if collection.description else None,
                theme=getattr(collection, 'theme', None),
                status=status_value,
                tags=getattr(collection, 'tags', []) or [],
                metadata=getattr(collection, 'collection_metadata', {}) or {},
                created_at=getattr(collection, 'created_at', None) if isinstance(getattr(collection, 'created_at', None), (type(None), __import__('datetime').datetime)) else None,
                updated_at=getattr(collection, 'updated_at', None) if isinstance(getattr(collection, 'updated_at', None), (type(None), __import__('datetime').datetime)) else None,
                total_clips=getattr(collection, 'clips_count', 0) or 0,
                clip_ids=clip_ids
            ))
        
        return CollectionListResponse(
            items=collection_responses,
            pagination=pagination_response
        )
    
    def create_collections_from_pipeline_result(self, project_id: int, clustering_result: Dict[str, Any]) -> List[Collection]:
        """从Pipeline聚类结果创建合集
        
        Args:
            project_id: 项目ID
            clustering_result: Pipeline步骤5的聚类结果
            
        Returns:
            创建的合集列表
        """
        logger.info(f"从Pipeline结果为项目 {project_id} 创建合集")
        
        try:
            collections = []
            
            # 获取项目信息
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"项目 {project_id} 不存在")
            
            # 解析聚类结果
            if not clustering_result.get('success'):
                raise ValueError(f"聚类结果无效: {clustering_result.get('error')}")
            
            clusters_data = clustering_result.get('data', {})
            clusters = clusters_data.get('clusters', [])
            
            for i, cluster in enumerate(clusters):
                # 创建合集
                collection_data = {
                    'title': cluster.get('title', f'合集 {i+1}'),
                    'description': cluster.get('description', ''),
                    'project_id': project_id,
                    'theme': cluster.get('theme', ''),
                    'clip_count': len(cluster.get('clips', [])),
                    'total_duration': sum(clip.get('duration', 0) for clip in cluster.get('clips', [])),
                    'metadata': {
                        'cluster_id': cluster.get('cluster_id'),
                        'confidence_score': cluster.get('confidence_score', 0.0),
                        'keywords': cluster.get('keywords', []),
                        'created_from_pipeline': True
                    }
                }
                
                collection = Collection(**collection_data)
                self.db.add(collection)
                self.db.flush()  # 获取ID但不提交
                
                # 关联切片到合集
                self._associate_clips_to_collection(collection.id, cluster.get('clips', []))
                
                collections.append(collection)
                logger.info(f"创建合集: {collection.title} (包含 {collection.clip_count} 个切片)")
            
            self.db.commit()
            logger.info(f"成功为项目 {project_id} 创建了 {len(collections)} 个合集")
            
            return collections
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"从Pipeline结果创建合集失败: {str(e)}")
            raise
    
    def _associate_clips_to_collection(self, collection_id: int, clips_data: List[Dict[str, Any]]):
        """将切片关联到合集
        
        Args:
            collection_id: 合集ID
            clips_data: 切片数据列表
        """
        for clip_data in clips_data:
            # 查找或创建切片
            clip = self._find_or_create_clip(clip_data)
            if clip:
                # 更新切片的合集关联
                clip.collection_id = collection_id
                self.db.add(clip)
    
    def _find_or_create_clip(self, clip_data: Dict[str, Any]) -> Optional[Clip]:
        """查找或创建切片
        
        Args:
            clip_data: 切片数据
            
        Returns:
            切片对象
        """
        try:
            # 根据时间范围查找现有切片
            start_time = clip_data.get('start_time')
            end_time = clip_data.get('end_time')
            project_id = clip_data.get('project_id')
            
            if start_time is not None and end_time is not None and project_id:
                existing_clip = self.db.query(Clip).filter(
                    Clip.project_id == project_id,
                    Clip.start_time == start_time,
                    Clip.end_time == end_time
                ).first()
                
                if existing_clip:
                    return existing_clip
            
            # 创建新切片
            clip_data_clean = {
                'title': clip_data.get('title', ''),
                'description': clip_data.get('description', ''),
                'start_time': start_time,
                'end_time': end_time,
                'duration': clip_data.get('duration', 0),
                'project_id': project_id,
                'score': clip_data.get('score', 0.0),
                'metadata': {
                    'created_from_pipeline': True,
                    'original_text': clip_data.get('text', ''),
                    'keywords': clip_data.get('keywords', []),
                    'confidence': clip_data.get('confidence', 0.0)
                }
            }
            
            clip = Clip(**clip_data_clean)
            self.db.add(clip)
            return clip
            
        except Exception as e:
            logger.error(f"创建切片失败: {str(e)}")
            return None
    
    def generate_collection_video(self, collection_id: int, output_path: Optional[Path] = None) -> Dict[str, Any]:
        """生成合集视频
        
        Args:
            collection_id: 合集ID
            output_path: 输出路径
            
        Returns:
            生成结果
        """
        logger.info(f"生成合集 {collection_id} 的视频")
        
        try:
            collection = self.get(collection_id)
            if not collection:
                raise ValueError(f"合集 {collection_id} 不存在")
            
            # 获取合集中的所有切片
            clips = self.db.query(Clip).filter(Clip.collection_id == collection_id).all()
            
            if not clips:
                raise ValueError(f"合集 {collection_id} 中没有切片")
            
            # 使用Pipeline的视频生成功能
            from services.pipeline_adapter import create_pipeline_adapter
            pipeline_adapter = create_pipeline_adapter(self.db)
            
            # 准备切片数据
            clips_data = []
            for clip in clips:
                clips_data.append({
                    'start_time': clip.start_time,
                    'end_time': clip.end_time,
                    'title': clip.title,
                    'score': clip.score
                })
            
            # 生成合集视频
            result = pipeline_adapter._step6_video_for_collection(
                collection.project_id,
                clips_data,
                collection.title,
                output_path
            )
            
            # 更新合集的视频路径
            if result.get('success') and result.get('data', {}).get('video_path'):
                collection.video_path = result['data']['video_path']
                collection.status = 'completed'
                self.db.commit()
            
            return result
            
        except Exception as e:
            logger.error(f"生成合集视频失败: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_collection_statistics(self, project_id: int) -> Dict[str, Any]:
        """获取项目的合集统计信息
        
        Args:
            project_id: 项目ID
            
        Returns:
            统计信息
        """
        collections = self.get_collections_by_project(str(project_id))
        
        total_collections = len(collections)
        total_clips = sum(collection.clip_count for collection in collections)
        total_duration = sum(collection.total_duration for collection in collections)
        
        # 按主题分组统计
        theme_stats = {}
        for collection in collections:
            theme = collection.theme or '未分类'
            if theme not in theme_stats:
                theme_stats[theme] = {
                    'count': 0,
                    'clips': 0,
                    'duration': 0
                }
            theme_stats[theme]['count'] += 1
            theme_stats[theme]['clips'] += collection.clip_count
            theme_stats[theme]['duration'] += collection.total_duration
        
        return {
            'total_collections': total_collections,
            'total_clips': total_clips,
            'total_duration': total_duration,
            'average_clips_per_collection': total_clips / total_collections if total_collections > 0 else 0,
            'average_duration_per_collection': total_duration / total_collections if total_collections > 0 else 0,
            'theme_statistics': theme_stats
        }
    
    def delete(self, collection_id: str) -> bool:
        """删除合集 - 删除数据库记录并记录删除信息"""
        try:
            # 获取合集信息
            collection = self.get(collection_id)
            if not collection:
                logger.warning(f"合集不存在: {collection_id}")
                return False
            
            # 获取项目目录
            from core.config import get_data_directory
            data_dir = get_data_directory()
            project_dir = data_dir / "projects" / collection.project_id
            
            # 删除数据库记录
            success = super().delete(collection_id)
            if not success:
                logger.error(f"删除数据库记录失败: {collection_id}")
                return False
            
            # 记录删除信息到文件系统
            self._record_collection_deletion(project_dir, collection_id)
            
            logger.info(f"合集删除成功: {collection_id}")
            return True
            
        except Exception as e:
            logger.error(f"删除合集失败: {collection_id}, 错误: {str(e)}")
            return False
    
    def _record_collection_deletion(self, project_dir: Path, collection_id: str):
        """记录合集删除信息到文件系统"""
        try:
            deleted_file = project_dir / "deleted_collections.json"
            
            # 读取现有的删除记录
            deleted_collections = {"deleted_collection_ids": []}
            if deleted_file.exists():
                try:
                    with open(deleted_file, 'r', encoding='utf-8') as f:
                        deleted_collections = json.load(f)
                except Exception as e:
                    logger.warning(f"读取删除记录失败: {e}")
            
            # 添加新的删除记录
            if collection_id not in deleted_collections["deleted_collection_ids"]:
                deleted_collections["deleted_collection_ids"].append(collection_id)
                
                # 写入文件
                with open(deleted_file, 'w', encoding='utf-8') as f:
                    json.dump(deleted_collections, f, ensure_ascii=False, indent=2)
                
                logger.info(f"已记录合集删除: {collection_id}")
            
        except Exception as e:
            logger.error(f"记录合集删除失败: {collection_id}, 错误: {str(e)}")