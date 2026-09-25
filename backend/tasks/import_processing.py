"""
本地导入处理任务
处理视频文件上传后的异步任务：字幕生成、缩略图生成、处理流程启动
"""

import logging
from pathlib import Path
from typing import NoReturn, Optional
from celery import Celery
from backend.core.database import session_scope
from backend.services.project_service import ProjectService
from backend.utils.thumbnail_generator import generate_project_thumbnail
from backend.utils.task_submission_utils import submit_video_pipeline_task

logger = logging.getLogger(__name__)

# 获取Celery应用实例
from backend.core.celery_app import celery_app


class ImportProcessingError(Exception):
    """导入任务失败。交给 Celery 记成带 exc_type 的 FAILURE，不要自己 update_state(FAILURE)。"""


def _record_import_failure(
    project_service,
    project_id: str,
    error: str,
    error_code: Optional[str] = None,
) -> None:
    """项目标失败，并把原因写进 project_metadata.last_error（详情页从这里读）。"""
    message = (error or "导入失败")[:2000]
    project_service.update_project_status(project_id, "failed")
    try:
        project = project_service.get(project_id)
        if project is None:
            return
        meta = dict(getattr(project, "project_metadata", None) or {})
        meta["last_error"] = message
        if error_code:
            meta["last_error_code"] = error_code
        project_service.update(project_id, project_metadata=meta)
    except Exception:
        logger.warning("写入导入失败原因失败: %s", project_id, exc_info=True)


def _fail_import(
    project_service,
    project_id: str,
    error: str,
    error_code: Optional[str] = None,
) -> NoReturn:
    """记录用户可见的失败原因，再抛出异常让结果后端保存 exc_type。

    手动把状态写成 FAILURE、meta 里只放 error 然后 return，结果后端没有 exc_type。
    worker 随后 mark_as_done / mark_as_failure 解码时会抛
    ValueError: Exception information must include the exception type。
    """
    _record_import_failure(project_service, project_id, error, error_code=error_code)
    raise ImportProcessingError(error)


def import_subtitle_failure(speech_error: Optional[str] = None):
    """导入关卡没有可用字幕时，沿用流水线同一套失败码和「设置 → 转写」提示。

    这只说明下一步该去哪，不表示 Whisper 一定能转写成功。
    """
    from backend.pipeline.failures import (
        HINT_SUBTITLE,
        PipelineFailure,
        failure_from_speech_error,
        missing_subtitle_failure,
    )

    try:
        if speech_error:
            return failure_from_speech_error(speech_error)
        return missing_subtitle_failure()
    except Exception:
        logger.warning("构造字幕失败说明失败", exc_info=True)
        return PipelineFailure(
            "SUBTITLE",
            "没有字幕可分析：视频不带字幕，这次也没有生成可用字幕。",
            HINT_SUBTITLE,
            code="subtitle_setup",
        )


def _generate_import_subtitle(task, project_id: str, video_path: str):
    """转写字幕。不持有数据库会话：Whisper 可能跑很久。返回 (srt_path, speech_error)。"""
    logger.info(f"开始为项目 {project_id} 生成字幕...")
    task.update_state(state='PROGRESS', meta={'progress': 40, 'message': '生成字幕...'})
    speech_error = None
    speech_config = None
    srt_path = None
    try:
        from backend.utils.speech_recognizer import generate_subtitle_for_video
        from backend.core.desktop_config import get_desktop_config

        config = get_desktop_config()
        speech_config = config.speech_recognition

        logger.info(f"使用语音转写配置 - 方法: {speech_config.method}")

        if speech_config.method == "whisper_local":
            model = speech_config.whisper_config.model_name
            language = speech_config.whisper_config.language
            enable_timestamps = speech_config.whisper_config.enable_timestamps
            enable_punctuation = speech_config.whisper_config.enable_punctuation
            enable_speaker_diarization = speech_config.whisper_config.enable_speaker_diarization
            timeout = speech_config.whisper_config.timeout

            logger.info(f"Whisper配置 - 模型: {model}, 语言: {language}, 时间戳: {enable_timestamps}")

            generated_subtitle = generate_subtitle_for_video(
                Path(video_path),
                language=language,
                model=model,
                method=speech_config.method,
                enable_timestamps=enable_timestamps,
                enable_punctuation=enable_punctuation,
                enable_speaker_diarization=enable_speaker_diarization,
                timeout=timeout
            )
        else:
            logger.info(f"使用API服务 - {speech_config.method}")

            if speech_config.method == "openai_api":
                api_config = speech_config.openai_config
            elif speech_config.method == "azure_speech":
                api_config = speech_config.azure_config
            elif speech_config.method == "google_speech":
                api_config = speech_config.google_config
            elif speech_config.method == "aliyun_speech":
                api_config = speech_config.aliyun_config
            elif speech_config.method == "custom_api":
                api_config = speech_config.custom_api_config
            else:
                raise ValueError(f"不支持的语音识别方法: {speech_config.method}")

            generated_subtitle = generate_subtitle_for_video(
                Path(video_path),
                method=speech_config.method,
                language=api_config.language,
                api_key=api_config.api_key,
                enable_timestamps=api_config.enable_timestamps,
                enable_punctuation=api_config.enable_punctuation
            )

        srt_path = str(generated_subtitle)
        logger.info(f"语音转写成功: {srt_path}")
    except Exception as e:
        logger.error(f"语音转写失败: {str(e)}")
        speech_error = str(e)

        if speech_config is not None and speech_config.enable_fallback and speech_config.fallback_method != speech_config.method:
            try:
                logger.info(f"尝试回退方法: {speech_config.fallback_method}")
                from backend.utils.speech_recognizer import generate_subtitle_for_video

                if speech_config.fallback_method == "whisper_local":
                    fallback_config = speech_config.whisper_config
                    generated_subtitle = generate_subtitle_for_video(
                        Path(video_path),
                        language=fallback_config.language,
                        model=fallback_config.model_name,
                        method=speech_config.fallback_method
                    )
                else:
                    generated_subtitle = generate_subtitle_for_video(
                        Path(video_path),
                        method=speech_config.fallback_method
                    )

                srt_path = str(generated_subtitle)
                speech_error = None
                logger.info(f"回退方法成功: {srt_path}")
            except Exception as fallback_error:
                logger.error(f"回退方法也失败: {str(fallback_error)}")
                speech_error = str(fallback_error)
                srt_path = None
        else:
            srt_path = None
    return srt_path, speech_error

@celery_app.task(bind=True)
def process_import_task(self, project_id: str, video_path: str, srt_file_path: Optional[str] = None):
    """
    处理本地导入的异步任务
    
    Args:
        project_id: 项目ID
        video_path: 视频文件路径
        srt_file_path: 字幕文件路径（可选）
    """
    try:
        logger.info(f"开始处理导入任务: {project_id}")

        # 会话只包住查重和缩略图。转写可能很久，不能占着连接。
        with session_scope() as db:
            project_service = ProjectService(db)

            from backend.models.task import Task, TaskStatus
            existing_task = db.query(Task).filter(
                Task.project_id == project_id,
                Task.status == TaskStatus.RUNNING,
                Task.name.like('%导入%')
            ).first()

            if existing_task and existing_task.celery_task_id != self.request.id:
                logger.warning(f"项目 {project_id} 已有处理任务在运行 (任务ID: {existing_task.celery_task_id})，跳过重复处理")
                return {
                    'success': False,
                    'error': '项目正在处理中，避免重复处理',
                    'existing_task_id': existing_task.celery_task_id
                }

            self.update_state(state='PROGRESS', meta={'progress': 10, 'message': '开始处理...'})

            logger.info(f"检查项目 {project_id} 缩略图...")
            self.update_state(state='PROGRESS', meta={'progress': 20, 'message': '检查缩略图...'})

            project = project_service.get(project_id)
            if project and not project.thumbnail:
                logger.info(f"项目 {project_id} 没有缩略图，开始生成...")
                self.update_state(state='PROGRESS', meta={'progress': 25, 'message': '生成缩略图...'})

                try:
                    thumbnail_data = generate_project_thumbnail(project_id, Path(video_path))
                    if thumbnail_data:
                        project.thumbnail = thumbnail_data
                        db.commit()
                        logger.info(f"项目 {project_id} 缩略图生成并保存成功")
                    else:
                        logger.warning(f"项目 {project_id} 缩略图生成失败")
                except Exception as e:
                    logger.error(f"生成项目缩略图时发生错误: {e}")
            else:
                logger.info(f"项目 {project_id} 已有缩略图，跳过生成")

        speech_error = None
        srt_path = srt_file_path
        if not srt_path:
            srt_path, speech_error = _generate_import_subtitle(self, project_id, video_path)

        logger.info(f"更新项目 {project_id} 状态为处理中...")
        self.update_state(state='PROGRESS', meta={'progress': 80, 'message': '启动处理流程...'})

        with session_scope() as db:
            project_service = ProjectService(db)
            project_service.update_project_status(project_id, "processing")

            if srt_path and Path(srt_path).exists():
                try:
                    task_result = submit_video_pipeline_task(
                        project_id=project_id,
                        input_video_path=video_path,
                        input_srt_path=srt_path
                    )
                except Exception as e:
                    logger.error(f"启动项目 {project_id} 处理失败: {str(e)}")
                    _fail_import(project_service, project_id, str(e))
                else:
                    if task_result['success']:
                        logger.info(f"项目 {project_id} 处理任务已启动，Celery任务ID: {task_result['task_id']}")
                        self.update_state(state='PROGRESS', meta={'progress': 100, 'message': '处理流程已启动'})
                    else:
                        logger.error(f"Celery任务提交失败: {task_result['error']}")
                        _fail_import(project_service, project_id, task_result['error'])
            else:
                failure = import_subtitle_failure(speech_error)
                logger.error("导入没有可用字幕: %s (%s)", failure.user_message(), failure.code)
                _fail_import(
                    project_service,
                    project_id,
                    failure.user_message(),
                    error_code=failure.code,
                )

        logger.info(f"导入任务完成: {project_id}")
        return {
            'status': 'completed',
            'project_id': project_id,
            'message': '导入处理完成'
        }

    except ImportProcessingError:
        raise
    except Exception as e:
        logger.error(f"导入任务失败: {project_id}, 错误: {e}")

        # 预期失败已经记过原因。这里只兜底未预料的异常，仍然不要手动写 FAILURE。
        try:
            with session_scope() as failure_db:
                project_service = ProjectService(failure_db)
                _record_import_failure(project_service, project_id, str(e))
        except Exception:
            logger.warning("导入任务失败后更新项目状态失败: %s", project_id, exc_info=True)
        raise

