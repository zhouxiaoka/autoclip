#!/usr/bin/env python3
"""
数据库初始化脚本
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(current_dir / "backend"))

# 设置工作目录
import os
os.chdir(current_dir)

def init_database():
    """初始化数据库"""
    print("🚀 开始初始化数据库...")
    
    try:
        # 导入所有模型确保表被创建
        from backend.models import Base, BilibiliAccount, UploadRecord
        from backend.core.database import init_database, create_tables
        
        print("✅ 所有模型导入成功")
        
        # 初始化数据库
        if init_database():
            print("✅ 数据库初始化成功")
        else:
            print("❌ 数据库初始化失败")
            return False
        
        # 创建表
        create_tables()
        print("✅ 数据库表创建成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        return False

if __name__ == "__main__":
    success = init_database()
    if success:
        print("\n🎉 数据库初始化完成！")
        print("现在可以启动系统了：")
        print("1. ./start_autoclip_with_upload.sh")
        print("2. 或者手动启动各个服务")
    else:
        print("\n❌ 数据库初始化失败，请检查错误信息")
        sys.exit(1)

