"""
增强的重试机制
支持从下载到处理的完整重试流程
"""

import logging
import uuid
from enum import Enum
from typing import Dict, Any, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ...core.database import get_db
from ...models.project import Project, ProjectStatus
from ...models.task import Task, TaskStatus, TaskType
from ...services.project_service import ProjectService
from ...services.processing_service import ProcessingService
from ...core.config import get_data_directory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/retry", tags=["Enhanced Retry"])

class RetryStrategy(str, Enum):
    """重试策略枚举"""
    DOWNLOAD_ONLY = "download_only"      # 仅重试下载
    PROCESSING_ONLY = "processing_only"  # 仅重试处理
    FULL_RETRY = "full_retry"           # 完整重试（下载+处理）
    SMART_RETRY = "smart_retry"         # 智能重试（自动判断）

class RetryRequest(BaseModel):
    """重试请求"""
    strategy: Optional[RetryStrategy] = RetryStrategy.SMART_RETRY
    force_redownload: bool = False  # 是否强制重新下载
    browser: Optional[str] = None   # 浏览器设置（用于下载）

class RetryResponse(BaseModel):
    """重试响应"""
    success: bool
    message: str
    strategy_used: RetryStrategy
    project_id: str
    task_id: Optional[str] = None
    download_task_id: Optional[str] = None

def determine_retry_strategy(project: Project, force_redownload: bool = False) -> RetryStrategy:
    """智能判断重试策略"""
    if force_redownload:
        return RetryStrategy.FULL_RETRY
    
    # 检查视频文件是否存在
    video_exists = project.video_path and Path(project.video_path).exists()
    
    if not video_exists:
        return RetryStrategy.FULL_RETRY  # 没有视频文件，完整重试
    
    # 检查项目状态
    if project.status == ProjectStatus.FAILED:
        return RetryStrategy.PROCESSING_ONLY  # 有视频文件但处理失败，仅重试处理
    elif project.status == ProjectStatus.PENDING:
        return RetryStrategy.PROCESSING_ONLY  # 有视频文件但未处理，仅重试处理
    else:
        return RetryStrategy.SMART_RETRY

async def retry_download_only(
    project_id: str, 
    browser: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """仅重试下载"""
    try:
        # 获取项目信息
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 获取原始下载信息（从项目描述中提取）
        description = project.description or ""
        if "从B站下载:" in description:
            # B站项目
            url = description.replace("从B站下载:", "").strip()
            return await retry_bilibili_download(project_id, url, browser, db)
        elif "从YouTube下载:" in description:
            # YouTube项目
            url = description.replace("从YouTube下载:", "").strip()
            return await retry_youtube_download(project_id, url, browser, db)
        else:
            raise HTTPException(status_code=400, detail="无法确定下载源")
    
    except Exception as e:
        logger.error(f"重试下载失败: {e}")
        raise HTTPException(status_code=500, detail=f"重试下载失败: {str(e)}")

async def retry_bilibili_download(
    project_id: str, 
    url: str, 
    browser: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """重试B站下载"""
    try:
        # 导入B站下载相关模块
        from .bilibili import process_download_task, BilibiliDownloadRequest
        from .async_task_manager import task_manager
        
        # 创建下载请求
        request = BilibiliDownloadRequest(
            url=url,
            project_name=db.query(Project).filter(Project.id == project_id).first().name,
            video_category="default",
            browser=browser
        )
        
        # 生成新的下载任务ID
        task_id = str(uuid.uuid4())
        
        # 启动下载任务
        await task_manager.create_safe_task(
            f"bilibili_retry_{task_id}",
            process_download_task,
            task_id,
            request,
            project_id
        )
        
        return {
            "success": True,
            "message": "B站下载重试已启动",
            "task_id": task_id
        }
    
    except Exception as e:
        logger.error(f"重试B站下载失败: {e}")
        raise HTTPException(status_code=500, detail=f"重试B站下载失败: {str(e)}")

async def retry_youtube_download(
    project_id: str, 
    url: str, 
    browser: Optional[str] = None,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """重试YouTube下载"""
    try:
        # 导入YouTube下载相关模块
        from .youtube import process_youtube_download_task, YouTubeDownloadRequest
        from .async_task_manager import task_manager
        
        # 创建下载请求
        request = YouTubeDownloadRequest(
            url=url,
            project_name=db.query(Project).filter(Project.id == project_id).first().name,
            video_category="default",
            browser=browser
        )
        
        # 生成新的下载任务ID
        task_id = str(uuid.uuid4())
        
        # 启动下载任务
        await task_manager.create_safe_task(
            f"youtube_retry_{task_id}",
            process_youtube_download_task,
            task_id,
            request,
            project_id
        )
        
        return {
            "success": True,
            "message": "YouTube下载重试已启动",
            "task_id": task_id
        }
    
    except Exception as e:
        logger.error(f"重试YouTube下载失败: {e}")
        raise HTTPException(status_code=500, detail=f"重试YouTube下载失败: {str(e)}")

async def retry_processing_only(
    project_id: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """仅重试处理"""
    try:
        # 使用现有的处理服务
        processing_service = ProcessingService(db)
        
        # 获取项目信息
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 检查视频文件
        if not project.video_path or not Path(project.video_path).exists():
            raise HTTPException(status_code=400, detail="视频文件不存在，请先重试下载")
        
        # 重置项目状态
        project.status = ProjectStatus.PENDING
        db.commit()
        
        # 启动处理任务
        result = processing_service.start_processing(
            project_id=project_id,
            srt_path=Path(project.video_path).parent / "input.srt" if (project.video_path and Path(project.video_path).parent / "input.srt").exists() else None
        )
        
        return {
            "success": True,
            "message": "处理重试已启动",
            "task_id": result.get("task_id")
        }
    
    except Exception as e:
        logger.error(f"重试处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"重试处理失败: {str(e)}")

@router.post("/projects/{project_id}/smart-retry", response_model=RetryResponse)
async def smart_retry_project(
    project_id: str,
    request: RetryRequest,
    db: Session = Depends(get_db)
):
    """智能重试项目"""
    try:
        # 获取项目信息
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        # 确定重试策略
        if request.strategy == RetryStrategy.SMART_RETRY:
            strategy = determine_retry_strategy(project, request.force_redownload)
        else:
            strategy = request.strategy
        
        logger.info(f"项目 {project_id} 使用重试策略: {strategy}")
        
        # 执行重试
        if strategy == RetryStrategy.FULL_RETRY:
            # 完整重试：先重试下载，下载完成后自动开始处理
            download_result = await retry_download_only(project_id, request.browser, db)
            return RetryResponse(
                success=True,
                message="完整重试已启动（下载+处理）",
                strategy_used=strategy,
                project_id=project_id,
                download_task_id=download_result.get("task_id")
            )
        
        elif strategy == RetryStrategy.DOWNLOAD_ONLY:
            # 仅重试下载
            download_result = await retry_download_only(project_id, request.browser, db)
            return RetryResponse(
                success=True,
                message="下载重试已启动",
                strategy_used=strategy,
                project_id=project_id,
                download_task_id=download_result.get("task_id")
            )
        
        elif strategy == RetryStrategy.PROCESSING_ONLY:
            # 仅重试处理
            processing_result = await retry_processing_only(project_id, db)
            return RetryResponse(
                success=True,
                message="处理重试已启动",
                strategy_used=strategy,
                project_id=project_id,
                task_id=processing_result.get("task_id")
            )
        
        else:
            raise HTTPException(status_code=400, detail=f"不支持的重试策略: {strategy}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"智能重试失败: {e}")
        raise HTTPException(status_code=500, detail=f"智能重试失败: {str(e)}")

@router.get("/projects/{project_id}/retry-strategy")
async def get_retry_strategy(
    project_id: str,
    force_redownload: bool = False,
    db: Session = Depends(get_db)
):
    """获取建议的重试策略"""
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")
        
        strategy = determine_retry_strategy(project, force_redownload)
        
        return {
            "project_id": project_id,
            "suggested_strategy": strategy,
            "reason": _get_strategy_reason(project, strategy),
            "video_exists": project.video_path and Path(project.video_path).exists(),
            "project_status": project.status
        }
    
    except Exception as e:
        logger.error(f"获取重试策略失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取重试策略失败: {str(e)}")

def _get_strategy_reason(project: Project, strategy: RetryStrategy) -> str:
    """获取策略选择原因"""
    if strategy == RetryStrategy.FULL_RETRY:
        return "没有视频文件或强制重新下载"
    elif strategy == RetryStrategy.PROCESSING_ONLY:
        return "视频文件存在但处理失败或未开始"
    elif strategy == RetryStrategy.DOWNLOAD_ONLY:
        return "仅重试下载阶段"
    else:
        return "智能判断"
