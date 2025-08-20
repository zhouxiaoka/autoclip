#!/usr/bin/env python3
"""
测试视频文件访问
"""

import requests
import json

def test_clip_video_access():
    """测试切片视频访问"""
    print("🧪 测试切片视频访问...")
    
    project_id = "5c48803d-0aa7-48d7-a270-2b33e4954f25"
    clip_id = "15d2e725-6a8c-4b66-b4d3-f22bbced74db"
    
    # 1. 获取切片信息
    try:
        clips_response = requests.get(f"http://localhost:8000/api/v1/clips/?project_id={project_id}")
        if clips_response.status_code == 200:
            clips_data = clips_response.json()
            clips = clips_data.get('items', [])
            
            # 找到目标切片
            target_clip = None
            for clip in clips:
                if clip['id'] == clip_id:
                    target_clip = clip
                    break
            
            if target_clip:
                print(f"✅ 找到切片: {target_clip['title']}")
                metadata = target_clip.get('clip_metadata', {})
                print(f"   - ID: {metadata.get('id', '无')}")
                print(f"   - chunk_index: {metadata.get('chunk_index', '无')}")
                
                # 2. 测试视频URL
                video_url = f"http://localhost:8000/api/v1/projects/{project_id}/clips/{clip_id}"
                print(f"   - 视频URL: {video_url}")
                
                video_response = requests.get(video_url)
                print(f"   - 状态码: {video_response.status_code}")
                
                if video_response.status_code == 200:
                    print("✅ 视频文件访问成功！")
                    print(f"   - 内容类型: {video_response.headers.get('content-type', '未知')}")
                    print(f"   - 文件大小: {len(video_response.content)} 字节")
                else:
                    print(f"❌ 视频文件访问失败: {video_response.text}")
            else:
                print(f"❌ 未找到切片: {clip_id}")
        else:
            print(f"❌ 获取切片列表失败: {clips_response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")

def test_collection_video_access():
    """测试合集视频访问"""
    print("\n🧪 测试合集视频访问...")
    
    project_id = "5c48803d-0aa7-48d7-a270-2b33e4954f25"
    
    try:
        collections_response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
        if collections_response.status_code == 200:
            collections_data = collections_response.json()
            collections = collections_data.get('items', [])
            
            if collections:
                collection = collections[0]
                collection_id = collection['id']
                print(f"✅ 找到合集: {collection['name']}")
                
                # 测试合集视频URL
                video_url = f"http://localhost:8000/api/v1/collections/{collection_id}/download"
                print(f"   - 视频URL: {video_url}")
                
                video_response = requests.get(video_url)
                print(f"   - 状态码: {video_response.status_code}")
                
                if video_response.status_code == 200:
                    print("✅ 合集视频文件访问成功！")
                else:
                    print(f"❌ 合集视频文件访问失败: {video_response.text}")
            else:
                print("❌ 未找到合集")
        else:
            print(f"❌ 获取合集列表失败: {collections_response.status_code}")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")

def main():
    """主函数"""
    print("🚀 开始测试视频文件访问...")
    
    test_clip_video_access()
    test_collection_video_access()
    
    print("\n📊 测试完成")

if __name__ == "__main__":
    main()
