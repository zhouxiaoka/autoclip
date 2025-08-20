#!/usr/bin/env python3
"""
前端状态调试脚本
检查前端页面的实际状态
"""
import requests
import time

def check_frontend_page():
    """检查前端页面状态"""
    print("🔍 检查前端页面状态...")
    
    try:
        # 获取前端页面
        response = requests.get("http://localhost:3000")
        print(f"前端页面状态码: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            print("✅ 前端页面正常加载")
            
            # 检查是否包含React应用的关键元素
            if "react" in content.lower() or "app" in content.lower():
                print("✅ 检测到React应用")
            else:
                print("⚠️ 未检测到React应用特征")
                
            # 检查页面大小
            print(f"页面大小: {len(content)} 字符")
            
        else:
            print(f"❌ 前端页面加载失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 检查前端页面失败: {e}")

def check_backend_health():
    """检查后端健康状态"""
    print("\n🔍 检查后端健康状态...")
    
    try:
        response = requests.get("http://localhost:8000/api/v1/health")
        print(f"后端健康检查: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"后端状态: {data}")
        else:
            print(f"❌ 后端健康检查失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 检查后端健康状态失败: {e}")

def check_projects_api():
    """检查项目API"""
    print("\n🔍 检查项目API...")
    
    try:
        response = requests.get("http://localhost:8000/api/v1/projects/")
        print(f"项目API状态: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            print(f"项目数量: {len(items)}")
            
            if len(items) > 0:
                print("📋 项目列表:")
                for i, project in enumerate(items):
                    print(f"  {i+1}. {project.get('name', 'Unknown')} - {project.get('status', 'Unknown')}")
            else:
                print("📭 没有项目")
        else:
            print(f"❌ 项目API失败: {response.status_code}")
            
    except Exception as e:
        print(f"❌ 检查项目API失败: {e}")

def main():
    """主函数"""
    print("🚀 前端状态调试开始")
    print("=" * 50)
    
    check_frontend_page()
    check_backend_health()
    check_projects_api()
    
    print("\n" + "=" * 50)
    print("✅ 调试完成")
    print("\n💡 建议:")
    print("1. 打开浏览器开发者工具查看控制台错误")
    print("2. 检查网络面板中的API请求")
    print("3. 查看React组件状态")

if __name__ == "__main__":
    main()

