"""
简化的进度服务 - 固定阶段 + 固定权重
基于你提出的"做笨做稳"方案
"""

import time
import json
import logging
from typing import List, Tuple, Optional, Dict, Any
import sqlite3
import threading
import os
try:
    import redis  # 可选依赖
except Exception:
    redis = None

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

class ProgressStore:
    def save(self, project_id: str, stage: str, percent: int, message: str, ts: int):
        raise NotImplementedError

    def get(self, project_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def delete(self, project_id: str):
        raise NotImplementedError

    def get_many(self, project_ids: List[str]) -> List[Dict[str, Any]]:
        return [s for pid in project_ids if (s := self.get(pid))]


class RedisProgressStore(ProgressStore):
    def __init__(self, redis_client):
        self.r = redis_client

    def save(self, project_id: str, stage: str, percent: int, message: str, ts: int):
        self.r.hset(f"progress:project:{project_id}", mapping={
            "stage": stage,
            "percent": str(percent),
            "message": message,
            "ts": str(ts)
        })
        payload = {"project_id": project_id, "stage": stage, "percent": percent, "message": message, "ts": ts}
        try:
            self.r.publish(f"progress:project:{project_id}", json.dumps(payload))
        except Exception:
            pass

    def get(self, project_id: str) -> Optional[Dict[str, Any]]:
        h = self.r.hgetall(f"progress:project:{project_id}")
        if not h:
            return None
        return {
            "project_id": project_id,
            "stage": h.get("stage", ""),
            "percent": int(h.get("percent", 0)),
            "message": h.get("message", ""),
            "ts": int(h.get("ts", 0))
        }

    def delete(self, project_id: str):
        self.r.delete(f"progress:project:{project_id}")


class SqliteProgressStore(ProgressStore):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS progress_snapshots (
                project_id TEXT PRIMARY KEY,
                stage TEXT,
                percent INTEGER,
                message TEXT,
                ts INTEGER
            )
            """
        )
        self._conn.commit()

    def save(self, project_id: str, stage: str, percent: int, message: str, ts: int):
        with self._lock:
            self._conn.execute(
                "REPLACE INTO progress_snapshots (project_id, stage, percent, message, ts) VALUES (?, ?, ?, ?, ?)",
                (project_id, stage, int(percent), message, int(ts))
            )
            self._conn.commit()

    def get(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT stage, percent, message, ts FROM progress_snapshots WHERE project_id = ?",
                (project_id,)
            )
            row = cur.fetchone()
        if not row:
            return None
        stage, percent, message, ts = row
        return {
            "project_id": project_id,
            "stage": stage or "",
            "percent": int(percent or 0),
            "message": message or "",
            "ts": int(ts or 0)
        }

    def delete(self, project_id: str):
        with self._lock:
            self._conn.execute("DELETE FROM progress_snapshots WHERE project_id = ?", (project_id,))
            self._conn.commit()

    def get_many(self, project_ids: List[str]) -> List[Dict[str, Any]]:
        if not project_ids:
            return []
        placeholders = ",".join(["?"] * len(project_ids))
        with self._lock:
            cur = self._conn.execute(
                f"SELECT project_id, stage, percent, message, ts FROM progress_snapshots WHERE project_id IN ({placeholders})",
                project_ids
            )
            rows = cur.fetchall()
        results = []
        for pid, stage, percent, message, ts in rows:
            results.append({
                "project_id": pid,
                "stage": stage or "",
                "percent": int(percent or 0),
                "message": message or "",
                "ts": int(ts or 0)
            })
        return results


# 选择存储：Desktop模式强制SQLite；Server模式优先Redis，失败则自动降级到SQLite
store: ProgressStore
try:
    from backend.core.desktop_config import is_desktop_mode, get_desktop_paths
    if is_desktop_mode():
        paths = get_desktop_paths()
        db_file = os.path.join(str(paths.data_dir), "progress.db")
        store = SqliteProgressStore(db_file)
        logger.info(f"桌面模式使用SQLite进度存储: {db_file}")
    else:
        if redis is None:
            raise RuntimeError("redis 未安装")
        # 从环境变量获取Redis URL，默认为本地地址
        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        r_client = redis.Redis.from_url(redis_url, decode_responses=True)
        r_client.ping()
        store = RedisProgressStore(r_client)
        logger.info("Server模式使用Redis进度存储")
except Exception as e:
    # 自动降级到SQLite
    try:
        # 优先使用桌面数据目录；若不可用则落到项目根 data 目录
        db_file = None
        try:
            from backend.core.desktop_config import get_desktop_paths
            db_file = os.path.join(str(get_desktop_paths().data_dir), "progress.db")
        except Exception:
            from pathlib import Path
            db_file = str((Path(__file__).parent.parent.parent / 'data' / 'progress.db').resolve())
        store = SqliteProgressStore(db_file)
        logger.warning(f"Redis不可用或未安装，自动降级到SQLite进度存储: {db_file}，原因: {e}")
    except Exception as e2:
        logger.error(f"初始化进度存储失败: {e2}")
        store = None


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
    if not store:
        logger.warning("进度存储未初始化，跳过进度发送")
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
        store.save(project_id, stage, percent, message, payload["ts"])
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
    if not store:
        return None
        
    try:
        return store.get(project_id)
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
    if not store:
        return []
    try:
        return store.get_many(project_ids)
    except Exception as e:
        logger.error(f"批量获取进度快照失败: {e}")
        return []


def clear_progress(project_id: str):
    """
    清除项目进度数据
    
    Args:
        project_id: 项目ID
    """
    if not store:
        return
    try:
        store.delete(project_id)
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
