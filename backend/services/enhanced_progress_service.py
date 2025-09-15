"""
增强进度服务
整合现有进度系统，提供更好的错误处理和状态管理
"""

import time
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import redis
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..models.project import Project, ProjectStatus
from ..models.task import Task, TaskStatus
from ..utils.error_handler import AutoClipsException, ErrorCategory

logger = logging.getLogger(__name__)


class ProgressStage(Enum):
    """进度阶段枚举"""
    INGEST = "INGEST"          # 下载/就绪
    SUBTITLE = "SUBTITLE"      # 字幕/对齐
    ANALYZE = "ANALYZE"        # 语义分析/大纲
    HIGHLIGHT = "HIGHLIGHT"    # 片段定位/打分
    EXPORT = "EXPORT"          # 导出/封装
    DONE = "DONE"              # 校验/归档
    ERROR = "ERROR"            # 错误状态


class ProgressStatus(Enum):
    """进度状态枚举"""
    PENDING = "PENDING"        # 等待中
    RUNNING = "RUNNING"        # 运行中
    COMPLETED = "COMPLETED"    # 已完成
    FAILED = "FAILED"          # 失败
    CANCELLED = "CANCELLED"    # 已取消


@dataclass
class ProgressInfo:
    """进度信息数据结构"""
    project_id: str
    task_id: Optional[str] = None
    stage: ProgressStage = ProgressStage.INGEST
    status: ProgressStatus = ProgressStatus.PENDING
    progress: int = 0  # 0-100
    message: str = ""
    error_message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    estimated_remaining: Optional[int] = None  # 预估剩余时间(秒)
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        data = asdict(self)
        # 转换枚举为字符串
        data['stage'] = self.stage.value
        data['status'] = self.status.value
        # 转换时间戳
        if self.start_time:
            data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProgressInfo':
        """从字典创建实例"""
        # 转换字符串为枚举
        if 'stage' in data and isinstance(data['stage'], str):
            data['stage'] = ProgressStage(data['stage'])
        if 'status' in data and isinstance(data['status'], str):
            data['status'] = ProgressStatus(data['status'])
        # 转换时间戳
        if 'start_time' in data and isinstance(data['start_time'], str):
            data['start_time'] = datetime.fromisoformat(data['start_time'])
        if 'end_time' in data and isinstance(data['end_time'], str):
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        return cls(**data)


class EnhancedProgressService:
    """增强进度服务"""
    
    # 阶段权重定义
    STAGE_WEIGHTS = {
        ProgressStage.INGEST: 10,
        ProgressStage.SUBTITLE: 15,
        ProgressStage.ANALYZE: 20,
        ProgressStage.HIGHLIGHT: 25,
        ProgressStage.EXPORT: 20,
        ProgressStage.DONE: 10,
    }
    
    # 阶段顺序
    STAGE_ORDER = [
        ProgressStage.INGEST,
        ProgressStage.SUBTITLE,
        ProgressStage.ANALYZE,
        ProgressStage.HIGHLIGHT,
        ProgressStage.EXPORT,
        ProgressStage.DONE,
    ]
    
    def __init__(self):
        self.redis_client = None
        self._init_redis()
        self.progress_cache: Dict[str, ProgressInfo] = {}
        self.progress_callbacks: List[Callable[[ProgressInfo], None]] = []
    
    def _init_redis(self):
        """初始化Redis连接"""
        try:
            self.redis_client = redis.Redis.from_url(
                "redis://127.0.0.1:6379/0", 
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # 测试连接
            self.redis_client.ping()
            logger.info("Redis连接成功")
        except Exception as e:
            logger.warning(f"Redis连接失败，将使用内存缓存: {e}")
            self.redis_client = None
    
    def _get_redis_key(self, project_id: str) -> str:
        """获取Redis键名"""
        return f"progress:{project_id}"
    
    def _calculate_progress(self, stage: ProgressStage, sub_progress: float = 0.0) -> int:
        """计算总进度百分比"""
        # 累加之前阶段的权重
        total_weight = 0
        current_stage_weight = 0
        
        for s in self.STAGE_ORDER:
            if s == stage:
                current_stage_weight = self.STAGE_WEIGHTS.get(s, 0)
                break
            total_weight += self.STAGE_WEIGHTS.get(s, 0)
        
        # 计算当前阶段的进度
        if stage == ProgressStage.DONE:
            return 100
        elif stage == ProgressStage.ERROR:
            return total_weight  # 错误时保持当前进度
        
        # 添加当前阶段的子进度
        current_progress = int(current_stage_weight * sub_progress / 100.0)
        total_progress = total_weight + current_progress
        
        return min(99, total_progress)
    
    def _estimate_remaining_time(self, progress_info: ProgressInfo) -> Optional[int]:
        """预估剩余时间"""
        if not progress_info.start_time or progress_info.progress <= 0:
            return None
        
        elapsed = (datetime.utcnow() - progress_info.start_time).total_seconds()
        if elapsed <= 0:
            return None
        
        # 基于当前进度预估总时间
        estimated_total = elapsed * 100 / progress_info.progress
        remaining = estimated_total - elapsed
        
        return max(0, int(remaining))
    
    def start_progress(self, project_id: str, task_id: Optional[str] = None, 
                      initial_message: str = "开始处理") -> ProgressInfo:
        """开始进度跟踪"""
        try:
            progress_info = ProgressInfo(
                project_id=project_id,
                task_id=task_id,
                stage=ProgressStage.INGEST,
                status=ProgressStatus.RUNNING,
                progress=0,
                message=initial_message,
                start_time=datetime.utcnow()
            )
            
            # 保存到缓存
            self.progress_cache[project_id] = progress_info
            
            # 保存到Redis
            if self.redis_client:
                try:
                    self.redis_client.setex(
                        self._get_redis_key(project_id),
                        3600,  # 1小时过期
                        json.dumps(progress_info.to_dict())
                    )
                except Exception as e:
                    logger.warning(f"保存进度到Redis失败: {e}")
            
            # 更新数据库
            self._update_database_progress(progress_info)
            
            # 触发回调
            self._trigger_callbacks(progress_info)
            
            logger.info(f"开始跟踪项目 {project_id} 的进度")
            return progress_info
            
        except Exception as e:
            logger.error(f"开始进度跟踪失败: {e}")
            raise AutoClipsException(
                message="开始进度跟踪失败",
                category=ErrorCategory.SYSTEM,
                original_exception=e
            )
    
    def update_progress(self, project_id: str, stage: ProgressStage, 
                       message: str = "", sub_progress: float = 0.0,
                       metadata: Optional[Dict[str, Any]] = None) -> ProgressInfo:
        """更新进度"""
        try:
            # 获取当前进度信息
            progress_info = self.get_progress(project_id)
            if not progress_info:
                logger.warning(f"项目 {project_id} 的进度信息不存在，创建新的")
                progress_info = self.start_progress(project_id, message=message)
            
            # 更新进度信息
            progress_info.stage = stage
            progress_info.message = message
            progress_info.progress = self._calculate_progress(stage, sub_progress)
            progress_info.estimated_remaining = self._estimate_remaining_time(progress_info)
            
            if metadata:
                if progress_info.metadata:
                    progress_info.metadata.update(metadata)
                else:
                    progress_info.metadata = metadata
            
            # 保存到缓存
            self.progress_cache[project_id] = progress_info
            
            # 保存到Redis
            if self.redis_client:
                try:
                    self.redis_client.setex(
                        self._get_redis_key(project_id),
                        3600,
                        json.dumps(progress_info.to_dict())
                    )
                except Exception as e:
                    logger.warning(f"更新Redis进度失败: {e}")
            
            # 更新数据库
            self._update_database_progress(progress_info)
            
            # 触发回调
            self._trigger_callbacks(progress_info)
            
            logger.info(f"项目 {project_id} 进度更新: {progress_info.progress}% - {stage.value}")
            return progress_info
            
        except Exception as e:
            logger.error(f"更新进度失败: {e}")
            raise AutoClipsException(
                message="更新进度失败",
                category=ErrorCategory.SYSTEM,
                original_exception=e
            )
    
    def complete_progress(self, project_id: str, message: str = "处理完成") -> ProgressInfo:
        """完成进度"""
        try:
            progress_info = self.get_progress(project_id)
            if not progress_info:
                logger.warning(f"项目 {project_id} 的进度信息不存在")
                return None
            
            # 更新为完成状态
            progress_info.stage = ProgressStage.DONE
            progress_info.status = ProgressStatus.COMPLETED
            progress_info.progress = 100
            progress_info.message = message
            progress_info.end_time = datetime.utcnow()
            progress_info.estimated_remaining = 0
            
            # 保存到缓存
            self.progress_cache[project_id] = progress_info
            
            # 保存到Redis
            if self.redis_client:
                try:
                    self.redis_client.setex(
                        self._get_redis_key(project_id),
                        3600,
                        json.dumps(progress_info.to_dict())
                    )
                except Exception as e:
                    logger.warning(f"保存完成状态到Redis失败: {e}")
            
            # 更新数据库
            self._update_database_progress(progress_info)
            
            # 触发回调
            self._trigger_callbacks(progress_info)
            
            logger.info(f"项目 {project_id} 处理完成")
            return progress_info
            
        except Exception as e:
            logger.error(f"完成进度失败: {e}")
            raise AutoClipsException(
                message="完成进度失败",
                category=ErrorCategory.SYSTEM,
                original_exception=e
            )
    
    def fail_progress(self, project_id: str, error_message: str) -> ProgressInfo:
        """标记进度为失败"""
        try:
            progress_info = self.get_progress(project_id)
            if not progress_info:
                logger.warning(f"项目 {project_id} 的进度信息不存在")
                return None
            
            # 更新为失败状态
            progress_info.stage = ProgressStage.ERROR
            progress_info.status = ProgressStatus.FAILED
            progress_info.error_message = error_message
            progress_info.end_time = datetime.utcnow()
            progress_info.estimated_remaining = 0
            
            # 保存到缓存
            self.progress_cache[project_id] = progress_info
            
            # 保存到Redis
            if self.redis_client:
                try:
                    self.redis_client.setex(
                        self._get_redis_key(project_id),
                        3600,
                        json.dumps(progress_info.to_dict())
                    )
                except Exception as e:
                    logger.warning(f"保存失败状态到Redis失败: {e}")
            
            # 更新数据库
            self._update_database_progress(progress_info)
            
            # 触发回调
            self._trigger_callbacks(progress_info)
            
            logger.error(f"项目 {project_id} 处理失败: {error_message}")
            return progress_info
            
        except Exception as e:
            logger.error(f"标记进度失败失败: {e}")
            raise AutoClipsException(
                message="标记进度失败失败",
                category=ErrorCategory.SYSTEM,
                original_exception=e
            )
    
    def get_progress(self, project_id: str) -> Optional[ProgressInfo]:
        """获取进度信息"""
        try:
            # 先从缓存获取
            if project_id in self.progress_cache:
                return self.progress_cache[project_id]
            
            # 从Redis获取
            if self.redis_client:
                try:
                    redis_data = self.redis_client.get(self._get_redis_key(project_id))
                    if redis_data:
                        data = json.loads(redis_data)
                        progress_info = ProgressInfo.from_dict(data)
                        self.progress_cache[project_id] = progress_info
                        return progress_info
                except Exception as e:
                    logger.warning(f"从Redis获取进度失败: {e}")
            
            # 从数据库获取
            db = SessionLocal()
            try:
                project = db.query(Project).filter(Project.id == project_id).first()
                if project:
                    # 根据项目状态创建进度信息
                    stage = self._map_project_status_to_stage(project.status)
                    status = self._map_project_status_to_progress_status(project.status)
                    
                    progress_info = ProgressInfo(
                        project_id=project_id,
                        stage=stage,
                        status=status,
                        progress=self._calculate_progress(stage),
                        message=f"项目状态: {project.status}",
                        start_time=project.created_at,
                        end_time=project.updated_at if status == ProgressStatus.COMPLETED else None
                    )
                    
                    self.progress_cache[project_id] = progress_info
                    return progress_info
            finally:
                db.close()
            
            return None
            
        except Exception as e:
            logger.error(f"获取进度信息失败: {e}")
            return None
    
    def _map_project_status_to_stage(self, project_status: str) -> ProgressStage:
        """将项目状态映射到进度阶段"""
        status_mapping = {
            ProjectStatus.PENDING: ProgressStage.INGEST,
            ProjectStatus.PROCESSING: ProgressStage.ANALYZE,
            ProjectStatus.COMPLETED: ProgressStage.DONE,
            ProjectStatus.FAILED: ProgressStage.ERROR,
        }
        return status_mapping.get(project_status, ProgressStage.INGEST)
    
    def _map_project_status_to_progress_status(self, project_status: str) -> ProgressStatus:
        """将项目状态映射到进度状态"""
        status_mapping = {
            ProjectStatus.PENDING: ProgressStatus.PENDING,
            ProjectStatus.PROCESSING: ProgressStatus.RUNNING,
            ProjectStatus.COMPLETED: ProgressStatus.COMPLETED,
            ProjectStatus.FAILED: ProgressStatus.FAILED,
        }
        return status_mapping.get(project_status, ProgressStatus.PENDING)
    
    def _update_database_progress(self, progress_info: ProgressInfo):
        """更新数据库中的进度信息"""
        try:
            db = SessionLocal()
            try:
                # 更新项目状态
                project = db.query(Project).filter(Project.id == progress_info.project_id).first()
                if project:
                    if progress_info.status == ProgressStatus.COMPLETED:
                        project.status = ProjectStatus.COMPLETED
                    elif progress_info.status == ProgressStatus.FAILED:
                        project.status = ProjectStatus.FAILED
                    elif progress_info.status == ProgressStatus.RUNNING:
                        project.status = ProjectStatus.PROCESSING
                    
                    project.updated_at = datetime.utcnow()
                    db.commit()
                
                # 更新任务状态
                if progress_info.task_id:
                    task = db.query(Task).filter(Task.id == progress_info.task_id).first()
                    if task:
                        task.progress = progress_info.progress
                        task.current_step = progress_info.stage.value
                        task.updated_at = datetime.utcnow()
                        
                        if progress_info.status == ProgressStatus.COMPLETED:
                            task.status = TaskStatus.COMPLETED
                        elif progress_info.status == ProgressStatus.FAILED:
                            task.status = TaskStatus.FAILED
                            task.error_message = progress_info.error_message
                        
                        db.commit()
                        
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"更新数据库进度失败: {e}")
    
    def add_progress_callback(self, callback: Callable[[ProgressInfo], None]):
        """添加进度回调函数"""
        self.progress_callbacks.append(callback)
    
    def remove_progress_callback(self, callback: Callable[[ProgressInfo], None]):
        """移除进度回调函数"""
        if callback in self.progress_callbacks:
            self.progress_callbacks.remove(callback)
    
    def _trigger_callbacks(self, progress_info: ProgressInfo):
        """触发进度回调"""
        for callback in self.progress_callbacks:
            try:
                callback(progress_info)
            except Exception as e:
                logger.error(f"进度回调执行失败: {e}")
    
    def cleanup_old_progress(self, max_age_hours: int = 24):
        """清理旧的进度信息"""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            cleaned_count = 0
            
            # 清理缓存
            for project_id, progress_info in list(self.progress_cache.items()):
                if progress_info.end_time and progress_info.end_time < cutoff_time:
                    del self.progress_cache[project_id]
                    cleaned_count += 1
            
            # 清理Redis
            if self.redis_client:
                try:
                    # 获取所有进度键
                    keys = self.redis_client.keys("progress:*")
                    for key in keys:
                        try:
                            data = self.redis_client.get(key)
                            if data:
                                progress_data = json.loads(data)
                                if 'end_time' in progress_data:
                                    end_time = datetime.fromisoformat(progress_data['end_time'])
                                    if end_time < cutoff_time:
                                        self.redis_client.delete(key)
                                        cleaned_count += 1
                        except Exception as e:
                            logger.warning(f"清理Redis键 {key} 失败: {e}")
                except Exception as e:
                    logger.warning(f"清理Redis进度失败: {e}")
            
            logger.info(f"清理了 {cleaned_count} 个旧进度记录")
            
        except Exception as e:
            logger.error(f"清理旧进度失败: {e}")
    
    def get_all_active_progress(self) -> List[ProgressInfo]:
        """获取所有活跃的进度信息"""
        try:
            active_progress = []
            
            # 从缓存获取
            for progress_info in self.progress_cache.values():
                if progress_info.status in [ProgressStatus.PENDING, ProgressStatus.RUNNING]:
                    active_progress.append(progress_info)
            
            # 从Redis获取
            if self.redis_client:
                try:
                    keys = self.redis_client.keys("progress:*")
                    for key in keys:
                        try:
                            data = self.redis_client.get(key)
                            if data:
                                progress_data = json.loads(data)
                                progress_info = ProgressInfo.from_dict(progress_data)
                                if progress_info.status in [ProgressStatus.PENDING, ProgressStatus.RUNNING]:
                                    # 避免重复
                                    if not any(p.project_id == progress_info.project_id for p in active_progress):
                                        active_progress.append(progress_info)
                        except Exception as e:
                            logger.warning(f"解析Redis进度数据失败: {e}")
                except Exception as e:
                    logger.warning(f"获取Redis进度失败: {e}")
            
            return active_progress
            
        except Exception as e:
            logger.error(f"获取活跃进度失败: {e}")
            return []


# 全局进度服务实例
progress_service = EnhancedProgressService()


# 便捷函数
def start_progress(project_id: str, task_id: Optional[str] = None, 
                  initial_message: str = "开始处理") -> ProgressInfo:
    """开始进度跟踪"""
    return progress_service.start_progress(project_id, task_id, initial_message)


def update_progress(project_id: str, stage: ProgressStage, 
                   message: str = "", sub_progress: float = 0.0,
                   metadata: Optional[Dict[str, Any]] = None) -> ProgressInfo:
    """更新进度"""
    return progress_service.update_progress(project_id, stage, message, sub_progress, metadata)


def complete_progress(project_id: str, message: str = "处理完成") -> ProgressInfo:
    """完成进度"""
    return progress_service.complete_progress(project_id, message)


def fail_progress(project_id: str, error_message: str) -> ProgressInfo:
    """标记进度为失败"""
    return progress_service.fail_progress(project_id, error_message)


def get_progress(project_id: str) -> Optional[ProgressInfo]:
    """获取进度信息"""
    return progress_service.get_progress(project_id)
