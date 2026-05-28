"""
并发控制管理器
管理系统的并发任务和资源使用
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading
from collections import defaultdict

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    name: str
    priority: TaskPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    resource_usage: Dict[str, Any] = field(default_factory=dict)


class ResourceLimiter:
    """资源限制器"""
    
    def __init__(self, max_concurrent: int, resource_name: str):
        self.max_concurrent = max_concurrent
        self.resource_name = resource_name
        self.current_usage = 0
        self.waiting_queue = asyncio.Queue()
        self.lock = asyncio.Lock()
    
    async def acquire(self, task_id: str) -> bool:
        """获取资源"""
        
        async with self.lock:
            if self.current_usage < self.max_concurrent:
                self.current_usage += 1
                logger.debug(f"任务 {task_id} 获取 {self.resource_name} 资源，当前使用: {self.current_usage}/{self.max_concurrent}")
                return True
            else:
                logger.debug(f"任务 {task_id} 等待 {self.resource_name} 资源")
                await self.waiting_queue.put(task_id)
                return False
    
    async def release(self, task_id: str):
        """释放资源"""
        
        async with self.lock:
            if self.current_usage > 0:
                self.current_usage -= 1
                logger.debug(f"任务 {task_id} 释放 {self.resource_name} 资源，当前使用: {self.current_usage}/{self.max_concurrent}")
                
                # 如果有等待的任务，通知下一个
                if not self.waiting_queue.empty():
                    next_task_id = await self.waiting_queue.get()
                    logger.debug(f"通知等待任务 {next_task_id} 可以获取 {self.resource_name} 资源")
    
    def get_status(self) -> Dict[str, Any]:
        """获取资源状态"""
        
        return {
            "resource_name": self.resource_name,
            "max_concurrent": self.max_concurrent,
            "current_usage": self.current_usage,
            "waiting_count": self.waiting_queue.qsize(),
            "utilization": self.current_usage / self.max_concurrent * 100
        }


class ConcurrencyManager:
    """并发管理器"""
    
    def __init__(self):
        self.resource_limiters: Dict[str, ResourceLimiter] = {}
        self.active_tasks: Dict[str, TaskInfo] = {}
        self.task_history: List[TaskInfo] = []
        self.task_counter = 0
        self.lock = asyncio.Lock()
        
        # 默认资源限制
        self._setup_default_limits()
    
    def _setup_default_limits(self):
        """设置默认资源限制"""
        
        # 文件上传限制
        self.add_resource_limiter("file_upload", 3)
        
        # 视频处理限制
        self.add_resource_limiter("video_processing", 2)
        
        # AI处理限制
        self.add_resource_limiter("ai_processing", 4)
        
        # 数据库操作限制
        self.add_resource_limiter("database", 10)
        
        # 网络请求限制
        self.add_resource_limiter("network", 5)
    
    def add_resource_limiter(self, resource_name: str, max_concurrent: int):
        """添加资源限制器"""
        
        self.resource_limiters[resource_name] = ResourceLimiter(max_concurrent, resource_name)
        logger.info(f"添加资源限制器: {resource_name}, 最大并发: {max_concurrent}")
    
    def _generate_task_id(self) -> str:
        """生成任务ID"""
        
        self.task_counter += 1
        return f"task_{self.task_counter}_{int(time.time())}"
    
    async def submit_task(
        self,
        name: str,
        coro: Callable,
        priority: TaskPriority = TaskPriority.NORMAL,
        required_resources: List[str] = None,
        *args,
        **kwargs
    ) -> str:
        """提交任务"""
        
        task_id = self._generate_task_id()
        
        # 创建任务信息
        task_info = TaskInfo(
            task_id=task_id,
            name=name,
            priority=priority,
            created_at=datetime.now()
        )
        
        async with self.lock:
            self.active_tasks[task_id] = task_info
        
        # 创建并启动任务
        asyncio.create_task(self._execute_task(task_id, coro, required_resources or [], *args, **kwargs))
        
        logger.info(f"提交任务: {task_id}, 名称: {name}, 优先级: {priority.value}")
        
        return task_id
    
    async def _execute_task(
        self,
        task_id: str,
        coro: Callable,
        required_resources: List[str],
        *args,
        **kwargs
    ):
        """执行任务"""
        
        task_info = self.active_tasks.get(task_id)
        if not task_info:
            return
        
        # 获取所需资源
        acquired_resources = []
        try:
            # 按优先级获取资源
            for resource_name in required_resources:
                if resource_name in self.resource_limiters:
                    limiter = self.resource_limiters[resource_name]
                    acquired = await limiter.acquire(task_id)
                    if acquired:
                        acquired_resources.append(resource_name)
                    else:
                        # 如果无法获取资源，等待
                        await self._wait_for_resource(task_id, resource_name)
                        acquired_resources.append(resource_name)
            
            # 更新任务状态
            task_info.status = TaskStatus.RUNNING
            task_info.started_at = datetime.now()
            
            # 执行任务
            if asyncio.iscoroutinefunction(coro):
                result = await coro(*args, **kwargs)
            else:
                result = coro(*args, **kwargs)
            
            # 任务完成
            task_info.status = TaskStatus.COMPLETED
            task_info.completed_at = datetime.now()
            task_info.result = result
            
            logger.info(f"任务完成: {task_id}, 耗时: {(task_info.completed_at - task_info.started_at).total_seconds():.2f}秒")
            
        except Exception as e:
            # 任务失败
            task_info.status = TaskStatus.FAILED
            task_info.completed_at = datetime.now()
            task_info.error = str(e)
            
            logger.error(f"任务失败: {task_id}, 错误: {e}")
        
        finally:
            # 释放资源
            for resource_name in acquired_resources:
                if resource_name in self.resource_limiters:
                    await self.resource_limiters[resource_name].release(task_id)
            
            # 移动到历史记录
            async with self.lock:
                if task_id in self.active_tasks:
                    self.task_history.append(self.active_tasks[task_id])
                    del self.active_tasks[task_id]
    
    async def _wait_for_resource(self, task_id: str, resource_name: str):
        """等待资源可用"""
        
        if resource_name not in self.resource_limiters:
            return
        
        limiter = self.resource_limiters[resource_name]
        
        # 等待资源可用
        while True:
            async with limiter.lock:
                if limiter.current_usage < limiter.max_concurrent:
                    limiter.current_usage += 1
                    break
            
            # 等待一段时间后重试
            await asyncio.sleep(0.1)
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        
        async with self.lock:
            task_info = self.active_tasks.get(task_id)
            if not task_info:
                return False
            
            task_info.status = TaskStatus.CANCELLED
            task_info.completed_at = datetime.now()
            
            # 移动到历史记录
            self.task_history.append(task_info)
            del self.active_tasks[task_id]
        
        logger.info(f"取消任务: {task_id}")
        return True
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        
        # 检查活跃任务
        task_info = self.active_tasks.get(task_id)
        if task_info:
            return self._task_info_to_dict(task_info)
        
        # 检查历史任务
        for task_info in self.task_history:
            if task_info.task_id == task_id:
                return self._task_info_to_dict(task_info)
        
        return None
    
    def _task_info_to_dict(self, task_info: TaskInfo) -> Dict[str, Any]:
        """将任务信息转换为字典"""
        
        result = {
            "task_id": task_info.task_id,
            "name": task_info.name,
            "priority": task_info.priority.value,
            "status": task_info.status.value,
            "created_at": task_info.created_at.isoformat(),
            "resource_usage": task_info.resource_usage
        }
        
        if task_info.started_at:
            result["started_at"] = task_info.started_at.isoformat()
        
        if task_info.completed_at:
            result["completed_at"] = task_info.completed_at.isoformat()
            
            # 计算执行时间
            if task_info.started_at:
                execution_time = (task_info.completed_at - task_info.started_at).total_seconds()
                result["execution_time"] = execution_time
        
        if task_info.error:
            result["error"] = task_info.error
        
        if task_info.result is not None:
            result["result"] = task_info.result
        
        return result
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """获取活跃任务列表"""
        
        return [self._task_info_to_dict(task_info) for task_info in self.active_tasks.values()]
    
    def get_task_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取任务历史"""
        
        recent_tasks = self.task_history[-limit:] if self.task_history else []
        return [self._task_info_to_dict(task_info) for task_info in recent_tasks]
    
    def get_resource_status(self) -> Dict[str, Any]:
        """获取资源状态"""
        
        status = {}
        for resource_name, limiter in self.resource_limiters.items():
            status[resource_name] = limiter.get_status()
        
        return status
    
    def get_system_load(self) -> Dict[str, Any]:
        """获取系统负载"""
        
        active_count = len(self.active_tasks)
        total_waiting = sum(limiter.waiting_queue.qsize() for limiter in self.resource_limiters.values())
        
        # 计算资源利用率
        resource_utilization = {}
        for resource_name, limiter in self.resource_limiters.items():
            resource_utilization[resource_name] = limiter.get_status()["utilization"]
        
        return {
            "active_tasks": active_count,
            "total_waiting": total_waiting,
            "resource_utilization": resource_utilization,
            "timestamp": datetime.now().isoformat()
        }
    
    def cleanup_old_history(self, max_age_hours: int = 24):
        """清理旧的历史记录"""
        
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        # 过滤历史记录
        self.task_history = [
            task_info for task_info in self.task_history
            if task_info.created_at >= cutoff_time
        ]
        
        logger.info(f"清理任务历史记录，保留最近 {max_age_hours} 小时的数据")


# 全局并发管理器实例
concurrency_manager = ConcurrencyManager()


# 并发控制装饰器
def limit_concurrency(resource_name: str, priority: TaskPriority = TaskPriority.NORMAL):
    """并发控制装饰器"""
    
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            task_id = await concurrency_manager.submit_task(
                name=func.__name__,
                coro=func,
                priority=priority,
                required_resources=[resource_name],
                *args,
                **kwargs
            )
            
            # 等待任务完成
            while True:
                status = concurrency_manager.get_task_status(task_id)
                if status and status["status"] in ["completed", "failed", "cancelled"]:
                    if status["status"] == "failed" and "error" in status:
                        raise Exception(status["error"])
                    return status.get("result")
                
                await asyncio.sleep(0.1)
        
        def sync_wrapper(*args, **kwargs):
            # 对于同步函数，创建异步包装器
            async def async_func():
                return func(*args, **kwargs)
            
            return asyncio.run(async_wrapper())
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
