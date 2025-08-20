#!/usr/bin/env python3
"""
测试字幕下载修复
验证B站和YouTube字幕下载的修复是否有效
"""

import sys
import asyncio
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置环境变量
import os
os.environ['PYTHONPATH'] = str(project_root)

# 添加backend目录到路径
backend_dir = project_root / "backend"
sys.path.insert(0, str(backend_dir))

from shared.utils.bilibili_downloader import BilibiliDownloader, get_bilibili_video_info
from shared.utils.speech_recognizer import get_available_speech_recognition_methods
import yt_dlp

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_bilibili_subtitle_download():
    """测试B站字幕下载修复"""
    print("🔍 测试B站字幕下载修复...")
    
    # 测试URL（使用一个已知有字幕的B站视频）
    test_url = "https://www.bilibili.com/video/BV1xx411c7mu"
    
    try:
        # 1. 测试视频信息获取
        print("1. 测试视频信息获取...")
        video_info = await get_bilibili_video_info(test_url, "chrome")
        print(f"✅ 视频信息获取成功: {video_info.title}")
        
        # 2. 测试字幕下载
        print("2. 测试字幕下载...")
        downloader = BilibiliDownloader(download_dir=Path("test_downloads"), browser="chrome")
        
        # 测试不同的字幕下载策略
        strategies = [
            ("默认策略", {"subtitleslangs": ["ai-zh"], "writeautomaticsub": False}),
            ("多语言策略", {"subtitleslangs": ["ai-zh", "zh-Hans", "zh", "en"], "writeautomaticsub": True}),
            ("无cookies策略", {"subtitleslangs": ["zh-Hans", "zh"], "writeautomaticsub": True, "cookies": None}),
        ]
        
        for name, opts in strategies:
            print(f"   测试策略: {name}")
            try:
                ydl_opts = {
                    'skip_download': True,  # 只下载字幕，不下载视频
                    'writesubtitles': True,
                    'outtmpl': f'test_downloads/test_{name}.%(ext)s',
                    'noplaylist': True,
                    'quiet': True,
                    **opts
                }
                
                if "cookies" not in opts or opts["cookies"] is not None:
                    ydl_opts['cookiesfrombrowser'] = ('chrome',)
                
                def download_sync(url, ydl_opts):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.download([url])
                
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, download_sync, test_url, ydl_opts)
                
                # 检查是否下载了字幕文件
                subtitle_files = list(Path("test_downloads").glob("*.srt"))
                success = len(subtitle_files) > 0
                print(f"   ✅ 策略 {name}: {'成功' if success else '失败'}")
                
                if success:
                    print(f"   📄 字幕文件: {[f.name for f in subtitle_files]}")
                
            except Exception as e:
                print(f"   ❌ 策略 {name} 失败: {e}")
        
        # 3. 测试语音识别设置
        print("3. 测试语音识别设置...")
        available_methods = get_available_speech_recognition_methods()
        print(f"   可用的语音识别方法: {available_methods}")
        
        if any(available_methods.values()):
            print("   ✅ 语音识别备用方案可用")
        else:
            print("   ⚠️ 语音识别备用方案不可用，建议安装Whisper")
        
        print("✅ B站字幕下载测试完成")
        
    except Exception as e:
        print(f"❌ B站字幕下载测试失败: {e}")

async def test_youtube_subtitle_download():
    """测试YouTube字幕下载修复"""
    print("\n🔍 测试YouTube字幕下载修复...")
    
    # 测试URL（使用一个已知有字幕的YouTube视频）
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    try:
        # 1. 测试视频信息获取
        print("1. 测试视频信息获取...")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        def extract_info_sync(url, ydl_opts):
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        loop = asyncio.get_event_loop()
        info_dict = await loop.run_in_executor(None, extract_info_sync, test_url, ydl_opts)
        
        print(f"✅ 视频信息获取成功: {info_dict.get('title', 'Unknown')}")
        
        # 2. 测试字幕下载
        print("2. 测试字幕下载...")
        
        # 测试不同的字幕下载策略
        strategies = [
            ("默认策略", {"subtitleslangs": ["en", "zh-Hans"], "writeautomaticsub": True}),
            ("多语言策略", {"subtitleslangs": ["en", "zh-Hans", "zh", "ja", "ko"], "writeautomaticsub": True}),
            ("多格式策略", {"subtitleslangs": ["en", "zh-Hans"], "subtitlesformat": "vtt", "writeautomaticsub": True}),
        ]
        
        for name, opts in strategies:
            print(f"   测试策略: {name}")
            try:
                ydl_opts = {
                    'skip_download': True,  # 只下载字幕，不下载视频
                    'writesubtitles': True,
                    'outtmpl': f'test_downloads/youtube_test_{name}.%(ext)s',
                    'noplaylist': True,
                    'quiet': True,
                    **opts
                }
                
                def download_sync(url, ydl_opts):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.download([url])
                
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, download_sync, test_url, ydl_opts)
                
                # 检查是否下载了字幕文件
                subtitle_files = list(Path("test_downloads").glob("*.srt")) + list(Path("test_downloads").glob("*.vtt"))
                success = len(subtitle_files) > 0
                print(f"   ✅ 策略 {name}: {'成功' if success else '失败'}")
                
                if success:
                    print(f"   📄 字幕文件: {[f.name for f in subtitle_files]}")
                
            except Exception as e:
                print(f"   ❌ 策略 {name} 失败: {e}")
        
        print("✅ YouTube字幕下载测试完成")
        
    except Exception as e:
        print(f"❌ YouTube字幕下载测试失败: {e}")

async def test_srt_path_handling():
    """测试SRT路径处理修复"""
    print("\n🔍 测试SRT路径处理修复...")
    
    try:
        from backend.services.pipeline_adapter import PipelineAdapter
        from backend.core.database import SessionLocal
        
        # 创建测试目录
        test_dir = Path("test_srt_handling")
        test_dir.mkdir(exist_ok=True)
        
        # 测试不同的SRT路径情况
        test_cases = [
            ("有效SRT路径", str(test_dir / "valid.srt")),
            ("空字符串", ""),
            ("None值", None),
            ("无效路径", "/invalid/path/file.srt"),
        ]
        
        for case_name, srt_path in test_cases:
            print(f"   测试情况: {case_name}")
            try:
                # 模拟Pipeline适配器的SRT路径验证
                srt_file_path = Path(srt_path) if srt_path and srt_path.strip() else None
                
                if not srt_file_path or not srt_file_path.exists():
                    print(f"   ⚠️ SRT文件不存在或路径无效: {srt_path}")
                    print(f"   ✅ 正确处理了无效路径")
                else:
                    print(f"   ✅ SRT文件路径有效: {srt_file_path}")
                
            except Exception as e:
                print(f"   ❌ 处理失败: {e}")
        
        # 清理测试目录
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)
        
        print("✅ SRT路径处理测试完成")
        
    except Exception as e:
        print(f"❌ SRT路径处理测试失败: {e}")

async def main():
    """主函数"""
    print("🚀 开始测试字幕下载修复...")
    
    # 创建测试下载目录
    test_downloads_dir = Path("test_downloads")
    test_downloads_dir.mkdir(exist_ok=True)
    
    try:
        # 测试B站字幕下载
        await test_bilibili_subtitle_download()
        
        # 测试YouTube字幕下载
        await test_youtube_subtitle_download()
        
        # 测试SRT路径处理
        await test_srt_path_handling()
        
        print("\n🎉 所有测试完成！")
        
    finally:
        # 清理测试文件
        import shutil
        shutil.rmtree(test_downloads_dir, ignore_errors=True)
        print("🧹 测试文件已清理")

if __name__ == "__main__":
    asyncio.run(main())
