#!/usr/bin/env python3
"""
为所有合集生成封面缩略图
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.core.database import get_db
from backend.models.collection import Collection
from backend.utils.video_processor import VideoProcessor
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_collection_thumbnails():
    """为所有没有封面的合集生成缩略图"""
    try:
        db = next(get_db())
        
        # 查找所有没有封面的合集
        collections_without_thumbnails = db.query(Collection).filter(
            Collection.thumbnail_path.is_(None)
        ).all()
        
        if not collections_without_thumbnails:
            logger.info("所有合集都已经有封面了")
            return True
        
        logger.info(f"找到 {len(collections_without_thumbnails)} 个没有封面的合集")
        
        success_count = 0
        for collection in collections_without_thumbnails:
            try:
                logger.info(f"正在为合集 '{collection.name}' ({collection.id}) 生成封面...")
                
                # 检查是否有导出视频文件
                if not collection.export_path:
                    logger.warning(f"合集 '{collection.name}' 没有导出视频文件，跳过")
                    continue
                
                video_path = Path(collection.export_path)
                if not video_path.exists():
                    logger.warning(f"合集 '{collection.name}' 的视频文件不存在: {video_path}")
                    continue
                
                # 生成封面文件名
                safe_name = "".join(c for c in collection.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_name = safe_name.replace(' ', '_')
                thumbnail_filename = f"{collection.id}_{safe_name}_thumbnail.jpg"
                thumbnail_path = video_path.parent / thumbnail_filename
                
                # 使用VideoProcessor生成封面
                thumbnail_success = VideoProcessor.extract_thumbnail(video_path, thumbnail_path, time_offset=5)
                
                if thumbnail_success:
                    # 更新数据库
                    collection.thumbnail_path = str(thumbnail_path)
                    db.commit()
                    logger.info(f"✅ 合集 '{collection.name}' 封面生成成功: {thumbnail_path}")
                    success_count += 1
                else:
                    logger.error(f"❌ 合集 '{collection.name}' 封面生成失败")
                    
            except Exception as e:
                logger.error(f"❌ 合集 '{collection.name}' 处理失败: {e}")
                db.rollback()
                continue
        
        logger.info(f"🎉 完成！成功为 {success_count}/{len(collections_without_thumbnails)} 个合集生成封面")
        return True
        
    except Exception as e:
        logger.error(f"❌ 生成合集封面过程中发生错误: {e}")
        return False
    finally:
        db.close()

def generate_thumbnail_for_collection(collection_id: str):
    """为指定合集生成缩略图"""
    try:
        db = next(get_db())
        
        collection = db.query(Collection).filter(Collection.id == collection_id).first()
        if not collection:
            logger.error(f"合集不存在: {collection_id}")
            return False
        
        if collection.thumbnail_path:
            logger.info(f"合集 '{collection.name}' 已经有封面了")
            return True
        
        # 检查是否有导出视频文件
        if not collection.export_path:
            logger.error(f"合集 '{collection.name}' 没有导出视频文件")
            return False
        
        video_path = Path(collection.export_path)
        if not video_path.exists():
            logger.error(f"合集 '{collection.name}' 的视频文件不存在: {video_path}")
            return False
        
        # 生成封面文件名
        safe_name = "".join(c for c in collection.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_name = safe_name.replace(' ', '_')
        thumbnail_filename = f"{collection.id}_{safe_name}_thumbnail.jpg"
        thumbnail_path = video_path.parent / thumbnail_filename
        
        # 使用VideoProcessor生成封面
        thumbnail_success = VideoProcessor.extract_thumbnail(video_path, thumbnail_path, time_offset=5)
        
        if thumbnail_success:
            # 更新数据库
            collection.thumbnail_path = str(thumbnail_path)
            db.commit()
            logger.info(f"✅ 合集 '{collection.name}' 封面生成成功: {thumbnail_path}")
            return True
        else:
            logger.error(f"❌ 合集 '{collection.name}' 封面生成失败")
            return False
            
    except Exception as e:
        logger.error(f"❌ 生成合集封面时发生错误: {e}")
        return False
    finally:
        db.close()

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='为合集生成封面缩略图')
    parser.add_argument('--collection-id', help='为指定合集生成封面')
    parser.add_argument('--all', action='store_true', help='为所有没有封面的合集生成封面')
    
    args = parser.parse_args()
    
    if args.collection_id:
        success = generate_thumbnail_for_collection(args.collection_id)
    elif args.all:
        success = generate_collection_thumbnails()
    else:
        print("请指定 --collection-id 或 --all 参数")
        return
    
    if success:
        print("操作完成")
    else:
        print("操作失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
