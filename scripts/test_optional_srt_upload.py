#!/usr/bin/env python3
"""
测试可选SRT文件上传功能
"""
import requests
import os
from pathlib import Path

def test_upload_with_srt():
    """测试同时上传视频和字幕文件"""
    print("🔍 测试上传视频+字幕文件...")
    
    url = "http://localhost:8000/api/v1/projects/upload"
    
    # 创建测试文件
    test_dir = Path("/tmp/test_upload")
    test_dir.mkdir(exist_ok=True)
    
    # 创建测试视频文件（空文件）
    video_file = test_dir / "test_video.mp4"
    with open(video_file, "wb") as f:
        f.write(b"fake video content")
    
    # 创建测试字幕文件
    srt_file = test_dir / "test_subtitle.srt"
    with open(srt_file, "w", encoding="utf-8") as f:
        f.write("""1
00:00:00,000 --> 00:00:05,000
这是测试字幕

2
00:00:05,000 --> 00:00:10,000
用户提供的字幕文件
""")
    
    try:
        with open(video_file, "rb") as vf, open(srt_file, "rb") as sf:
            files = {
                'video_file': ('test_video.mp4', vf, 'video/mp4'),
                'srt_file': ('test_subtitle.srt', sf, 'application/x-subrip')
            }
            data = {
                'project_name': '测试项目-用户字幕',
                'video_category': 'default'
            }
            
            response = requests.post(url, files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 上传成功: {result['name']}")
                print(f"   项目ID: {result['id']}")
                print(f"   描述: {result['description']}")
                return result['id']
            else:
                print(f"❌ 上传失败: {response.status_code}")
                print(f"   错误: {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return None

def test_upload_video_only():
    """测试只上传视频文件（应该自动语音识别）"""
    print("\n🔍 测试只上传视频文件（会因为语音识别失败而报错，这是预期的）...")
    
    url = "http://localhost:8000/api/v1/projects/upload"
    
    # 创建测试文件
    test_dir = Path("/tmp/test_upload")
    test_dir.mkdir(exist_ok=True)
    
    # 创建测试视频文件（空文件）
    video_file = test_dir / "test_video_only.mp4"
    with open(video_file, "wb") as f:
        f.write(b"fake video content for speech recognition")
    
    try:
        with open(video_file, "rb") as vf:
            files = {
                'video_file': ('test_video_only.mp4', vf, 'video/mp4')
            }
            data = {
                'project_name': '测试项目-自动字幕',
                'video_category': 'knowledge'
            }
            
            response = requests.post(url, files=files, data=data)
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 上传成功: {result['name']}")
                print(f"   项目ID: {result['id']}")
                print(f"   描述: {result['description']}")
                print(f"   自动生成字幕: {result['settings'].get('auto_generate_subtitle', False)}")
                return result['id']
            elif response.status_code == 400:
                # 这是预期的，因为fake视频文件无法进行语音识别
                error_detail = response.json().get('detail', '')
                if '语音识别失败' in error_detail:
                    print(f"✅ 预期的失败: 语音识别失败（因为使用了fake视频文件）")
                    print(f"   错误详情: {error_detail}")
                    return "expected_failure"
                else:
                    print(f"❌ 意外的400错误: {error_detail}")
                    return None
            else:
                print(f"❌ 上传失败: {response.status_code}")
                print(f"   错误: {response.text}")
                return None
                
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return None

def cleanup_test_projects(project_ids):
    """清理测试项目"""
    print(f"\n🧹 清理测试项目...")
    
    for project_id in project_ids:
        if project_id and project_id != "expected_failure":
            try:
                response = requests.delete(f"http://localhost:8000/api/v1/projects/{project_id}")
                if response.status_code == 200:
                    print(f"✅ 删除项目 {project_id}")
                else:
                    print(f"❌ 删除项目失败 {project_id}: {response.status_code}")
            except Exception as e:
                print(f"❌ 删除项目异常 {project_id}: {e}")
        elif project_id == "expected_failure":
            print("✅ 跳过预期的失败测试（无需清理）")

def main():
    """主测试函数"""
    print("🚀 可选SRT文件上传功能测试开始")
    print("=" * 50)
    
    project_ids = []
    
    # 测试1：上传视频+字幕
    project_id1 = test_upload_with_srt()
    if project_id1:
        project_ids.append(project_id1)
    
    # 测试2：只上传视频
    project_id2 = test_upload_video_only()
    if project_id2:
        project_ids.append(project_id2)
    
    # 清理测试项目
    cleanup_test_projects(project_ids)
    
    print("\n" + "=" * 50)
    print("✅ 测试完成")
    
    print("\n💡 功能说明:")
    print("1. 用户可以同时上传视频和字幕文件（使用用户字幕）")
    print("2. 用户可以只上传视频文件（自动语音识别生成字幕）")
    print("3. 系统根据视频分类智能选择语音识别语言")

if __name__ == "__main__":
    main()
