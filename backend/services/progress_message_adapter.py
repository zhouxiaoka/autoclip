"""
进度消息适配器
将富消息转换为简消息，实现向下兼容
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ProgressMessageAdapter:
    """进度消息适配器"""
    
    @staticmethod
    def to_simple(msg: dict) -> dict:
        """
        将富消息转换为简消息
        
        Args:
            msg: 富消息字典
            
        Returns:
            简消息字典
        """
        # 状态映射
        status_map = {
            "PROGRESS": "running", 
            "RUNNING": "running",
            "COMPLETED": "completed", 
            "FAILED": "failed", 
            "ERROR": "failed",
            "PENDING": "running",
            "CANCELLED": "failed"
        }
        
        # 提取项目ID
        project_id = msg.get("project_id") or msg.get("projectId")
        
        # 提取进度值 - 支持新的统一格式
        progress = msg.get("progress", 0) or msg.get("percent", 0)
        if isinstance(progress, (int, float)):
            progress = int(round(float(progress)))
        else:
            progress = 0
        
        # 提取步骤名称
        step_name = (
            msg.get("step_name") or 
            msg.get("phase") or 
            msg.get("current_step") or 
            msg.get("message") or
            "处理中"
        )
        
        # 提取状态
        status = msg.get("status", "running")
        if isinstance(status, str):
            status = status_map.get(status.upper(), "running")
        
        # 构建简消息
        simple_msg = {
            "type": "task_progress_update",
            "project_id": project_id,
            "progress": progress,
            "step_name": step_name,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # 可选字段
        if "task_id" in msg:
            simple_msg["task_id"] = msg["task_id"]
        
        if "message" in msg:
            simple_msg["message"] = msg["message"]
        
        logger.debug(f"消息适配: 富消息 -> 简消息: {simple_msg}")
        return simple_msg
    
    @staticmethod
    def is_progress_message(msg: dict) -> bool:
        """
        判断是否为进度消息
        
        Args:
            msg: 消息字典
            
        Returns:
            是否为进度消息
        """
        progress_types = [
            "task_progress_update",
            "task_update", 
            "project_update",
            "progress_update",
            "project_progress"  # 新增统一格式
        ]
        
        msg_type = msg.get("type", "")
        return msg_type in progress_types
    
    @staticmethod
    def extract_project_id(msg: dict) -> Optional[str]:
        """
        从消息中提取项目ID
        
        Args:
            msg: 消息字典
            
        Returns:
            项目ID或None
        """
        return msg.get("project_id") or msg.get("projectId")
    
    @staticmethod
    def should_throttle(last_progress: int, current_progress: int, 
                       last_timestamp: float, current_timestamp: float,
                       min_interval: float = 0.2) -> bool:
        """
        判断是否应该节流发送
        
        Args:
            last_progress: 上次进度
            current_progress: 当前进度
            last_timestamp: 上次时间戳
            current_timestamp: 当前时间戳
            min_interval: 最小间隔(秒)
            
        Returns:
            是否应该节流
        """
        # 时间间隔检查
        if current_timestamp - last_timestamp < min_interval:
            return True
        
        # 进度回退检查 - 避免UI回闪
        if current_progress < last_progress:
            logger.debug(f"进度回退，使用上次进度: {current_progress} -> {last_progress}")
            return True
        
        return False

# 全局适配器实例
progress_adapter = ProgressMessageAdapter()
