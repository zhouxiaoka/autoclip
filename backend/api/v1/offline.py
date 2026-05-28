"""
离线模式支持API
提供网络状态检测、离线模式管理和缓存功能
"""
import os
import time
import asyncio
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.core.desktop_config import is_desktop_mode

router = APIRouter()

# 检查桌面模式
def check_desktop_mode():
    if not is_desktop_mode():
        raise HTTPException(status_code=400, detail="此端点仅在桌面模式下可用")

class NetworkStatus(BaseModel):
    """网络状态模型"""
    is_online: bool
    connection_quality: str  # excellent, good, poor, offline
    latency: Optional[float] = None
    last_check: str
    error_message: Optional[str] = None

class OfflineModeStatus(BaseModel):
    """离线模式状态模型"""
    is_offline_mode: bool
    auto_offline_threshold: int  # 连续失败次数阈值
    consecutive_failures: int
    last_successful_request: Optional[str] = None
    offline_since: Optional[str] = None

class CacheItem(BaseModel):
    """缓存项模型"""
    key: str
    data: Any
    created_at: str
    expires_at: Optional[str] = None
    size: int

class SyncQueueItem(BaseModel):
    """同步队列项模型"""
    id: str
    action: str  # create, update, delete
    resource_type: str  # project, clip, collection
    resource_id: str
    data: Dict[str, Any]
    created_at: str
    retry_count: int = 0
    max_retries: int = 3

# 内存中的状态存储（生产环境应使用持久化存储）
_network_status = NetworkStatus(
    is_online=True,
    connection_quality="good",
    last_check=datetime.now().isoformat()
)

_offline_mode_status = OfflineModeStatus(
    is_offline_mode=False,
    auto_offline_threshold=3,
    consecutive_failures=0
)

_cache: Dict[str, CacheItem] = {}
_sync_queue: List[SyncQueueItem] = []

@router.get("/network/status", response_model=NetworkStatus)
async def get_network_status():
    """获取网络状态"""
    check_desktop_mode()
    
    try:
        # 测试网络连接
        start_time = time.time()
        response = requests.get("https://www.google.com", timeout=5)
        latency = (time.time() - start_time) * 1000  # 转换为毫秒
        
        if response.status_code == 200:
            # 根据延迟判断连接质量
            if latency < 100:
                quality = "excellent"
            elif latency < 500:
                quality = "good"
            else:
                quality = "poor"
            
            _network_status.is_online = True
            _network_status.connection_quality = quality
            _network_status.latency = latency
            _network_status.last_check = datetime.now().isoformat()
            _network_status.error_message = None
            
            # 重置连续失败计数
            _offline_mode_status.consecutive_failures = 0
            _offline_mode_status.last_successful_request = datetime.now().isoformat()
            
        else:
            raise requests.RequestException(f"HTTP {response.status_code}")
            
    except Exception as e:
        # 网络连接失败
        _network_status.is_online = False
        _network_status.connection_quality = "offline"
        _network_status.latency = None
        _network_status.last_check = datetime.now().isoformat()
        _network_status.error_message = str(e)
        
        # 增加连续失败计数
        _offline_mode_status.consecutive_failures += 1
        
        # 检查是否应该自动进入离线模式
        if (_offline_mode_status.consecutive_failures >= _offline_mode_status.auto_offline_threshold 
            and not _offline_mode_status.is_offline_mode):
            _offline_mode_status.is_offline_mode = True
            _offline_mode_status.offline_since = datetime.now().isoformat()
    
    return _network_status

@router.get("/offline/status", response_model=OfflineModeStatus)
async def get_offline_mode_status():
    """获取离线模式状态"""
    check_desktop_mode()
    return _offline_mode_status

@router.post("/offline/toggle")
async def toggle_offline_mode():
    """切换离线模式"""
    check_desktop_mode()
    
    _offline_mode_status.is_offline_mode = not _offline_mode_status.is_offline_mode
    
    if _offline_mode_status.is_offline_mode:
        _offline_mode_status.offline_since = datetime.now().isoformat()
    else:
        _offline_mode_status.offline_since = None
        _offline_mode_status.consecutive_failures = 0
    
    return {
        "is_offline_mode": _offline_mode_status.is_offline_mode,
        "message": "离线模式已开启" if _offline_mode_status.is_offline_mode else "离线模式已关闭"
    }

@router.post("/offline/auto-threshold")
async def set_auto_offline_threshold(threshold: int):
    """设置自动离线阈值"""
    check_desktop_mode()
    
    if threshold < 1 or threshold > 10:
        raise HTTPException(status_code=400, detail="阈值必须在1-10之间")
    
    _offline_mode_status.auto_offline_threshold = threshold
    
    return {
        "auto_offline_threshold": threshold,
        "message": f"自动离线阈值已设置为 {threshold}"
    }

@router.get("/cache", response_model=List[CacheItem])
async def get_cache_items():
    """获取缓存项列表"""
    check_desktop_mode()
    
    # 清理过期缓存
    current_time = datetime.now()
    expired_keys = []
    
    for key, item in _cache.items():
        if item.expires_at:
            expires_at = datetime.fromisoformat(item.expires_at)
            if current_time > expires_at:
                expired_keys.append(key)
    
    for key in expired_keys:
        del _cache[key]
    
    return list(_cache.values())

@router.post("/cache")
async def add_cache_item(key: str, data: Any, expires_in_seconds: Optional[int] = None):
    """添加缓存项"""
    check_desktop_mode()
    
    created_at = datetime.now().isoformat()
    expires_at = None
    
    if expires_in_seconds:
        expires_at = (datetime.now() + timedelta(seconds=expires_in_seconds)).isoformat()
    
    # 计算数据大小（简单估算）
    size = len(str(data))
    
    _cache[key] = CacheItem(
        key=key,
        data=data,
        created_at=created_at,
        expires_at=expires_at,
        size=size
    )
    
    return {
        "key": key,
        "message": "缓存项已添加",
        "expires_at": expires_at
    }

@router.delete("/cache/{key}")
async def remove_cache_item(key: str):
    """删除缓存项"""
    check_desktop_mode()
    
    if key in _cache:
        del _cache[key]
        return {"message": f"缓存项 {key} 已删除"}
    else:
        raise HTTPException(status_code=404, detail="缓存项不存在")

@router.get("/sync-queue", response_model=List[SyncQueueItem])
async def get_sync_queue():
    """获取同步队列"""
    check_desktop_mode()
    return _sync_queue

@router.post("/sync-queue")
async def add_sync_queue_item(
    action: str,
    resource_type: str,
    resource_id: str,
    data: Dict[str, Any]
):
    """添加同步队列项"""
    check_desktop_mode()
    
    if action not in ["create", "update", "delete"]:
        raise HTTPException(status_code=400, detail="无效的操作类型")
    
    if resource_type not in ["project", "clip", "collection"]:
        raise HTTPException(status_code=400, detail="无效的资源类型")
    
    item = SyncQueueItem(
        id=f"{resource_type}_{resource_id}_{int(time.time())}",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        data=data,
        created_at=datetime.now().isoformat()
    )
    
    _sync_queue.append(item)
    
    return {
        "id": item.id,
        "message": "同步队列项已添加"
    }

@router.post("/sync-queue/process")
async def process_sync_queue():
    """处理同步队列"""
    check_desktop_mode()
    
    if _offline_mode_status.is_offline_mode:
        return {
            "message": "当前处于离线模式，无法处理同步队列",
            "queue_size": len(_sync_queue)
        }
    
    processed = 0
    failed = 0
    
    for item in _sync_queue[:]:  # 使用切片复制避免修改列表时的问题
        try:
            # 这里应该调用实际的API来同步数据
            # 为了演示，我们模拟一个简单的处理过程
            await simulate_sync_operation(item)
            
            _sync_queue.remove(item)
            processed += 1
            
        except Exception as e:
            item.retry_count += 1
            if item.retry_count >= item.max_retries:
                _sync_queue.remove(item)
                failed += 1
            else:
                # 保留在队列中等待重试
                pass
    
    return {
        "processed": processed,
        "failed": failed,
        "remaining": len(_sync_queue),
        "message": f"处理完成：成功 {processed} 个，失败 {failed} 个"
    }

async def simulate_sync_operation(item: SyncQueueItem):
    """模拟同步操作"""
    # 在实际实现中，这里应该调用相应的API端点
    # 例如：创建项目、更新片段、删除合集等
    await asyncio.sleep(0.1)  # 模拟网络延迟
    
    # 模拟偶尔的失败
    import random
    if random.random() < 0.1:  # 10% 的失败率
        raise Exception("模拟网络错误")

@router.delete("/sync-queue/clear")
async def clear_sync_queue():
    """清空同步队列"""
    check_desktop_mode()
    
    count = len(_sync_queue)
    _sync_queue.clear()
    
    return {
        "message": f"同步队列已清空，删除了 {count} 个项目"
    }

@router.get("/offline/summary")
async def get_offline_summary():
    """获取离线模式摘要信息"""
    check_desktop_mode()
    
    return {
        "network_status": _network_status,
        "offline_mode_status": _offline_mode_status,
        "cache_stats": {
            "total_items": len(_cache),
            "total_size": sum(item.size for item in _cache.values()),
            "expired_items": len([
                item for item in _cache.values() 
                if item.expires_at and datetime.fromisoformat(item.expires_at) < datetime.now()
            ])
        },
        "sync_queue_stats": {
            "total_items": len(_sync_queue),
            "pending_items": len([item for item in _sync_queue if item.retry_count < item.max_retries]),
            "failed_items": len([item for item in _sync_queue if item.retry_count >= item.max_retries])
        }
    }
