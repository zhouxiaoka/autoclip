#!/usr/bin/env python3
"""
测试clip文件命名和查找逻辑
"""

import json
import logging
from pathlib import Path
import sys
import uuid

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))

from utils.video_processor import VideoProcessor
from core.path_utils import get_clips_directory, get_clip_file_path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_clip_file_naming():
    """测试clip文件命名逻辑"""
    print("🧪 测试clip文件命名逻辑...")
    
    # 测试数据
    test_cases = [
        {
            "clip_id": str(uuid.uuid4()),
            "title": "测试标题1",
            "expected_pattern": "测试标题1"
        },
        {
            "clip_id": str(uuid.uuid4()),
            "title": "测试标题2: 包含特殊字符",
            "expected_pattern": "测试标题2_ 包含特殊字符"
        },
        {
            "clip_id": str(uuid.uuid4()),
            "title": "测试标题3/包含/斜杠",
            "expected_pattern": "测试标题3_包含_斜杠"
        },
        {
            "clip_id": str(uuid.uuid4()),
            "title": "测试标题4*包含*星号",
            "expected_pattern": "测试标题4_包含_星号"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n📝 测试用例 {i}:")
        print(f"  Clip ID: {test_case['clip_id']}")
        print(f"  原始标题: {test_case['title']}")
        
        # 测试文件名清理
        safe_title = VideoProcessor.sanitize_filename(test_case['title'])
        print(f"  清理后标题: {safe_title}")
        
        # 测试完整文件路径生成
        expected_path = get_clip_file_path(test_case['clip_id'], test_case['title'])
        print(f"  生成的文件路径: {expected_path}")
        
        # 验证文件名格式
        expected_filename = f"{test_case['clip_id']}_{safe_title}.mp4"
        if expected_filename in str(expected_path):
            print(f"  ✅ 文件名格式正确")
        else:
            print(f"  ❌ 文件名格式错误")
        
        # 测试文件查找模式
        clips_dir = get_clips_directory()
        search_pattern = f"{test_case['clip_id']}_*.mp4"
        print(f"  查找模式: {search_pattern}")
        
        # 模拟文件查找
        print(f"  预期查找结果: {clips_dir / expected_filename}")

def test_storage_service_naming():
    """测试存储服务的文件命名逻辑"""
    print("\n🧪 测试存储服务文件命名逻辑...")
    
    # 模拟clip数据
    clip_data = {
        "id": str(uuid.uuid4()),
        "title": "存储服务测试标题",
        "start_time": 0,
        "end_time": 60
    }
    
    print(f"  Clip ID: {clip_data['id']}")
    print(f"  标题: {clip_data['title']}")
    
    # 模拟存储服务的命名逻辑
    from utils.video_processor import VideoProcessor
    safe_title = VideoProcessor.sanitize_filename(clip_data['title'])
    expected_filename = f"{clip_data['id']}_{safe_title}.mp4"
    
    print(f"  预期文件名: {expected_filename}")
    
    # 验证与path_utils的一致性
    from core.path_utils import get_clip_file_path
    path_utils_filename = get_clip_file_path(clip_data['id'], clip_data['title']).name
    
    if expected_filename == path_utils_filename:
        print(f"  ✅ 存储服务与path_utils命名一致")
    else:
        print(f"  ❌ 存储服务与path_utils命名不一致")
        print(f"    存储服务: {expected_filename}")
        print(f"    path_utils: {path_utils_filename}")

def test_api_lookup_logic():
    """测试API查找逻辑"""
    print("\n🧪 测试API查找逻辑...")
    
    clip_id = str(uuid.uuid4())
    title = "API查找测试标题"
    
    print(f"  Clip ID: {clip_id}")
    print(f"  标题: {title}")
    
    # 模拟API查找逻辑
    clips_dir = get_clips_directory()
    search_pattern = f"{clip_id}_*.mp4"
    
    print(f"  查找目录: {clips_dir}")
    print(f"  查找模式: {search_pattern}")
    
    # 模拟查找结果
    expected_files = list(clips_dir.glob(search_pattern))
    print(f"  查找结果: {len(expected_files)} 个文件")
    
    if expected_files:
        for file in expected_files:
            print(f"    找到文件: {file.name}")
    else:
        print(f"    未找到文件（这是正常的，因为文件不存在）")
    
    # 验证查找逻辑的正确性
    safe_title = VideoProcessor.sanitize_filename(title)
    expected_filename = f"{clip_id}_{safe_title}.mp4"
    expected_path = clips_dir / expected_filename
    
    print(f"  预期文件路径: {expected_path}")
    
    # 检查查找模式是否能匹配预期文件
    import fnmatch
    if fnmatch.fnmatch(expected_filename, search_pattern.replace("*", "*")):
        print(f"  ✅ 查找模式能正确匹配预期文件")
    else:
        print(f"  ❌ 查找模式无法匹配预期文件")

if __name__ == "__main__":
    test_clip_file_naming()
    test_storage_service_naming()
    test_api_lookup_logic()
    
    print("\n🎉 测试完成！")


