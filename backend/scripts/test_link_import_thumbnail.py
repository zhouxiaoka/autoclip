#!/usr/bin/env python3
"""
测试链接导入项目缩略图功能
"""

import sys
import asyncio
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.utils.bilibili_downloader import BilibiliDownloader
import requests
import base64

async def test_bilibili_thumbnail_extraction():
    """测试B站缩略图提取功能"""
    print("🧪 测试B站缩略图提取功能...")
    
    # 使用一个公开的B站视频链接进行测试
    test_url = "https://www.bilibili.com/video/BV1LSegzbEp9/"
    
    try:
        # 创建下载器
        downloader = BilibiliDownloader()
        
        # 获取视频信息
        video_info = await downloader.get_video_info(test_url)
        
        print(f"✅ 视频信息获取成功:")
        print(f"   标题: {video_info.title}")
        print(f"   上传者: {video_info.uploader}")
        print(f"   缩略图URL: {video_info.thumbnail_url}")
        
        # 测试缩略图下载
        if video_info.thumbnail_url:
            print("🖼️  测试缩略图下载...")
            response = requests.get(video_info.thumbnail_url, timeout=10)
            if response.status_code == 200:
                # 转换为base64
                thumbnail_base64 = base64.b64encode(response.content).decode('utf-8')
                thumbnail_data = f"data:image/jpeg;base64,{thumbnail_base64}"
                
                print(f"✅ 缩略图下载成功，大小: {len(response.content)} bytes")
                print(f"   Base64长度: {len(thumbnail_base64)} 字符")
                print(f"   数据URI前缀: {thumbnail_data[:50]}...")
                
                return True
            else:
                print(f"❌ 缩略图下载失败: HTTP {response.status_code}")
                return False
        else:
            print("⚠️  没有缩略图URL")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

async def test_youtube_thumbnail_extraction():
    """测试YouTube缩略图提取功能"""
    print("\n🧪 测试YouTube缩略图提取功能...")
    
    # 使用一个公开的YouTube视频链接进行测试
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    try:
        import yt_dlp
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        def extract_info_sync(url, ydl_opts):
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=False)
        
        loop = asyncio.get_event_loop()
        video_info = await loop.run_in_executor(None, extract_info_sync, test_url, ydl_opts)
        
        print(f"✅ 视频信息获取成功:")
        print(f"   标题: {video_info.get('title', 'Unknown')}")
        print(f"   上传者: {video_info.get('uploader', 'Unknown')}")
        print(f"   缩略图URL: {video_info.get('thumbnail', '')}")
        
        # 测试缩略图下载
        thumbnail_url = video_info.get('thumbnail', '')
        if thumbnail_url:
            print("🖼️  测试缩略图下载...")
            response = requests.get(thumbnail_url, timeout=10)
            if response.status_code == 200:
                # 转换为base64
                thumbnail_base64 = base64.b64encode(response.content).decode('utf-8')
                thumbnail_data = f"data:image/jpeg;base64,{thumbnail_base64}"
                
                print(f"✅ 缩略图下载成功，大小: {len(response.content)} bytes")
                print(f"   Base64长度: {len(thumbnail_base64)} 字符")
                print(f"   数据URI前缀: {thumbnail_data[:50]}...")
                
                return True
            else:
                print(f"❌ 缩略图下载失败: HTTP {response.status_code}")
                return False
        else:
            print("⚠️  没有缩略图URL")
            return False
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

async def main():
    """主函数"""
    print("🚀 开始测试链接导入项目缩略图功能...\n")
    
    # 测试B站缩略图提取
    bilibili_success = await test_bilibili_thumbnail_extraction()
    
    # 测试YouTube缩略图提取
    youtube_success = await test_youtube_thumbnail_extraction()
    
    print(f"\n📊 测试结果:")
    print(f"   B站缩略图提取: {'✅ 成功' if bilibili_success else '❌ 失败'}")
    print(f"   YouTube缩略图提取: {'✅ 成功' if youtube_success else '❌ 失败'}")
    
    if bilibili_success and youtube_success:
        print("\n🎉 所有测试通过！链接导入项目缩略图功能正常")
        return True
    else:
        print("\n⚠️  部分测试失败，请检查相关功能")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
