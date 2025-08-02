"""
Repository模式测试
验证数据访问层的功能
"""

import sys, os
# 添加项目根目录到sys.path，确保能找到backend包
current_file = os.path.abspath(__file__)
backend_dir = os.path.dirname(os.path.dirname(current_file))  # backend目录
project_root = os.path.dirname(backend_dir)  # autoclip根目录

# 将项目根目录添加到sys.path，这样Python能找到backend包
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from repositories.factory import (
    get_project_repository,
    get_clip_repository,
    get_collection_repository,
    get_task_repository
)
from core.database import get_db, init_database, reset_database
from models.project import ProjectStatus, ProjectType
from models.clip import ClipStatus
from models.collection import CollectionStatus
from models.task import TaskStatus, TaskType

class TestRepositoryPattern:
    """Repository模式测试类"""
    
    @pytest.fixture(autouse=True)
    def setup_database(self):
        """设置测试数据库"""
        # 重置数据库，确保测试环境干净
        reset_database()
        # 初始化数据库
        init_database()
        yield
        # 测试结束后清理数据库
        reset_database()
    
    def test_project_repository_crud(self):
        """测试项目Repository的CRUD操作"""
        db = next(get_db())
        project_repo = get_project_repository(db)
        
        # 创建项目
        project_data = {
            "name": "测试项目",
            "description": "这是一个测试项目",
            "project_type": ProjectType.KNOWLEDGE,
            "status": ProjectStatus.PENDING
        }
        
        project = project_repo.create(**project_data)
        assert project.id is not None
        assert project.name == "测试项目"
        assert project.status == ProjectStatus.PENDING
        
        # 查询项目
        retrieved_project = project_repo.get_by_id(project.id)
        assert retrieved_project is not None
        assert retrieved_project.name == "测试项目"
        
        # 更新项目
        updated_project = project_repo.update(project.id, status=ProjectStatus.PROCESSING)
        assert updated_project.status == ProjectStatus.PROCESSING
        
        # 删除项目
        success = project_repo.delete(project.id)
        assert success is True
        
        # 验证删除
        deleted_project = project_repo.get_by_id(project.id)
        assert deleted_project is None
    
    def test_clip_repository_operations(self):
        """测试切片Repository的操作"""
        db = next(get_db())
        project_repo = get_project_repository(db)
        clip_repo = get_clip_repository(db)
        
        # 创建项目
        project = project_repo.create(
            name="测试项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        
        # 创建切片
        clip_data = {
            "project_id": project.id,
            "title": "测试切片",
            "description": "这是一个测试切片",
            "start_time": 0,
            "end_time": 60,
            "duration": 60,
            "score": 0.8,
            "status": ClipStatus.COMPLETED
        }
        
        clip = clip_repo.create(**clip_data)
        assert clip.project_id == project.id
        assert clip.title == "测试切片"
        
        # 测试按项目查询切片
        project_clips = clip_repo.get_by_project(project.id)
        assert len(project_clips) == 1
        assert project_clips[0].id == clip.id
        
        # 测试按状态查询切片
        completed_clips = clip_repo.get_by_status(ClipStatus.COMPLETED)
        assert len(completed_clips) == 1
        assert completed_clips[0].id == clip.id
        
        # 测试高分切片查询
        high_score_clips = clip_repo.get_high_score_clips(project.id, min_score=0.7)
        assert len(high_score_clips) == 1
        assert high_score_clips[0].id == clip.id
    
    def test_collection_repository_operations(self):
        """测试合集Repository的操作"""
        db = next(get_db())
        project_repo = get_project_repository(db)
        collection_repo = get_collection_repository(db)
        
        # 创建项目
        project = project_repo.create(
            name="测试项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        
        # 创建合集
        collection_data = {
            "project_id": project.id,
            "name": "测试合集",
            "description": "这是一个测试合集",
            "theme": "测试主题",
            "clips_count": 5,
            "total_duration": 300,
            "status": CollectionStatus.COMPLETED
        }
        
        collection = collection_repo.create(**collection_data)
        assert collection.project_id == project.id
        assert collection.name == "测试合集"
        
        # 测试按项目查询合集
        project_collections = collection_repo.get_by_project(project.id)
        assert len(project_collections) == 1
        assert project_collections[0].id == collection.id
        
        # 测试按主题查询合集
        theme_collections = collection_repo.get_by_theme(project.id, "测试主题")
        assert len(theme_collections) == 1
        assert theme_collections[0].id == collection.id
    
    def test_task_repository_operations(self):
        """测试任务Repository的操作"""
        db = next(get_db())
        project_repo = get_project_repository(db)
        task_repo = get_task_repository(db)
        
        # 创建项目
        project = project_repo.create(
            name="测试项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        
        # 创建任务
        task_data = {
            "project_id": project.id,
            "name": "测试任务",
            "description": "这是一个测试任务",
            "task_type": TaskType.VIDEO_PROCESSING,
            "status": TaskStatus.PENDING,
            "priority": 1
        }
        
        task = task_repo.create(**task_data)
        assert task.project_id == project.id
        assert task.name == "测试任务"
        assert task.status == TaskStatus.PENDING
        
        # 测试任务状态更新
        task_repo.update_task_status(task.id, TaskStatus.RUNNING)
        updated_task = task_repo.get_by_id(task.id)
        assert updated_task.status == TaskStatus.RUNNING
        
        # 测试任务完成
        task_repo.update_task_status(task.id, TaskStatus.COMPLETED)
        completed_task = task_repo.get_by_id(task.id)
        assert completed_task.status == TaskStatus.COMPLETED
        
        # 测试按项目查询任务
        project_tasks = task_repo.get_by_project(project.id)
        assert len(project_tasks) == 1
        assert project_tasks[0].id == task.id
    
    def test_repository_statistics(self):
        """测试Repository统计功能"""
        db = next(get_db())
        project_repo = get_project_repository(db)
        clip_repo = get_clip_repository(db)
        collection_repo = get_collection_repository(db)
        task_repo = get_task_repository(db)
        
        # 创建项目
        project = project_repo.create(
            name="统计测试项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.COMPLETED
        )
        
        # 创建多个切片
        for i in range(5):
            clip_repo.create(
                project_id=project.id,
                title=f"切片{i+1}",
                start_time=i*60,
                end_time=(i+1)*60,
                duration=60,
                score=0.7 + i*0.1,
                status=ClipStatus.COMPLETED
            )
        
        # 创建多个合集
        for i in range(3):
            collection_repo.create(
                project_id=project.id,
                name=f"合集{i+1}",
                theme=f"主题{i+1}",
                clips_count=2,
                total_duration=120,
                status=CollectionStatus.COMPLETED
            )
        
        # 创建多个任务
        for i in range(6):
            task_repo.create(
                project_id=project.id,
                name=f"任务{i+1}",
                            task_type=TaskType.VIDEO_PROCESSING,
            status=TaskStatus.COMPLETED if i < 5 else TaskStatus.FAILED
            )
        
        # 测试项目统计
        project_stats = project_repo.get_project_statistics()
        assert project_stats["total"] >= 1
        assert project_stats["completed"] >= 1
        
        # 测试切片统计
        clip_stats = clip_repo.get_clips_statistics(project.id)
        assert clip_stats["total"] == 5
        assert clip_stats["completed"] == 5
        assert clip_stats["avg_score"] > 0.7
        
        # 测试合集统计
        collection_stats = collection_repo.get_collections_statistics(project.id)
        assert collection_stats["total"] == 3
        assert collection_stats["completed"] == 3
        
        # 测试任务统计
        task_stats = task_repo.get_tasks_statistics(project.id)
        assert task_stats["total"] == 6
        assert task_stats["completed"] == 5
        assert task_stats["failed"] == 1
    
    def test_repository_search(self):
        """测试Repository搜索功能"""
        db = next(get_db())
        project_repo = get_project_repository(db)
        clip_repo = get_clip_repository(db)
        
        # 创建项目
        project = project_repo.create(
            name="搜索测试项目",
            description="这是一个用于搜索测试的项目",
            project_type=ProjectType.KNOWLEDGE,
            status=ProjectStatus.PENDING
        )
        
        # 创建切片
        clip_repo.create(
            project_id=project.id,
            title="包含关键词的切片",
            description="这个切片包含重要的关键词",
            start_time=0,
            end_time=60,
            duration=60,
            status=ClipStatus.COMPLETED
        )
        
        # 测试项目搜索
        search_results = project_repo.search_projects("搜索测试")
        assert len(search_results) == 1
        assert search_results[0].id == project.id
        
        # 测试切片搜索
        clip_results = clip_repo.search_clips(project.id, "关键词")
        assert len(clip_results) == 1
        assert "关键词" in clip_results[0].title or "关键词" in clip_results[0].description

if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"]) 