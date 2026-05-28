#!/usr/bin/env python3
"""
清空数据库中的所有项目数据
"""
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.core.database import get_db
from backend.models.project import Project
from backend.models.clip import Clip
from backend.models.collection import Collection
from backend.models.task import Task
from sqlalchemy.orm import Session

def clean_database():
    """清空数据库中的所有项目相关数据"""
    print("🧹 开始清理数据库...")
    
    # 获取数据库会话
    db = next(get_db())
    
    try:
        # 删除所有数据（按依赖关系顺序）
        print("删除任务数据...")
        deleted_tasks = db.query(Task).delete()
        print(f"✅ 删除了 {deleted_tasks} 个任务")
        
        print("删除合集数据...")
        deleted_collections = db.query(Collection).delete()
        print(f"✅ 删除了 {deleted_collections} 个合集")
        
        print("删除切片数据...")
        deleted_clips = db.query(Clip).delete()
        print(f"✅ 删除了 {deleted_clips} 个切片")
        
        print("删除项目数据...")
        deleted_projects = db.query(Project).delete()
        print(f"✅ 删除了 {deleted_projects} 个项目")
        
        # 提交事务
        db.commit()
        
        print("\n🎉 数据库清理完成!")
        print("现在数据库是干净的，没有任何项目数据")
        
    except Exception as e:
        print(f"❌ 清理数据库时发生错误: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    clean_database()
