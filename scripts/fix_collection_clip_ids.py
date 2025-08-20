#!/usr/bin/env python3
"""
修复合集中的clip_ids映射问题
将chunk_index映射到实际的切片UUID
"""

import sys
import json
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
from backend.models.clip import Clip
from backend.models.collection import Collection

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_collection_clip_ids(project_id: str):
    """修复合集中的clip_ids映射"""
    print(f"🔧 修复合集中的clip_ids映射: {project_id}")
    
    try:
        db = SessionLocal()
        
        try:
            # 获取项目的所有切片，按chunk_index排序
            clips = db.query(Clip).filter(Clip.project_id == project_id).all()
            print(f"📊 找到 {len(clips)} 个切片")
            
            # 创建metadata_id到clip_id的映射
            metadata_id_to_clip_mapping = {}
            for clip in clips:
                metadata = clip.clip_metadata or {}
                metadata_id = metadata.get('id')
                if metadata_id:
                    metadata_id_to_clip_mapping[str(metadata_id)] = clip.id
                    print(f"   映射: metadata_id {metadata_id} -> clip_id {clip.id}")
            
            # 获取项目的所有合集
            collections = db.query(Collection).filter(Collection.project_id == project_id).all()
            print(f"📊 找到 {len(collections)} 个合集")
            
            for collection in collections:
                try:
                    # 获取元数据文件路径
                    metadata_file = collection.collection_metadata.get('metadata_file') if collection.collection_metadata else None
                    
                    if not metadata_file or not Path(metadata_file).exists():
                        print(f"⚠️ 合集 {collection.id} 的元数据文件不存在: {metadata_file}")
                        continue
                    
                    # 读取元数据文件
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata_data = json.load(f)
                    
                    # 获取原始的clip_ids（metadata_id）
                    original_clip_ids = metadata_data.get('clip_ids', [])
                    print(f"   合集 {collection.id} 原始clip_ids: {original_clip_ids}")
                    
                    # 映射到实际的clip_id
                    mapped_clip_ids = []
                    for metadata_id in original_clip_ids:
                        if metadata_id in metadata_id_to_clip_mapping:
                            mapped_clip_ids.append(metadata_id_to_clip_mapping[metadata_id])
                        else:
                            print(f"   ⚠️ 未找到metadata_id {metadata_id} 对应的clip_id")
                    
                    print(f"   映射后的clip_ids: {mapped_clip_ids}")
                    
                    # 更新数据库中的clip_ids（通过collection_metadata）
                    if collection.collection_metadata:
                        collection.collection_metadata['clip_ids'] = mapped_clip_ids
                    
                    print(f"✅ 更新合集 {collection.id}: {collection.name}")
                    
                except Exception as e:
                    print(f"❌ 更新合集 {collection.id} 失败: {e}")
                    continue
            
            # 提交更改
            db.commit()
            print(f"✅ 成功修复 {len(collections)} 个合集的clip_ids映射")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ 修复失败: {e}")

def test_collection_data(project_id: str):
    """测试合集数据"""
    print(f"🧪 测试合集数据: {project_id}")
    
    try:
        import requests
        
        # 测试合集API
        collections_response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
        if collections_response.status_code == 200:
            collections_data = collections_response.json()
            collections = collections_data.get('items', [])
            print(f"✅ 合集API返回 {len(collections)} 个合集")
            
            for collection in collections:
                print(f"   合集: {collection['name']}")
                print(f"   - clip_ids: {collection.get('clip_ids', [])}")
                print(f"   - total_clips: {collection.get('total_clips', 0)}")
                
                # 检查clip_ids是否对应实际的切片
                clip_ids = collection.get('clip_ids', [])
                if clip_ids:
                    clips_response = requests.get(f"http://localhost:8000/api/v1/clips/?project_id={project_id}")
                    if clips_response.status_code == 200:
                        clips_data = clips_response.json()
                        all_clip_ids = [clip['id'] for clip in clips_data.get('items', [])]
                        
                        valid_clips = [clip_id for clip_id in clip_ids if clip_id in all_clip_ids]
                        print(f"   - 有效切片: {len(valid_clips)}/{len(clip_ids)}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="修复合集中的clip_ids映射")
    parser.add_argument("--project-id", type=str, required=True, help="项目ID")
    parser.add_argument("--test-only", action="store_true", help="仅测试数据")
    
    args = parser.parse_args()
    
    project_id = args.project_id
    
    if args.test_only:
        # 仅测试数据
        test_collection_data(project_id)
    else:
        # 修复并测试
        print("🔧 开始修复clip_ids映射...")
        fix_collection_clip_ids(project_id)
        
        print("\n🧪 测试修复结果...")
        test_collection_data(project_id)

if __name__ == "__main__":
    main()
