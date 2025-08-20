#!/usr/bin/env python3
"""
测试切片API的数据转换
"""

import requests
import json

def test_clips_api():
    """测试切片API的数据转换"""
    base_url = "http://localhost:8000/api/v1"
    project_id = "1fdb0bf1-7f3c-44f7-a69d-90c5a1d26fbe"
    
    print("🧪 开始测试切片API...")
    
    # 1. 测试后端API
    print("\n1. 测试后端API...")
    try:
        response = requests.get(f"{base_url}/clips/?project_id={project_id}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 后端API返回 {len(data['items'])} 个切片")
            
            if data['items']:
                clip = data['items'][0]
                print(f"   第一个切片:")
                print(f"   - ID: {clip['id']}")
                print(f"   - 标题: {clip['title']}")
                print(f"   - 开始时间: {clip['start_time']}秒")
                print(f"   - 结束时间: {clip['end_time']}秒")
                print(f"   - 分数: {clip['score']}")
                
                metadata = clip.get('clip_metadata', {})
                print(f"   - 推荐理由: {metadata.get('recommend_reason', '无')}")
                print(f"   - 内容要点: {len(metadata.get('content', []))} 个")
        else:
            print(f"❌ 后端API失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 后端API异常: {e}")
        return
    
    # 2. 测试前端API（模拟）
    print("\n2. 测试前端API数据转换...")
    try:
        # 模拟前端的数据转换逻辑
        clips = data['items']
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
                'final_score': clip['score'] or 0,
                'recommend_reason': metadata.get('recommend_reason') or clip['description'] or '',
                'outline': metadata.get('outline') or clip['description'] or '',
                'content': metadata.get('content') or [clip['description'] or ''],
                'chunk_index': metadata.get('chunk_index') or 0
            }
            converted_clips.append(converted_clip)
        
        print(f"✅ 前端转换完成: {len(converted_clips)} 个切片")
        
        if converted_clips:
            clip = converted_clips[0]
            print(f"   第一个转换后的切片:")
            print(f"   - ID: {clip['id']}")
            print(f"   - 标题: {clip['title']}")
            print(f"   - 开始时间: {clip['start_time']}")
            print(f"   - 结束时间: {clip['end_time']}")
            print(f"   - 分数: {clip['final_score']}")
            print(f"   - 推荐理由: {clip['recommend_reason'][:50]}...")
            print(f"   - 内容要点: {len(clip['content'])} 个")
            
    except Exception as e:
        print(f"❌ 前端转换异常: {e}")
        return
    
    print("\n🎉 切片API测试完成!")

if __name__ == "__main__":
    test_clips_api()

