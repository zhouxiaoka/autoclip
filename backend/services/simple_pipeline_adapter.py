"""
简化的流水线适配器 - 集成新的进度系统
"""

import logging
from typing import Dict, Any, Optional, Callable
from pathlib import Path

from backend.services.simple_progress import emit_progress, clear_progress, compute_percent
from backend.pipeline.step1_outline import run_step1_outline
from backend.pipeline.step2_timeline import run_step2_timeline
from backend.pipeline.step3_scoring import run_step3_scoring
from backend.pipeline.step4_title import run_step4_title
from backend.pipeline.step5_clustering import run_step5_clustering
from backend.pipeline.step6_video import run_step6_video

logger = logging.getLogger(__name__)


class SimplePipelineAdapter:
    """简化的流水线适配器，使用固定阶段进度系统"""
    
    def __init__(
        self,
        project_id: str,
        task_id: str,
        progress_callback: Optional[Callable[[int, str, str], None]] = None
    ):
        self.project_id = project_id
        self.task_id = task_id
        self.progress_callback = progress_callback

    def _emit_progress(self, stage: str, message: str, subpercent: Optional[float] = None) -> None:
        """发送简化进度，并回写到任务进度（若提供回调）"""
        emit_progress(self.project_id, stage, message, subpercent=subpercent)
        if self.progress_callback:
            try:
                percent = compute_percent(stage, subpercent)
                self.progress_callback(percent, stage, message)
            except Exception as e:
                logger.warning(f"回调任务进度失败: {e}")
        
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
            self._emit_progress("SUBTITLE", "正在使用AI生成字幕...", subpercent=25)
            
            # 优先尝试阿里云百炼 ASR
            try:
                from backend.utils.speech_recognizer import generate_subtitle_for_video
                from pathlib import Path
                
                video_file_path = Path(video_path)
                if not video_file_path.exists():
                    logger.error(f"视频文件不存在: {video_path}")
                    return None
                
                # 使用阿里云百炼ASR生成字幕
                logger.info("尝试使用阿里云百炼ASR生成字幕")
                output_path = metadata_dir / f"{video_file_path.stem}.srt"
                srt_path = generate_subtitle_for_video(
                    video_file_path,
                    output_path=output_path,
                    method="aliyun_speech",
                    model="base",
                    language="auto"
                )
                
                if srt_path and srt_path.exists():
                    logger.info(f"阿里云百炼ASR生成字幕成功: {srt_path}")
                    self._emit_progress("SUBTITLE", "AI字幕生成完成", subpercent=40)
                    return srt_path
                else:
                    logger.warning("阿里云百炼ASR生成字幕失败")
                    
            except Exception as e:
                logger.warning(f"阿里云百炼ASR生成字幕失败: {e}")
            
            # 如果百炼ASR失败，尝试使用Whisper本地模型
            try:
                logger.info("尝试使用Whisper本地模型生成字幕")
                output_path = metadata_dir / f"{Path(video_path).stem}.srt"
                srt_path = generate_subtitle_for_video(
                    Path(video_path),
                    output_path=output_path,
                    method="whisper_local",
                    model="base",
                    language="auto"
                )
                
                if srt_path and srt_path.exists():
                    logger.info(f"Whisper生成字幕成功: {srt_path}")
                    self._emit_progress("SUBTITLE", "AI字幕生成完成", subpercent=40)
                    return srt_path
                else:
                    logger.warning("Whisper生成字幕失败")
                    
            except Exception as e:
                logger.warning(f"Whisper生成字幕失败: {e}")
            
            logger.error("所有ASR方法都失败了")
            return None
            
        except Exception as e:
            logger.error(f"自动生成字幕过程中发生错误: {e}")
            return None
        
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
            
            # 阶段1: 素材准备
            self._emit_progress("INGEST", "素材准备完成")
            
            # 阶段2: 字幕处理
            self._emit_progress("SUBTITLE", "开始字幕处理")
            
            # Step 1: 大纲提取
            logger.info("执行Step 1: 大纲提取")
            subtitle_source = "provided_srt"
            if input_srt_path and Path(input_srt_path).exists():
                logger.info(f"使用现有SRT文件: {input_srt_path}")
                outlines = run_step1_outline(
                    Path(input_srt_path),
                    metadata_dir=metadata_dir,
                    progress_callback=lambda done, total, msg: self._emit_progress(
                        "SUBTITLE",
                        msg,
                        subpercent=min(95, 50 + int((done / max(1, total)) * 45)),
                    ),
                )
            else:
                logger.warning("没有SRT文件，尝试自动生成字幕")
                subtitle_source = "auto_generated"
                # 尝试自动生成字幕
                srt_path = await self._generate_subtitle_automatically(input_video_path, metadata_dir)
                if srt_path and srt_path.exists():
                    logger.info(f"自动生成字幕成功: {srt_path}")
                    outlines = run_step1_outline(
                        srt_path,
                        metadata_dir=metadata_dir,
                        progress_callback=lambda done, total, msg: self._emit_progress(
                            "SUBTITLE",
                            msg,
                            subpercent=min(95, 50 + int((done / max(1, total)) * 45)),
                        ),
                    )
                else:
                    failure_msg = (
                        "字幕自动生成失败：阿里云百炼 ASR 与 Whisper 均未成功，无法继续自动剪辑。"
                        "请检查网络、ASR依赖（whisper/ffmpeg）与运行环境。"
                    )
                    logger.error(failure_msg)
                    emit_progress(self.project_id, "DONE", f"处理失败: {failure_msg}")
                    return {
                        "status": "failed",
                        "project_id": self.project_id,
                        "task_id": self.task_id,
                        "error": failure_msg,
                    }
            self._emit_progress("SUBTITLE", "字幕处理完成", subpercent=50)

            # 没有有效大纲时直接失败，避免“0 clips 也标记完成”的假成功
            if not outlines:
                failure_msg = (
                    "未从字幕中提取到有效大纲，自动剪辑已终止。"
                    "请检查字幕内容质量，或确认 LLM 配置/密钥可用。"
                )
                logger.error(f"{failure_msg} source={subtitle_source}")
                self._emit_progress("DONE", f"处理失败: {failure_msg}")
                return {
                    "status": "failed",
                    "project_id": self.project_id,
                    "task_id": self.task_id,
                    "error": failure_msg,
                    "result": {
                        "outlines": [],
                        "video_result": {"status": "failed", "message": failure_msg},
                    },
                }
            
            # 阶段3: 内容分析
            self._emit_progress("ANALYZE", "开始内容分析")
            
            # Step 2: 时间线提取
            logger.info("执行Step 2: 时间线提取")
            timeline_data = run_step2_timeline(
                metadata_dir / "step1_outline.json",
                metadata_dir=metadata_dir
            )
            self._emit_progress("ANALYZE", "时间线提取完成", subpercent=50)
            
            # Step 3: 内容评分
            logger.info("执行Step 3: 内容评分")
            scored_clips = run_step3_scoring(
                metadata_dir / "step2_timeline.json",
                metadata_dir=metadata_dir,
                progress_callback=lambda done, total, msg: self._emit_progress(
                    "ANALYZE",
                    msg,
                    subpercent=min(95, 50 + int((done / max(1, total)) * 45)),
                ),
            )
            self._emit_progress("ANALYZE", "内容分析完成", subpercent=100)
            
            # 阶段4: 片段定位
            self._emit_progress("HIGHLIGHT", "开始片段定位")
            
            # Step 4: 标题生成
            logger.info("执行Step 4: 标题生成")
            titled_clips = run_step4_title(
                metadata_dir / "step3_high_score_clips.json",
                metadata_dir=str(metadata_dir)
            )
            self._emit_progress("HIGHLIGHT", "标题生成完成", subpercent=40)
            
            # Step 5: 主题聚类
            logger.info("执行Step 5: 主题聚类")
            collections = run_step5_clustering(
                metadata_dir / "step4_titles.json",
                metadata_dir=str(metadata_dir)
            )
            self._emit_progress("HIGHLIGHT", "片段定位完成", subpercent=100)
            
            # 阶段5: 视频导出
            self._emit_progress("EXPORT", "开始视频导出")
            
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
            self._emit_progress("EXPORT", "视频导出完成", subpercent=100)
            
            # 阶段6: 处理完成
            self._emit_progress("DONE", "处理完成")
            
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
            
        except Exception as e:
            error_msg = f"流水线处理失败: {str(e)}"
            logger.error(error_msg)
            
            # 发送失败状态
            self._emit_progress("DONE", f"处理失败: {error_msg}")
            
            return {
                "status": "failed",
                "project_id": self.project_id,
                "task_id": self.task_id,
                "error": error_msg
            }


def create_simple_pipeline_adapter(
    project_id: str,
    task_id: str,
    progress_callback: Optional[Callable[[int, str, str], None]] = None
) -> SimplePipelineAdapter:
    """创建简化的流水线适配器实例"""
    return SimplePipelineAdapter(project_id, task_id, progress_callback=progress_callback)
