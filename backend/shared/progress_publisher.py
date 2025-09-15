"""
统一的进度发布服务
提供标准化的进度事件发布接口
"""

import json
import time
import logging
import asyncio
from typing import Dict, Any, Optional
import redis.asyncio as redis
from .progress_channels import project_progress_channel
from ..core.config import get_redis_url

logger = logging.getLogger(__name__)

class ProgressPublisher:
    """统一的进度发布器"""
    
    def __init__(self):
        self.redis_url = get_redis_url()
        self.redis_client: Optional[redis.Redis] = None
    
    async def _get_redis_client(self) -> redis.Redis:
        """获取Redis客户端"""
        if self.redis_client is None:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        return self.redis_client
    
    async def publish_project_progress(
        self, 
        project_id: str, 
        step: int, 
        total_steps: int, 
        percent: float, 
        message: str, 
        status: str = "running",
        task_id: Optional[str] = None
    ) -> bool:
        """
        发布项目进度事件
        
        Args:
            project_id: 项目ID
            step: 当前步骤
            total_steps: 总步骤数
            percent: 进度百分比 (0-100)
            message: 进度消息
            status: 状态 (running/succeeded/failed)
            task_id: 任务ID（可选）
            
        Returns:
            是否发布成功
        """
        try:
            channel = project_progress_channel(project_id)
            payload = {
                "type": "project_progress",
                "projectId": project_id,
                "step": step,
                "totalSteps": total_steps,
                "percent": percent,
                "message": message,
                "status": status,
                "ts": time.time()
            }
            
            if task_id:
                payload["taskId"] = task_id
            
            redis_client = await self._get_redis_client()
            await redis_client.publish(channel, json.dumps(payload, ensure_ascii=False))
            
            logger.info(f"进度事件已发布: {project_id} - {percent}% - {message}")
            return True
            
        except Exception as e:
            logger.error(f"发布进度事件失败: {e}")
            return False
    
    async def close(self):
        """关闭Redis连接"""
        if self.redis_client:
            await self.redis_client.close()

# 全局实例
progress_publisher = ProgressPublisher()

# 便捷函数
async def publish_project_progress(
    project_id: str, 
    step: int, 
    total_steps: int, 
    percent: float, 
    message: str, 
    status: str = "running",
    task_id: Optional[str] = None
) -> bool:
    """发布项目进度的便捷函数"""
    return await progress_publisher.publish_project_progress(
        project_id, step, total_steps, percent, message, status, task_id
    )
