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
from ...core.config import get_data_directory
import uuid
import asyncio
from datetime import datetime
from contextlib import contextmanager
import os
import yt_dlp

logger = logging.getLogger(__name__)
router = APIRouter()

# 存储下载任务的状态
download_tasks = {}

_CHROMIUM_BROWSERS = frozenset({
    "chrome", "edge", "chromium", "brave", "opera", "vivaldi", "whale",
})

# Prefer HLS 1080p60 (m3u8). DASH 299 often has a URL but writes 0 bytes under SABR.
YOUTUBE_VIDEO_FORMAT = (
    "bestvideo[height<=1080][fps>=50][protocol^=m3u8]+bestaudio[ext=m4a]/"
    "bestvideo[height<=1080][protocol^=m3u8]+bestaudio/"
    "bestvideo[height<=1080][fps>=50][vcodec^=avc1]+bestaudio[ext=m4a]/"
    "bestvideo[height<=1080]+bestaudio/"
    "best[height<=1080]/best"
)
# android/web currently only return 360p (SABR). tv_embedded still has 1080p60 AVC.
YOUTUBE_PLAYER_CLIENTS = ["tv_embedded"]


@contextmanager
def sanitized_yt_env():
    """临时清理与 yt-dlp 相关的环境变量，避免外部配置影响行为"""
    original_env = os.environ.copy()
    try:
        for key in list(os.environ.keys()):
            upper_key = key.upper()
            if upper_key.startswith("YT_DLP") or upper_key.startswith("YTDL") or upper_key.startswith("YOUTUBE_DL") or upper_key.startswith("YOUTUBEDL"):
                os.environ.pop(key, None)
        yield
    finally:
        os.environ.clear()
        os.environ.update(original_env)


def _cookie_browser(browser: Optional[str]) -> Optional[str]:
    """Return a yt-dlp browser name, or None when cookies cannot be used."""
    if not browser or not str(browser).strip():
        return None
    name = browser.strip().lower()
    if sys.platform == "win32" and name in _CHROMIUM_BROWSERS:
        logger.warning(
            "Skipping %s cookies on Windows (Chrome DPAPI / app-bound encryption)",
            name,
        )
        return None
    return name


def _is_cookie_error(err: Exception) -> bool:
    text = str(err).lower()
    return any(token in text for token in ("dpapi", "failed to decrypt", "cookiesfrombrowser", "cookie database"))


def _video_meets_1080p60(path: Path) -> bool:
    try:
        from ...utils.ffmpeg_utils import get_ffprobe_path
        import json as _json
        import subprocess
        result = subprocess.run(
            [
                get_ffprobe_path(),
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate",
                "-of", "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        if result.returncode != 0:
            return False
        streams = (_json.loads(result.stdout or "{}").get("streams") or [{}])[0]
        height = int(streams.get("height") or 0)
        rate = str(streams.get("r_frame_rate") or "0/1")
        num, den = rate.split("/", 1) if "/" in rate else (rate, "1")
        fps = float(num) / max(float(den), 1.0)
        return height >= 1080 and fps >= 50
    except Exception:
        return False


def _yt_dlp_run(url: str, ydl_opts: dict, download: bool = False):
    with sanitized_yt_env():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if download:
                return ydl.download([url])
            return ydl.extract_info(url, download=False)


def _yt_dlp_with_cookie_fallback(url: str, ydl_opts: dict, browser: Optional[str] = None, download: bool = False):
    opts = dict(ydl_opts)
    cookie_browser = _cookie_browser(browser)
    if cookie_browser:
        opts["cookiesfrombrowser"] = (cookie_browser,)
    else:
        opts.pop("cookiesfrombrowser", None)
    try:
        return _yt_dlp_run(url, opts, download=download)
    except Exception as err:
        if opts.get("cookiesfrombrowser") and _is_cookie_error(err):
            logger.warning("Browser cookies failed (%s); retrying without cookies", err)
            opts = dict(ydl_opts)
            opts.pop("cookiesfrombrowser", None)
            return _yt_dlp_run(url, opts, download=download)
        raise

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
    browser: Optional[str] = Form(None),
    client: Optional[str] = Form(None)
):
    """解析YouTube视频信息"""
    try:
        logger.info(f"开始解析YouTube视频: {url}")
        
        # 简单的URL验证
        if "youtube.com" not in url and "youtu.be" not in url:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")

        try:
            logger.info(f"yt-dlp={yt_dlp.version.__version__}, py={sys.executable}")
        except Exception:
            pass

        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreconfig': True,
            'noplaylist': True,
            'skip_download': True,
            'cachedir': False,
        }

        yt_client = (client or os.getenv('AUTOCLIP_YT_CLIENT', '')).strip().lower()
        player_clients = list(YOUTUBE_PLAYER_CLIENTS)
        if yt_client in {"android", "ios", "tv", "tv_embedded"}:
            player_clients = [yt_client]
        ydl_opts.setdefault('extractor_args', {}).setdefault('youtube', {})['player_client'] = player_clients

        loop = asyncio.get_event_loop()
        info_dict = await loop.run_in_executor(
            None, lambda: _yt_dlp_with_cookie_fallback(url, ydl_opts, browser, download=False)
        )
        
        logger.info(f"YouTube视频信息解析成功: {info_dict.get('title', 'Unknown')}")
        
        return {
            "success": True,
            "video_info": {
                "title": info_dict.get('title', 'Unknown'),
                "description": info_dict.get('description', ''),
                "duration": info_dict.get('duration', 0) or 0,
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
    """创建YouTube视频下载任务 - 立即创建项目"""
    try:
        logger.info(f"创建YouTube下载任务: {request.url}")
        
        # 先获取视频信息以获取缩略图
        import yt_dlp
        import asyncio
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreconfig': True,
            'noplaylist': True,
            'config_locations': [],
            'cachedir': False,
        }
        
        yt_client_env = os.getenv('AUTOCLIP_YT_CLIENT', '').strip().lower()
        player_clients = list(YOUTUBE_PLAYER_CLIENTS)
        if yt_client_env in {"android", "ios", "tv", "tv_embedded"}:
            player_clients = [yt_client_env]
        ydl_opts.setdefault('extractor_args', {}).setdefault('youtube', {})['player_client'] = player_clients
        
        loop = asyncio.get_event_loop()
        video_info = await loop.run_in_executor(
            None, lambda: _yt_dlp_with_cookie_fallback(request.url, ydl_opts, request.browser, download=False)
        )
        
        # 立即创建项目记录
        from ...core.database import SessionLocal
        from ...services.project_service import ProjectService
        from ...schemas.project import ProjectCreate, ProjectType, ProjectStatus
        
        db = SessionLocal()
        try:
            project_service = ProjectService(db)
            
            # 处理缩略图 - 直接使用解析出来的封面图
            thumbnail_data = None
            thumbnail_url = video_info.get('thumbnail', '')
            if thumbnail_url:
                try:
                    import requests
                    import base64
                    
                    # 下载缩略图
                    response = requests.get(thumbnail_url, timeout=10)
                    if response.status_code == 200:
                        # 转换为base64
                        thumbnail_base64 = base64.b64encode(response.content).decode('utf-8')
                        thumbnail_data = f"data:image/jpeg;base64,{thumbnail_base64}"
                        logger.info(f"YouTube缩略图获取成功: {video_info.get('title', 'Unknown')}")
                    else:
                        logger.warning(f"下载YouTube缩略图失败: {response.status_code}")
                except Exception as e:
                    logger.error(f"处理YouTube缩略图失败: {e}")
                    # 缩略图处理失败不影响主流程
            
            # 创建项目数据
            project_data = ProjectCreate(
                name=request.project_name,
                description=f"从YouTube下载: {video_info.get('title', 'Unknown')}",
                project_type=ProjectType(request.video_category),
                status=ProjectStatus.PENDING,  # 初始状态为等待中
                source_url=request.url,
                source_file=None,  # 暂时为空，下载完成后更新
                settings={
                    "download_status": "downloading",
                    "download_progress": 0.0,
                    "youtube_info": {
                        "url": request.url,
                        "browser": request.browser,
                        "title": video_info.get('title', 'Unknown'),
                        "uploader": video_info.get('uploader', 'Unknown'),
                        "duration": video_info.get('duration', 0),
                        "view_count": video_info.get('view_count', 0),
                        "thumbnail_url": thumbnail_url
                    }
                }
            )
            
            project = project_service.create_project(project_data)
            project_id = str(project.id)
            
            # 设置缩略图
            if thumbnail_data:
                project.thumbnail = thumbnail_data
                db.commit()
                logger.info(f"项目 {project_id} 缩略图已设置")
            
            # 创建项目目录
            from ...core.path_utils import get_project_directory
            project_dir = get_project_directory(project_id)
            raw_dir = project_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"项目已创建: {project_id}")
            
            # 生成下载任务ID
            task_id = str(uuid.uuid4())
            
            # 创建任务记录
            task = YouTubeDownloadTask(
                id=task_id,
                url=request.url,
                project_name=request.project_name,
                video_category=request.video_category,
                status="pending",
                progress=0.0,
                project_id=project_id,  # 关联项目ID
                created_at=str(uuid.uuid1().time),
                updated_at=str(uuid.uuid1().time)
            )
            
            # 存储任务
            download_tasks[task_id] = task
            
            # 异步启动下载任务 - 使用安全的任务管理器
            from .async_task_manager import task_manager
            await task_manager.create_safe_task(
                f"youtube_download_{task_id}", 
                process_youtube_download_task, 
                task_id, 
                request, 
                project_id
            )
            
            # 返回项目信息而不是任务信息
            return {
                "project_id": project_id,
                "task_id": task_id,
                "status": "created",
                "message": "项目已创建，正在下载中..."
            }
            
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"创建YouTube下载任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

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

async def update_project_download_progress(project_id: str, progress: float, message: str):
    """更新项目下载进度"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_update_download_progress, project_id, progress, message)


def _sync_update_download_progress(project_id: str, progress: float, message: str) -> None:
    try:
        from ...core.database import SessionLocal
        from ...services.project_service import ProjectService
        from sqlalchemy.orm.attributes import flag_modified

        db = SessionLocal()
        try:
            project_service = ProjectService(db)
            project = project_service.get(project_id)
            if not project:
                return
            config = dict(project.processing_config or {})
            config.update({
                "download_progress": progress,
                "download_message": message,
            })
            project.processing_config = config
            flag_modified(project, "processing_config")
            db.commit()
            logger.info(f"项目 {project_id} 下载进度更新: {progress:.1f}% - {message}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"更新项目下载进度失败: {e}")


def _make_download_progress_hook(project_id: str):
    last = {"pct": -10.0}

    def hook(d):
        if d.get("status") != "downloading":
            return
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        done = d.get("downloaded_bytes") or 0
        if not total:
            return
        mapped = 15.0 + min(50.0, (done / total) * 50.0)
        if mapped - last["pct"] < 3:
            return
        last["pct"] = mapped
        _sync_update_download_progress(project_id, mapped, "Downloading video…")

    return hook

async def process_youtube_download_task(task_id: str, request: YouTubeDownloadRequest, project_id: str):
    """处理YouTube下载任务"""
    try:
        # 更新任务状态为处理中
        if task_id in download_tasks:
            download_tasks[task_id].status = "processing"
            download_tasks[task_id].progress = 10.0
        
        # 更新项目状态和进度
        await update_project_download_progress(project_id, 10.0, "正在获取视频信息...")
        
        # 使用yt-dlp下载视频
        import yt_dlp
        import asyncio
        from ...core.config import get_data_directory
        from ...core.path_utils import get_project_raw_directory

        data_dir = get_data_directory()
        download_dir = data_dir / "temp"
        download_dir.mkdir(exist_ok=True)

        existing_video = get_project_raw_directory(project_id) / "input.mp4"
        subtitle_path = ""

        if existing_video.exists() and existing_video.stat().st_size > 1024 * 1024 and _video_meets_1080p60(existing_video):
            video_path = str(existing_video)
            logger.info(f"Using already-downloaded 1080p60 video: {video_path}")
            await update_project_download_progress(project_id, 60.0, "Video already on disk, generating subtitles…")
        else:
            data_dir = get_data_directory()
            download_dir = data_dir / "temp"
            download_dir.mkdir(exist_ok=True)

            await update_project_download_progress(project_id, 30.0, "正在下载视频...")

            # Download the video only. YouTube auto-captions often 429 and abort the
            # whole job; Whisper generates the SRT after the file is on disk.
            ydl_opts = {
                'format': YOUTUBE_VIDEO_FORMAT,
                'format_sort': ['res:1080', 'fps', 'codec:h264:vp9', 'size'],
                'merge_output_format': 'mp4',
                'writesubtitles': False,
                'writeautomaticsub': False,
                'outtmpl': str(download_dir / f'{project_id}_%(id)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
                'no_warnings': False,
                'ignoreconfig': True,
                'config_locations': [],
                'cachedir': False,
                'retries': 10,
                'fragment_retries': 10,
                'concurrent_fragment_downloads': 4,
                'js_runtimes': {'node': {}},
                'remote_components': ['ejs:github'],
                'progress_hooks': [_make_download_progress_hook(project_id)],
            }
            ydl_opts.setdefault('extractor_args', {}).setdefault('youtube', {})['player_client'] = (
                YOUTUBE_PLAYER_CLIENTS
            )

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, lambda: _yt_dlp_with_cookie_fallback(request.url, ydl_opts, request.browser, download=True)
            )

            video_files = []
            for pattern in (f"{project_id}_*.mp4", f"{project_id}_*.mkv", f"{project_id}_*.webm"):
                video_files.extend(p for p in download_dir.glob(pattern) if p.is_file())
            subtitle_files = list(download_dir.glob(f"{project_id}_*.srt"))

            if not video_files:
                raise Exception("Video file was not downloaded")

            video_path = str(max(video_files, key=lambda p: p.stat().st_size))
            subtitle_path = str(subtitle_files[0]) if subtitle_files else ""
            await update_project_download_progress(project_id, 60.0, "视频下载完成，正在处理字幕...")

        if task_id in download_tasks:
            download_tasks[task_id].progress = 80.0
        
        # 如果没有字幕文件，优先使用Whisper生成字幕
        if not subtitle_path:
            logger.info("优先使用Whisper生成高质量字幕")
            # 更新项目进度
            await update_project_download_progress(project_id, 70.0, "正在使用Whisper生成字幕...")
            
            try:
                from ...utils.speech_recognizer import generate_subtitle_for_video, SpeechRecognitionError
                from ...core.path_utils import get_project_raw_directory as _raw_dir
                video_file_path = Path(video_path)
                srt_out = _raw_dir(project_id) / "input.srt"
                model = "base"
                language = "en"

                logger.info(f"使用Whisper生成字幕 - 语言: {language}, 模型: {model}")
                loop = asyncio.get_event_loop()
                generated_subtitle = await loop.run_in_executor(
                    None,
                    lambda: generate_subtitle_for_video(
                        video_file_path,
                        output_path=srt_out,
                        language=language,
                        model=model,
                    ),
                )
                subtitle_path = str(generated_subtitle)
                logger.info(f"Whisper字幕生成成功: {subtitle_path}")
                
                # 更新项目进度
                await update_project_download_progress(project_id, 90.0, "字幕生成完成，正在准备处理...")
                
            except SpeechRecognitionError as e:
                logger.error(f"Whisper字幕生成失败: {e}")
                subtitle_path = None
            except Exception as e:
                logger.error(f"生成字幕过程中发生未知错误: {e}")
                subtitle_path = None
        
        logger.info(f"下载完成 - 视频文件: {video_path}, 字幕文件: {subtitle_path}")
        
        # 更新项目信息（项目已在开始时创建）
        from ...services.project_service import ProjectService
        from ...core.database import SessionLocal
        
        db = SessionLocal()
        try:
            project_service = ProjectService(db)
            
            # 获取已创建的项目
            project = project_service.get(project_id)
            if not project:
                raise Exception(f"项目 {project_id} 不存在")
            
            # 更新项目信息
            project.description = f"从YouTube下载: {request.project_name}"
            # 注意：不要在这里设置video_path，等文件移动完成后再设置
            
            # 更新项目设置
            if not project.processing_config:
                project.processing_config = {}
            
            project.processing_config.update({
                "youtube_info": {
                    "title": request.project_name,
                    "uploader": "YouTube",
                    "duration": 0,
                    "view_count": 0,
                    "like_count": 0
                },
                "subtitle_path": subtitle_path,
                "download_status": "completed",
                "download_progress": 100.0
            })
            
            # 移动文件到项目目录
            from ...core.path_utils import get_project_directory
            project_dir = get_project_directory(project_id)
            raw_dir = project_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            
            import shutil

            if video_path:
                video_file_path = Path(video_path)
                if video_file_path.exists():
                    new_video_path = raw_dir / "input.mp4"
                    if video_file_path.resolve() != new_video_path.resolve():
                        shutil.move(str(video_file_path), str(new_video_path))
                        logger.info(f"视频文件已移动到: {new_video_path}")
                    project.video_path = str(new_video_path)

            if subtitle_path:
                subtitle_file_path = Path(subtitle_path)
                if subtitle_file_path.exists():
                    new_subtitle_path = raw_dir / "input.srt"
                    if subtitle_file_path.resolve() != new_subtitle_path.resolve():
                        shutil.move(str(subtitle_file_path), str(new_subtitle_path))
                        logger.info(f"字幕文件已移动到: {new_subtitle_path}")
                    if not project.processing_config:
                        project.processing_config = {}
                    project.processing_config["subtitle_path"] = str(new_subtitle_path)
            
            # 保存项目更新
            db.commit()
            
            # 检查字幕文件是否存在，如果不存在则标记项目为失败
            srt_file_path = raw_dir / "input.srt"
            if not srt_file_path.exists():
                logger.error(f"字幕文件不存在: {srt_file_path}，项目将标记为失败状态")
                from ...schemas.project import ProjectStatus
                project.status = ProjectStatus.FAILED
                if not project.processing_config:
                    project.processing_config = {}
                project.processing_config["error_message"] = "字幕文件不存在且Whisper生成失败"
                db.commit()
                
                # 更新任务状态为失败
                if task_id in download_tasks:
                    download_tasks[task_id].status = "failed"
                    download_tasks[task_id].error_message = "字幕文件不存在且Whisper生成失败"
                    download_tasks[task_id].progress = 0.0
                    download_tasks[task_id].project_id = str(project.id)
                    download_tasks[task_id].updated_at = datetime.now().isoformat()
                
                # 更新项目下载进度为失败
                await update_project_download_progress(project_id, 0.0, "下载失败：字幕文件不存在")
                
                logger.info(f"YouTube下载任务失败: {task_id}, 项目ID: {project.id}, 原因: 字幕文件不存在")
                return
            
            # 更新项目下载进度为完成
            await update_project_download_progress(project_id, 100.0, "下载完成，准备开始处理")
            
            # 更新任务状态
            if task_id in download_tasks:
                download_tasks[task_id].status = "completed"
                download_tasks[task_id].progress = 100.0
                download_tasks[task_id].project_id = str(project.id)
                download_tasks[task_id].updated_at = datetime.now().isoformat()
            
            logger.info(f"YouTube下载任务完成: {task_id}, 项目ID: {project.id}")
            
            # 自动启动处理流程
            try:
                # 更新项目状态为等待处理
                from ...schemas.project import ProjectStatus
                project.status = ProjectStatus.PENDING  # 改为PENDING，让自动化服务启动
                db.commit()
                
                logger.info(f"YouTube项目 {project.id} 下载完成，等待自动化流水线启动")
                
                # 异步启动自动化流水线
                import asyncio
                from ...services.auto_pipeline_service import auto_pipeline_service
                
                # 使用create_task在已运行的事件循环中执行
                try:
                    loop = asyncio.get_running_loop()
                    # 在已运行的事件循环中创建任务
                    task = loop.create_task(
                        auto_pipeline_service.auto_start_pipeline(str(project.id))
                    )
                    # 等待任务完成
                    pipeline_result = await task
                except RuntimeError:
                    # 如果没有运行的事件循环，创建新的
                    pipeline_result = await auto_pipeline_service.auto_start_pipeline(str(project.id))
                
                if pipeline_result['status'] == 'started':
                    logger.info(f"YouTube项目 {project.id} 自动化流水线已启动: {pipeline_result}")
                else:
                    logger.warning(f"YouTube项目 {project.id} 自动化流水线启动结果: {pipeline_result}")
                
            except Exception as e:
                logger.error(f"启动YouTube项目 {project.id} 自动化流水线失败: {str(e)}")
                # 即使处理启动失败，也要返回下载成功
                # 用户可以通过重试按钮重新启动处理
            
        except Exception as e:
            logger.error(f"创建项目失败: {str(e)}")
            # 即使处理启动失败，也要返回下载成功
            # 用户可以通过重试按钮重新启动处理
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"处理下载任务失败: {str(e)}")
        if task_id in download_tasks:
            download_tasks[task_id].status = "failed"
            download_tasks[task_id].error_message = str(e)
            download_tasks[task_id].progress = 0.0
            download_tasks[task_id].updated_at = datetime.now().isoformat()
        try:
            from ...core.database import SessionLocal
            from ...schemas.project import ProjectStatus
            from sqlalchemy.orm.attributes import flag_modified
            db = SessionLocal()
            try:
                from ...services.project_service import ProjectService
                project = ProjectService(db).get(project_id)
                if project:
                    project.status = ProjectStatus.FAILED
                    config = dict(project.processing_config or {})
                    config.update({
                        "download_progress": 0.0,
                        "download_message": f"Download failed: {e}",
                        "error_message": str(e),
                    })
                    project.processing_config = config
                    flag_modified(project, "processing_config")
                    db.commit()
            finally:
                db.close()
        except Exception as mark_err:
            logger.error(f"Failed to mark project as failed: {mark_err}")


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
    import asyncio
    logger.info("尝试下载不同格式的YouTube字幕...")
    
    formats = ['srt', 'vtt', 'json3']
    
    for fmt in formats:
        try:
            ydl_opts = {
                'format': YOUTUBE_VIDEO_FORMAT,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'zh-Hans', 'zh'],
                'subtitlesformat': fmt,
                'outtmpl': str(download_dir / f'subtitle_%(title)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
                'ignoreconfig': True,
                'config_locations': [],
            }
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, lambda: _yt_dlp_with_cookie_fallback(url, ydl_opts, browser, download=True)
            )
            
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
    import asyncio
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
                'format': YOUTUBE_VIDEO_FORMAT,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': langs,
                'subtitlesformat': 'srt',
                'outtmpl': str(download_dir / f'lang_%(title)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
                'ignoreconfig': True,
                'config_locations': [],
            }
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, lambda: _yt_dlp_with_cookie_fallback(url, ydl_opts, browser, download=True)
            )
            
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
    import asyncio
    logger.info("尝试从YouTube视频元数据提取字幕信息...")
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreconfig': True,
            'config_locations': [],
        }
        
        loop = asyncio.get_event_loop()
        info_dict = await loop.run_in_executor(
            None, lambda: _yt_dlp_with_cookie_fallback(url, ydl_opts, browser, download=False)
        )
        
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
