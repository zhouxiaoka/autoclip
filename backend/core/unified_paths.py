"""
统一路径配置管理
确保所有路径配置都从同一个地方获取，避免路径混乱
"""

from pathlib import Path
from typing import Dict, Any

class UnifiedPathManager:
    """统一的路径管理器"""
    
    def __init__(self):
        self._project_root = self._get_project_root()
        self._data_dir = self._project_root / "data"
        self._output_dir = self._data_dir / "output"
        
        # 确保关键目录存在
        self._ensure_directories()
    
    def _get_project_root(self) -> Path:
        """获取项目根目录"""
        current_path = Path(__file__).parent  # backend/core/
        
        # 向上查找项目根目录
        while current_path.parent != current_path:
            if (current_path.parent / "frontend").exists() and (current_path.parent / "backend").exists():
                return current_path.parent
            current_path = current_path.parent
        
        # 如果没找到，使用默认路径
        return Path(__file__).parent.parent.parent
    
    def _ensure_directories(self):
        """确保关键目录存在"""
        directories = [
            self._data_dir,
            self._output_dir,
            self._output_dir / "clips",
            self._output_dir / "collections",
            self._output_dir / "metadata",
            self._data_dir / "projects",
            self._data_dir / "uploads",
            self._data_dir / "temp",
            self._data_dir / "backups"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    @property
    def project_root(self) -> Path:
        """项目根目录"""
        return self._project_root
    
    @property
    def data_directory(self) -> Path:
        """数据目录"""
        return self._data_dir
    
    @property
    def output_directory(self) -> Path:
        """输出目录"""
        return self._output_dir
    
    @property
    def clips_directory(self) -> Path:
        """切片目录"""
        return self._output_dir / "clips"
    
    @property
    def collections_directory(self) -> Path:
        """合集目录"""
        return self._output_dir / "collections"
    
    @property
    def metadata_directory(self) -> Path:
        """元数据目录"""
        return self._output_dir / "metadata"
    
    @property
    def projects_directory(self) -> Path:
        """项目目录"""
        return self._data_dir / "projects"
    
    @property
    def uploads_directory(self) -> Path:
        """上传目录"""
        return self._data_dir / "uploads"
    
    @property
    def temp_directory(self) -> Path:
        """临时目录"""
        return self._data_dir / "temp"
    
    @property
    def backups_directory(self) -> Path:
        """备份目录"""
        return self._data_dir / "backups"
    
    def get_project_directory(self, project_id: str) -> Path:
        """获取项目目录"""
        project_dir = self.projects_directory / project_id
        project_dir.mkdir(exist_ok=True)
        return project_dir
    
    def get_project_raw_directory(self, project_id: str) -> Path:
        """获取项目原始文件目录"""
        raw_dir = self.get_project_directory(project_id) / "raw"
        raw_dir.mkdir(exist_ok=True)
        return raw_dir
    
    def get_project_output_directory(self, project_id: str) -> Path:
        """获取项目输出目录"""
        output_dir = self.get_project_directory(project_id) / "output"
        output_dir.mkdir(exist_ok=True)
        return output_dir
    
    def get_project_clips_directory(self, project_id: str) -> Path:
        """获取项目切片目录"""
        clips_dir = self.clips_directory / project_id
        clips_dir.mkdir(exist_ok=True)
        return clips_dir
    
    def get_project_collections_directory(self, project_id: str) -> Path:
        """获取项目合集目录"""
        collections_dir = self.collections_directory / project_id
        collections_dir.mkdir(exist_ok=True)
        return collections_dir
    
    def get_database_path(self) -> Path:
        """获取数据库路径"""
        return self.data_directory / "autoclip.db"
    
    def get_settings_file_path(self) -> Path:
        """获取设置文件路径"""
        return self.data_directory / "settings.json"
    
    def get_clip_file_path(self, project_id: str, clip_title: str, extension: str = "mp4") -> Path:
        """获取切片文件路径"""
        clips_dir = self.get_project_clips_directory(project_id)
        # 清理文件名，移除特殊字符
        safe_title = "".join(c for c in clip_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        return clips_dir / f"{safe_title}.{extension}"
    
    def get_collection_file_path(self, project_id: str, collection_title: str, extension: str = "mp4") -> Path:
        """获取合集文件路径"""
        collections_dir = self.get_project_collections_directory(project_id)
        # 清理文件名，移除特殊字符
        safe_title = "".join(c for c in collection_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        return collections_dir / f"{safe_title}.{extension}"
    
    def get_metadata_file_path(self, project_id: str, step_name: str, filename: str) -> Path:
        """获取元数据文件路径"""
        metadata_dir = self.get_project_directory(project_id) / step_name
        metadata_dir.mkdir(exist_ok=True)
        return metadata_dir / filename
    
    def validate_paths(self) -> Dict[str, Any]:
        """验证所有路径配置"""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "paths": {}
        }
        
        try:
            # 检查关键目录
            key_paths = {
                "project_root": self.project_root,
                "data_directory": self.data_directory,
                "output_directory": self.output_directory,
                "clips_directory": self.clips_directory,
                "collections_directory": self.collections_directory,
                "metadata_directory": self.metadata_directory,
                "projects_directory": self.projects_directory
            }
            
            for name, path in key_paths.items():
                validation_result["paths"][name] = str(path)
                
                if not path.exists():
                    validation_result["warnings"].append(f"目录不存在: {name} = {path}")
                elif not path.is_dir():
                    validation_result["errors"].append(f"路径不是目录: {name} = {path}")
                    validation_result["valid"] = False
            
            # 检查是否有重复或冲突的路径
            all_paths = list(validation_result["paths"].values())
            if len(all_paths) != len(set(all_paths)):
                validation_result["errors"].append("存在重复的路径配置")
                validation_result["valid"] = False
            
        except Exception as e:
            validation_result["errors"].append(f"路径验证失败: {str(e)}")
            validation_result["valid"] = False
        
        return validation_result
    
    def get_path_summary(self) -> Dict[str, str]:
        """获取路径配置摘要"""
        return {
            "project_root": str(self.project_root),
            "data_directory": str(self.data_directory),
            "output_directory": str(self.output_directory),
            "clips_directory": str(self.clips_directory),
            "collections_directory": str(self.collections_directory),
            "metadata_directory": str(self.metadata_directory),
            "projects_directory": str(self.projects_directory),
            "uploads_directory": str(self.uploads_directory),
            "temp_directory": str(self.temp_directory),
            "backups_directory": str(self.backups_directory)
        }

# 全局路径管理器实例
path_manager = UnifiedPathManager()

# 向后兼容的路径常量
PROJECT_ROOT = path_manager.project_root
DATA_DIR = path_manager.data_directory
OUTPUT_DIR = path_manager.output_directory
CLIPS_DIR = path_manager.clips_directory
COLLECTIONS_DIR = path_manager.collections_directory
METADATA_DIR = path_manager.metadata_directory
PROJECTS_DIR = path_manager.projects_directory
UPLOADS_DIR = path_manager.uploads_directory
TEMP_DIR = path_manager.temp_directory
BACKUPS_DIR = path_manager.backups_directory

# 便捷函数
def get_project_directory(project_id: str) -> Path:
    """获取项目目录"""
    return path_manager.get_project_directory(project_id)

def get_clip_file_path(project_id: str, clip_title: str, extension: str = "mp4") -> Path:
    """获取切片文件路径"""
    return path_manager.get_clip_file_path(project_id, clip_title, extension)

def get_collection_file_path(project_id: str, collection_title: str, extension: str = "mp4") -> Path:
    """获取合集文件路径"""
    return path_manager.get_collection_file_path(project_id, collection_title, extension)

def validate_paths() -> Dict[str, Any]:
    """验证所有路径配置"""
    return path_manager.validate_paths()

def get_path_summary() -> Dict[str, str]:
    """获取路径配置摘要"""
    return path_manager.get_path_summary()
