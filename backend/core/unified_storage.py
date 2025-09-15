"""
统一存储管理服务
确保所有组件使用相同的路径逻辑和数据存储策略
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

logger = logging.getLogger(__name__)

class UnifiedStorageManager:
    """统一存储管理器"""
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        初始化统一存储管理器
        
        Args:
            project_root: 项目根目录，如果为None则自动检测
        """
        self.project_root = project_root or self._get_project_root()
        self.data_dir = self.project_root / "data"
        self.output_dir = self.data_dir / "output"
        
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
            self.data_dir,
            self.output_dir,
            self.output_dir / "clips",
            self.output_dir / "collections",
            self.output_dir / "metadata",
            self.data_dir / "projects",
            self.data_dir / "uploads",
            self.data_dir / "temp",
            self.data_dir / "backups"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    # 项目相关路径
    def get_project_directory(self, project_id: str) -> Path:
        """获取项目目录"""
        project_dir = self.data_dir / "projects" / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir
    
    def get_project_raw_directory(self, project_id: str) -> Path:
        """获取项目原始文件目录"""
        raw_dir = self.get_project_directory(project_id) / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        return raw_dir
    
    def get_project_output_directory(self, project_id: str) -> Path:
        """获取项目输出目录"""
        output_dir = self.get_project_directory(project_id) / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    
    def get_project_clips_directory(self, project_id: str) -> Path:
        """获取项目切片目录"""
        clips_dir = self.get_project_output_directory(project_id) / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        return clips_dir
    
    def get_project_collections_directory(self, project_id: str) -> Path:
        """获取项目合集目录"""
        collections_dir = self.get_project_output_directory(project_id) / "collections"
        collections_dir.mkdir(parents=True, exist_ok=True)
        return collections_dir
    
    def get_project_metadata_directory(self, project_id: str) -> Path:
        """获取项目元数据目录"""
        metadata_dir = self.get_project_directory(project_id) / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        return metadata_dir
    
    # 文件路径构建
    def get_video_file_path(self, project_id: str, filename: str) -> Path:
        """获取项目视频文件路径"""
        return self.get_project_raw_directory(project_id) / filename
    
    def get_srt_file_path(self, project_id: str, filename: str) -> Path:
        """获取项目SRT文件路径"""
        return self.get_project_raw_directory(project_id) / filename
    
    def get_clip_file_path(self, project_id: str, clip_id: str, title: str) -> Path:
        """获取切片文件路径"""
        # 清理文件名，移除特殊字符
        safe_title = self._sanitize_filename(title)
        return self.get_project_clips_directory(project_id) / f"{clip_id}_{safe_title}.mp4"
    
    def get_collection_file_path(self, project_id: str, collection_id: str, title: str) -> Path:
        """获取合集文件路径"""
        # 清理文件名，移除特殊字符
        safe_title = self._sanitize_filename(title)
        return self.get_project_collections_directory(project_id) / f"{collection_id}_{safe_title}.mp4"
    
    def get_metadata_file_path(self, project_id: str, filename: str) -> Path:
        """获取项目元数据文件路径"""
        return self.get_project_metadata_directory(project_id) / filename
    
    # 文件操作
    def save_metadata(self, project_id: str, filename: str, data: Dict[str, Any]) -> Path:
        """保存元数据到文件"""
        metadata_file = self.get_metadata_file_path(project_id, filename)
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"元数据已保存: {metadata_file}")
        return metadata_file
    
    def load_metadata(self, project_id: str, filename: str) -> Optional[Dict[str, Any]]:
        """加载元数据文件"""
        metadata_file = self.get_metadata_file_path(project_id, filename)
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载元数据失败 {metadata_file}: {e}")
        
        return None
    
    def file_exists(self, file_path: Union[str, Path]) -> bool:
        """检查文件是否存在"""
        return Path(file_path).exists()
    
    def get_file_size(self, file_path: Union[str, Path]) -> int:
        """获取文件大小（字节）"""
        try:
            return Path(file_path).stat().st_size
        except Exception:
            return 0
    
    def get_file_modified_time(self, file_path: Union[str, Path]) -> Optional[datetime]:
        """获取文件修改时间"""
        try:
            timestamp = Path(file_path).stat().st_mtime
            return datetime.fromtimestamp(timestamp)
        except Exception:
            return None
    
    # 路径验证和修复
    def validate_file_path(self, file_path: Union[str, Path]) -> bool:
        """验证文件路径是否安全"""
        try:
            file_path = Path(file_path).resolve()
            # 检查路径是否在允许的目录内
            allowed_dirs = [
                self.data_dir,
                self.output_dir,
                self.project_root
            ]
            
            return any(file_path.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs)
        except Exception:
            return False
    
    def fix_file_path(self, file_path: Union[str, Path], project_id: str, file_type: str = "clip") -> Optional[Path]:
        """
        修复文件路径，确保文件在正确的位置
        
        Args:
            file_path: 原始文件路径
            project_id: 项目ID
            file_type: 文件类型 ("clip", "collection", "raw")
            
        Returns:
            修复后的文件路径，如果文件不存在则返回None
        """
        original_path = Path(file_path)
        
        # 如果文件存在且路径安全，直接返回
        if original_path.exists() and self.validate_file_path(original_path):
            return original_path
        
        # 尝试在标准位置查找文件
        if file_type == "clip":
            # 从文件名中提取clip_id和title
            filename = original_path.name
            if '_' in filename:
                parts = filename.split('_', 1)
                if len(parts) == 2:
                    clip_id = parts[0]
                    title = parts[1].replace('.mp4', '')
                    standard_path = self.get_clip_file_path(project_id, clip_id, title)
                    if standard_path.exists():
                        return standard_path
        
        elif file_type == "collection":
            # 从文件名中提取collection_id和title
            filename = original_path.name
            if '_' in filename:
                parts = filename.split('_', 1)
                if len(parts) == 2:
                    collection_id = parts[0]
                    title = parts[1].replace('.mp4', '')
                    standard_path = self.get_collection_file_path(project_id, collection_id, title)
                    if standard_path.exists():
                        return standard_path
            else:
                # 尝试直接使用文件名作为title
                title = filename.replace('.mp4', '')
                # 这里需要collection_id，暂时返回None
                return None
        
        elif file_type == "raw":
            # 原始文件通常在raw目录
            filename = original_path.name
            standard_path = self.get_project_raw_directory(project_id) / filename
            if standard_path.exists():
                return standard_path
        
        return None
    
    # 工具方法
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除特殊字符"""
        # 移除或替换特殊字符
        safe_chars = []
        for char in filename:
            if char.isalnum() or char in (' ', '-', '_', '，', '。', '？', '！', '：', '；'):
                safe_chars.append(char)
            else:
                safe_chars.append('_')
        
        # 移除多余的空格和下划线
        result = ''.join(safe_chars).strip()
        result = result.replace(' ', '_')
        
        # 移除连续的下划线
        while '__' in result:
            result = result.replace('__', '_')
        
        return result
    
    def get_storage_info(self, project_id: str) -> Dict[str, Any]:
        """获取项目存储信息"""
        project_dir = self.get_project_directory(project_id)
        
        info = {
            "project_id": project_id,
            "project_directory": str(project_dir),
            "raw_files": [],
            "clips": [],
            "collections": [],
            "metadata_files": [],
            "total_size": 0
        }
        
        # 扫描原始文件
        raw_dir = self.get_project_raw_directory(project_id)
        for file_path in raw_dir.iterdir():
            if file_path.is_file():
                info["raw_files"].append({
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                })
                info["total_size"] += file_path.stat().st_size
        
        # 扫描切片文件
        clips_dir = self.get_project_clips_directory(project_id)
        for file_path in clips_dir.iterdir():
            if file_path.is_file() and file_path.suffix == '.mp4':
                info["clips"].append({
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                })
                info["total_size"] += file_path.stat().st_size
        
        # 扫描合集文件
        collections_dir = self.get_project_collections_directory(project_id)
        for file_path in collections_dir.iterdir():
            if file_path.is_file() and file_path.suffix == '.mp4':
                info["collections"].append({
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                })
                info["total_size"] += file_path.stat().st_size
        
        # 扫描元数据文件
        metadata_dir = self.get_project_metadata_directory(project_id)
        for file_path in metadata_dir.iterdir():
            if file_path.is_file() and file_path.suffix == '.json':
                info["metadata_files"].append({
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                })
                info["total_size"] += file_path.stat().st_size
        
        return info

# 全局实例
_storage_manager = None

def get_storage_manager() -> UnifiedStorageManager:
    """获取全局存储管理器实例"""
    global _storage_manager
    if _storage_manager is None:
        _storage_manager = UnifiedStorageManager()
    return _storage_manager

