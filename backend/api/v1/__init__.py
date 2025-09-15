"""
API v1 package for FastAPI routes.
统一管理所有API路由
"""

from fastapi import APIRouter

# 创建主路由器
api_router = APIRouter()

# 导入所有路由模块
from .health import router as health_router
from .projects import router as projects_router
from .clips import router as clips_router
from .collections import router as collections_router
from .tasks import router as tasks_router
from .processing import router as processing_router
# from .websocket import router as websocket_router  # 已禁用WebSocket系统
from .files import router as files_router
from .settings import router as settings_router
from .bilibili import router as bilibili_router
from .youtube import router as youtube_router
from .speech_recognition import router as speech_recognition_router
from .subtitle_editor import router as subtitle_editor_router
from .upload import router as upload_router
from .progress import router as progress_router
from .pipeline_control import router as pipeline_control_router
from .debug import router as debug_router
from .simple_progress import router as simple_progress_router
from ..upload_queue import router as upload_queue_router
from ..account_health import router as account_health_router

# 注册所有路由
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(clips_router, prefix="/clips", tags=["clips"])
api_router.include_router(collections_router, prefix="/collections", tags=["collections"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
api_router.include_router(processing_router, tags=["processing"])
# api_router.include_router(websocket_router, tags=["websocket"])  # 已禁用WebSocket系统
api_router.include_router(files_router, tags=["files"])
api_router.include_router(settings_router, prefix="/settings", tags=["settings"])
api_router.include_router(bilibili_router, prefix="/bilibili", tags=["bilibili"])
api_router.include_router(youtube_router, prefix="/youtube", tags=["youtube"])
api_router.include_router(speech_recognition_router, tags=["speech-recognition"])
api_router.include_router(subtitle_editor_router, prefix="/subtitle-editor", tags=["subtitle-editor"])
api_router.include_router(upload_router, tags=["upload"])
api_router.include_router(progress_router, prefix="/progress", tags=["progress"])
api_router.include_router(pipeline_control_router, prefix="/pipeline", tags=["pipeline"])
api_router.include_router(debug_router, tags=["debug"])
api_router.include_router(simple_progress_router, tags=["simple-progress"])
api_router.include_router(upload_queue_router, tags=["upload-queue"])
api_router.include_router(account_health_router, tags=["account-health"])

__all__ = ["api_router"]