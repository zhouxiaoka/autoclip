#!/usr/bin/env python3
"""
测试同步特定项目
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

def test_sync_project(project_id: str):
    """测试同步特定项目"""
    db = SessionLocal()
    try:
        data_sync_service = DataSyncService(db)
        data_dir = get_data_directory()
        project_dir = data_dir / "projects" / project_id
        
        print(f"项目目录: {project_dir}")
        print(f"项目目录存在: {project_dir.exists()}")
        
        if project_dir.exists():
            print(f"项目目录内容:")
            for item in project_dir.iterdir():
                print(f"  - {item.name}")
        
        # 检查切片文件
        step4_file = project_dir / "step4_titles.json"
        print(f"\n检查切片文件: {step4_file}")
        print(f"文件存在: {step4_file.exists()}")
        
        if step4_file.exists():
            try:
                with open(step4_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"文件内容长度: {len(data)}")
                print(f"第一个切片: {data[0] if data else 'None'}")
            except Exception as e:
                print(f"读取文件失败: {e}")
        
        # 手动同步
        print(f"\n开始手动同步...")
        result = data_sync_service.sync_project_from_filesystem(project_id, project_dir)
        print(f"同步结果: {result}")
        
    except Exception as e:
        print(f"错误: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    project_id = "1fdb0bf1-7f3c-44f7-a69d-90c5a1d26fbe"
    test_sync_project(project_id)
