"""
投稿相关Celery任务
"""

import logging
from pathlib import Path
from sqlalchemy.orm import Session
import uuid

from ..core.celery_app import celery_app
from ..core.database import SessionLocal
from ..services.bilibili_service import BilibiliUploadService
from ..core.path_utils import get_project_output_directory

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='backend.tasks.upload.upload_clip_task')
def upload_clip_task(self, record_id: str, clip_id: str):
    """上传切片任务"""
    db = SessionLocal()
    try:
        logger.info(f"开始上传切片: record_id={record_id}, clip_id={clip_id}")
        
        # 获取投稿服务
        upload_service = BilibiliUploadService(db)
        
        # 转换record_id为UUID类型
        try:
            record_uuid = uuid.UUID(record_id)
        except ValueError:
            raise ValueError(f"无效的record_id格式: {record_id}")
        
        # 获取投稿记录
        upload_record = upload_service.get_upload_record(record_uuid)
        if not upload_record:
            raise ValueError(f"投稿记录不存在: {record_id}")
        
        # 构建视频文件路径
        project_output_dir = get_project_output_directory(str(upload_record.project_id))
        logger.info(f"项目输出目录: {project_output_dir}")
        
        # 尝试多种可能的文件命名模式
        possible_paths = [
            project_output_dir / "clips" / f"{clip_id}.mp4",  # 标准命名
            project_output_dir / "clips" / f"{clip_id}_clip_{clip_id}.mp4",  # 带clip后缀的命名
            project_output_dir / "clips" / f"{clip_id}_clip.mp4",  # 简化clip后缀
        ]
        
        logger.info(f"尝试查找文件，可能的路径: {[str(p) for p in possible_paths]}")
        
        video_path = None
        for path in possible_paths:
            if path.exists():
                video_path = path
                logger.info(f"找到视频文件: {video_path}")
                break
        
        if not video_path:
            # 如果都找不到，尝试在clips目录中搜索包含clip_id的文件
            clips_dir = project_output_dir / "clips"
            if clips_dir.exists():
                logger.info(f"在clips目录中搜索包含{clip_id}的文件")
                for file_path in clips_dir.glob(f"*{clip_id}*.mp4"):
                    if file_path.exists():
                        video_path = file_path
                        logger.info(f"通过搜索找到视频文件: {video_path}")
                        break
        
        if not video_path:
            # 列出clips目录中的所有文件，帮助调试
            clips_dir = project_output_dir / "clips"
            if clips_dir.exists():
                all_files = list(clips_dir.glob("*.mp4"))
                logger.error(f"clips目录中的所有文件: {[f.name for f in all_files]}")
            
            raise FileNotFoundError(f"视频文件不存在，尝试了以下路径: {[str(p) for p in possible_paths]}")
        
        # 上传视频
        success = upload_service.upload_clip(record_uuid, str(video_path))
        
        if success:
            logger.info(f"切片上传成功: clip_id={clip_id}")
            # 更新任务状态为成功
            upload_service.update_upload_status(record_uuid, "success")
        else:
            logger.error(f"切片上传失败: clip_id={clip_id}")
            # 更新任务状态为失败
            upload_service.update_upload_status(record_uuid, "failed", "上传失败")
            
    except Exception as e:
        logger.error(f"上传切片任务失败: {str(e)}")
        # 更新任务状态为失败
        upload_service.update_upload_status(record_uuid, "failed", str(e))
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name='backend.tasks.upload.batch_upload_task')
def batch_upload_task(self, record_id: str):
    """批量上传任务"""
    db = SessionLocal()
    try:
        logger.info(f"开始批量上传: record_id={record_id}")
        
        # 获取投稿服务
        upload_service = BilibiliUploadService(db)
        
        # 转换record_id为UUID类型
        try:
            record_uuid = uuid.UUID(record_id)
        except ValueError:
            raise ValueError(f"无效的record_id格式: {record_id}")
        
        # 获取投稿记录
        upload_record = upload_service.get_upload_record(record_uuid)
        if not upload_record:
            raise ValueError(f"投稿记录不存在: {record_id}")
        
        # 解析clip_ids
        clip_ids = upload_record.clip_id.split(",") if upload_record.clip_id else []
        
        if not clip_ids:
            raise ValueError("没有要上传的切片")
        
        # 逐个上传切片
        for clip_id in clip_ids:
            clip_id = clip_id.strip()
            if clip_id:
                # 构建视频文件路径
                project_output_dir = get_project_output_directory(str(upload_record.project_id))
                
                # 尝试多种可能的文件命名模式
                possible_paths = [
                    project_output_dir / "clips" / f"{clip_id}.mp4",  # 标准命名
                    project_output_dir / "clips" / f"{clip_id}_clip_{clip_id}.mp4",  # 带clip后缀的命名
                    project_output_dir / "clips" / f"{clip_id}_clip.mp4",  # 简化clip后缀
                ]
                
                video_path = None
                for path in possible_paths:
                    if path.exists():
                        video_path = path
                        break
                
                if not video_path:
                    # 如果都找不到，尝试在clips目录中搜索包含clip_id的文件
                    clips_dir = project_output_dir / "clips"
                    if clips_dir.exists():
                        for file_path in clips_dir.glob(f"*{clip_id}*.mp4"):
                            if file_path.exists():
                                video_path = file_path
                                break
                
                if video_path:
                    success = upload_service.upload_clip(record_uuid, str(video_path))
                    if success:
                        logger.info(f"切片上传成功: {clip_id}")
                    else:
                        logger.error(f"切片上传失败: {clip_id}")
                else:
                    logger.error(f"视频文件不存在，尝试了以下路径: {[str(p) for p in possible_paths]}")
        
        logger.info(f"批量上传完成: record_id={record_id}")
        # 更新任务状态为成功
        upload_service.update_upload_status(record_uuid, "success")
        
    except Exception as e:
        logger.error(f"批量上传任务失败: {str(e)}")
        # 更新任务状态为失败
        upload_service.update_upload_status(record_uuid, "failed", str(e))
        raise
    finally:
        db.close()

