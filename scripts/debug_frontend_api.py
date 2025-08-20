#!/usr/bin/env python3
"""
前端API调试脚本
模拟前端的API调用行为
"""
import requests
import json

def simulate_frontend_api_call():
    """模拟前端的API调用"""
    print("🔍 模拟前端API调用...")
    
    # 模拟前端的axios配置
    headers = {
        'Content-Type': 'application/json',
        'Origin': 'http://localhost:3000'
    }
    
    try:
        # 模拟前端的项目列表API调用
        print("📡 调用项目列表API...")
        response = requests.get(
            "http://localhost:8000/api/v1/projects/",
            headers=headers,
            timeout=30
        )
        
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            # 模拟前端的处理逻辑
            items = data.get('items', [])
            print(f"项目数量: {len(items)}")
            
            if len(items) == 0:
                print("✅ 空项目列表，这是正常的")
            else:
                print("📋 项目列表:")
                for i, project in enumerate(items):
                    print(f"  {i+1}. {project.get('name', 'Unknown')} - {project.get('status', 'Unknown')}")
        else:
            print(f"❌ API调用失败: {response.text}")
            
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
    except requests.exceptions.ConnectionError:
        print("❌ 连接错误")
    except Exception as e:
        print(f"❌ 其他错误: {e}")

def test_api_response_structure():
    """测试API响应结构"""
    print("\n🔍 测试API响应结构...")
    
    try:
        response = requests.get("http://localhost:8000/api/v1/projects/")
        data = response.json()
        
        # 检查响应结构
        print("响应结构检查:")
        print(f"  - 有 'items' 字段: {'items' in data}")
        print(f"  - 有 'pagination' 字段: {'pagination' in data}")
        
        if 'items' in data:
            print(f"  - items 类型: {type(data['items'])}")
            print(f"  - items 长度: {len(data['items'])}")
        
        if 'pagination' in data:
            print(f"  - pagination 内容: {data['pagination']}")
            
    except Exception as e:
        print(f"❌ 结构测试失败: {e}")

def main():
    """主函数"""
    print("🚀 前端API调试开始")
    print("=" * 50)
    
    simulate_frontend_api_call()
    test_api_response_structure()
    
    print("\n" + "=" * 50)
    print("✅ 调试完成")

if __name__ == "__main__":
    main()

