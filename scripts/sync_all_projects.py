#!/usr/bin/env python3
"""
同步所有项目数据到数据库
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

# 添加backend目录到路径
backend_dir = project_root / "backend"
sys.path.insert(0, str(backend_dir))

from core.database import SessionLocal
from services.data_sync_service import DataSyncService
from core.config import get_data_directory

def sync_all_projects():
    """同步所有项目数据到数据库"""
    db = SessionLocal()
    try:
        data_sync_service = DataSyncService(db)
        data_dir = get_data_directory()
        
        print(f"开始同步所有项目数据...")
        print(f"数据目录: {data_dir}")
        
        # 同步所有项目
        result = data_sync_service.sync_all_projects_from_filesystem(data_dir)
        
        if result["success"]:
            print(f"✅ 同步完成!")
            print(f"   成功同步: {result['total_synced']} 个项目")
            print(f"   失败: {result['total_failed']} 个项目")
            
            if result['synced_projects']:
                print(f"   成功同步的项目:")
                for project_id in result['synced_projects']:
                    print(f"     - {project_id}")
            
            if result['failed_projects']:
                print(f"   失败的项目:")
                for failed in result['failed_projects']:
                    print(f"     - {failed['project_id']}: {failed['error']}")
        else:
            print(f"❌ 同步失败: {result.get('error', '未知错误')}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 同步过程中发生错误: {str(e)}")
        return False
    finally:
        db.close()

def sync_specific_project(project_id: str):
    """同步特定项目"""
    db = SessionLocal()
    try:
        data_sync_service = DataSyncService(db)
        data_dir = get_data_directory()
        project_dir = data_dir / "projects" / project_id
        
        if not project_dir.exists():
            print(f"❌ 项目目录不存在: {project_dir}")
            return False
        
        print(f"开始同步项目: {project_id}")
        
        # 同步项目数据
        result = data_sync_service.sync_project_from_filesystem(project_id, project_dir)
        
        if result["success"]:
            print(f"✅ 项目 {project_id} 同步成功")
            print(f"   切片: {result.get('clips_synced', 0)} 个")
            print(f"   合集: {result.get('collections_synced', 0)} 个")
        else:
            print(f"❌ 项目 {project_id} 同步失败: {result.get('error', '未知错误')}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ 同步项目 {project_id} 时发生错误: {str(e)}")
        return False
    finally:
        db.close()

def check_database_status():
    """检查数据库状态"""
    db = SessionLocal()
    try:
        from models.project import Project
        from models.clip import Clip
        from models.collection import Collection
        
        # 统计数据库中的数据
        total_projects = db.query(Project).count()
        total_clips = db.query(Clip).count()
        total_collections = db.query(Collection).count()
        
        print(f"📊 数据库状态:")
        print(f"   项目总数: {total_projects}")
        print(f"   切片总数: {total_clips}")
        print(f"   合集总数: {total_collections}")
        
        # 显示项目列表
        if total_projects > 0:
            print(f"\n📋 项目列表:")
            projects = db.query(Project).all()
            for project in projects:
                clips_count = db.query(Clip).filter(Clip.project_id == project.id).count()
                collections_count = db.query(Collection).filter(Collection.project_id == project.id).count()
                print(f"   - {project.id}: {project.name} (切片: {clips_count}, 合集: {collections_count})")
        
    except Exception as e:
        print(f"❌ 检查数据库状态失败: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # 同步所有项目
        print("🔄 开始同步所有项目数据...")
        success = sync_all_projects()
        if success:
            print("\n📊 同步后的数据库状态:")
            check_database_status()
    elif len(sys.argv) == 2:
        if sys.argv[1] == "status":
            # 检查状态
            check_database_status()
        else:
            # 同步特定项目
            project_id = sys.argv[1]
            success = sync_specific_project(project_id)
            if success:
                print(f"\n📊 项目 {project_id} 同步后的状态:")
                check_database_status()
    else:
        print("用法:")
        print("  python sync_all_projects.py          # 同步所有项目")
        print("  python sync_all_projects.py status   # 检查数据库状态")
        print("  python sync_all_projects.py <project_id>  # 同步特定项目")
