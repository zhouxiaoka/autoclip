"""
统一存储服务
"""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
from core.config import get_data_directory

logger = logging.getLogger(__name__)

class StorageService:
    """统一存储服务"""
    
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.data_dir = get_data_directory()
        self.project_dir = self.data_dir / "projects" / project_id
        
        # 确保项目目录结构存在
        self._ensure_project_structure()
    
    def _ensure_project_structure(self):
        """确保项目目录结构存在"""
        directories = [
            self.project_dir / "raw",
            self.project_dir / "processing",
            self.project_dir / "output" / "clips",
            self.project_dir / "output" / "collections"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
    
    def save_metadata(self, metadata: Dict[str, Any], step: str) -> str:
        """保存处理元数据到文件系统"""
        metadata_file = self.project_dir / "processing" / f"{step}.json"
        
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        logger.info(f"保存元数据: {metadata_file}")
        return str(metadata_file)
    
    def get_metadata(self, step: str) -> Optional[Dict[str, Any]]:
        """获取处理元数据"""
        metadata_file = self.project_dir / "processing" / f"{step}.json"
        
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    def save_file(self, file_path: Path, target_name: str, file_type: str = "raw") -> str:
        """保存文件到项目目录"""
        if file_type == "raw":
            target_path = self.project_dir / "raw" / target_name
        elif file_type == "clip":
            target_path = self.project_dir / "output" / "clips" / target_name
        elif file_type == "collection":
            target_path = self.project_dir / "output" / "collections" / target_name
        else:
            raise ValueError(f"不支持的文件类型: {file_type}")
        
        # 确保目标目录存在
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 复制文件
        shutil.copy2(file_path, target_path)
        logger.info(f"保存文件: {target_path}")
        return str(target_path)
    
    def save_processing_result(self, step: str, result: Dict[str, Any]) -> str:
        """保存处理结果到文件系统"""
        return self.save_metadata(result, step)
    
    def save_clip_file(self, clip_data: Dict[str, Any], clip_id: str) -> str:
        """保存切片文件并返回路径"""
        # 获取标题并清理文件名
        title = clip_data.get('title', f'clip_{clip_id}')
        from utils.video_processor import VideoProcessor
        safe_title = VideoProcessor.sanitize_filename(title)
        
        # 使用统一的命名格式：{clip_id}_{safe_title}.mp4
        clip_file = f"{clip_id}_{safe_title}.mp4"
        target_path = self.project_dir / "output" / "clips" / clip_file
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建模拟文件（实际应该保存真实的视频文件）
        target_path.touch()
        logger.info(f"保存切片文件: {target_path}")
        return str(target_path)
    
    def save_collection_file(self, collection_data: Dict[str, Any], collection_id: str) -> str:
        """保存合集文件并返回路径"""
        # 这里应该包含实际的合集文件保存逻辑
        # 暂时返回模拟路径
        collection_file = f"collection_{collection_id}.mp4"
        target_path = self.project_dir / "output" / "collections" / collection_file
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建模拟文件（实际应该保存真实的合集文件）
        target_path.touch()
        logger.info(f"保存合集文件: {target_path}")
        return str(target_path)
    
    def get_file_content(self, file_path: str) -> Optional[Dict[str, Any]]:
        """获取文件内容"""
        try:
            file_path_obj = Path(file_path)
            if file_path_obj.exists() and file_path_obj.suffix == '.json':
                with open(file_path_obj, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"读取文件内容失败: {e}")
            return None
    
    def get_file_path(self, file_type: str, file_name: str) -> Optional[Path]:
        """获取文件路径"""
        if file_type == "raw":
            return self.project_dir / "raw" / file_name
        elif file_type == "clip":
            return self.project_dir / "output" / "clips" / file_name
        elif file_type == "collection":
            return self.project_dir / "output" / "collections" / file_name
        else:
            return None
    
    def cleanup_temp_files(self):
        """清理临时文件"""
        temp_dir = self.data_dir / "temp"
        if temp_dir.exists():
            for temp_file in temp_dir.iterdir():
                if temp_file.is_file():
                    temp_file.unlink()
                    logger.info(f"清理临时文件: {temp_file}")
    
    def cleanup_old_files(self, project_id: str, keep_days: int = 30):
        """清理旧文件"""
        try:
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            
            project_dir = self.data_dir / "projects" / project_id
            if not project_dir.exists():
                return
            
            # 清理处理中间文件
            processing_dir = project_dir / "processing"
            if processing_dir.exists():
                for file_path in processing_dir.iterdir():
                    if file_path.is_file():
                        file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                        if file_time < cutoff_date:
                            file_path.unlink()
                            logger.info(f"清理旧文件: {file_path}")
            
            logger.info(f"项目 {project_id} 旧文件清理完成")
            
        except Exception as e:
            logger.error(f"清理旧文件失败: {e}")
    
    def get_project_storage_info(self) -> Dict[str, Any]:
        """获取项目存储信息"""
        try:
            total_size = 0
            file_count = 0
            
            for file_path in self.project_dir.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    file_count += 1
            
            return {
                "project_id": self.project_id,
                "total_size": total_size,
                "file_count": file_count,
                "project_dir": str(self.project_dir)
            }
            
        except Exception as e:
            logger.error(f"获取存储信息失败: {e}")
            return {}
