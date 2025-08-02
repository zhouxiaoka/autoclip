"""
健康检查API路由
"""

from fastapi import APIRouter
from datetime import datetime
from typing import Dict, Any

router = APIRouter()


@router.get("/")
async def health_check() -> Dict[str, Any]:
    """健康检查端点."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }


@router.get("/video-categories")
async def get_video_categories() -> Dict[str, Any]:
    """获取视频分类配置."""
    return {
        "categories": [
            {
                "value": "knowledge",
                "name": "知识科普",
                "description": "科学、技术、历史、文化等知识类内容",
                "icon": "book",
                "color": "#1890ff"
            },
            {
                "value": "entertainment", 
                "name": "娱乐休闲",
                "description": "游戏、音乐、电影、综艺等娱乐内容",
                "icon": "play-circle",
                "color": "#52c41a"
            },
            {
                "value": "experience",
                "name": "生活经验",
                "description": "生活技巧、美食、旅行、手工等实用内容",
                "icon": "heart",
                "color": "#fa8c16"
            },
            {
                "value": "opinion",
                "name": "观点评论",
                "description": "时事评论、观点分享、社会话题等",
                "icon": "message",
                "color": "#722ed1"
            },
            {
                "value": "business",
                "name": "商业财经",
                "description": "商业分析、财经资讯、投资理财等",
                "icon": "dollar",
                "color": "#13c2c2"
            },
            {
                "value": "speech",
                "name": "演讲访谈",
                "description": "演讲、访谈、对话等口语化内容",
                "icon": "sound",
                "color": "#eb2f96"
            }
        ],
        "default_category": "knowledge"
    } 