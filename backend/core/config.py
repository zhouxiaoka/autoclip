"""
统一配置管理
集中管理应用的所有配置项
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings
from pydantic import Field

class DatabaseConfig(BaseSettings):
    """数据库配置"""
    url: str = Field(default="", description="数据库连接URL")
    
    class Config:
        env_prefix = "DATABASE_"

class RedisConfig(BaseSettings):
    """Redis配置"""
    url: str = Field(default="redis://localhost:6379/0", description="Redis连接URL")
    
    class Config:
        env_prefix = "REDIS_"

class APIConfig(BaseSettings):
    """API配置"""
    dashscope_api_key: Optional[str] = Field(default=None, description="DashScope API密钥")
    model_name: str = Field(default="qwen-plus", description="使用的模型名称")
    max_tokens: int = Field(default=4096, description="最大token数")
    timeout: int = Field(default=30, description="API超时时间")
    
    class Config:
        env_prefix = "API_"

class ProcessingConfig(BaseSettings):
    """处理配置"""
    chunk_size: int = Field(default=5000, description="文本分块大小")
    min_score_threshold: float = Field(default=0.7, description="最小评分阈值")
    max_clips_per_collection: int = Field(default=5, description="每个合集最大切片数")
    max_retries: int = Field(default=3, description="最大重试次数")
    
    class Config:
        env_prefix = "PROCESSING_"

class PathConfig(BaseSettings):
    """路径配置"""
    project_root: Optional[Path] = Field(default=None, description="项目根目录")
    data_dir: Optional[Path] = Field(default=None, description="数据目录")
    uploads_dir: Optional[Path] = Field(default=None, description="上传文件目录")
    temp_dir: Optional[Path] = Field(default=None, description="临时文件目录")
    output_dir: Optional[Path] = Field(default=None, description="输出文件目录")
    
    class Config:
        env_prefix = "PATH_"

class LoggingConfig(BaseSettings):
    """日志配置"""
    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="日志格式")
    file: Optional[str] = Field(default="backend.log", description="日志文件")
    
    class Config:
        env_prefix = "LOG_"

class Settings(BaseSettings):
    """应用设置"""
    
    # 环境配置
    environment: str = Field(default="development", description="运行环境")
    debug: bool = Field(default=True, description="调试模式")
    
    # 日志配置字段（直接映射.env中的字段）
    log_level: str = Field(default="INFO", description="日志级别")
    log_format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="日志格式")
    log_file: str = Field(default="backend.log", description="日志文件")
    
    # 子配置
    database: DatabaseConfig = DatabaseConfig()
    redis: RedisConfig = RedisConfig()
    api: APIConfig = APIConfig()
    processing: ProcessingConfig = ProcessingConfig()
    paths: PathConfig = PathConfig()
    logging: LoggingConfig = LoggingConfig()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # 忽略额外字段

# 全局配置实例
settings = Settings()

def get_project_root() -> Path:
    """获取项目根目录"""
    if settings.paths.project_root:
        return settings.paths.project_root
    
    # 使用新的路径工具
    from core.path_utils import get_project_root as get_root
    return get_root()

def get_data_directory() -> Path:
    """获取数据目录"""
    if settings.paths.data_dir:
        return settings.paths.data_dir
    
    project_root = get_project_root()
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir

def get_uploads_directory() -> Path:
    """获取上传文件目录"""
    if settings.paths.uploads_dir:
        return settings.paths.uploads_dir
    
    data_dir = get_data_directory()
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    return uploads_dir

def get_temp_directory() -> Path:
    """获取临时文件目录"""
    if settings.paths.temp_dir:
        return settings.paths.temp_dir
    
    data_dir = get_data_directory()
    temp_dir = data_dir / "temp"
    temp_dir.mkdir(exist_ok=True)
    return temp_dir

def get_output_directory() -> Path:
    """获取输出文件目录"""
    if settings.paths.output_dir:
        return settings.paths.output_dir
    
    data_dir = get_data_directory()
    output_dir = data_dir / "output"
    output_dir.mkdir(exist_ok=True)
    return output_dir

def get_database_url() -> str:
    """获取数据库URL"""
    if settings.database.url:
        return settings.database.url
    
    # 默认使用项目根目录下的data目录
    data_dir = get_data_directory()
    database_path = data_dir / "autoclip.db"
    return f"sqlite:///{database_path}"

def get_redis_url() -> str:
    """获取Redis URL"""
    return settings.redis.url

def get_api_key() -> Optional[str]:
    """获取API密钥"""
    # 首先尝试从环境变量获取
    api_key = settings.api.dashscope_api_key
    if api_key:
        return api_key
    
    # 如果环境变量中没有，尝试从settings.json文件读取
    try:
        import json
        from pathlib import Path
        
        from core.path_utils import get_settings_file_path
        settings_file = get_settings_file_path()
        if settings_file.exists():
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)
                if settings_data.get("dashscope_api_key"):
                    return settings_data["dashscope_api_key"]
    except Exception as e:
        print(f"读取settings.json文件失败: {e}")
    
    return None

def get_model_config() -> Dict[str, Any]:
    """获取模型配置"""
    return {
        "model_name": settings.api.model_name,
        "max_tokens": settings.api.max_tokens,
        "timeout": settings.api.timeout
    }

def get_processing_config() -> Dict[str, Any]:
    """获取处理配置"""
    return {
        "chunk_size": settings.processing.chunk_size,
        "min_score_threshold": settings.processing.min_score_threshold,
        "max_clips_per_collection": settings.processing.max_clips_per_collection,
        "max_retries": settings.processing.max_retries
    }

def get_logging_config() -> Dict[str, Any]:
    """获取日志配置"""
    return {
        "level": settings.log_level,
        "format": settings.log_format,
        "file": settings.log_file
    }

# 初始化路径配置
def init_paths():
    """初始化路径配置"""
    project_root = get_project_root()
    data_dir = get_data_directory()
    uploads_dir = get_uploads_directory()
    temp_dir = get_temp_directory()
    output_dir = get_output_directory()
    
    print(f"项目根目录: {project_root}")
    print(f"数据目录: {data_dir}")
    print(f"上传目录: {uploads_dir}")
    print(f"临时目录: {temp_dir}")
    print(f"输出目录: {output_dir}")

if __name__ == "__main__":
    # 测试配置加载
    init_paths()
    print(f"数据库URL: {get_database_url()}")
    print(f"Redis URL: {get_redis_url()}")
    print(f"API配置: {get_model_config()}")
    print(f"处理配置: {get_processing_config()}") 