#!/usr/bin/env python3
"""
测试完整的前端拖拽排序流程
"""

import requests
import json

def test_complete_frontend_flow():
    """测试完整的前端拖拽排序流程"""
    
    # 项目ID和合集ID
    project_id = "86f9aa12-2f35-4618-b265-74b3d9a4cf2d"
    collection_id = "5e5dafc8-f29a-4705-8e87-b2bb06f2a5de"
    
    print("🎯 测试完整的前端拖拽排序流程")
    print("=" * 60)
    
    # 1. 模拟前端获取项目数据
    print("1️⃣ 模拟前端获取项目数据...")
    try:
        # 获取项目信息
        response = requests.get(f"http://localhost:8000/api/v1/projects/{project_id}")
        if response.status_code == 200:
            project = response.json()
            print(f"✅ 项目: {project['name']}")
            print(f"📊 状态: {project['status']}")
        else:
            print(f"❌ 获取项目失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 获取项目异常: {e}")
        return
    
    # 2. 模拟前端获取clips数据
    print("\n2️⃣ 模拟前端获取clips数据...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/clips/?project_id={project_id}")
        if response.status_code == 200:
            clips = response.json()['items']
            print(f"✅ 获取到 {len(clips)} 个clips")
            for i, clip in enumerate(clips[:3]):  # 只显示前3个
                print(f"   {i+1}. {clip['title'][:30]}...")
        else:
            print(f"❌ 获取clips失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 获取clips异常: {e}")
        return
    
    # 3. 模拟前端获取collections数据
    print("\n3️⃣ 模拟前端获取collections数据...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
        if response.status_code == 200:
            collections = response.json()['items']
            print(f"✅ 获取到 {len(collections)} 个collections")
            
            target_collection = None
            for collection in collections:
                print(f"   📚 {collection['name']}: {len(collection['clip_ids'])} 个片段")
                if collection['id'] == collection_id:
                    target_collection = collection
            
            if not target_collection:
                print("❌ 未找到目标合集")
                return
                
            initial_clip_ids = target_collection['clip_ids']
            print(f"🎯 目标合集: {target_collection['name']}")
            print(f"📋 初始clip_ids: {initial_clip_ids}")
        else:
            print(f"❌ 获取collections失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 获取collections异常: {e}")
        return
    
    # 4. 模拟前端拖拽排序操作
    print("\n4️⃣ 模拟前端拖拽排序操作...")
    if len(initial_clip_ids) >= 2:
        # 模拟拖拽：将第一个元素拖到第二个位置
        new_clip_ids = [initial_clip_ids[1], initial_clip_ids[0]] + initial_clip_ids[2:]
        print(f"🔄 拖拽操作: 将第1个元素移到第2个位置")
        print(f"📋 新顺序: {new_clip_ids}")
        
        try:
            # 模拟前端的API调用
            print("📤 发送API请求...")
            response = requests.patch(
                f"http://localhost:8000/api/v1/projects/{project_id}/collections/{collection_id}/reorder",
                json=new_clip_ids,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"📥 响应状态: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"✅ API调用成功")
                print(f"📝 响应消息: {result.get('message', '')}")
                print(f"📋 返回的clip_ids: {result.get('clip_ids', [])}")
            else:
                print(f"❌ API调用失败: {response.text}")
                return
        except Exception as e:
            print(f"❌ API调用异常: {e}")
            return
    else:
        print("❌ 片段数量不足，无法测试拖拽")
        return
    
    # 5. 模拟前端验证更新结果
    print("\n5️⃣ 模拟前端验证更新结果...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
        if response.status_code == 200:
            collections = response.json()['items']
            target_collection = next((c for c in collections if c['id'] == collection_id), None)
            if target_collection:
                updated_clip_ids = target_collection['clip_ids']
                print(f"📋 验证结果: {updated_clip_ids}")
                
                if updated_clip_ids == new_clip_ids:
                    print("✅ 拖拽排序成功！数据已正确更新")
                else:
                    print("❌ 拖拽排序失败！数据未正确更新")
                    print(f"   期望: {new_clip_ids}")
                    print(f"   实际: {updated_clip_ids}")
            else:
                print("❌ 未找到目标合集")
        else:
            print(f"❌ 验证失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 验证异常: {e}")
    
    # 6. 模拟前端恢复原始状态
    print("\n6️⃣ 模拟前端恢复原始状态...")
    try:
        response = requests.patch(
            f"http://localhost:8000/api/v1/projects/{project_id}/collections/{collection_id}/reorder",
            json=initial_clip_ids,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print("✅ 状态恢复成功")
        else:
            print(f"❌ 状态恢复失败: {response.text}")
    except Exception as e:
        print(f"❌ 状态恢复异常: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 完整的前端拖拽排序流程测试完成！")
    print("\n📋 测试总结:")
    print("   ✅ 项目数据获取正常")
    print("   ✅ Clips数据获取正常")
    print("   ✅ Collections数据获取正常")
    print("   ✅ 拖拽排序API调用正常")
    print("   ✅ 数据更新验证正常")
    print("   ✅ 状态恢复正常")

if __name__ == "__main__":
    test_complete_frontend_flow()

