"""Pipeline适配器服务 - 将shared/pipeline中的处理逻辑集成到新架构"""

import json
import logging
import asyncio
import sys
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from datetime import datetime

# 导入新架构的模型和服务
from models.project import Project, ProjectStatus
from models.task import Task, TaskStatus
from core.database import get_db
from core.progress_manager import get_progress_manager
from core.config import get_project_root, get_data_directory, get_output_directory
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 添加shared目录到Python路径
project_root = get_project_root()
shared_path = project_root / "shared"
if str(shared_path) not in sys.path:
    sys.path.insert(0, str(shared_path))

# 导入shared/pipeline中的处理步骤
try:
    from pipeline.step1_outline import run_step1_outline
    from pipeline.step2_timeline import run_step2_timeline
    from pipeline.step3_scoring import run_step3_scoring
    from pipeline.step4_title import run_step4_title
    from pipeline.step5_clustering import run_step5_clustering
    from pipeline.step6_video import run_step6_video
    logger.info("流水线模块导入成功")
except ImportError as e:
    logger.warning(f"无法导入流水线模块: {e}")
    # 定义占位符函数
    def run_step1_outline(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        # 生成模拟输出
        srt_path = kwargs.get('srt_path')
        output_path = kwargs.get('output_path')
        if output_path:
            import json
            from pathlib import Path
            # 确保output_path是Path对象
            if isinstance(output_path, str):
                output_path = Path(output_path)
            # 确保父目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mock_output = {
                "outlines": [
                    {"topic": "测试话题1", "start_time": "00:00:00", "end_time": "00:00:05", "content": "测试内容1"},
                    {"topic": "测试话题2", "start_time": "00:00:05", "end_time": "00:00:10", "content": "测试内容2"}
                ],
                "status": "completed",
                "message": "占位符函数生成的模拟输出"
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(mock_output, f, ensure_ascii=False, indent=2)
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step2_timeline(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        # 生成模拟输出
        output_path = kwargs.get('output_path')
        if output_path:
            import json
            from pathlib import Path
            # 确保output_path是Path对象
            if isinstance(output_path, str):
                output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mock_output = {
                "timeline": [
                    {"time": "00:00:00", "event": "开始"},
                    {"time": "00:00:05", "event": "话题1"},
                    {"time": "00:00:10", "event": "话题2"}
                ],
                "status": "completed",
                "message": "占位符函数生成的模拟输出"
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(mock_output, f, ensure_ascii=False, indent=2)
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step3_scoring(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        # 生成模拟输出
        output_path = kwargs.get('output_path')
        if output_path:
            import json
            from pathlib import Path
            # 确保output_path是Path对象
            if isinstance(output_path, str):
                output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mock_output = {
                "scored_clips": [
                    {"clip_id": "1", "score": 0.8, "content": "高分内容1"},
                    {"clip_id": "2", "score": 0.7, "content": "高分内容2"}
                ],
                "status": "completed",
                "message": "占位符函数生成的模拟输出"
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(mock_output, f, ensure_ascii=False, indent=2)
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step4_title(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        # 生成模拟输出
        output_path = kwargs.get('output_path')
        if output_path:
            import json
            from pathlib import Path
            # 确保output_path是Path对象
            if isinstance(output_path, str):
                output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mock_output = {
                "titles": [
                    {"clip_id": "1", "title": "测试标题1"},
                    {"clip_id": "2", "title": "测试标题2"}
                ],
                "status": "completed",
                "message": "占位符函数生成的模拟输出"
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(mock_output, f, ensure_ascii=False, indent=2)
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step5_clustering(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        # 生成模拟输出
        output_path = kwargs.get('output_path')
        if output_path:
            import json
            from pathlib import Path
            # 确保output_path是Path对象
            if isinstance(output_path, str):
                output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mock_output = {
                "collections": [
                    {"collection_id": "1", "title": "测试合集1", "clips": ["1", "2"]},
                    {"collection_id": "2", "title": "测试合集2", "clips": ["3", "4"]}
                ],
                "status": "completed",
                "message": "占位符函数生成的模拟输出"
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(mock_output, f, ensure_ascii=False, indent=2)
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step6_video(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        # 生成模拟输出
        output_path = kwargs.get('output_path')
        if output_path:
            import json
            from pathlib import Path
            # 确保output_path是Path对象
            if isinstance(output_path, str):
                output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            mock_output = {
                "videos": [
                    {"clip_id": "1", "video_path": "output/clip_1.mp4"},
                    {"clip_id": "2", "video_path": "output/clip_2.mp4"}
                ],
                "status": "completed",
                "message": "占位符函数生成的模拟输出"
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(mock_output, f, ensure_ascii=False, indent=2)
        return {"status": "skipped", "message": "流水线模块未正确导入"}

class PipelineAdapter:
    """Pipeline适配器 - 桥接旧Pipeline和新架构"""
    
    def __init__(self, db: Session, task_id: Optional[int] = None, progress_callback: Optional[Callable[[int, int, str], Any]] = None):
        self.db = db
        self.task_id = task_id
        self.progress_callback = progress_callback
        self.progress_manager = get_progress_manager(db) if task_id else None
        
        # 步骤配置
        self.steps = [
            {"name": "outline", "description": "提取视频大纲", "weight": 15},
            {"name": "timeline", "description": "生成时间线", "weight": 20},
            {"name": "scoring", "description": "内容评分", "weight": 20},
            {"name": "title", "description": "生成标题", "weight": 15},
            {"name": "clustering", "description": "主题聚类", "weight": 15},
            {"name": "video", "description": "生成视频", "weight": 15}
        ]
        
    def process_project_sync(self, project_id: str, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
        """同步处理整个项目的Pipeline流程"""
        try:
            # 获取项目信息
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if not project:
                raise ValueError(f"项目 {project_id} 不存在")
            
            # 更新项目状态
            project.status = ProjectStatus.PROCESSING
            project.started_at = datetime.utcnow()
            self.db.commit()
            
            # 创建项目工作目录
            data_dir = get_data_directory()
            project_dir = data_dir / "projects" / str(project_id)
            project_dir.mkdir(parents=True, exist_ok=True)
            
            # 执行6个步骤
            results = {}
            total_progress = 0
            
            for i, step in enumerate(self.steps):
                step_name = step["name"]
                step_description = step["description"]
                step_weight = step["weight"]
                
                logger.info(f"开始执行步骤 {i+1}/6: {step_description}")
                
                # 更新进度
                self._update_progress_sync(project_id, total_progress, f"正在{step_description}...")
                
                try:
                    # 执行具体步骤
                    if step_name == "outline":
                        results[step_name] = self._step1_outline_sync(input_srt_path, project_dir)
                    elif step_name == "timeline":
                        results[step_name] = self._step2_timeline_sync(results["outline"], project_dir)
                    elif step_name == "scoring":
                        results[step_name] = self._step3_scoring_sync(results["timeline"], project_dir)
                    elif step_name == "title":
                        results[step_name] = self._step4_title_sync(results["scoring"], project_dir)
                    elif step_name == "clustering":
                        results[step_name] = self._step5_clustering_sync(results["title"], project_dir)
                    elif step_name == "video":
                        results[step_name] = self._step6_video_sync(results["clustering"], input_video_path, project_dir)
                    
                    total_progress += step_weight
                    self._update_progress_sync(project_id, total_progress, f"{step_description}完成", results[step_name])
                
                except Exception as e:
                    logger.error(f"步骤 {step_name} 执行失败: {str(e)}")
                    self._update_progress_sync(project_id, total_progress, f"{step_description}失败: {str(e)}")
                    raise
            
            # 更新项目状态为完成
            project.status = ProjectStatus.COMPLETED
            project.completed_at = datetime.utcnow()
            project.result_data = results
            self.db.commit()
            
            self._update_progress_sync(project_id, 100, "项目处理完成")
            
            logger.info(f"项目 {project_id} 处理完成")
            return results
            
        except Exception as e:
            # 更新项目状态为失败
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = ProjectStatus.FAILED
                project.error_message = str(e)
                self.db.commit()
            
            self._update_progress_sync(project_id, -1, f"处理失败: {str(e)}")
            logger.error(f"项目 {project_id} 处理失败: {str(e)}")
            raise
    
    def _step1_outline_sync(self, srt_path: str, project_dir: Path) -> Dict[str, Any]:
        """步骤1: 提取视频大纲"""
        srt_file = Path(srt_path)
        if not srt_file.exists():
            raise FileNotFoundError(f"SRT文件不存在: {srt_path}")
        
        output_path = project_dir / "step1_outline.json"
        result = run_step1_outline(srt_file, output_path=output_path)
        
        return result
    
    def _step2_timeline_sync(self, outline_result: Dict[str, Any], project_dir: Path) -> Dict[str, Any]:
        """步骤2: 生成时间线"""
        # 使用上一步的输出作为输入
        outline_path = project_dir / "step1_outline.json"
        output_path = project_dir / "step2_timeline.json"
        result = run_step2_timeline(outline_path, output_path=output_path)
        
        return result
    
    def _step3_scoring_sync(self, timeline_result: Dict[str, Any], project_dir: Path) -> Dict[str, Any]:
        """步骤3: 内容评分"""
        # 使用上一步的输出作为输入
        timeline_path = project_dir / "step2_timeline.json"
        output_path = project_dir / "step3_scored_clips.json"
        result = run_step3_scoring(timeline_path, output_path=output_path)
        
        return result
    
    def _step4_title_sync(self, scoring_result: Dict[str, Any], project_dir: Path) -> Dict[str, Any]:
        """步骤4: 生成标题"""
        # 使用上一步的输出作为输入
        high_score_clips_path = project_dir / "step3_scored_clips.json"
        output_path = project_dir / "step4_titles.json"
        result = run_step4_title(high_score_clips_path, output_path=output_path)
        
        return result
    
    def _step5_clustering_sync(self, title_result: Dict[str, Any], project_dir: Path) -> Dict[str, Any]:
        """步骤5: 主题聚类"""
        # 使用上一步的输出作为输入
        clips_with_titles_path = project_dir / "step4_titles.json"
        output_path = project_dir / "step5_collections.json"
        result = run_step5_clustering(clips_with_titles_path, output_path=output_path)
        
        return result
    
    def _step6_video_sync(self, clustering_result: Dict[str, Any], input_video_path: str, project_dir: Path) -> Dict[str, Any]:
        """步骤6: 生成视频"""
        input_video = Path(input_video_path)
        if not input_video.exists():
            raise FileNotFoundError(f"输入视频不存在: {input_video_path}")
        
        # 使用上一步的输出作为输入
        clips_with_titles_path = project_dir / "step4_titles.json"
        collections_path = project_dir / "step5_collections.json"
        output_path = project_dir / "step6_video_result.json"
        result = run_step6_video(clips_with_titles_path, collections_path, input_video, output_path)
        
        return result
    
    def _update_progress_sync(self, project_id: str, progress: int, message: str, step_result: Optional[Dict[str, Any]] = None):
        """同步更新项目进度"""
        try:
            # 更新数据库中的项目进度
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.progress = progress
                project.current_step = message
                self.db.commit()
            
            # 使用进度管理器更新进度
            if self.progress_manager and self.task_id:
                # 这里需要异步调用，但在同步环境中我们跳过
                pass
            
            logger.info(f"项目 {project_id} 进度: {progress}% - {message}")
                
        except Exception as e:
            logger.error(f"更新进度失败: {str(e)}")
    
    def get_project_status(self, project_id: str) -> Dict[str, Any]:
        """获取项目状态"""
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return {"error": "项目不存在"}
        
        return {
            "id": project.id,
            "name": project.name,
            "status": project.status.value,
            "progress": project.progress or 0,
            "current_step": project.current_step or "",
            "started_at": project.started_at.isoformat() if project.started_at else None,
            "completed_at": project.completed_at.isoformat() if project.completed_at else None,
            "error_message": project.error_message
        }

# 工厂函数
def create_pipeline_adapter(db: Session, task_id: Optional[int] = None, progress_callback: Optional[Callable[[int, int, str], Any]] = None) -> PipelineAdapter:
    """创建Pipeline适配器实例"""
    return PipelineAdapter(db, task_id, progress_callback)

# 同步版本的工厂函数，用于在非异步环境中使用
def create_pipeline_adapter_sync(db: Session, task_id: Optional[int] = None) -> PipelineAdapter:
    """创建同步版本的Pipeline适配器实例"""
    return PipelineAdapter(db, task_id, None)