"""
YouTube相关API路由
处理YouTube视频解析和下载功能
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Form, UploadFile, File
from pydantic import BaseModel
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))
from core.config import get_data_directory
import uuid
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter()

# 存储下载任务的状态
download_tasks = {}

class YouTubeParseRequest(BaseModel):
    url: str
    browser: Optional[str] = None

class YouTubeDownloadRequest(BaseModel):
    url: str
    project_name: str
    video_category: Optional[str] = "default"
    browser: Optional[str] = None

class YouTubeVideoInfo(BaseModel):
    title: str
    description: str
    duration: int
    uploader: str
    upload_date: str
    view_count: int
    like_count: int
    thumbnail: str

class YouTubeDownloadTask(BaseModel):
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
async def parse_youtube_video(
    url: str = Form(...),
    browser: Optional[str] = Form(None)
):
    """解析YouTube视频信息"""
    try:
        logger.info(f"开始解析YouTube视频: {url}")
        
        # 简单的URL验证
        if "youtube.com" not in url and "youtu.be" not in url:
            raise HTTPException(status_code=400, detail="无效的YouTube视频链接")
        
        # 使用yt-dlp获取真实的视频信息
        import yt_dlp
        import asyncio
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        if browser:
            ydl_opts['cookiesfrombrowser'] = (browser.lower(),)
        
        def extract_info_sync(url, ydl_opts):
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        loop = asyncio.get_event_loop()
        info_dict = await loop.run_in_executor(None, extract_info_sync, url, ydl_opts)
        
        logger.info(f"YouTube视频信息解析成功: {info_dict.get('title', 'Unknown')}")
        
        return {
            "success": True,
            "video_info": {
                "title": info_dict.get('title', 'Unknown'),
                "description": info_dict.get('description', ''),
                "duration": info_dict.get('duration', 0),
                "uploader": info_dict.get('uploader', 'Unknown'),
                "upload_date": info_dict.get('upload_date', ''),
                "view_count": info_dict.get('view_count', 0),
                "like_count": info_dict.get('like_count', 0),
                "thumbnail": info_dict.get('thumbnail', '')
            }
        }
        
    except Exception as e:
        logger.error(f"解析YouTube视频失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")

@router.post("/download")
async def create_youtube_download_task(request: YouTubeDownloadRequest):
    """创建YouTube视频下载任务"""
    try:
        logger.info(f"创建YouTube下载任务: {request.url}")
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 创建任务记录
        task = YouTubeDownloadTask(
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
        asyncio.create_task(process_youtube_download_task(task_id, request))
        
        return task
        
    except Exception as e:
        logger.error(f"创建YouTube下载任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"创建任务失败: {str(e)}")

@router.get("/tasks/{task_id}")
async def get_youtube_task_status(task_id: str):
    """获取YouTube下载任务状态"""
    if task_id not in download_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return download_tasks[task_id]

@router.get("/tasks")
async def get_all_youtube_tasks():
    """获取所有YouTube下载任务"""
    return list(download_tasks.values())

async def process_youtube_download_task(task_id: str, request: YouTubeDownloadRequest):
    """处理YouTube下载任务"""
    try:
        # 更新任务状态为处理中
        download_tasks[task_id].status = "processing"
        download_tasks[task_id].progress = 10.0
        
        # 使用yt-dlp下载视频
        import yt_dlp
        from core.config import get_data_directory
        
        data_dir = get_data_directory()
        download_dir = data_dir / "temp"
        download_dir.mkdir(exist_ok=True)
        
        # 设置下载选项
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'writesubtitles': True,
            'writeautomaticsub': True,  # 下载自动生成的字幕
            'subtitleslangs': ['en', 'zh-Hans', 'zh', 'en-US', 'auto'],  # 英文和中文字幕，包括自动检测
            'subtitlesformat': 'srt',
            'outtmpl': str(download_dir / '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'no_warnings': False,  # 显示警告信息以便调试
        }
        
        if request.browser:
            ydl_opts['cookiesfrombrowser'] = (request.browser.lower(),)
        
        def download_sync(url, ydl_opts):
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.download([url])
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, download_sync, request.url, ydl_opts)
        
        download_tasks[task_id].progress = 80.0
        
        # 查找下载的文件
        video_files = list(download_dir.glob("*.mp4"))
        subtitle_files = list(download_dir.glob("*.srt"))
        
        if not video_files:
            raise Exception("未找到下载的视频文件")
        
        video_path = str(video_files[0])
        subtitle_path = str(subtitle_files[0]) if subtitle_files else ""
        
        # 如果没有字幕文件，尝试多种策略获取字幕
        if not subtitle_path:
            logger.warning("未找到字幕文件，尝试备用策略...")
            subtitle_path = await _try_youtube_subtitle_strategies(request.url, download_dir, request.browser)
        
        # 如果仍然没有字幕文件，尝试生成字幕
        if not subtitle_path:
            logger.warning("所有字幕获取策略都失败，尝试生成字幕")
            try:
                from backend.utils.speech_recognizer import generate_subtitle_for_video, SpeechRecognitionError
                video_file_path = Path(video_path)
                generated_subtitle = generate_subtitle_for_video(video_file_path)
                subtitle_path = str(generated_subtitle)
                logger.info(f"字幕生成成功: {subtitle_path}")
            except SpeechRecognitionError as e:
                logger.error(f"语音识别失败: {e}")
                # 语音识别失败，但不影响下载任务，只是没有字幕
            except Exception as e:
                logger.error(f"生成字幕失败: {e}")
        
        logger.info(f"下载完成 - 视频文件: {video_path}, 字幕文件: {subtitle_path}")
        
        # 创建项目
        from services.project_service import ProjectService
        from core.database import SessionLocal
        
        db = SessionLocal()
        try:
            project_service = ProjectService(db)
            
            # 创建项目
            from schemas.project import ProjectCreate, ProjectType, ProjectStatus
            
            project_data = ProjectCreate(
                name=request.project_name,
                description=f"从YouTube下载: {request.project_name}",
                project_type=ProjectType(request.video_category),
                status=ProjectStatus.PENDING,
                source_url=request.url,
                source_file=video_path,
                settings={
                    "youtube_info": {
                        "title": request.project_name,
                        "uploader": "YouTube",
                        "duration": 0,
                        "view_count": 0,
                        "like_count": 0
                    },
                    "subtitle_path": subtitle_path
                }
            )
            
            project = project_service.create_project(project_data)
            
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
            if subtitle_path:
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
            
            logger.info(f"YouTube下载任务完成: {task_id}, 项目ID: {project.id}")
            
        except Exception as e:
            logger.error(f"创建项目失败: {str(e)}")
            # 即使处理启动失败，也要返回下载成功
            # 用户可以通过重试按钮重新启动处理
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"处理下载任务失败: {str(e)}")
        download_tasks[task_id].status = "failed"
        download_tasks[task_id].error_message = str(e)
        download_tasks[task_id].progress = 0.0
        download_tasks[task_id].updated_at = datetime.now().isoformat()


async def _try_youtube_subtitle_strategies(url: str, download_dir: Path, browser: Optional[str] = None) -> str:
    """尝试多种YouTube字幕获取策略"""
    strategies = [
        lambda: _try_download_with_different_formats(url, download_dir, browser),
        lambda: _try_download_with_different_langs(url, download_dir, browser),
        lambda: _try_extract_from_metadata(url, download_dir, browser)
    ]
    
    for strategy in strategies:
        try:
            subtitle_path = await strategy()
            if subtitle_path:
                logger.info(f"YouTube备用字幕策略成功")
                return subtitle_path
        except Exception as e:
            logger.warning(f"YouTube备用字幕策略失败: {e}")
            continue
    
    logger.warning("所有YouTube字幕获取策略都失败了")
    return ""


async def _try_download_with_different_formats(url: str, download_dir: Path, browser: Optional[str] = None) -> str:
    """尝试下载不同格式的字幕"""
    logger.info("尝试下载不同格式的YouTube字幕...")
    
    formats = ['srt', 'vtt', 'json3']
    
    for fmt in formats:
        try:
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'zh-Hans', 'zh'],
                'subtitlesformat': fmt,
                'outtmpl': str(download_dir / f'subtitle_%(title)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
            }
            
            if browser:
                ydl_opts['cookiesfrombrowser'] = (browser.lower(),)
            
            def download_sync(url, ydl_opts):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.download([url])
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, download_sync, url, ydl_opts)
            
            # 查找下载的字幕文件
            subtitle_files = list(download_dir.glob(f"*.{fmt}"))
            if subtitle_files:
                subtitle_path = str(subtitle_files[0])
                
                # 如果是VTT格式，转换为SRT
                if fmt == 'vtt':
                    srt_path = subtitle_path.replace('.vtt', '.srt')
                    await _convert_vtt_to_srt(subtitle_path, srt_path)
                    return srt_path
                
                return subtitle_path
                
        except Exception as e:
            logger.debug(f"尝试格式 {fmt} 失败: {e}")
            continue
    
    return ""


async def _try_download_with_different_langs(url: str, download_dir: Path, browser: Optional[str] = None) -> str:
    """尝试下载不同语言的字幕"""
    logger.info("尝试下载不同语言的YouTube字幕...")
    
    lang_combinations = [
        ['en', 'en-US'],      # 英文
        ['zh-Hans', 'zh'],    # 中文
        ['ja', 'ja-JP'],      # 日文
        ['ko', 'ko-KR'],      # 韩文
        ['auto']              # 自动检测
    ]
    
    for langs in lang_combinations:
        try:
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': langs,
                'subtitlesformat': 'srt',
                'outtmpl': str(download_dir / f'lang_%(title)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
            }
            
            if browser:
                ydl_opts['cookiesfrombrowser'] = (browser.lower(),)
            
            def download_sync(url, ydl_opts):
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.download([url])
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, download_sync, url, ydl_opts)
            
            # 查找下载的字幕文件
            subtitle_files = list(download_dir.glob("*.srt"))
            if subtitle_files:
                return str(subtitle_files[0])
                
        except Exception as e:
            logger.debug(f"尝试语言 {langs} 失败: {e}")
            continue
    
    return ""


async def _try_extract_from_metadata(url: str, download_dir: Path, browser: Optional[str] = None) -> str:
    """尝试从视频元数据中提取字幕信息"""
    logger.info("尝试从YouTube视频元数据提取字幕信息...")
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        if browser:
            ydl_opts['cookiesfrombrowser'] = (browser.lower(),)
        
        def extract_info_sync(url, ydl_opts):
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        loop = asyncio.get_event_loop()
        info_dict = await loop.run_in_executor(None, extract_info_sync, url, ydl_opts)
        
        # 检查是否有字幕信息
        subtitles = info_dict.get('subtitles', {})
        auto_subtitles = info_dict.get('automatic_captions', {})
        
        if subtitles or auto_subtitles:
            logger.info(f"发现YouTube字幕信息: {list(subtitles.keys()) + list(auto_subtitles.keys())}")
            # 这里可以进一步处理字幕信息，但目前返回空字符串
            return ""
        
        return ""
        
    except Exception as e:
        logger.debug(f"提取YouTube视频元数据失败: {e}")
        return ""


async def _convert_vtt_to_srt(vtt_path: str, srt_path: str):
    """将VTT字幕文件转换为SRT格式"""
    try:
        with open(vtt_path, 'r', encoding='utf-8') as vtt_file:
            vtt_content = vtt_file.read()
        
        # 简单的VTT到SRT转换
        lines = vtt_content.split('\n')
        srt_lines = []
        subtitle_count = 1
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 跳过VTT头部信息
            if line.startswith('WEBVTT') or line.startswith('NOTE') or not line:
                i += 1
                continue
            
            # 查找时间戳行
            if '-->' in line:
                # 转换时间格式 (VTT使用点，SRT使用逗号)
                time_line = line.replace('.', ',')
                srt_lines.append(str(subtitle_count))
                srt_lines.append(time_line)
                
                # 获取字幕文本
                i += 1
                subtitle_text = []
                while i < len(lines) and lines[i].strip():
                    subtitle_text.append(lines[i].strip())
                    i += 1
                
                srt_lines.extend(subtitle_text)
                srt_lines.append('')  # 空行分隔
                subtitle_count += 1
            
            i += 1
        
        # 写入SRT文件
        with open(srt_path, 'w', encoding='utf-8') as srt_file:
            srt_file.write('\n'.join(srt_lines))
            
        logger.info(f"VTT转SRT转换成功: {vtt_path} -> {srt_path}")
        
    except Exception as e:
        logger.error(f"VTT转SRT转换失败: {e}")
        raise
