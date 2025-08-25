#!/usr/bin/env python3
"""
字幕下载诊断工具
帮助用户排查B站和YouTube字幕下载问题
"""

import sys
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置环境变量
import os
os.environ['PYTHONPATH'] = str(project_root)

# 添加backend目录到路径
backend_dir = project_root / "backend"
sys.path.insert(0, str(backend_dir))

from backend.utils.bilibili_downloader import BilibiliDownloader, get_bilibili_video_info
from backend.utils.speech_recognizer import get_available_speech_recognition_methods, SpeechRecognitionError
import yt_dlp

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SubtitleDownloadDiagnostic:
    """字幕下载诊断工具"""
    
    def __init__(self):
        self.results = {}
    
    async def diagnose_bilibili_subtitle(self, url: str, browser: Optional[str] = None) -> Dict[str, Any]:
        """诊断B站字幕下载问题"""
        logger.info(f"开始诊断B站字幕下载: {url}")
        
        result = {
            "url": url,
            "platform": "bilibili",
            "video_info": None,
            "subtitle_availability": {},
            "download_attempts": [],
            "recommendations": []
        }
        
        try:
            # 1. 获取视频信息
            logger.info("1. 获取视频信息...")
            video_info = await get_bilibili_video_info(url, browser)
            result["video_info"] = {
                "title": video_info.title,
                "duration": video_info.duration,
                "uploader": video_info.uploader,
                "view_count": video_info.view_count
            }
            logger.info(f"✅ 视频信息获取成功: {video_info.title}")
            
            # 2. 检查字幕可用性
            logger.info("2. 检查字幕可用性...")
            subtitle_check = await self._check_bilibili_subtitle_availability(url, browser)
            result["subtitle_availability"] = subtitle_check
            
            # 3. 尝试不同的下载策略
            logger.info("3. 尝试不同的下载策略...")
            download_attempts = await self._test_bilibili_download_strategies(url, browser)
            result["download_attempts"] = download_attempts
            
            # 4. 生成建议
            result["recommendations"] = self._generate_bilibili_recommendations(subtitle_check, download_attempts)
            
        except Exception as e:
            logger.error(f"❌ B站诊断失败: {e}")
            result["error"] = str(e)
            result["recommendations"].append(f"诊断过程出错: {e}")
        
        return result
    
    async def diagnose_youtube_subtitle(self, url: str, browser: Optional[str] = None) -> Dict[str, Any]:
        """诊断YouTube字幕下载问题"""
        logger.info(f"开始诊断YouTube字幕下载: {url}")
        
        result = {
            "url": url,
            "platform": "youtube",
            "video_info": None,
            "subtitle_availability": {},
            "download_attempts": [],
            "recommendations": []
        }
        
        try:
            # 1. 获取视频信息
            logger.info("1. 获取视频信息...")
            video_info = await self._get_youtube_video_info(url, browser)
            result["video_info"] = video_info
            logger.info(f"✅ 视频信息获取成功: {video_info.get('title', 'Unknown')}")
            
            # 2. 检查字幕可用性
            logger.info("2. 检查字幕可用性...")
            subtitle_check = await self._check_youtube_subtitle_availability(url, browser)
            result["subtitle_availability"] = subtitle_check
            
            # 3. 尝试不同的下载策略
            logger.info("3. 尝试不同的下载策略...")
            download_attempts = await self._test_youtube_download_strategies(url, browser)
            result["download_attempts"] = download_attempts
            
            # 4. 生成建议
            result["recommendations"] = self._generate_youtube_recommendations(subtitle_check, download_attempts)
            
        except Exception as e:
            logger.error(f"❌ YouTube诊断失败: {e}")
            result["error"] = str(e)
            result["recommendations"].append(f"诊断过程出错: {e}")
        
        return result
    
    async def _check_bilibili_subtitle_availability(self, url: str, browser: Optional[str] = None) -> Dict[str, Any]:
        """检查B站字幕可用性"""
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
            
            subtitles = info_dict.get('subtitles', {})
            auto_subtitles = info_dict.get('automatic_captions', {})
            
            return {
                "manual_subtitles": list(subtitles.keys()) if subtitles else [],
                "auto_subtitles": list(auto_subtitles.keys()) if auto_subtitles else [],
                "requires_login": len(subtitles) == 0 and len(auto_subtitles) == 0,
                "total_subtitle_tracks": len(subtitles) + len(auto_subtitles)
            }
            
        except Exception as e:
            logger.error(f"检查B站字幕可用性失败: {e}")
            return {"error": str(e)}
    
    async def _check_youtube_subtitle_availability(self, url: str, browser: Optional[str] = None) -> Dict[str, Any]:
        """检查YouTube字幕可用性"""
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
            
            subtitles = info_dict.get('subtitles', {})
            auto_subtitles = info_dict.get('automatic_captions', {})
            
            return {
                "manual_subtitles": list(subtitles.keys()) if subtitles else [],
                "auto_subtitles": list(auto_subtitles.keys()) if auto_subtitles else [],
                "total_subtitle_tracks": len(subtitles) + len(auto_subtitles)
            }
            
        except Exception as e:
            logger.error(f"检查YouTube字幕可用性失败: {e}")
            return {"error": str(e)}
    
    async def _test_bilibili_download_strategies(self, url: str, browser: Optional[str] = None) -> list:
        """测试B站不同的下载策略"""
        strategies = [
            ("默认策略", {"subtitleslangs": ["ai-zh"], "writeautomaticsub": False}),
            ("多语言策略", {"subtitleslangs": ["ai-zh", "zh-Hans", "zh", "en"], "writeautomaticsub": True}),
            ("无cookies策略", {"subtitleslangs": ["zh-Hans", "zh"], "writeautomaticsub": True, "cookies": None}),
        ]
        
        results = []
        temp_dir = Path("temp_diagnostic")
        temp_dir.mkdir(exist_ok=True)
        
        for name, opts in strategies:
            try:
                logger.info(f"测试策略: {name}")
                
                ydl_opts = {
                    'format': 'best[ext=mp4]/best',
                    'writesubtitles': True,
                    'outtmpl': str(temp_dir / f'test_{name}.%(ext)s'),
                    'noplaylist': True,
                    'quiet': True,
                    **opts
                }
                
                if browser and opts.get("cookies") is not None:
                    ydl_opts['cookiesfrombrowser'] = (browser.lower(),)
                
                def download_sync(url, ydl_opts):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.download([url])
                
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, download_sync, url, ydl_opts)
                
                # 检查是否下载了字幕文件
                subtitle_files = list(temp_dir.glob("*.srt"))
                success = len(subtitle_files) > 0
                
                results.append({
                    "strategy": name,
                    "success": success,
                    "subtitle_files": [f.name for f in subtitle_files],
                    "options": opts
                })
                
                logger.info(f"✅ 策略 {name}: {'成功' if success else '失败'}")
                
            except Exception as e:
                logger.error(f"❌ 策略 {name} 失败: {e}")
                results.append({
                    "strategy": name,
                    "success": False,
                    "error": str(e),
                    "options": opts
                })
        
        # 清理临时文件
        for file in temp_dir.glob("*"):
            file.unlink()
        temp_dir.rmdir()
        
        return results
    
    async def _test_youtube_download_strategies(self, url: str, browser: Optional[str] = None) -> list:
        """测试YouTube不同的下载策略"""
        strategies = [
            ("默认策略", {"subtitleslangs": ["en", "zh-Hans"], "writeautomaticsub": True}),
            ("多语言策略", {"subtitleslangs": ["en", "zh-Hans", "zh", "ja", "ko"], "writeautomaticsub": True}),
            ("多格式策略", {"subtitleslangs": ["en", "zh-Hans"], "subtitlesformat": "vtt", "writeautomaticsub": True}),
        ]
        
        results = []
        temp_dir = Path("temp_diagnostic")
        temp_dir.mkdir(exist_ok=True)
        
        for name, opts in strategies:
            try:
                logger.info(f"测试策略: {name}")
                
                ydl_opts = {
                    'format': 'best[ext=mp4]/best',
                    'writesubtitles': True,
                    'outtmpl': str(temp_dir / f'test_{name}.%(ext)s'),
                    'noplaylist': True,
                    'quiet': True,
                    **opts
                }
                
                if browser:
                    ydl_opts['cookiesfrombrowser'] = (browser.lower(),)
                
                def download_sync(url, ydl_opts):
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        return ydl.download([url])
                
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, download_sync, url, ydl_opts)
                
                # 检查是否下载了字幕文件
                subtitle_files = list(temp_dir.glob("*.srt")) + list(temp_dir.glob("*.vtt"))
                success = len(subtitle_files) > 0
                
                results.append({
                    "strategy": name,
                    "success": success,
                    "subtitle_files": [f.name for f in subtitle_files],
                    "options": opts
                })
                
                logger.info(f"✅ 策略 {name}: {'成功' if success else '失败'}")
                
            except Exception as e:
                logger.error(f"❌ 策略 {name} 失败: {e}")
                results.append({
                    "strategy": name,
                    "success": False,
                    "error": str(e),
                    "options": opts
                })
        
        # 清理临时文件
        for file in temp_dir.glob("*"):
            file.unlink()
        temp_dir.rmdir()
        
        return results
    
    async def _get_youtube_video_info(self, url: str, browser: Optional[str] = None) -> Dict[str, Any]:
        """获取YouTube视频信息"""
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
            
            return {
                "title": info_dict.get('title', 'Unknown'),
                "duration": info_dict.get('duration', 0),
                "uploader": info_dict.get('uploader', 'Unknown'),
                "view_count": info_dict.get('view_count', 0),
                "upload_date": info_dict.get('upload_date', ''),
            }
            
        except Exception as e:
            logger.error(f"获取YouTube视频信息失败: {e}")
            return {"error": str(e)}
    
    def _generate_bilibili_recommendations(self, subtitle_check: Dict, download_attempts: list) -> list:
        """生成B站字幕下载建议"""
        recommendations = []
        
        if subtitle_check.get("requires_login", False):
            recommendations.append("🔐 需要登录才能下载字幕，请选择浏览器并确保已登录B站")
        
        if subtitle_check.get("total_subtitle_tracks", 0) == 0:
            recommendations.append("⚠️ 该视频可能没有字幕，建议使用语音识别生成字幕")
        
        successful_strategies = [s for s in download_attempts if s.get("success", False)]
        if successful_strategies:
            best_strategy = successful_strategies[0]
            recommendations.append(f"✅ 推荐使用策略: {best_strategy['strategy']}")
        else:
            recommendations.append("❌ 所有下载策略都失败，建议检查网络连接和视频链接")
        
        return recommendations
    
    def _generate_youtube_recommendations(self, subtitle_check: Dict, download_attempts: list) -> list:
        """生成YouTube字幕下载建议"""
        recommendations = []
        
        if subtitle_check.get("total_subtitle_tracks", 0) == 0:
            recommendations.append("⚠️ 该视频可能没有字幕，建议使用语音识别生成字幕")
        
        successful_strategies = [s for s in download_attempts if s.get("success", False)]
        if successful_strategies:
            best_strategy = successful_strategies[0]
            recommendations.append(f"✅ 推荐使用策略: {best_strategy['strategy']}")
        else:
            recommendations.append("❌ 所有下载策略都失败，建议检查网络连接和视频链接")
        
        return recommendations
    
    def check_speech_recognition_setup(self) -> Dict[str, Any]:
        """检查语音识别设置"""
        logger.info("检查语音识别设置...")
        
        available_methods = get_available_speech_recognition_methods()
        
        result = {
            "available_methods": available_methods,
            "recommendations": []
        }
        
        if not any(available_methods.values()):
            result["recommendations"].append("❌ 没有可用的语音识别服务")
            result["recommendations"].append("💡 建议安装Whisper: pip install openai-whisper")
            result["recommendations"].append("💡 同时安装ffmpeg: brew install ffmpeg (macOS) 或 sudo apt install ffmpeg (Ubuntu)")
        else:
            available = [k for k, v in available_methods.items() if v]
            result["recommendations"].append(f"✅ 可用的语音识别服务: {', '.join(available)}")
        
        return result

async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法:")
        print("  python debug_subtitle_download.py <url> [browser]")
        print("  python debug_subtitle_download.py --check-speech")
        print("")
        print("示例:")
        print("  python debug_subtitle_download.py https://www.bilibili.com/video/BV1xx411c7mu")
        print("  python debug_subtitle_download.py https://www.youtube.com/watch?v=dQw4w9WgXcQ chrome")
        print("  python debug_subtitle_download.py --check-speech")
        return
    
    diagnostic = SubtitleDownloadDiagnostic()
    
    if sys.argv[1] == "--check-speech":
        # 检查语音识别设置
        speech_result = diagnostic.check_speech_recognition_setup()
        print("\n🎤 语音识别设置检查结果:")
        print(json.dumps(speech_result, indent=2, ensure_ascii=False))
        return
    
    url = sys.argv[1]
    browser = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"🔍 开始诊断字幕下载问题...")
    print(f"URL: {url}")
    print(f"浏览器: {browser or '未指定'}")
    print("=" * 50)
    
    # 检查语音识别设置
    speech_result = diagnostic.check_speech_recognition_setup()
    print("\n🎤 语音识别设置:")
    print(json.dumps(speech_result, indent=2, ensure_ascii=False))
    
    # 根据URL类型选择诊断方法
    if "bilibili.com" in url or "b23.tv" in url:
        result = await diagnostic.diagnose_bilibili_subtitle(url, browser)
    elif "youtube.com" in url or "youtu.be" in url:
        result = await diagnostic.diagnose_youtube_subtitle(url, browser)
    else:
        print("❌ 不支持的URL格式，请提供B站或YouTube链接")
        return
    
    print("\n📊 诊断结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 保存结果到文件
    output_file = f"subtitle_diagnostic_{result['platform']}_{Path(url).name}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 诊断结果已保存到: {output_file}")

if __name__ == "__main__":
    asyncio.run(main())

