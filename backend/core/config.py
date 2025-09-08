"""
统一配置管理
集中管理应用的所有配置项
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

class APISettings(BaseModel):
    """API配置"""
    dashscope_api_key: str = Field(default='', validation_alias=AliasChoices('API_DASHSCOPE_API_KEY'))
    model_name: str = Field(default='qwen-plus', validation_alias=AliasChoices('API_MODEL_NAME'))
    max_tokens: int = Field(default=4096, validation_alias=AliasChoices('API_MAX_TOKENS'))
    timeout: int = Field(default=30, validation_alias=AliasChoices('API_TIMEOUT'))

class DatabaseSettings(BaseModel):
    """数据库配置"""
    url: str = Field(default='sqlite:///./data/autoclip.db', validation_alias=AliasChoices('DATABASE_URL'))

class RedisSettings(BaseModel):
    """Redis配置"""
    url: str = Field(default='redis://localhost:6379/0', validation_alias=AliasChoices('REDIS_URL'))

class ProcessingSettings(BaseModel):
    """处理配置"""
    chunk_size: int = Field(default=5000, validation_alias=AliasChoices('PROCESSING_CHUNK_SIZE'))
    min_score_threshold: float = Field(default=0.7, validation_alias=AliasChoices('PROCESSING_MIN_SCORE_THRESHOLD'))
    max_clips_per_collection: int = Field(default=5, validation_alias=AliasChoices('PROCESSING_MAX_CLIPS_PER_COLLECTION'))
    max_retries: int = Field(default=3, validation_alias=AliasChoices('PROCESSING_MAX_RETRIES'))

class LoggingSettings(BaseModel):
    """日志配置"""
    level: str = Field(default='INFO', validation_alias=AliasChoices('LOG_LEVEL'))
    fmt: str = Field(default='%(asctime)s - %(name)s - %(levelname)s - %(message)s', validation_alias=AliasChoices('LOG_FORMAT'))
    file: str = Field(default='backend.log', validation_alias=AliasChoices('LOG_FILE'))

class Settings(BaseSettings):
    """应用设置"""
    # 允许 .env + 忽略未声明的键，避免"Extra inputs are not permitted"
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    environment: str = Field(default='development', validation_alias=AliasChoices('ENVIRONMENT'))
    debug: bool = Field(default=True, validation_alias=AliasChoices('DEBUG'))
    encryption_key: str = Field(default='', validation_alias=AliasChoices('ENCRYPTION_KEY'))

    # 直接定义字段，不使用嵌套的BaseModel
    database_url: str = Field(default='sqlite:///./data/autoclip.db', validation_alias=AliasChoices('DATABASE_URL'))
    redis_url: str = Field(default='redis://localhost:6379/0', validation_alias=AliasChoices('REDIS_URL'))
    api_dashscope_api_key: str = Field(default='', validation_alias=AliasChoices('API_DASHSCOPE_API_KEY'))
    api_model_name: str = Field(default='qwen-plus', validation_alias=AliasChoices('API_MODEL_NAME'))
    api_max_tokens: int = Field(default=4096, validation_alias=AliasChoices('API_MAX_TOKENS'))
    api_timeout: int = Field(default=30, validation_alias=AliasChoices('API_TIMEOUT'))
    processing_chunk_size: int = Field(default=5000, validation_alias=AliasChoices('PROCESSING_CHUNK_SIZE'))
    processing_min_score_threshold: float = Field(default=0.7, validation_alias=AliasChoices('PROCESSING_MIN_SCORE_THRESHOLD'))
    processing_max_clips_per_collection: int = Field(default=5, validation_alias=AliasChoices('PROCESSING_MAX_CLIPS_PER_COLLECTION'))
    processing_max_retries: int = Field(default=3, validation_alias=AliasChoices('PROCESSING_MAX_RETRIES'))
    log_level: str = Field(default='INFO', validation_alias=AliasChoices('LOG_LEVEL'))
    log_format: str = Field(default='%(asctime)s - %(name)s - %(levelname)s - %(message)s', validation_alias=AliasChoices('LOG_FORMAT'))
    log_file: str = Field(default='backend.log', validation_alias=AliasChoices('LOG_FILE'))

# 全局配置实例
settings = Settings()

def get_project_root() -> Path:
    """获取项目根目录"""
    # 使用新的路径工具
    from ..core.path_utils import get_project_root as get_root
    return get_root()

def get_data_directory() -> Path:
    """获取数据目录"""
    project_root = get_project_root()
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir

def get_uploads_directory() -> Path:
    """获取上传文件目录"""
    data_dir = get_data_directory()
    uploads_dir = data_dir / "uploads"
    uploads_dir.mkdir(exist_ok=True)
    return uploads_dir

def get_temp_directory() -> Path:
    """获取临时文件目录"""
    data_dir = get_data_directory()
    temp_dir = data_dir / "temp"
    temp_dir.mkdir(exist_ok=True)
    return temp_dir

def get_output_directory() -> Path:
    """获取输出文件目录"""
    data_dir = get_data_directory()
    output_dir = data_dir / "output"
    output_dir.mkdir(exist_ok=True)
    return output_dir

def get_database_url() -> str:
    """获取数据库URL"""
    return settings.database_url

def get_redis_url() -> str:
    """获取Redis URL"""
    return settings.redis_url

def get_api_key() -> Optional[str]:
    """获取API密钥"""
    return settings.api_dashscope_api_key if settings.api_dashscope_api_key else None

def get_model_config() -> Dict[str, Any]:
    """获取模型配置"""
    return {
        "model_name": settings.api_model_name,
        "max_tokens": settings.api_max_tokens,
        "timeout": settings.api_timeout
    }

def get_processing_config() -> Dict[str, Any]:
    """获取处理配置"""
    return {
        "chunk_size": settings.processing_chunk_size,
        "min_score_threshold": settings.processing_min_score_threshold,
        "max_clips_per_collection": settings.processing_max_clips_per_collection,
        "max_retries": settings.processing_max_retries
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