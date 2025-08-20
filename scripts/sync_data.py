#!/usr/bin/env python3
"""
简单的数据同步脚本
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
os.environ['PYTHONPATH'] = str(project_root)

from backend.core.database import SessionLocal
from backend.services.data_sync_service import DataSyncService
from backend.core.config import get_data_directory

def sync_project_data(project_id: str):
    """同步项目数据到数据库"""
    db = SessionLocal()
    try:
        data_sync_service = DataSyncService(db)
        data_dir = get_data_directory()
        project_dir = data_dir / "projects" / project_id
        
        if not project_dir.exists():
            print(f"❌ 项目目录不存在: {project_dir}")
            return False
        
        print(f"开始同步项目: {project_id}")
        
        # 同步数据到数据库
        result = data_sync_service.sync_project_data(project_id, project_dir)
        
        print(f"✅ 同步完成: {result}")
        return True
        
    except Exception as e:
        print(f"❌ 同步失败: {str(e)}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python scripts/sync_data.py <project_id>")
        sys.exit(1)
    
    project_id = sys.argv[1]
    sync_project_data(project_id)

