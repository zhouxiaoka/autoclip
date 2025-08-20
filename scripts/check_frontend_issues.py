#!/usr/bin/env python3
"""
检查前端可能遇到的所有问题
"""

import requests
import json

def check_frontend_issues():
    """检查前端可能遇到的所有问题"""
    
    print("🔍 检查前端可能遇到的所有问题")
    print("=" * 60)
    
    # 1. 检查后端服务状态
    print("\n1️⃣ 检查后端服务状态...")
    try:
        response = requests.get("http://localhost:8000/health")
        print(f"📥 健康检查: {response.status_code}")
        if response.status_code == 200:
            print("✅ 后端服务正常")
        else:
            print("❌ 后端服务异常")
    except Exception as e:
        print(f"❌ 后端服务连接失败: {e}")
        return
    
    # 2. 检查前端服务状态
    print("\n2️⃣ 检查前端服务状态...")
    try:
        response = requests.get("http://localhost:3000")
        print(f"📥 前端服务: {response.status_code}")
        if response.status_code == 200:
            print("✅ 前端服务正常")
        else:
            print("❌ 前端服务异常")
    except Exception as e:
        print(f"❌ 前端服务连接失败: {e}")
        print("💡 前端服务可能没有启动")
    
    # 3. 检查API端点
    print("\n3️⃣ 检查API端点...")
    endpoints = [
        "/api/v1/collections/0e181e1a-52c2-42c2-9481-cc306e3b27f9",
        "/api/v1/collections/0e181e1a-52c2-42c2-9481-cc306e3b27f9/reorder",
        "/api/v1/projects/5c48803d-0aa7-48d7-a270-2b33e4954f25"
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"http://localhost:8000{endpoint}")
            print(f"📥 {endpoint}: {response.status_code}")
            if response.status_code in [200, 404]:
                print(f"✅ {endpoint} 可访问")
            else:
                print(f"❌ {endpoint} 异常")
        except Exception as e:
            print(f"❌ {endpoint} 连接失败: {e}")
    
    # 4. 检查CORS设置
    print("\n4️⃣ 检查CORS设置...")
    try:
        response = requests.options(
            "http://localhost:8000/api/v1/collections/0e181e1a-52c2-42c2-9481-cc306e3b27f9/reorder",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "Content-Type"
            }
        )
        print(f"📥 CORS预检: {response.status_code}")
        cors_headers = {k: v for k, v in response.headers.items() if k.lower().startswith('access-control')}
        print(f"📥 CORS头: {cors_headers}")
        if response.status_code == 200:
            print("✅ CORS设置正常")
        else:
            print("❌ CORS设置异常")
    except Exception as e:
        print(f"❌ CORS检查失败: {e}")
    
    # 5. 检查网络连接
    print("\n5️⃣ 检查网络连接...")
    try:
        response = requests.get("http://localhost:8000/api/v1/projects/", timeout=5)
        print(f"📥 网络连接: {response.status_code}")
        if response.status_code == 200:
            print("✅ 网络连接正常")
        else:
            print("❌ 网络连接异常")
    except requests.exceptions.Timeout:
        print("❌ 网络连接超时")
    except Exception as e:
        print(f"❌ 网络连接失败: {e}")
    
    # 6. 检查数据库连接
    print("\n6️⃣ 检查数据库连接...")
    try:
        response = requests.get("http://localhost:8000/api/v1/collections/0e181e1a-52c2-42c2-9481-cc306e3b27f9")
        print(f"📥 数据库查询: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 数据库连接正常，合集: {data.get('name', 'Unknown')}")
        else:
            print(f"❌ 数据库查询失败: {response.text}")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 前端问题检查完成！")
    print("\n💡 如果后端API正常但前端仍然失败，可能的原因:")
    print("1. 前端JavaScript错误 - 请检查浏览器控制台")
    print("2. 前端缓存问题 - 请清除浏览器缓存或重启前端服务")
    print("3. 前端使用了旧版本的代码 - 请重新构建前端")
    print("4. 前端网络请求被拦截 - 请检查浏览器网络面板")
    print("5. 前端组件没有正确绑定事件 - 请检查拖拽组件")

if __name__ == "__main__":
    check_frontend_issues()
