#!/usr/bin/env python3
"""
清理数据库中的重复切片数据
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database import SessionLocal
from models.clip import Clip
from models.project import Project
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def cleanup_duplicate_clips():
    """清理重复的切片数据"""
    db = SessionLocal()
    
    try:
        # 获取所有项目
        projects = db.query(Project).all()
        
        for project in projects:
            logger.info(f"处理项目: {project.name} (ID: {project.id})")
            
            # 获取项目的所有切片
            clips = db.query(Clip).filter(Clip.project_id == project.id).all()
            logger.info(f"  数据库中有 {len(clips)} 个切片")
            
            # 读取文件系统中的原始数据
            data_dir = Path("data/projects")
            project_dir = data_dir / project.id
            
            clips_metadata_file = project_dir / "clips_metadata.json"
            if not clips_metadata_file.exists():
                logger.warning(f"  项目 {project.id} 的clips_metadata.json不存在")
                continue
            
            try:
                with open(clips_metadata_file, 'r', encoding='utf-8') as f:
                    original_clips = json.load(f)
                logger.info(f"  文件系统中有 {len(original_clips)} 个切片")
                
                # 创建原始切片的ID映射
                original_clip_ids = {clip['id']: clip for clip in original_clips}
                
                # 删除数据库中的重复切片，只保留与文件系统匹配的切片
                deleted_count = 0
                kept_count = 0
                
                for db_clip in clips:
                    # 检查这个切片是否在原始数据中
                    metadata = db_clip.clip_metadata or {}
                    original_id = metadata.get('id')
                    
                    if original_id and original_id in original_clip_ids:
                        # 这个切片是有效的，保留
                        kept_count += 1
                        logger.info(f"    保留切片: {db_clip.title} (ID: {original_id})")
                    else:
                        # 这个切片是重复的或无效的，删除
                        logger.info(f"    删除重复切片: {db_clip.title} (DB ID: {db_clip.id})")
                        db.delete(db_clip)
                        deleted_count += 1
                
                db.commit()
                logger.info(f"  项目 {project.id} 清理完成: 保留 {kept_count} 个，删除 {deleted_count} 个")
                
            except Exception as e:
                logger.error(f"  处理项目 {project.id} 时出错: {e}")
                db.rollback()
        
        logger.info("所有项目清理完成")
        
    except Exception as e:
        logger.error(f"清理过程中出错: {e}")
        db.rollback()
    finally:
        db.close()

def verify_clips_data():
    """验证切片数据的正确性"""
    db = SessionLocal()
    
    try:
        projects = db.query(Project).all()
        
        for project in projects:
            logger.info(f"\n验证项目: {project.name}")
            
            clips = db.query(Clip).filter(Clip.project_id == project.id).all()
            logger.info(f"  数据库切片数量: {len(clips)}")
            
            # 检查时间数据
            for clip in clips:
                if clip.start_time == 0 and clip.end_time > 0:
                    logger.warning(f"    切片 {clip.title} 的start_time为0，可能有问题")
                
                if clip.duration <= 0:
                    logger.warning(f"    切片 {clip.title} 的duration为{clip.duration}，可能有问题")
                
                # 检查metadata
                metadata = clip.clip_metadata or {}
                if not metadata.get('id'):
                    logger.warning(f"    切片 {clip.title} 缺少原始ID")
                
                # 检查content字段
                content = metadata.get('content', [])
                if not content or (isinstance(content, list) and len(content) == 0):
                    logger.warning(f"    切片 {clip.title} 缺少content数据")
                elif isinstance(content, list) and len(content) == 1 and content[0] == clip.title:
                    logger.warning(f"    切片 {clip.title} 的content只是标题的重复")
    
    except Exception as e:
        logger.error(f"验证过程中出错: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🧹 开始清理重复的切片数据...")
    cleanup_duplicate_clips()
    
    print("\n🔍 验证切片数据...")
    verify_clips_data()
    
    print("\n✅ 清理和验证完成!")
