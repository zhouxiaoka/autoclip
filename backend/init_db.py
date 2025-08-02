#!/usr/bin/env python3
"""
数据库初始化脚本
重新创建所有数据库表
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database import engine, create_tables
from models.base import Base
from models import project, clip, collection, task

def init_database():
    """初始化数据库"""
    print("🗄️  正在初始化数据库...")
    
    try:
        # 先删除所有表
        Base.metadata.drop_all(bind=engine)
        # 再创建所有表
        Base.metadata.create_all(bind=engine)
        print("✅ 数据库表创建成功")
        
        # 验证表是否创建
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"📋 已创建的表: {tables}")
        
        return True
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False

if __name__ == "__main__":
    success = init_database()
    exit(0 if success else 1) 