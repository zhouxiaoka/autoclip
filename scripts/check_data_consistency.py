#!/usr/bin/env python3
"""
数据一致性检查工具
检查clip数据、文件路径和标题的对应关系
"""

import json
import logging
from pathlib import Path
import sys
from typing import Dict, List, Any

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import sys
sys.path.insert(0, str(project_root / "backend"))

from core.database import SessionLocal
from models.clip import Clip
from models.project import Project
from core.path_utils import get_clips_directory, get_project_directory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_clip_data_consistency(project_id: str = None):
    """检查clip数据一致性"""
    print("🔍 开始检查数据一致性...")
    
    db = SessionLocal()
    try:
        # 获取所有项目或指定项目
        if project_id:
            projects = [db.query(Project).filter(Project.id == project_id).first()]
            if not projects[0]:
                print(f"❌ 项目不存在: {project_id}")
                return
        else:
            projects = db.query(Project).all()
        
        total_issues = 0
        
        for project in projects:
            print(f"\n📁 检查项目: {project.name} ({project.id})")
            project_issues = check_project_clips(project, db)
            total_issues += project_issues
            
            if project_issues == 0:
                print(f"✅ 项目 {project.name} 数据一致")
            else:
                print(f"⚠️ 项目 {project.name} 发现 {project_issues} 个问题")
        
        print(f"\n📊 检查完成，总共发现 {total_issues} 个问题")
        
    finally:
        db.close()

def check_project_clips(project: Project, db) -> int:
    """检查单个项目的clip数据"""
    issues = 0
    clips = db.query(Clip).filter(Clip.project_id == project.id).all()
    
    print(f"  📋 找到 {len(clips)} 个切片")
    
    # 检查文件系统
    clips_dir = get_clips_dir()
    if not clips_dir.exists():
        print(f"  ❌ Clips目录不存在: {clips_dir}")
        return len(clips)  # 所有clip都有问题
    
    # 检查每个clip
    for clip in clips:
        clip_issues = check_single_clip(clip, clips_dir)
        issues += clip_issues
        
        if clip_issues > 0:
            print(f"    ⚠️ Clip {clip.id}: {clip.title}")
            print(f"      问题: {clip_issues} 个")
    
    return issues

def check_single_clip(clip: Clip, clips_dir: Path) -> int:
    """检查单个clip的数据一致性"""
    issues = 0
    
    # 1. 检查标题是否为空
    if not clip.title or clip.title.strip() == "":
        print(f"      - 标题为空")
        issues += 1
    
    # 2. 检查文件路径
    if not clip.video_path:
        print(f"      - 数据库中没有视频文件路径")
        issues += 1
    else:
        video_file = Path(clip.video_path)
        if not video_file.exists():
            print(f"      - 视频文件不存在: {video_file}")
            issues += 1
    
    # 3. 检查文件系统中的文件
    expected_files = list(clips_dir.glob(f"{clip.id}_*.mp4"))
    if not expected_files:
        print(f"      - 文件系统中找不到对应的视频文件")
        issues += 1
    elif len(expected_files) > 1:
        print(f"      - 找到多个匹配的文件: {[f.name for f in expected_files]}")
        issues += 1
    else:
        # 检查文件名是否包含标题
        file_name = expected_files[0].name
        if clip.title and clip.title not in file_name:
            print(f"      - 文件名不包含标题: {file_name}")
            issues += 1
    
    # 4. 检查元数据
    if not clip.clip_metadata:
        print(f"      - 没有元数据")
        issues += 1
    else:
        # 检查元数据文件是否存在
        metadata_file = clip.clip_metadata.get('metadata_file')
        if metadata_file and not Path(metadata_file).exists():
            print(f"      - 元数据文件不存在: {metadata_file}")
            issues += 1
    
    return issues

def get_clips_dir() -> Path:
    """获取clips目录"""
    try:
        return get_clips_directory()
    except Exception as e:
        logger.error(f"获取clips目录失败: {e}")
        return Path("data/output/clips")

def fix_clip_data_issues(project_id: str = None):
    """修复clip数据问题"""
    print("🔧 开始修复数据问题...")
    
    db = SessionLocal()
    try:
        # 获取所有项目或指定项目
        if project_id:
            projects = [db.query(Project).filter(Project.id == project_id).first()]
            if not projects[0]:
                print(f"❌ 项目不存在: {project_id}")
                return
        else:
            projects = db.query(Project).all()
        
        for project in projects:
            print(f"\n🔧 修复项目: {project.name} ({project.id})")
            fix_project_clips(project, db)
        
        print("\n✅ 修复完成")
        
    finally:
        db.close()

def fix_project_clips(project: Project, db):
    """修复单个项目的clip数据"""
    clips = db.query(Clip).filter(Clip.project_id == project.id).all()
    clips_dir = get_clips_dir()
    
    for clip in clips:
        fix_single_clip(clip, clips_dir, db)
    
    db.commit()

def fix_single_clip(clip: Clip, clips_dir: Path, db):
    """修复单个clip的数据问题"""
    # 1. 修复空标题
    if not clip.title or clip.title.strip() == "":
        # 尝试从元数据中获取标题
        if clip.clip_metadata:
            generated_title = clip.clip_metadata.get('generated_title')
            if generated_title:
                clip.title = generated_title
                print(f"  ✅ 修复clip {clip.id} 的标题: {generated_title}")
            else:
                clip.title = f"Clip_{clip.id[:8]}"
                print(f"  ✅ 为clip {clip.id} 设置默认标题: {clip.title}")
    
    # 2. 修复文件路径
    if not clip.video_path:
        # 查找对应的文件
        expected_files = list(clips_dir.glob(f"{clip.id}_*.mp4"))
        if expected_files:
            clip.video_path = str(expected_files[0])
            print(f"  ✅ 修复clip {clip.id} 的文件路径: {clip.video_path}")
    
    # 3. 修复元数据
    if not clip.clip_metadata:
        clip.clip_metadata = {
            'clip_id': clip.id,
            'created_at': clip.created_at.isoformat() if clip.created_at else None
        }
        print(f"  ✅ 为clip {clip.id} 创建基础元数据")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="数据一致性检查工具")
    parser.add_argument("--project-id", help="指定项目ID")
    parser.add_argument("--fix", action="store_true", help="修复发现的问题")
    
    args = parser.parse_args()
    
    if args.fix:
        fix_clip_data_issues(args.project_id)
    else:
        check_clip_data_consistency(args.project_id)
