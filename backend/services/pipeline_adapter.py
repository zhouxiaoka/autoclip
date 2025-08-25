"""Pipeline适配器服务 - 将backend/pipeline中的处理逻辑集成到新架构"""

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

# 导入backend/pipeline中的处理步骤
try:
    # 添加backend目录到Python路径
    import sys
    backend_path = Path(__file__).parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    
    from pipeline.step1_outline import OutlineExtractor
    from pipeline.step2_timeline import TimelineExtractor
    from pipeline.step3_scoring import ClipScorer
    from pipeline.step4_title import TitleGenerator
    from pipeline.step5_clustering import ClusteringEngine
    from pipeline.step6_video import VideoGenerator
    logger.info("流水线模块导入成功")
except ImportError as e:
    logger.warning(f"无法导入流水线模块: {e}")
    # 定义占位符函数
    def run_step1_outline(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step2_timeline(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step3_scoring(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step4_title(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step5_clustering(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        return {"status": "skipped", "message": "流水线模块未正确导入"}
    
    def run_step6_video(**kwargs): 
        logger.warning("流水线模块未正确导入，使用占位符函数")
        return {"status": "skipped", "message": "流水线模块未正确导入"}

class PipelineAdapter:
    """Pipeline适配器，将backend/pipeline中的处理逻辑集成到新架构"""
    
    def __init__(self, db: Session, task_id: Optional[str] = None, project_id: Optional[str] = None):
        self.db = db
        self.task_id = task_id
        self.project_id = project_id
        self.progress_manager = get_progress_manager(db)
        
        # 获取项目根目录和输出目录
        self.project_root = get_project_root()
        self.data_dir = get_data_directory()
        self.output_dir = get_output_directory()
        
        # 初始化存储服务
        if project_id:
            from .storage_service import StorageService
            self.storage_service = StorageService(project_id)
        else:
            self.storage_service = None
        
        logger.info(f"Pipeline适配器初始化完成: project_root={self.project_root}, data_dir={self.data_dir}, output_dir={self.output_dir}")
    
    def process_project_sync(self, project_id: str, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
        """
        同步处理项目 - 执行完整的6步处理流程
        
        Args:
            project_id: 项目ID
            input_video_path: 输入视频路径
            input_srt_path: 输入SRT路径
            
        Returns:
            处理结果
        """
        logger.info(f"开始处理项目: {project_id}")
        
        try:
            # 更新项目状态为处理中
            self._update_project_status(project_id, ProjectStatus.PROCESSING)
            
            # 准备项目目录
            project_dir = self.data_dir / "projects" / project_id
            project_dir.mkdir(parents=True, exist_ok=True)
            
            # 准备输出目录
            output_dir = self.output_dir / "metadata" / f"step1_chunks"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 步骤1: 大纲提取
            logger.info("开始步骤1: 大纲提取")
            self._update_progress(project_id, 16, "大纲提取")
            step1_result = self._run_step1_outline(project_id, input_srt_path, project_dir)
            
            # 步骤2: 时间定位
            logger.info("开始步骤2: 时间定位")
            self._update_progress(project_id, 33, "时间定位")
            step2_result = self._run_step2_timeline(project_id, project_dir)
            
            # 步骤3: 内容评分
            logger.info("开始步骤3: 内容评分")
            self._update_progress(project_id, 50, "内容评分")
            step3_result = self._run_step3_scoring(project_id, project_dir)
            
            # 步骤4: 标题生成
            logger.info("开始步骤4: 标题生成")
            self._update_progress(project_id, 66, "标题生成")
            step4_result = self._run_step4_title(project_id, project_dir)
            
            # 步骤5: 主题聚类
            logger.info("开始步骤5: 主题聚类")
            self._update_progress(project_id, 83, "主题聚类")
            step5_result = self._run_step5_clustering(project_id, project_dir)
            
            # 步骤6: 视频切割
            logger.info("开始步骤6: 视频切割")
            self._update_progress(project_id, 100, "视频切割")
            step6_result = self._run_step6_video(project_id, input_video_path, project_dir)
            
            # 检查所有步骤的结果
            all_steps = [step1_result, step2_result, step3_result, step4_result, step5_result, step6_result]
            failed_steps = [step for step in all_steps if step.get('status') == 'failed']
            skipped_steps = [step for step in all_steps if step.get('status') == 'skipped']
            
            # 如果有失败的步骤，整个项目失败
            if failed_steps:
                self._update_project_status(project_id, ProjectStatus.FAILED)
                result = {
                    "project_id": project_id,
                    "status": "failed",
                    "steps": {
                        "step1": step1_result,
                        "step2": step2_result,
                        "step3": step3_result,
                        "step4": step4_result,
                        "step5": step5_result,
                        "step6": step6_result
                    },
                    "message": f"项目处理失败: {len(failed_steps)} 个步骤失败",
                    "failed_steps": [step.get('error', '未知错误') for step in failed_steps]
                }
            # 如果所有步骤都被跳过，也标记为失败
            elif len(skipped_steps) == len(all_steps):
                self._update_project_status(project_id, ProjectStatus.FAILED)
                result = {
                    "project_id": project_id,
                    "status": "failed",
                    "steps": {
                        "step1": step1_result,
                        "step2": step2_result,
                        "step3": step3_result,
                        "step4": step4_result,
                        "step5": step5_result,
                        "step6": step6_result
                    },
                    "message": "项目处理失败: 所有步骤都被跳过",
                    "failed_steps": ["所有处理步骤都被跳过，可能是配置问题或文件缺失"]
                }
            else:
                # 更新项目状态为完成
                self._update_project_status(project_id, ProjectStatus.COMPLETED)
                result = {
                    "project_id": project_id,
                    "status": "completed",
                    "steps": {
                        "step1": step1_result,
                        "step2": step2_result,
                        "step3": step3_result,
                        "step4": step4_result,
                        "step5": step5_result,
                        "step6": step6_result
                    },
                    "message": "项目处理完成"
                }
            
            logger.info(f"项目处理完成: {project_id}")
            return result
            
        except Exception as e:
            error_msg = f"项目处理失败: {str(e)}"
            logger.error(error_msg)
            
            # 更新项目状态为失败
            self._update_project_status(project_id, ProjectStatus.FAILED)
            
            raise Exception(error_msg)
    
    def _run_step1_outline(self, project_id: str, srt_path: str, project_dir: Path) -> Dict[str, Any]:
        """运行步骤1: 大纲提取"""
        try:
            output_dir = project_dir / "step1_outline"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 验证SRT文件路径
            srt_file_path = Path(srt_path) if srt_path and srt_path.strip() else None
            
            if not srt_file_path or not srt_file_path.exists():
                logger.warning(f"SRT文件不存在或路径无效: {srt_path}")
                return {"status": "failed", "error": "SRT文件不存在"}
            
            # 使用OutlineExtractor类
            try:
                extractor = OutlineExtractor()
                outlines = extractor.extract_outline(srt_file_path)
                
                # 保存结果
                with open(output_dir / "step1_outline.json", 'w', encoding='utf-8') as f:
                    json.dump(outlines, f, ensure_ascii=False, indent=2)
                
                logger.info(f"步骤1完成: 提取了 {len(outlines)} 个大纲项")
                return {"status": "completed", "outlines": outlines, "count": len(outlines)}
                
            except Exception as step_error:
                logger.error(f"大纲提取失败: {str(step_error)}")
                return {"status": "failed", "error": str(step_error)}
            
        except Exception as e:
            logger.error(f"步骤1失败: {str(e)}")
            return {"status": "failed", "error": str(e)}
    
    def _run_step2_timeline(self, project_id: str, project_dir: Path) -> Dict[str, Any]:
        """运行步骤2: 时间定位"""
        try:
            step1_output = project_dir / "step1_outline" / "step1_outline.json"
            output_dir = project_dir / "step2_timeline"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 检查步骤1的输出
            if not step1_output.exists():
                logger.warning("步骤1输出文件不存在，跳过步骤2")
                return {"status": "skipped", "message": "步骤1输出文件不存在"}
            
            # 使用TimelineExtractor类
            try:
                extractor = TimelineExtractor()
                with open(step1_output, 'r', encoding='utf-8') as f:
                    outlines = json.load(f)
                
                timeline_data = extractor.extract_timeline(outlines)
                
                # 保存结果
                with open(output_dir / "step2_timeline.json", 'w', encoding='utf-8') as f:
                    json.dump(timeline_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"步骤2完成: 提取了 {len(timeline_data)} 个时间点")
                return {"status": "completed", "timeline": timeline_data, "count": len(timeline_data)}
                
            except Exception as step_error:
                logger.error(f"时间定位失败: {str(step_error)}")
                return {"status": "failed", "error": str(step_error)}
            
        except Exception as e:
            logger.error(f"步骤2失败: {str(e)}")
            return {"status": "failed", "error": str(e)}
    
    def _run_step3_scoring(self, project_id: str, project_dir: Path) -> Dict[str, Any]:
        """运行步骤3: 内容评分"""
        try:
            step2_output = project_dir / "step2_timeline" / "step2_timeline.json"
            output_dir = project_dir / "step3_scoring"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 检查步骤2的输出
            if not step2_output.exists():
                logger.warning("步骤2输出文件不存在，跳过步骤3")
                return {"status": "skipped", "message": "步骤2输出文件不存在"}
            
            # 使用ClipScorer类
            try:
                scorer = ClipScorer()
                with open(step2_output, 'r', encoding='utf-8') as f:
                    timeline_data = json.load(f)
                
                scored_data = scorer.score_clips(timeline_data)
                
                # 保存结果
                with open(output_dir / "step3_scoring.json", 'w', encoding='utf-8') as f:
                    json.dump(scored_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"步骤3完成: 评分了 {len(scored_data)} 个片段")
                return {"status": "completed", "scored": scored_data, "count": len(scored_data)}
                
            except Exception as step_error:
                logger.error(f"内容评分失败: {str(step_error)}")
                return {"status": "failed", "error": str(step_error)}
            
        except Exception as e:
            logger.error(f"步骤3失败: {str(e)}")
            return {"status": "failed", "error": str(e)}
    
    def _run_step4_title(self, project_id: str, project_dir: Path) -> Dict[str, Any]:
        """运行步骤4: 标题生成"""
        try:
            step3_output = project_dir / "step3_scoring" / "step3_scoring.json"
            output_dir = project_dir / "step4_title"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 检查步骤3的输出
            if not step3_output.exists():
                logger.warning("步骤3输出文件不存在，跳过步骤4")
                return {"status": "skipped", "message": "步骤3输出文件不存在"}
            
            # 使用TitleGenerator类
            try:
                generator = TitleGenerator()
                with open(step3_output, 'r', encoding='utf-8') as f:
                    scored_data = json.load(f)
                
                titled_data = generator.generate_titles(scored_data)
                
                # 保存结果
                with open(output_dir / "step4_title.json", 'w', encoding='utf-8') as f:
                    json.dump(titled_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"步骤4完成: 生成了 {len(titled_data)} 个标题")
                return {"status": "completed", "titled": titled_data, "count": len(titled_data)}
                
            except Exception as step_error:
                logger.error(f"标题生成失败: {str(step_error)}")
                return {"status": "failed", "error": str(step_error)}
            
        except Exception as e:
            logger.error(f"步骤4失败: {str(e)}")
            return {"status": "failed", "error": str(e)}
    
    def _run_step5_clustering(self, project_id: str, project_dir: Path) -> Dict[str, Any]:
        """运行步骤5: 主题聚类"""
        try:
            step4_output = project_dir / "step4_title" / "step4_title.json"
            output_dir = project_dir / "step5_clustering"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 检查步骤4的输出
            if not step4_output.exists():
                logger.warning("步骤4输出文件不存在，跳过步骤5")
                return {"status": "skipped", "message": "步骤4输出文件不存在"}
            
            # 使用ClusteringEngine类
            try:
                clusterer = ClusteringEngine()
                with open(step4_output, 'r', encoding='utf-8') as f:
                    titled_data = json.load(f)
                
                clustered_data = clusterer.cluster_clips(titled_data)
                
                # 保存结果
                with open(output_dir / "step5_clustering.json", 'w', encoding='utf-8') as f:
                    json.dump(clustered_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"步骤5完成: 聚类了 {len(clustered_data)} 个合集")
                return {"status": "completed", "clustered": clustered_data, "count": len(clustered_data)}
                
            except Exception as step_error:
                logger.error(f"主题聚类失败: {str(step_error)}")
                return {"status": "failed", "error": str(step_error)}
            
        except Exception as e:
            logger.error(f"步骤5失败: {str(e)}")
            return {"status": "failed", "error": str(e)}
    
    def _run_step6_video(self, project_id: str, input_video_path: str, project_dir: Path) -> Dict[str, Any]:
        """运行步骤6: 视频切割"""
        try:
            step4_output = project_dir / "step4_title" / "step4_title.json"
            step5_output = project_dir / "step5_clustering" / "step5_clustering.json"
            output_dir = project_dir / "step6_video"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 准备视频输出目录
            clips_dir = self.output_dir / "clips"
            collections_dir = self.output_dir / "collections"
            clips_dir.mkdir(parents=True, exist_ok=True)
            collections_dir.mkdir(parents=True, exist_ok=True)
            
            # 检查输入文件
            if not Path(input_video_path).exists():
                logger.warning("输入视频文件不存在，跳过步骤6")
                return {"status": "skipped", "message": "输入视频文件不存在"}
            
            # 检查步骤4和5的输出
            if not step4_output.exists():
                logger.warning("步骤4输出文件不存在，跳过步骤6")
                return {"status": "skipped", "message": "步骤4输出文件不存在"}
            
            if not step5_output.exists():
                logger.warning("步骤5输出文件不存在，跳过步骤6")
                return {"status": "skipped", "message": "步骤5输出文件不存在"}
            
            # 使用VideoGenerator类
            try:
                processor = VideoGenerator()
                with open(step4_output, 'r', encoding='utf-8') as f:
                    clips_data = json.load(f)
                with open(step5_output, 'r', encoding='utf-8') as f:
                    collections_data = json.load(f)
                
                # 生成切片视频
                clips_paths = processor.generate_clips(clips_data, Path(input_video_path))
                
                # 生成合集视频
                collections_paths = processor.generate_collections(collections_data)
                
                # 保存元数据
                processor.save_clip_metadata(clips_data, output_dir / "clips_metadata.json")
                processor.save_collection_metadata(collections_data, output_dir / "collections_metadata.json")
                
                result = {
                    'clips_generated': len(clips_paths),
                    'collections_generated': len(collections_paths),
                    'clips_count': len(clips_data),
                    'collections_count': len(collections_data),
                    'clips_paths': [str(p) for p in clips_paths],
                    'collections_paths': [str(p) for p in collections_paths]
                }
                
                # 保存结果
                with open(output_dir / "step6_video_output.json", 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                # 将数据保存到数据库
                if result.get('clips_generated', 0) > 0:
                    self._save_clips_to_database(project_id, step4_output)
                
                if result.get('collections_generated', 0) > 0:
                    self._save_collections_to_database(project_id, step5_output)
                
                logger.info(f"步骤6完成: 生成了 {result.get('clips_count', 0)} 个片段和 {result.get('collections_count', 0)} 个合集")
                return {"status": "completed", "result": result}
                
            except Exception as step_error:
                logger.error(f"视频切割失败: {str(step_error)}")
                return {"status": "failed", "error": str(step_error)}
            
        except Exception as e:
            logger.error(f"步骤6失败: {str(e)}")
            return {"status": "failed", "error": str(e)}
    
    def _update_progress(self, project_id: str, progress: int, current_step: str):
        """更新处理进度"""
        if self.progress_manager and self.task_id:
            # 使用正确的方法名和参数
            import asyncio
            try:
                # 计算当前步骤
                step_mapping = {
                    "大纲提取": 1,
                    "时间定位": 2,
                    "内容评分": 3,
                    "标题生成": 4,
                    "主题聚类": 5,
                    "视频切割": 6
                }
                current_step_num = step_mapping.get(current_step, 1)
                
                # 创建事件循环并运行异步方法
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    self.progress_manager.update_task_progress(
                        task_id=self.task_id,  # 不转换为int，保持UUID字符串
                        current_step=current_step_num,
                        total_steps=6,
                        step_name=current_step,
                        progress=progress
                    )
                )
                loop.close()
            except Exception as e:
                logger.warning(f"更新进度失败: {e}")
        
        # 直接更新数据库中的任务
        if self.task_id:
            task = self.db.query(Task).filter(Task.id == self.task_id).first()
            if task:
                task.progress = progress
                task.current_step = current_step
                self.db.commit()
    
    def _update_project_status(self, project_id: str, status: ProjectStatus):
        """更新项目状态"""
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if project:
            project.status = status
            if status == ProjectStatus.COMPLETED:
                project.completed_at = datetime.now()
            self.db.commit()
    
    def _save_clips_to_database(self, project_id: str, clips_file: Path):
        """将切片数据保存到数据库（分离存储模式）"""
        try:
            import json
            from models.clip import Clip
            from datetime import datetime
            import uuid
            
            # 确保存储服务可用
            if not self.storage_service:
                self.storage_service = StorageService(project_id)
            
            # 读取切片数据
            with open(clips_file, 'r', encoding='utf-8') as f:
                clips_data = json.load(f)
            
            # 保存到数据库（只保存元数据）
            for clip_data in clips_data:
                # 转换时间格式
                start_time = self._convert_time_to_seconds(clip_data['start_time'])
                end_time = self._convert_time_to_seconds(clip_data['end_time'])
                duration = end_time - start_time
                
                # 生成切片ID
                clip_id = str(uuid.uuid4())
                
                # 保存切片文件到文件系统
                video_path = self.storage_service.save_clip_file(clip_data, clip_id)
                
                # 保存完整数据到文件系统
                metadata_path = self.storage_service.save_metadata(clip_data, f"clip_{clip_id}")
                
                # 创建切片记录（只保存元数据和路径引用）
                clip = Clip(
                    id=clip_id,
                    project_id=project_id,
                    title=clip_data.get('generated_title', clip_data.get('outline', '')),
                    description=clip_data.get('recommend_reason', ''),
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration,
                    score=clip_data.get('final_score', 0.0),
                    video_path=video_path,  # 只存储路径引用
                    clip_metadata={
                        'metadata_file': metadata_path,  # 完整数据文件路径
                        'clip_id': clip_id,
                        'created_at': datetime.now().isoformat(),
                        # 添加完整的元数据字段
                        'recommend_reason': clip_data.get('recommend_reason', ''),
                        'outline': clip_data.get('outline', ''),
                        'content': clip_data.get('content', []),
                        'chunk_index': clip_data.get('chunk_index', 0),
                        'generated_title': clip_data.get('generated_title', '')
                    },
                    status='completed'
                )
                
                self.db.add(clip)
            
            self.db.commit()
            logger.info(f"成功保存 {len(clips_data)} 个切片（分离存储模式）")
            
        except Exception as e:
            logger.error(f"保存切片到数据库失败: {str(e)}")
            self.db.rollback()
    
    def _save_collections_to_database(self, project_id: str, collections_file: Path):
        """将合集数据保存到数据库（分离存储模式）"""
        try:
            import json
            from models.collection import Collection
            from datetime import datetime
            import uuid
            
            # 确保存储服务可用
            if not self.storage_service:
                self.storage_service = StorageService(project_id)
            
            # 读取合集数据
            with open(collections_file, 'r', encoding='utf-8') as f:
                collections_data = json.load(f)
            
            # 保存到数据库（只保存元数据）
            for collection_data in collections_data:
                # 生成合集ID
                collection_id = str(uuid.uuid4())
                
                # 保存合集文件到文件系统
                export_path = self.storage_service.save_collection_file(collection_data, collection_id)
                
                # 保存完整数据到文件系统
                metadata_path = self.storage_service.save_metadata(collection_data, f"collection_{collection_id}")
                
                # 创建合集记录（只保存元数据和路径引用）
                collection = Collection(
                    id=collection_id,
                    project_id=project_id,
                    name=collection_data.get('collection_title', ''),
                    description=collection_data.get('collection_summary', ''),
                    export_path=str(self.output_dir / "collections" / f"{collection_data.get('collection_title', '')}.mp4"),  # 使用正确的路径
                    collection_metadata={
                        'metadata_file': metadata_path,  # 完整数据文件路径
                        'clip_ids': collection_data.get('clip_ids', []),
                        'collection_type': 'ai_recommended',
                        'collection_id': collection_id,
                        'created_at': datetime.now().isoformat(),
                        # 添加完整的元数据字段
                        'collection_title': collection_data.get('collection_title', ''),
                        'collection_summary': collection_data.get('collection_summary', '')
                    }
                )
                
                self.db.add(collection)
            
            self.db.commit()
            logger.info(f"成功保存 {len(collections_data)} 个合集（分离存储模式）")
            
        except Exception as e:
            logger.error(f"保存合集到数据库失败: {str(e)}")
            self.db.rollback()
    
    def _convert_time_to_seconds(self, time_str: str) -> int:
        """将时间字符串转换为秒数"""
        try:
            # 处理格式 "00:00:00,120" 或 "00:00:00.120"
            time_str = time_str.replace(',', '.')
            parts = time_str.split(':')
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds_parts = parts[2].split('.')
            seconds = int(seconds_parts[0])
            milliseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0
            
            total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000
            return int(total_seconds)
        except Exception as e:
            logger.error(f"时间转换失败: {time_str}, 错误: {e}")
            return 0

    # 为ProcessingOrchestrator添加适配器方法
    def adapt_step1_outline(self, srt_path: str) -> Dict[str, Any]:
        """适配步骤1参数"""
        project_dir = self.data_dir / "projects" / self.project_id
        output_dir = project_dir / "step1_outline"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        return {
            "srt_path": Path(srt_path),
            "metadata_dir": project_dir,
            "output_path": output_dir / "step1_outline.json"
        }
    
    def adapt_step2_timeline(self) -> Dict[str, Any]:
        """适配步骤2参数"""
        project_dir = self.data_dir / "projects" / self.project_id
        step1_output = project_dir / "step1_outline" / "step1_outline.json"
        output_dir = project_dir / "step2_timeline"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        return {
            "outline_path": step1_output,
            "output_path": output_dir / "step2_timeline.json",
            "metadata_dir": project_dir
        }
    
    def adapt_step3_scoring(self) -> Dict[str, Any]:
        """适配步骤3参数"""
        project_dir = self.data_dir / "projects" / self.project_id
        step2_output = project_dir / "step2_timeline" / "step2_timeline.json"
        output_dir = project_dir / "step3_scoring"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        return {
            "timeline_path": step2_output,
            "output_path": output_dir / "step3_scoring.json",
            "metadata_dir": project_dir
        }
    
    def adapt_step4_title(self) -> Dict[str, Any]:
        """适配步骤4参数"""
        project_dir = self.data_dir / "projects" / self.project_id
        step3_output = project_dir / "step3_scoring" / "step3_scoring.json"
        output_dir = project_dir / "step4_title"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        return {
            "high_score_clips_path": step3_output,
            "output_path": output_dir / "step4_title.json",
            "metadata_dir": project_dir
        }
    
    def adapt_step5_clustering(self) -> Dict[str, Any]:
        """适配步骤5参数"""
        project_dir = self.data_dir / "projects" / self.project_id
        step4_output = project_dir / "step4_title" / "step4_title.json"
        output_dir = project_dir / "step5_clustering"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        return {
            "clips_with_titles_path": step4_output,
            "output_path": output_dir / "step5_clustering.json",
            "metadata_dir": project_dir
        }
    
    def adapt_step6_video(self) -> Dict[str, Any]:
        """适配步骤6参数"""
        project_dir = self.data_dir / "projects" / self.project_id
        step5_output = project_dir / "step5_clustering" / "step5_clustering.json"
        step4_output = project_dir / "step4_title" / "step4_title.json"
        output_dir = project_dir / "step6_video"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 准备视频输出目录
        clips_dir = self.output_dir / "clips"
        collections_dir = self.output_dir / "collections"
        clips_dir.mkdir(parents=True, exist_ok=True)
        collections_dir.mkdir(parents=True, exist_ok=True)
        
        return {
            "clips_with_titles_path": step4_output,
            "collections_path": step5_output,
            "input_video": project_dir / "raw" / "input.mp4",
            "output_dir": output_dir,
            "clips_dir": str(clips_dir),
            "collections_dir": str(collections_dir),
            "metadata_dir": str(project_dir)
        }
    
    def prepare_step_environment(self, step_name: str):
        """准备步骤执行环境"""
        logger.info(f"准备步骤环境: {step_name}")
        # 这里可以添加步骤特定的环境准备逻辑
        pass

    def validate_pipeline_prerequisites(self) -> List[str]:
        """
        验证流水线前置条件
        
        Returns:
            错误信息列表，空列表表示验证通过
        """
        errors = []
        
        try:
            # 检查项目目录是否存在
            if not hasattr(self, 'project_id') or not self.project_id:
                errors.append("项目ID未设置")
                return errors
            
            # 检查项目目录结构
            project_dir = self.data_dir / "projects" / self.project_id
            if not project_dir.exists():
                errors.append(f"项目目录不存在: {project_dir}")
            
            # 检查raw目录
            raw_dir = project_dir / "raw"
            if not raw_dir.exists():
                errors.append(f"项目raw目录不存在: {raw_dir}")
            
            # 检查视频文件
            video_files = list(raw_dir.glob("*.mp4")) if raw_dir.exists() else []
            if not video_files:
                errors.append("未找到视频文件(.mp4)")
            
            # 检查字幕文件
            srt_files = list(raw_dir.glob("*.srt")) if raw_dir.exists() else []
            if not srt_files:
                errors.append("未找到字幕文件(.srt)")
            
            # 检查输出目录权限
            output_dir = self.output_dir
            if not output_dir.exists():
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors.append(f"无法创建输出目录: {e}")
            
            # 检查API密钥配置
            import os
            import json
            
            # 首先检查环境变量
            api_key = os.getenv('DASHSCOPE_API_KEY') or os.getenv('OPENAI_API_KEY')
            
            # 如果环境变量中没有，尝试从配置文件读取
            if not api_key:
                try:
                    settings_path = self.data_dir / "settings.json"
                    if settings_path.exists():
                        with open(settings_path, 'r', encoding='utf-8') as f:
                            settings = json.load(f)
                            api_key = settings.get('dashscope_api_key') or settings.get('openai_api_key')
                except Exception as e:
                    logger.warning(f"读取配置文件失败: {e}")
            
            if not api_key:
                errors.append("未配置API密钥(DASHSCOPE_API_KEY或OPENAI_API_KEY)")
            
            logger.info(f"流水线前置条件验证完成，发现 {len(errors)} 个错误")
            return errors
            
        except Exception as e:
            logger.error(f"验证流水线前置条件时发生错误: {e}")
            errors.append(f"验证过程发生错误: {e}")
            return errors

def create_pipeline_adapter_sync(db: Session, task_id: Optional[str] = None, project_id: Optional[str] = None) -> PipelineAdapter:
    """创建同步Pipeline适配器"""
    return PipelineAdapter(db, task_id, project_id)