#!/usr/bin/env python3
"""
数据迁移脚本 - 将文件系统数据迁移到数据库
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置环境变量
import os
os.environ['PYTHONPATH'] = str(project_root)

from backend.core.database import SessionLocal
from backend.services.data_sync_service import DataSyncService
from backend.core.config import get_data_directory

def migrate_project_data(project_id: str):
    """迁移单个项目的数据到数据库"""
    db = SessionLocal()
    try:
        data_sync_service = DataSyncService(db)
        data_dir = get_data_directory()
        project_dir = data_dir / "projects" / project_id
        
        if not project_dir.exists():
            print(f"❌ 项目目录不存在: {project_dir}")
            return False
        
        print(f"开始迁移项目: {project_id}")
        
        # 同步数据到数据库
        result = data_sync_service.sync_project_data(project_id, project_dir)
        
        print(f"✅ 迁移完成: {result}")
        return True
        
    except Exception as e:
        print(f"❌ 迁移失败: {str(e)}")
        return False
    finally:
        db.close()

def migrate_all_projects():
    """迁移所有项目的数据到数据库"""
    data_dir = get_data_directory()
    projects_dir = data_dir / "projects"
    
    if not projects_dir.exists():
        print("❌ 项目目录不存在")
        return
    
    success_count = 0
    total_count = 0
    
    for project_dir in projects_dir.iterdir():
        if project_dir.is_dir() and not project_dir.name.startswith('.'):
            total_count += 1
            if migrate_project_data(project_dir.name):
                success_count += 1
    
    print(f"\n✅ 迁移完成: {success_count}/{total_count} 个项目成功迁移")

def check_database_data():
    """检查数据库中的数据"""
    db = SessionLocal()
    try:
        from backend.models.project import Project
        from backend.models.collection import Collection
        from backend.models.clip import Clip
        
        # 检查项目数量
        projects_count = db.query(Project).count()
        print(f"数据库中的项目数量: {projects_count}")
        
        # 检查合集数量
        collections_count = db.query(Collection).count()
        print(f"数据库中的合集数量: {collections_count}")
        
        # 检查切片数量
        clips_count = db.query(Clip).count()
        print(f"数据库中的切片数量: {clips_count}")
        
        # 显示一些示例数据
        if collections_count > 0:
            print("\n示例合集数据:")
            collections = db.query(Collection).limit(3).all()
            for collection in collections:
                print(f"  - {collection.name} (ID: {collection.id})")
                metadata = collection.collection_metadata or {}
                clip_ids = metadata.get('clip_ids', [])
                print(f"    包含切片: {clip_ids}")
        
    except Exception as e:
        print(f"❌ 检查数据库数据失败: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "check":
            check_database_data()
        elif sys.argv[1] == "migrate":
            if len(sys.argv) > 2:
                migrate_project_data(sys.argv[2])
            else:
                migrate_all_projects()
        else:
            print("用法:")
            print("  python scripts/migrate_to_database.py check     # 检查数据库数据")
            print("  python scripts/migrate_to_database.py migrate   # 迁移所有项目")
            print("  python scripts/migrate_to_database.py migrate <project_id>  # 迁移指定项目")
    else:
        print("用法:")
        print("  python scripts/migrate_to_database.py check     # 检查数据库数据")
        print("  python scripts/migrate_to_database.py migrate   # 迁移所有项目")
        print("  python scripts/migrate_to_database.py migrate <project_id>  # 迁移指定项目")
