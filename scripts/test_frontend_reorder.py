#!/usr/bin/env python3
"""
测试前端拖拽排序功能
"""

import requests
import json

def test_frontend_reorder():
    """测试前端拖拽排序功能"""
    
    # 项目ID和合集ID
    project_id = "86f9aa12-2f35-4618-b265-74b3d9a4cf2d"
    collection_id = "5e5dafc8-f29a-4705-8e87-b2bb06f2a5de"
    
    print("🎯 测试前端拖拽排序功能")
    print("=" * 50)
    
    # 1. 获取初始状态
    print("1️⃣ 获取初始状态...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
        if response.status_code == 200:
            collections = response.json()['items']
            target_collection = next((c for c in collections if c['id'] == collection_id), None)
            if target_collection:
                initial_clip_ids = target_collection['clip_ids']
                print(f"✅ 合集: {target_collection['name']}")
                print(f"📋 初始clip_ids: {initial_clip_ids}")
            else:
                print("❌ 未找到目标合集")
                return
        else:
            print(f"❌ 获取合集失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 获取合集异常: {e}")
        return
    
    # 2. 模拟拖拽排序（交换前两个元素）
    print("\n2️⃣ 模拟拖拽排序（交换前两个元素）...")
    if len(initial_clip_ids) >= 2:
        new_clip_ids = [initial_clip_ids[1], initial_clip_ids[0]] + initial_clip_ids[2:]
        print(f"🔄 新顺序: {new_clip_ids}")
        
        try:
            # 模拟前端API调用
            response = requests.patch(
                f"http://localhost:8000/api/v1/projects/{project_id}/collections/{collection_id}/reorder",
                json=new_clip_ids,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"📥 响应状态: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 排序成功: {result.get('clip_ids', [])}")
                print(f"📝 消息: {result.get('message', '')}")
            else:
                print(f"❌ 排序失败: {response.text}")
                return
        except Exception as e:
            print(f"❌ 排序异常: {e}")
            return
    else:
        print("❌ 片段数量不足，无法测试排序")
        return
    
    # 3. 验证排序结果
    print("\n3️⃣ 验证排序结果...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
        if response.status_code == 200:
            collections = response.json()['items']
            target_collection = next((c for c in collections if c['id'] == collection_id), None)
            if target_collection:
                updated_clip_ids = target_collection['clip_ids']
                print(f"📋 更新后的clip_ids: {updated_clip_ids}")
                
                if updated_clip_ids == new_clip_ids:
                    print("✅ 排序验证成功！")
                else:
                    print("❌ 排序验证失败！")
            else:
                print("❌ 未找到目标合集")
        else:
            print(f"❌ 验证失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 验证异常: {e}")
    
    # 4. 恢复原始顺序
    print("\n4️⃣ 恢复原始顺序...")
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/projects/{project_id}/collections/{collection_id}/reorder",
            json=initial_clip_ids,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"📥 响应状态: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 恢复成功: {result.get('clip_ids', [])}")
        else:
            print(f"❌ 恢复失败: {response.text}")
    except Exception as e:
        print(f"❌ 恢复异常: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 前端拖拽排序功能测试完成！")

if __name__ == "__main__":
    test_frontend_reorder()
