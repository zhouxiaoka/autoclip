#!/usr/bin/env python3
"""
专门诊断前端拖拽排序问题
"""

import requests
import json
import time

def debug_frontend_issue():
    """诊断前端拖拽排序问题"""
    
    # 项目ID和合集ID
    project_id = "86f9aa12-2f35-4618-b265-74b3d9a4cf2d"
    collection_id = "5e5dafc8-f29a-4705-8e87-b2bb06f2a5de"
    
    print("🔍 专门诊断前端拖拽排序问题")
    print("=" * 60)
    
    # 1. 检查后端服务状态
    print("1️⃣ 检查后端服务状态...")
    try:
        response = requests.get("http://localhost:8000/api/v1/")
        print(f"✅ 后端服务正常运行")
    except Exception as e:
        print(f"❌ 后端服务异常: {e}")
        return
    
    # 2. 检查当前数据状态
    print("\n2️⃣ 检查当前数据状态...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
        if response.status_code == 200:
            collections = response.json()['items']
            target_collection = next((c for c in collections if c['id'] == collection_id), None)
            if target_collection:
                current_clip_ids = target_collection['clip_ids']
                print(f"✅ 目标合集: {target_collection['name']}")
                print(f"📋 当前clip_ids: {current_clip_ids}")
                print(f"📊 片段数量: {len(current_clip_ids)}")
            else:
                print("❌ 未找到目标合集")
                return
        else:
            print(f"❌ 获取collections失败: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ 获取数据异常: {e}")
        return
    
    # 3. 监控拖拽排序调用
    print("\n3️⃣ 监控拖拽排序调用...")
    print("🔔 请在前端进行拖拽排序操作，然后按回车键继续...")
    input()
    
    # 检查最近的日志
    print("📋 检查后端日志中的拖拽排序记录...")
    try:
        with open('/Users/zhoukk/autoclip/backend.log', 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-50:]  # 获取最近50行
            
            reorder_logs = []
            for line in recent_lines:
                if 'reorder' in line.lower() or '排序' in line:
                    reorder_logs.append(line.strip())
            
            if reorder_logs:
                print("📋 找到相关日志:")
                for log in reorder_logs[-10:]:  # 显示最近10条
                    print(f"   {log}")
            else:
                print("❌ 未找到拖拽排序相关的日志")
    except Exception as e:
        print(f"❌ 读取日志失败: {e}")
    
    # 4. 再次检查数据状态
    print("\n4️⃣ 再次检查数据状态...")
    try:
        response = requests.get(f"http://localhost:8000/api/v1/collections/?project_id={project_id}")
        if response.status_code == 200:
            collections = response.json()['items']
            target_collection = next((c for c in collections if c['id'] == collection_id), None)
            if target_collection:
                updated_clip_ids = target_collection['clip_ids']
                print(f"📋 更新后的clip_ids: {updated_clip_ids}")
                
                if updated_clip_ids != current_clip_ids:
                    print("✅ 数据已更新！")
                else:
                    print("❌ 数据未更新")
            else:
                print("❌ 未找到目标合集")
        else:
            print(f"❌ 获取collections失败: {response.status_code}")
    except Exception as e:
        print(f"❌ 获取数据异常: {e}")
    
    # 5. 提供调试建议
    print("\n5️⃣ 调试建议...")
    print("📋 如果拖拽排序仍然失败，请检查以下几点:")
    print("   1. 打开浏览器开发者工具的Network标签")
    print("   2. 进行拖拽排序操作")
    print("   3. 查看是否有API调用发出")
    print("   4. 检查API调用的状态码和响应")
    print("   5. 查看Console标签是否有JavaScript错误")
    
    print("\n6️⃣ 常见问题排查:")
    print("   ❓ 问题1: 前端没有发出API请求")
    print("   💡 解决: 检查前端代码中的事件处理是否正确绑定")
    print()
    print("   ❓ 问题2: API请求被拦截或失败")
    print("   💡 解决: 检查CORS设置，确认后端服务可访问")
    print()
    print("   ❓ 问题3: 前端状态更新失败")
    print("   💡 解决: 检查store的状态管理逻辑")
    print()
    print("   ❓ 问题4: 错误处理逻辑问题")
    print("   💡 解决: 检查try-catch块和错误消息显示")
    
    print("\n" + "=" * 60)
    print("🎯 诊断完成！")

if __name__ == "__main__":
    debug_frontend_issue()

