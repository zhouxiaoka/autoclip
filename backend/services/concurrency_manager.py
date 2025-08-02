"""
并发控制管理器
处理任务并发和锁控制
"""

import logging
import threading
import time
from typing import Dict, Any, Optional, Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

from .exceptions import ConcurrentError, ErrorCode

logger = logging.getLogger(__name__)


@dataclass
class LockInfo:
    """锁信息"""
    resource_id: str
    task_id: str
    acquired_at: datetime
    timeout: timedelta
    is_released: bool = False


class ConcurrencyManager:
    """并发控制管理器"""
    
    def __init__(self):
        self._locks: Dict[str, LockInfo] = {}
        self._lock = threading.RLock()  # 用于保护内部状态
    
    def acquire_lock(self, resource_id: str, task_id: str, timeout_seconds: int = 30) -> bool:
        """
        获取锁
        
        Args:
            resource_id: 资源ID
            task_id: 任务ID
            timeout_seconds: 超时时间（秒）
            
        Returns:
            是否成功获取锁
        """
        with self._lock:
            # 检查资源是否已被锁定
            if resource_id in self._locks:
                existing_lock = self._locks[resource_id]
                
                # 检查锁是否已超时
                if datetime.now() - existing_lock.acquired_at > existing_lock.timeout:
                    logger.warning(f"锁已超时，强制释放: {resource_id}")
                    self._release_lock_internal(resource_id)
                else:
                    # 检查是否为同一任务
                    if existing_lock.task_id == task_id:
                        logger.debug(f"任务 {task_id} 已持有锁: {resource_id}")
                        return True
                    else:
                        logger.warning(f"资源 {resource_id} 已被任务 {existing_lock.task_id} 锁定")
                        return False
            
            # 创建新锁
            lock_info = LockInfo(
                resource_id=resource_id,
                task_id=task_id,
                acquired_at=datetime.now(),
                timeout=timedelta(seconds=timeout_seconds)
            )
            
            self._locks[resource_id] = lock_info
            logger.info(f"任务 {task_id} 成功获取锁: {resource_id}")
            return True
    
    def release_lock(self, resource_id: str, task_id: str) -> bool:
        """
        释放锁
        
        Args:
            resource_id: 资源ID
            task_id: 任务ID
            
        Returns:
            是否成功释放锁
        """
        with self._lock:
            if resource_id not in self._locks:
                logger.warning(f"尝试释放不存在的锁: {resource_id}")
                return False
            
            lock_info = self._locks[resource_id]
            if lock_info.task_id != task_id:
                logger.warning(f"任务 {task_id} 尝试释放不属于自己的锁: {resource_id}")
                return False
            
            return self._release_lock_internal(resource_id)
    
    def _release_lock_internal(self, resource_id: str) -> bool:
        """内部释放锁方法"""
        if resource_id in self._locks:
            lock_info = self._locks[resource_id]
            lock_info.is_released = True
            del self._locks[resource_id]
            logger.info(f"锁已释放: {resource_id}")
            return True
        return False
    
    def is_locked(self, resource_id: str) -> bool:
        """检查资源是否被锁定"""
        with self._lock:
            if resource_id not in self._locks:
                return False
            
            lock_info = self._locks[resource_id]
            # 检查是否超时
            if datetime.now() - lock_info.acquired_at > lock_info.timeout:
                self._release_lock_internal(resource_id)
                return False
            
            return True
    
    def get_lock_info(self, resource_id: str) -> Optional[Dict[str, Any]]:
        """获取锁信息"""
        with self._lock:
            if resource_id not in self._locks:
                return None
            
            lock_info = self._locks[resource_id]
            return {
                "resource_id": lock_info.resource_id,
                "task_id": lock_info.task_id,
                "acquired_at": lock_info.acquired_at.isoformat(),
                "timeout": lock_info.timeout.total_seconds(),
                "is_released": lock_info.is_released
            }
    
    def cleanup_expired_locks(self):
        """清理过期的锁"""
        with self._lock:
            current_time = datetime.now()
            expired_resources = []
            
            for resource_id, lock_info in self._locks.items():
                if current_time - lock_info.acquired_at > lock_info.timeout:
                    expired_resources.append(resource_id)
            
            for resource_id in expired_resources:
                self._release_lock_internal(resource_id)
                logger.info(f"清理过期锁: {resource_id}")
    
    def get_all_locks(self) -> Dict[str, Dict[str, Any]]:
        """获取所有锁信息"""
        with self._lock:
            return {
                resource_id: self.get_lock_info(resource_id)
                for resource_id in self._locks.keys()
            }
    
    @contextmanager
    def lock_context(self, resource_id: str, task_id: str, timeout_seconds: int = 30):
        """
        锁上下文管理器
        
        Usage:
            with concurrency_manager.lock_context("project_123", "task_456"):
                # 执行需要锁保护的操作
                pass
        """
        try:
            if not self.acquire_lock(resource_id, task_id, timeout_seconds):
                raise ConcurrentError(
                    f"无法获取锁: {resource_id}",
                    resource=resource_id,
                    details={"task_id": task_id, "timeout": timeout_seconds}
                )
            yield
        finally:
            self.release_lock(resource_id, task_id)


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, concurrency_manager: ConcurrencyManager):
        self.concurrency_manager = concurrency_manager
        self._running_tasks: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
    
    def can_start_task(self, project_id: str, task_id: str) -> bool:
        """检查是否可以启动任务"""
        resource_id = f"project_{project_id}"
        
        # 检查项目是否已被锁定
        if self.concurrency_manager.is_locked(resource_id):
            return False
        
        # 检查任务是否已在运行
        with self._lock:
            if task_id in self._running_tasks:
                return False
        
        return True
    
    def start_task(self, project_id: str, task_id: str, task_info: Dict[str, Any]) -> bool:
        """启动任务"""
        resource_id = f"project_{project_id}"
        
        if not self.can_start_task(project_id, task_id):
            return False
        
        # 获取锁
        if not self.concurrency_manager.acquire_lock(resource_id, task_id):
            return False
        
        # 记录运行中的任务
        with self._lock:
            self._running_tasks[task_id] = {
                "project_id": project_id,
                "task_id": task_id,
                "started_at": datetime.now(),
                "task_info": task_info
            }
        
        logger.info(f"任务已启动: {task_id} (项目: {project_id})")
        return True
    
    def finish_task(self, project_id: str, task_id: str):
        """完成任务"""
        resource_id = f"project_{project_id}"
        
        # 释放锁
        self.concurrency_manager.release_lock(resource_id, task_id)
        
        # 移除运行中的任务记录
        with self._lock:
            if task_id in self._running_tasks:
                del self._running_tasks[task_id]
        
        logger.info(f"任务已完成: {task_id} (项目: {project_id})")
    
    def get_running_tasks(self) -> Dict[str, Dict[str, Any]]:
        """获取运行中的任务"""
        with self._lock:
            return self._running_tasks.copy()
    
    def is_task_running(self, task_id: str) -> bool:
        """检查任务是否在运行"""
        with self._lock:
            return task_id in self._running_tasks


# 全局并发管理器实例
concurrency_manager = ConcurrencyManager()
task_scheduler = TaskScheduler(concurrency_manager)


def with_concurrency_control(resource_id_func: Callable = None):
    """
    并发控制装饰器
    
    Args:
        resource_id_func: 生成资源ID的函数，默认为使用project_id
        
    Usage:
        @with_concurrency_control()
        def process_project(project_id: str, task_id: str, ...):
            # 函数体
            pass
        
        @with_concurrency_control(lambda ctx: f"custom_{ctx.project_id}")
        def custom_process(ctx: ProcessingContext):
            # 函数体
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 尝试从参数中提取project_id和task_id
            project_id = None
            task_id = None
            context = None
            
            # 检查是否有ProcessingContext参数
            for arg in args:
                if hasattr(arg, 'project_id') and hasattr(arg, 'task_id'):
                    context = arg
                    project_id = context.project_id
                    task_id = context.task_id
                    break
            
            # 如果没有找到context，尝试从kwargs中获取
            if not project_id:
                project_id = kwargs.get('project_id')
                task_id = kwargs.get('task_id')
            
            # 如果还是没有找到，尝试从函数签名中获取第一个参数作为project_id
            if not project_id and len(args) > 0:
                project_id = str(args[0])
                # 生成一个临时的task_id
                task_id = f"temp_task_{project_id}"
            
            if not project_id:
                raise ValueError("无法确定project_id和task_id")
            
            # 生成资源ID
            if resource_id_func:
                resource_id = resource_id_func(context or project_id)
            else:
                resource_id = f"project_{project_id}"
            
            # 检查是否可以启动任务
            if not task_scheduler.can_start_task(project_id, task_id):
                raise ConcurrentError(
                    f"项目 {project_id} 正在被其他任务处理",
                    resource=resource_id,
                    details={"project_id": project_id, "task_id": task_id}
                )
            
            # 启动任务
            if not task_scheduler.start_task(project_id, task_id, {"function": func.__name__}):
                raise ConcurrentError(
                    f"无法启动任务: {task_id}",
                    resource=resource_id,
                    details={"project_id": project_id, "task_id": task_id}
                )
            
            try:
                # 执行函数
                result = func(*args, **kwargs)
                return result
            finally:
                # 完成任务
                task_scheduler.finish_task(project_id, task_id)
        
        return wrapper
    return decorator 