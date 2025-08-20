#!/usr/bin/env python3
"""
模拟前端的完整调用流程
"""

import requests
import json
from typing import List

def simulate_frontend_flow():
    """模拟前端的完整调用流程"""
    
    # 测试数据
    project_id = "5c48803d-0aa7-48d7-a270-2b33e4954f25"
    collection_id = "0e181e1a-52c2-42c2-9481-cc306e3b27f9"
    
    print("🎯 模拟前端的完整调用流程")
    print("=" * 50)
    
    # 1. 模拟前端获取项目数据
    print("\n1️⃣ 模拟前端获取项目数据...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/projects/{project_id}")
        if response.status_code == 200:
            project = response.json()
            print(f"✅ 项目: {project.get('name', 'Unknown')}")
        else:
            print(f"❌ 获取项目失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 获取项目异常: {e}")
        return
    
    # 2. 模拟前端获取合集数据
    print("\n2️⃣ 模拟前端获取合集数据...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
        if response.status_code == 200:
            collections_data = response.json()
            collections = collections_data.get('items', []) if isinstance(collections_data, dict) else collections_data
            
            target_collection = None
            for collection in collections:
                if collection.get('id') == collection_id:
                    target_collection = collection
                    break
            
            if target_collection:
                print(f"✅ 找到合集: {target_collection.get('name', 'Unknown')}")
                current_clip_ids = target_collection.get('clip_ids', [])
                print(f"📋 当前clip_ids: {current_clip_ids}")
            else:
                print("❌ 未找到目标合集")
                return
        else:
            print(f"❌ 获取合集失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 获取合集异常: {e}")
        return
    
    if len(current_clip_ids) < 2:
        print("⚠️  clip_ids数量不足，无法测试排序")
        return
    
    # 3. 模拟前端拖拽排序
    print("\n3️⃣ 模拟前端拖拽排序...")
    print("模拟用户拖拽第一个切片到第二个位置")
    
    # 交换前两个元素
    new_clip_ids = current_clip_ids[1:] + current_clip_ids[:1]
    print(f"📤 新顺序: {new_clip_ids}")
    
    # 4. 模拟前端调用store的reorderCollectionClips方法
    print("\n4️⃣ 模拟前端调用store的reorderCollectionClips方法...")
    try:
        # 模拟前端的API调用
        response = requests.patch(
            f"http://localhost:8000/api/v1/collections/{collection_id}/reorder",
            json=new_clip_ids,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"📥 响应状态: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 排序成功: {result.get('clip_ids', [])}")
            
            # 检查返回的数据是否正确
            if result.get('clip_ids') == new_clip_ids:
                print("✅ 返回数据正确")
            else:
                print("❌ 返回数据不正确")
        else:
            print(f"❌ 排序失败: {response.text}")
            return
    except Exception as e:
        print(f"❌ 排序异常: {e}")
        return
    
    # 5. 模拟前端重新获取数据验证
    print("\n5️⃣ 模拟前端重新获取数据验证...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
        if response.status_code == 200:
            collections_data = response.json()
            collections = collections_data.get('items', []) if isinstance(collections_data, dict) else collections_data
            
            target_collection = None
            for collection in collections:
                if collection.get('id') == collection_id:
                    target_collection = collection
                    break
            
            if target_collection:
                updated_clip_ids = target_collection.get('clip_ids', [])
                print(f"✅ 验证结果: {updated_clip_ids}")
                
                if updated_clip_ids == new_clip_ids:
                    print("✅ 前端验证成功！排序功能完全正常")
                else:
                    print("❌ 前端验证失败，数据没有更新")
            else:
                print("❌ 验证时未找到目标合集")
        else:
            print(f"❌ 验证失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 验证异常: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 前端调用流程模拟完成！")

if __name__ == "__main__":
    simulate_frontend_flow()
