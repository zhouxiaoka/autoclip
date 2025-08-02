"""
配置文件 - 管理API密钥、文件路径等配置信息
支持新的配置管理系统和向后兼容
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, validator
from enum import Enum

# 视频分类枚举
class VideoCategory(str, Enum):
    DEFAULT = "default"
    KNOWLEDGE = "knowledge"
    BUSINESS = "business"
    OPINION = "opinion"
    EXPERIENCE = "experience"
    SPEECH = "speech"
    CONTENT_REVIEW = "content_review"
    ENTERTAINMENT = "entertainment"

# 视频分类配置
VIDEO_CATEGORIES_CONFIG = {
    VideoCategory.DEFAULT: {
        "name": "默认",
        "description": "通用视频内容，适用于大部分场景",
        "icon": "🎬",
        "color": "#4facfe"
    },
    VideoCategory.KNOWLEDGE: {
        "name": "知识科普",
        "description": "教育、科普、技术分享等知识性内容",
        "icon": "📚",
        "color": "#52c41a"
    },
    VideoCategory.BUSINESS: {
        "name": "商业财经",
        "description": "商业分析、财经资讯、投资理财等",
        "icon": "💼",
        "color": "#faad14"
    },
    VideoCategory.OPINION: {
        "name": "观点评论",
        "description": "观点表达、评论分析、思辨讨论等",
        "icon": "💭",
        "color": "#722ed1"
    },
    VideoCategory.EXPERIENCE: {
        "name": "经验分享",
        "description": "生活经验、技能分享、实用技巧等",
        "icon": "🌟",
        "color": "#13c2c2"
    },
    VideoCategory.SPEECH: {
        "name": "演讲脱口秀",
        "description": "演讲、脱口秀、访谈等口语表达内容",
        "icon": "🎤",
        "color": "#eb2f96"
    },
    VideoCategory.CONTENT_REVIEW: {
        "name": "内容解说",
        "description": "影视解说、游戏解说、作品分析等",
        "icon": "🎭",
        "color": "#f5222d"
    },
    VideoCategory.ENTERTAINMENT: {
        "name": "娱乐内容",
        "description": "娱乐节目、综艺、表演等轻松内容",
        "icon": "🎪",
        "color": "#fa8c16"
    }
}

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 输入文件路径
INPUT_DIR = PROJECT_ROOT / "input"
INPUT_VIDEO = INPUT_DIR / "input.mp4"
INPUT_SRT = INPUT_DIR / "input.srt"
INPUT_TXT = INPUT_DIR / "input.txt"

# 输出目录
OUTPUT_DIR = PROJECT_ROOT / "output"
CLIPS_DIR = OUTPUT_DIR / "clips"
COLLECTIONS_DIR = OUTPUT_DIR / "collections"
METADATA_DIR = OUTPUT_DIR / "metadata"

# Prompt文件路径
PROMPT_DIR = PROJECT_ROOT / "prompt"
PROMPT_FILES = {
    "outline": PROMPT_DIR / "大纲.txt",
    "timeline": PROMPT_DIR / "时间点.txt", 
    "recommendation": PROMPT_DIR / "推荐理由.txt",
    "title": PROMPT_DIR / "标题生成.txt",
    "clustering": PROMPT_DIR / "主题聚类.txt"
}

# API配置
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
MODEL_NAME = "qwen-plus"  # 通义千问模型名称

# 处理参数
CHUNK_SIZE = 5000  # 文本分块大小
MIN_SCORE_THRESHOLD = 0.7  # 最低评分阈值
MAX_CLIPS_PER_COLLECTION = 5  # 每个合集最大切片数

# 新增：话题提取控制参数
MIN_TOPIC_DURATION_MINUTES = 2  # 话题最小时长（分钟）
MAX_TOPIC_DURATION_MINUTES = 12  # 话题最大时长（分钟）
TARGET_TOPIC_DURATION_MINUTES = 5  # 话题目标时长（分钟）
MIN_TOPICS_PER_CHUNK = 3  # 每个文本块最少话题数
MAX_TOPICS_PER_CHUNK = 8  # 每个文本块最多话题数

# 确保输出目录存在
for dir_path in [CLIPS_DIR, COLLECTIONS_DIR, METADATA_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# 新的配置管理系统
class Settings(BaseModel):
    """系统设置"""
    dashscope_api_key: Optional[str] = ""
    model_name: str = "qwen-plus"
    chunk_size: int = 5000
    min_score_threshold: float = 0.7
    max_clips_per_collection: int = 5
    max_retries: int = 3
    timeout_seconds: int = 30
    # 新增话题提取控制参数
    min_topic_duration_minutes: int = 2
    max_topic_duration_minutes: int = 12
    target_topic_duration_minutes: int = 5
    min_topics_per_chunk: int = 3
    max_topics_per_chunk: int = 8
    # B站上传配置 (已移除 bilitool 相关功能)
    # bilibili_auto_upload: bool = False
    # bilibili_default_tid: int = 21  # 默认分区：日常
    # bilibili_max_concurrent_uploads: int = 3
    # bilibili_upload_timeout_minutes: int = 30
    # bilibili_auto_generate_tags: bool = True
    # bilibili_tag_limit: int = 12
    
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

@dataclass
class APIConfig:
    """API配置"""
    model_name: str = "qwen-plus"
    api_key: Optional[str] = None
    base_url: str = "https://dashscope.aliyuncs.com"
    max_tokens: int = 4096

@dataclass
class ProcessingConfig:
    """处理配置"""
    chunk_size: int = 5000
    min_score_threshold: float = 0.7
    max_clips_per_collection: int = 5
    max_retries: int = 3
    timeout_seconds: int = 30

# @dataclass
# class BilibiliConfig:
#     """B站上传配置 (已移除 bilitool 相关功能)"""
#     auto_upload: bool = False
#     default_tid: int = 21  # 默认分区：日常
#     max_concurrent_uploads: int = 3
#     upload_timeout_minutes: int = 30
#     auto_generate_tags: bool = True
#     tag_limit: int = 12

@dataclass
class PathConfig:
    """路径配置"""
    project_root: Path = field(default_factory=lambda: PROJECT_ROOT)
    data_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "data")
    uploads_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "uploads")
    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "output")
    prompt_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "prompt")
    temp_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "temp")

class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.settings = Settings()
        self._load_settings()
        self._setup_prompt_files()
    
    def _load_settings(self):
        """加载设置"""
        # 从环境变量加载
        if os.getenv("DASHSCOPE_API_KEY"):
            self.settings.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        
        # 从配置文件加载
        config_file = PROJECT_ROOT / "data" / "settings.json"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    for key, value in config_data.items():
                        if hasattr(self.settings, key):
                            setattr(self.settings, key, value)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
    
    def _setup_prompt_files(self):
        """设置提示词文件"""
        self.prompt_files = PROMPT_FILES.copy()
        
        # 确保提示词目录存在
        PROMPT_DIR.mkdir(exist_ok=True)
        
        # 创建默认提示词文件
        default_prompts = {
            "大纲.txt": "请分析以下视频内容，提取主要话题和结构：\n\n{content}",
            "时间点.txt": "请为以下话题定位具体的时间区间：\n\n{content}",
            "推荐理由.txt": "请评估以下内容的质量和推荐度：\n\n{content}",
            "标题生成.txt": "请为以下内容生成吸引人的标题：\n\n{content}",
            "主题聚类.txt": "请将以下话题按主题进行聚合：\n\n{content}"
        }
        
        for filename, content in default_prompts.items():
            file_path = PROMPT_DIR / filename
            if not file_path.exists():
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                except Exception as e:
                    print(f"创建提示词文件失败 {filename}: {e}")
    
    def get_api_config(self) -> APIConfig:
        """获取API配置"""
        return APIConfig(
            model_name=self.settings.model_name,
            api_key=self.settings.dashscope_api_key
        )
    
    def get_processing_config(self) -> ProcessingConfig:
        """获取处理配置"""
        return ProcessingConfig(
            chunk_size=self.settings.chunk_size,
            min_score_threshold=self.settings.min_score_threshold,
            max_clips_per_collection=self.settings.max_clips_per_collection,
            max_retries=self.settings.max_retries,
            timeout_seconds=self.settings.timeout_seconds
        )
    
    def get_path_config(self) -> PathConfig:
        """获取路径配置"""
        return PathConfig()
    
    # def get_bilibili_config(self) -> BilibiliConfig:
    #     """获取B站上传配置 (已移除 bilitool 相关功能)"""
    #     return BilibiliConfig(
    #         auto_upload=self.settings.bilibili_auto_upload,
    #         default_tid=self.settings.bilibili_default_tid,
    #         max_concurrent_uploads=self.settings.bilibili_max_concurrent_uploads,
    #         upload_timeout_minutes=self.settings.bilibili_upload_timeout_minutes,
    #         auto_generate_tags=self.settings.bilibili_auto_generate_tags,
    #         tag_limit=self.settings.bilibili_tag_limit
    #     )
    
    def ensure_project_directories(self, project_id: str):
        """确保项目目录结构存在"""
        paths = self.get_project_paths(project_id)
        
        for path in paths.values():
            if isinstance(path, Path):
                path.mkdir(parents=True, exist_ok=True)
    
    def get_project_paths(self, project_id: str) -> Dict[str, Path]:
        """获取项目路径配置"""
        uploads_dir = self.get_path_config().uploads_dir
        project_base = uploads_dir / project_id
        
        return {
            "project_base": project_base,
            "input_dir": project_base / "input",
            "output_dir": project_base / "output",
            "clips_dir": project_base / "output" / "clips",
            "collections_dir": project_base / "output" / "collections",
            "metadata_dir": project_base / "output" / "metadata",
            "logs_dir": project_base / "logs",
            "temp_dir": project_base / "temp"
        }
    
    def update_api_key(self, api_key: str):
        """更新API密钥"""
        self.settings.dashscope_api_key = api_key
        os.environ["DASHSCOPE_API_KEY"] = api_key
        
        # 保存到配置文件
        self._save_settings()
    
    def update_settings(self, **kwargs):
        """更新设置"""
        for key, value in kwargs.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        
        self._save_settings()
    
    def _save_settings(self):
        """保存设置到文件"""
        config_file = PROJECT_ROOT / "data" / "settings.json"
        config_file.parent.mkdir(exist_ok=True)
        
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings.dict(), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def export_config(self) -> Dict[str, Any]:
        """导出配置"""
        return {
            "api_config": {
                "model_name": self.settings.model_name,
                "api_key": self.settings.dashscope_api_key[:8] + "..." if self.settings.dashscope_api_key else None
            },
            "processing_config": {
                "chunk_size": self.settings.chunk_size,
                "min_score_threshold": self.settings.min_score_threshold,
                "max_clips_per_collection": self.settings.max_clips_per_collection,
                "max_retries": self.settings.max_retries,
                "timeout_seconds": self.settings.timeout_seconds
            },
            # "bilibili_config": {
            #     "auto_upload": self.settings.bilibili_auto_upload,
            #     "default_tid": self.settings.bilibili_default_tid,
            #     "max_concurrent_uploads": self.settings.bilibili_max_concurrent_uploads,
            #     "upload_timeout_minutes": self.settings.bilibili_upload_timeout_minutes,
            #     "auto_generate_tags": self.settings.bilibili_auto_generate_tags,
            #     "tag_limit": self.settings.bilibili_tag_limit
            # },  # 已移除 bilitool 相关功能
            "paths": {
                "project_root": str(self.get_path_config().project_root),
                "data_dir": str(self.get_path_config().data_dir),
                "uploads_dir": str(self.get_path_config().uploads_dir),
                "output_dir": str(self.get_path_config().output_dir),
                "prompt_dir": str(self.get_path_config().prompt_dir)
            }
        }

# 根据视频分类获取prompt文件路径
def get_prompt_files(video_category: str = VideoCategory.DEFAULT) -> Dict[str, Path]:
    """
    根据视频分类获取对应的prompt文件路径
    如果分类专用的prompt文件不存在，则回退到默认prompt文件
    """
    category_prompt_dir = PROMPT_DIR / video_category
    default_prompt_files = PROMPT_FILES.copy()
    
    # 如果分类目录存在，尝试使用分类专用的prompt文件
    if category_prompt_dir.exists():
        category_prompt_files = {}
        for key, default_path in default_prompt_files.items():
            category_file = category_prompt_dir / default_path.name
            if category_file.exists():
                category_prompt_files[key] = category_file
            else:
                # 回退到默认文件
                category_prompt_files[key] = default_path
        return category_prompt_files
    
    # 如果分类目录不存在，返回默认prompt文件
    return default_prompt_files

# 创建全局配置管理器实例
config_manager = ConfigManager()

def get_legacy_config() -> Dict[str, Any]:
    """获取向后兼容的配置"""
    return {
        'PROJECT_ROOT': PROJECT_ROOT,
        'INPUT_DIR': INPUT_DIR,
        'INPUT_VIDEO': INPUT_VIDEO,
        'INPUT_SRT': INPUT_SRT,
        'INPUT_TXT': INPUT_TXT,
        'OUTPUT_DIR': OUTPUT_DIR,
        'CLIPS_DIR': CLIPS_DIR,
        'COLLECTIONS_DIR': COLLECTIONS_DIR,
        'METADATA_DIR': METADATA_DIR,
        'PROMPT_DIR': PROMPT_DIR,
        'PROMPT_FILES': PROMPT_FILES,
        'DASHSCOPE_API_KEY': DASHSCOPE_API_KEY,
        'MODEL_NAME': MODEL_NAME,
        'CHUNK_SIZE': CHUNK_SIZE,
        'MIN_SCORE_THRESHOLD': MIN_SCORE_THRESHOLD,
        'MAX_CLIPS_PER_COLLECTION': MAX_CLIPS_PER_COLLECTION,
        'MIN_TOPIC_DURATION_MINUTES': MIN_TOPIC_DURATION_MINUTES,
        'MAX_TOPIC_DURATION_MINUTES': MAX_TOPIC_DURATION_MINUTES,
        'TARGET_TOPIC_DURATION_MINUTES': TARGET_TOPIC_DURATION_MINUTES,
        'MIN_TOPICS_PER_CHUNK': MIN_TOPICS_PER_CHUNK,
        'MAX_TOPICS_PER_CHUNK': MAX_TOPICS_PER_CHUNK
    }