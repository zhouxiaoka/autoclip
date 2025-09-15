"""
改进的YouTube下载处理
解决403错误和异常处理问题
"""

import logging
import asyncio
from typing import Optional, Dict, Any
from pathlib import Path
import yt_dlp
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

class YouTubeDownloadError(Exception):
    """YouTube下载异常"""
    pass

class YouTubeDownloader:
    """改进的YouTube下载器"""
    
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 5  # 秒
        
    async def download_video(
        self, 
        url: str, 
        output_dir: Path, 
        browser: Optional[str] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        下载YouTube视频
        
        Args:
            url: YouTube视频URL
            output_dir: 输出目录
            browser: 浏览器类型（用于cookies）
            retry_count: 当前重试次数
            
        Returns:
            包含下载信息的字典
        """
        
        try:
            # 构建下载选项
            ydl_opts = self._build_download_options(output_dir, browser)
            
            # 执行下载
            def download_sync():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # 先获取视频信息
                    info = ydl.extract_info(url, download=False)
                    
                    # 检查视频是否可下载
                    if not self._is_video_downloadable(info):
                        raise YouTubeDownloadError(f"视频不可下载: {info.get('title', 'Unknown')}")
                    
                    # 执行下载
                    ydl.download([url])
                    
                    return info
            
            # 在异步环境中执行同步下载
            loop = asyncio.get_event_loop()
            video_info = await loop.run_in_executor(None, download_sync)
            
            # 查找下载的文件
            video_files = list(output_dir.glob("*.mp4"))
            subtitle_files = list(output_dir.glob("*.srt"))
            
            if not video_files:
                raise YouTubeDownloadError("视频文件下载失败")
            
            return {
                "success": True,
                "video_file": video_files[0],
                "subtitle_file": subtitle_files[0] if subtitle_files else None,
                "video_info": video_info
            }
            
        except yt_dlp.DownloadError as e:
            error_msg = str(e)
            logger.error(f"YouTube下载错误: {error_msg}")
            
            # 分析错误类型
            if "HTTP Error 403" in error_msg:
                if retry_count < self.max_retries:
                    logger.info(f"403错误，尝试重试 ({retry_count + 1}/{self.max_retries})")
                    await asyncio.sleep(self.retry_delay)
                    return await self.download_video(url, output_dir, browser, retry_count + 1)
                else:
                    raise YouTubeDownloadError("视频访问被拒绝，可能需要登录或视频受保护")
            elif "Video unavailable" in error_msg:
                raise YouTubeDownloadError("视频不可用，可能已被删除或设为私有")
            elif "Private video" in error_msg:
                raise YouTubeDownloadError("视频为私有，无法下载")
            else:
                raise YouTubeDownloadError(f"下载失败: {error_msg}")
                
        except Exception as e:
            logger.error(f"下载过程中发生未知错误: {e}")
            raise YouTubeDownloadError(f"下载失败: {str(e)}")
    
    def _build_download_options(self, output_dir: Path, browser: Optional[str] = None) -> Dict[str, Any]:
        """构建下载选项"""
        
        options = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'zh-Hans', 'zh', 'en-US', 'auto'],
            'subtitlesformat': 'srt',
            'outtmpl': str(output_dir / '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True,
            'no_warnings': False,
            # 添加User-Agent以避免被检测
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
            # 添加重试机制
            'retries': 3,
            'fragment_retries': 3,
            # 设置超时
            'socket_timeout': 30,
            'retries': 3,
        }
        
        # 如果指定了浏览器，使用cookies
        if browser:
            options['cookiesfrombrowser'] = (browser.lower(),)
        
        return options
    
    def _is_video_downloadable(self, video_info: Dict[str, Any]) -> bool:
        """检查视频是否可下载"""
        
        # 检查视频状态
        if video_info.get('availability') == 'private':
            return False
        
        if video_info.get('availability') == 'premium_only':
            return False
        
        # 检查是否有可用的格式
        formats = video_info.get('formats', [])
        if not formats:
            return False
        
        # 检查是否有视频格式
        video_formats = [f for f in formats if f.get('vcodec') != 'none']
        if not video_formats:
            return False
        
        return True

async def improved_youtube_download_task(
    task_id: str, 
    url: str, 
    project_name: str, 
    output_dir: Path,
    browser: Optional[str] = None
) -> Dict[str, Any]:
    """
    改进的YouTube下载任务处理
    
    Args:
        task_id: 任务ID
        url: YouTube视频URL
        project_name: 项目名称
        output_dir: 输出目录
        browser: 浏览器类型
        
    Returns:
        下载结果
    """
    
    downloader = YouTubeDownloader()
    
    try:
        logger.info(f"开始下载YouTube视频: {url}")
        
        # 创建输出目录
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 执行下载
        result = await downloader.download_video(url, output_dir, browser)
        
        logger.info(f"YouTube视频下载成功: {result['video_file']}")
        
        return {
            "success": True,
            "task_id": task_id,
            "video_file": result["video_file"],
            "subtitle_file": result["subtitle_file"],
            "video_info": result["video_info"]
        }
        
    except YouTubeDownloadError as e:
        logger.error(f"YouTube下载失败: {e}")
        return {
            "success": False,
            "task_id": task_id,
            "error": str(e),
            "error_type": "download_error"
        }
        
    except Exception as e:
        logger.error(f"YouTube下载过程中发生未知错误: {e}")
        return {
            "success": False,
            "task_id": task_id,
            "error": str(e),
            "error_type": "unknown_error"
        }

# 使用示例
async def main():
    """测试改进的下载功能"""
    
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    output_dir = Path("/tmp/youtube_test")
    task_id = str(uuid.uuid4())
    
    result = await improved_youtube_download_task(
        task_id=task_id,
        url=test_url,
        project_name="测试项目",
        output_dir=output_dir
    )
    
    if result["success"]:
        print(f"✅ 下载成功: {result['video_file']}")
    else:
        print(f"❌ 下载失败: {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())

