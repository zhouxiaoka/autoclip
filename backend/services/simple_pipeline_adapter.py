"""
简化的流水线适配器 - 集成新的进度系统
"""

import logging
import os
from typing import Dict, Any, Optional, Callable
from pathlib import Path

from backend.services.simple_progress import emit_progress, clear_progress
from backend.pipeline.failures import (
    PipelineFailure, HINT_CHECK_LLM, HINT_SUBTITLE, HINT_LOWER_THRESHOLD, HINT_CHECK_FFMPEG,
)
from backend.pipeline.step1_outline import run_step1_outline
from backend.pipeline.step2_timeline import run_step2_timeline
from backend.pipeline.step3_scoring import run_step3_scoring
from backend.pipeline.step4_title import run_step4_title
from backend.pipeline.step5_clustering import run_step5_clustering
from backend.pipeline.step6_video import run_step6_video

logger = logging.getLogger(__name__)


class SimplePipelineAdapter:
    """简化的流水线适配器，使用固定阶段进度系统"""
    
    def __init__(self, project_id: str, task_id: str):
        self.project_id = project_id
        self.task_id = task_id

    def _prompt_files(self, project_dir: Path):
        """按项目类型选 prompt/<category>/，桌面端以前从没传过，类别目录形同虚设。"""
        from backend.core.shared_config import get_prompt_files
        import json

        category = "default"
        meta_path = project_dir / "project.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                category = meta.get("video_category") or "default"
            except Exception:  # noqa: BLE001
                pass
        if category == "default":
            try:
                from backend.core.database import SessionLocal
                from backend.models.project import Project
                db = SessionLocal()
                try:
                    row = db.query(Project).filter(Project.id == self.project_id).first()
                    if row is not None and row.project_type is not None:
                        category = row.project_type.value if hasattr(row.project_type, "value") else str(row.project_type)
                finally:
                    db.close()
            except Exception:  # noqa: BLE001
                pass
        logger.info(f"使用类别提示词: {category}")
        return get_prompt_files(category)
        
    async def _generate_subtitle_automatically(self, video_path: str, metadata_dir: Path) -> Path:
        """
        自动生成字幕文件
        
        Args:
            video_path: 视频文件路径
            metadata_dir: 元数据目录
            
        Returns:
            生成的SRT文件路径，如果失败返回None
        """
        try:
            logger.info(f"开始为视频 {video_path} 自动生成字幕")
            
            # 更新进度
            from backend.services.simple_progress import emit_progress
            emit_progress(self.project_id, "SUBTITLE", "正在使用AI生成字幕...", subpercent=25)
            
            # 使用Whisper本地模型生成字幕
            try:
                from backend.utils.speech_recognizer import generate_subtitle_for_video
                from pathlib import Path
                
                video_file_path = Path(video_path)
                if not video_file_path.exists():
                    logger.error(f"视频文件不存在: {video_path}")
                    return None
                
                logger.info("尝试使用Whisper本地模型生成字幕")
                output_path = metadata_dir / f"{video_file_path.stem}.srt"
                srt_path = generate_subtitle_for_video(
                    video_file_path,
                    output_path=output_path,
                    method="whisper_local",
                    model="base",
                    language="auto"
                )
                
                if srt_path and srt_path.exists():
                    logger.info(f"Whisper生成字幕成功: {srt_path}")
                    emit_progress(self.project_id, "SUBTITLE", "AI字幕生成完成", subpercent=40)
                    return srt_path
                else:
                    logger.warning("Whisper生成字幕失败")
                    
            except Exception as e:
                logger.warning(f"Whisper生成字幕失败: {e}")
            
            logger.error("Whisper字幕生成失败")
            return None
            
        except Exception as e:
            logger.error(f"自动生成字幕过程中发生错误: {e}")
            return None
        
    @staticmethod
    def _preflight_llm() -> None:
        """跑任何 LLM 步骤之前先确认提供商可用；否则 step1 会把每个块都报错然后交一个空大纲出去。
        AUTOCLIP_LLM_CACHE_DIR 回放模式下不需要真实提供商（backend/eval）。"""
        if os.getenv("AUTOCLIP_LLM_CACHE_DIR"):
            return
        from backend.core.llm_manager import get_llm_manager
        info = get_llm_manager().get_current_provider_info()
        if info.get("available"):
            return
        name = info.get("display_name") or info.get("provider") or "未选择"
        model = info.get("model") or "-"
        raise PipelineFailure(
            "ANALYZE",
            f"没有可用的 LLM 提供商（当前选择：{name} · {model}），缺少 API Key 或本地服务地址。",
            HINT_CHECK_LLM,
        )

    async def process_project_sync(self, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
        """
        同步处理项目 - 使用简化的进度系统
        
        Args:
            input_video_path: 输入视频路径
            input_srt_path: 输入SRT路径
            
        Returns:
            处理结果
        """
        logger.info(f"开始处理项目: {self.project_id}")
        
        try:
            # 清除之前的进度数据
            clear_progress(self.project_id)
            
            # 创建必要的目录结构 - 使用正确的路径
            from backend.core.path_utils import get_project_directory
            project_dir = get_project_directory(self.project_id)
            metadata_dir = project_dir / "metadata"
            output_dir = project_dir / "output"
            metadata_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)
            # 项目内专属输出子目录
            clips_output_dir = output_dir / "clips"
            collections_output_dir = output_dir / "collections"
            clips_output_dir.mkdir(parents=True, exist_ok=True)
            collections_output_dir.mkdir(parents=True, exist_ok=True)
            prompt_files = self._prompt_files(project_dir)
            
            # 阶段1: 素材准备。先确认 LLM 可用，否则后面每一步都是白跑
            emit_progress(self.project_id, "INGEST", "素材准备完成")
            self._preflight_llm()
            
            # 阶段2: 字幕处理
            emit_progress(self.project_id, "SUBTITLE", "开始字幕处理")
            
            if input_srt_path and Path(input_srt_path).exists():
                logger.info(f"使用现有SRT文件: {input_srt_path}")
                srt_path = Path(input_srt_path)
            else:
                logger.warning("没有SRT文件，尝试自动生成字幕")
                srt_path = await self._generate_subtitle_automatically(input_video_path, metadata_dir)
                if not (srt_path and srt_path.exists()):
                    # 以前这里写一个空大纲然后一路「成功」到底，用户看到的是 Completed · 0 切片
                    raise PipelineFailure(
                        "SUBTITLE",
                        "没有字幕可分析：视频不带字幕，且本地转写没有生成结果。",
                        HINT_SUBTITLE,
                    )
                logger.info(f"自动生成字幕成功: {srt_path}")

            # Step 1: 大纲提取（字幕为空 / 模型全部失败 / 无法解析时由 step1 自己抛 PipelineFailure）
            logger.info("执行Step 1: 大纲提取")
            outlines = run_step1_outline(srt_path, metadata_dir=metadata_dir, prompt_files=prompt_files)
            emit_progress(self.project_id, "SUBTITLE", "字幕处理完成", subpercent=50)
            
            # 阶段3: 内容分析
            emit_progress(self.project_id, "ANALYZE", "开始内容分析")
            
            # Step 2: 时间线提取
            logger.info("执行Step 2: 时间线提取")
            timeline_data = run_step2_timeline(
                metadata_dir / "step1_outline.json",
                metadata_dir=metadata_dir,
                prompt_files=prompt_files,
            )
            if not timeline_data:
                raise PipelineFailure(
                    "ANALYZE",
                    f"时间线提取为空：{len(outlines)} 个话题都没能对齐到字幕时间轴。",
                    HINT_CHECK_LLM,
                )
            emit_progress(self.project_id, "ANALYZE", "时间线提取完成", subpercent=50)
            
            # Step 3: 内容评分
            logger.info("执行Step 3: 内容评分")
            scored_clips = run_step3_scoring(
                metadata_dir / "step2_timeline.json",
                metadata_dir=metadata_dir,
                prompt_files=prompt_files,
            )
            if not scored_clips:
                from backend.pipeline.step3_scoring import resolve_min_score_threshold
                raise PipelineFailure(
                    "ANALYZE",
                    f"没有片段通过评分筛选（{len(timeline_data)} 个候选，阈值 {resolve_min_score_threshold()}）。",
                    HINT_LOWER_THRESHOLD,
                )
            emit_progress(self.project_id, "ANALYZE", "内容分析完成", subpercent=100)
            
            # 阶段4: 片段定位
            emit_progress(self.project_id, "HIGHLIGHT", "开始片段定位")
            
            # Step 4: 标题生成
            logger.info("执行Step 4: 标题生成")
            titled_clips = run_step4_title(
                metadata_dir / "step3_high_score_clips.json",
                metadata_dir=str(metadata_dir),
                prompt_files=prompt_files,
            )
            emit_progress(self.project_id, "HIGHLIGHT", "标题生成完成", subpercent=40)
            
            # Step 5: 主题聚类
            logger.info("执行Step 5: 主题聚类")
            collections = run_step5_clustering(
                metadata_dir / "step4_titles.json",
                metadata_dir=str(metadata_dir),
                prompt_files=prompt_files,
            )
            emit_progress(self.project_id, "HIGHLIGHT", "片段定位完成", subpercent=100)
            
            # 阶段5: 视频导出
            emit_progress(self.project_id, "EXPORT", "开始视频导出")
            
            # Step 6: 视频切割
            logger.info("执行Step 6: 视频切割")
            video_result = run_step6_video(
                metadata_dir / "step4_titles.json",
                metadata_dir / "step5_collections.json",
                input_video_path,
                output_dir=output_dir,
                clips_dir=str(clips_output_dir),
                collections_dir=str(collections_output_dir),
                metadata_dir=str(metadata_dir)
            )
            if titled_clips and not video_result.get("clips_generated"):
                raise PipelineFailure(
                    "EXPORT",
                    f"视频切割没有产出任何文件（{len(titled_clips)} 个片段待切）。",
                    HINT_CHECK_FFMPEG,
                )
            emit_progress(self.project_id, "EXPORT", "视频导出完成", subpercent=100)
            
            # 阶段6: 处理完成
            emit_progress(self.project_id, "DONE", "处理完成")
            
            # 自动同步数据到数据库
            try:
                from backend.services.data_sync_service import DataSyncService
                from backend.core.database import SessionLocal
                
                db = SessionLocal()
                try:
                    sync_service = DataSyncService(db)
                    sync_result = sync_service.sync_project_from_filesystem(self.project_id, project_dir)
                    if sync_result.get("success"):
                        logger.info(f"项目 {self.project_id} 数据同步成功: {sync_result}")
                    else:
                        logger.error(f"项目 {self.project_id} 数据同步失败: {sync_result}")
                finally:
                    db.close()
            except Exception as e:
                logger.error(f"数据同步失败: {e}")
            
            logger.info(f"项目处理完成: {self.project_id}")
            return {
                "status": "succeeded",
                "project_id": self.project_id,
                "task_id": self.task_id,
                "result": {
                    "outlines": outlines,
                    "timeline": timeline_data,
                    "scored_clips": scored_clips,
                    "titled_clips": titled_clips,
                    "collections": collections,
                    "video_result": video_result
                }
            }
            
        except PipelineFailure as e:
            # 明确失败：带阶段和下一步提示，前端失败态 / 应用内反馈直接展示
            error_msg = e.user_message()
            logger.error(f"流水线在 {e.stage} 阶段失败: {error_msg}")
            emit_progress(self.project_id, e.stage, f"处理失败：{error_msg}")
            return {
                "status": "failed",
                "project_id": self.project_id,
                "task_id": self.task_id,
                "stage": e.stage,
                "error": error_msg,
                "message": error_msg,
            }
        except Exception as e:
            error_msg = f"流水线处理失败: {str(e)}"
            logger.exception(error_msg)
            
            # 发送失败状态
            emit_progress(self.project_id, "DONE", f"处理失败: {error_msg}")
            
            return {
                "status": "failed",
                "project_id": self.project_id,
                "task_id": self.task_id,
                "error": error_msg,
                "message": error_msg,
            }


def create_simple_pipeline_adapter(project_id: str, task_id: str) -> SimplePipelineAdapter:
    """创建简化的流水线适配器实例"""
    return SimplePipelineAdapter(project_id, task_id)
