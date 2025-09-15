"""
数据清理任务
定期清理数据库和文件系统中的过期数据
"""

import os
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
from celery import current_task, shared_task

from ..core.celery_app import celery_app
from ..core.database import SessionLocal
from ..models.task import Task, TaskStatus
from ..models.project import Project, ProjectStatus
from ..models.clip import Clip
from ..models.collection import Collection
from ..repositories.task_repository import TaskRepository
from ..repositories.project_repository import ProjectRepository

logger = logging.getLogger(__name__)


@shared_task(bind=True, name='backend.tasks.data_cleanup.cleanup_expired_data')
def cleanup_expired_data(self, days: int = 30) -> Dict[str, Any]:
    """
    清理过期数据
    
    Args:
        days: 保留天数，默认30天
        
    Returns:
        清理结果
    """
    logger.info(f"开始清理过期数据，保留天数: {days}")
    
    try:
        # 创建数据库会话
        db = SessionLocal()
        
        try:
            cleanup_results = {
                'timestamp': datetime.utcnow().isoformat(),
                'days': days,
                'tasks_cleaned': 0,
                'projects_cleaned': 0,
                'files_cleaned': 0,
                'errors': []
            }
            
            # 1. 清理过期任务
            try:
                task_repo = TaskRepository(db)
                tasks_cleaned = task_repo.cleanup_old_tasks(days)
                cleanup_results['tasks_cleaned'] = tasks_cleaned
                logger.info(f"清理了 {tasks_cleaned} 个过期任务")
            except Exception as e:
                error_msg = f"清理任务失败: {str(e)}"
                logger.error(error_msg)
                cleanup_results['errors'].append(error_msg)
            
            # 2. 清理过期项目
            try:
                projects_cleaned = _cleanup_expired_projects(db, days)
                cleanup_results['projects_cleaned'] = projects_cleaned
                logger.info(f"清理了 {projects_cleaned} 个过期项目")
            except Exception as e:
                error_msg = f"清理项目失败: {str(e)}"
                logger.error(error_msg)
                cleanup_results['errors'].append(error_msg)
            
            # 3. 清理孤立文件
            try:
                files_cleaned = _cleanup_orphaned_files()
                cleanup_results['files_cleaned'] = files_cleaned
                logger.info(f"清理了 {files_cleaned} 个孤立文件")
            except Exception as e:
                error_msg = f"清理文件失败: {str(e)}"
                logger.error(error_msg)
                cleanup_results['errors'].append(error_msg)
            
            # 4. 清理临时文件
            try:
                temp_files_cleaned = _cleanup_temp_files()
                cleanup_results['temp_files_cleaned'] = temp_files_cleaned
                logger.info(f"清理了 {temp_files_cleaned} 个临时文件")
            except Exception as e:
                error_msg = f"清理临时文件失败: {str(e)}"
                logger.error(error_msg)
                cleanup_results['errors'].append(error_msg)
            
            cleanup_results['success'] = len(cleanup_results['errors']) == 0
            cleanup_results['total_cleaned'] = (
                cleanup_results['tasks_cleaned'] + 
                cleanup_results['projects_cleaned'] + 
                cleanup_results['files_cleaned'] +
                cleanup_results.get('temp_files_cleaned', 0)
            )
            
            logger.info(f"数据清理完成，共清理 {cleanup_results['total_cleaned']} 项数据")
            return cleanup_results
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"清理过期数据失败，错误: {e}")
        raise


def _cleanup_expired_projects(db: SessionLocal, days: int) -> int:
    """清理过期项目"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # 查找过期的已完成项目
    expired_projects = db.query(Project).filter(
        Project.status == ProjectStatus.COMPLETED,
        Project.updated_at < cutoff_date
    ).all()
    
    cleaned_count = 0
    for project in expired_projects:
        try:
            # 删除项目相关数据
            _delete_project_data(db, project.id)
            cleaned_count += 1
            logger.info(f"清理过期项目: {project.id}")
        except Exception as e:
            logger.error(f"清理项目 {project.id} 失败: {e}")
    
    return cleaned_count


def _delete_project_data(db: SessionLocal, project_id: str):
    """删除项目数据"""
    # 删除相关任务
    db.query(Task).filter(Task.project_id == project_id).delete()
    
    # 删除相关切片
    db.query(Clip).filter(Clip.project_id == project_id).delete()
    
    # 删除相关合集
    db.query(Collection).filter(Collection.project_id == project_id).delete()
    
    # 删除项目记录
    db.query(Project).filter(Project.id == project_id).delete()
    
    # 删除项目文件
    project_dir = Path(f"data/projects/{project_id}")
    if project_dir.exists():
        shutil.rmtree(project_dir)
    
    # 清理进度数据
    try:
        from ..services.simple_progress import clear_progress
        clear_progress(project_id)
    except Exception as e:
        logger.warning(f"清理进度数据失败: {e}")
    
    db.commit()


def _cleanup_orphaned_files() -> int:
    """清理孤立文件"""
    cleaned_count = 0
    
    try:
        # 获取数据库中的项目ID
        db = SessionLocal()
        try:
            db_projects = {p.id for p in db.query(Project).all()}
        finally:
            db.close()
        
        # 清理孤立的项目目录
        projects_dir = Path("data/projects")
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir() and project_dir.name not in db_projects:
                    if not project_dir.name.startswith('.'):
                        shutil.rmtree(project_dir)
                        cleaned_count += 1
                        logger.info(f"清理孤立项目目录: {project_dir.name}")
        
        # 清理孤立的输出文件
        output_dir = Path("data/output")
        if output_dir.exists():
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    # 检查文件是否属于现有项目
                    file_name = file_path.name
                    is_orphaned = True
                    
                    for project_id in db_projects:
                        if project_id in file_name:
                            is_orphaned = False
                            break
                    
                    if is_orphaned:
                        file_path.unlink()
                        cleaned_count += 1
                        logger.info(f"清理孤立输出文件: {file_path}")
        
    except Exception as e:
        logger.error(f"清理孤立文件失败: {e}")
    
    return cleaned_count


def _cleanup_temp_files() -> int:
    """清理临时文件"""
    cleaned_count = 0
    
    try:
        temp_dir = Path("data/temp")
        if temp_dir.exists():
            for file_path in temp_dir.iterdir():
                if file_path.is_file():
                    # 检查文件是否超过1小时
                    file_age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_age > timedelta(hours=1):
                        file_path.unlink()
                        cleaned_count += 1
                        logger.info(f"清理临时文件: {file_path}")
        
        # 清理处理中间文件
        projects_dir = Path("data/projects")
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir():
                    processing_dir = project_dir / "processing"
                    if processing_dir.exists():
                        for file_path in processing_dir.iterdir():
                            if file_path.is_file():
                                # 检查文件是否超过24小时
                                file_age = datetime.now() - datetime.fromtimestamp(file_path.stat().st_mtime)
                                if file_age > timedelta(hours=24):
                                    file_path.unlink()
                                    cleaned_count += 1
                                    logger.info(f"清理处理中间文件: {file_path}")
        
    except Exception as e:
        logger.error(f"清理临时文件失败: {e}")
    
    return cleaned_count


@shared_task(bind=True, name='backend.tasks.data_cleanup.check_data_consistency')
def check_data_consistency(self) -> Dict[str, Any]:
    """
    检查数据一致性
    
    Returns:
        一致性检查结果
    """
    logger.info("开始数据一致性检查")
    
    try:
        # 创建数据库会话
        db = SessionLocal()
        
        try:
            issues = []
            
            # 1. 检查项目数据一致性
            db_projects = {p.id for p in db.query(Project).all()}
            fs_projects = set()
            
            projects_dir = Path("data/projects")
            if projects_dir.exists():
                for project_dir in projects_dir.iterdir():
                    if project_dir.is_dir() and not project_dir.name.startswith('.'):
                        fs_projects.add(project_dir.name)
            
            # 检查孤立文件
            orphaned_files = fs_projects - db_projects
            if orphaned_files:
                issues.append({
                    "type": "orphaned_files",
                    "count": len(orphaned_files),
                    "details": list(orphaned_files)
                })
            
            # 检查缺失文件
            missing_files = db_projects - fs_projects
            if missing_files:
                issues.append({
                    "type": "missing_files",
                    "count": len(missing_files),
                    "details": list(missing_files)
                })
            
            # 2. 检查任务数据一致性
            orphaned_tasks = db.query(Task).filter(
                ~Task.project_id.in_(db_projects)
            ).count()
            
            if orphaned_tasks > 0:
                issues.append({
                    "type": "orphaned_tasks",
                    "count": orphaned_tasks,
                    "details": []
                })
            
            # 3. 检查切片数据一致性
            orphaned_clips = db.query(Clip).filter(
                ~Clip.project_id.in_(db_projects)
            ).count()
            
            if orphaned_clips > 0:
                issues.append({
                    "type": "orphaned_clips",
                    "count": orphaned_clips,
                    "details": []
                })
            
            # 4. 检查合集数据一致性
            orphaned_collections = db.query(Collection).filter(
                ~Collection.project_id.in_(db_projects)
            ).count()
            
            if orphaned_collections > 0:
                issues.append({
                    "type": "orphaned_collections",
                    "count": orphaned_collections,
                    "details": []
                })
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'total_issues': len(issues),
                'issues': issues,
                'status': 'healthy' if len(issues) == 0 else 'unhealthy'
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"数据一致性检查失败，错误: {e}")
        raise


@shared_task(bind=True, name='backend.tasks.data_cleanup.cleanup_orphaned_data')
def cleanup_orphaned_data(self) -> Dict[str, Any]:
    """
    清理孤立数据
    
    Returns:
        清理结果
    """
    logger.info("开始清理孤立数据")
    
    try:
        # 创建数据库会话
        db = SessionLocal()
        
        try:
            cleanup_results = {
                'timestamp': datetime.utcnow().isoformat(),
                'orphaned_tasks_cleaned': 0,
                'orphaned_clips_cleaned': 0,
                'orphaned_collections_cleaned': 0,
                'orphaned_files_cleaned': 0
            }
            
            # 获取所有项目ID
            db_projects = {p.id for p in db.query(Project).all()}
            
            # 1. 清理孤立任务
            orphaned_tasks = db.query(Task).filter(
                ~Task.project_id.in_(db_projects)
            ).all()
            
            for task in orphaned_tasks:
                db.delete(task)
                cleanup_results['orphaned_tasks_cleaned'] += 1
                logger.info(f"清理孤立任务: {task.id}")
            
            # 2. 清理孤立切片
            orphaned_clips = db.query(Clip).filter(
                ~Clip.project_id.in_(db_projects)
            ).all()
            
            for clip in orphaned_clips:
                db.delete(clip)
                cleanup_results['orphaned_clips_cleaned'] += 1
                logger.info(f"清理孤立切片: {clip.id}")
            
            # 3. 清理孤立合集
            orphaned_collections = db.query(Collection).filter(
                ~Collection.project_id.in_(db_projects)
            ).all()
            
            for collection in orphaned_collections:
                db.delete(collection)
                cleanup_results['orphaned_collections_cleaned'] += 1
                logger.info(f"清理孤立合集: {collection.id}")
            
            # 4. 清理孤立文件
            cleanup_results['orphaned_files_cleaned'] = _cleanup_orphaned_files()
            
            db.commit()
            
            total_cleaned = (
                cleanup_results['orphaned_tasks_cleaned'] +
                cleanup_results['orphaned_clips_cleaned'] +
                cleanup_results['orphaned_collections_cleaned'] +
                cleanup_results['orphaned_files_cleaned']
            )
            
            cleanup_results['total_cleaned'] = total_cleaned
            cleanup_results['success'] = True
            
            logger.info(f"孤立数据清理完成，共清理 {total_cleaned} 项数据")
            return cleanup_results
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"清理孤立数据失败，错误: {e}")
        raise
