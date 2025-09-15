"""
统一配置管理系统
整合所有配置源，提供统一的配置访问接口
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class DatabaseConfig(BaseModel):
    """数据库配置"""
    url: str = Field(default="sqlite:///./data/autoclip.db", description="数据库连接URL")
    echo: bool = Field(default=False, description="是否打印SQL语句")
    pool_size: int = Field(default=5, description="连接池大小")
    max_overflow: int = Field(default=10, description="最大溢出连接数")


class RedisConfig(BaseModel):
    """Redis配置"""
    url: str = Field(default="redis://localhost:6379/0", description="Redis连接URL")
    max_connections: int = Field(default=10, description="最大连接数")
    socket_timeout: int = Field(default=5, description="Socket超时时间")


class APIConfig(BaseModel):
    """API配置"""
    dashscope_api_key: str = Field(default="", description="DashScope API密钥")
    model_name: str = Field(default="qwen-plus", description="模型名称")
    max_tokens: int = Field(default=4096, description="最大token数")
    timeout: int = Field(default=30, description="API超时时间")
    max_retries: int = Field(default=3, description="最大重试次数")
    
    @validator('max_tokens')
    def validate_max_tokens(cls, v):
        if v <= 0:
            raise ValueError('max_tokens必须大于0')
        return v
    
    @validator('timeout')
    def validate_timeout(cls, v):
        if v <= 0:
            raise ValueError('timeout必须大于0')
        return v


class ProcessingConfig(BaseModel):
    """处理配置"""
    chunk_size: int = Field(default=5000, description="文本分块大小")
    min_score_threshold: float = Field(default=0.7, description="最小评分阈值")
    max_clips_per_collection: int = Field(default=5, description="每个合集最大切片数")
    max_retries: int = Field(default=3, description="最大重试次数")
    timeout_seconds: int = Field(default=30, description="处理超时时间")
    
    # 话题提取控制参数
    min_topic_duration_minutes: int = Field(default=2, description="最小话题时长(分钟)")
    max_topic_duration_minutes: int = Field(default=12, description="最大话题时长(分钟)")
    target_topic_duration_minutes: int = Field(default=5, description="目标话题时长(分钟)")
    min_topics_per_chunk: int = Field(default=3, description="每个分块最小话题数")
    max_topics_per_chunk: int = Field(default=8, description="每个分块最大话题数")
    
    @validator('min_score_threshold')
    def validate_score_threshold(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('评分阈值必须在0-1之间')
        return v
    
    @validator('chunk_size')
    def validate_chunk_size(cls, v):
        if v <= 0:
            raise ValueError('分块大小必须大于0')
        return v


class SpeechRecognitionConfig(BaseModel):
    """语音识别配置"""
    method: str = Field(default="whisper_local", description="识别方法")
    language: str = Field(default="auto", description="识别语言")
    model: str = Field(default="base", description="模型大小")
    timeout: int = Field(default=1000, description="识别超时时间")


class BilibiliConfig(BaseModel):
    """B站配置"""
    auto_upload: bool = Field(default=False, description="是否自动上传")
    default_tid: int = Field(default=21, description="默认分区ID")
    max_concurrent_uploads: int = Field(default=3, description="最大并发上传数")
    upload_timeout_minutes: int = Field(default=30, description="上传超时时间(分钟)")
    auto_generate_tags: bool = Field(default=True, description="是否自动生成标签")
    tag_limit: int = Field(default=12, description="标签数量限制")


class LoggingConfig(BaseModel):
    """日志配置"""
    level: str = Field(default="INFO", description="日志级别")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s", description="日志格式")
    file: str = Field(default="backend.log", description="日志文件")
    max_size: int = Field(default=10 * 1024 * 1024, description="日志文件最大大小(字节)")
    backup_count: int = Field(default=5, description="日志文件备份数量")


class PathConfig(BaseModel):
    """路径配置"""
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)
    data_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "data")
    uploads_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "data" / "uploads")
    output_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "data" / "output")
    temp_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "data" / "temp")
    prompt_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "prompt")
    
    def __init__(self, **data):
        super().__init__(**data)
        # 确保所有目录存在
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, Path):
                field_value.mkdir(parents=True, exist_ok=True)


class UnifiedConfig(BaseSettings):
    """统一配置类"""
    
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        env_nested_delimiter='__'
    )
    
    # 环境配置
    environment: str = Field(default="development", description="运行环境")
    debug: bool = Field(default=True, description="调试模式")
    encryption_key: str = Field(default="", description="加密密钥")
    
    # 子配置
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    speech_recognition: SpeechRecognitionConfig = Field(default_factory=SpeechRecognitionConfig)
    bilibili: BilibiliConfig = Field(default_factory=BilibiliConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    paths: PathConfig = Field(default_factory=PathConfig)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_from_files()
        self._setup_environment()
    
    def _load_from_files(self):
        """从配置文件加载设置"""
        # 从data/settings.json加载
        settings_file = self.paths.data_dir / "settings.json"
        if settings_file.exists():
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    file_settings = json.load(f)
                    self._merge_settings(file_settings)
            except Exception as e:
                logger.warning(f"加载配置文件失败: {e}")
        
        # 从环境变量加载
        self._load_from_env()
    
    def _merge_settings(self, settings: Dict[str, Any]):
        """合并设置到配置对象"""
        for key, value in settings.items():
            if hasattr(self, key):
                if isinstance(getattr(self, key), BaseModel):
                    # 如果是子配置对象，递归合并
                    sub_config = getattr(self, key)
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if hasattr(sub_config, sub_key):
                                setattr(sub_config, sub_key, sub_value)
                else:
                    setattr(self, key, value)
    
    def _load_from_env(self):
        """从环境变量加载配置"""
        # 数据库配置
        if os.getenv("DATABASE_URL"):
            self.database.url = os.getenv("DATABASE_URL")
        
        # Redis配置
        if os.getenv("REDIS_URL"):
            self.redis.url = os.getenv("REDIS_URL")
        
        # API配置
        if os.getenv("DASHSCOPE_API_KEY"):
            self.api.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        if os.getenv("API_MODEL_NAME"):
            self.api.model_name = os.getenv("API_MODEL_NAME")
        
        # 处理配置
        if os.getenv("PROCESSING_CHUNK_SIZE"):
            self.processing.chunk_size = int(os.getenv("PROCESSING_CHUNK_SIZE"))
        if os.getenv("PROCESSING_MIN_SCORE_THRESHOLD"):
            self.processing.min_score_threshold = float(os.getenv("PROCESSING_MIN_SCORE_THRESHOLD"))
        
        # 日志配置
        if os.getenv("LOG_LEVEL"):
            self.logging.level = os.getenv("LOG_LEVEL")
        if os.getenv("LOG_FILE"):
            self.logging.file = os.getenv("LOG_FILE")
    
    def _setup_environment(self):
        """设置环境变量"""
        # 设置API密钥到环境变量
        if self.api.dashscope_api_key:
            os.environ["DASHSCOPE_API_KEY"] = self.api.dashscope_api_key
        
        # 设置数据库URL
        os.environ["DATABASE_URL"] = self.database.url
        
        # 设置Redis URL
        os.environ["REDIS_URL"] = self.redis.url
    
    def save_to_file(self, file_path: Optional[Path] = None):
        """保存配置到文件"""
        if file_path is None:
            file_path = self.paths.data_dir / "settings.json"
        
        try:
            # 创建配置字典，排除敏感信息
            config_dict = self._to_safe_dict()
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
            
            logger.info(f"配置已保存到: {file_path}")
            
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            raise
    
    def _to_safe_dict(self) -> Dict[str, Any]:
        """转换为安全的字典格式（隐藏敏感信息）"""
        config_dict = {}
        
        for key, value in self.__dict__.items():
            if key.startswith('_'):
                continue
            
            if isinstance(value, BaseModel):
                config_dict[key] = value.dict()
            else:
                config_dict[key] = value
        
        # 隐藏敏感信息
        if 'api' in config_dict and 'dashscope_api_key' in config_dict['api']:
            api_key = config_dict['api']['dashscope_api_key']
            if api_key:
                config_dict['api']['dashscope_api_key'] = api_key[:8] + "..." if len(api_key) > 8 else "***"
        
        return config_dict
    
    def update_config(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                if isinstance(getattr(self, key), BaseModel):
                    # 如果是子配置对象，递归更新
                    sub_config = getattr(self, key)
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            if hasattr(sub_config, sub_key):
                                setattr(sub_config, sub_key, sub_value)
                else:
                    setattr(self, key, value)
        
        # 重新设置环境变量
        self._setup_environment()
        
        # 保存到文件
        self.save_to_file()
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        return {
            "environment": self.environment,
            "debug": self.debug,
            "database": {
                "url": self.database.url,
                "echo": self.database.echo
            },
            "redis": {
                "url": self.redis.url
            },
            "api": {
                "model_name": self.api.model_name,
                "max_tokens": self.api.max_tokens,
                "timeout": self.api.timeout,
                "has_api_key": bool(self.api.dashscope_api_key)
            },
            "processing": {
                "chunk_size": self.processing.chunk_size,
                "min_score_threshold": self.processing.min_score_threshold,
                "max_clips_per_collection": self.processing.max_clips_per_collection
            },
            "speech_recognition": {
                "method": self.speech_recognition.method,
                "language": self.speech_recognition.language,
                "model": self.speech_recognition.model
            },
            "bilibili": {
                "auto_upload": self.bilibili.auto_upload,
                "default_tid": self.bilibili.default_tid,
                "max_concurrent_uploads": self.bilibili.max_concurrent_uploads
            },
            "logging": {
                "level": self.logging.level,
                "file": self.logging.file
            },
            "paths": {
                "data_dir": str(self.paths.data_dir),
                "uploads_dir": str(self.paths.uploads_dir),
                "output_dir": str(self.paths.output_dir),
                "temp_dir": str(self.paths.temp_dir)
            }
        }
    
    def validate_config(self) -> Dict[str, Any]:
        """验证配置"""
        issues = []
        
        # 验证API配置
        if not self.api.dashscope_api_key:
            issues.append("DashScope API密钥未配置")
        
        # 验证路径
        for path_name, path_value in self.paths.__dict__.items():
            if isinstance(path_value, Path) and not path_value.exists():
                issues.append(f"路径不存在: {path_name} = {path_value}")
        
        # 验证数据库连接
        if not self.database.url:
            issues.append("数据库URL未配置")
        
        # 验证Redis连接
        if not self.redis.url:
            issues.append("Redis URL未配置")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }


# 全局配置实例
config = UnifiedConfig()


# 便捷函数
def get_config() -> UnifiedConfig:
    """获取全局配置实例"""
    return config


def get_database_url() -> str:
    """获取数据库URL"""
    return config.database.url


def get_redis_url() -> str:
    """获取Redis URL"""
    return config.redis.url


def get_api_key() -> str:
    """获取API密钥"""
    return config.api.dashscope_api_key


def get_data_directory() -> Path:
    """获取数据目录"""
    return config.paths.data_dir


def get_uploads_directory() -> Path:
    """获取上传目录"""
    return config.paths.uploads_dir


def get_output_directory() -> Path:
    """获取输出目录"""
    return config.paths.output_dir


def get_temp_directory() -> Path:
    """获取临时目录"""
    return config.paths.temp_dir


def get_prompt_directory() -> Path:
    """获取提示词目录"""
    return config.paths.prompt_dir


def update_api_key(api_key: str):
    """更新API密钥"""
    config.api.dashscope_api_key = api_key
    config._setup_environment()
    config.save_to_file()


def update_processing_config(**kwargs):
    """更新处理配置"""
    config.update_config(processing=kwargs)


def update_bilibili_config(**kwargs):
    """更新B站配置"""
    config.update_config(bilibili=kwargs)
