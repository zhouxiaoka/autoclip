#!/usr/bin/env python3
"""
测试前端数据读取
模拟前端的API调用和数据转换逻辑
"""

import requests
import json

def test_frontend_clips_logic():
    """测试前端切片数据读取逻辑"""
    print("🧪 测试前端切片数据读取逻辑...")
    
    project_id = "5c48803d-0aa7-48d7-a270-2b33e4954f25"
    
    try:
        # 模拟前端API调用
        response = requests.get(f"http://localhost:8000/api/v1/clips/?project_id={project_id}")
        if response.status_code != 200:
            print(f"❌ API调用失败: {response.status_code}")
            return
        
        data = response.json()
        clips = data.get('items', [])
        print(f"✅ API返回 {len(clips)} 个切片")
        
        # 模拟前端数据转换逻辑
        converted_clips = []
        for clip in clips:
            # 转换秒数为时间字符串格式
            def format_seconds_to_time(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = int(seconds % 60)
                return f"{hours:02d}:{minutes:02d}:{secs:02d}"
            
            # 获取metadata中的内容
            metadata = clip.get('clip_metadata', {})
            
            converted_clip = {
                'id': clip['id'],
                'title': clip['title'],
                'generated_title': clip['title'],
                'start_time': format_seconds_to_time(clip['start_time']),
                'end_time': format_seconds_to_time(clip['end_time']),
                'duration': clip.get('duration', 0),
                'final_score': clip.get('score', 0),
                'recommend_reason': metadata.get('recommend_reason', ''),
                'outline': metadata.get('outline', ''),
                'content': metadata.get('content', []),
                'chunk_index': metadata.get('chunk_index', 0)
            }
            
            converted_clips.append(converted_clip)
        
        print(f"✅ 转换后得到 {len(converted_clips)} 个切片")
        
        if converted_clips:
            first_clip = converted_clips[0]
            print(f"📄 第一个切片示例:")
            print(f"   - ID: {first_clip['id']}")
            print(f"   - 标题: {first_clip['title']}")
            print(f"   - 开始时间: {first_clip['start_time']}")
            print(f"   - 结束时间: {first_clip['end_time']}")
            print(f"   - 评分: {first_clip['final_score']}")
            print(f"   - 推荐理由: {first_clip['recommend_reason']}")
            print(f"   - 大纲: {first_clip['outline']}")
            print(f"   - 内容要点: {len(first_clip['content'])} 个")
        
        return converted_clips
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return []

def test_frontend_collections_logic():
    """测试前端合集数据读取逻辑"""
    print("\n🧪 测试前端合集数据读取逻辑...")
    
    project_id = "5c48803d-0aa7-48d7-a270-2b33e4954f25"
    
    try:
        # 模拟前端API调用
        response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
        if response.status_code != 200:
            print(f"❌ API调用失败: {response.status_code}")
            return
        
        data = response.json()
        collections = data.get('items', [])
        print(f"✅ API返回 {len(collections)} 个合集")
        
        # 模拟前端数据转换逻辑
        converted_collections = []
        for collection in collections:
            metadata = collection.get('metadata', {})
            
            converted_collection = {
                'id': collection['id'],
                'collection_title': metadata.get('collection_title', collection.get('name', '')),
                'collection_summary': metadata.get('collection_summary', collection.get('description', '')),
                'clip_ids': metadata.get('clip_ids', []),
                'collection_type': metadata.get('collection_type', 'ai_recommended'),
                'created_at': collection.get('created_at', '')
            }
            
            converted_collections.append(converted_collection)
        
        print(f"✅ 转换后得到 {len(converted_collections)} 个合集")
        
        if converted_collections:
            first_collection = converted_collections[0]
            print(f"📄 第一个合集示例:")
            print(f"   - ID: {first_collection['id']}")
            print(f"   - 标题: {first_collection['collection_title']}")
            print(f"   - 描述: {first_collection['collection_summary']}")
            print(f"   - 切片数量: {len(first_collection['clip_ids'])}")
            print(f"   - 类型: {first_collection['collection_type']}")
        
        return converted_collections
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return []

def test_video_urls():
    """测试视频URL生成"""
    print("\n🧪 测试视频URL生成...")
    
    project_id = "5c48803d-0aa7-48d7-a270-2b33e4954f25"
    
    # 测试切片视频URL
    clips_response = requests.get(f"http://localhost:8000/api/v1/clips/?project_id={project_id}")
    if clips_response.status_code == 200:
        clips = clips_response.json().get('items', [])
        if clips:
            clip_id = clips[0]['id']
            clip_video_url = f"http://localhost:8000/api/v1/projects/{project_id}/clips/{clip_id}"
            print(f"✅ 切片视频URL: {clip_video_url}")
            
            # 测试URL是否可访问
            try:
                video_response = requests.head(clip_video_url)
                print(f"   状态码: {video_response.status_code}")
            except Exception as e:
                print(f"   ❌ URL访问失败: {e}")
    
    # 测试合集视频URL
    collections_response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
    if collections_response.status_code == 200:
        collections = collections_response.json().get('items', [])
        if collections:
            collection_id = collections[0]['id']
            collection_video_url = f"http://localhost:8000/api/v1/projects/{project_id}/files/output/collections/{collection_id}.mp4"
            print(f"✅ 合集视频URL: {collection_video_url}")
            
            # 测试URL是否可访问
            try:
                video_response = requests.head(collection_video_url)
                print(f"   状态码: {video_response.status_code}")
            except Exception as e:
                print(f"   ❌ URL访问失败: {e}")

def main():
    """主函数"""
    print("🚀 开始测试前端数据读取...")
    
    # 测试切片数据
    clips = test_frontend_clips_logic()
    
    # 测试合集数据
    collections = test_frontend_collections_logic()
    
    # 测试视频URL
    test_video_urls()
    
    # 总结
    print(f"\n📊 测试总结:")
    print(f"   - 切片数量: {len(clips) if clips else 0}")
    print(f"   - 合集数量: {len(collections) if collections else 0}")
    
    if clips and collections:
        print("✅ 前端数据读取测试通过！")
    else:
        print("❌ 前端数据读取测试失败！")

if __name__ == "__main__":
    main()
