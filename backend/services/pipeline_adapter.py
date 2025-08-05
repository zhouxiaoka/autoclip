"""Pipeline适配器服务 - 将shared/pipeline中的处理逻辑集成到新架构"""

import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path
from datetime import datetime

# 导入shared/pipeline中的处理步骤
import sys
shared_path = Path(__file__).parent.parent.parent / "shared"
if str(shared_path) not in sys.path:
    sys.path.insert(0, str(shared_path))

from pipeline.step1_outline import OutlineExtractor
from pipeline.step2_timeline import TimelineExtractor
from pipeline.step3_scoring import ClipScorer
from pipeline.step4_title import TitleGenerator
from pipeline.step5_clustering import ClusteringEngine
from pipeline.step6_video import VideoGenerator
from utils.project_manager import ProjectManager
from config import METADATA_DIR, PROMPT_FILES

# 导入新架构的模型和服务
from models.project import Project, ProjectStatus
from models.task import Task, TaskStatus
from core.database import get_db
from core.progress_manager import get_progress_manager
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class PipelineAdapter:
    """Pipeline适配器 - 桥接旧Pipeline和新架构"""
    
    def __init__(self, db: Session, task_id: Optional[int] = None, progress_callback: Optional[Callable[[int, int, str], Any]] = None):
        self.db = db
        self.task_id = task_id
        self.progress_callback = progress_callback
        self.progress_manager = get_progress_manager(db) if task_id else None
        
        # 初始化各个步骤的处理器
        self.outline_extractor = None
        self.timeline_generator = None
        self.clip_scorer = None
        self.title_generator = None
        self.clustering_engine = None
        self.video_generator = None
        
        # 步骤配置
        self.steps = [
            {"name": "outline", "description": "提取视频大纲", "weight": 15},
            {"name": "timeline", "description": "生成时间线", "weight": 20},
            {"name": "scoring", "description": "内容评分", "weight": 20},
            {"name": "title", "description": "生成标题", "weight": 15},
            {"name": "clustering", "description": "主题聚类", "weight": 15},
            {"name": "video", "description": "生成视频", "weight": 15}
        ]
        
    async def process_project(self, project_id: int, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
        """处理整个项目的Pipeline流程"""
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
            project_dir = Path(METADATA_DIR) / f"project_{project_id}"
            project_dir.mkdir(parents=True, exist_ok=True)
            
            # 初始化处理器
            self._initialize_processors(project_dir)
            
            # 执行6个步骤
            results = {}
            total_progress = 0
            
            for i, step in enumerate(self.steps):
                step_name = step["name"]
                step_description = step["description"]
                step_weight = step["weight"]
                
                logger.info(f"开始执行步骤 {i+1}/6: {step_description}")
                
                # 更新进度
                await self._update_progress(project_id, total_progress, f"正在{step_description}...")
                
                try:
                    # 执行具体步骤
                    if step_name == "outline":
                        results[step_name] = await self._step1_outline(input_srt_path, project_dir)
                    elif step_name == "timeline":
                        results[step_name] = await self._step2_timeline(results["outline"], project_dir)
                    elif step_name == "scoring":
                        results[step_name] = await self._step3_scoring(results["timeline"], project_dir)
                    elif step_name == "title":
                        results[step_name] = await self._step4_title(results["scoring"], project_dir)
                    elif step_name == "clustering":
                        results[step_name] = await self._step5_clustering(results["title"], project_dir)
                    elif step_name == "video":
                        results[step_name] = await self._step6_video(results["clustering"], input_video_path, project_dir)
                    
                    total_progress += step_weight
                    await self._update_progress(project_id, total_progress, f"{step_description}完成", results[step_name])
                
                except Exception as e:
                    logger.error(f"步骤 {step_name} 执行失败: {str(e)}")
                    await self._update_progress(project_id, total_progress, f"{step_description}失败: {str(e)}")
                    raise
            
            # 更新项目状态为完成
            project.status = ProjectStatus.COMPLETED
            project.completed_at = datetime.utcnow()
            project.result_data = results
            self.db.commit()
            
            await self._update_progress(project_id, 100, "项目处理完成")
            
            logger.info(f"项目 {project_id} 处理完成")
            return results
            
        except Exception as e:
            # 更新项目状态为失败
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.status = ProjectStatus.FAILED
                project.error_message = str(e)
                self.db.commit()
            
            await self._update_progress(project_id, -1, f"处理失败: {str(e)}")
            logger.error(f"项目 {project_id} 处理失败: {str(e)}")
            raise
    
    def _initialize_processors(self, project_dir: Path):
        """初始化各个处理器"""
        self.outline_extractor = OutlineExtractor(metadata_dir=project_dir, prompt_files=PROMPT_FILES)
        self.timeline_extractor = TimelineExtractor(metadata_dir=project_dir, prompt_files=PROMPT_FILES)
        self.clip_scorer = ClipScorer(prompt_files=PROMPT_FILES)
        self.title_generator = TitleGenerator(prompt_files=PROMPT_FILES)
        self.clustering_engine = ClusteringEngine(prompt_files=PROMPT_FILES)
        self.video_generator = VideoGenerator(metadata_dir=str(project_dir))
    
    async def _step1_outline(self, srt_path: str, project_dir: Path) -> List[Dict]:
        """步骤1: 提取视频大纲"""
        srt_file = Path(srt_path)
        if not srt_file.exists():
            raise FileNotFoundError(f"SRT文件不存在: {srt_path}")
        
        # 在线程池中执行CPU密集型任务
        loop = asyncio.get_event_loop()
        outlines = await loop.run_in_executor(
            None, 
            self.outline_extractor.extract_outline, 
            srt_file
        )
        
        # 保存结果
        output_path = project_dir / "step1_outline.json"
        self.outline_extractor.save_outline(outlines, output_path)
        
        return outlines
    
    async def _step2_timeline(self, outlines: List[Dict], project_dir: Path) -> List[Dict]:
        """步骤2: 生成时间线"""
        # 加载SRT块数据
        srt_chunks_dir = project_dir / "step1_srt_chunks"
        if not srt_chunks_dir.exists():
            raise FileNotFoundError(f"SRT块目录不存在: {srt_chunks_dir}")
        
        loop = asyncio.get_event_loop()
        timeline_data = await loop.run_in_executor(
            None,
            self.timeline_extractor.extract_timeline,
            outlines
        )
        
        # 保存结果
        output_path = project_dir / "step2_timeline.json"
        self.timeline_extractor.save_timeline(timeline_data, output_path)
        
        return timeline_data
    
    async def _step3_scoring(self, timeline_data: List[Dict], project_dir: Path) -> List[Dict]:
        """步骤3: 内容评分"""
        loop = asyncio.get_event_loop()
        scored_clips = await loop.run_in_executor(
            None,
            self.clip_scorer.score_clips,
            timeline_data
        )
        
        # 保存结果
        output_path = project_dir / "step3_scored_clips.json"
        self.clip_scorer.save_scores(scored_clips, output_path)
        
        return scored_clips
    
    async def _step4_title(self, scored_clips: List[Dict], project_dir: Path) -> List[Dict]:
        """步骤4: 生成标题"""
        loop = asyncio.get_event_loop()
        clips_with_titles = await loop.run_in_executor(
            None,
            self.title_generator.generate_titles,
            scored_clips
        )
        
        # 保存结果
        output_path = project_dir / "step4_titles.json"
        self.title_generator.save_titles(clips_with_titles, output_path)
        
        return clips_with_titles
    
    async def _step5_clustering(self, clips_with_titles: List[Dict], project_dir: Path) -> List[Dict]:
        """步骤5: 主题聚类"""
        loop = asyncio.get_event_loop()
        collections = await loop.run_in_executor(
            None,
            self.clustering_engine.create_collections,
            clips_with_titles
        )
        
        # 保存结果
        output_path = project_dir / "step5_collections.json"
        self.clustering_engine.save_collections(collections, output_path)
        
        return collections
    
    async def _step6_video(self, collections: List[Dict], input_video_path: str, project_dir: Path) -> Dict:
        """步骤6: 生成视频"""
        # 从collections中提取clips_with_titles
        clips_with_titles = []
        for collection in collections:
            clips_with_titles.extend(collection.get('clips', []))
        
        input_video = Path(input_video_path)
        if not input_video.exists():
            raise FileNotFoundError(f"输入视频不存在: {input_video_path}")
        
        loop = asyncio.get_event_loop()
        
        # 生成切片视频
        successful_clips = await loop.run_in_executor(
            None,
            self.video_generator.generate_clips,
            clips_with_titles,
            input_video
        )
        
        # 生成合集视频
        successful_collections = await loop.run_in_executor(
            None,
            self.video_generator.generate_collections,
            collections
        )
        
        # 保存元数据
        self.video_generator.save_clip_metadata(clips_with_titles)
        self.video_generator.save_collection_metadata(collections)
        
        result = {
            'clips_generated': len(successful_clips),
            'collections_generated': len(successful_collections),
            'clip_paths': [str(path) for path in successful_clips],
            'collection_paths': [str(path) for path in successful_collections]
        }
        
        # 保存结果
        output_path = project_dir / "step6_video_result.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        return result
    
    async def _update_progress(self, project_id: int, progress: int, message: str, step_result: Optional[Dict[str, Any]] = None):
        """更新项目进度"""
        try:
            # 更新数据库中的项目进度
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.progress = progress
                project.current_step = message
                self.db.commit()
            
            # 使用进度管理器更新进度
            if self.progress_manager and self.task_id:
                await self.progress_manager.update_task_progress(
                    task_id=self.task_id,
                    current_step=progress // 17 + 1,  # 估算当前步骤
                    total_steps=6,
                    step_name=message,
                    progress=progress,
                    message=message,
                    step_result=step_result
                )
            
            # 调用进度回调函数（用于WebSocket推送）
            if self.progress_callback:
                await self.progress_callback(project_id, progress, message)
                
        except Exception as e:
            logger.error(f"更新进度失败: {str(e)}")
    
    def get_project_status(self, project_id: int) -> Dict[str, Any]:
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