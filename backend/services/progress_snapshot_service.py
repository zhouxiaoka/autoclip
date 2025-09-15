"""
进度快照服务
管理Redis快照存储和回放
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import redis.asyncio as redis
from ..core.config import get_redis_url

logger = logging.getLogger(__name__)

class ProgressSnapshotService:
    """进度快照服务"""
    
    def __init__(self):
        self.redis_url = get_redis_url()
        self.redis_client: Optional[redis.Redis] = None
        self._connected = False
    
    async def connect(self):
        """连接Redis"""
        if self._connected:
            return
        
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            await self.redis_client.ping()
            self._connected = True
            logger.info("进度快照服务已连接Redis")
        except Exception as e:
            logger.error(f"连接Redis失败: {e}")
            self._connected = False
    
    async def disconnect(self):
        """断开Redis连接"""
        if self.redis_client:
            await self.redis_client.aclose()
            self.redis_client = None
        self._connected = False
        logger.info("进度快照服务已断开Redis")
    
    def _get_snapshot_key(self, channel: str) -> str:
        """获取快照键名"""
        return f"progress:last:{channel}"
    
    async def save_snapshot(self, channel: str, payload: dict) -> bool:
        """
        保存进度快照
        
        Args:
            channel: 频道名
            payload: 消息载荷
            
        Returns:
            是否保存成功
        """
        if not self._connected:
            await self.connect()
        
        if not self.redis_client:
            return False
        
        try:
            snapshot_key = self._get_snapshot_key(channel)
            
            # 添加时间戳
            payload_with_ts = {
                **payload,
                "snapshot_timestamp": datetime.utcnow().isoformat()
            }
            
            # 保存到Redis Hash
            await self.redis_client.hset(snapshot_key, mapping=payload_with_ts)
            
            # 设置过期时间（24小时）
            await self.redis_client.expire(snapshot_key, 86400)
            
            logger.debug(f"快照已保存: {channel} -> {snapshot_key}")
            return True
            
        except Exception as e:
            logger.error(f"保存快照失败: {e}")
            return False
    
    async def get_snapshot(self, channel: str) -> Optional[dict]:
        """
        获取进度快照
        
        Args:
            channel: 频道名
            
        Returns:
            快照数据或None
        """
        if not self._connected:
            await self.connect()
        
        if not self.redis_client:
            return None
        
        try:
            snapshot_key = self._get_snapshot_key(channel)
            snapshot_data = await self.redis_client.hgetall(snapshot_key)
            
            if snapshot_data:
                logger.debug(f"快照已获取: {channel} -> {snapshot_data}")
                return snapshot_data
            else:
                logger.debug(f"快照不存在: {channel}")
                return None
                
        except Exception as e:
            logger.error(f"获取快照失败: {e}")
            return None
    
    async def delete_snapshot(self, channel: str) -> bool:
        """
        删除进度快照
        
        Args:
            channel: 频道名
            
        Returns:
            是否删除成功
        """
        if not self._connected:
            await self.connect()
        
        if not self.redis_client:
            return False
        
        try:
            snapshot_key = self._get_snapshot_key(channel)
            result = await self.redis_client.delete(snapshot_key)
            
            if result:
                logger.debug(f"快照已删除: {channel}")
            else:
                logger.debug(f"快照不存在，无需删除: {channel}")
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"删除快照失败: {e}")
            return False
    
    async def cleanup_expired_snapshots(self) -> int:
        """
        清理过期的快照
        
        Returns:
            清理的快照数量
        """
        if not self._connected:
            await self.connect()
        
        if not self.redis_client:
            return 0
        
        try:
            # 查找所有快照键
            pattern = "progress:last:*"
            keys = await self.redis_client.keys(pattern)
            
            cleaned_count = 0
            for key in keys:
                # 检查是否过期
                ttl = await self.redis_client.ttl(key)
                if ttl == -1:  # 没有设置过期时间
                    await self.redis_client.expire(key, 86400)  # 设置24小时过期
                elif ttl == -2:  # 键不存在
                    cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"清理了 {cleaned_count} 个过期快照")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理过期快照失败: {e}")
            return 0

# 全局快照服务实例
snapshot_service = ProgressSnapshotService()
