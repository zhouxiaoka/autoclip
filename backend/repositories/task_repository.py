"""
任务Repository
提供任务相关的数据访问操作
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func
from .base import BaseRepository
from ..models.task import Task, TaskStatus, TaskType

class TaskRepository(BaseRepository[Task]):
    """任务Repository类"""
    
    def __init__(self, db: Session):
        super().__init__(Task, db)
    
    def find_all(self, skip: int = 0, limit: int = 100, **filters) -> List[Task]:
        """
        获取所有任务，支持过滤和分页
        
        Args:
            skip: 跳过的记录数
            limit: 返回的记录数限制
            **filters: 过滤条件
            
        Returns:
            任务列表
        """
        query = self.db.query(self.model)
        
        # 应用过滤条件
        for key, value in filters.items():
            if hasattr(self.model, key) and value is not None:
                query = query.filter(getattr(self.model, key) == value)
        
        return query.offset(skip).limit(limit).all()
    
    def get_by_project(self, project_id: str) -> List[Task]:
        """
        获取项目的所有任务
        
        Args:
            project_id: 项目ID
            
        Returns:
            任务列表
        """
        return self.find_by(project_id=project_id)
    
    def get_by_status(self, status: TaskStatus) -> List[Task]:
        """
        根据状态获取任务列表
        
        Args:
            status: 任务状态
            
        Returns:
            任务列表
        """
        return self.find_by(status=status)
    
    def get_by_type(self, task_type: TaskType) -> List[Task]:
        """
        根据任务类型获取任务列表
        
        Args:
            task_type: 任务类型
            
        Returns:
            任务列表
        """
        return self.find_by(task_type=task_type)
    
    def get_by_project_and_status(self, project_id: str, status: TaskStatus) -> List[Task]:
        """
        根据项目和状态获取任务列表
        
        Args:
            project_id: 项目ID
            status: 任务状态
            
        Returns:
            任务列表
        """
        return self.find_by(project_id=project_id, status=status)
    
    def get_by_project_and_type(self, project_id: str, task_type: TaskType) -> List[Task]:
        """
        根据项目和任务类型获取任务列表
        
        Args:
            project_id: 项目ID
            task_type: 任务类型
            
        Returns:
            任务列表
        """
        return self.find_by(project_id=project_id, task_type=task_type)
    
    def get_pending_tasks(self) -> List[Task]:
        """
        获取待处理的任务
        
        Returns:
            待处理任务列表
        """
        return self.find_by(status=TaskStatus.PENDING)
    
    def get_running_tasks(self) -> List[Task]:
        """
        获取正在运行的任务
        
        Returns:
            正在运行的任务列表
        """
        return self.find_by(status=TaskStatus.RUNNING)
    
    def get_completed_tasks(self) -> List[Task]:
        """
        获取已完成的任务
        
        Returns:
            已完成的任务列表
        """
        return self.find_by(status=TaskStatus.COMPLETED)
    
    def get_failed_tasks(self) -> List[Task]:
        """
        获取失败的任务
        
        Returns:
            失败的任务列表
        """
        return self.find_by(status=TaskStatus.FAILED)
    
    def get_tasks_by_step(self, project_id: str, step: int) -> List[Task]:
        """
        根据处理步骤获取任务
        
        Args:
            project_id: 项目ID
            step: 处理步骤
            
        Returns:
            任务列表
        """
        return self.find_by(project_id=project_id, step=step)
    
    def get_next_pending_task(self) -> Optional[Task]:
        """
        获取下一个待处理任务
        
        Returns:
            下一个待处理任务或None
        """
        return self.db.query(self.model).filter(
            self.model.status == TaskStatus.PENDING
        ).order_by(asc(self.model.created_at)).first()
    
    def get_tasks_by_priority(self, priority: int) -> List[Task]:
        """
        根据优先级获取任务
        
        Args:
            priority: 优先级
            
        Returns:
            任务列表
        """
        return self.find_by(priority=priority)
    
    def update_task_status(self, task_id: str, status: TaskStatus) -> Optional[Task]:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 新状态
            
        Returns:
            更新后的任务实例或None
        """
        return self.update(task_id, status=status)
    
    def update_task_progress(self, task_id: str, progress: float) -> Optional[Task]:
        """
        更新任务进度
        
        Args:
            task_id: 任务ID
            progress: 进度百分比
            
        Returns:
            更新后的任务实例或None
        """
        return self.update(task_id, progress=progress)
    
    def update_task_result(self, task_id: str, result: dict) -> Optional[Task]:
        """
        更新任务结果
        
        Args:
            task_id: 任务ID
            result: 任务结果
            
        Returns:
            更新后的任务实例或None
        """
        return self.update(task_id, result=result)
    
    def update_task_error(self, task_id: str, error_message: str) -> Optional[Task]:
        """
        更新任务错误信息
        
        Args:
            task_id: 任务ID
            error_message: 错误信息
            
        Returns:
            更新后的任务实例或None
        """
        return self.update(task_id, error_message=error_message, status=TaskStatus.FAILED)
    
    def get_tasks_statistics(self, project_id: str = None) -> dict:
        """
        获取任务统计信息
        
        Args:
            project_id: 项目ID，如果为None则统计所有项目
            
        Returns:
            统计信息字典
        """
        query = self.db.query(self.model)
        if project_id:
            query = query.filter(self.model.project_id == project_id)
        
        total_tasks = query.count()
        pending_tasks = query.filter(self.model.status == TaskStatus.PENDING).count()
        running_tasks = query.filter(self.model.status == TaskStatus.RUNNING).count()
        completed_tasks = query.filter(self.model.status == TaskStatus.COMPLETED).count()
        failed_tasks = query.filter(self.model.status == TaskStatus.FAILED).count()
        
        return {
            "total": total_tasks,
            "pending": pending_tasks,
            "running": running_tasks,
            "completed": completed_tasks,
            "failed": failed_tasks,
            "success_rate": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        }
    
    def get_recent_tasks(self, limit: int = 10) -> List[Task]:
        """
        获取最近的任务
        
        Args:
            limit: 返回数量限制
            
        Returns:
            最近的任务列表
        """
        return self.db.query(self.model).order_by(
            desc(self.model.created_at)
        ).limit(limit).all()
    
    def get_tasks_by_date_range(self, start_date, end_date, project_id: str = None) -> List[Task]:
        """
        根据日期范围获取任务
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            project_id: 项目ID，如果为None则查询所有项目
            
        Returns:
            任务列表
        """
        query = self.db.query(self.model).filter(
            self.model.created_at >= start_date,
            self.model.created_at <= end_date
        )
        
        if project_id:
            query = query.filter(self.model.project_id == project_id)
        
        return query.order_by(desc(self.model.created_at)).all()
    
    def get_long_running_tasks(self, max_duration_hours: int = 2) -> List[Task]:
        """
        获取长时间运行的任务
        
        Args:
            max_duration_hours: 最大运行时间（小时）
            
        Returns:
            长时间运行的任务列表
        """
        from datetime import datetime, timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=max_duration_hours)
        
        return self.db.query(self.model).filter(
            self.model.status == TaskStatus.RUNNING,
            self.model.started_at <= cutoff_time
        ).all()
    
    def cleanup_old_tasks(self, days: int = 30) -> int:
        """
        清理旧任务，包括异常状态的任务
        
        Args:
            days: 保留天数
            
        Returns:
            删除的任务数量
        """
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        long_running_cutoff = datetime.utcnow() - timedelta(hours=24)
        
        total_deleted = 0
        
        try:
            # 1. 清理过期的已完成/失败任务
            completed_tasks = self.db.query(self.model).filter(
                self.model.created_at < cutoff_date,
                self.model.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED])
            ).delete(synchronize_session=False)
            
            total_deleted += completed_tasks
            logger.info(f"清理了 {completed_tasks} 个过期的已完成/失败任务")
            
            # 2. 修复长时间运行的异常任务
            long_running_tasks = self.db.query(self.model).filter(
                self.model.status == TaskStatus.RUNNING,
                self.model.created_at < long_running_cutoff
            ).all()
            
            fixed_count = 0
            for task in long_running_tasks:
                task.status = TaskStatus.FAILED
                task.error_message = "任务超时，已自动标记为失败"
                task.updated_at = datetime.utcnow()
                fixed_count += 1
                logger.info(f"修复长时间运行任务: {task.id}")
            
            if fixed_count > 0:
                self.db.commit()
                logger.info(f"修复了 {fixed_count} 个长时间运行的任务")
            
            # 3. 清理孤立的任务（没有对应项目的任务）
            from ..models.project import Project
            all_project_ids = {p.id for p in self.db.query(Project).all()}
            orphaned_tasks = self.db.query(self.model).filter(
                ~self.model.project_id.in_(all_project_ids)
            ).all()
            
            orphaned_count = 0
            for task in orphaned_tasks:
                self.db.delete(task)
                orphaned_count += 1
                logger.info(f"清理孤立任务: {task.id}")
            
            if orphaned_count > 0:
                self.db.commit()
                logger.info(f"清理了 {orphaned_count} 个孤立任务")
            
            return total_deleted + fixed_count + orphaned_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"清理任务失败: {e}")
            raise