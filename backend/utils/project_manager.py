"""
项目管理工具
"""
import json
import logging
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime

# 修复导入问题
try:
    from ..core.shared_config import config_manager
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    from pathlib import Path
    backend_path = Path(__file__).parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from ..core.shared_config import config_manager

logger = logging.getLogger(__name__)

class ProjectManager:
    """项目数据管理器"""
    
    def __init__(self):
        self.config = config_manager
    
    def create_project(self, project_name: Optional[str] = None) -> str:
        """
        创建新项目
        
        Args:
            project_name: 项目名称（可选）
            
        Returns:
            项目ID
        """
        project_id = str(uuid.uuid4())
        project_name = project_name or f"project_{project_id[:8]}"
        
        # 确保项目目录结构存在
        self.config.ensure_project_directories(project_id)
        
        # 创建项目元数据
        project_metadata = {
            "project_id": project_id,
            "project_name": project_name,
            "created_at": datetime.now().isoformat(),
            "status": "created",
            "current_step": 0,
            "total_steps": 6,
            "error_message": None,
            "file_info": {
                "video_file": None,
                "srt_file": None,
                "txt_file": None
            }
        }
        
        # 保存项目元数据
        self._save_project_metadata(project_id, project_metadata)
        
        logger.info(f"创建项目: {project_id} ({project_name})")
        return project_id
    
    def get_project_paths(self, project_id: str) -> Dict[str, Path]:
        """
        获取项目路径配置
        
        Args:
            project_id: 项目ID
            
        Returns:
            项目路径字典
        """
        return self.config.get_project_paths(project_id)
    
    def validate_project_exists(self, project_id: str) -> bool:
        """
        验证项目是否存在
        
        Args:
            project_id: 项目ID
            
        Returns:
            项目是否存在
        """
        paths = self.get_project_paths(project_id)
        return paths["project_base"].exists()
    
    def get_project_metadata(self, project_id: str) -> Dict[str, Any]:
        """
        获取项目元数据
        
        Args:
            project_id: 项目ID
            
        Returns:
            项目元数据
        """
        if not self.validate_project_exists(project_id):
            raise FileIOError(f"项目不存在: {project_id}")
        
        metadata_file = self.get_project_paths(project_id)["metadata_dir"] / "project_metadata.json"
        
        if not metadata_file.exists():
            # 如果元数据文件不存在，创建默认元数据
            default_metadata = {
                "project_id": project_id,
                "project_name": f"project_{project_id[:8]}",
                "created_at": datetime.now().isoformat(),
                "status": "unknown",
                "current_step": 0,
                "total_steps": 6,
                "error_message": None,
                "file_info": {
                    "video_file": None,
                    "srt_file": None,
                    "txt_file": None
                }
            }
            self._save_project_metadata(project_id, default_metadata)
            return default_metadata
        
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise FileIOError(f"读取项目元数据失败: {e}")
    
    def update_project_metadata(self, project_id: str, updates: Dict[str, Any]):
        """
        更新项目元数据
        
        Args:
            project_id: 项目ID
            updates: 要更新的字段
        """
        metadata = self.get_project_metadata(project_id)
        metadata.update(updates)
        metadata["updated_at"] = datetime.now().isoformat()
        
        self._save_project_metadata(project_id, metadata)
    
    def _save_project_metadata(self, project_id: str, metadata: Dict[str, Any]) -> None:
        """保存项目元数据"""
        paths = self.get_project_paths(project_id)
        metadata_dir = paths["metadata_dir"]
        metadata_file = metadata_dir / "project_metadata.json"
        
        try:
            # 确保metadata目录存在
            metadata_dir.mkdir(parents=True, exist_ok=True)
            
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise FileIOError(f"保存项目元数据失败: {e}")
    
    def save_input_file(self, project_id: str, file_path: Path, file_type: str) -> str:
        """
        保存输入文件到项目目录
        
        Args:
            project_id: 项目ID
            file_path: 源文件路径
            file_type: 文件类型 (video, srt, txt)
            
        Returns:
            保存后的文件路径
        """
        if not self.validate_project_exists(project_id):
            raise FileIOError(f"项目不存在: {project_id}")
        
        if not file_path.exists():
            raise FileIOError(f"源文件不存在: {file_path}")
        
        paths = self.get_project_paths(project_id)
        input_dir = paths["input_dir"]
        
        # 确定目标文件名
        if file_type == "video":
            target_name = "input.mp4"
        elif file_type == "srt":
            target_name = "input.srt"
        elif file_type == "txt":
            target_name = "input.txt"
        else:
            raise ValidationError(f"不支持的文件类型: {file_type}")
        
        target_path = input_dir / target_name
        
        try:
            # 复制文件
            shutil.copy2(file_path, target_path)
            
            # 更新项目元数据
            metadata = self.get_project_metadata(project_id)
            metadata["file_info"][f"{file_type}_file"] = str(target_path)
            self._save_project_metadata(project_id, metadata)
            
            logger.info(f"文件已保存到项目 {project_id}: {target_path}")
            return str(target_path)
            
        except Exception as e:
            raise FileIOError(f"保存文件失败: {e}")
    
    def get_input_files(self, project_id: str) -> Dict[str, Optional[Path]]:
        """
        获取项目输入文件
        
        Args:
            project_id: 项目ID
            
        Returns:
            输入文件路径字典
        """
        if not self.validate_project_exists(project_id):
            raise FileIOError(f"项目不存在: {project_id}")
        
        paths = self.get_project_paths(project_id)
        project_base = paths["project_base"]
        input_dir = paths["input_dir"]
        
        # 检查两个可能的位置：input子目录和项目根目录
        file_names = ["input.mp4", "input.srt", "input.txt"]
        file_keys = ["video_file", "srt_file", "txt_file"]
        
        files = {}
        for key, name in zip(file_keys, file_names):
            # 优先检查input子目录
            input_path = input_dir / name
            if input_path.exists():
                files[key] = input_path
            else:
                # 检查项目根目录
                root_path = project_base / name
                if root_path.exists():
                    files[key] = root_path
                else:
                    files[key] = None
        
        return files
    
    def validate_input_files(self, project_id: str) -> Dict[str, bool]:
        """
        验证项目输入文件
        
        Args:
            project_id: 项目ID
            
        Returns:
            文件验证结果
        """
        files = self.get_input_files(project_id)
        
        validation = {
            "has_video": files["video_file"] is not None,
            "has_srt": files["srt_file"] is not None,
            "has_txt": files["txt_file"] is not None,
            "can_process": files["video_file"] is not None and files["srt_file"] is not None
        }
        
        return validation
    
    def save_processing_result(self, project_id: str, step: int, result: Dict[str, Any]):
        """
        保存处理结果
        
        Args:
            project_id: 项目ID
            step: 处理步骤
            result: 处理结果
        """
        if not self.validate_project_exists(project_id):
            raise FileIOError(f"项目不存在: {project_id}")
        
        paths = self.get_project_paths(project_id)
        metadata_dir = paths["metadata_dir"]
        
        # 确保metadata目录存在
        metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存步骤结果
        step_file = metadata_dir / f"step{step}_result.json"
        
        try:
            with open(step_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            # 更新项目状态
            self.update_project_metadata(project_id, {
                "current_step": step,
                "status": "processing" if step < 6 else "completed"
            })
            
            logger.info(f"步骤 {step} 结果已保存到项目 {project_id}")
            
        except Exception as e:
            raise FileIOError(f"保存处理结果失败: {e}")
    
    def get_processing_result(self, project_id: str, step: int) -> Optional[Dict[str, Any]]:
        """
        获取处理结果
        
        Args:
            project_id: 项目ID
            step: 处理步骤
            
        Returns:
            处理结果，如果不存在则返回None
        """
        if not self.validate_project_exists(project_id):
            raise FileIOError(f"项目不存在: {project_id}")
        
        paths = self.get_project_paths(project_id)
        metadata_dir = paths["metadata_dir"]
        step_file = metadata_dir / f"step{step}_result.json"
        
        if not step_file.exists():
            return None
        
        try:
            with open(step_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise FileIOError(f"读取处理结果失败: {e}")
    
    def save_clip(self, project_id: str, clip_data: Dict[str, Any], clip_index: int):
        """
        保存视频切片信息
        
        Args:
            project_id: 项目ID
            clip_data: 切片数据
            clip_index: 切片索引
        """
        if not self.validate_project_exists(project_id):
            raise FileIOError(f"项目不存在: {project_id}")
        
        paths = self.get_project_paths(project_id)
        metadata_dir = paths["metadata_dir"]
        
        # 确保metadata目录存在
        metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # 读取现有切片数据
        clips_file = metadata_dir / "clips_metadata.json"
        clips_data = []
        
        if clips_file.exists():
            try:
                with open(clips_file, 'r', encoding='utf-8') as f:
                    clips_data = json.load(f)
            except Exception:
                clips_data = []
        
        # 添加新切片
        clip_data["clip_index"] = clip_index
        clip_data["created_at"] = datetime.now().isoformat()
        
        # 确保不重复添加
        existing_indices = [clip["clip_index"] for clip in clips_data]
        if clip_index in existing_indices:
            # 更新现有切片
            for i, clip in enumerate(clips_data):
                if clip["clip_index"] == clip_index:
                    clips_data[i] = clip_data
                    break
        else:
            # 添加新切片
            clips_data.append(clip_data)
        
        # 保存切片数据
        try:
            with open(clips_file, 'w', encoding='utf-8') as f:
                json.dump(clips_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"切片 {clip_index} 已保存到项目 {project_id}")
            
        except Exception as e:
            raise FileIOError(f"保存切片数据失败: {e}")
    
    def get_clips(self, project_id: str) -> List[Dict[str, Any]]:
        """
        获取项目所有切片
        
        Args:
            project_id: 项目ID
            
        Returns:
            切片列表
        """
        if not self.validate_project_exists(project_id):
            raise FileIOError(f"项目不存在: {project_id}")
        
        paths = self.get_project_paths(project_id)
        metadata_dir = paths["metadata_dir"]
        clips_file = metadata_dir / "clips_metadata.json"
        
        if not clips_file.exists():
            return []
        
        try:
            with open(clips_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise FileIOError(f"读取切片数据失败: {e}")
    
    def save_collection(self, project_id: str, collection_data: Dict[str, Any]):
        """
        保存合集信息
        
        Args:
            project_id: 项目ID
            collection_data: 合集数据
        """
        if not self.validate_project_exists(project_id):
            raise FileIOError(f"项目不存在: {project_id}")
        
        paths = self.get_project_paths(project_id)
        metadata_dir = paths["metadata_dir"]
        
        # 确保metadata目录存在
        metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # 读取现有合集数据
        collections_file = metadata_dir / "collections_metadata.json"
        collections_data = []
        
        if collections_file.exists():
            try:
                with open(collections_file, 'r', encoding='utf-8') as f:
                    collections_data = json.load(f)
            except Exception:
                collections_data = []
        
        # 添加新合集
        collection_data["created_at"] = datetime.now().isoformat()
        collections_data.append(collection_data)
        
        # 保存合集数据
        try:
            with open(collections_file, 'w', encoding='utf-8') as f:
                json.dump(collections_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"合集已保存到项目 {project_id}")
            
        except Exception as e:
            raise FileIOError(f"保存合集数据失败: {e}")
    
    def get_collections(self, project_id: str) -> List[Dict[str, Any]]:
        """
        获取项目所有合集
        
        Args:
            project_id: 项目ID
            
        Returns:
            合集列表
        """
        if not self.validate_project_exists(project_id):
            raise FileIOError(f"项目不存在: {project_id}")
        
        paths = self.get_project_paths(project_id)
        metadata_dir = paths["metadata_dir"]
        collections_file = metadata_dir / "collections_metadata.json"
        
        if not collections_file.exists():
            return []
        
        try:
            with open(collections_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            raise FileIOError(f"读取合集数据失败: {e}")
    
    def list_projects(self) -> List[Dict[str, Any]]:
        """
        列出所有项目
        
        Returns:
            项目列表
        """
        projects = []
        uploads_dir = Path(self.config.settings.uploads_dir)
        
        if not uploads_dir.exists():
            return projects
        
        for project_dir in uploads_dir.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                try:
                    metadata = self.get_project_metadata(project_dir.name)
                    projects.append(metadata)
                except Exception as e:
                    logger.warning(f"读取项目 {project_dir.name} 元数据失败: {e}")
        
        # 按创建时间排序
        projects.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return projects
    
    def delete_project(self, project_id: str) -> bool:
        """
        删除项目
        
        Args:
            project_id: 项目ID
            
        Returns:
            是否删除成功
        """
        if not self.validate_project_exists(project_id):
            logger.warning(f"项目不存在: {project_id}")
            return False
        
        paths = self.get_project_paths(project_id)
        project_base = paths["project_base"]
        
        try:
            shutil.rmtree(project_base)
            logger.info(f"项目已删除: {project_id}")
            return True
        except Exception as e:
            logger.error(f"删除项目失败: {e}")
            return False
    
    def get_project_summary(self, project_id: str) -> Dict[str, Any]:
        """
        获取项目摘要信息
        
        Args:
            project_id: 项目ID
            
        Returns:
            项目摘要
        """
        if not self.validate_project_exists(project_id):
            raise FileIOError(f"项目不存在: {project_id}")
        
        metadata = self.get_project_metadata(project_id)
        validation = self.validate_input_files(project_id)
        clips = self.get_clips(project_id)
        collections = self.get_collections(project_id)
        
        return {
            "project_info": metadata,
            "file_validation": validation,
            "clips_count": len(clips),
            "collections_count": len(collections),
            "processing_progress": {
                "current_step": metadata.get("current_step", 0),
                "total_steps": metadata.get("total_steps", 6),
                "progress_percentage": (metadata.get("current_step", 0) / metadata.get("total_steps", 6)) * 100
            }
        }

# 全局项目管理器实例
project_manager = ProjectManager()