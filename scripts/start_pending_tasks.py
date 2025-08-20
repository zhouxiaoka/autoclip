#!/usr/bin/env python3
"""
启动等待中的任务
查看并启动所有等待中的任务
"""

import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置环境变量
import os
os.environ['PYTHONPATH'] = str(project_root)

# 添加backend目录到路径
backend_dir = project_root / "backend"
sys.path.insert(0, str(backend_dir))

from backend.core.database import SessionLocal
from backend.models.task import Task, TaskStatus, TaskType
from backend.models.project import Project, ProjectStatus
from backend.services.task_queue_service import TaskQueueService
from backend.services.processing_service import ProcessingService
from backend.core.celery_simple import celery_app

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def list_pending_tasks():
    """列出所有等待中的任务"""
    print("🔍 查看等待中的任务...")
    
    try:
        db = SessionLocal()
        
        try:
            # 查询等待中的任务
            pending_tasks = db.query(Task).filter(Task.status == TaskStatus.PENDING).all()
            
            if not pending_tasks:
                print("✅ 没有等待中的任务")
                return []
            
            print(f"📋 找到 {len(pending_tasks)} 个等待中的任务:")
            print("-" * 80)
            
            for i, task in enumerate(pending_tasks, 1):
                print(f"{i}. 任务ID: {task.id}")
                print(f"   名称: {task.name}")
                print(f"   类型: {task.task_type}")
                print(f"   项目ID: {task.project_id}")
                print(f"   创建时间: {task.created_at}")
                print(f"   优先级: {task.priority}")
                if task.description:
                    print(f"   描述: {task.description}")
                print("-" * 80)
            
            return pending_tasks
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ 查询等待中的任务失败: {e}")
        return []

def list_pending_projects():
    """列出所有等待中的项目"""
    print("\n🔍 查看等待中的项目...")
    
    try:
        db = SessionLocal()
        
        try:
            # 查询等待中的项目
            pending_projects = db.query(Project).filter(Project.status == ProjectStatus.PENDING).all()
            
            if not pending_projects:
                print("✅ 没有等待中的项目")
                return []
            
            print(f"📋 找到 {len(pending_projects)} 个等待中的项目:")
            print("-" * 80)
            
            for i, project in enumerate(pending_projects, 1):
                print(f"{i}. 项目ID: {project.id}")
                print(f"   名称: {project.name}")
                print(f"   类型: {project.project_type}")
                print(f"   创建时间: {project.created_at}")
                if project.description:
                    print(f"   描述: {project.description}")
                print("-" * 80)
            
            return pending_projects
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ 查询等待中的项目失败: {e}")
        return []

def start_task(task_id: str):
    """启动指定任务"""
    print(f"🚀 启动任务: {task_id}")
    
    try:
        db = SessionLocal()
        task_service = TaskQueueService(db)
        
        try:
            # 获取任务信息
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                print(f"❌ 任务不存在: {task_id}")
                return False
            
            if task.status != TaskStatus.PENDING:
                print(f"❌ 任务状态不是等待中: {task.status}")
                return False
            
            print(f"📋 任务信息:")
            print(f"   名称: {task.name}")
            print(f"   类型: {task.task_type}")
            print(f"   项目ID: {task.project_id}")
            
            # 根据任务类型启动不同的处理
            if task.task_type == TaskType.VIDEO_PROCESSING:
                return start_video_processing_task(task, db)
            else:
                print(f"⚠️ 不支持的任务类型: {task.task_type}")
                return False
                
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ 启动任务失败: {e}")
        return False

def start_video_processing_task(task: Task, db):
    """启动视频处理任务"""
    print("🎬 启动视频处理任务...")
    
    try:
        # 获取项目信息
        project = db.query(Project).filter(Project.id == task.project_id).first()
        if not project:
            print(f"❌ 项目不存在: {task.project_id}")
            return False
        
        # 获取项目文件路径
        from backend.core.path_utils import get_project_raw_directory
        raw_dir = get_project_raw_directory(project.id)
        
        video_path = None
        srt_path = None
        
        # 从项目配置中获取文件路径
        if project.video_path:
            video_path = project.video_path
        
        # 从processing_config中获取SRT路径
        if project.processing_config and "subtitle_path" in project.processing_config:
            srt_path = project.processing_config["subtitle_path"]
        
        # 如果路径不存在，尝试从raw目录查找
        if not video_path or not Path(video_path).exists():
            video_files = list(raw_dir.glob("*.mp4"))
            if video_files:
                video_path = str(video_files[0])
        
        if not srt_path or not Path(srt_path).exists():
            srt_files = list(raw_dir.glob("*.srt"))
            if srt_files:
                srt_path = str(srt_files[0])
        
        print(f"📁 文件路径:")
        print(f"   视频: {video_path}")
        print(f"   字幕: {srt_path}")
        
        # 启动Celery任务
        from backend.tasks.processing import process_video_pipeline
        
        celery_task = process_video_pipeline.delay(
            project_id=str(project.id),
            input_video_path=video_path or "",
            input_srt_path=srt_path or ""
        )
        
        # 更新任务状态
        task.status = TaskStatus.RUNNING
        task.celery_task_id = celery_task.id
        task.started_at = datetime.utcnow()
        db.commit()
        
        print(f"✅ 任务已启动，Celery任务ID: {celery_task.id}")
        return True
        
    except Exception as e:
        print(f"❌ 启动视频处理任务失败: {e}")
        return False

def start_project(project_id: str):
    """启动指定项目"""
    print(f"🚀 启动项目: {project_id}")
    
    try:
        db = SessionLocal()
        processing_service = ProcessingService(db)
        
        try:
            # 获取项目信息
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                print(f"❌ 项目不存在: {project_id}")
                return False
            
            if project.status != ProjectStatus.PENDING:
                print(f"❌ 项目状态不是等待中: {project.status}")
                return False
            
            print(f"📋 项目信息:")
            print(f"   名称: {project.name}")
            print(f"   类型: {project.project_type}")
            
            # 获取项目文件路径
            from backend.core.path_utils import get_project_raw_directory
            raw_dir = get_project_raw_directory(project.id)
            
            video_path = None
            srt_path = None
            
            # 从项目配置中获取文件路径
            if project.video_path:
                video_path = project.video_path
            
            # 从processing_config中获取SRT路径
            if project.processing_config and "subtitle_path" in project.processing_config:
                srt_path = project.processing_config["subtitle_path"]
            
            # 如果路径不存在，尝试从raw目录查找
            if not video_path or not Path(video_path).exists():
                video_files = list(raw_dir.glob("*.mp4"))
                if video_files:
                    video_path = str(video_files[0])
            
            if not srt_path or not Path(srt_path).exists():
                srt_files = list(raw_dir.glob("*.srt"))
                if srt_files:
                    srt_path = str(srt_files[0])
            
            print(f"📁 文件路径:")
            print(f"   视频: {video_path}")
            print(f"   字幕: {srt_path}")
            
            # 启动处理
            result = processing_service.start_processing(project_id, Path(srt_path) if srt_path else None)
            
            print(f"✅ 项目处理已启动")
            print(f"   结果: {result}")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ 启动项目失败: {e}")
        return False

def start_all_pending_tasks():
    """启动所有等待中的任务"""
    print("🚀 启动所有等待中的任务...")
    
    # 获取等待中的任务
    pending_tasks = list_pending_tasks()
    
    if not pending_tasks:
        print("✅ 没有等待中的任务需要启动")
        return
    
    # 启动每个任务
    success_count = 0
    for task in pending_tasks:
        if start_task(task.id):
            success_count += 1
    
    print(f"✅ 成功启动 {success_count}/{len(pending_tasks)} 个任务")

def start_all_pending_projects():
    """启动所有等待中的项目"""
    print("🚀 启动所有等待中的项目...")
    
    # 获取等待中的项目
    pending_projects = list_pending_projects()
    
    if not pending_projects:
        print("✅ 没有等待中的项目需要启动")
        return
    
    # 启动每个项目
    success_count = 0
    for project in pending_projects:
        if start_project(project.id):
            success_count += 1
    
    print(f"✅ 成功启动 {success_count}/{len(pending_projects)} 个项目")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="启动等待中的任务")
    parser.add_argument("--list", action="store_true", help="列出等待中的任务")
    parser.add_argument("--list-projects", action="store_true", help="列出等待中的项目")
    parser.add_argument("--start-task", type=str, help="启动指定任务ID")
    parser.add_argument("--start-project", type=str, help="启动指定项目ID")
    parser.add_argument("--start-all", action="store_true", help="启动所有等待中的任务")
    parser.add_argument("--start-all-projects", action="store_true", help="启动所有等待中的项目")
    
    args = parser.parse_args()
    
    if args.list:
        list_pending_tasks()
    elif args.list_projects:
        list_pending_projects()
    elif args.start_task:
        start_task(args.start_task)
    elif args.start_project:
        start_project(args.start_project)
    elif args.start_all:
        start_all_pending_tasks()
    elif args.start_all_projects:
        start_all_pending_projects()
    else:
        # 默认显示所有等待中的任务和项目
        list_pending_tasks()
        list_pending_projects()
        
        # 询问是否启动所有任务
        response = input("\n是否启动所有等待中的任务？(y/N): ")
        if response.lower() in ['y', 'yes']:
            start_all_pending_tasks()
            start_all_pending_projects()

if __name__ == "__main__":
    main()
