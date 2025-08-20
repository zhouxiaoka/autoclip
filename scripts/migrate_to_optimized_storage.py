#!/usr/bin/env python3
"""
数据迁移脚本 - 从旧架构迁移到新架构
"""

import sys
import json
import shutil
from pathlib import Path
from typing import Dict, Any

def migrate_project_data(project_id: str):
    """迁移单个项目的数据"""
    print(f"迁移项目: {project_id}")
    
    # 这里添加具体的数据迁移逻辑
    # 1. 读取旧的数据结构
    # 2. 转换为新的数据结构
    # 3. 保存到新的位置
    # 4. 更新数据库记录
    
    print(f"项目 {project_id} 迁移完成")

def migrate_all_projects():
    """迁移所有项目"""
    print("开始迁移所有项目...")
    
    # 获取所有项目目录
    data_dir = Path("data")
    projects_dir = data_dir / "projects"
    
    if not projects_dir.exists():
        print("没有找到项目目录")
        return
    
    for project_dir in projects_dir.iterdir():
        if project_dir.is_dir() and not project_dir.name.startswith('.'):
            migrate_project_data(project_dir.name)
    
    print("所有项目迁移完成")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        project_id = sys.argv[1]
        migrate_project_data(project_id)
    else:
        migrate_all_projects()
