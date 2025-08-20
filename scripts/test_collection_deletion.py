#!/usr/bin/env python3
"""
测试合集删除功能的脚本
"""

import sys
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_collection_deletion():
    """测试合集删除功能"""
    print("开始测试合集删除功能...")
    
    # 检查数据目录
    data_dir = Path("data/projects")
    if not data_dir.exists():
        print("❌ 数据目录不存在")
        return
    
    # 查找有合集数据的项目
    projects_with_collections = []
    for project_dir in data_dir.iterdir():
        if project_dir.is_dir() and not project_dir.name.startswith('.'):
            collections_file = project_dir / "step5_collections.json"
            if collections_file.exists():
                try:
                    with open(collections_file, 'r', encoding='utf-8') as f:
                        collections_data = json.load(f)
                    if collections_data:
                        projects_with_collections.append({
                            'project_id': project_dir.name,
                            'collections': collections_data
                        })
                except Exception as e:
                    print(f"❌ 读取项目 {project_dir.name} 的合集数据失败: {e}")
    
    if not projects_with_collections:
        print("❌ 没有找到包含合集数据的项目")
        return
    
    print(f"✅ 找到 {len(projects_with_collections)} 个包含合集数据的项目")
    
    # 测试第一个项目
    test_project = projects_with_collections[0]
    project_id = test_project['project_id']
    collections = test_project['collections']
    
    print(f"\n测试项目: {project_id}")
    print(f"原始合集数量: {len(collections)}")
    
    # 显示合集信息
    for i, collection in enumerate(collections):
        print(f"  合集 {i+1}: {collection.get('collection_title', '无标题')} (ID: {collection.get('id', '无ID')})")
    
    # 检查删除记录文件
    project_dir = data_dir / project_id
    deleted_file = project_dir / ".deleted_collections"
    
    if deleted_file.exists():
        print(f"\n✅ 删除记录文件存在: {deleted_file}")
        try:
            with open(deleted_file, 'r', encoding='utf-8') as f:
                deleted_collections = f.read().splitlines()
            print(f"已删除的合集: {deleted_collections}")
        except Exception as e:
            print(f"❌ 读取删除记录失败: {e}")
    else:
        print(f"\nℹ️  删除记录文件不存在: {deleted_file}")
    
    # 检查collections_metadata.json
    metadata_file = project_dir / "collections_metadata.json"
    if metadata_file.exists():
        print(f"\n✅ 元数据文件存在: {metadata_file}")
        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            print(f"元数据中的合集数量: {len(metadata)}")
        except Exception as e:
            print(f"❌ 读取元数据失败: {e}")
    else:
        print(f"\nℹ️  元数据文件不存在: {metadata_file}")
    
    print("\n✅ 测试完成")

if __name__ == "__main__":
    test_collection_deletion()

