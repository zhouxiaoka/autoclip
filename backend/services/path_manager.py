"""
路径管理器
专门管理项目相关的路径操作
"""

import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class PathManager:
    """路径管理器，负责项目路径的统一管理"""
    
    def __init__(self, project_id: str, base_dir: str = "data/projects"):
        self.project_id = project_id
        # 使用绝对路径
        project_root = Path(__file__).parent.parent.parent
        self.base_dir = project_root / base_dir
        self.project_dir = self.base_dir / project_id
        
        # 定义项目目录结构
        self.directory_structure = {
            "project_dir": self.project_dir,
            "metadata_dir": self.project_dir / "metadata",
            "raw_dir": self.project_dir / "raw",
            "outputs_dir": self.project_dir / "outputs",
            "logs_dir": self.project_dir / "logs",
            "backups_dir": self.project_dir / "backups",
            "temp_dir": self.project_dir / "temp"
        }
        
        # 确保目录结构存在
        self.ensure_directories()
    
    def ensure_directories(self):
        """确保所有必要的目录存在"""
        for dir_name, dir_path in self.directory_structure.items():
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"确保目录存在: {dir_name} -> {dir_path}")
    
    def get_project_paths(self) -> Dict[str, Path]:
        """获取项目相关路径"""
        return self.directory_structure.copy()
    
    def get_step_paths(self, step_name: str) -> Dict[str, Path]:
        """
        获取步骤相关的路径
        
        Args:
            step_name: 步骤名称
            
        Returns:
            步骤相关路径
        """
        metadata_dir = self.directory_structure["metadata_dir"]
        
        return {
            "input_path": metadata_dir / f"{step_name}_input.json",
            "output_path": metadata_dir / f"{step_name}_output.json",
            "intermediate_dir": metadata_dir / f"{step_name}_intermediate",
            "log_path": self.directory_structure["logs_dir"] / f"{step_name}.log"
        }
    
    def get_step_input_path(self, step_name: str) -> Path:
        """获取步骤输入文件路径"""
        return self.get_step_paths(step_name)["input_path"]
    
    def get_step_output_path(self, step_name: str) -> Path:
        """获取步骤输出文件路径"""
        return self.get_step_paths(step_name)["output_path"]
    
    def get_step_intermediate_dir(self, step_name: str) -> Path:
        """获取步骤中间文件目录"""
        return self.get_step_paths(step_name)["intermediate_dir"]
    
    def get_step_log_path(self, step_name: str) -> Path:
        """获取步骤日志文件路径"""
        return self.get_step_paths(step_name)["log_path"]
    
    def get_backup_path(self, filename: str) -> Path:
        """获取备份文件路径"""
        return self.directory_structure["backups_dir"] / filename
    
    def get_temp_path(self, filename: str) -> Path:
        """获取临时文件路径"""
        return self.directory_structure["temp_dir"] / filename
    
    def get_config_path(self) -> Path:
        """获取配置文件路径"""
        return self.project_dir / "config.yaml"
    
    def get_srt_path(self) -> Path:
        """获取SRT文件路径"""
        # 尝试从项目配置中获取SRT文件名
        try:
            from .config_manager import ProjectConfigManager
            config_manager = ProjectConfigManager(self.project_id)
            project_config = config_manager.get_project_config()
            
            if project_config and "processing_config" in project_config:
                srt_file = project_config["processing_config"].get("srt_file")
                if srt_file:
                    return self.directory_structure["raw_dir"] / srt_file
            
            # 如果配置中没有，尝试查找raw目录中的SRT文件
            raw_dir = self.directory_structure["raw_dir"]
            srt_files = list(raw_dir.glob("*.srt"))
            if srt_files:
                return srt_files[0]
            
            return raw_dir / "transcript.srt"
        except Exception as e:
            logger.warning(f"获取SRT路径失败: {e}")
            return self.directory_structure["raw_dir"] / "transcript.srt"
    
    def get_video_path(self) -> Path:
        """获取视频文件路径"""
        # 尝试从项目配置中获取视频文件名
        try:
            from .config_manager import ProjectConfigManager
            config_manager = ProjectConfigManager(self.project_id)
            project_config = config_manager.get_project_config()
            
            if project_config and "processing_config" in project_config:
                video_file = project_config["processing_config"].get("video_file")
                if video_file:
                    return self.directory_structure["raw_dir"] / video_file
            
            # 如果配置中没有，尝试查找raw目录中的视频文件
            raw_dir = self.directory_structure["raw_dir"]
            video_extensions = [".mp4", ".avi", ".mov", ".mkv", ".flv"]
            for ext in video_extensions:
                video_files = list(raw_dir.glob(f"*{ext}"))
                if video_files:
                    return video_files[0]
            
            return None
        except Exception as e:
            logger.warning(f"获取视频路径失败: {e}")
            return None
            
            if project_config and "srt_file" in project_config:
                srt_filename = project_config["srt_file"]
                return self.directory_structure["raw_dir"] / srt_filename
        except Exception as e:
            logger.warning(f"无法从项目配置获取SRT文件名: {e}")
        
        # 回退到默认文件名
        return self.directory_structure["raw_dir"] / "transcript.srt"
    
    def get_prompt_dir(self) -> Path:
        """获取prompt目录路径"""
        # 使用绝对路径指向项目根目录的prompt文件夹
        project_root = Path(__file__).parent.parent.parent
        return project_root / "prompt"
    
    def create_step_directories(self, step_name: str):
        """为特定步骤创建必要的目录"""
        step_paths = self.get_step_paths(step_name)
        
        # 创建中间文件目录
        step_paths["intermediate_dir"].mkdir(parents=True, exist_ok=True)
        
        # 确保日志目录存在
        step_paths["log_path"].parent.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"为步骤 {step_name} 创建目录结构")
    
    def cleanup_step_files(self, step_name: str, keep_output: bool = True):
        """
        清理步骤的临时文件
        
        Args:
            step_name: 步骤名称
            keep_output: 是否保留输出文件
        """
        step_paths = self.get_step_paths(step_name)
        
        # 清理中间文件目录
        if step_paths["intermediate_dir"].exists():
            import shutil
            shutil.rmtree(step_paths["intermediate_dir"])
            logger.info(f"已清理步骤 {step_name} 的中间文件")
        
        # 清理输入文件（可选）
        if step_paths["input_path"].exists():
            step_paths["input_path"].unlink()
            logger.debug(f"已清理步骤 {step_name} 的输入文件")
        
        # 清理输出文件（可选）
        if not keep_output and step_paths["output_path"].exists():
            step_paths["output_path"].unlink()
            logger.info(f"已清理步骤 {step_name} 的输出文件")
    
    def get_directory_size(self, dir_path: Path) -> int:
        """获取目录大小（字节）"""
        total_size = 0
        try:
            for file_path in dir_path.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            logger.warning(f"计算目录大小时出错: {dir_path}, 错误: {e}")
        
        return total_size
    
    def get_project_size_info(self) -> Dict[str, Any]:
        """获取项目大小信息"""
        size_info = {}
        
        for dir_name, dir_path in self.directory_structure.items():
            if dir_path.exists():
                size_info[dir_name] = {
                    "path": str(dir_path),
                    "size_bytes": self.get_directory_size(dir_path),
                    "file_count": len(list(dir_path.rglob("*"))) if dir_path.is_dir() else 0
                }
            else:
                size_info[dir_name] = {
                    "path": str(dir_path),
                    "size_bytes": 0,
                    "file_count": 0,
                    "exists": False
                }
        
        return size_info
    
    def validate_paths(self) -> List[str]:
        """验证路径的有效性"""
        errors = []
        
        # 检查项目目录是否可写
        if not self.project_dir.exists():
            try:
                self.project_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"无法创建项目目录: {self.project_dir}, 错误: {e}")
        
        # 检查各个子目录
        for dir_name, dir_path in self.directory_structure.items():
            if not dir_path.exists():
                try:
                    dir_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors.append(f"无法创建目录 {dir_name}: {dir_path}, 错误: {e}")
            elif not dir_path.is_dir():
                errors.append(f"路径不是目录: {dir_name} -> {dir_path}")
        
        return errors
    
    def get_relative_path(self, absolute_path: Path) -> str:
        """获取相对于项目目录的路径"""
        try:
            return str(absolute_path.relative_to(self.project_dir))
        except ValueError:
            return str(absolute_path)
    
    def get_absolute_path(self, relative_path: str) -> Path:
        """获取绝对路径"""
        return self.project_dir / relative_path 