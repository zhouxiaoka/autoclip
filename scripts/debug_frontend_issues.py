#!/usr/bin/env python3
"""
调试前端可能遇到的所有问题
"""

import requests
import json
from typing import List

def debug_frontend_issues():
    """调试前端可能遇到的所有问题"""
    
    # 测试数据
    project_id = "5c48803d-0aa7-48d7-a270-2b33e4954f25"
    collection_id = "0e181e1a-52c2-42c2-9481-cc306e3b27f9"
    
    print("🔍 调试前端可能遇到的所有问题")
    print("=" * 60)
    
    # 1. 检查后端服务是否正常运行
    print("\n1️⃣ 检查后端服务状态...")
    try:
        response = requests.get("http://localhost:8000/health")
        print(f"📥 健康检查响应: {response.status_code}")
        if response.status_code == 200:
            print("✅ 后端服务正常运行")
        else:
            print("❌ 后端服务异常")
    except Exception as e:
        print(f"❌ 后端服务连接失败: {e}")
        return
    
    # 2. 检查项目是否存在
    print("\n2️⃣ 检查项目是否存在...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/projects/{project_id}")
        print(f"📥 项目查询响应: {response.status_code}")
        if response.status_code == 200:
            project = response.json()
            print(f"✅ 项目存在: {project.get('name', 'Unknown')}")
        else:
            print(f"❌ 项目不存在: {response.text}")
            return
    except Exception as e:
        print(f"❌ 项目查询异常: {e}")
        return
    
    # 3. 检查合集是否存在
    print("\n3️⃣ 检查合集是否存在...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/{collection_id}")
        print(f"📥 合集查询响应: {response.status_code}")
        if response.status_code == 200:
            collection = response.json()
            print(f"✅ 合集存在: {collection.get('name', 'Unknown')}")
            current_clip_ids = collection.get('clip_ids', [])
            print(f"📋 当前clip_ids: {current_clip_ids}")
        else:
            print(f"❌ 合集不存在: {response.text}")
            return
    except Exception as e:
        print(f"❌ 合集查询异常: {e}")
        return
    
    if len(current_clip_ids) < 2:
        print("⚠️  clip_ids数量不足，无法测试排序")
        return
    
    # 4. 测试前端可能使用的所有API端点
    print("\n4️⃣ 测试前端可能使用的所有API端点...")
    
    # 端点1: 新的排序端点
    print("\n🔄 端点1: PATCH /collections/{collection_id}/reorder")
    new_clip_ids = current_clip_ids[1:] + current_clip_ids[:1]
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/collections/{collection_id}/reorder",
            json=new_clip_ids,
            headers={"Content-Type": "application/json"}
        )
        print(f"📥 响应状态: {response.status_code}")
        print(f"📥 响应头: {dict(response.headers)}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 端点1成功: {result.get('clip_ids', [])}")
        else:
            print(f"❌ 端点1失败: {response.text}")
    except Exception as e:
        print(f"❌ 端点1异常: {e}")
    
    # 端点2: 旧的PUT端点
    print("\n🔄 端点2: PUT /collections/{collection_id}")
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
        print(f"📥 响应头: {dict(response.headers)}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 端点2成功: {result.get('clip_ids', [])}")
        else:
            print(f"❌ 端点2失败: {response.text}")
    except Exception as e:
        print(f"❌ 端点2异常: {e}")
    
    # 端点3: 检查是否有其他端点
    print("\n🔄 端点3: 检查其他可能的端点")
    possible_endpoints = [
        f"/api/v1/projects/{project_id}/collections/{collection_id}/reorder",
        f"/api/v1/collections/{collection_id}/clips/reorder",
        f"/api/v1/projects/{project_id}/collections/{collection_id}/clips/reorder"
    ]
    
    for endpoint in possible_endpoints:
        try:
            response = requests.patch(
                f"http://localhost:8000{endpoint}",
                json=new_clip_ids,
                headers={"Content-Type": "application/json"}
            )
            print(f"📥 {endpoint} - 响应状态: {response.status_code}")
            if response.status_code == 200:
                print(f"✅ {endpoint} 存在且工作正常")
            elif response.status_code == 404:
                print(f"❌ {endpoint} 不存在")
            else:
                print(f"⚠️ {endpoint} 返回: {response.status_code}")
        except Exception as e:
            print(f"❌ {endpoint} 异常: {e}")
    
    # 5. 检查CORS设置
    print("\n5️⃣ 检查CORS设置...")
    try:
        response = requests.options(
            f"http://localhost:8000/api/v1/collections/{collection_id}/reorder",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        print(f"📥 CORS预检响应: {response.status_code}")
        print(f"📥 CORS响应头: {dict(response.headers)}")
        if response.status_code == 200:
            print("✅ CORS设置正常")
        else:
            print("❌ CORS设置异常")
    except Exception as e:
        print(f"❌ CORS检查异常: {e}")
    
    # 6. 检查前端可能发送的错误请求格式
    print("\n6️⃣ 检查前端可能发送的错误请求格式...")
    
    # 格式1: 错误的Content-Type
    print("\n🔄 格式1: 错误的Content-Type")
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/collections/{collection_id}/reorder",
            data=json.dumps(new_clip_ids),
            headers={"Content-Type": "text/plain"}
        )
        print(f"📥 响应状态: {response.status_code}")
        if response.status_code == 200:
            print("✅ 格式1成功")
        else:
            print(f"❌ 格式1失败: {response.text}")
    except Exception as e:
        print(f"❌ 格式1异常: {e}")
    
    # 格式2: 错误的JSON格式
    print("\n🔄 格式2: 错误的JSON格式")
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/collections/{collection_id}/reorder",
            json={"clip_ids": new_clip_ids},
            headers={"Content-Type": "application/json"}
        )
        print(f"📥 响应状态: {response.status_code}")
        if response.status_code == 200:
            print("✅ 格式2成功")
        else:
            print(f"❌ 格式2失败: {response.text}")
    except Exception as e:
        print(f"❌ 格式2异常: {e}")
    
    # 格式3: 空数据
    print("\n🔄 格式3: 空数据")
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/collections/{collection_id}/reorder",
            json=[],
            headers={"Content-Type": "application/json"}
        )
        print(f"📥 响应状态: {response.status_code}")
        if response.status_code == 200:
            print("✅ 格式3成功")
        else:
            print(f"❌ 格式3失败: {response.text}")
    except Exception as e:
        print(f"❌ 格式3异常: {e}")
    
    # 7. 检查数据库状态
    print("\n7️⃣ 检查数据库状态...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/{collection_id}")
        if response.status_code == 200:
            collection = response.json()
            updated_clip_ids = collection.get('clip_ids', [])
            print(f"✅ 数据库状态: {updated_clip_ids}")
            
            if updated_clip_ids == new_clip_ids:
                print("✅ 数据库更新成功")
            else:
                print("❌ 数据库更新失败")
        else:
            print(f"❌ 数据库状态检查失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 数据库状态检查异常: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 前端问题调试完成！")
    print("\n💡 建议:")
    print("1. 检查前端控制台是否有JavaScript错误")
    print("2. 检查网络面板中的请求详情")
    print("3. 确认前端使用的是最新版本的代码")
    print("4. 尝试清除浏览器缓存")

if __name__ == "__main__":
    debug_frontend_issues()
