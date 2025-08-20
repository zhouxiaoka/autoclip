"""
B站相关API路由
处理B站视频解析和下载功能
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from pydantic import BaseModel
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from shared.utils.bilibili_downloader import BilibiliDownloader, get_bilibili_video_info
from core.config import get_data_directory
from pathlib import Path
import uuid
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

# 存储下载任务的状态
download_tasks = {}

class BilibiliParseRequest(BaseModel):
    url: str
    browser: Optional[str] = None

class BilibiliDownloadRequest(BaseModel):
    url: str
    project_name: str
    video_category: Optional[str] = "default"
    browser: Optional[str] = None

class BilibiliVideoInfo(BaseModel):
    title: str
    description: str
    duration: int
    uploader: str
    upload_date: str
    view_count: int
    like_count: int
    thumbnail: str

class BilibiliDownloadTask(BaseModel):
    id: str
    url: str
    project_name: str
    video_category: str
    status: str  # pending, processing, completed, failed
    progress: float
    error_message: Optional[str] = None
    project_id: Optional[str] = None
    created_at: str
    updated_at: str

@router.post("/parse")
async def parse_bilibili_video(
    url: str = Form(...),
    browser: Optional[str] = Form(None)
):
    """解析B站视频信息"""
    try:
        logger.info(f"开始解析B站视频: {url}")
        
        # 验证URL格式
        downloader = BilibiliDownloader(browser=browser)
        if not downloader.validate_bilibili_url(url):
            raise HTTPException(status_code=400, detail="无效的B站视频链接")
        
        # 获取真实的视频信息
        video_info = await downloader.get_video_info(url)
        
        logger.info(f"视频信息解析成功: {video_info.title}")
        
        return {
            "success": True,
            "video_info": {
                "title": video_info.title,
                "description": video_info.description,
                "duration": video_info.duration,
                "uploader": video_info.uploader,
                "upload_date": video_info.upload_date,
                "view_count": video_info.view_count,
                "like_count": 0,  # B站API可能不提供点赞数
                "thumbnail": video_info.thumbnail_url
            }
        }
        
    except Exception as e:
        logger.error(f"解析B站视频失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")

@router.post("/download")
async def create_bilibili_download_task(request: BilibiliDownloadRequest):
    """创建B站视频下载任务"""
    try:
        logger.info(f"创建B站下载任务: {request.url}")
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 创建任务记录
        task = BilibiliDownloadTask(
            id=task_id,
            url=request.url,
            project_name=request.project_name,
            video_category=request.video_category,
            status="pending",
            progress=0.0,
            created_at=str(uuid.uuid1().time),
            updated_at=str(uuid.uuid1().time)
        )
        
        # 存储任务
        download_tasks[task_id] = task
        
        # 异步启动下载任务
        asyncio.create_task(process_download_task(task_id, request))
        
        return task
        
    except Exception as e:
        logger.error(f"创建下载任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")

@router.get("/tasks/{task_id}")
async def get_bilibili_task_status(task_id: str):
    """获取下载任务状态"""
    if task_id not in download_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return download_tasks[task_id]

@router.get("/tasks")
async def get_all_bilibili_tasks():
    """获取所有下载任务"""
    return list(download_tasks.values())

async def process_download_task(task_id: str, request: BilibiliDownloadRequest):
    """处理下载任务"""
    try:
        # 更新任务状态为处理中
        download_tasks[task_id].status = "processing"
        download_tasks[task_id].progress = 10.0
        
        # 获取视频信息
        video_info = await get_bilibili_video_info(request.url, request.browser)
        download_tasks[task_id].progress = 30.0
        
        # 下载视频
        data_dir = get_data_directory()
        download_dir = data_dir / "temp"
        download_dir.mkdir(exist_ok=True)
        
        from shared.utils.bilibili_downloader import download_bilibili_video
        download_result = await download_bilibili_video(
            request.url, 
            download_dir, 
            request.browser
        )
        
        video_path = download_result.get('video_path', '')
        subtitle_path = download_result.get('subtitle_path', '')
        
        # 如果没有字幕文件，尝试生成字幕
        if not subtitle_path and video_path:
            logger.warning("未找到字幕文件，尝试生成字幕")
            try:
                from shared.utils.speech_recognizer import generate_subtitle_for_video, SpeechRecognitionError
                from pathlib import Path
                video_file_path = Path(video_path)
                generated_subtitle = generate_subtitle_for_video(video_file_path)
                subtitle_path = str(generated_subtitle)
                logger.info(f"字幕生成成功: {subtitle_path}")
            except SpeechRecognitionError as e:
                logger.error(f"语音识别失败: {e}")
                # 语音识别失败，但不影响下载任务，只是没有字幕
            except Exception as e:
                logger.error(f"生成字幕失败: {e}")
        
        download_tasks[task_id].progress = 80.0
        
        # 创建项目
        from services.project_service import ProjectService
        from core.database import SessionLocal
        
        db = SessionLocal()
        try:
            project_service = ProjectService(db)
            
            # 创建项目
            project_data = {
                "name": request.project_name,
                "description": f"从B站下载: {video_info.title}",
                "project_type": request.video_category,
                "source_url": request.url,
                "source_file": video_path,
                "settings": {
                    "bilibili_info": {
                        "title": video_info.title,
                        "uploader": video_info.uploader,
                        "duration": video_info.duration,
                        "view_count": video_info.view_count
                    },
                    "subtitle_path": subtitle_path if subtitle_path else None
                }
            }
            
            # 创建项目数据
            from schemas.project import ProjectCreate
            
            project_create_data = ProjectCreate(
                name=project_data["name"],
                description=project_data["description"],
                project_type=project_data["project_type"],
                source_url=project_data["source_url"],
                source_file=project_data["source_file"],
                settings=project_data["settings"]
            )
            
            project = project_service.create_project(project_create_data)
            
            # 创建项目目录并移动文件
            project_root = data_dir.parent / "data" / "projects" / str(project.id)
            raw_dir = project_root / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            
            # 移动视频文件到项目目录
            import shutil
            from pathlib import Path
            
            if video_path:
                video_file_path = Path(video_path)
                if video_file_path.exists():
                    # 重命名视频文件为input.mp4
                    new_video_path = raw_dir / "input.mp4"
                    shutil.move(str(video_file_path), str(new_video_path))
                    logger.info(f"视频文件已移动到: {new_video_path}")
                    
                    # 更新项目中的视频路径
                    project.video_path = str(new_video_path)
            
            # 移动字幕文件到项目目录
            if subtitle_path and subtitle_path.strip():
                subtitle_file_path = Path(subtitle_path)
                if subtitle_file_path.exists():
                    # 重命名字幕文件为input.srt
                    new_subtitle_path = raw_dir / "input.srt"
                    shutil.move(str(subtitle_file_path), str(new_subtitle_path))
                    logger.info(f"字幕文件已移动到: {new_subtitle_path}")
                    
                    # 更新项目处理配置中的字幕路径
                    if not project.processing_config:
                        project.processing_config = {}
                    project.processing_config["subtitle_path"] = str(new_subtitle_path)
            
            # 保存项目更新
            db.commit()
            
            # 更新任务状态
            download_tasks[task_id].status = "completed"
            download_tasks[task_id].progress = 100.0
            download_tasks[task_id].project_id = str(project.id)
            download_tasks[task_id].updated_at = datetime.now().isoformat()
            
            logger.info(f"B站下载任务完成: {task_id}, 项目ID: {project.id}")
            
            # 自动启动处理流程
            try:
                # 更新项目状态为处理中
                from schemas.project import ProjectStatus
                project.status = ProjectStatus.PROCESSING
                db.commit()
                
                # 提交Celery任务
                logger.info(f"准备提交Celery任务: {project.id}")
                from tasks.processing import process_video_pipeline
                
                # 准备处理参数
                input_video_path = str(new_video_path) if video_path else ""
                input_srt_path = str(new_subtitle_path) if subtitle_path and subtitle_path.strip() else ""
                
                celery_task = process_video_pipeline.delay(
                    project_id=str(project.id),
                    input_video_path=input_video_path,
                    input_srt_path=input_srt_path
                )
                logger.info(f"Celery任务已提交: {celery_task.id}")
                
                # 创建处理任务记录
                from models.task import Task, TaskType, TaskStatus
                task = Task(
                    name=f"B站视频处理流水线",
                    description=f"处理B站项目 {project.id} 的完整视频流水线",
                    task_type=TaskType.VIDEO_PROCESSING,
                    project_id=str(project.id),
                    celery_task_id=celery_task.id,
                    status=TaskStatus.RUNNING,
                    progress=0,
                    current_step="初始化",
                    total_steps=6
                )
                db.add(task)
                db.commit()
                
                logger.info(f"B站项目 {project.id} 处理任务已启动，Celery任务ID: {celery_task.id}")
                
            except Exception as e:
                logger.error(f"启动B站项目 {project.id} 处理失败: {str(e)}")
                # 即使处理启动失败，也要返回下载成功
                # 用户可以通过重试按钮重新启动处理
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"处理下载任务失败: {str(e)}")
        download_tasks[task_id].status = "failed"
        download_tasks[task_id].error_message = str(e)
        download_tasks[task_id].progress = 0.0
