#!/usr/bin/env python3
"""
模拟前端实际的合集排序调用
"""

import requests
import json
from typing import List

def test_frontend_reorder():
    """模拟前端实际的排序调用"""
    
    # 测试数据
    project_id = "5c48803d-0aa7-48d7-a270-2b33e4954f25"
    collection_id = "0e181e1a-52c2-42c2-9481-cc306e3b27f9"
    
    print("🔍 模拟前端合集排序调用...")
    
    # 1. 获取当前合集信息
    print("\n1️⃣ 获取当前合集信息...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/{collection_id}")
        if response.status_code == 200:
            collection = response.json()
            print(f"✅ 当前合集: {collection['name']}")
            print(f"📋 当前clip_ids: {collection.get('clip_ids', [])}")
            current_clip_ids = collection.get('clip_ids', [])
        else:
            print(f"❌ 获取合集失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 获取合集异常: {e}")
        return
    
    if len(current_clip_ids) < 2:
        print("⚠️  clip_ids数量不足，无法测试排序")
        return
    
    # 2. 模拟前端store中的reorderCollectionClips调用
    print("\n2️⃣ 模拟前端store调用...")
    try:
        # 交换前两个元素
        new_clip_ids = current_clip_ids[1:] + current_clip_ids[:1]
        
        print(f"📤 前端调用: projectApi.reorderCollectionClips('{collection_id}', {new_clip_ids})")
        
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
        else:
            print(f"❌ 排序失败: {response.text}")
            return
    except Exception as e:
        print(f"❌ 前端调用异常: {e}")
        return
    
    # 3. 验证更新结果
    print("\n3️⃣ 验证更新结果...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/{collection_id}")
        if response.status_code == 200:
            updated_collection = response.json()
            print(f"✅ 更新后的clip_ids: {updated_collection.get('clip_ids', [])}")
            
            # 检查是否真的更新了
            if updated_collection.get('clip_ids') == new_clip_ids:
                print("✅ 排序更新成功！")
            else:
                print("❌ 排序更新失败，数据没有变化")
        else:
            print(f"❌ 验证失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 验证异常: {e}")
    
    # 4. 测试前端的错误处理
    print("\n4️⃣ 测试错误处理...")
    try:
        # 测试无效的collection_id
        invalid_collection_id = "invalid-id"
        response = requests.patch(
            f"http://localhost:8000/api/v1/collections/{invalid_collection_id}/reorder",
            json=new_clip_ids,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"📥 无效ID响应状态: {response.status_code}")
        if response.status_code == 404:
            print("✅ 错误处理正常")
        else:
            print(f"❌ 错误处理异常: {response.text}")
    except Exception as e:
        print(f"❌ 错误处理测试异常: {e}")

if __name__ == "__main__":
    test_frontend_reorder()
