#!/usr/bin/env python3
"""
重新创建数据库表
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 添加backend目录到路径
backend_dir = project_root / "backend"
sys.path.insert(0, str(backend_dir))

from core.database import create_tables, engine
from models.base import Base

def main():
    """重新创建数据库表"""
    print("🚀 重新创建数据库表...")
    
    try:
        # 删除所有表
        Base.metadata.drop_all(bind=engine)
        print("🗑️ 已删除所有表")
        
        # 重新创建所有表
        create_tables()
        print("✅ 已重新创建所有表")
        
        # 验证表结构
        from sqlalchemy import inspect
        inspector = inspect(engine)
        
        tables = inspector.get_table_names()
        print(f"📊 数据库表: {tables}")
        
        for table_name in tables:
            columns = inspector.get_columns(table_name)
            print(f"\n📋 {table_name} 表结构:")
            for column in columns:
                print(f"  - {column['name']}: {column['type']}")
        
        print("\n🎉 数据库重新创建完成！")
        
    except Exception as e:
        print(f"❌ 重新创建数据库失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
