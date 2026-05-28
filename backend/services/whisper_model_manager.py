"""
Whisper模型管理服务
负责模型的下载、状态检查、存储管理等功能
"""
import os
import json
import logging
import subprocess
import asyncio
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import requests
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class ModelStatus(str, Enum):
    """模型状态枚举"""
    AVAILABLE = "available"  # 可用
    DOWNLOADING = "downloading"  # 下载中
    DOWNLOADED = "downloaded"  # 已下载
    ERROR = "error"  # 错误
    NOT_FOUND = "not_found"  # 未找到


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    size: str
    size_bytes: int
    description: str
    accuracy: str
    speed: str
    status: ModelStatus
    download_progress: Optional[int] = None
    local_path: Optional[str] = None
    error_message: Optional[str] = None


class WhisperModelManager:
    """Whisper模型管理器"""
    
    def __init__(self, models_dir: Optional[Path] = None):
        self.models_dir = models_dir or self._get_default_models_dir()
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.download_tasks: Dict[str, asyncio.Task] = {}
        
        # 模型信息配置
        self.model_configs = {
            "tiny": {
                "size": "39 MB",
                "size_bytes": 39 * 1024 * 1024,
                "description": "最快速度，适合实时处理",
                "accuracy": "较低",
                "speed": "最快"
            },
            "base": {
                "size": "74 MB", 
                "size_bytes": 74 * 1024 * 1024,
                "description": "平衡选择，推荐日常使用",
                "accuracy": "中等",
                "speed": "快"
            },
            "small": {
                "size": "244 MB",
                "size_bytes": 244 * 1024 * 1024,
                "description": "较好准确度，适合重要内容",
                "accuracy": "较好",
                "speed": "中等"
            },
            "medium": {
                "size": "769 MB",
                "size_bytes": 769 * 1024 * 1024,
                "description": "高准确度，适合专业用途",
                "accuracy": "高",
                "speed": "较慢"
            },
            "large": {
                "size": "1550 MB",
                "size_bytes": 1550 * 1024 * 1024,
                "description": "最高准确度，适合重要项目",
                "accuracy": "最高",
                "speed": "最慢"
            }
        }
    
    def _get_default_models_dir(self) -> Path:
        """获取默认模型目录"""
        from backend.core.desktop_config import get_desktop_data_dir
        return get_desktop_data_dir() / "whisper_models"
    
    def get_all_models_info(self) -> List[ModelInfo]:
        """获取所有模型信息"""
        models = []
        
        for model_name, config in self.model_configs.items():
            status = self._check_model_status(model_name)
            local_path = self._get_model_path(model_name) if status == ModelStatus.DOWNLOADED else None
            
            models.append(ModelInfo(
                name=model_name,
                size=config["size"],
                size_bytes=config["size_bytes"],
                description=config["description"],
                accuracy=config["accuracy"],
                speed=config["speed"],
                status=status,
                local_path=local_path
            ))
        
        return models
    
    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """获取指定模型信息"""
        if model_name not in self.model_configs:
            return None
        
        config = self.model_configs[model_name]
        status = self._check_model_status(model_name)
        local_path = self._get_model_path(model_name) if status == ModelStatus.DOWNLOADED else None
        
        return ModelInfo(
            name=model_name,
            size=config["size"],
            size_bytes=config["size_bytes"],
            description=config["description"],
            accuracy=config["accuracy"],
            speed=config["speed"],
            status=status,
            local_path=local_path
        )
    
    def _check_model_status(self, model_name: str) -> ModelStatus:
        """检查模型状态"""
        try:
            # 检查是否正在下载
            if model_name in self.download_tasks and not self.download_tasks[model_name].done():
                return ModelStatus.DOWNLOADING
            
            # 检查本地文件是否存在
            model_path = self._get_model_path(model_name)
            if model_path.exists():
                return ModelStatus.DOWNLOADED
            
            # 检查whisper是否可用
            if not self._check_whisper_available():
                return ModelStatus.ERROR
            
            return ModelStatus.AVAILABLE
            
        except Exception as e:
            logger.error(f"检查模型状态失败: {e}")
            return ModelStatus.ERROR
    
    def _get_model_path(self, model_name: str) -> Path:
        """获取模型文件路径"""
        # Whisper模型通常存储在 ~/.cache/whisper/ 目录
        home_dir = Path.home()
        whisper_cache = home_dir / ".cache" / "whisper"
        
        # 检查常见的模型文件扩展名
        possible_files = [
            f"{model_name}.pt",
            f"{model_name}.bin",
            f"{model_name}.model"
        ]
        
        for filename in possible_files:
            model_file = whisper_cache / filename
            if model_file.exists():
                return model_file
        
        # 如果没找到，返回默认路径
        return whisper_cache / f"{model_name}.pt"
    
    def _check_whisper_available(self) -> bool:
        """检查Whisper是否可用"""
        try:
            result = subprocess.run(['whisper', '--help'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def download_model(self, model_name: str) -> bool:
        """下载模型"""
        if model_name not in self.model_configs:
            raise ValueError(f"不支持的模型: {model_name}")
        
        if model_name in self.download_tasks and not self.download_tasks[model_name].done():
            raise ValueError(f"模型 {model_name} 正在下载中")
        
        if self._check_model_status(model_name) == ModelStatus.DOWNLOADED:
            logger.info(f"模型 {model_name} 已存在")
            return True
        
        try:
            # 创建下载任务
            task = asyncio.create_task(self._download_model_async(model_name))
            self.download_tasks[model_name] = task
            
            result = await task
            return result
            
        except Exception as e:
            logger.error(f"下载模型 {model_name} 失败: {e}")
            return False
        finally:
            # 清理任务
            if model_name in self.download_tasks:
                del self.download_tasks[model_name]
    
    async def _download_model_async(self, model_name: str) -> bool:
        """异步下载模型"""
        try:
            logger.info(f"开始下载模型: {model_name}")
            
            # 使用whisper命令下载模型
            cmd = ['whisper', '--model', model_name, '--help']
            
            # 在后台线程中执行下载
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor, 
                    self._run_whisper_download, 
                    model_name
                )
            
            if result:
                logger.info(f"模型 {model_name} 下载完成")
                return True
            else:
                logger.error(f"模型 {model_name} 下载失败")
                return False
                
        except Exception as e:
            logger.error(f"下载模型 {model_name} 时发生错误: {e}")
            return False
    
    def _run_whisper_download(self, model_name: str) -> bool:
        """运行whisper下载命令"""
        try:
            # 使用whisper的模型下载功能
            # 这里我们通过运行一个简单的命令来触发模型下载
            cmd = ['python', '-c', f'import whisper; whisper.load_model("{model_name}")']
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600  # 1小时超时
            )
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            logger.error(f"模型 {model_name} 下载超时")
            return False
        except Exception as e:
            logger.error(f"运行whisper下载命令失败: {e}")
            return False
    
    def get_download_progress(self, model_name: str) -> Optional[int]:
        """获取下载进度"""
        if model_name not in self.download_tasks:
            return None
        
        task = self.download_tasks[model_name]
        if task.done():
            return 100
        
        # 这里可以实现更精确的进度跟踪
        # 目前返回一个估算值
        return 50  # 占位符
    
    def cancel_download(self, model_name: str) -> bool:
        """取消下载"""
        if model_name not in self.download_tasks:
            return False
        
        task = self.download_tasks[model_name]
        if not task.done():
            task.cancel()
            del self.download_tasks[model_name]
            logger.info(f"已取消模型 {model_name} 的下载")
            return True
        
        return False
    
    def delete_model(self, model_name: str) -> bool:
        """删除模型"""
        try:
            model_path = self._get_model_path(model_name)
            
            if not model_path.exists():
                logger.warning(f"模型文件不存在: {model_path}")
                return True
            
            # 删除模型文件
            model_path.unlink()
            logger.info(f"模型 {model_name} 已删除")
            return True
            
        except Exception as e:
            logger.error(f"删除模型 {model_name} 失败: {e}")
            return False
    
    def set_models_directory(self, directory: str) -> bool:
        """设置模型存储目录"""
        try:
            new_dir = Path(directory)
            new_dir.mkdir(parents=True, exist_ok=True)
            
            # 更新模型目录
            self.models_dir = new_dir
            
            # 这里可以添加将现有模型移动到新目录的逻辑
            logger.info(f"模型目录已设置为: {new_dir}")
            return True
            
        except Exception as e:
            logger.error(f"设置模型目录失败: {e}")
            return False
    
# 全局模型管理器实例
_model_manager: Optional[WhisperModelManager] = None


def get_model_manager() -> WhisperModelManager:
    """获取模型管理器实例"""
    global _model_manager
    if _model_manager is None:
        _model_manager = WhisperModelManager()
    return _model_manager
