#!/usr/bin/env python3
"""
测试合集排序功能
"""

import requests
import json
from typing import List

def test_collection_reorder():
    """测试合集排序功能"""
    
    # 测试数据
    project_id = "5c48803d-0aa7-48d7-a270-2b33e4954f25"
    collection_id = "0e181e1a-52c2-42c2-9481-cc306e3b27f9"
    
    # 获取当前合集信息
    print("🔍 获取当前合集信息...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/{collection_id}")
        if response.status_code == 200:
            collection = response.json()
            print(f"✅ 当前合集: {collection['name']}")
            print(f"📋 当前clip_ids: {collection.get('clip_ids', [])}")
        else:
            print(f"❌ 获取合集失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 获取合集异常: {e}")
        return
    
    # 测试新的排序端点
    print("\n🔄 测试新的排序端点: PATCH /collections/{collection_id}/reorder")
    try:
        # 获取当前的clip_ids并重新排序
        current_clip_ids = collection.get('clip_ids', [])
        if len(current_clip_ids) >= 2:
            # 交换前两个元素
            new_clip_ids = current_clip_ids[1:] + current_clip_ids[:1]
            
            print(f"📤 发送排序请求: {new_clip_ids}")
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
        else:
            print("⚠️  clip_ids数量不足，无法测试排序")
    except Exception as e:
        print(f"❌ 新排序端点测试异常: {e}")
    
    # 测试修复后的PUT端点
    print("\n🔄 测试修复后的PUT端点: PUT /collections/{collection_id}")
    try:
        current_clip_ids = collection.get('clip_ids', [])
        if len(current_clip_ids) >= 2:
            # 再次交换前两个元素
            new_clip_ids = current_clip_ids[1:] + current_clip_ids[:1]
            
            update_data = {
                "metadata": {
                    "clip_ids": new_clip_ids
                }
            }
            
            print(f"📤 发送更新请求: {update_data}")
            response = requests.put(
                f"http://localhost:8000/api/v1/collections/{collection_id}",
                json=update_data,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"📥 响应状态: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 更新成功: {result.get('clip_ids', [])}")
            else:
                print(f"❌ 更新失败: {response.text}")
        else:
            print("⚠️  clip_ids数量不足，无法测试排序")
    except Exception as e:
        print(f"❌ PUT端点测试异常: {e}")
    
    # 验证更新结果
    print("\n🔍 验证更新结果...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/{collection_id}")
        if response.status_code == 200:
            updated_collection = response.json()
            print(f"✅ 更新后的clip_ids: {updated_collection.get('clip_ids', [])}")
        else:
            print(f"❌ 验证失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 验证异常: {e}")

if __name__ == "__main__":
    test_collection_reorder()
