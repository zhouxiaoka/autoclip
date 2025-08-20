#!/usr/bin/env python3
"""
完整测试合集排序功能
"""

import requests
import json
from typing import List

def test_complete_reorder():
    """完整测试合集排序功能"""
    
    # 测试数据
    project_id = "5c48803d-0aa7-48d7-a270-2b33e4954f25"
    collection_id = "0e181e1a-52c2-42c2-9481-cc306e3b27f9"
    
    print("🎯 完整测试合集排序功能")
    print("=" * 50)
    
    # 1. 获取初始状态
    print("\n1️⃣ 获取初始状态...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/{collection_id}")
        if response.status_code == 200:
            collection = response.json()
            print(f"✅ 合集: {collection['name']}")
            initial_clip_ids = collection.get('clip_ids', [])
            print(f"📋 初始clip_ids: {initial_clip_ids}")
        else:
            print(f"❌ 获取合集失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 获取合集异常: {e}")
        return
    
    if len(initial_clip_ids) < 2:
        print("⚠️  clip_ids数量不足，无法测试排序")
        return
    
    # 2. 测试多次排序
    print("\n2️⃣ 测试多次排序...")
    
    # 第一次排序：交换前两个
    print("\n🔄 第一次排序：交换前两个元素")
    new_clip_ids_1 = initial_clip_ids[1:] + initial_clip_ids[:1]
    print(f"📤 新顺序: {new_clip_ids_1}")
    
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/collections/{collection_id}/reorder",
            json=new_clip_ids_1,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 第一次排序成功: {result.get('clip_ids', [])}")
        else:
            print(f"❌ 第一次排序失败: {response.text}")
            return
    except Exception as e:
        print(f"❌ 第一次排序异常: {e}")
        return
    
    # 第二次排序：再次交换前两个
    print("\n🔄 第二次排序：再次交换前两个元素")
    new_clip_ids_2 = new_clip_ids_1[1:] + new_clip_ids_1[:1]
    print(f"📤 新顺序: {new_clip_ids_2}")
    
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/collections/{collection_id}/reorder",
            json=new_clip_ids_2,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 第二次排序成功: {result.get('clip_ids', [])}")
        else:
            print(f"❌ 第二次排序失败: {response.text}")
            return
    except Exception as e:
        print(f"❌ 第二次排序异常: {e}")
        return
    
    # 第三次排序：恢复到原始顺序
    print("\n🔄 第三次排序：恢复到原始顺序")
    print(f"📤 原始顺序: {initial_clip_ids}")
    
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/collections/{collection_id}/reorder",
            json=initial_clip_ids,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 第三次排序成功: {result.get('clip_ids', [])}")
        else:
            print(f"❌ 第三次排序失败: {response.text}")
            return
    except Exception as e:
        print(f"❌ 第三次排序异常: {e}")
        return
    
    # 3. 最终验证
    print("\n3️⃣ 最终验证...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/{collection_id}")
        if response.status_code == 200:
            final_collection = response.json()
            final_clip_ids = final_collection.get('clip_ids', [])
            print(f"✅ 最终clip_ids: {final_clip_ids}")
            
            # 检查是否恢复到原始顺序
            if final_clip_ids == initial_clip_ids:
                print("✅ 排序功能完全正常！数据已恢复到原始顺序")
            else:
                print("❌ 排序功能异常，数据未恢复到原始顺序")
        else:
            print(f"❌ 最终验证失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 最终验证异常: {e}")
    
    # 4. 测试前端API兼容性
    print("\n4️⃣ 测试前端API兼容性...")
    try:
        # 测试前端可能使用的其他API格式
        response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
        if response.status_code == 200:
            collections = response.json()
            if 'items' in collections:
                items = collections['items']
            else:
                items = collections
            
            # 查找我们的合集
            target_collection = None
            for item in items:
                if item.get('id') == collection_id:
                    target_collection = item
                    break
            
            if target_collection:
                print(f"✅ 前端API兼容性正常: {target_collection.get('clip_ids', [])}")
            else:
                print("❌ 前端API兼容性异常：未找到目标合集")
        else:
            print(f"❌ 前端API兼容性测试失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 前端API兼容性测试异常: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 合集排序功能测试完成！")

if __name__ == "__main__":
    test_complete_reorder()
