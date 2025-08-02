"""
FastAPI main application.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
        logging.FileHandler('backend.log')  # 输出到文件
    ]
)

logger = logging.getLogger(__name__)

# 使用绝对导入
from api.v1 import health, projects, clips, collections, tasks, settings
from core.database import engine
from models.base import Base

# Create FastAPI app
app = FastAPI(
    title="AutoClip API",
    description="AI视频切片处理API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Create database tables
@app.on_event("startup")
async def startup_event():
    logger.info("启动AutoClip API服务...")
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表创建完成")
    
    # 加载设置到环境变量
    try:
        from api.v1.settings import load_settings
        settings = load_settings()
        if settings.get("dashscope_api_key"):
            import os
            os.environ["DASHSCOPE_API_KEY"] = settings["dashscope_api_key"]
            logger.info("API密钥已加载到环境变量")
        else:
            logger.warning("未找到API密钥配置")
    except Exception as e:
        logger.warning(f"加载设置失败: {e}")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(clips.router, prefix="/api/v1/clips", tags=["clips"])
app.include_router(collections.router, prefix="/api/v1/collections", tags=["collections"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["settings"])

# Include WebSocket routes
from api.v1 import websocket
app.include_router(websocket.router, prefix="/api/v1", tags=["websocket"])

# 添加独立的video-categories端点
@app.get("/api/v1/video-categories")
async def get_video_categories():
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

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    logger.info("访问根端点")
    return {
        "message": "AutoClip API is running!",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health"
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"全局异常处理: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)