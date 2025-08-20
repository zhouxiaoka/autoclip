#!/usr/bin/env python3
"""
更新切片元数据
更新数据库中现有切片的clip_metadata字段，添加完整的元数据
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

def update_clip_metadata(project_id: str):
    """更新项目切片的元数据"""
    print(f"🔧 更新项目切片元数据: {project_id}")
    
    try:
        db = SessionLocal()
        
        try:
            # 获取项目的所有切片
            clips = db.query(Clip).filter(Clip.project_id == project_id).all()
            print(f"📊 找到 {len(clips)} 个切片")
            
            updated_count = 0
            
            for clip in clips:
                try:
                    # 获取元数据文件路径
                    metadata_file = clip.clip_metadata.get('metadata_file') if clip.clip_metadata else None
                    
                    if not metadata_file or not Path(metadata_file).exists():
                        print(f"⚠️ 切片 {clip.id} 的元数据文件不存在: {metadata_file}")
                        continue
                    
                    # 读取元数据文件
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        metadata_data = json.load(f)
                    
                    # 更新clip_metadata字段
                    updated_metadata = {
                        'metadata_file': metadata_file,
                        'clip_id': clip.id,
                        'created_at': clip.clip_metadata.get('created_at', ''),
                        # 添加完整的元数据字段
                        'recommend_reason': metadata_data.get('recommend_reason', ''),
                        'outline': metadata_data.get('outline', ''),
                        'content': metadata_data.get('content', []),
                        'chunk_index': metadata_data.get('chunk_index', 0),
                        'generated_title': metadata_data.get('generated_title', ''),
                        'id': metadata_data.get('id', '')  # 添加id字段
                    }
                    
                    # 更新数据库
                    clip.clip_metadata = updated_metadata
                    updated_count += 1
                    
                    print(f"✅ 更新切片 {clip.id}: {clip.title}")
                    
                except Exception as e:
                    print(f"❌ 更新切片 {clip.id} 失败: {e}")
                    continue
            
            # 提交更改
            db.commit()
            print(f"✅ 成功更新 {updated_count}/{len(clips)} 个切片的元数据")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ 更新失败: {e}")

def update_collection_metadata(project_id: str):
    """更新项目合集的元数据"""
    print(f"🔧 更新项目合集元数据: {project_id}")
    
    try:
        db = SessionLocal()
        
        try:
            # 获取项目的所有合集
            collections = db.query(Collection).filter(Collection.project_id == project_id).all()
            print(f"📊 找到 {len(collections)} 个合集")
            
            updated_count = 0
            
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
                    
                    # 更新collection_metadata字段
                    updated_metadata = {
                        'metadata_file': metadata_file,
                        'clip_ids': metadata_data.get('clip_ids', []),
                        'collection_type': 'ai_recommended',
                        'collection_id': collection.id,
                        'created_at': collection.collection_metadata.get('created_at', ''),
                        # 添加完整的元数据字段
                        'collection_title': metadata_data.get('collection_title', ''),
                        'collection_summary': metadata_data.get('collection_summary', '')
                    }
                    
                    # 更新数据库
                    collection.collection_metadata = updated_metadata
                    updated_count += 1
                    
                    print(f"✅ 更新合集 {collection.id}: {collection.name}")
                    
                except Exception as e:
                    print(f"❌ 更新合集 {collection.id} 失败: {e}")
                    continue
            
            # 提交更改
            db.commit()
            print(f"✅ 成功更新 {updated_count}/{len(collections)} 个合集的元数据")
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ 更新失败: {e}")

def test_api_response(project_id: str):
    """测试API响应"""
    print(f"🧪 测试API响应: {project_id}")
    
    try:
        import requests
        
        # 测试切片API
        clips_response = requests.get(f"http://localhost:8000/api/v1/clips/?project_id={project_id}")
        if clips_response.status_code == 200:
            clips_data = clips_response.json()
            print(f"✅ 切片API返回 {len(clips_data['items'])} 个切片")
            
            if clips_data['items']:
                first_clip = clips_data['items'][0]
                metadata = first_clip.get('clip_metadata', {})
                print(f"   第一个切片的元数据:")
                print(f"   - recommend_reason: {metadata.get('recommend_reason', '无')}")
                print(f"   - outline: {metadata.get('outline', '无')}")
                print(f"   - content: {len(metadata.get('content', []))} 个要点")
        
        # 测试合集API
        collections_response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
        if collections_response.status_code == 200:
            collections_data = collections_response.json()
            print(f"✅ 合集API返回 {len(collections_data['items'])} 个合集")
            
            if collections_data['items']:
                first_collection = collections_data['items'][0]
                metadata = first_collection.get('collection_metadata', {})
                print(f"   第一个合集的元数据:")
                print(f"   - collection_title: {metadata.get('collection_title', '无')}")
                print(f"   - collection_summary: {metadata.get('collection_summary', '无')}")
        
    except Exception as e:
        print(f"❌ API测试失败: {e}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="更新切片和合集元数据")
    parser.add_argument("--project-id", type=str, required=True, help="项目ID")
    parser.add_argument("--test-only", action="store_true", help="仅测试API响应")
    
    args = parser.parse_args()
    
    project_id = args.project_id
    
    if args.test_only:
        # 仅测试API响应
        test_api_response(project_id)
    else:
        # 更新元数据并测试
        print("🔧 开始更新元数据...")
        update_clip_metadata(project_id)
        update_collection_metadata(project_id)
        
        print("\n🧪 测试API响应...")
        test_api_response(project_id)

if __name__ == "__main__":
    main()
