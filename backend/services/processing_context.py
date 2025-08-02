"""
处理上下文
统一管理处理相关的上下文信息
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ProcessingContext:
    """处理上下文，统一管理处理相关的上下文信息"""
    
    project_id: str
    task_id: str
    db_session: Any = None
    srt_path: Optional[Path] = None
    debug_mode: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    
    # 处理状态
    is_initialized: bool = False
    is_completed: bool = False
    error_message: Optional[str] = None
    
    # 配置信息
    config: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """初始化后的处理"""
        self.validate_context()
    
    def validate_context(self):
        """验证上下文的有效性"""
        if not self.project_id:
            raise ValueError("project_id不能为空")
        if not self.task_id:
            raise ValueError("task_id不能为空")
        
        logger.debug(f"ProcessingContext验证通过: project_id={self.project_id}, task_id={self.task_id}")
    
    def set_srt_path(self, srt_path: Path):
        """设置SRT文件路径"""
        if not srt_path.exists():
            raise FileNotFoundError(f"SRT文件不存在: {srt_path}")
        self.srt_path = srt_path
        logger.debug(f"设置SRT路径: {srt_path}")
    
    def set_debug_mode(self, debug_mode: bool):
        """设置调试模式"""
        self.debug_mode = debug_mode
        logger.debug(f"设置调试模式: {debug_mode}")
    
    def set_config(self, config: Dict[str, Any]):
        """设置配置信息"""
        self.config.update(config)
        logger.debug(f"更新配置: {list(config.keys())}")
    
    def mark_initialized(self):
        """标记为已初始化"""
        self.is_initialized = True
        logger.debug("ProcessingContext已初始化")
    
    def mark_completed(self):
        """标记为已完成"""
        self.is_completed = True
        logger.debug("ProcessingContext已完成")
    
    def set_error(self, error_message: str):
        """设置错误信息"""
        self.error_message = error_message
        logger.error(f"ProcessingContext错误: {error_message}")
    
    def is_valid_for_execution(self) -> bool:
        """检查是否适合执行"""
        if not self.is_initialized:
            return False
        if self.is_completed:
            return False
        if self.error_message:
            return False
        return True
    
    def get_context_summary(self) -> Dict[str, Any]:
        """获取上下文摘要"""
        return {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "srt_path": str(self.srt_path) if self.srt_path else None,
            "debug_mode": self.debug_mode,
            "is_initialized": self.is_initialized,
            "is_completed": self.is_completed,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
            "config_keys": list(self.config.keys()) if self.config else []
        }
    
    def clone(self) -> 'ProcessingContext':
        """克隆上下文"""
        cloned = ProcessingContext(
            project_id=self.project_id,
            task_id=self.task_id,
            db_session=self.db_session,
            srt_path=self.srt_path,
            debug_mode=self.debug_mode,
            config=self.config.copy()
        )
        
        # 复制状态字段
        cloned.is_initialized = self.is_initialized
        cloned.is_completed = self.is_completed
        cloned.error_message = self.error_message
        
        return cloned 