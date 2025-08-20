#!/usr/bin/env python3
"""
调试前端实际发送的请求
"""

import requests
import json
from typing import List

def debug_frontend_request():
    """调试前端实际发送的请求"""
    
    # 测试数据
    project_id = "5c48803d-0aa7-48d7-a270-2b33e4954f25"
    collection_id = "0e181e1a-52c2-42c2-9481-cc306e3b27f9"
    
    print("🔍 调试前端实际发送的请求")
    print("=" * 50)
    
    # 1. 获取当前合集信息
    print("\n1️⃣ 获取当前合集信息...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/{collection_id}")
        if response.status_code == 200:
            collection = response.json()
            print(f"✅ 当前合集: {collection['name']}")
            current_clip_ids = collection.get('clip_ids', [])
            print(f"📋 当前clip_ids: {current_clip_ids}")
        else:
            print(f"❌ 获取合集失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 获取合集异常: {e}")
        return
    
    if len(current_clip_ids) < 2:
        print("⚠️  clip_ids数量不足，无法测试排序")
        return
    
    # 2. 测试前端可能使用的不同API调用方式
    print("\n2️⃣ 测试前端可能使用的不同API调用方式...")
    
    # 方式1: 新的排序端点
    print("\n🔄 方式1: PATCH /collections/{collection_id}/reorder")
    new_clip_ids = current_clip_ids[1:] + current_clip_ids[:1]
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/collections/{collection_id}/reorder",
            json=new_clip_ids,
            headers={"Content-Type": "application/json"}
        )
        print(f"📥 响应状态: {response.status_code}")
        if response.status_code == 200:
            print("✅ 方式1成功")
        else:
            print(f"❌ 方式1失败: {response.text}")
    except Exception as e:
        print(f"❌ 方式1异常: {e}")
    
    # 方式2: 旧的PUT方式
    print("\n🔄 方式2: PUT /collections/{collection_id}")
    try:
        update_data = {
            "metadata": {
                "clip_ids": new_clip_ids
            }
        }
        response = requests.put(
            f"http://localhost:8000/api/v1/collections/{collection_id}",
            json=update_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"📥 响应状态: {response.status_code}")
        if response.status_code == 200:
            print("✅ 方式2成功")
        else:
            print(f"❌ 方式2失败: {response.text}")
    except Exception as e:
        print(f"❌ 方式2异常: {e}")
    
    # 方式3: 前端可能使用的其他格式
    print("\n🔄 方式3: PUT /collections/{collection_id} (直接clip_ids)")
    try:
        update_data = {
            "clip_ids": new_clip_ids
        }
        response = requests.put(
            f"http://localhost:8000/api/v1/collections/{collection_id}",
            json=update_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"📥 响应状态: {response.status_code}")
        if response.status_code == 200:
            print("✅ 方式3成功")
        else:
            print(f"❌ 方式3失败: {response.text}")
    except Exception as e:
        print(f"❌ 方式3异常: {e}")
    
    # 方式4: 检查是否有其他端点
    print("\n🔄 方式4: 检查是否有其他端点")
    try:
        # 检查是否有 /projects/{project_id}/collections/{collection_id}/reorder 端点
        response = requests.patch(
            f"http://localhost:8000/api/v1/projects/{project_id}/collections/{collection_id}/reorder",
            json=new_clip_ids,
            headers={"Content-Type": "application/json"}
        )
        print(f"📥 响应状态: {response.status_code}")
        if response.status_code == 200:
            print("✅ 方式4成功")
        else:
            print(f"❌ 方式4失败: {response.text}")
    except Exception as e:
        print(f"❌ 方式4异常: {e}")
    
    # 3. 检查后端日志中的请求
    print("\n3️⃣ 检查后端日志...")
    print("请查看后端日志，看看前端实际发送了什么请求")
    print("如果日志中没有看到任何请求，说明前端可能没有调用API")

if __name__ == "__main__":
    debug_frontend_request()
