"""
统一的后端应用工厂函数
支持 web 和 desktop 两种模式
"""
import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.v1 import api_router
from backend.api.v1.health import router as health_router
from backend.core.database import engine
from backend.models.base import Base
from backend.core.config import get_logging_config, get_api_key
from backend.core.error_middleware import global_exception_handler

logger = logging.getLogger(__name__)

def create_app(mode: str = "web") -> FastAPI:
    """
    创建 FastAPI 应用实例
    
    Args:
        mode: 运行模式，支持 "web" 或 "desktop"
    """
    # 设置模式环境变量
    os.environ["AUTOCLIP_MODE"] = mode
    
    # 配置日志
    logging_config = get_logging_config()
    logging.basicConfig(
        level=getattr(logging, logging_config["level"]),
        format=logging_config["format"],
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(logging_config["file"])
        ]
    )
    
    # 创建 FastAPI 应用
    app = FastAPI(
        title="AutoClip API",
        description="AI视频切片处理API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # 设置应用状态
    app.state.mode = mode
    
    # 配置 CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境需要配置具体域名
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 注册全局异常处理器
    app.add_exception_handler(Exception, global_exception_handler)
    
    # 启动事件
    @app.on_event("startup")
    async def startup_event():
        logger.info(f"启动 AutoClip API 服务 (模式: {mode})...")
        
        # 导入所有模型以确保表被创建
        from backend.models.bilibili import BilibiliAccount, UploadRecord
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表创建完成")
        
        # 加载 API 密钥到环境变量
        api_key = get_api_key()
        if api_key:
            os.environ["DASHSCOPE_API_KEY"] = api_key
            logger.info("API 密钥已加载到环境变量")
        else:
            logger.warning("未找到 API 密钥配置")
        
        # 根据模式进行不同的初始化
        if mode == "desktop":
            logger.info("桌面模式：使用本地队列和 SQLite")
        else:
            logger.info("Web 模式：使用 Redis/Celery")
        
        logger.info("WebSocket 网关服务已禁用，使用新的简化进度系统")
    
    # 关闭事件
    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("正在关闭 AutoClip API 服务...")
        logger.info("WebSocket 网关服务已禁用")
    
    # 注册路由
    app.include_router(health_router, prefix="/api/health", tags=["health"])
    app.include_router(api_router, prefix="/api/v1")
    
    # 添加 video-categories 路由（统一到 api_router 中）
    @app.get("/api/v1/video-categories")
    async def get_video_categories():
        """获取视频分类配置."""
        return {
            "categories": [
                {
                    "value": "default",
                    "name": "默认",
                    "description": "通用视频内容处理",
                    "icon": "🎬",
                    "color": "#4facfe"
                },
                {
                    "value": "knowledge",
                    "name": "知识科普",
                    "description": "科学、技术、历史、文化等知识类内容",
                    "icon": "📚",
                    "color": "#52c41a"
                },
                {
                    "value": "entertainment",
                    "name": "娱乐",
                    "description": "游戏、音乐、电影等娱乐内容",
                    "icon": "🎮",
                    "color": "#722ed1"
                },
                {
                    "value": "business",
                    "name": "商业",
                    "description": "商业、创业、投资等商业内容",
                    "icon": "💼",
                    "color": "#fa8c16"
                },
                {
                    "value": "experience",
                    "name": "经验分享",
                    "description": "个人经历、生活感悟等经验内容",
                    "icon": "🌟",
                    "color": "#eb2f96"
                },
                {
                    "value": "opinion",
                    "name": "观点评论",
                    "description": "时事评论、观点分析等评论内容",
                    "icon": "💭",
                    "color": "#13c2c2"
                },
                {
                    "value": "speech",
                    "name": "演讲",
                    "description": "公开演讲、讲座等演讲内容",
                    "icon": "🎤",
                    "color": "#f5222d"
                }
            ],
            "default_category": "default"
        }
    
    # 根健康检查
    @app.get("/health")
    async def root_health():
        try:
            return {
                "status": "ok",
                "mode": mode,
                "version": "1.0.0"
            }
        except Exception as e:
            return JSONResponse(
                status_code=500, 
                content={"status": "error", "detail": str(e)}
            )
    
    return app
