#!/usr/bin/env python3
"""
前端后端连接测试脚本
"""
import requests
import json
import time

def test_backend_api():
    """测试后端API"""
    print("🔍 测试后端API...")
    
    try:
        # 测试健康检查
        response = requests.get("http://localhost:8000/api/v1/health")
        print(f"✅ 健康检查: {response.status_code}")
        
        # 测试项目列表
        response = requests.get("http://localhost:8000/api/v1/projects/")
        print(f"✅ 项目列表: {response.status_code}")
        data = response.json()
        print(f"   项目数量: {len(data.get('items', []))}")
        
        # 测试视频分类
        response = requests.get("http://localhost:8000/api/v1/video-categories")
        print(f"✅ 视频分类: {response.status_code}")
        
        # 测试语音识别状态
        response = requests.get("http://localhost:8000/api/v1/speech-recognition/status")
        print(f"✅ 语音识别状态: {response.status_code}")
        
        return True
    except Exception as e:
        print(f"❌ 后端API测试失败: {e}")
        return False

def test_frontend_connection():
    """测试前端连接"""
    print("\n🌐 测试前端连接...")
    
    try:
        response = requests.get("http://localhost:3000")
        print(f"✅ 前端服务: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ 前端连接失败: {e}")
        return False

def test_cors():
    """测试CORS"""
    print("\n🔗 测试CORS...")
    
    try:
        headers = {
            'Origin': 'http://localhost:3000',
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'Content-Type'
        }
        
        response = requests.options("http://localhost:8000/api/v1/projects/", headers=headers)
        print(f"✅ CORS预检: {response.status_code}")
        
        # 测试实际请求
        headers = {
            'Origin': 'http://localhost:3000',
            'Content-Type': 'application/json'
        }
        
        response = requests.get("http://localhost:8000/api/v1/projects/", headers=headers)
        print(f"✅ CORS实际请求: {response.status_code}")
        
        return True
    except Exception as e:
        print(f"❌ CORS测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 前端后端连接测试开始")
    print("=" * 50)
    
    tests = [
        ("后端API", test_backend_api),
        ("前端连接", test_frontend_connection),
        ("CORS", test_cors),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} 测试通过")
            else:
                print(f"❌ {test_name} 测试失败")
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！前后端连接正常")
        return 0
    else:
        print("⚠️ 部分测试失败，请检查服务状态")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())

