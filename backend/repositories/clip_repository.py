"""
切片Repository
提供切片相关的数据访问操作
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func
from .base import BaseRepository
from models.clip import Clip, ClipStatus

class ClipRepository(BaseRepository[Clip]):
    """切片Repository类"""
    
    def __init__(self, db: Session):
        super().__init__(Clip, db)
    
    def get_by_project(self, project_id: str) -> List[Clip]:
        """
        获取项目的所有切片
        
        Args:
            project_id: 项目ID
            
        Returns:
            切片列表
        """
        return self.find_by(project_id=project_id)
    
    def get_by_status(self, status: ClipStatus) -> List[Clip]:
        """
        根据状态获取切片列表
        
        Args:
            status: 切片状态
            
        Returns:
            切片列表
        """
        return self.find_by(status=status)
    
    def get_by_project_and_status(self, project_id: str, status: ClipStatus) -> List[Clip]:
        """
        根据项目和状态获取切片列表
        
        Args:
            project_id: 项目ID
            status: 切片状态
            
        Returns:
            切片列表
        """
        return self.find_by(project_id=project_id, status=status)
    
    def get_high_score_clips(self, project_id: str, min_score: float = 0.7, limit: int = 10) -> List[Clip]:
        """
        获取高分切片
        
        Args:
            project_id: 项目ID
            min_score: 最低评分
            limit: 返回数量限制
            
        Returns:
            高分切片列表
        """
        return self.db.query(self.model).filter(
            self.model.project_id == project_id,
            self.model.score >= min_score
        ).order_by(desc(self.model.score)).limit(limit).all()
    
    def get_clips_by_duration_range(self, project_id: str, min_duration: int, max_duration: int) -> List[Clip]:
        """
        根据时长范围获取切片
        
        Args:
            project_id: 项目ID
            min_duration: 最小时长（秒）
            max_duration: 最大时长（秒）
            
        Returns:
            切片列表
        """
        return self.db.query(self.model).filter(
            self.model.project_id == project_id,
            self.model.duration >= min_duration,
            self.model.duration <= max_duration
        ).order_by(asc(self.model.start_time)).all()
    
    def get_clips_by_time_range(self, project_id: str, start_time: int, end_time: int) -> List[Clip]:
        """
        根据时间范围获取切片
        
        Args:
            project_id: 项目ID
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            
        Returns:
            切片列表
        """
        return self.db.query(self.model).filter(
            self.model.project_id == project_id,
            self.model.start_time >= start_time,
            self.model.end_time <= end_time
        ).order_by(asc(self.model.start_time)).all()
    
    def search_clips(self, project_id: str, keyword: str) -> List[Clip]:
        """
        搜索切片
        
        Args:
            project_id: 项目ID
            keyword: 搜索关键词
            
        Returns:
            匹配的切片列表
        """
        return self.db.query(self.model).filter(
            self.model.project_id == project_id,
            (self.model.title.contains(keyword) | 
             self.model.description.contains(keyword) |
             self.model.recommendation_reason.contains(keyword))
        ).all()
    
    def get_clips_statistics(self, project_id: str) -> dict:
        """
        获取切片统计信息
        
        Args:
            project_id: 项目ID
            
        Returns:
            统计信息字典
        """
        total_clips = self.db.query(self.model).filter(
            self.model.project_id == project_id
        ).count()
        
        completed_clips = self.db.query(self.model).filter(
            self.model.project_id == project_id,
            self.model.status == ClipStatus.COMPLETED
        ).count()
        
        avg_score = self.db.query(func.avg(self.model.score)).filter(
            self.model.project_id == project_id,
            self.model.score.isnot(None)
        ).scalar()
        
        total_duration = self.db.query(func.sum(self.model.duration)).filter(
            self.model.project_id == project_id
        ).scalar()
        
        return {
            "total": total_clips,
            "completed": completed_clips,
            "avg_score": float(avg_score) if avg_score else 0.0,
            "total_duration": int(total_duration) if total_duration else 0,
            "completion_rate": (completed_clips / total_clips * 100) if total_clips > 0 else 0
        }
    
    def update_clip_status(self, clip_id: str, status: ClipStatus) -> Optional[Clip]:
        """
        更新切片状态
        
        Args:
            clip_id: 切片ID
            status: 新状态
            
        Returns:
            更新后的切片实例或None
        """
        return self.update(clip_id, status=status)
    
    def update_clip_score(self, clip_id: str, score: float) -> Optional[Clip]:
        """
        更新切片评分
        
        Args:
            clip_id: 切片ID
            score: 新评分
            
        Returns:
            更新后的切片实例或None
        """
        return self.update(clip_id, score=score)
    
    def get_clips_for_collection(self, project_id: str, collection_size: int = 5) -> List[Clip]:
        """
        获取适合合集的切片
        
        Args:
            project_id: 项目ID
            collection_size: 合集大小
            
        Returns:
            切片列表
        """
        return self.db.query(self.model).filter(
            self.model.project_id == project_id,
            self.model.status == ClipStatus.COMPLETED,
            self.model.score >= 0.7
        ).order_by(desc(self.model.score)).limit(collection_size).all()
    
    def get_clips_by_processing_step(self, project_id: str, step: int) -> List[Clip]:
        """
        根据处理步骤获取切片
        
        Args:
            project_id: 项目ID
            step: 处理步骤
            
        Returns:
            切片列表
        """
        return self.find_by(project_id=project_id, processing_step=step)