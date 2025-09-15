"""
进度事件服务
基于Redis PubSub实现任务进度同步
"""

import json
import time
import logging
import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
import redis.asyncio as redis
from ..core.config import get_redis_url
from ..shared.progress_channels import project_progress_channel

logger = logging.getLogger(__name__)

@dataclass
class ProgressEvent:
    """进度事件数据结构"""
    task_id: str
    progress: int  # 0-100
    step: int
    total: int
    phase: str  # transcribe|analyze|clip|encode|upload
    message: str
    status: str  # PENDING|PROGRESS|DONE|FAIL
    seq: int  # 递增序列号
    ts: float  # 单调递增时间戳
    meta: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProgressEvent':
        """从字典创建实例"""
        return cls(**data)

class ProgressEventService:
    """进度事件服务"""
    
    def __init__(self):
        self.redis_url = get_redis_url()
        self.redis_client: Optional[redis.Redis] = None
        self.sequence_counters: Dict[str, int] = {}  # 每个task_id的序列号计数器
        self.throttle_cache: Dict[str, Dict[str, Any]] = {}  # 节流缓存
        self.throttle_interval = 0.2  # 200ms节流间隔
        
    async def _get_redis_client(self) -> redis.Redis:
        """获取Redis客户端"""
        if self.redis_client is None:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
        return self.redis_client
    
    def _get_next_seq(self, task_id: str) -> int:
        """获取下一个序列号"""
        if task_id not in self.sequence_counters:
            self.sequence_counters[task_id] = 0
        self.sequence_counters[task_id] += 1
        return self.sequence_counters[task_id]
    
    def _should_throttle(self, task_id: str, progress: int) -> bool:
        """检查是否需要节流"""
        now = time.time()
        cache_key = f"{task_id}_{progress}"
        
        if cache_key in self.throttle_cache:
            last_time = self.throttle_cache[cache_key]['timestamp']
            if now - last_time < self.throttle_interval:
                return True
        
        # 更新缓存
        self.throttle_cache[cache_key] = {
            'timestamp': now,
            'progress': progress
        }
        
        # 清理过期缓存（超过1分钟的）
        expired_keys = [
            key for key, data in self.throttle_cache.items()
            if now - data['timestamp'] > 60
        ]
        for key in expired_keys:
            del self.throttle_cache[key]
        
        return False
    
    async def report_progress(
        self,
        task_id: str,
        progress: int,
        step: int,
        total: int,
        phase: str,
        message: str,
        status: str = "PROGRESS",
        meta: Optional[Dict[str, Any]] = None
    ) -> bool:
        """报告任务进度"""
        try:
            # 节流检查
            if status == "PROGRESS" and self._should_throttle(task_id, progress):
                logger.debug(f"任务 {task_id} 进度 {progress}% 被节流")
                return True
            
            # 创建进度事件
            event = ProgressEvent(
                task_id=task_id,
                progress=progress,
                step=step,
                total=total,
                phase=phase,
                message=message,
                status=status,
                seq=self._get_next_seq(task_id),
                ts=time.time(),
                meta=meta
            )
            
            # 发布到Redis频道 - 使用项目ID而不是任务ID
            # 从task_id中提取project_id，或者使用meta中的project_id
            project_id = meta.get("project_id") if meta else None
            if not project_id:
                # 如果meta中没有project_id，尝试从task_id推断
                # 这里需要根据实际情况调整
                project_id = task_id  # 临时使用task_id，后续需要优化
            channel = project_progress_channel(project_id)
            redis_client = await self._get_redis_client()
            
            # 同时保存快照到Redis Hash
            snapshot_key = f"progress:last:{channel}"
            event_dict = event.to_dict()
            
            # 过滤掉None值，并将所有值转换为字符串，避免Redis存储错误
            filtered_dict = {}
            for k, v in event_dict.items():
                if v is not None:
                    if isinstance(v, dict):
                        # 将字典转换为JSON字符串
                        filtered_dict[k] = json.dumps(v, ensure_ascii=False)
                    else:
                        filtered_dict[k] = str(v)
            
            await redis_client.hset(snapshot_key, mapping=filtered_dict)
            await redis_client.expire(snapshot_key, 3600)  # 1小时过期
            
            # 发布到频道
            await redis_client.publish(channel, json.dumps(event_dict))
            
            logger.info(f"进度事件已发布: {task_id} - {progress}% - {phase} - seq:{event.seq}")
            return True
            
        except Exception as e:
            logger.error(f"发布进度事件失败: {e}")
            return False
    
    async def subscribe_to_task(
        self,
        task_id: str,
        callback: Callable[[ProgressEvent], None]
    ) -> bool:
        """订阅特定任务的进度事件"""
        try:
            channel = f"progress:{task_id}"
            redis_client = await self._get_redis_client()
            
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel)
            
            logger.info(f"已订阅任务进度频道: {channel}")
            
            # 异步处理消息
            async def message_handler():
                try:
                    async for message in pubsub.listen():
                        if message['type'] == 'message':
                            try:
                                data = json.loads(message['data'])
                                event = ProgressEvent.from_dict(data)
                                callback(event)
                            except Exception as e:
                                logger.error(f"处理进度事件失败: {e}")
                except Exception as e:
                    logger.error(f"订阅消息处理失败: {e}")
                finally:
                    await pubsub.unsubscribe(channel)
                    await pubsub.close()
            
            # 启动消息处理协程
            asyncio.create_task(message_handler())
            return True
            
        except Exception as e:
            logger.error(f"订阅任务进度失败: {e}")
            return False
    
    async def get_task_snapshot(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务进度快照"""
        try:
            redis_client = await self._get_redis_client()
            channel = f"progress:{task_id}"
            snapshot_key = f"progress:last:{channel}"
            snapshot = await redis_client.hgetall(snapshot_key)
            if snapshot:
                # 转换字符串值回适当类型
                if 'progress' in snapshot:
                    snapshot['progress'] = int(snapshot['progress'])
                if 'step' in snapshot:
                    snapshot['step'] = int(snapshot['step'])
                if 'total' in snapshot:
                    snapshot['total'] = int(snapshot['total'])
                if 'seq' in snapshot:
                    snapshot['seq'] = int(snapshot['seq'])
                if 'ts' in snapshot:
                    snapshot['ts'] = float(snapshot['ts'])
                return snapshot
            return None
        except Exception as e:
            logger.error(f"获取任务进度快照失败: {e}")
            return None

    async def get_task_final_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务最终状态（用于终态校准）"""
        try:
            redis_client = await self._get_redis_client()
            key = f"task_final_state:{task_id}"
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"获取任务最终状态失败: {e}")
            return None
    
    async def save_task_final_state(self, task_id: str, state: Dict[str, Any]) -> bool:
        """保存任务最终状态"""
        try:
            redis_client = await self._get_redis_client()
            key = f"task_final_state:{task_id}"
            await redis_client.setex(key, 3600, json.dumps(state))  # 1小时过期
            return True
        except Exception as e:
            logger.error(f"保存任务最终状态失败: {e}")
            return False
    
    async def close(self):
        """关闭Redis连接"""
        if self.redis_client:
            await self.redis_client.close()

# 全局实例
progress_event_service = ProgressEventService()

# 便捷函数
async def report_progress(
    task_id: str,
    progress: int,
    step: int,
    total: int,
    phase: str,
    message: str,
    status: str = "PROGRESS",
    meta: Optional[Dict[str, Any]] = None
) -> bool:
    """报告任务进度的便捷函数"""
    return await progress_event_service.report_progress(
        task_id, progress, step, total, phase, message, status, meta
    )

