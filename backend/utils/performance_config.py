"""
性能配置和优化设置
提供系统性能相关的配置和优化参数
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from enum import Enum


class PerformanceLevel(Enum):
    """性能级别"""
    LOW = "low"          # 低性能，适合资源受限环境
    MEDIUM = "medium"    # 中等性能，平衡性能和资源使用
    HIGH = "high"        # 高性能，适合资源充足环境
    CUSTOM = "custom"    # 自定义配置


class FileUploadConfig(BaseModel):
    """文件上传配置"""
    # 分片上传配置
    chunk_size: int = Field(default=2 * 1024 * 1024, description="分片大小(字节)")  # 2MB
    max_file_size: int = Field(default=2 * 1024 * 1024 * 1024, description="最大文件大小(字节)")  # 2GB
    max_concurrent_uploads: int = Field(default=3, description="最大并发上传数")
    upload_timeout: int = Field(default=1800, description="上传超时时间(秒)")  # 30分钟
    
    # 重试配置
    max_retries: int = Field(default=3, description="最大重试次数")
    retry_delay: int = Field(default=5, description="重试延迟(秒)")
    
    # 支持的格式
    supported_video_formats: list = Field(
        default=['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'],
        description="支持的视频格式"
    )
    supported_subtitle_formats: list = Field(
        default=['.srt', '.vtt', '.ass', '.ssa'],
        description="支持的字幕格式"
    )
    
    @validator('chunk_size')
    def validate_chunk_size(cls, v):
        if v <= 0 or v > 10 * 1024 * 1024:  # 最大10MB
            raise ValueError('分片大小必须在1字节到10MB之间')
        return v
    
    @validator('max_file_size')
    def validate_max_file_size(cls, v):
        if v <= 0 or v > 10 * 1024 * 1024 * 1024:  # 最大10GB
            raise ValueError('最大文件大小必须在1字节到10GB之间')
        return v


class ProcessingConfig(BaseModel):
    """处理配置"""
    # 并发控制
    max_concurrent_tasks: int = Field(default=2, description="最大并发处理任务数")
    max_concurrent_workers: int = Field(default=4, description="最大并发工作进程数")
    
    # 内存控制
    max_memory_usage: int = Field(default=4 * 1024 * 1024 * 1024, description="最大内存使用(字节)")  # 4GB
    memory_check_interval: int = Field(default=30, description="内存检查间隔(秒)")
    
    # 处理超时
    video_processing_timeout: int = Field(default=3600, description="视频处理超时(秒)")  # 1小时
    audio_processing_timeout: int = Field(default=1800, description="音频处理超时(秒)")  # 30分钟
    ai_processing_timeout: int = Field(default=300, description="AI处理超时(秒)")  # 5分钟
    
    # 批处理配置
    batch_size: int = Field(default=10, description="批处理大小")
    batch_timeout: int = Field(default=600, description="批处理超时(秒)")  # 10分钟
    
    @validator('max_concurrent_tasks')
    def validate_max_concurrent_tasks(cls, v):
        if v <= 0 or v > 10:
            raise ValueError('最大并发任务数必须在1到10之间')
        return v


class CacheConfig(BaseModel):
    """缓存配置"""
    # 缓存大小
    max_cache_size: int = Field(default=1024 * 1024 * 1024, description="最大缓存大小(字节)")  # 1GB
    cache_ttl: int = Field(default=3600, description="缓存生存时间(秒)")  # 1小时
    
    # 缓存策略
    enable_file_cache: bool = Field(default=True, description="启用文件缓存")
    enable_result_cache: bool = Field(default=True, description="启用结果缓存")
    enable_metadata_cache: bool = Field(default=True, description="启用元数据缓存")
    
    # 清理策略
    cache_cleanup_interval: int = Field(default=1800, description="缓存清理间隔(秒)")  # 30分钟
    cache_cleanup_threshold: float = Field(default=0.8, description="缓存清理阈值")  # 80%


class DatabaseConfig(BaseModel):
    """数据库配置"""
    # 连接池配置
    pool_size: int = Field(default=10, description="连接池大小")
    max_overflow: int = Field(default=20, description="最大溢出连接数")
    pool_timeout: int = Field(default=30, description="连接池超时(秒)")
    pool_recycle: int = Field(default=3600, description="连接回收时间(秒)")
    
    # 查询优化
    query_timeout: int = Field(default=30, description="查询超时(秒)")
    enable_query_cache: bool = Field(default=True, description="启用查询缓存")
    
    @validator('pool_size')
    def validate_pool_size(cls, v):
        if v <= 0 or v > 100:
            raise ValueError('连接池大小必须在1到100之间')
        return v


class PerformanceConfig(BaseModel):
    """性能配置主类"""
    level: PerformanceLevel = Field(default=PerformanceLevel.MEDIUM, description="性能级别")
    
    # 子配置
    file_upload: FileUploadConfig = Field(default_factory=FileUploadConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    
    # 全局设置
    enable_monitoring: bool = Field(default=True, description="启用性能监控")
    monitoring_interval: int = Field(default=60, description="监控间隔(秒)")
    log_performance_metrics: bool = Field(default=True, description="记录性能指标")
    
    def get_config_for_level(self, level: PerformanceLevel) -> 'PerformanceConfig':
        """根据性能级别获取配置"""
        if level == PerformanceLevel.LOW:
            return self._get_low_performance_config()
        elif level == PerformanceLevel.MEDIUM:
            return self._get_medium_performance_config()
        elif level == PerformanceLevel.HIGH:
            return self._get_high_performance_config()
        else:
            return self
    
    def _get_low_performance_config(self) -> 'PerformanceConfig':
        """低性能配置"""
        return PerformanceConfig(
            level=PerformanceLevel.LOW,
            file_upload=FileUploadConfig(
                chunk_size=1024 * 1024,  # 1MB
                max_file_size=512 * 1024 * 1024,  # 512MB
                max_concurrent_uploads=1,
                upload_timeout=900,  # 15分钟
                max_retries=2
            ),
            processing=ProcessingConfig(
                max_concurrent_tasks=1,
                max_concurrent_workers=2,
                max_memory_usage=2 * 1024 * 1024 * 1024,  # 2GB
                video_processing_timeout=1800,  # 30分钟
                audio_processing_timeout=900,  # 15分钟
                ai_processing_timeout=180  # 3分钟
            ),
            cache=CacheConfig(
                max_cache_size=256 * 1024 * 1024,  # 256MB
                cache_ttl=1800,  # 30分钟
                enable_file_cache=False,
                enable_result_cache=True,
                enable_metadata_cache=True
            ),
            database=DatabaseConfig(
                pool_size=5,
                max_overflow=10,
                enable_query_cache=False
            )
        )
    
    def _get_medium_performance_config(self) -> 'PerformanceConfig':
        """中等性能配置"""
        return PerformanceConfig(
            level=PerformanceLevel.MEDIUM,
            file_upload=FileUploadConfig(
                chunk_size=2 * 1024 * 1024,  # 2MB
                max_file_size=2 * 1024 * 1024 * 1024,  # 2GB
                max_concurrent_uploads=3,
                upload_timeout=1800,  # 30分钟
                max_retries=3
            ),
            processing=ProcessingConfig(
                max_concurrent_tasks=2,
                max_concurrent_workers=4,
                max_memory_usage=4 * 1024 * 1024 * 1024,  # 4GB
                video_processing_timeout=3600,  # 1小时
                audio_processing_timeout=1800,  # 30分钟
                ai_processing_timeout=300  # 5分钟
            ),
            cache=CacheConfig(
                max_cache_size=1024 * 1024 * 1024,  # 1GB
                cache_ttl=3600,  # 1小时
                enable_file_cache=True,
                enable_result_cache=True,
                enable_metadata_cache=True
            ),
            database=DatabaseConfig(
                pool_size=10,
                max_overflow=20,
                enable_query_cache=True
            )
        )
    
    def _get_high_performance_config(self) -> 'PerformanceConfig':
        """高性能配置"""
        return PerformanceConfig(
            level=PerformanceLevel.HIGH,
            file_upload=FileUploadConfig(
                chunk_size=4 * 1024 * 1024,  # 4MB
                max_file_size=5 * 1024 * 1024 * 1024,  # 5GB
                max_concurrent_uploads=5,
                upload_timeout=3600,  # 1小时
                max_retries=5
            ),
            processing=ProcessingConfig(
                max_concurrent_tasks=4,
                max_concurrent_workers=8,
                max_memory_usage=8 * 1024 * 1024 * 1024,  # 8GB
                video_processing_timeout=7200,  # 2小时
                audio_processing_timeout=3600,  # 1小时
                ai_processing_timeout=600  # 10分钟
            ),
            cache=CacheConfig(
                max_cache_size=2 * 1024 * 1024 * 1024,  # 2GB
                cache_ttl=7200,  # 2小时
                enable_file_cache=True,
                enable_result_cache=True,
                enable_metadata_cache=True
            ),
            database=DatabaseConfig(
                pool_size=20,
                max_overflow=40,
                enable_query_cache=True
            )
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "level": self.level.value,
            "file_upload": self.file_upload.dict(),
            "processing": self.processing.dict(),
            "cache": self.cache.dict(),
            "database": self.database.dict(),
            "enable_monitoring": self.enable_monitoring,
            "monitoring_interval": self.monitoring_interval,
            "log_performance_metrics": self.log_performance_metrics
        }


# 全局性能配置实例
performance_config = PerformanceConfig()

# 性能级别配置映射
PERFORMANCE_LEVELS = {
    PerformanceLevel.LOW: performance_config._get_low_performance_config(),
    PerformanceLevel.MEDIUM: performance_config._get_medium_performance_config(),
    PerformanceLevel.HIGH: performance_config._get_high_performance_config(),
}


def get_performance_config(level: PerformanceLevel = PerformanceLevel.MEDIUM) -> PerformanceConfig:
    """获取指定级别的性能配置"""
    return PERFORMANCE_LEVELS.get(level, performance_config._get_medium_performance_config())


def update_performance_config(config_dict: Dict[str, Any]) -> PerformanceConfig:
    """更新性能配置"""
    global performance_config
    
    # 更新配置
    if 'level' in config_dict:
        level = PerformanceLevel(config_dict['level'])
        performance_config = performance_config.get_config_for_level(level)
    
    # 更新子配置
    if 'file_upload' in config_dict:
        performance_config.file_upload = FileUploadConfig(**config_dict['file_upload'])
    
    if 'processing' in config_dict:
        performance_config.processing = ProcessingConfig(**config_dict['processing'])
    
    if 'cache' in config_dict:
        performance_config.cache = CacheConfig(**config_dict['cache'])
    
    if 'database' in config_dict:
        performance_config.database = DatabaseConfig(**config_dict['database'])
    
    # 更新全局设置
    if 'enable_monitoring' in config_dict:
        performance_config.enable_monitoring = config_dict['enable_monitoring']
    
    if 'monitoring_interval' in config_dict:
        performance_config.monitoring_interval = config_dict['monitoring_interval']
    
    if 'log_performance_metrics' in config_dict:
        performance_config.log_performance_metrics = config_dict['log_performance_metrics']
    
    return performance_config
