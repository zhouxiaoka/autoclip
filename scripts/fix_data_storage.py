#!/usr/bin/env python3
"""
修复数据存储问题
手动触发数据存储，解决前端显示0个切片和0个合集的问题
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置环境变量
import os
os.environ['PYTHONPATH'] = str(project_root)

# 添加backend目录到路径
backend_dir = project_root / "backend"
sys.path.insert(0, str(backend_dir))

from backend.core.database import SessionLocal
from backend.services.pipeline_adapter import PipelineAdapter
from backend.models.project import Project

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_project_data_storage(project_id: str):
    """修复项目数据存储"""
    print(f"🔧 修复项目数据存储: {project_id}")
    
    try:
        db = SessionLocal()
        
        try:
            # 验证项目是否存在
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                print(f"❌ 项目不存在: {project_id}")
                return False
            
            print(f"✅ 项目存在: {project.name}")
            
            # 创建Pipeline适配器
            adapter = PipelineAdapter(db, None, project_id)
            
            # 获取项目目录
            project_dir = adapter.data_dir / "projects" / project_id
            
            # 检查数据文件是否存在
            clips_file = project_dir / "step4_title" / "step4_title.json"
            collections_file = project_dir / "step5_clustering" / "step5_clustering.json"
            
            if not clips_file.exists():
                print(f"❌ 切片数据文件不存在: {clips_file}")
                return False
            
            if not collections_file.exists():
                print(f"❌ 合集数据文件不存在: {collections_file}")
                return False
            
            print(f"✅ 数据文件存在")
            
            # 保存切片数据到数据库
            print("📝 保存切片数据到数据库...")
            adapter._save_clips_to_database(project_id, clips_file)
            
            # 保存合集数据到数据库
            print("📝 保存合集数据到数据库...")
            adapter._save_collections_to_database(project_id, collections_file)
            
            print("✅ 数据存储修复完成")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        return False

def check_database_data(project_id: str):
    """检查数据库中的数据"""
    print(f"🔍 检查数据库数据: {project_id}")
    
    try:
        db = SessionLocal()
        
        try:
            # 检查切片数据
            from backend.models.clip import Clip
            clips = db.query(Clip).filter(Clip.project_id == project_id).all()
            print(f"📊 数据库中的切片数量: {len(clips)}")
            
            if clips:
                for clip in clips[:3]:  # 显示前3个切片
                    print(f"   - {clip.title} (ID: {clip.id})")
            
            # 检查合集数据
            from backend.models.collection import Collection
            collections = db.query(Collection).filter(Collection.project_id == project_id).all()
            print(f"📊 数据库中的合集数量: {len(collections)}")
            
            if collections:
                for collection in collections:
                    print(f"   - {collection.name} (ID: {collection.id})")
            
            return len(clips), len(collections)
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return 0, 0

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="修复数据存储问题")
    parser.add_argument("--project-id", type=str, required=True, help="项目ID")
    parser.add_argument("--check-only", action="store_true", help="仅检查数据，不修复")
    
    args = parser.parse_args()
    
    project_id = args.project_id
    
    if args.check_only:
        # 仅检查数据
        check_database_data(project_id)
    else:
        # 检查并修复数据
        print("🔍 修复前检查...")
        clips_before, collections_before = check_database_data(project_id)
        
        print("\n🔧 开始修复...")
        success = fix_project_data_storage(project_id)
        
        if success:
            print("\n🔍 修复后检查...")
            clips_after, collections_after = check_database_data(project_id)
            
            print(f"\n📊 修复结果:")
            print(f"   切片: {clips_before} -> {clips_after}")
            print(f"   合集: {collections_before} -> {collections_after}")
            
            if clips_after > clips_before or collections_after > collections_before:
                print("✅ 数据存储修复成功！")
            else:
                print("⚠️ 数据存储修复可能失败，请检查日志")
        else:
            print("❌ 数据存储修复失败")

if __name__ == "__main__":
    main()
