"""
项目Repository
提供项目相关的数据访问操作
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
from .base import BaseRepository
from backend.models.project import Project, ProjectStatus, ProjectType

class ProjectRepository(BaseRepository[Project]):
    """项目Repository类"""
    
    def __init__(self, db: Session):
        super().__init__(Project, db)
    
    def get_by_status(self, status: ProjectStatus) -> List[Project]:
        """
        根据状态获取项目列表
        
        Args:
            status: 项目状态
            
        Returns:
            项目列表
        """
        return self.find_by(status=status)
    
    def get_by_category(self, category: ProjectType) -> List[Project]:
        """
        根据项目类型获取项目列表
        
        Args:
            category: 项目类型
            
        Returns:
            项目列表
        """
        return self.find_by(project_type=category)
    
    def get_recent_projects(self, limit: int = 10) -> List[Project]:
        """
        获取最近创建的项目
        
        Args:
            limit: 返回数量限制
            
        Returns:
            最近的项目列表
        """
        return self.db.query(self.model).order_by(
            desc(self.model.created_at)
        ).limit(limit).all()
    
    def get_processing_projects(self) -> List[Project]:
        """
        获取正在处理的项目
        
        Returns:
            正在处理的项目列表
        """
        return self.find_by(status=ProjectStatus.PROCESSING)
    
    def get_completed_projects(self) -> List[Project]:
        """
        获取已完成的项目
        
        Returns:
            已完成的项目列表
        """
        return self.find_by(status=ProjectStatus.COMPLETED)
    
    def get_error_projects(self) -> List[Project]:
        """
        获取出错的项目
        
        Returns:
            出错的项目列表
        """
        return self.find_by(status=ProjectStatus.FAILED)
    
    def search_projects(self, keyword: str) -> List[Project]:
        """
        搜索项目
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            匹配的项目列表
        """
        return self.db.query(self.model).filter(
            self.model.name.contains(keyword) | 
            self.model.description.contains(keyword)
        ).all()
    
    def get_projects_with_clips_count(self, skip: int = 0, limit: int = 100) -> List[Project]:
        """
        获取项目列表，包含切片数量
        
        Args:
            skip: 跳过的记录数
            limit: 返回的记录数限制
            
        Returns:
            项目列表
        """
        return self.db.query(self.model).options(
            # 这里可以添加预加载选项，减少N+1查询问题
        ).offset(skip).limit(limit).all()
    
    def get_project_with_details(self, project_id: str) -> Optional[Project]:
        """
        获取项目详情，包含关联的切片和合集
        
        Args:
            project_id: 项目ID
            
        Returns:
            项目实例或None
        """
        return self.db.query(self.model).filter(
            self.model.id == project_id
        ).first()
    
    def update_project_status(self, project_id: str, status: ProjectStatus) -> Optional[Project]:
        """
        更新项目状态
        
        Args:
            project_id: 项目ID
            status: 新状态
            
        Returns:
            更新后的项目实例或None
        """
        return self.update(project_id, status=status)
    
    def get_projects_by_date_range(self, start_date, end_date) -> List[Project]:
        """
        根据日期范围获取项目
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            项目列表
        """
        return self.db.query(self.model).filter(
            self.model.created_at >= start_date,
            self.model.created_at <= end_date
        ).order_by(desc(self.model.created_at)).all()
    
    def get_project_statistics(self) -> dict:
        """
        获取项目统计信息
        
        Returns:
            统计信息字典
        """
        total_projects = self.count()
        processing_projects = len(self.get_processing_projects())
        completed_projects = len(self.get_completed_projects())
        error_projects = len(self.get_error_projects())
        
        return {
            "total": total_projects,
            "processing": processing_projects,
            "completed": completed_projects,
            "error": error_projects,
            "success_rate": (completed_projects / total_projects * 100) if total_projects > 0 else 0
        }