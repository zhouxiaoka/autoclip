"""
简化的进度服务 - 固定阶段 + 固定权重
基于你提出的"做笨做稳"方案
"""

import time
import json
import logging
from typing import List, Tuple, Optional, Dict, Any
import redis

logger = logging.getLogger(__name__)

# 固定阶段定义 - 根据你的项目实际调整
STAGES: List[Tuple[str, int]] = [
    ("INGEST", 10),        # 下载/就绪
    ("SUBTITLE", 15),      # 字幕/对齐
    ("ANALYZE", 20),       # 语义分析/大纲
    ("HIGHLIGHT", 25),     # 片段定位/打分
    ("EXPORT", 20),        # 导出/封装
    ("DONE", 10),          # 校验/归档
]

# 阶段权重映射
WEIGHTS = {name: w for name, w in STAGES}
# 阶段顺序
ORDER = [name for name, _ in STAGES]

# Redis连接 - 使用项目现有的Redis配置
try:
    r = redis.Redis.from_url("redis://127.0.0.1:6379/0", decode_responses=True)
    # 测试连接
    r.ping()
    logger.info("Redis连接成功")
except Exception as e:
    logger.error(f"Redis连接失败: {e}")
    r = None


def compute_percent(stage: str, subpercent: Optional[float] = None) -> int:
    """
    计算阶段对应的百分比
    
    Args:
        stage: 当前阶段名称
        subpercent: 子进度百分比 (0-100)，可选
        
    Returns:
        总进度百分比 (0-100)
    """
    # 累加之前阶段权重
    done = 0
    for s in ORDER:
        if s == stage:
            break
        done += WEIGHTS[s]
    
    # 当前阶段
    cur = WEIGHTS.get(stage, 0)
    
    if subpercent is None:
        # 阶段切换时，显示到当前阶段开始
        return min(100, done + cur) if stage == "DONE" else min(99, done)
    else:
        # 带子进度，按权重线性换算
        subpercent = max(0, min(100, subpercent))
        return min(99, done + int(cur * subpercent / 100))


def emit_progress(project_id: str, stage: str, message: str = "", subpercent: Optional[float] = None):
    """
    发送进度事件
    
    Args:
        project_id: 项目ID
        stage: 当前阶段
        message: 进度消息
        subpercent: 子进度百分比，可选
    """
    if not r:
        logger.warning("Redis未连接，跳过进度发送")
        return
        
    percent = compute_percent(stage, subpercent)
    payload = {
        "project_id": project_id,
        "stage": stage,
        "percent": percent,
        "message": message,
        "ts": int(time.time())
    }
    
    try:
        # 1) 持久化最新快照（给轮询/刷新用）
        r.hset(f"progress:project:{project_id}", mapping={
            "stage": stage, 
            "percent": str(percent), 
            "message": message, 
            "ts": str(payload["ts"])
        })
        
        # 2) 即时广播（可选，用于WebSocket）
        r.publish(f"progress:project:{project_id}", json.dumps(payload))
        
        logger.info(f"进度事件已发送: {project_id} - {stage} ({percent}%) - {message}")
        
    except Exception as e:
        logger.error(f"发送进度事件失败: {e}")


def get_progress_snapshot(project_id: str) -> Optional[Dict[str, Any]]:
    """
    获取项目进度快照
    
    Args:
        project_id: 项目ID
        
    Returns:
        进度快照数据，如果不存在返回None
    """
    if not r:
        return None
        
    try:
        h = r.hgetall(f"progress:project:{project_id}")
        if not h:
            return None
            
        return {
            "project_id": project_id,
            "stage": h.get("stage", ""),
            "percent": int(h.get("percent", 0)),
            "message": h.get("message", ""),
            "ts": int(h.get("ts", 0))
        }
    except Exception as e:
        logger.error(f"获取进度快照失败: {e}")
        return None


def get_multiple_progress_snapshots(project_ids: List[str]) -> List[Dict[str, Any]]:
    """
    批量获取多个项目的进度快照
    
    Args:
        project_ids: 项目ID列表
        
    Returns:
        进度快照列表
    """
    if not r:
        return []
        
    results = []
    for project_id in project_ids:
        snapshot = get_progress_snapshot(project_id)
        if snapshot:
            results.append(snapshot)
    
    return results


def clear_progress(project_id: str):
    """
    清除项目进度数据
    
    Args:
        project_id: 项目ID
    """
    if not r:
        return
        
    try:
        r.delete(f"progress:project:{project_id}")
        logger.info(f"已清除项目进度数据: {project_id}")
    except Exception as e:
        logger.error(f"清除进度数据失败: {e}")


# 阶段名称映射（用于显示）
STAGE_NAMES = {
    "INGEST": "素材准备",
    "SUBTITLE": "字幕处理", 
    "ANALYZE": "内容分析",
    "HIGHLIGHT": "片段定位",
    "EXPORT": "视频导出",
    "DONE": "处理完成"
}

def get_stage_display_name(stage: str) -> str:
    """获取阶段的显示名称"""
    return STAGE_NAMES.get(stage, stage)
