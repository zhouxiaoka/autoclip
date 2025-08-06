"""
维护任务
系统维护、清理、健康检查等任务
"""

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
from celery import current_task

from backend.core.celery_app import celery_app
from backend.core.database import SessionLocal
from backend.models.task import Task, TaskStatus
from backend.models.project import Project, ProjectStatus
from backend.repositories.task_repository import TaskRepository
from backend.repositories.project_repository import ProjectRepository

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='backend.tasks.maintenance.cleanup_expired_tasks')
def cleanup_expired_tasks(self, days: int = 7) -> Dict[str, Any]:
    """
    清理过期任务
    
    Args:
        days: 过期天数，默认7天
        
    Returns:
        清理结果
    """
    logger.info(f"开始清理过期任务，过期天数: {days}")
    
    try:
        # 创建数据库会话
        db = SessionLocal()
        
        try:
            task_repo = TaskRepository(db)
            
            # 计算过期时间
            expired_time = datetime.utcnow() - timedelta(days=days)
            
            # 查找过期任务
            expired_tasks = db.query(Task).filter(
                Task.created_at < expired_time,
                Task.status.in_([TaskStatus.COMPLETED, TaskStatus.FAILED])
            ).all()
            
            cleaned_count = 0
            
            for task in expired_tasks:
                try:
                    # 删除任务相关文件
                    if task.result and isinstance(task.result, dict):
                        # 这里可以添加文件清理逻辑
                        pass
                    
                    # 删除任务记录
                    task_repo.delete(task.id)
                    cleaned_count += 1
                    
                    logger.info(f"已清理过期任务: {task.id}")
                    
                except Exception as e:
                    logger.error(f"清理任务失败: {task.id}, 错误: {e}")
            
            logger.info(f"过期任务清理完成，共清理 {cleaned_count} 个任务")
            return {
                'success': True,
                'cleaned_count': cleaned_count,
                'expired_time': expired_time.isoformat(),
                'message': f'成功清理 {cleaned_count} 个过期任务'
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"清理过期任务失败，错误: {e}")
        raise


@celery_app.task(bind=True, name='backend.tasks.maintenance.health_check')
def health_check(self) -> Dict[str, Any]:
    """
    系统健康检查
    
    Returns:
        健康检查结果
    """
    logger.info("开始系统健康检查")
    
    try:
        health_status = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'healthy',
            'checks': {}
        }
        
        # 检查数据库连接
        try:
            db = SessionLocal()
            db.execute("SELECT 1")
            db.close()
            health_status['checks']['database'] = {'status': 'healthy', 'message': '数据库连接正常'}
        except Exception as e:
            health_status['checks']['database'] = {'status': 'unhealthy', 'message': f'数据库连接失败: {e}'}
            health_status['status'] = 'unhealthy'
        
        # 检查Redis连接
        try:
            import redis
            r = redis.Redis.from_url('redis://localhost:6379/0')
            r.ping()
            health_status['checks']['redis'] = {'status': 'healthy', 'message': 'Redis连接正常'}
        except Exception as e:
            health_status['checks']['redis'] = {'status': 'unhealthy', 'message': f'Redis连接失败: {e}'}
            health_status['status'] = 'unhealthy'
        
        # 检查磁盘空间
        try:
            import psutil
            disk_usage = psutil.disk_usage('/')
            disk_percent = disk_usage.percent
            if disk_percent < 90:
                health_status['checks']['disk'] = {'status': 'healthy', 'message': f'磁盘使用率: {disk_percent}%'}
            else:
                health_status['checks']['disk'] = {'status': 'warning', 'message': f'磁盘使用率过高: {disk_percent}%'}
        except Exception as e:
            health_status['checks']['disk'] = {'status': 'unknown', 'message': f'无法检查磁盘状态: {e}'}
        
        # 检查内存使用
        try:
            import psutil
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            if memory_percent < 80:
                health_status['checks']['memory'] = {'status': 'healthy', 'message': f'内存使用率: {memory_percent}%'}
            else:
                health_status['checks']['memory'] = {'status': 'warning', 'message': f'内存使用率过高: {memory_percent}%'}
        except Exception as e:
            health_status['checks']['memory'] = {'status': 'unknown', 'message': f'无法检查内存状态: {e}'}
        
        logger.info(f"系统健康检查完成，状态: {health_status['status']}")
        return health_status
        
    except Exception as e:
        logger.error(f"系统健康检查失败，错误: {e}")
        raise


@celery_app.task(bind=True, name='backend.tasks.maintenance.backup_project_data')
def backup_project_data(self, project_id: str, backup_path: str = None) -> Dict[str, Any]:
    """
    备份项目数据
    
    Args:
        project_id: 项目ID
        backup_path: 备份路径
        
    Returns:
        备份结果
    """
    logger.info(f"开始备份项目数据: {project_id}")
    
    try:
        # 创建数据库会话
        db = SessionLocal()
        
        try:
            project_repo = ProjectRepository(db)
            project = project_repo.get_by_id(project_id)
            
            if not project:
                raise ValueError(f"项目不存在: {project_id}")
            
            # 生成备份路径
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"data/backups/{project_id}_{timestamp}"
            
            backup_dir = Path(backup_path)
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # 备份项目目录
            project_dir = Path(f"data/projects/{project_id}")
            if project_dir.exists():
                backup_project_dir = backup_dir / "project_files"
                shutil.copytree(project_dir, backup_project_dir, dirs_exist_ok=True)
            
            # 备份数据库记录
            project_data = {
                'project': {
                    'id': project.id,
                    'name': project.name,
                    'status': project.status.value,
                    'created_at': project.created_at.isoformat(),
                    'updated_at': project.updated_at.isoformat()
                },
                'tasks': [],
                'clips': [],
                'collections': []
            }
            
            # 备份任务数据
            tasks = db.query(Task).filter(Task.project_id == project_id).all()
            for task in tasks:
                project_data['tasks'].append({
                    'id': task.id,
                    'name': task.name,
                    'status': task.status.value,
                    'task_type': task.task_type.value,
                    'created_at': task.created_at.isoformat(),
                    'updated_at': task.updated_at.isoformat()
                })
            
            # 保存备份数据
            import json
            backup_file = backup_dir / "project_data.json"
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"项目数据备份完成: {project_id} -> {backup_path}")
            return {
                'success': True,
                'project_id': project_id,
                'backup_path': str(backup_path),
                'backup_size': sum(f.stat().st_size for f in backup_dir.rglob('*') if f.is_file()),
                'message': '项目数据备份成功'
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"项目数据备份失败: {project_id}, 错误: {e}")
        raise