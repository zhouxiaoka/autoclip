"""
统一路径管理工具
解决项目中路径构建不一致的问题
"""

import os
from pathlib import Path
from typing import Optional

def get_project_root() -> Path:
    """
    获取项目根目录
    从backend目录向上查找，直到找到包含frontend和backend的目录
    """
    current_path = Path(__file__).parent  # backend/core/
    
    # 向上查找项目根目录
    while current_path.parent != current_path:  # 未到达根目录
        if (current_path.parent / "frontend").exists() and (current_path.parent / "backend").exists():
            return current_path.parent
        current_path = current_path.parent
    
    # 如果没找到，使用默认路径
    return Path(__file__).parent.parent.parent

def get_data_directory() -> Path:
    """获取数据目录"""
    return get_project_root() / "data"

def get_output_directory() -> Path:
    """获取输出目录"""
    return get_project_root() / "output"

def get_project_directory(project_id: str) -> Path:
    """获取项目目录"""
    return get_data_directory() / "projects" / project_id

def get_project_raw_directory(project_id: str) -> Path:
    """获取项目原始文件目录"""
    return get_project_directory(project_id) / "raw"

def get_project_output_directory(project_id: str) -> Path:
    """获取项目输出目录"""
    return get_project_directory(project_id) / "output"

def get_clips_directory() -> Path:
    """获取切片目录"""
    # 首先检查backend/output/clips目录是否存在且有文件
    backend_clips_dir = get_project_root() / "backend" / "output" / "clips"
    if backend_clips_dir.exists() and any(backend_clips_dir.iterdir()):
        return backend_clips_dir
    
    # 如果backend目录不存在或为空，使用data目录
    return get_data_directory() / "output" / "clips"

def get_collections_directory() -> Path:
    """获取合集目录"""
    # 首先检查backend/output/collections目录是否存在且有文件
    backend_collections_dir = get_project_root() / "backend" / "output" / "collections"
    if backend_collections_dir.exists() and any(backend_collections_dir.iterdir()):
        return backend_collections_dir
    
    # 如果backend目录不存在或为空，使用data目录
    return get_data_directory() / "output" / "collections"

def get_metadata_directory() -> Path:
    """获取元数据目录"""
    return get_output_directory() / "metadata"

def get_settings_file_path() -> Path:
    """获取设置文件路径"""
    return get_data_directory() / "settings.json"

def get_uploads_directory() -> Path:
    """获取上传目录"""
    return get_data_directory() / "uploads"

def get_temp_directory() -> Path:
    """获取临时目录"""
    return get_data_directory() / "temp"

def ensure_directory_exists(path: Path) -> Path:
    """确保目录存在"""
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_video_file_path(project_id: str, filename: str) -> Path:
    """获取项目视频文件路径"""
    return get_project_raw_directory(project_id) / filename

def get_srt_file_path(project_id: str, filename: str) -> Path:
    """获取项目SRT文件路径"""
    return get_project_raw_directory(project_id) / filename

def get_clip_file_path(clip_id: str, title: str) -> Path:
    """获取切片文件路径"""
    from utils.video_processor import VideoProcessor
    safe_title = VideoProcessor.sanitize_filename(title)
    return get_clips_directory() / f"{clip_id}_{safe_title}.mp4"

def get_collection_file_path(collection_title: str) -> Path:
    """获取合集文件路径"""
    from utils.video_processor import VideoProcessor
    safe_title = VideoProcessor.sanitize_filename(collection_title)
    return get_collections_directory() / f"{safe_title}.mp4"

def find_video_files(project_id: str) -> list[Path]:
    """查找项目中的所有视频文件"""
    raw_dir = get_project_raw_directory(project_id)
    if not raw_dir.exists():
        return []
    
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm']
    video_files = []
    
    for ext in video_extensions:
        video_files.extend(raw_dir.glob(f"*{ext}"))
    
    return video_files

def find_srt_files(project_id: str) -> list[Path]:
    """查找项目中的所有SRT文件"""
    raw_dir = get_project_raw_directory(project_id)
    if not raw_dir.exists():
        return []
    
    return list(raw_dir.glob("*.srt"))

def find_clip_files(clip_id: str) -> list[Path]:
    """查找切片文件"""
    clips_dir = get_clips_directory()
    if not clips_dir.exists():
        return []
    
    return list(clips_dir.glob(f"{clip_id}_*.mp4"))

def get_project_paths(project_id: str) -> dict[str, Path]:
    """获取项目的所有相关路径"""
    return {
        "project_dir": get_project_directory(project_id),
        "raw_dir": get_project_raw_directory(project_id),
        "output_dir": get_project_output_directory(project_id),
        "clips_dir": get_clips_directory(),
        "collections_dir": get_collections_directory(),
        "metadata_dir": get_metadata_directory(),
        "temp_dir": get_temp_directory()
    }

def ensure_project_directories(project_id: str) -> dict[str, Path]:
    """确保项目所有目录存在"""
    paths = get_project_paths(project_id)
    
    for key, path in paths.items():
        if key != "clips_dir" and key != "collections_dir" and key != "metadata_dir":
            # 项目特定目录
            ensure_directory_exists(path)
        else:
            # 全局目录
            ensure_directory_exists(path)
    
    return paths

def get_relative_path(absolute_path: Path, base_path: Optional[Path] = None) -> str:
    """获取相对路径"""
    if base_path is None:
        base_path = get_project_root()
    
    try:
        return str(absolute_path.relative_to(base_path))
    except ValueError:
        return str(absolute_path)

def is_safe_path(path: Path, base_path: Path) -> bool:
    """检查路径是否安全（在基础路径内）"""
    try:
        path.resolve().relative_to(base_path.resolve())
        return True
    except ValueError:
        return False

# 向后兼容的函数
def get_legacy_project_root() -> Path:
    """向后兼容的项目根目录获取函数"""
    return Path(__file__).parent.parent.parent

def get_legacy_data_directory() -> Path:
    """向后兼容的数据目录获取函数"""
    return get_legacy_project_root() / "data"

