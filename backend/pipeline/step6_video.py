"""
Step 6: 视频生成 - 根据聚类结果生成最终视频切片
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

# 导入依赖
from ..utils.video_processor import VideoProcessor
from ..core.shared_config import METADATA_DIR, CLIPS_DIR, COLLECTIONS_DIR

logger = logging.getLogger(__name__)

class VideoGenerator:
    """视频生成器"""
    
    def __init__(self, clips_dir: Optional[str] = None, collections_dir: Optional[str] = None, metadata_dir: Optional[str] = None):
        # 强制使用项目内专属目录，不使用全局目录作为后备
        if not clips_dir:
            raise ValueError("clips_dir 参数是必需的，不能使用全局路径")
        if not collections_dir:
            raise ValueError("collections_dir 参数是必需的，不能使用全局路径")
        
        self.clips_dir = Path(clips_dir)
        self.collections_dir = Path(collections_dir)
        self.metadata_dir = Path(metadata_dir) if metadata_dir else METADATA_DIR
        
        # 确保目录存在
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self.collections_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建VideoProcessor实例，强制使用项目内路径
        self.video_processor = VideoProcessor(clips_dir=str(self.clips_dir), collections_dir=str(self.collections_dir))
    
    def generate_clips(self, clips_with_titles: List[Dict], input_video: Path) -> List[Path]:
        """
        生成切片视频
        
        Args:
            clips_with_titles: 带标题的片段数据
            input_video: 输入视频路径
            
        Returns:
            生成的切片视频路径列表
        """
        logger.info("开始生成切片视频...")
        
        # 准备切片数据
        clips_data = []
        for clip in clips_with_titles:
            clips_data.append({
                'id': clip['id'],
                'title': clip.get('generated_title', f"片段_{clip['id']}"),
                'start_time': clip['start_time'],
                'end_time': clip['end_time']
            })
        
        # 批量生成切片
        successful_clips = self.video_processor.batch_extract_clips(input_video, clips_data)
        
        logger.info(f"切片视频生成完成，共{len(successful_clips)}个切片")
        return successful_clips
    
    def generate_collections(self, collections_data: List[Dict]) -> List[Path]:
        """
        生成合集视频
        
        Args:
            collections_data: 合集数据
            
        Returns:
            生成的合集视频路径列表
        """
        logger.info("开始生成合集视频...")
        
        # 生成合集视频
        successful_collections = self.video_processor.create_collections_from_metadata(collections_data)
        
        logger.info(f"合集视频生成完成，共{len(successful_collections)}个合集")
        return successful_collections
    
    def save_clip_metadata(self, clips_with_titles: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        保存最终的切片元数据到clips_metadata.json
        
        Args:
            clips_with_titles: 带标题的片段数据（来自step4）
            output_path: 输出路径，默认为clips_metadata.json
            
        Returns:
            保存的文件路径
            
        Note:
            此方法保存的是最终的切片元数据，包含视频生成后的完整信息。
            与step4的step4_titles.json不同，这里保存的是用于前端展示的最终数据。
        """
        if output_path is None:
            output_path = self.metadata_dir / "clips_metadata.json"
        
        # 确保目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存数据
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(clips_with_titles, f, ensure_ascii=False, indent=2)
        
        logger.info(f"切片元数据已保存到: {output_path}")
        return output_path
    
    def save_collection_metadata(self, collections_data: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        保存合集元数据
        
        Args:
            collections_data: 合集数据
            output_path: 输出路径
            
        Returns:
            保存的文件路径
        """
        if output_path is None:
            output_path = self.metadata_dir / "collections_metadata.json"
        
        # 确保目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 保存数据
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(collections_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"合集元数据已保存到: {output_path}")
        return output_path

def run_step6_video(clips_with_titles_path: Path, collections_path: Path, 
                   input_video: Path, output_dir: Optional[Path] = None, 
                   clips_dir: Optional[str] = None, collections_dir: Optional[str] = None, 
                   metadata_dir: Optional[str] = None) -> Dict:
    """
    运行Step 6: 视频切割
    
    Args:
        clips_with_titles_path: 带标题的片段文件路径
        collections_path: 合集文件路径
        input_video: 输入视频路径
        output_dir: 输出目录
        
    Returns:
        生成结果信息
    """
    # 加载数据
    with open(clips_with_titles_path, 'r', encoding='utf-8') as f:
        clips_with_titles = json.load(f)
    
    with open(collections_path, 'r', encoding='utf-8') as f:
        collections_data = json.load(f)
    
    # 创建视频生成器
    generator = VideoGenerator(clips_dir=clips_dir, collections_dir=collections_dir, metadata_dir=metadata_dir)
    
    # 生成切片视频
    successful_clips = generator.generate_clips(clips_with_titles, input_video)
    
    # 生成合集视频
    successful_collections = generator.generate_collections(collections_data)
    
    # 保存元数据到项目目录
    # 注意：clips_metadata.json在这里保存，包含最终的切片元数据（包含视频路径等信息）
    # 这与step4的step4_titles.json不同，step4只保存带标题的片段数据
    if metadata_dir:
        project_metadata_dir = Path(metadata_dir)
        generator.save_clip_metadata(clips_with_titles, project_metadata_dir / "clips_metadata.json")
        generator.save_collection_metadata(collections_data, project_metadata_dir / "collections_metadata.json")
    else:
        generator.save_clip_metadata(clips_with_titles)
        generator.save_collection_metadata(collections_data)
    
    # 返回结果信息
    result = {
        'clips_generated': len(successful_clips),
        'collections_generated': len(successful_collections),
        'clip_paths': [str(path) for path in successful_clips],
        'collection_paths': [str(path) for path in successful_collections]
    }
    
    logger.info(f"视频生成完成: {result['clips_generated']}个切片, {result['collections_generated']}个合集")
    
    # 保存结果到输出文件
    if output_dir is not None:
        output_path = output_dir / "step6_video_output.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"步骤6结果已保存到: {output_path}")
    
    return result