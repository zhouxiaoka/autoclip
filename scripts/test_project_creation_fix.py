#!/usr/bin/env python3
"""
测试项目创建修复
验证B站和YouTube项目创建时的字段映射问题是否已修复
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

from backend.core.database import SessionLocal
from backend.services.project_service import ProjectService
from backend.schemas.project import ProjectCreate, ProjectType, ProjectStatus

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_project_creation():
    """测试项目创建修复"""
    print("🔍 测试项目创建修复...")
    
    try:
        # 创建数据库会话
        db = SessionLocal()
        project_service = ProjectService(db)
        
        try:
            # 测试1: 创建B站项目
            print("1. 测试B站项目创建...")
            bilibili_project_data = ProjectCreate(
                name="测试B站项目",
                description="测试B站项目创建",
                project_type=ProjectType.KNOWLEDGE,
                source_url="https://www.bilibili.com/video/BV1xx411c7mu",
                source_file="/path/to/video.mp4",
                settings={
                    "bilibili_info": {
                        "title": "测试视频",
                        "uploader": "测试UP主",
                        "duration": 300,
                        "view_count": 1000
                    },
                    "subtitle_path": "/path/to/subtitle.srt"
                }
            )
            
            bilibili_project = project_service.create_project(bilibili_project_data)
            print(f"   ✅ B站项目创建成功: {bilibili_project.id}")
            
            # 验证字段映射
            print(f"   📋 项目字段验证:")
            print(f"      - video_path: {bilibili_project.video_path}")
            print(f"      - processing_config: {bilibili_project.processing_config}")
            print(f"      - project_metadata: {bilibili_project.project_metadata}")
            
            # 测试2: 创建YouTube项目
            print("2. 测试YouTube项目创建...")
            youtube_project_data = ProjectCreate(
                name="测试YouTube项目",
                description="测试YouTube项目创建",
                project_type=ProjectType.ENTERTAINMENT,
                source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                source_file="/path/to/youtube_video.mp4",
                settings={
                    "youtube_info": {
                        "title": "测试YouTube视频",
                        "uploader": "YouTube",
                        "duration": 240,
                        "view_count": 5000
                    },
                    "subtitle_path": "/path/to/youtube_subtitle.srt"
                }
            )
            
            youtube_project = project_service.create_project(youtube_project_data)
            print(f"   ✅ YouTube项目创建成功: {youtube_project.id}")
            
            # 验证字段映射
            print(f"   📋 项目字段验证:")
            print(f"      - video_path: {youtube_project.video_path}")
            print(f"      - processing_config: {youtube_project.processing_config}")
            print(f"      - project_metadata: {youtube_project.project_metadata}")
            
            # 测试3: 测试字段更新
            print("3. 测试字段更新...")
            
            # 测试B站项目的字段更新
            if not bilibili_project.processing_config:
                bilibili_project.processing_config = {}
            bilibili_project.processing_config["subtitle_path"] = "/new/path/to/subtitle.srt"
            bilibili_project.video_path = "/new/path/to/video.mp4"
            db.commit()
            print(f"   ✅ B站项目字段更新成功")
            
            # 测试YouTube项目的字段更新
            if not youtube_project.processing_config:
                youtube_project.processing_config = {}
            youtube_project.processing_config["subtitle_path"] = "/new/path/to/youtube_subtitle.srt"
            youtube_project.video_path = "/new/path/to/youtube_video.mp4"
            db.commit()
            print(f"   ✅ YouTube项目字段更新成功")
            
            # 清理测试数据
            print("4. 清理测试数据...")
            db.delete(bilibili_project)
            db.delete(youtube_project)
            db.commit()
            print(f"   ✅ 测试数据清理完成")
            
            print("✅ 项目创建修复测试完成")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ 项目创建修复测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_field_access():
    """测试字段访问"""
    print("\n🔍 测试字段访问...")
    
    try:
        # 创建数据库会话
        db = SessionLocal()
        project_service = ProjectService(db)
        
        try:
            # 创建测试项目
            test_project_data = ProjectCreate(
                name="字段访问测试",
                description="测试字段访问",
                project_type=ProjectType.DEFAULT,
                settings={"test_key": "test_value"}
            )
            
            project = project_service.create_project(test_project_data)
            
            # 测试各种字段访问
            print("1. 测试基本字段访问...")
            print(f"   - project.id: {project.id}")
            print(f"   - project.name: {project.name}")
            print(f"   - project.status: {project.status}")
            print(f"   - project.project_type: {project.project_type}")
            
            print("2. 测试配置字段访问...")
            print(f"   - project.processing_config: {project.processing_config}")
            print(f"   - project.project_metadata: {project.project_metadata}")
            
            print("3. 测试计算属性...")
            print(f"   - project.has_video_file: {project.has_video_file}")
            print(f"   - project.has_subtitle_file: {project.has_subtitle_file}")
            print(f"   - project.is_processing: {project.is_processing}")
            print(f"   - project.is_completed: {project.is_completed}")
            
            # 测试字段更新
            print("4. 测试字段更新...")
            project.processing_config["new_key"] = "new_value"
            project.video_path = "/test/video.mp4"
            project.subtitle_path = "/test/subtitle.srt"
            db.commit()
            
            print(f"   - 更新后 processing_config: {project.processing_config}")
            print(f"   - 更新后 video_path: {project.video_path}")
            print(f"   - 更新后 subtitle_path: {project.subtitle_path}")
            print(f"   - 更新后 has_video_file: {project.has_video_file}")
            print(f"   - 更新后 has_subtitle_file: {project.has_subtitle_file}")
            
            # 清理测试数据
            db.delete(project)
            db.commit()
            
            print("✅ 字段访问测试完成")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ 字段访问测试失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主函数"""
    print("🚀 开始测试项目创建修复...")
    
    # 测试项目创建
    test_project_creation()
    
    # 测试字段访问
    test_field_access()
    
    print("\n🎉 所有测试完成！")

if __name__ == "__main__":
    main()
