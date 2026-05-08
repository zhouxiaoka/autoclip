"""
本地导入处理任务
处理视频文件上传后的异步任务：字幕生成、缩略图生成、处理流程启动
"""

import logging
from pathlib import Path
from typing import Optional
from celery import Celery
from backend.core.database import get_db
from backend.services.project_service import ProjectService
from backend.utils.thumbnail_generator import generate_project_thumbnail
from backend.utils.task_submission_utils import submit_video_pipeline_task

logger = logging.getLogger(__name__)

# 获取Celery应用实例
from backend.core.celery_app import celery_app

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
        
        # 获取数据库会话
        db = next(get_db())
        project_service = ProjectService(db)
        
        # 检查是否已有相同项目正在处理中（防重复处理）
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
        
        # 更新任务进度
        self.update_state(state='PROGRESS', meta={'progress': 10, 'message': '开始处理...'})
        
        # 1. 检查并生成缩略图（如果还没有）
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
                # 缩略图生成失败不影响后续流程
        else:
            logger.info(f"项目 {project_id} 已有缩略图，跳过生成")
        
        # 2. 生成字幕（如果没有提供）
        srt_path = srt_file_path
        if not srt_path:
            logger.info(f"开始为项目 {project_id} 生成字幕...")
            self.update_state(state='PROGRESS', meta={'progress': 40, 'message': '生成字幕...'})
            
            try:
                from backend.utils.speech_recognizer import generate_subtitle_for_video
                from backend.core.desktop_config import get_desktop_config
                
                # 获取用户配置的语音转写设置
                config = get_desktop_config()
                speech_config = config.speech_recognition
                
                logger.info(f"使用语音转写配置 - 方法: {speech_config.method}")
                
                # 根据配置选择参数
                if speech_config.method == "whisper_local":
                    # 使用用户配置的Whisper参数
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
                    # 使用API服务
                    logger.info(f"使用API服务 - {speech_config.method}")
                    
                    # 根据服务类型获取API配置
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
                
                # 如果启用了回退机制，尝试使用回退方法
                if speech_config.enable_fallback and speech_config.fallback_method != speech_config.method:
                    try:
                        logger.info(f"尝试回退方法: {speech_config.fallback_method}")
                        
                        if speech_config.fallback_method == "whisper_local":
                            fallback_config = speech_config.whisper_config
                            generated_subtitle = generate_subtitle_for_video(
                                Path(video_path),
                                language=fallback_config.language,
                                model=fallback_config.model_name,
                                method=speech_config.fallback_method
                            )
                        else:
                            # 其他回退方法
                            generated_subtitle = generate_subtitle_for_video(
                                Path(video_path),
                                method=speech_config.fallback_method
                            )
                        
                        srt_path = str(generated_subtitle)
                        logger.info(f"回退方法成功: {srt_path}")
                        
                    except Exception as fallback_error:
                        logger.error(f"回退方法也失败: {str(fallback_error)}")
                        srt_path = None
                else:
                    srt_path = None
        
        # 3. 更新项目状态为处理中
        logger.info(f"更新项目 {project_id} 状态为处理中...")
        self.update_state(state='PROGRESS', meta={'progress': 80, 'message': '启动处理流程...'})
        
        project_service.update_project_status(project_id, "processing")
        
        # 4. 启动处理流程
        if srt_path and Path(srt_path).exists():
            try:
                task_result = submit_video_pipeline_task(
                    project_id=project_id,
                    input_video_path=video_path,
                    input_srt_path=srt_path
                )
                
                if task_result['success']:
                    logger.info(f"项目 {project_id} 处理任务已启动，Celery任务ID: {task_result['task_id']}")
                    self.update_state(state='PROGRESS', meta={'progress': 100, 'message': '处理流程已启动'})
                else:
                    logger.error(f"Celery任务提交失败: {task_result['error']}")
                    project_service.update_project_status(project_id, "failed")
                    self.update_state(state='FAILURE', meta={'error': task_result['error']})
                    return
                    
            except Exception as e:
                logger.error(f"启动项目 {project_id} 处理失败: {str(e)}")
                project_service.update_project_status(project_id, "failed")
                self.update_state(state='FAILURE', meta={'error': str(e)})
                return
        else:
            logger.error(f"字幕文件不存在: {srt_path}")
            project_service.update_project_status(project_id, "failed")
            self.update_state(state='FAILURE', meta={'error': '字幕文件不存在'})
            return
        
        logger.info(f"导入任务完成: {project_id}")
        return {
            'status': 'completed',
            'project_id': project_id,
            'message': '导入处理完成'
        }
        
    except Exception as e:
        logger.error(f"导入任务失败: {project_id}, 错误: {e}")
        
        # 更新项目状态为失败
        try:
            db = next(get_db())
            project_service = ProjectService(db)
            project_service.update_project_status(project_id, "failed")
        except:
            pass
        
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise
    finally:
        try:
            db.close()
        except:
            pass

