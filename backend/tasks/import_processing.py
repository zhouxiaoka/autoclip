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
                
                # 根据视频分类选择模型
                project = project_service.get(project_id)
                video_category = "knowledge"  # 默认分类
                if project and project.processing_config:
                    video_category = project.processing_config.get("video_category", "knowledge")
                
                model = "base"  # 默认使用平衡模型
                if video_category in ["business", "knowledge"]:
                    model = "small"  # 知识类内容使用更准确的模型
                elif video_category == "speech":
                    model = "medium"  # 演讲内容使用高精度模型
                
                logger.info(f"使用Whisper生成字幕 - 语言: auto, 模型: {model}")
                
                generated_subtitle = generate_subtitle_for_video(
                    Path(video_path),
                    language="auto",
                    model=model
                )
                srt_path = str(generated_subtitle)
                logger.info(f"Whisper字幕生成成功: {srt_path}")
                
            except Exception as e:
                logger.error(f"Whisper字幕生成失败: {str(e)}")
                # 字幕生成失败，使用空字幕文件
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

