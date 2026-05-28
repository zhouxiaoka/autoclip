#!/usr/bin/env python3
"""
同步桌面客户端数据脚本
将Web版本的数据同步到桌面客户端的数据目录
"""

import os
import sys
import shutil
import sqlite3
import json
from pathlib import Path
from typing import Dict, Any

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
WEB_DATA_DIR = PROJECT_ROOT / "data"
DESKTOP_DATA_DIR = Path.home() / "Library" / "Application Support" / "AutoClip"

def log(message: str, level: str = "INFO"):
    """日志输出"""
    print(f"[{level}] {message}")

def sync_database():
    """同步数据库文件"""
    log("🔄 同步数据库文件...")
    
    web_db = WEB_DATA_DIR / "autoclip.db"
    desktop_db = DESKTOP_DATA_DIR / "autoclip.db"
    
    if not web_db.exists():
        log("Web版本数据库文件不存在", "WARNING")
        return False
    
    try:
        # 确保桌面数据目录存在
        DESKTOP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # 复制数据库文件
        shutil.copy2(web_db, desktop_db)
        log(f"✅ 数据库文件已同步: {desktop_db}")
        return True
        
    except Exception as e:
        log(f"❌ 数据库同步失败: {e}", "ERROR")
        return False

def sync_settings():
    """同步配置文件"""
    log("🔄 同步配置文件...")
    
    web_settings = WEB_DATA_DIR / "settings.json"
    desktop_settings = DESKTOP_DATA_DIR / "settings.json"
    
    if not web_settings.exists():
        log("Web版本配置文件不存在", "WARNING")
        return False
    
    try:
        # 确保桌面数据目录存在
        DESKTOP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # 复制配置文件
        shutil.copy2(web_settings, desktop_settings)
        log(f"✅ 配置文件已同步: {desktop_settings}")
        return True
        
    except Exception as e:
        log(f"❌ 配置文件同步失败: {e}", "ERROR")
        return False

def sync_projects():
    """同步项目文件"""
    log("🔄 同步项目文件...")
    
    web_projects_dir = WEB_DATA_DIR / "projects"
    desktop_projects_dir = DESKTOP_DATA_DIR / "projects"
    
    if not web_projects_dir.exists():
        log("Web版本项目目录不存在", "WARNING")
        return False
    
    try:
        # 确保桌面项目目录存在
        desktop_projects_dir.mkdir(parents=True, exist_ok=True)
        
        # 同步项目文件
        for item in web_projects_dir.iterdir():
            dest = desktop_projects_dir / item.name
            if item.is_file():
                shutil.copy2(item, dest)
                log(f"  📄 同步文件: {item.name}")
            elif item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
                log(f"  📁 同步目录: {item.name}")
        
        log("✅ 项目文件已同步")
        return True
        
    except Exception as e:
        log(f"❌ 项目文件同步失败: {e}", "ERROR")
        return False

def verify_sync():
    """验证同步结果"""
    log("🔍 验证同步结果...")
    
    # 检查数据库
    desktop_db = DESKTOP_DATA_DIR / "autoclip.db"
    if desktop_db.exists():
        try:
            conn = sqlite3.connect(desktop_db)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM projects")
            project_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM tasks")
            task_count = cursor.fetchone()[0]
            conn.close()
            log(f"  📊 数据库: {project_count} 个项目, {task_count} 个任务")
        except Exception as e:
            log(f"  ❌ 数据库验证失败: {e}", "ERROR")
    else:
        log("  ❌ 数据库文件不存在", "ERROR")
    
    # 检查配置文件
    desktop_settings = DESKTOP_DATA_DIR / "settings.json"
    if desktop_settings.exists():
        try:
            with open(desktop_settings, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            api_keys = settings.get("api", {}).get("api_keys", {})
            dashscope_key = api_keys.get("dashscope", "")
            if dashscope_key:
                log(f"  🔑 API密钥: {dashscope_key[:10]}...")
            else:
                log("  ⚠️  API密钥未配置", "WARNING")
        except Exception as e:
            log(f"  ❌ 配置文件验证失败: {e}", "ERROR")
    else:
        log("  ❌ 配置文件不存在", "ERROR")
    
    # 检查项目目录
    desktop_projects_dir = DESKTOP_DATA_DIR / "projects"
    if desktop_projects_dir.exists():
        project_files = list(desktop_projects_dir.iterdir())
        log(f"  📁 项目目录: {len(project_files)} 个项目")
    else:
        log("  ❌ 项目目录不存在", "ERROR")

def main():
    """主函数"""
    log("🚀 开始同步桌面客户端数据...")
    
    # 检查Web版本数据目录
    if not WEB_DATA_DIR.exists():
        log("Web版本数据目录不存在", "ERROR")
        return 1
    
    # 同步数据
    success_count = 0
    
    if sync_database():
        success_count += 1
    
    if sync_settings():
        success_count += 1
    
    if sync_projects():
        success_count += 1
    
    # 验证同步结果
    verify_sync()
    
    if success_count == 3:
        log("🎉 数据同步完成！")
        log("📝 现在桌面客户端应该包含最新的数据和配置了")
        return 0
    else:
        log(f"⚠️  部分同步失败，成功: {success_count}/3", "WARNING")
        return 1

if __name__ == "__main__":
    sys.exit(main())
