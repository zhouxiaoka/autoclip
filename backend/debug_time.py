#!/usr/bin/env python3
"""
调试脚本：检查项目时间字段
"""

import sys
from pathlib import Path

# 添加backend目录到Python路径
backend_dir = Path(__file__).parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from core.database import SessionLocal
from models.project import Project
from datetime import datetime

def check_project_times():
    """检查项目时间字段"""
    db = SessionLocal()
    try:
        projects = db.query(Project).all()
        
        print(f"找到 {len(projects)} 个项目:")
        print("-" * 80)
        
        for project in projects:
            print(f"项目ID: {project.id}")
            print(f"项目名称: {project.name}")
            print(f"创建时间: {project.created_at} (类型: {type(project.created_at)})")
            print(f"更新时间: {project.updated_at} (类型: {type(project.updated_at)})")
            
            if project.created_at:
                # 计算时间差
                now = datetime.utcnow()
                time_diff = now - project.created_at
                print(f"距离现在: {time_diff}")
            
            print("-" * 40)
            
    except Exception as e:
        print(f"检查失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_project_times() 