"""
调试导入问题
"""

import sys
import os
sys.path.insert(0, '.')

print("=== 调试导入问题 ===")
print(f"当前工作目录: {os.getcwd()}")
print(f"Python路径: {sys.path}")

try:
    print("1. 测试导入core.celery_app...")
    from core.celery_app import celery_app
    print("✅ core.celery_app 导入成功")
except Exception as e:
    print(f"❌ core.celery_app 导入失败: {e}")

try:
    print("2. 测试导入tasks.processing...")
    from tasks.processing import process_video_pipeline
    print("✅ tasks.processing 导入成功")
except Exception as e:
    print(f"❌ tasks.processing 导入失败: {e}")

try:
    print("3. 测试导入api.v1.projects...")
    from api.v1.projects import router
    print("✅ api.v1.projects 导入成功")
except Exception as e:
    print(f"❌ api.v1.projects 导入失败: {e}")

try:
    print("4. 测试导入完整的main应用...")
    from main import app
    print("✅ main.app 导入成功")
    print(f"应用类型: {type(app)}")
except Exception as e:
    print(f"❌ main.app 导入失败: {e}")
    import traceback
    traceback.print_exc()

print("=== 调试完成 ===")