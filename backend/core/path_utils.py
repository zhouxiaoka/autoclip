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
    data_dir = get_project_root() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir

def get_projects_directory() -> Path:
    """获取项目目录"""
    projects_dir = get_data_directory() / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    return projects_dir

def get_output_directory() -> Path:
    """获取输出目录"""
    output_dir = get_project_root() / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def get_project_directory(project_id: str) -> Path:
    """获取项目目录"""
    project_dir = get_projects_directory() / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir

def get_project_raw_directory(project_id: str) -> Path:
    """获取项目原始文件目录"""
    raw_dir = get_project_directory(project_id) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir

def get_project_output_directory(project_id: str) -> Path:
    """获取项目输出目录"""
    output_dir = get_project_directory(project_id) / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir

def get_clips_directory() -> Path:
    """获取切片目录"""
    clips_dir = get_output_directory() / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    return clips_dir

def get_collections_directory() -> Path:
    """获取合集目录"""
    collections_dir = get_output_directory() / "collections"
    collections_dir.mkdir(parents=True, exist_ok=True)
    return collections_dir

def get_metadata_directory() -> Path:
    """获取元数据目录"""
    metadata_dir = get_output_directory() / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    return metadata_dir

def get_settings_file_path() -> Path:
    """获取设置文件路径"""
    return get_data_directory() / "settings.json"

def get_uploads_directory() -> Path:
    """获取上传目录"""
    uploads_dir = get_data_directory() / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    return uploads_dir

def get_temp_directory() -> Path:
    """获取临时目录"""
    temp_dir = get_data_directory() / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir

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
    # 清理文件名，移除特殊字符
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_title = safe_title.replace(' ', '_')
    return get_clips_directory() / f"{clip_id}_{safe_title}.mp4"

def get_collection_file_path(collection_id: str, title: str) -> Path:
    """获取合集文件路径"""
    # 清理文件名，移除特殊字符
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_title = safe_title.replace(' ', '_')
    return get_collections_directory() / f"{collection_id}_{safe_title}.mp4"

def get_metadata_file_path(project_id: str) -> Path:
    """获取项目元数据文件路径"""
    return get_metadata_directory() / f"{project_id}_metadata.json"

def get_log_file_path() -> Path:
    """获取日志文件路径"""
    return get_project_root() / "backend.log"

def get_cache_directory() -> Path:
    """获取缓存目录"""
    cache_dir = get_data_directory() / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir

def get_backup_directory() -> Path:
    """获取备份目录"""
    backup_dir = get_data_directory() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir

def cleanup_temp_files(max_age_hours: int = 24):
    """清理临时文件"""
    import time
    temp_dir = get_temp_directory()
    current_time = time.time()
    
    for file_path in temp_dir.iterdir():
        if file_path.is_file():
            file_age = current_time - file_path.stat().st_mtime
            if file_age > (max_age_hours * 3600):
                try:
                    file_path.unlink()
                except Exception as e:
                    print(f"清理临时文件失败: {file_path}, 错误: {e}")

def validate_file_path(file_path: Path) -> bool:
    """验证文件路径是否安全"""
    try:
        # 检查路径是否在允许的目录内
        allowed_dirs = [
            get_data_directory(),
            get_output_directory(),
            get_project_root()
        ]
        
        file_path = file_path.resolve()
        return any(file_path.is_relative_to(allowed_dir) for allowed_dir in allowed_dirs)
    except Exception:
        return False

