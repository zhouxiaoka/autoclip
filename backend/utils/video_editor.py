import logging
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from .video_processor import VideoProcessor
from .subtitle_processor import SubtitleProcessor

logger = logging.getLogger(__name__)

class VideoEditor:
    """视频编辑器 - 支持基于字幕删除的视频重新剪辑"""
    
    def __init__(self, clips_dir: Optional[str] = None, collections_dir: Optional[str] = None):
        # VideoEditor 也需要指定路径参数，防止使用全局路径
        if clips_dir is None or collections_dir is None:
            # 如果没有提供路径，使用临时目录（不影响主流水线）
            from ..core.shared_config import CLIPS_DIR, COLLECTIONS_DIR
            clips_dir = str(CLIPS_DIR) if clips_dir is None else clips_dir
            collections_dir = str(COLLECTIONS_DIR) if collections_dir is None else collections_dir
        
        self.video_processor = VideoProcessor(clips_dir=clips_dir, collections_dir=collections_dir)
        self.subtitle_processor = SubtitleProcessor()
    
    def edit_video_by_subtitle_deletion(self, 
                                      video_path: Path,
                                      subtitle_data: List[Dict],
                                      deleted_segments: List[str],
                                      output_path: Path) -> Dict:
        """
        基于字幕删除编辑视频
        
        Args:
            video_path: 原始视频路径
            subtitle_data: 字幕数据
            deleted_segments: 要删除的字幕段ID列表
            output_path: 输出视频路径
            
        Returns:
            编辑结果信息
        """
        try:
            logger.info(f"开始基于字幕删除编辑视频: {video_path}")
            
            # 生成编辑后的时间轴
            timeline = self.subtitle_processor.generate_edited_video_timeline(
                subtitle_data, deleted_segments
            )
            
            if not timeline:
                logger.warning("没有保留的时间段，无法生成视频")
                return {
                    'success': False,
                    'error': '没有保留的时间段'
                }
            
            # 计算删除的总时长
            total_deleted_duration = self._calculate_deleted_duration(
                subtitle_data, deleted_segments
            )
            
            # 执行视频剪辑
            success = self._concatenate_video_segments(
                video_path, timeline, output_path
            )
            
            if success:
                # 获取最终视频时长
                final_duration = self._get_video_duration(output_path)
                
                result = {
                    'success': True,
                    'originalVideoPath': str(video_path),
                    'editedVideoPath': str(output_path),
                    'totalDeletedDuration': total_deleted_duration,
                    'finalDuration': final_duration,
                    'timeline': timeline,
                    'deletedSegments': deleted_segments
                }
                
                logger.info(f"视频编辑完成: 删除时长 {total_deleted_duration:.2f}秒，"
                          f"最终时长 {final_duration:.2f}秒")
                return result
            else:
                return {
                    'success': False,
                    'error': '视频剪辑失败'
                }
                
        except Exception as e:
            logger.error(f"视频编辑失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_deleted_duration(self, subtitle_data: List[Dict], 
                                  deleted_segments: List[str]) -> float:
        """
        计算删除的总时长
        
        Args:
            subtitle_data: 字幕数据
            deleted_segments: 删除的字幕段ID列表
            
        Returns:
            删除的总时长（秒）
        """
        deleted_ids = set(deleted_segments)
        total_duration = 0.0
        
        for segment in subtitle_data:
            if segment['id'] in deleted_ids:
                duration = segment['endTime'] - segment['startTime']
                total_duration += duration
        
        return total_duration
    
    def _concatenate_video_segments(self, video_path: Path, 
                                  timeline: List[Tuple[float, float]], 
                                  output_path: Path) -> bool:
        """
        拼接视频片段
        
        Args:
            video_path: 原始视频路径
            timeline: 时间轴 [(start, end), ...]
            output_path: 输出路径
            
        Returns:
            是否成功
        """
        try:
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            if len(timeline) == 1:
                # 只有一个片段，直接提取
                start_time, end_time = timeline[0]
                return self._extract_single_segment(
                    video_path, start_time, end_time, output_path
                )
            else:
                # 多个片段，需要拼接
                return self._concatenate_multiple_segments(
                    video_path, timeline, output_path
                )
                
        except Exception as e:
            logger.error(f"拼接视频片段失败: {e}")
            return False
    
    def _extract_single_segment(self, video_path: Path, 
                              start_time: float, end_time: float, 
                              output_path: Path) -> bool:
        """
        提取单个视频片段
        
        Args:
            video_path: 原始视频路径
            start_time: 开始时间（秒）
            end_time: 结束时间（秒）
            output_path: 输出路径
            
        Returns:
            是否成功
        """
        try:
            duration = end_time - start_time
            
            cmd = [
                'ffmpeg',
                '-ss', str(start_time),
                '-i', str(video_path),
                '-t', str(duration),
                '-c:v', 'copy',
                '-c:a', 'copy',
                '-avoid_negative_ts', 'make_zero',
                '-y',
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"成功提取视频片段: {start_time:.2f}s - {end_time:.2f}s")
                return True
            else:
                logger.error(f"提取视频片段失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"提取视频片段异常: {e}")
            return False
    
    def _concatenate_multiple_segments(self, video_path: Path, 
                                     timeline: List[Tuple[float, float]], 
                                     output_path: Path) -> bool:
        """
        拼接多个视频片段
        
        Args:
            video_path: 原始视频路径
            timeline: 时间轴 [(start, end), ...]
            output_path: 输出路径
            
        Returns:
            是否成功
        """
        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # 提取所有片段
                segment_files = []
                for i, (start_time, end_time) in enumerate(timeline):
                    segment_file = temp_path / f"segment_{i:03d}.mp4"
                    
                    success = self._extract_single_segment(
                        video_path, start_time, end_time, segment_file
                    )
                    
                    if success:
                        segment_files.append(segment_file)
                    else:
                        logger.error(f"提取片段 {i} 失败")
                        return False
                
                # 创建文件列表
                file_list_path = temp_path / "file_list.txt"
                with open(file_list_path, 'w', encoding='utf-8') as f:
                    for segment_file in segment_files:
                        f.write(f"file '{segment_file}'\n")
                
                # 拼接所有片段
                cmd = [
                    'ffmpeg',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', str(file_list_path),
                    '-c', 'copy',
                    '-y',
                    str(output_path)
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    logger.info(f"成功拼接 {len(segment_files)} 个视频片段")
                    return True
                else:
                    logger.error(f"拼接视频片段失败: {result.stderr}")
                    return False
                    
        except Exception as e:
            logger.error(f"拼接多个视频片段异常: {e}")
            return False
    
    def _get_video_duration(self, video_path: Path) -> float:
        """
        获取视频时长
        
        Args:
            video_path: 视频路径
            
        Returns:
            视频时长（秒）
        """
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                duration = float(result.stdout.strip())
                return duration
            else:
                logger.warning(f"获取视频时长失败: {result.stderr}")
                return 0.0
                
        except Exception as e:
            logger.error(f"获取视频时长异常: {e}")
            return 0.0
    
    def create_preview_clips(self, video_path: Path, 
                           subtitle_data: List[Dict],
                           deleted_segments: List[str],
                           output_dir: Path) -> List[Path]:
        """
        创建预览片段，用于编辑前的预览
        
        Args:
            video_path: 原始视频路径
            subtitle_data: 字幕数据
            deleted_segments: 要删除的字幕段ID列表
            output_dir: 输出目录
            
        Returns:
            预览片段文件路径列表
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            preview_files = []
            
            # 为每个要删除的片段创建预览
            for segment_id in deleted_segments:
                segment = next((s for s in subtitle_data if s['id'] == segment_id), None)
                if segment:
                    preview_file = output_dir / f"preview_{segment_id}.mp4"
                    
                    success = self._extract_single_segment(
                        video_path,
                        segment['startTime'],
                        segment['endTime'],
                        preview_file
                    )
                    
                    if success:
                        preview_files.append(preview_file)
            
            logger.info(f"创建了 {len(preview_files)} 个预览片段")
            return preview_files
            
        except Exception as e:
            logger.error(f"创建预览片段失败: {e}")
            return []
    
    def validate_edit_operations(self, subtitle_data: List[Dict], 
                               deleted_segments: List[str]) -> Dict:
        """
        验证编辑操作的有效性
        
        Args:
            subtitle_data: 字幕数据
            deleted_segments: 要删除的字幕段ID列表
            
        Returns:
            验证结果
        """
        try:
            # 检查删除的字幕段是否存在
            existing_ids = {seg['id'] for seg in subtitle_data}
            deleted_ids = set(deleted_segments)
            
            invalid_ids = deleted_ids - existing_ids
            if invalid_ids:
                return {
                    'valid': False,
                    'error': f'无效的字幕段ID: {list(invalid_ids)}'
                }
            
            # 检查删除后是否还有剩余内容
            remaining_segments = [seg for seg in subtitle_data if seg['id'] not in deleted_ids]
            
            if not remaining_segments:
                return {
                    'valid': False,
                    'error': '删除所有字幕段后没有剩余内容'
                }
            
            # 计算删除的时长
            total_deleted_duration = self._calculate_deleted_duration(
                subtitle_data, deleted_segments
            )
            
            # 计算总时长
            total_duration = max(seg['endTime'] for seg in subtitle_data) - min(seg['startTime'] for seg in subtitle_data)
            
            return {
                'valid': True,
                'totalDuration': total_duration,
                'deletedDuration': total_deleted_duration,
                'remainingDuration': total_duration - total_deleted_duration,
                'deletedSegments': len(deleted_segments),
                'remainingSegments': len(remaining_segments)
            }
            
        except Exception as e:
            logger.error(f"验证编辑操作失败: {e}")
            return {
                'valid': False,
                'error': str(e)
            }
