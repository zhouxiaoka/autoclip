#!/usr/bin/env python3
"""
修复所有项目的数据同步问题
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 添加backend目录到路径
backend_dir = project_root / "backend"
sys.path.insert(0, str(backend_dir))

from core.database import SessionLocal
from services.data_sync_service import DataSyncService
from core.config import get_data_directory

def fix_all_projects():
    """修复所有项目的数据同步问题"""
    db = SessionLocal()
    try:
        data_sync_service = DataSyncService(db)
        data_dir = get_data_directory()
        projects_dir = data_dir / "projects"
        
        print(f"开始修复所有项目数据...")
        print(f"数据目录: {data_dir}")
        
        fixed_projects = []
        failed_projects = []
        
        # 遍历所有项目目录
        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                project_id = project_dir.name
                try:
                    print(f"\n处理项目: {project_id}")
                    
                    # 同步项目数据
                    result = data_sync_service.sync_project_from_filesystem(project_id, project_dir)
                    
                    if result["success"]:
                        clips_count = result.get('clips_synced', 0)
                        collections_count = result.get('collections_synced', 0)
                        print(f"  ✅ 成功: 切片 {clips_count} 个, 合集 {collections_count} 个")
                        fixed_projects.append({
                            "project_id": project_id,
                            "clips": clips_count,
                            "collections": collections_count
                        })
                    else:
                        print(f"  ❌ 失败: {result.get('error', '未知错误')}")
                        failed_projects.append({"project_id": project_id, "error": result.get('error')})
                        
                except Exception as e:
                    print(f"  ❌ 异常: {str(e)}")
                    failed_projects.append({"project_id": project_id, "error": str(e)})
        
        # 输出总结
        print(f"\n📊 修复完成!")
        print(f"   成功修复: {len(fixed_projects)} 个项目")
        print(f"   失败: {len(failed_projects)} 个项目")
        
        if fixed_projects:
            print(f"\n✅ 成功修复的项目:")
            for project in fixed_projects:
                print(f"   - {project['project_id']}: 切片 {project['clips']} 个, 合集 {project['collections']} 个")
        
        if failed_projects:
            print(f"\n❌ 失败的项目:")
            for project in failed_projects:
                print(f"   - {project['project_id']}: {project['error']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 修复过程中发生错误: {str(e)}")
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
        
        print(f"\n📊 数据库状态:")
        print(f"   项目总数: {total_projects}")
        print(f"   切片总数: {total_clips}")
        print(f"   合集总数: {total_collections}")
        
        # 显示有数据的项目
        print(f"\n📋 有数据的项目:")
        projects = db.query(Project).all()
        for project in projects:
            clips_count = db.query(Clip).filter(Clip.project_id == project.id).count()
            collections_count = db.query(Collection).filter(Collection.project_id == project.id).count()
            if clips_count > 0 or collections_count > 0:
                print(f"   - {project.id}: {project.name} (切片: {clips_count}, 合集: {collections_count})")
        
    except Exception as e:
        print(f"❌ 检查数据库状态失败: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🔧 开始修复所有项目的数据同步问题...")
    success = fix_all_projects()
    if success:
        check_database_status()
    else:
        print("❌ 修复失败")
