"""
数据库迁移脚本
添加celery_task_id字段到tasks表
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import os

def add_celery_task_id_column():
    """添加celery_task_id字段"""
    
    # 数据库路径 - 使用项目根目录的数据库文件
    db_path = Path("autoclip.db")
    
    # 创建数据库引擎
    engine = create_engine(f"sqlite:///{db_path}")
    
    try:
        with engine.connect() as conn:
            # 检查字段是否已存在
            result = conn.execute(text("PRAGMA table_info(tasks)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'celery_task_id' not in columns:
                # 添加celery_task_id字段
                conn.execute(text("""
                    ALTER TABLE tasks 
                    ADD COLUMN celery_task_id VARCHAR(255)
                """))
                conn.commit()
                print("✅ 已添加celery_task_id字段到tasks表")
            else:
                print("ℹ️  celery_task_id字段已存在")
                
    except Exception as e:
        print(f"❌ 添加字段失败: {e}")
        raise

if __name__ == "__main__":
    add_celery_task_id_column() 