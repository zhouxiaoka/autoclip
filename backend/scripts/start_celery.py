#!/usr/bin/env python3
"""
Celery启动脚本
启动Celery Worker和Beat调度器
"""

import os
import sys
import subprocess
import signal
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def start_celery_worker():
    """启动Celery Worker"""
    print("🚀 启动Celery Worker...")
    
    cmd = [
        "celery", "-A", "backend.core.celery_app", "worker",
        "--loglevel=info",
        "--concurrency=2",
        "--queues=processing,video,notification,maintenance",
        "--hostname=worker1@%h"
    ]
    
    try:
        process = subprocess.Popen(cmd, cwd=str(project_root))
        print(f"✅ Celery Worker已启动 (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"❌ 启动Celery Worker失败: {e}")
        return None

def start_celery_beat():
    """启动Celery Beat调度器"""
    print("⏰ 启动Celery Beat调度器...")
    
    cmd = [
        "celery", "-A", "backend.core.celery_app", "beat",
        "--loglevel=info",
        "--schedule=/tmp/celerybeat-schedule",
        "--pidfile=/tmp/celerybeat.pid"
    ]
    
    try:
        process = subprocess.Popen(cmd, cwd=str(project_root))
        print(f"✅ Celery Beat已启动 (PID: {process.pid})")
        return process
    except Exception as e:
        print(f"❌ 启动Celery Beat失败: {e}")
        return None

def start_flower():
    """启动Flower监控界面"""
    print("🌸 启动Flower监控界面...")
    
    cmd = [
        "celery", "-A", "backend.core.celery_app", "flower",
        "--port=5555",
        "--loglevel=info"
    ]
    
    try:
        process = subprocess.Popen(cmd, cwd=str(project_root))
        print(f"✅ Flower已启动 (PID: {process.pid})")
        print("🌐 Flower监控界面: http://localhost:5555")
        return process
    except Exception as e:
        print(f"❌ 启动Flower失败: {e}")
        return None

def signal_handler(signum, frame):
    """信号处理函数"""
    print("\n🛑 收到停止信号，正在关闭服务...")
    sys.exit(0)

def main():
    """主函数"""
    print("🎯 AutoClip Celery 任务队列启动器")
    print("=" * 50)
    
    # 设置信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 检查Redis连接
    try:
        import redis
        r = redis.Redis.from_url('redis://localhost:6379/0')
        r.ping()
        print("✅ Redis连接正常")
    except Exception as e:
        print(f"❌ Redis连接失败: {e}")
        print("请确保Redis服务正在运行: redis-server")
        return
    
    # 启动服务
    processes = []
    
    # 启动Worker
    worker_process = start_celery_worker()
    if worker_process:
        processes.append(worker_process)
    
    # 启动Beat
    beat_process = start_celery_beat()
    if beat_process:
        processes.append(beat_process)
    
    # 启动Flower
    flower_process = start_flower()
    if flower_process:
        processes.append(flower_process)
    
    if not processes:
        print("❌ 没有成功启动任何服务")
        return
    
    print("\n🎉 所有服务已启动!")
    print("📊 服务状态:")
    print("   - Celery Worker: 处理任务")
    print("   - Celery Beat: 定时任务调度")
    print("   - Flower: 任务监控界面 (http://localhost:5555)")
    print("\n按 Ctrl+C 停止所有服务")
    
    try:
        # 等待进程
        while True:
            time.sleep(1)
            # 检查进程是否还在运行
            for process in processes:
                if process.poll() is not None:
                    print(f"⚠️  进程 {process.pid} 已退出")
    except KeyboardInterrupt:
        print("\n🛑 正在停止服务...")
    finally:
        # 停止所有进程
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                print(f"🛑 进程 {process.pid} 已停止")

if __name__ == "__main__":
    main() 