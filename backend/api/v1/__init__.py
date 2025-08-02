"""
API v1 package for FastAPI routes.
"""

from fastapi import APIRouter
from .projects import router as projects_router
from .clips import router as clips_router
from .collections import router as collections_router
from .tasks import router as tasks_router
from .health import router as health_router
from .processing import router as processing_router
from .websocket import router as websocket_router

api_router = APIRouter(prefix="/v1")

# Include all route modules
api_router.include_router(health_router, tags=["health"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(clips_router, prefix="/clips", tags=["clips"])
api_router.include_router(collections_router, prefix="/collections", tags=["collections"])
api_router.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
api_router.include_router(processing_router, tags=["processing"])
api_router.include_router(websocket_router, tags=["websocket"])

__all__ = ["api_router"]