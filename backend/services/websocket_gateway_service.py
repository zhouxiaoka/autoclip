"""
WebSocket网关服务
订阅Redis进度事件并转发给前端WebSocket连接
支持消息适配、快照回放、幂等订阅
"""

import json
import logging
import asyncio
from typing import Dict, Set, Any, Optional, Callable
from datetime import datetime
import redis.asyncio as redis
from ..core.config import get_redis_url
from ..core.websocket_manager import manager
from .progress_event_service import ProgressEvent, progress_event_service
from .progress_message_adapter import progress_adapter
from .progress_snapshot_service import snapshot_service
from ..shared.progress_channels import normalize_channel, project_progress_channel

logger = logging.getLogger(__name__)

class WebSocketGatewayService:
    """WebSocket网关服务"""
    
    def __init__(self):
        self.redis_url = get_redis_url()
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        self.channels_ref: Dict[str, int] = {}  # channel -> refcount
        self.router: Dict[str, Set[Callable]] = {}  # channel -> set of senders
        self.user_subscriptions: Dict[str, Set[str]] = {}  # user_id -> set of normalized channels
        self.lock = asyncio.Lock()
        self.listen_task: Optional[asyncio.Task] = None
        self.is_running = False
        
        # 节流控制
        self.last_progress: Dict[str, Dict[str, Any]] = {}  # channel -> {progress, timestamp}
        self.throttle_interval = 0.2  # 200ms最小间隔
    
    @staticmethod
    def normalize_channel(raw: str) -> str:
        """
        规范化频道名称，使用统一的频道命名规范
        
        Args:
            raw: 原始频道名
            
        Returns:
            规范化的频道名
        """
        return normalize_channel(raw)
        
    async def start(self):
        """启动网关服务"""
        if self.is_running:
            return
        
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            self.pubsub = self.redis_client.pubsub(ignore_subscribe_messages=True)
            self.is_running = True
            
            # 启动快照服务
            await snapshot_service.connect()
            
            # 启动监听循环
            self.listen_task = asyncio.create_task(self._listen_loop())
            
            logger.info("WebSocket网关服务已启动")
            
        except Exception as e:
            logger.error(f"启动WebSocket网关服务失败: {e}")
            self.is_running = False
    
    async def stop(self):
        """停止网关服务"""
        self.is_running = False
        
        if self.listen_task:
            self.listen_task.cancel()
            try:
                await self.listen_task
            except asyncio.CancelledError:
                pass
        
        if self.pubsub:
            await self.pubsub.aclose()  # redis-py 5.x 正确方法
        
        if self.redis_client:
            await self.redis_client.aclose()  # redis-py 5.x 正确方法
        
        # 停止快照服务
        await snapshot_service.disconnect()
        
        logger.info("WebSocket网关服务已停止")
    
    async def sync_user_subscriptions(self, user_id: str, channels: Set[str]) -> Dict[str, int]:
        """
        同步用户订阅 - 幂等操作
        
        Args:
            user_id: 用户ID
            channels: 要订阅的频道集合（原始格式，会自动规范化）
            
        Returns:
            操作统计: {"added": X, "removed": Y, "unchanged": Z}
        """
        async with self.lock:
            # 1) 规范化所有频道名
            desired = {self.normalize_channel(ch) for ch in channels}
            current = self.user_subscriptions.get(user_id, set())
            
            # 2) 计算差集
            to_add = desired - current
            to_remove = current - desired
            unchanged = current & desired
            
            # 3) 统计信息
            added, removed, same = len(to_add), len(to_remove), len(unchanged)
            
            # 4) 处理新增订阅
            for channel in to_add:
                try:
                    await self._subscribe_to_channel(channel)
                    current.add(channel)  # 本地集合立即更新
                    # 立即回放快照
                    await self._replay_snapshot(user_id, channel)
                except Exception as e:
                    logger.error(f"订阅频道失败 {channel}: {e}")
            
            # 5) 处理移除订阅
            for channel in to_remove:
                try:
                    await self._unsubscribe_from_channel(channel)
                    current.discard(channel)  # 本地集合立即删除
                except Exception as e:
                    logger.error(f"取消订阅频道失败 {channel}: {e}")
            
            # 6) 更新用户订阅记录（使用规范化后的集合）
            self.user_subscriptions[user_id] = current
            
            # 7) 日志降噪：只有变化时才INFO
            if added or removed:
                logger.info(f"订阅集同步完成: 用户 {user_id}, 新增 {added}, 移除 {removed}, 未变 {same}")
            else:
                logger.debug(f"订阅集同步完成(无变更): 用户 {user_id}, 未变 {same}")
            
            return {
                "added": added,
                "removed": removed, 
                "unchanged": same
            }
    
    async def _subscribe_to_channel(self, channel: str):
        """订阅频道"""
        if channel not in self.channels_ref:
            self.channels_ref[channel] = 0
            await self.pubsub.subscribe(channel)
            logger.debug(f"已订阅频道: {channel}")
        
        self.channels_ref[channel] += 1
    
    async def _unsubscribe_from_channel(self, channel: str):
        """取消订阅频道"""
        if channel in self.channels_ref:
            self.channels_ref[channel] -= 1
            if self.channels_ref[channel] <= 0:
                await self.pubsub.unsubscribe(channel)
                del self.channels_ref[channel]
                logger.debug(f"已取消订阅频道: {channel}")
    
    async def _replay_snapshot(self, user_id: str, channel: str):
        """回放快照"""
        try:
            snapshot = await snapshot_service.get_snapshot(channel)
            if snapshot:
                # 转换为简消息
                simple_msg = progress_adapter.to_simple(snapshot)
                simple_msg["snapshot"] = True
                
                # 发送给用户
                await manager.send_personal_message(simple_msg, user_id)
                logger.debug(f"快照已回放: {user_id} -> {channel}")
        except Exception as e:
            logger.error(f"回放快照失败: {e}")
    
    async def subscribe_user_to_task(self, user_id: str, task_id: str) -> bool:
        """用户订阅特定任务的进度"""
        try:
            # 规范化频道名 - 使用项目ID而不是任务ID
            # 这里需要从task_id推断project_id，或者修改调用方式
            # 临时使用task_id，但应该改为project_id
            channel = project_progress_channel(task_id)
            
            # 记录用户订阅
            if user_id not in self.user_subscriptions:
                self.user_subscriptions[user_id] = set()
            self.user_subscriptions[user_id].add(channel)
            
            # 创建发送器函数 - 使用用户ID作为标识
            async def sender(data: str):
                try:
                    logger.debug(f"发送器收到数据: {data}")
                    message_data = json.loads(data)
                    logger.debug(f"解析后的消息: {message_data}")
                    
                    # 构建WebSocket消息
                    ws_message = {
                        "type": "task_progress_update",
                        "task_id": message_data.get("task_id"),
                        "progress": message_data.get("progress"),
                        "step": message_data.get("step"),
                        "total": message_data.get("total"),
                        "phase": message_data.get("phase"),
                        "message": message_data.get("message"),
                        "status": message_data.get("status"),
                        "seq": message_data.get("seq"),
                        "ts": message_data.get("ts"),
                        "meta": message_data.get("meta"),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    await manager.send_personal_message(ws_message, user_id)
                    logger.debug(f"消息已发送给用户 {user_id}")
                except Exception as e:
                    logger.error(f"发送消息给用户 {user_id} 失败: {e}")
            
            # 为发送器添加标识，便于后续匹配
            sender._user_id = user_id
            sender._task_id = task_id
            
            # 订阅频道
            await self._subscribe_channel(channel, sender)
            
            # 发送订阅确认
            await manager.send_personal_message({
                "type": "subscription_confirmed",
                "task_id": task_id,
                "message": f"已订阅任务 {task_id} 的进度更新",
                "timestamp": datetime.utcnow().isoformat()
            }, user_id)
            
            # 发送快照（如果存在）
            try:
                from .progress_event_service import progress_event_service
                snapshot = await progress_event_service.get_task_snapshot(task_id)
                if snapshot:
                    snapshot_message = {
                        "type": "task_progress_update",
                        **snapshot,
                        "snapshot": True  # 标记为快照消息
                    }
                    await manager.send_personal_message(snapshot_message, user_id)
                    logger.debug(f"已发送任务 {task_id} 的快照给用户 {user_id}")
            except Exception as e:
                logger.error(f"发送任务快照失败: {e}")
            
            logger.debug(f"用户 {user_id} 已订阅任务 {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"用户订阅任务失败: {e}")
            return False
    
    async def unsubscribe_user_from_task(self, user_id: str, task_id: str) -> bool:
        """用户取消订阅特定任务的进度"""
        try:
            channel = f"progress:{task_id}"
            
            # 创建发送器函数（用于匹配）
            async def sender(data: str):
                try:
                    await manager.send_personal_message(json.loads(data), user_id)
                except Exception as e:
                    logger.error(f"发送消息给用户 {user_id} 失败: {e}")
            
            # 取消订阅频道
            await self._unsubscribe_channel(channel, sender)
            
            # 发送取消订阅确认
            await manager.send_personal_message({
                "type": "unsubscription_confirmed",
                "task_id": task_id,
                "message": f"已取消订阅任务 {task_id} 的进度更新",
                "timestamp": datetime.utcnow().isoformat()
            }, user_id)
            
            logger.debug(f"用户 {user_id} 已取消订阅任务 {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"用户取消订阅任务失败: {e}")
            return False
    
    async def unsubscribe_user_from_all_tasks(self, user_id: str):
        """用户断开连接时，取消所有订阅"""
        if user_id in self.user_subscriptions:
            task_ids = list(self.user_subscriptions[user_id])
            for task_id in task_ids:
                await self.unsubscribe_user_from_task(user_id, task_id)
            del self.user_subscriptions[user_id]
            logger.info(f"用户 {user_id} 已取消所有任务订阅")

    async def subscribe_user_to_many_tasks(self, user_id: str, task_ids: list[str]) -> dict:
        """批量订阅多个任务 - 幂等操作"""
        results = {"added": [], "already_subscribed": []}
        
        for task_id in task_ids:
            # 检查是否已经订阅
            if user_id in self.user_subscriptions and task_id in self.user_subscriptions[user_id]:
                results["already_subscribed"].append(task_id)
                logger.debug(f"用户 {user_id} 已订阅任务 {task_id}，跳过")
                continue
            
            # 执行订阅
            if await self.subscribe_user_to_task(user_id, task_id):
                results["added"].append(task_id)
            else:
                logger.error(f"用户 {user_id} 订阅任务 {task_id} 失败")
        
        logger.info(f"批量订阅完成: 用户 {user_id}, 新增 {len(results['added'])}, 已存在 {len(results['already_subscribed'])}")
        return results

    async def unsubscribe_user_from_many_tasks(self, user_id: str, task_ids: list[str]) -> dict:
        """批量取消订阅多个任务"""
        results = {"removed": [], "not_subscribed": []}
        
        for task_id in task_ids:
            # 检查是否已订阅
            if user_id not in self.user_subscriptions or task_id not in self.user_subscriptions[user_id]:
                results["not_subscribed"].append(task_id)
                logger.debug(f"用户 {user_id} 未订阅任务 {task_id}，跳过")
                continue
            
            # 执行取消订阅
            if await self.unsubscribe_user_from_task(user_id, task_id):
                results["removed"].append(task_id)
            else:
                logger.error(f"用户 {user_id} 取消订阅任务 {task_id} 失败")
        
        logger.info(f"批量取消订阅完成: 用户 {user_id}, 移除 {len(results['removed'])}, 未订阅 {len(results['not_subscribed'])}")
        return results

    async def sync_user_subscriptions(self, user_id: str, desired_task_ids: list[str]) -> dict:
        """同步用户订阅集 - 幂等对齐"""
        current_task_ids = list(self.user_subscriptions.get(user_id, set()))
        desired_set = set(desired_task_ids)
        current_set = set(current_task_ids)
        
        # 计算差异
        to_add = list(desired_set - current_set)
        to_remove = list(current_set - desired_set)
        
        results = {"added": [], "removed": [], "unchanged": []}
        
        # 批量添加
        if to_add:
            add_results = await self.subscribe_user_to_many_tasks(user_id, to_add)
            results["added"] = add_results["added"]
        
        # 批量移除
        if to_remove:
            remove_results = await self.unsubscribe_user_from_many_tasks(user_id, to_remove)
            results["removed"] = remove_results["removed"]
        
        # 未变化的
        results["unchanged"] = list(desired_set & current_set)
        
        # 只在有实际变化时才记录INFO日志，避免噪音
        if len(results['added']) > 0 or len(results['removed']) > 0:
            logger.info(f"订阅集同步完成: 用户 {user_id}, 新增 {len(results['added'])}, 移除 {len(results['removed'])}, 未变 {len(results['unchanged'])}")
        else:
            logger.debug(f"订阅集同步完成: 用户 {user_id}, 新增 {len(results['added'])}, 移除 {len(results['removed'])}, 未变 {len(results['unchanged'])}")
        return results
    
    async def _subscribe_channel(self, channel: str, sender: Callable):
        """订阅Redis频道 - 幂等操作"""
        async with self.lock:
            # 检查是否已经订阅过这个频道
            if sender in self.router.get(channel, set()):
                logger.debug(f"发送器已订阅频道 {channel}，跳过")
                return
            
            need_sub = channel not in self.channels_ref
            self.channels_ref[channel] = self.channels_ref.get(channel, 0) + 1
            self.router.setdefault(channel, set()).add(sender)
            
            if need_sub:
                await self.pubsub.subscribe(channel)
                logger.info(f"[Redis] SUB {channel}; total={len(self.channels_ref)}")
            else:
                logger.debug(f"[Redis] 频道 {channel} 已有订阅者，新增发送器")
    
    async def _unsubscribe_channel(self, channel: str, sender: Callable):
        """取消订阅Redis频道"""
        async with self.lock:
            if channel in self.router:
                self.router[channel].discard(sender)
            
            if channel in self.channels_ref:
                self.channels_ref[channel] -= 1
                if self.channels_ref[channel] <= 0:
                    del self.channels_ref[channel]
                    self.router.pop(channel, None)
                    await self.pubsub.unsubscribe(channel)
                    logger.info(f"[Redis] UNSUB {channel}; total={len(self.channels_ref)}")
    
    async def _listen_loop(self):
        """监听Redis消息的循环 - 集成消息适配和节流控制"""
        backoff = 0.05
        
        while self.is_running:
            try:
                # 检查是否有订阅的频道
                async with self.lock:
                    has_channels = bool(self.channels_ref)
                
                if not has_channels:
                    await asyncio.sleep(0.2)
                    continue
                
                # 获取消息 - 使用redis-py 5.x的正确方式
                msg = await self.pubsub.get_message(timeout=0.1)
                
                if not msg or msg["type"] != "message":
                    await asyncio.sleep(0.05)  # 短暂等待，避免CPU占用过高
                    continue
                
                channel = msg["channel"]
                data = msg["data"]
                
                # 解析消息
                try:
                    message_data = json.loads(data)
                except json.JSONDecodeError as e:
                    logger.error(f"解析消息失败: {e}, 数据: {data}")
                    continue
                
                # 检查是否为进度消息
                if not progress_adapter.is_progress_message(message_data):
                    logger.debug(f"跳过非进度消息: {message_data.get('type', 'unknown')}")
                    continue
                
                # 节流控制
                current_time = datetime.utcnow().timestamp()
                current_progress = message_data.get("progress", 0)
                
                if channel in self.last_progress:
                    last_data = self.last_progress[channel]
                    if progress_adapter.should_throttle(
                        last_data["progress"], current_progress,
                        last_data["timestamp"], current_time,
                        self.throttle_interval
                    ):
                        logger.debug(f"消息被节流: {channel} - {current_progress}%")
                        continue
                
                # 更新节流记录
                self.last_progress[channel] = {
                    "progress": current_progress,
                    "timestamp": current_time
                }
                
                # 转换为简消息
                simple_msg = progress_adapter.to_simple(message_data)
                
                # 获取目标用户 - 从频道订阅者中查找
                async with self.lock:
                    subscribed_users = set()
                    for user_id, user_channels in self.user_subscriptions.items():
                        if channel in user_channels:
                            subscribed_users.add(user_id)
                
                # 发送给所有订阅用户
                if subscribed_users:
                    logger.debug(f"转发简消息给 {len(subscribed_users)} 个用户: {channel} - {simple_msg}")
                    
                    # 并发发送
                    send_tasks = []
                    for user_id in subscribed_users:
                        send_tasks.append(
                            manager.send_personal_message(simple_msg, user_id)
                        )
                    
                    if send_tasks:
                        await asyncio.gather(*send_tasks, return_exceptions=True)
                else:
                    logger.debug(f"频道 {channel} 没有订阅用户")
                
                backoff = 0.05  # 重置退避时间
                
            except Exception as e:
                logger.error(f"处理Redis消息失败: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 1.0)  # 指数退避，最大1秒
    
    async def get_subscription_status(self, user_id: str) -> Dict[str, Any]:
        """获取用户订阅状态"""
        async with self.lock:
            return {
                "user_id": user_id,
                "subscribed_tasks": [],  # 简化实现
                "total_subscriptions": 0,
                "active_channels": len(self.channels_ref)
            }

# 全局实例
websocket_gateway_service = WebSocketGatewayService()
