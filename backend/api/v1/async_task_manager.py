"""
异步任务管理器
防止未捕获的异常导致后端重启
"""

import asyncio
import logging
from typing import Callable, Any, Dict, Optional
import traceback
from datetime import datetime

logger = logging.getLogger(__name__)

class AsyncTaskManager:
    """异步任务管理器"""
    
    def __init__(self):
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.task_results: Dict[str, Any] = {}
    
    async def create_safe_task(
        self, 
        task_id: str, 
        coro: Callable, 
        *args, 
        **kwargs
    ) -> asyncio.Task:
        """
        创建安全的异步任务，防止未捕获异常
        
        Args:
            task_id: 任务ID
            coro: 协程函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            异步任务对象
        """
        
        async def safe_wrapper():
            """安全包装器，捕获所有异常"""
            try:
                logger.info(f"开始执行任务: {task_id}")
                result = await coro(*args, **kwargs)
                self.task_results[task_id] = {
                    "status": "completed",
                    "result": result,
                    "completed_at": datetime.now().isoformat()
                }
                logger.info(f"任务完成: {task_id}")
                return result
                
            except Exception as e:
                error_info = {
                    "status": "failed",
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                    "failed_at": datetime.now().isoformat()
                }
                self.task_results[task_id] = error_info
                logger.error(f"任务失败: {task_id}, 错误: {e}")
                logger.error(f"错误详情: {traceback.format_exc()}")
                
                # 不重新抛出异常，防止影响主事件循环
                return error_info
        
        # 创建任务
        task = asyncio.create_task(safe_wrapper())
        self.running_tasks[task_id] = task
        
        # 添加完成回调
        task.add_done_callback(lambda t: self._cleanup_task(task_id))
        
        return task
    
    def _cleanup_task(self, task_id: str):
        """清理完成的任务"""
        if task_id in self.running_tasks:
            del self.running_tasks[task_id]
        logger.debug(f"任务已清理: {task_id}")
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            return {
                "status": "running",
                "task_id": task_id,
                "created_at": "unknown"  # 可以扩展记录创建时间
            }
        elif task_id in self.task_results:
            return self.task_results[task_id]
        else:
            return None
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            task.cancel()
            logger.info(f"任务已取消: {task_id}")
            return True
        return False
    
    def get_all_tasks(self) -> Dict[str, Any]:
        """获取所有任务状态"""
        all_tasks = {}
        
        # 运行中的任务
        for task_id, task in self.running_tasks.items():
            all_tasks[task_id] = {
                "status": "running",
                "task_id": task_id
            }
        
        # 已完成的任务
        for task_id, result in self.task_results.items():
            all_tasks[task_id] = result
        
        return all_tasks

# 全局任务管理器实例
task_manager = AsyncTaskManager()

# 装饰器函数
def safe_async_task(task_id: str):
    """
    装饰器：将函数包装为安全的异步任务
    
    Usage:
        @safe_async_task("my_task")
        async def my_function():
            # 函数实现
            pass
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            return await task_manager.create_safe_task(task_id, func, *args, **kwargs)
        return wrapper
    return decorator

# 使用示例
async def example_usage():
    """使用示例"""
    
    async def risky_task():
        """可能失败的任务"""
        await asyncio.sleep(1)
        # 模拟可能的异常
        if True:  # 可以改为False来测试正常情况
            raise ValueError("模拟错误")
        return "任务完成"
    
    # 创建安全任务
    task = await task_manager.create_safe_task("example_task", risky_task)
    
    # 等待任务完成
    result = await task
    print(f"任务结果: {result}")
    
    # 检查任务状态
    status = task_manager.get_task_status("example_task")
    print(f"任务状态: {status}")

if __name__ == "__main__":
    asyncio.run(example_usage())

