#!/usr/bin/env python3
"""
测试数据库集成的完整流程
"""

import requests
import json
import time

def test_database_integration():
    """测试数据库集成的完整流程"""
    base_url = "http://localhost:8000/api/v1"
    
    print("🧪 开始测试数据库集成...")
    
    # 1. 测试获取合集
    print("\n1. 测试获取合集...")
    project_id = "1fdb0bf1-7f3c-44f7-a69d-90c5a1d26fbe"
    
    try:
        response = requests.get(f"{base_url}/collections/?project_id={project_id}")
        if response.status_code == 200:
            collections = response.json()
            print(f"✅ 获取合集成功: {len(collections['items'])} 个合集")
            
            if collections['items']:
                collection = collections['items'][0]
                print(f"   合集名称: {collection['name']}")
                print(f"   合集ID: {collection['id']}")
                print(f"   包含切片: {collection['clip_ids']}")
                collection_id = collection['id']
            else:
                print("   没有找到合集，需要先同步数据")
                return
        else:
            print(f"❌ 获取合集失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 获取合集异常: {e}")
        return
    
    # 2. 测试删除合集
    print(f"\n2. 测试删除合集 {collection_id}...")
    try:
        response = requests.delete(f"{base_url}/collections/{collection_id}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 删除合集成功: {result['message']}")
        else:
            print(f"❌ 删除合集失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 删除合集异常: {e}")
        return
    
    # 3. 验证删除结果
    print("\n3. 验证删除结果...")
    try:
        response = requests.get(f"{base_url}/collections/?project_id={project_id}")
        if response.status_code == 200:
            collections = response.json()
            if len(collections['items']) == 0:
                print("✅ 删除验证成功: 合集已从数据库中移除")
            else:
                print(f"❌ 删除验证失败: 仍有 {len(collections['items'])} 个合集")
        else:
            print(f"❌ 验证删除结果失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 验证删除结果异常: {e}")
    
    # 4. 测试创建合集
    print("\n4. 测试创建合集...")
    new_collection_data = {
        "project_id": project_id,
        "name": "测试合集",
        "description": "这是一个测试合集",
        "metadata": {
            "clip_ids": ["1", "2"],
            "collection_type": "manual"
        }
    }
    
    try:
        response = requests.post(f"{base_url}/collections/", json=new_collection_data)
        if response.status_code == 200:
            new_collection = response.json()
            print(f"✅ 创建合集成功: {new_collection['name']} (ID: {new_collection['id']})")
            new_collection_id = new_collection['id']
        else:
            print(f"❌ 创建合集失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return
    except Exception as e:
        print(f"❌ 创建合集异常: {e}")
        return
    
    # 5. 验证创建结果
    print("\n5. 验证创建结果...")
    try:
        response = requests.get(f"{base_url}/collections/?project_id={project_id}")
        if response.status_code == 200:
            collections = response.json()
            if len(collections['items']) == 1:
                print("✅ 创建验证成功: 新合集已添加到数据库")
            else:
                print(f"❌ 创建验证失败: 期望1个合集，实际{len(collections['items'])}个")
        else:
            print(f"❌ 验证创建结果失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 验证创建结果异常: {e}")
    
    # 6. 清理测试数据
    print(f"\n6. 清理测试数据...")
    try:
        response = requests.delete(f"{base_url}/collections/{new_collection_id}")
        if response.status_code == 200:
            print("✅ 清理测试数据成功")
        else:
            print(f"❌ 清理测试数据失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 清理测试数据异常: {e}")
    
    print("\n🎉 数据库集成测试完成!")

if __name__ == "__main__":
    test_database_integration()

