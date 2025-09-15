#!/usr/bin/env python3
"""
修复项目缩略图脚本
处理链接导入和文件导入项目的缩略图问题
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.core.database import SessionLocal
from backend.models.project import Project
from backend.utils.thumbnail_generator import generate_project_thumbnail
import requests
import base64
import logging

logger = logging.getLogger(__name__)

def fix_project_thumbnail(project_id: str):
    """修复指定项目的缩略图"""
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        
        if not project:
            print(f"❌ 项目 {project_id} 不存在")
            return False
        
        if project.thumbnail:
            print(f"✅ 项目 {project_id} 已有缩略图，跳过")
            return True
        
        print(f"🔧 修复项目 {project_id} 的缩略图...")
        
        # 检查项目类型和来源
        source_url = project.project_metadata.get('source_url') if project.project_metadata else None
        is_bilibili_project = source_url and 'bilibili.com' in source_url
        has_video_file = project.video_path and Path(project.video_path).exists()
        
        if is_bilibili_project:
            # 链接导入项目 - 尝试从B站获取缩略图
            print(f"📺 检测到B站项目，尝试获取原视频缩略图...")
            success = fix_bilibili_thumbnail(project, db)
        elif has_video_file:
            # 文件导入项目 - 从视频文件生成缩略图
            print(f"📁 检测到文件导入项目，从视频文件生成缩略图...")
            success = fix_file_import_thumbnail(project, db)
        else:
            # 没有原始视频文件，尝试从切片生成缩略图
            print(f"🎬 没有原始视频文件，尝试从切片生成缩略图...")
            success = fix_clip_thumbnail(project, db)
        
        if success:
            print(f"✅ 项目 {project_id} 缩略图修复成功")
        else:
            print(f"❌ 项目 {project_id} 缩略图修复失败")
        
        return success
        
    except Exception as e:
        print(f"❌ 修复项目 {project_id} 缩略图时发生错误: {e}")
        return False
    finally:
        db.close()

def fix_bilibili_thumbnail(project, db):
    """修复B站项目的缩略图"""
    try:
        # 从项目设置中获取B站信息
        if not project.processing_config:
            return False
        
        bilibili_info = project.processing_config.get('bilibili_info', {})
        if not bilibili_info:
            return False
        
        # 尝试从B站API获取缩略图
        # 这里需要根据实际的B站API来实现
        # 暂时返回False，表示需要手动处理
        print("⚠️  B站缩略图获取需要API支持，暂时跳过")
        return False
        
    except Exception as e:
        logger.error(f"修复B站缩略图失败: {e}")
        return False

def fix_file_import_thumbnail(project, db):
    """修复文件导入项目的缩略图"""
    try:
        video_path = Path(project.video_path)
        if not video_path.exists():
            print(f"⚠️  视频文件不存在: {video_path}")
            return False
        
        # 生成缩略图
        thumbnail_data = generate_project_thumbnail(project.id, video_path)
        
        if thumbnail_data:
            # 保存到数据库
            project.thumbnail = thumbnail_data
            db.commit()
            return True
        else:
            print("⚠️  缩略图生成失败")
            return False
            
    except Exception as e:
        logger.error(f"修复文件导入缩略图失败: {e}")
        return False

def fix_clip_thumbnail(project, db):
    """从切片生成缩略图"""
    try:
        # 查找项目目录中的切片文件
        project_dir = Path(f"/Users/zhoukk/autoclip/data/projects/{project.id}")
        clips_dir = project_dir / "output" / "clips"
        
        if not clips_dir.exists():
            print(f"⚠️  切片目录不存在: {clips_dir}")
            return False
        
        # 获取第一个切片文件
        clip_files = list(clips_dir.glob("*.mp4"))
        if not clip_files:
            print(f"⚠️  没有找到切片文件")
            return False
        
        first_clip = clip_files[0]
        print(f"🎬 使用切片文件生成缩略图: {first_clip.name}")
        
        # 生成缩略图
        thumbnail_data = generate_project_thumbnail(project.id, first_clip)
        
        if thumbnail_data:
            # 保存到数据库
            project.thumbnail = thumbnail_data
            db.commit()
            return True
        else:
            print("⚠️  从切片生成缩略图失败")
            return False
            
    except Exception as e:
        logger.error(f"从切片生成缩略图失败: {e}")
        return False

def fix_all_project_thumbnails():
    """修复所有项目的缩略图"""
    db = SessionLocal()
    try:
        # 查找所有没有缩略图的项目
        projects = db.query(Project).filter(Project.thumbnail.is_(None)).all()
        
        if not projects:
            print("✅ 所有项目都已有缩略图")
            return True
        
        print(f"📋 找到 {len(projects)} 个需要修复缩略图的项目")
        
        success_count = 0
        for project in projects:
            if fix_project_thumbnail(project.id):
                success_count += 1
        
        print(f"🎉 完成！成功修复 {success_count}/{len(projects)} 个项目的缩略图")
        return True
        
    except Exception as e:
        print(f"❌ 修复所有项目缩略图时发生错误: {e}")
        return False
    finally:
        db.close()

def main():
    """主函数"""
    if len(sys.argv) > 1:
        # 修复指定项目
        project_id = sys.argv[1]
        print(f"🚀 开始修复项目 {project_id} 的缩略图...")
        if fix_project_thumbnail(project_id):
            print("🎉 缩略图修复完成！")
        else:
            print("❌ 缩略图修复失败")
            sys.exit(1)
    else:
        # 修复所有项目
        print("🚀 开始修复所有项目的缩略图...")
        if fix_all_project_thumbnails():
            print("🎉 所有缩略图修复完成！")
        else:
            print("❌ 缩略图修复失败")
            sys.exit(1)

if __name__ == "__main__":
    main()
