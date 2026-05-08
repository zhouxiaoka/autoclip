#!/usr/bin/env python3
"""
清理重复任务脚本
清理数据库中大量重复的PENDING任务
"""

import os
import sys
import sqlite3
from pathlib import Path
from typing import Dict, Any

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / "data" / "autoclip.db"

def log(message: str, level: str = "INFO"):
    """日志输出"""
    print(f"[{level}] {message}")

def analyze_tasks():
    """分析任务情况"""
    log("🔍 分析任务情况...")
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # 总任务数
    cursor.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = cursor.fetchone()[0]
    
    # 按状态分组
    cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
    status_counts = cursor.fetchall()
    
    # 按项目分组
    cursor.execute("SELECT project_id, COUNT(*) FROM tasks GROUP BY project_id")
    project_counts = cursor.fetchall()
    
    # 按时间分组（每分钟）
    cursor.execute("""
        SELECT strftime('%Y-%m-%d %H:%M', created_at) as time, COUNT(*) as count 
        FROM tasks 
        GROUP BY strftime('%Y-%m-%d %H:%M', created_at) 
        ORDER BY count DESC 
        LIMIT 10
    """)
    time_counts = cursor.fetchall()
    
    conn.close()
    
    log(f"📊 总任务数: {total_tasks}")
    log("📊 按状态分组:")
    for status, count in status_counts:
        log(f"  {status}: {count}")
    
    log("📊 按项目分组:")
    for project_id, count in project_counts:
        log(f"  {project_id}: {count}")
    
    log("📊 按时间分组 (前10个):")
    for time, count in time_counts:
        log(f"  {time}: {count}")
    
    return {
        "total_tasks": total_tasks,
        "status_counts": dict(status_counts),
        "project_counts": dict(project_counts),
        "time_counts": time_counts
    }

def cleanup_duplicate_tasks():
    """清理重复任务"""
    log("🧹 开始清理重复任务...")
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # 1. 保留每个项目的最新任务，删除其他PENDING任务
    log("1. 清理重复的PENDING任务...")
    
    # 获取每个项目的最新任务ID
    cursor.execute("""
        SELECT project_id, MAX(id) as latest_task_id
        FROM tasks 
        WHERE status = 'PENDING'
        GROUP BY project_id
    """)
    latest_tasks = cursor.fetchall()
    
    deleted_count = 0
    for project_id, latest_task_id in latest_tasks:
        # 删除该项目的其他PENDING任务
        cursor.execute("""
            DELETE FROM tasks 
            WHERE project_id = ? AND status = 'PENDING' AND id != ?
        """, (project_id, latest_task_id))
        
        deleted_count += cursor.rowcount
        log(f"  项目 {project_id}: 删除了 {cursor.rowcount} 个重复任务")
    
    # 2. 清理时间戳相同的任务（可能是批量创建的）
    log("2. 清理时间戳相同的重复任务...")
    
    cursor.execute("""
        SELECT created_at, COUNT(*) as count
        FROM tasks 
        WHERE status = 'PENDING'
        GROUP BY created_at
        HAVING count > 1
    """)
    duplicate_times = cursor.fetchall()
    
    for created_at, count in duplicate_times:
        # 保留第一个，删除其他
        cursor.execute("""
            DELETE FROM tasks 
            WHERE created_at = ? AND status = 'PENDING' AND id NOT IN (
                SELECT id FROM tasks 
                WHERE created_at = ? AND status = 'PENDING' 
                ORDER BY id 
                LIMIT 1
            )
        """, (created_at, created_at))
        
        deleted_count += cursor.rowcount
        log(f"  时间 {created_at}: 删除了 {cursor.rowcount} 个重复任务")
    
    # 3. 清理失败的任务（保留最近的几个）
    log("3. 清理失败的任务...")
    
    cursor.execute("""
        SELECT project_id, COUNT(*) as count
        FROM tasks 
        WHERE status = 'FAILED'
        GROUP BY project_id
    """)
    failed_counts = cursor.fetchall()
    
    for project_id, count in failed_counts:
        if count > 5:  # 如果失败任务超过5个，只保留最近的5个
            cursor.execute("""
                DELETE FROM tasks 
                WHERE project_id = ? AND status = 'FAILED' AND id NOT IN (
                    SELECT id FROM tasks 
                    WHERE project_id = ? AND status = 'FAILED' 
                    ORDER BY created_at DESC 
                    LIMIT 5
                )
            """, (project_id, project_id))
            
            deleted_count += cursor.rowcount
            log(f"  项目 {project_id}: 删除了 {cursor.rowcount} 个失败任务")
    
    conn.commit()
    conn.close()
    
    log(f"✅ 清理完成，共删除了 {deleted_count} 个重复任务")
    return deleted_count

def verify_cleanup():
    """验证清理结果"""
    log("🔍 验证清理结果...")
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # 总任务数
    cursor.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = cursor.fetchone()[0]
    
    # 按状态分组
    cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
    status_counts = cursor.fetchall()
    
    # 按项目分组
    cursor.execute("SELECT project_id, COUNT(*) FROM tasks GROUP BY project_id")
    project_counts = cursor.fetchall()
    
    conn.close()
    
    log(f"📊 清理后总任务数: {total_tasks}")
    log("📊 按状态分组:")
    for status, count in status_counts:
        log(f"  {status}: {count}")
    
    log("📊 按项目分组:")
    for project_id, count in project_counts:
        log(f"  {project_id}: {count}")

def main():
    """主函数"""
    log("🚀 开始清理重复任务...")
    
    if not DATABASE_PATH.exists():
        log("数据库文件不存在", "ERROR")
        return 1
    
    # 1. 分析任务情况
    analysis = analyze_tasks()
    
    if analysis["total_tasks"] < 1000:
        log("任务数量正常，无需清理", "INFO")
        return 0
    
    # 2. 清理重复任务
    deleted_count = cleanup_duplicate_tasks()
    
    # 3. 验证清理结果
    verify_cleanup()
    
    log("🎉 任务清理完成！")
    return 0

if __name__ == "__main__":
    sys.exit(main())
