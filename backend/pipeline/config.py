"""
Pipeline模块配置文件
"""

import os
from pathlib import Path

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
BACKEND_ROOT = Path(__file__).parent.parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
METADATA_DIR = DATA_DIR / "output" / "metadata"

# 提示词文件路径
PROMPT_DIR = PROJECT_ROOT / "prompt"
PROMPT_FILES = {
    'outline': PROMPT_DIR / "大纲.txt",
    'timeline': PROMPT_DIR / "时间点.txt", 
    'scoring': PROMPT_DIR / "推荐理由.txt",
    'recommendation': PROMPT_DIR / "推荐理由.txt",  # 添加别名
    'title': PROMPT_DIR / "标题生成.txt",
    'clustering': PROMPT_DIR / "主题聚类.txt"
}

# 确保目录存在
METADATA_DIR.mkdir(parents=True, exist_ok=True)
PROMPT_DIR.mkdir(parents=True, exist_ok=True)

# API密钥配置
DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# 默认API密钥
DEFAULT_API_KEY = DASHSCOPE_API_KEY or OPENAI_API_KEY

# 评分阈值
MIN_SCORE_THRESHOLD = 7.0

# 聚类配置
MAX_CLIPS_PER_COLLECTION = 10
