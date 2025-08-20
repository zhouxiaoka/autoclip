#!/usr/bin/env python3
"""
视频处理功能测试脚本
用于验证FFmpeg集成和视频切割功能
"""

import sys
import os
import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入视频处理模块
try:
    from shared.utils.video_processor import VideoProcessor
    from shared.config import get_legacy_config
    print("✅ 成功导入视频处理模块")
except ImportError as e:
    print(f"❌ 导入视频处理模块失败: {e}")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_ffmpeg_installation():
    """测试FFmpeg是否正确安装"""
    print("\n🔧 测试FFmpeg安装...")
    
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ FFmpeg安装正确")
            print(f"   版本信息: {result.stdout.split('Copyright')[0].strip()}")
            return True
        else:
            print("❌ FFmpeg安装有问题")
            return False
    except FileNotFoundError:
        print("❌ FFmpeg未安装")
        return False
    except subprocess.TimeoutExpired:
        print("❌ FFmpeg响应超时")
        return False
    except Exception as e:
        print(f"❌ FFmpeg测试失败: {e}")
        return False

def test_video_processor():
    """测试视频处理器类"""
    print("\n🎬 测试视频处理器...")
    
    try:
        # 创建视频处理器实例
        processor = VideoProcessor()
        print("✅ 视频处理器创建成功")
        
        # 测试文件名清理
        test_filename = "测试文件<>:\"/\\|?*名称.mp4"
        cleaned = VideoProcessor.sanitize_filename(test_filename)
        print(f"✅ 文件名清理测试: '{test_filename}' -> '{cleaned}'")
        
        # 测试时间格式转换
        srt_time = "00:01:30,500"
        ffmpeg_time = VideoProcessor.convert_srt_time_to_ffmpeg_time(srt_time)
        print(f"✅ 时间格式转换: '{srt_time}' -> '{ffmpeg_time}'")
        
        # 测试秒数转换
        seconds = 90.5
        time_str = VideoProcessor.convert_seconds_to_ffmpeg_time(seconds)
        print(f"✅ 秒数转换: {seconds}s -> '{time_str}'")
        
        # 测试时间解析
        parsed_seconds = VideoProcessor.convert_ffmpeg_time_to_seconds(time_str)
        print(f"✅ 时间解析: '{time_str}' -> {parsed_seconds}s")
        
        return True
        
    except Exception as e:
        print(f"❌ 视频处理器测试失败: {e}")
        return False

def test_video_extraction():
    """测试视频切割功能"""
    print("\n✂️ 测试视频切割功能...")
    
    # 检查是否有测试视频文件
    config = get_legacy_config()
    test_video_path = config['INPUT_VIDEO']
    
    if not test_video_path.exists():
        print(f"⚠️ 测试视频文件不存在: {test_video_path}")
        print("   请将测试视频文件放在 input/input.mp4")
        return False
    
    try:
        # 创建输出目录
        output_dir = Path("test_output")
        output_dir.mkdir(exist_ok=True)
        
        # 测试视频信息获取
        video_info = VideoProcessor.get_video_info(test_video_path)
        if video_info:
            print(f"✅ 获取视频信息成功: 时长={video_info.get('duration', 'N/A')}秒")
        else:
            print("❌ 获取视频信息失败")
            return False
        
        # 测试视频切割
        output_path = output_dir / "test_clip.mp4"
        start_time = "00:00:10"
        end_time = "00:00:20"
        
        print(f"   切割视频: {start_time} -> {end_time}")
        success = VideoProcessor.extract_clip(test_video_path, output_path, start_time, end_time)
        
        if success and output_path.exists():
            print(f"✅ 视频切割成功: {output_path}")
            # 清理测试文件
            output_path.unlink()
            return True
        else:
            print("❌ 视频切割失败")
            return False
            
    except Exception as e:
        print(f"❌ 视频切割测试失败: {e}")
        return False

def test_batch_processing():
    """测试批量处理功能"""
    print("\n📦 测试批量处理功能...")
    
    config = get_legacy_config()
    test_video_path = config['INPUT_VIDEO']
    
    if not test_video_path.exists():
        print("⚠️ 跳过批量处理测试（无测试视频）")
        return True
    
    try:
        # 创建测试数据
        test_clips = [
            {
                'id': 'test_001',
                'title': '测试片段1',
                'start_time': 10,  # 秒数
                'end_time': 20
            },
            {
                'id': 'test_002', 
                'title': '测试片段2',
                'start_time': 30,
                'end_time': 40
            }
        ]
        
        # 创建输出目录
        clips_dir = Path("test_output/clips")
        clips_dir.mkdir(parents=True, exist_ok=True)
        
        processor = VideoProcessor(clips_dir=str(clips_dir))
        
        print(f"   批量处理 {len(test_clips)} 个片段...")
        successful_clips = processor.batch_extract_clips(test_video_path, test_clips)
        
        print(f"✅ 批量处理完成: {len(successful_clips)}/{len(test_clips)} 成功")
        
        # 清理测试文件
        for clip_path in successful_clips:
            clip_path.unlink()
        
        return len(successful_clips) > 0
        
    except Exception as e:
        print(f"❌ 批量处理测试失败: {e}")
        return False

def test_collection_creation():
    """测试合集创建功能"""
    print("\n🎭 测试合集创建功能...")
    
    try:
        # 创建测试数据
        test_collections = [
            {
                'id': 'collection_001',
                'collection_title': '测试合集1',
                'clip_ids': ['test_001', 'test_002']
            }
        ]
        
        # 创建输出目录
        collections_dir = Path("test_output/collections")
        collections_dir.mkdir(parents=True, exist_ok=True)
        
        processor = VideoProcessor(collections_dir=str(collections_dir))
        
        print(f"   创建 {len(test_collections)} 个合集...")
        successful_collections = processor.create_collections_from_metadata(test_collections)
        
        print(f"✅ 合集创建完成: {len(successful_collections)} 成功")
        
        # 清理测试文件
        for collection_path in successful_collections:
            collection_path.unlink()
        
        return True
        
    except Exception as e:
        print(f"❌ 合集创建测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始视频处理功能测试")
    print("=" * 50)
    
    tests = [
        ("FFmpeg安装", test_ffmpeg_installation),
        ("视频处理器", test_video_processor),
        ("视频切割", test_video_extraction),
        ("批量处理", test_batch_processing),
        ("合集创建", test_collection_creation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}测试异常: {e}")
            results.append((test_name, False))
    
    # 输出测试结果
    print("\n" + "=" * 50)
    print("📊 测试结果汇总:")
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 总体结果: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！视频处理功能正常")
        return 0
    else:
        print("⚠️ 部分测试失败，请检查相关功能")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

