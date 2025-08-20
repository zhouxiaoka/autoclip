#!/usr/bin/env python3
"""
直接测试前端API调用
"""

import requests
import json

def test_frontend_api_direct():
    """直接测试前端API调用"""
    
    collection_id = "0e181e1a-52c2-42c2-9481-cc306e3b27f9"
    
    print("🔍 直接测试前端API调用")
    print("=" * 50)
    
    # 获取当前合集信息
    print("\n1️⃣ 获取当前合集信息...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/{collection_id}")
        if response.status_code == 200:
            collection = response.json()
            current_clip_ids = collection.get('clip_ids', [])
            print(f"✅ 当前clip_ids: {current_clip_ids}")
        else:
            print(f"❌ 获取合集失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 获取合集异常: {e}")
        return
    
    if len(current_clip_ids) < 2:
        print("⚠️  clip_ids数量不足，无法测试排序")
        return
    
    # 测试前端API调用
    print("\n2️⃣ 测试前端API调用...")
    new_clip_ids = current_clip_ids[1:] + current_clip_ids[:1]
    
    # 模拟前端调用
    try:
        print(f"📤 发送请求: PATCH /collections/{collection_id}/reorder")
        print(f"📤 请求数据: {new_clip_ids}")
        
        response = requests.patch(
            f"http://localhost:8000/api/v1/collections/{collection_id}/reorder",
            json=new_clip_ids,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )
        
        print(f"📥 响应状态: {response.status_code}")
        print(f"📥 响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 请求成功: {result.get('clip_ids', [])}")
        else:
            print(f"❌ 请求失败: {response.text}")
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
    
    # 验证结果
    print("\n3️⃣ 验证结果...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/{collection_id}")
        if response.status_code == 200:
            collection = response.json()
            updated_clip_ids = collection.get('clip_ids', [])
            print(f"✅ 更新后的clip_ids: {updated_clip_ids}")
            
            if updated_clip_ids == new_clip_ids:
                print("✅ 验证成功！")
            else:
                print("❌ 验证失败！")
        else:
            print(f"❌ 验证失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 验证异常: {e}")

if __name__ == "__main__":
    test_frontend_api_direct()
