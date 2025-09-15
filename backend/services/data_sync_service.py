"""
数据同步服务 - 将处理结果同步到数据库
"""

import json
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from sqlalchemy.orm import Session
from backend.models.clip import Clip, ClipStatus
from backend.models.collection import Collection, CollectionStatus
from backend.models.project import Project, ProjectStatus, ProjectType
from backend.models.task import Task, TaskStatus, TaskType
from datetime import datetime

logger = logging.getLogger(__name__)


class DataSyncService:
    """数据同步服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def sync_all_projects_from_filesystem(self, data_dir: Path) -> Dict[str, Any]:
        """从文件系统同步所有项目到数据库"""
        try:
            logger.info(f"开始从文件系统同步所有项目: {data_dir}")
            
            projects_dir = data_dir / "projects"
            if not projects_dir.exists():
                logger.warning(f"项目目录不存在: {projects_dir}")
                return {"success": False, "error": "项目目录不存在"}
            
            synced_projects = []
            failed_projects = []
            
            # 遍历所有项目目录
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir() and not project_dir.name.startswith('.'):
                    project_id = project_dir.name
                    try:
                        result = self.sync_project_from_filesystem(project_id, project_dir)
                        if result["success"]:
                            synced_projects.append(project_id)
                        else:
                            failed_projects.append({"project_id": project_id, "error": result.get("error")})
                    except Exception as e:
                        logger.error(f"同步项目 {project_id} 失败: {str(e)}")
                        failed_projects.append({"project_id": project_id, "error": str(e)})
            
            logger.info(f"同步完成: 成功 {len(synced_projects)} 个, 失败 {len(failed_projects)} 个")
            
            return {
                "success": True,
                "synced_projects": synced_projects,
                "failed_projects": failed_projects,
                "total_synced": len(synced_projects),
                "total_failed": len(failed_projects)
            }
            
        except Exception as e:
            logger.error(f"同步所有项目失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def sync_project_from_filesystem(self, project_id: str, project_dir: Path) -> Dict[str, Any]:
        """从文件系统同步单个项目到数据库"""
        try:
            logger.info(f"开始同步项目: {project_id}")
            
            # 检查项目是否已存在于数据库
            existing_project = self.db.query(Project).filter(Project.id == project_id).first()
            if existing_project:
                logger.info(f"项目 {project_id} 已存在于数据库，继续同步切片数据")
            else:
                # 读取项目元数据
                project_metadata = self._read_project_metadata(project_dir)
                if not project_metadata:
                    logger.warning(f"项目 {project_id} 没有元数据文件，创建基础项目记录")
                    project_metadata = {
                        "project_name": f"项目_{project_id[:8]}",
                        "created_at": datetime.now().isoformat(),
                        "status": "pending"
                    }
                
                # 创建项目记录
                project = Project(
                    id=project_id,
                    name=project_metadata.get("project_name", f"项目_{project_id[:8]}"),
                    description=project_metadata.get("description", ""),
                    project_type=ProjectType.KNOWLEDGE,  # 默认类型
                    status=ProjectStatus.PENDING,
                    processing_config=project_metadata.get("processing_config", {}),
                    project_metadata=project_metadata
                )
                
                self.db.add(project)
                self.db.commit()
                self.db.refresh(project)
                
                logger.info(f"项目 {project_id} 同步到数据库成功")
            

            
            # 同步切片数据
            clips_count = self._sync_clips_from_filesystem(project_id, project_dir)
            
            # 同步合集数据
            logger.info(f"开始同步项目 {project_id} 的合集数据")
            collections_count = self._sync_collections_from_filesystem(project_id, project_dir)
            logger.info(f"项目 {project_id} 合集同步完成，同步了 {collections_count} 个合集")
            
            # 检查项目是否已完成处理，更新项目状态
            self._update_project_status_if_completed(project_id, project_dir)
            
            return {
                "success": True,
                "project_id": project_id,
                "clips_synced": clips_count,
                "collections_synced": collections_count
            }
            
        except Exception as e:
            logger.error(f"同步项目 {project_id} 失败: {str(e)}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def _read_project_metadata(self, project_dir: Path) -> Optional[Dict[str, Any]]:
        """读取项目元数据"""
        metadata_files = [
            project_dir / "project.json",
            project_dir / "metadata.json",
            project_dir / "info.json"
        ]
        
        for metadata_file in metadata_files:
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"读取元数据文件失败 {metadata_file}: {e}")
        
        return None
    
    def _sync_clips_from_filesystem(self, project_id: str, project_dir: Path) -> int:
        """从文件系统同步切片数据"""
        try:
            # 查找切片数据文件
            clips_files = [
                project_dir / "step6_video" / "clips_metadata.json",  # 最完整的数据源
                project_dir / "step3_all_scored.json",  # 优先使用正确的数据源
                project_dir / "step4_title" / "step4_title.json",
                project_dir / "step4_titles.json",
                project_dir / "clips_metadata.json",
                project_dir / "metadata" / "clips_metadata.json"
            ]
            
            clips_data = None
            for clips_file in clips_files:
                logger.info(f"检查切片文件: {clips_file}")
                if clips_file.exists():
                    try:
                        with open(clips_file, 'r', encoding='utf-8') as f:
                            clips_data = json.load(f)
                        logger.info(f"成功读取切片文件: {clips_file}, 数据长度: {len(clips_data) if isinstance(clips_data, list) else 'not list'}")
                        break
                    except Exception as e:
                        logger.warning(f"读取切片文件失败 {clips_file}: {e}")
                else:
                    logger.info(f"切片文件不存在: {clips_file}")
            
            if not clips_data:
                logger.info(f"项目 {project_id} 没有找到切片数据")
                return 0
            
            # 确保clips_data是列表
            if isinstance(clips_data, dict) and "clips" in clips_data:
                clips_data = clips_data["clips"]
            elif not isinstance(clips_data, list):
                logger.warning(f"项目 {project_id} 切片数据格式不正确")
                return 0
            
            synced_count = 0
            updated_count = 0
            for clip_data in clips_data:
                try:
                    # 检查切片是否已存在
                    existing_clip = self.db.query(Clip).filter(
                        Clip.project_id == project_id,
                        Clip.title == clip_data.get("generated_title", clip_data.get("title", ""))
                    ).first()
                    
                    if existing_clip:
                        # 更新现有切片的video_path和tags，强制使用项目内输出目录
                        clip_id = clip_data.get('id', str(synced_count + 1))
                        safe_title = clip_data.get('generated_title', clip_data.get('title', clip_data.get('outline', '')))
                        # 清理文件名，移除特殊字符
                        safe_title = "".join(c for c in safe_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        safe_title = safe_title.replace(' ', '_')
                        
                        # 强制使用项目内标准路径
                        from ..core.path_utils import get_project_directory
                        project_dir = get_project_directory(project_id)
                        project_clips_dir = project_dir / "output" / "clips"
                        project_clips_dir.mkdir(parents=True, exist_ok=True)
                        project_video_path = project_clips_dir / f"{clip_id}_{safe_title}.mp4"
                        
                        # 兼容旧的全局输出目录，如果存在则迁移到项目目录
                        from ..core.path_utils import get_data_directory
                        legacy_video_path = get_data_directory() / "output" / "clips" / f"{clip_id}_{safe_title}.mp4"
                        try:
                            if legacy_video_path.exists() and not project_video_path.exists():
                                import shutil
                                shutil.copy2(legacy_video_path, project_video_path)
                                logger.info(f"迁移旧切片文件到项目目录: {legacy_video_path} -> {project_video_path}")
                        except Exception as _e:
                            logger.warning(f"迁移旧切片文件失败: {legacy_video_path} -> {project_video_path}: {_e}")
                        
                        # 始终使用项目内路径
                        video_path = str(project_video_path)
                        logger.info(f"更新切片 {existing_clip.id} 的video_path: {video_path}")
                        existing_clip.video_path = video_path
                        if existing_clip.tags is None:
                            existing_clip.tags = []  # 确保tags是空列表而不是null
                        updated_count += 1
                        continue
                    
                    # 转换时间格式
                    start_time = self._convert_time_to_seconds(clip_data.get('start_time', '00:00:00'))
                    end_time = self._convert_time_to_seconds(clip_data.get('end_time', '00:00:00'))
                    duration = end_time - start_time
                    
                    # 构建视频文件路径，强制使用项目内目录
                    clip_id = clip_data.get('id', str(synced_count + 1))
                    title = clip_data.get('generated_title', clip_data.get('title', clip_data.get('outline', '')))
                    
                    # 强制使用项目内路径
                    from ..core.path_utils import get_project_directory, get_data_directory
                    project_dir = get_project_directory(project_id)
                    project_clips_dir = project_dir / "output" / "clips"
                    project_clips_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 查找实际的文件名（保留特殊字符）
                    actual_filename = None
                    for file_path in project_clips_dir.glob(f"{clip_id}_*.mp4"):
                        actual_filename = file_path.name
                        break
                    
                    if actual_filename:
                        project_video_path = project_clips_dir / actual_filename
                    else:
                        # 如果找不到实际文件，使用清理后的文件名作为后备
                        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        safe_title = safe_title.replace(' ', '_')
                        project_video_path = project_clips_dir / f"{clip_id}_{safe_title}.mp4"
                    
                    # 兼容旧的全局输出目录，如果存在则迁移到项目目录
                    global_clips_dir = get_data_directory() / "output" / "clips"
                    if actual_filename:
                        global_video_path = global_clips_dir / actual_filename
                    else:
                        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        safe_title = safe_title.replace(' ', '_')
                        global_video_path = global_clips_dir / f"{clip_id}_{safe_title}.mp4"
                    
                    if global_video_path.exists() and not project_video_path.exists():
                        import shutil
                        shutil.copy2(global_video_path, project_video_path)
                        logger.info(f"将切片文件从全局目录迁移到项目目录: {global_video_path} -> {project_video_path}")
                    
                    # 始终使用项目内路径
                    video_path = str(project_video_path)
                    
                    # 创建切片记录
                    clip = Clip(
                        project_id=project_id,
                        title=clip_data.get('generated_title', clip_data.get('title', clip_data.get('outline', ''))),
                        description=clip_data.get('recommend_reason', ''),
                        start_time=start_time,
                        end_time=end_time,
                        duration=duration,
                        score=clip_data.get('final_score', 0.0),
                        video_path=video_path,
                        tags=[],  # 确保tags是空列表而不是null
                        clip_metadata=clip_data,
                        status=ClipStatus.COMPLETED
                    )
                    
                    self.db.add(clip)
                    synced_count += 1
                    
                except Exception as e:
                    logger.error(f"同步切片失败: {e}")
                    continue
            
            self.db.commit()
            logger.info(f"项目 {project_id} 同步了 {synced_count} 个切片，更新了 {updated_count} 个切片")
            return synced_count
            
        except Exception as e:
            logger.error(f"同步切片数据失败: {str(e)}")
            return 0
    
    def _sync_collections_from_filesystem(self, project_id: str, project_dir: Path) -> int:
        """从文件系统同步合集数据"""
        try:
            # 查找合集数据文件
            collections_files = [
                project_dir / "step6_video" / "collections_metadata.json",  # 最完整的数据源
                project_dir / "step5_clustering" / "step5_clustering.json",
                project_dir / "metadata" / "step5_collections.json",  # 添加step5_collections.json
                project_dir / "collections_metadata.json",
                project_dir / "metadata" / "collections_metadata.json"
            ]
            
            collections_data = None
            for collections_file in collections_files:
                logger.info(f"检查合集文件: {collections_file}")
                if collections_file.exists():
                    try:
                        with open(collections_file, 'r', encoding='utf-8') as f:
                            collections_data = json.load(f)
                        logger.info(f"成功读取合集文件: {collections_file}, 数据长度: {len(collections_data) if isinstance(collections_data, list) else 'not list'}")
                        break
                    except Exception as e:
                        logger.warning(f"读取合集文件失败 {collections_file}: {e}")
                else:
                    logger.info(f"合集文件不存在: {collections_file}")
            
            if not collections_data:
                logger.info(f"项目 {project_id} 没有找到合集数据")
                return 0
            
            # 确保collections_data是列表
            if isinstance(collections_data, dict) and "collections" in collections_data:
                collections_data = collections_data["collections"]
            elif not isinstance(collections_data, list):
                logger.warning(f"项目 {project_id} 合集数据格式不正确")
                return 0
            
            # 读取删除记录文件
            deleted_collections_file = project_dir / "deleted_collections.json"
            deleted_collections = set()
            if deleted_collections_file.exists():
                try:
                    with open(deleted_collections_file, 'r', encoding='utf-8') as f:
                        deleted_data = json.load(f)
                        deleted_collections = set(deleted_data.get('deleted_collection_ids', []))
                except Exception as e:
                    logger.warning(f"读取删除记录失败: {e}")
            
            synced_count = 0
            for collection_data in collections_data:
                try:
                    collection_id = collection_data.get("id", "")
                    collection_title = collection_data.get("collection_title", "")
                    
                    # 检查是否已被删除
                    if collection_id in deleted_collections:
                        logger.info(f"合集 {collection_id} 已被删除，跳过同步")
                        continue
                    
                    # 检查合集是否已存在
                    existing_collection = self.db.query(Collection).filter(
                        Collection.project_id == project_id,
                        Collection.name == collection_title
                    ).first()
                    
                    if existing_collection:
                        # 合集已存在，检查是否需要建立关联关系
                        collection = existing_collection
                        logger.info(f"合集 {collection_title} 已存在，检查关联关系")
                    else:
                        # 创建新合集
                        collection = None
                    
                    # 构建合集视频文件路径，强制使用项目内目录
                    # 尝试多种可能的文件名格式
                    possible_filenames = [
                        f"{collection_id}_{collection_title}.mp4",
                        f"{collection_title}.mp4",
                        f"collection_{collection_id}.mp4"
                    ]
                    
                    from ..core.path_utils import get_project_directory, get_data_directory
                    project_dir = get_project_directory(project_id)
                    project_collections_dir = project_dir / "output" / "collections"
                    project_collections_dir.mkdir(parents=True, exist_ok=True)
                    
                    video_path = None
                    # 首先在项目目录中查找
                    for filename in possible_filenames:
                        project_video_path = project_collections_dir / filename
                        if project_video_path.exists():
                            video_path = str(project_video_path)
                            break
                    
                    # 如果项目目录中没找到，尝试全局目录并迁移
                    if not video_path:
                        for filename in possible_filenames:
                            legacy_video_path = get_data_directory() / "output" / "collections" / filename
                            if legacy_video_path.exists():
                                # 迁移到项目目录
                                project_video_path = project_collections_dir / filename
                                import shutil
                                shutil.copy2(legacy_video_path, project_video_path)
                                video_path = str(project_video_path)
                                logger.info(f"将合集文件从全局目录迁移到项目目录: {legacy_video_path} -> {project_video_path}")
                                break
                    
                    # 如果还是没找到，使用项目内路径（文件可能还未生成）
                    if not video_path:
                        video_path = str(project_collections_dir / possible_filenames[0])
                    
                    # 将数字格式的clip_ids转换为UUID格式
                    original_clip_ids = collection_data.get('clip_ids', [])
                    uuid_clip_ids = []
                    
                    # 获取项目中所有切片的映射关系（数字ID -> UUID）
                    clips = self.db.query(Clip).filter(Clip.project_id == project_id).all()
                    clip_id_mapping = {}
                    for clip in clips:
                        # 从clip_metadata中获取原始ID
                        if clip.clip_metadata and 'id' in clip.clip_metadata:
                            original_id = str(clip.clip_metadata['id'])
                            clip_id_mapping[original_id] = clip.id
                    
                    # 转换clip_ids
                    for original_id in original_clip_ids:
                        if str(original_id) in clip_id_mapping:
                            uuid_clip_ids.append(clip_id_mapping[str(original_id)])
                        else:
                            logger.warning(f"找不到切片ID {original_id} 对应的UUID")
                    
                    # 如果合集不存在，创建新合集
                    if not collection:
                        collection = Collection(
                            project_id=project_id,
                            name=collection_title,
                            description=collection_data.get('collection_summary', ''),
                            video_path=video_path,
                            export_path=video_path,  # 设置export_path
                            collection_metadata={
                                'clip_ids': uuid_clip_ids,  # 使用UUID格式的clip_ids
                                'original_clip_ids': original_clip_ids,  # 保留原始数字ID
                                'collection_type': 'ai_recommended',
                                'original_id': collection_id
                            },
                            status=CollectionStatus.COMPLETED
                        )
                        
                        self.db.add(collection)
                        self.db.flush()  # 确保collection有ID
                        logger.info(f"创建新合集: {collection.id}")
                    else:
                        # 更新现有合集的元数据
                        if not collection.collection_metadata:
                            collection.collection_metadata = {}
                        collection.collection_metadata.update({
                            'clip_ids': uuid_clip_ids,
                            'original_clip_ids': original_clip_ids,
                            'collection_type': 'ai_recommended',
                            'original_id': collection_id
                        })
                        collection.video_path = video_path
                        collection.export_path = video_path  # 设置export_path
                        logger.info(f"更新现有合集: {collection.id}")
                    
                    # 建立合集和切片的关联关系
                    for i, clip_id in enumerate(uuid_clip_ids):
                        try:
                            # 检查切片是否存在
                            clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
                            if clip:
                                # 检查关联关系是否已存在
                                from ..models.collection import clip_collection
                                existing_relation = self.db.execute(
                                    clip_collection.select().where(
                                        clip_collection.c.clip_id == clip_id,
                                        clip_collection.c.collection_id == collection.id
                                    )
                                ).first()
                                
                                if not existing_relation:
                                    # 使用关联表插入记录
                                    stmt = clip_collection.insert().values(
                                        clip_id=clip_id,
                                        collection_id=collection.id,
                                        order_index=i
                                    )
                                    self.db.execute(stmt)
                                    logger.info(f"建立合集 {collection.id} 和切片 {clip_id} 的关联关系")
                                else:
                                    logger.info(f"合集 {collection.id} 和切片 {clip_id} 的关联关系已存在")
                            else:
                                logger.warning(f"切片 {clip_id} 不存在，跳过关联")
                        except Exception as e:
                            logger.error(f"建立合集和切片关联关系失败: {e}")
                    
                    synced_count += 1
                    
                except Exception as e:
                    logger.error(f"同步合集失败: {e}")
                    continue
            
            self.db.commit()
            logger.info(f"项目 {project_id} 同步了 {synced_count} 个合集")
            return synced_count
            
        except Exception as e:
            logger.error(f"同步合集数据失败: {str(e)}")
            return 0
    
    def sync_project_data(self, project_id: str, project_dir: Path) -> Dict[str, Any]:
        """同步项目数据到数据库"""
        try:
            logger.info(f"开始同步项目数据: {project_id}")
            
            # 同步clips数据
            clips_count = self._sync_clips(project_id, project_dir)
            
            # 同步collections数据
            collections_count = self._sync_collections(project_id, project_dir)
            
            # 更新项目统计信息
            self._update_project_stats(project_id, clips_count, collections_count)
            
            logger.info(f"项目数据同步完成: {project_id}, clips: {clips_count}, collections: {collections_count}")
            
            return {
                "success": True,
                "clips_synced": clips_count,
                "collections_synced": collections_count
            }
            
        except Exception as e:
            logger.error(f"同步项目数据失败: {str(e)}")
            raise
    
    def _sync_clips(self, project_id: str, project_dir: Path) -> int:
        """同步clips数据"""
        clips_file = project_dir / "step4_titles.json"
        if not clips_file.exists():
            logger.warning(f"Clips文件不存在: {clips_file}")
            return 0
        
        try:
            with open(clips_file, 'r', encoding='utf-8') as f:
                clips_data = json.load(f)
            
            clips_count = 0
            for clip_data in clips_data:
                # 检查是否已存在
                existing_clip = self.db.query(Clip).filter(
                    Clip.project_id == project_id,
                    Clip.title == clip_data.get("generated_title")
                ).first()
                
                if existing_clip:
                    logger.info(f"Clip已存在，跳过: {clip_data.get('generated_title')}")
                    continue
                
                # 创建新的clip记录
                clip = Clip(
                    project_id=project_id,
                    title=clip_data.get("generated_title", ""),
                    description=clip_data.get("outline", ""),
                    start_time=self._parse_time(clip_data.get("start_time", "00:00:00")),
                    end_time=self._parse_time(clip_data.get("end_time", "00:00:00")),
                    duration=self._calculate_duration(
                        clip_data.get("start_time", "00:00:00"),
                        clip_data.get("end_time", "00:00:00")
                    ),
                    score=clip_data.get("final_score", 0.0),
                    status=ClipStatus.COMPLETED,
                    tags=[],
                    clip_metadata={
                        "outline": clip_data.get("outline"),
                        "content": clip_data.get("content", []),
                        "recommend_reason": clip_data.get("recommend_reason"),
                        "chunk_index": clip_data.get("chunk_index"),
                        "original_id": clip_data.get("id")
                    }
                )
                
                self.db.add(clip)
                clips_count += 1
                logger.info(f"创建clip: {clip.title}")
            
            self.db.commit()
            logger.info(f"同步了 {clips_count} 个clips")
            return clips_count
            
        except Exception as e:
            logger.error(f"同步clips失败: {str(e)}")
            self.db.rollback()
            raise
    
    def _sync_collections(self, project_id: str, project_dir: Path) -> int:
        """同步collections数据到数据库"""
        collections_file = project_dir / "step5_collections.json"
        if not collections_file.exists():
            logger.warning(f"Collections文件不存在: {collections_file}")
            return 0
        
        try:
            with open(collections_file, 'r', encoding='utf-8') as f:
                collections_data = json.load(f)
            
            collections_count = 0
            for collection_data in collections_data:
                # 检查是否已存在
                existing_collection = self.db.query(Collection).filter(
                    Collection.project_id == project_id,
                    Collection.name == collection_data.get("collection_title")
                ).first()
                
                if existing_collection:
                    logger.info(f"Collection已存在，跳过: {collection_data.get('collection_title')}")
                    continue
                
                # 创建新的collection记录
                collection = Collection(
                    project_id=project_id,
                    name=collection_data.get("collection_title", ""),
                    description=collection_data.get("collection_summary", ""),
                    theme="default",
                    status=CollectionStatus.COMPLETED,
                    tags=[],
                    collection_metadata={
                        "clip_ids": collection_data.get("clip_ids", []),
                        "original_id": collection_data.get("id"),
                        "collection_type": "ai_recommended"  # 标记为AI推荐
                    }
                )
                
                self.db.add(collection)
                collections_count += 1
                logger.info(f"创建collection: {collection.name}")
            
            self.db.commit()
            logger.info(f"同步了 {collections_count} 个collections")
            return collections_count
            
        except Exception as e:
            logger.error(f"同步collections失败: {str(e)}")
            self.db.rollback()
            raise
    
    def _update_project_stats(self, project_id: str, clips_count: int, collections_count: int):
        """更新项目统计信息"""
        try:
            project = self.db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.total_clips = clips_count
                project.total_collections = collections_count
                self.db.commit()
                logger.info(f"更新项目统计: clips={clips_count}, collections={collections_count}")
        except Exception as e:
            logger.error(f"更新项目统计失败: {str(e)}")
    
    def _parse_time(self, time_str: str) -> float:
        """解析时间字符串为秒数"""
        try:
            if ',' in time_str:
                time_str = time_str.replace(',', '.')
            
            parts = time_str.split(':')
            if len(parts) == 3:
                hours = int(parts[0])
                minutes = int(parts[1])
                seconds = float(parts[2])
                return hours * 3600 + minutes * 60 + seconds
            else:
                return 0.0
        except Exception:
            return 0.0
    
    def _calculate_duration(self, start_time: str, end_time: str) -> float:
        """计算持续时间"""
        start_seconds = self._parse_time(start_time)
        end_seconds = self._parse_time(end_time)
        return end_seconds - start_seconds

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
    
    def _update_project_status_if_completed(self, project_id: str, project_dir: Path):
        """检查项目是否已完成处理，如果是则更新状态为completed"""
        try:
            # 检查是否有step6_video_output.json文件，这是处理完成的标志
            step6_output_file = project_dir / "output" / "step6_video_output.json"
            
            if step6_output_file.exists():
                # 获取项目记录
                project = self.db.query(Project).filter(Project.id == project_id).first()
                if project and project.status != ProjectStatus.COMPLETED:
                    # 读取step6输出文件获取统计信息
                    try:
                        with open(step6_output_file, 'r', encoding='utf-8') as f:
                            step6_output = json.load(f)
                        
                        # 更新项目状态和统计信息
                        project.status = ProjectStatus.COMPLETED
                        project.total_clips = step6_output.get("clips_count", 0)
                        project.total_collections = step6_output.get("collections_count", 0)
                        project.completed_at = datetime.now()
                        
                        self.db.commit()
                        logger.info(f"项目 {project_id} 状态已更新为已完成，切片数: {project.total_clips}, 合集数: {project.total_collections}")
                        
                    except Exception as e:
                        logger.error(f"读取step6输出文件失败: {e}")
                        # 即使读取失败，也标记为已完成
                        project.status = ProjectStatus.COMPLETED
                        project.completed_at = datetime.now()
                        self.db.commit()
                        logger.info(f"项目 {project_id} 状态已更新为已完成（无统计信息）")
                        
        except Exception as e:
            logger.error(f"更新项目状态失败: {e}")
