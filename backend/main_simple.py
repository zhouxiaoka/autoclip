"""简化的FastAPI应用入口点"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 导入配置管理
from core.config import settings, get_logging_config

# 配置日志
logging_config = get_logging_config()
logging.basicConfig(
    level=getattr(logging, logging_config["level"]),
    format=logging_config["format"],
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
        logging.FileHandler(logging_config["file"])  # 输出到文件
    ]
)

logger = logging.getLogger(__name__)

# 直接在这里定义简单的路由，避免复杂的导入
from fastapi import APIRouter
from core.database import engine
from models.base import Base

# 创建应用实例
app = FastAPI(
    title="AutoClip API",
    description="自动视频切片工具 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发环境允许所有源
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"全局异常处理: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "内部服务器错误"}
    )

# 创建简单的健康检查路由
health_router = APIRouter()

@health_router.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": "AutoClip API",
        "version": "1.0.0-simple"
    }

# 注册路由
app.include_router(health_router, prefix="/api/v1", tags=["健康检查"])

# 启动事件
@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    logger.info("AutoClip 后端服务正在启动...")
    
    # 创建数据库表
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表创建/更新完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise
    
    logger.info("AutoClip 后端服务启动完成")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时的清理"""
    logger.info("AutoClip 后端服务正在关闭...")

# 根路径
@app.get("/")
async def root():
    return {
        "message": "AutoClip API", 
        "version": "1.0.0",
        "status": "running",
        "mode": "simplified"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)