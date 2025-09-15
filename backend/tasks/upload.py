"""
投稿相关Celery任务
"""

import logging
from pathlib import Path
from sqlalchemy.orm import Session

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
        
        # 转换record_id为整数类型
        try:
            record_id_int = int(record_id)
        except ValueError:
            raise ValueError(f"无效的record_id格式: {record_id}")
        
        # 获取投稿记录
        upload_record = upload_service.get_upload_record_by_id(record_id_int)
        if not upload_record:
            raise ValueError(f"投稿记录不存在: {record_id}")
        
        # 构建视频文件路径
        project_output_dir = get_project_output_directory(str(upload_record.project_id))
        logger.info(f"项目输出目录: {project_output_dir}")
        
        # 获取clip信息以匹配正确的文件名
        from ..models.clip import Clip
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            raise ValueError(f"切片记录不存在: {clip_id}")
        
        clip_title = clip.title or clip.generated_title or ""
        logger.info(f"切片标题: {clip_title}")
        
        # 尝试多种可能的文件命名模式
        possible_paths = [
            project_output_dir / "clips" / f"{clip_id}.mp4",  # 标准命名
            project_output_dir / "clips" / f"{clip_id}_clip_{clip_id}.mp4",  # 带clip后缀的命名
            project_output_dir / "clips" / f"{clip_id}_clip.mp4",  # 简化clip后缀
        ]
        
        # 如果clip有标题，尝试通过标题匹配
        if clip_title:
            # 清理标题中的特殊字符，用于文件名匹配
            import re
            clean_title = re.sub(r'[<>:"/\\|?*]', '', clip_title)
            possible_paths.extend([
                project_output_dir / "clips" / f"{clean_title}.mp4",
                project_output_dir / "clips" / f"*{clean_title}*.mp4",
            ])
        
        logger.info(f"尝试查找文件，可能的路径: {[str(p) for p in possible_paths]}")
        
        # 查找视频文件
        video_path = None
        for path in possible_paths:
            if path.exists():
                video_path = path
                logger.info(f"找到视频文件: {video_path}")
                break
        
        if not video_path:
            # 如果标准路径都没找到，尝试在clips目录下查找所有mp4文件
            clips_dir = project_output_dir / "clips"
            if clips_dir.exists():
                mp4_files = list(clips_dir.glob("*.mp4"))
                logger.info(f"clips目录下的所有mp4文件: {[str(f) for f in mp4_files]}")
                
                # 如果只有一个mp4文件，就使用它
                if len(mp4_files) == 1:
                    video_path = mp4_files[0]
                    logger.info(f"使用唯一的mp4文件: {video_path}")
                else:
                    # 尝试通过标题匹配文件名
                    if clip_title:
                        for mp4_file in mp4_files:
                            # 检查文件名是否包含标题的关键词
                            if any(keyword in mp4_file.name for keyword in clip_title.split()[:3]):  # 使用标题的前3个词
                                video_path = mp4_file
                                logger.info(f"通过标题匹配找到: {video_path}")
                                break
                    
                    # 如果还是没找到，尝试通过clip_id匹配
                    if not video_path:
                        for mp4_file in mp4_files:
                            if clip_id in mp4_file.name:
                                video_path = mp4_file
                                logger.info(f"通过clip_id匹配找到: {video_path}")
                                break
        
        if not video_path:
            raise FileNotFoundError(f"未找到切片视频文件: {clip_id}")
        
        # 检查文件大小
        file_size = video_path.stat().st_size
        logger.info(f"视频文件大小: {file_size} bytes")
        
        if file_size == 0:
            raise ValueError("视频文件为空")
        
        # 执行上传
        logger.info(f"开始上传视频: {video_path}")
        success = upload_service.upload_clip_sync(record_id_int, str(video_path))
        
        if success:
            logger.info(f"切片上传成功: {clip_id}")
            upload_service.update_upload_status(record_id_int, "success")
        else:
            logger.error(f"切片上传失败: {clip_id}")
            upload_service.update_upload_status(record_id_int, "failed", "上传失败")
            
    except Exception as e:
        logger.error(f"上传切片任务失败: {str(e)}")
        upload_service.update_upload_status(record_id_int, "failed", str(e))
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name='backend.tasks.upload.upload_project_task')
def upload_project_task(self, record_id: str, clip_ids: list):
    """上传项目任务"""
    db = SessionLocal()
    try:
        logger.info(f"开始上传项目: record_id={record_id}, clip_ids={clip_ids}")
        
        # 获取投稿服务
        upload_service = BilibiliUploadService(db)
        
        # 转换record_id为整数类型
        try:
            record_id_int = int(record_id)
        except ValueError:
            raise ValueError(f"无效的record_id格式: {record_id}")
        
        # 获取投稿记录
        upload_record = upload_service.get_upload_record_by_id(record_id_int)
        if not upload_record:
            raise ValueError(f"投稿记录不存在: {record_id}")
        
        # 构建视频文件路径
        project_output_dir = get_project_output_directory(str(upload_record.project_id))
        logger.info(f"项目输出目录: {project_output_dir}")
        
        # 查找所有切片文件
        clips_dir = project_output_dir / "clips"
        if not clips_dir.exists():
            raise FileNotFoundError(f"clips目录不存在: {clips_dir}")
        
        # 获取所有mp4文件
        mp4_files = list(clips_dir.glob("*.mp4"))
        logger.info(f"找到的mp4文件: {[str(f) for f in mp4_files]}")
        
        if not mp4_files:
            raise FileNotFoundError("未找到任何mp4文件")
        
        # 如果只有一个文件，直接上传
        if len(mp4_files) == 1:
            video_path = mp4_files[0]
            logger.info(f"单个文件上传: {video_path}")
            
            # 检查文件大小
            file_size = video_path.stat().st_size
            if file_size == 0:
                raise ValueError("视频文件为空")
            
            # 执行上传
            success = upload_service.upload_clip(record_id_int, str(video_path))
            
            if success:
                logger.info("项目上传成功")
                upload_service.update_upload_status(record_id_int, "success")
            else:
                logger.error("项目上传失败")
                upload_service.update_upload_status(record_id_int, "failed", "上传失败")
        else:
            # 多个文件的情况，这里可以扩展为合并上传或分别上传
            logger.warning(f"发现多个视频文件，当前只支持单个文件上传: {len(mp4_files)}")
            upload_service.update_upload_status(record_id_int, "failed", "暂不支持多文件上传")
            
    except Exception as e:
        logger.error(f"上传项目任务失败: {str(e)}")
        upload_service.update_upload_status(record_id_int, "failed", str(e))
        raise
    finally:
        db.close()