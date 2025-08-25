#!/usr/bin/env python3
"""
调试前端拖拽排序问题
"""

import requests
import json

def debug_frontend_reorder():
    """调试前端拖拽排序问题"""
    
    # 项目ID和合集ID
    project_id = "86f9aa12-2f35-4618-b265-74b3d9a4cf2d"
    collection_id = "5e5dafc8-f29a-4705-8e87-b2bb06f2a5de"
    
    print("🔍 调试前端拖拽排序问题")
    print("=" * 50)
    
    # 1. 检查后端API是否正常工作
    print("1️⃣ 检查后端API...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
        if response.status_code == 200:
            collections = response.json()['items']
            target_collection = next((c for c in collections if c['id'] == collection_id), None)
            if target_collection:
                initial_clip_ids = target_collection['clip_ids']
                print(f"✅ 后端API正常，合集: {target_collection['name']}")
                print(f"📋 当前clip_ids: {initial_clip_ids}")
            else:
                print("❌ 未找到目标合集")
                return
        else:
            print(f"❌ 后端API异常: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 后端API异常: {e}")
        return
    
    # 2. 测试不同的API调用方式
    print("\n2️⃣ 测试不同的API调用方式...")
    
    # 方式1: 使用正确的API端点
    print("\n🔄 方式1: PATCH /projects/{project_id}/collections/{collection_id}/reorder")
    new_clip_ids_1 = [initial_clip_ids[1], initial_clip_ids[0]] + initial_clip_ids[2:]
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/projects/{project_id}/collections/{collection_id}/reorder",
            json=new_clip_ids_1,
            headers={"Content-Type": "application/json"}
        )
        print(f"📥 响应状态: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 方式1成功: {result.get('clip_ids', [])}")
        else:
            print(f"❌ 方式1失败: {response.text}")
    except Exception as e:
        print(f"❌ 方式1异常: {e}")
    
    # 方式2: 使用错误的API端点（前端可能使用的）
    print("\n🔄 方式2: PATCH /collections/{collection_id}/reorder")
    new_clip_ids_2 = [initial_clip_ids[0], initial_clip_ids[1]] + initial_clip_ids[2:]
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/collections/{collection_id}/reorder",
            json=new_clip_ids_2,
            headers={"Content-Type": "application/json"}
        )
        print(f"📥 响应状态: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 方式2成功: {result.get('clip_ids', [])}")
        else:
            print(f"❌ 方式2失败: {response.text}")
    except Exception as e:
        print(f"❌ 方式2异常: {e}")
    
    # 方式3: 使用PUT方式更新metadata
    print("\n🔄 方式3: PUT /collections/{collection_id} (metadata格式)")
    new_clip_ids_3 = [initial_clip_ids[1], initial_clip_ids[0]] + initial_clip_ids[2:]
    try:
        update_data = {
            "metadata": {
                "clip_ids": new_clip_ids_3
            }
        }
        response = requests.put(
            f"http://localhost:8000/api/v1/collections/{collection_id}",
            json=update_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"📥 响应状态: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 方式3成功: {result.get('clip_ids', [])}")
        else:
            print(f"❌ 方式3失败: {response.text}")
    except Exception as e:
        print(f"❌ 方式3异常: {e}")
    
    # 3. 检查前端可能的问题
    print("\n3️⃣ 检查前端可能的问题...")
    
    # 检查网络连接
    print("\n🌐 检查网络连接...")
    try:
        response = requests.get("http://localhost:8000/api/v1/")
        print(f"✅ 网络连接正常: {response.status_code}")
    except Exception as e:
        print(f"❌ 网络连接异常: {e}")
    
    # 检查CORS
    print("\n🔒 检查CORS...")
    try:
        response = requests.options(
            f"http://localhost:8000/api/v1/projects/{project_id}/collections/{collection_id}/reorder",
            headers={"Origin": "http://localhost:3000"}
        )
        print(f"✅ CORS检查: {response.status_code}")
        print(f"📋 CORS头: {dict(response.headers)}")
    except Exception as e:
        print(f"❌ CORS检查异常: {e}")
    
    # 4. 模拟前端的完整错误流程
    print("\n4️⃣ 模拟前端的完整错误流程...")
    
    # 模拟前端可能遇到的错误
    print("\n🔄 模拟错误1: 无效的collection_id")
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/projects/{project_id}/collections/invalid-id/reorder",
            json=initial_clip_ids,
            headers={"Content-Type": "application/json"}
        )
        print(f"📥 错误1响应: {response.status_code}")
        if response.status_code == 404:
            print("✅ 错误处理正常")
        else:
            print(f"❌ 错误处理异常: {response.text}")
    except Exception as e:
        print(f"❌ 错误1异常: {e}")
    
    print("\n🔄 模拟错误2: 无效的请求体")
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/projects/{project_id}/collections/{collection_id}/reorder",
            json={"invalid": "data"},
            headers={"Content-Type": "application/json"}
        )
        print(f"📥 错误2响应: {response.status_code}")
        print(f"📋 错误2内容: {response.text}")
    except Exception as e:
        print(f"❌ 错误2异常: {e}")
    
    print("\n🔄 模拟错误3: 空的clip_ids")
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/projects/{project_id}/collections/{collection_id}/reorder",
            json=[],
            headers={"Content-Type": "application/json"}
        )
        print(f"📥 错误3响应: {response.status_code}")
        print(f"📋 错误3内容: {response.text}")
    except Exception as e:
        print(f"❌ 错误3异常: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 调试完成！")
    print("\n📋 可能的问题:")
    print("   1. 前端使用了错误的API端点")
    print("   2. 前端发送了错误的请求格式")
    print("   3. 网络连接问题")
    print("   4. CORS问题")
    print("   5. 前端错误处理逻辑问题")

if __name__ == "__main__":
    debug_frontend_reorder()

