"""
视频缩略图生成工具
"""
import subprocess
import logging
from pathlib import Path
from typing import Optional
import base64
from PIL import Image
import io

logger = logging.getLogger(__name__)

class ThumbnailGenerator:
    """视频缩略图生成器"""
    
    def __init__(self):
        self.supported_formats = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv']
    
    def generate_thumbnail(self, video_path: Path, output_path: Optional[Path] = None, 
                          time_offset: Optional[float] = None, width: int = 320, height: int = 180) -> Optional[Path]:
        """
        生成视频缩略图 - 使用智能帧选择策略
        
        Args:
            video_path: 视频文件路径
            output_path: 输出缩略图路径，如果为None则自动生成
            time_offset: 提取时间点（秒），如果为None则自动选择最佳时间点
            width: 缩略图宽度
            height: 缩略图高度
            
        Returns:
            生成的缩略图路径，失败返回None
        """
        try:
            if not video_path.exists():
                logger.error(f"视频文件不存在: {video_path}")
                return None
            
            # 检查文件格式
            if video_path.suffix.lower() not in self.supported_formats:
                logger.error(f"不支持的视频格式: {video_path.suffix}")
                return None
            
            # 生成输出路径
            if output_path is None:
                output_path = video_path.parent / f"{video_path.stem}_thumbnail.jpg"
            
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 智能选择时间点
            if time_offset is None:
                time_offset = self._get_optimal_thumbnail_time(video_path)
            
            # 检查是否使用视频封面
            if time_offset == -1.0:
                # 使用视频封面
                cover_path = video_path.parent / f"{video_path.stem}_cover.jpg"
                if cover_path.exists():
                    # 直接复制封面文件并调整大小
                    cmd = [
                        'ffmpeg',
                        '-i', str(cover_path),
                        '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black',
                        '-q:v', '2',
                        '-y',
                        str(output_path)
                    ]
                    logger.info(f"使用视频封面生成缩略图: {cover_path} -> {output_path}")
                else:
                    # 封面不存在，回退到默认时间点
                    time_offset = 1.0
                    cmd = [
                        'ffmpeg',
                        '-ss', str(time_offset),
                        '-i', str(video_path),
                        '-vframes', '1',
                        '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black',
                        '-q:v', '2',
                        '-y',
                        str(output_path)
                    ]
                    logger.info(f"封面不存在，回退到默认时间点: {time_offset}秒")
            else:
                # 使用指定时间点
                logger.info(f"为视频 {video_path.name} 选择缩略图时间点: {time_offset}秒")
                cmd = [
                    'ffmpeg',
                    '-ss', str(time_offset),  # 跳转到指定时间
                    '-i', str(video_path),    # 输入视频
                    '-vframes', '1',          # 只提取一帧
                    '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black',  # 缩放并居中
                    '-q:v', '2',              # 高质量
                    '-y',                     # 覆盖输出文件
                    str(output_path)
                ]
            
            logger.info(f"生成缩略图: {video_path} -> {output_path}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"缩略图生成成功: {output_path}")
                return output_path
            else:
                logger.error(f"缩略图生成失败: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            logger.error(f"缩略图生成超时: {video_path}")
            return None
        except Exception as e:
            logger.error(f"缩略图生成异常: {e}")
            return None
    
    def _extract_video_cover(self, video_path: Path) -> Optional[Path]:
        """
        尝试提取视频的封面图片
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            封面图片路径，如果不存在则返回None
        """
        try:
            # 检查是否有嵌入的封面图片
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-an',  # 禁用音频
                '-vcodec', 'copy',  # 复制视频流
                '-f', 'image2',
                '-vframes', '1',
                '-y',
                str(video_path.parent / f"{video_path.stem}_cover.jpg")
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                cover_path = video_path.parent / f"{video_path.stem}_cover.jpg"
                if cover_path.exists() and cover_path.stat().st_size > 0:
                    logger.info(f"成功提取视频封面: {cover_path}")
                    return cover_path
            
            return None
            
        except Exception as e:
            logger.debug(f"提取视频封面失败: {e}")
            return None
    
    def _get_optimal_thumbnail_time(self, video_path: Path) -> float:
        """
        智能选择最佳的缩略图时间点
        
        策略：
        1. 优先尝试提取视频封面（如果存在）
        2. 如果视频很短（<30秒），选择中间位置
        3. 如果视频中等长度（30秒-5分钟），选择10%位置
        4. 如果视频很长（>5分钟），选择5%位置
        5. 避免选择开头和结尾，因为这些位置通常是黑屏或过渡
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            最佳时间点（秒）
        """
        try:
            # 首先尝试提取视频封面
            cover_path = self._extract_video_cover(video_path)
            if cover_path:
                logger.info(f"使用视频封面作为缩略图: {cover_path}")
                # 如果成功提取封面，返回一个特殊值表示使用封面
                return -1.0  # 特殊值，表示使用封面
            
            # 获取视频信息
            video_info = self.get_video_info(video_path)
            if not video_info:
                logger.warning(f"无法获取视频信息，使用默认时间点: {video_path}")
                return 1.0
            
            # 获取视频时长
            duration = float(video_info.get('format', {}).get('duration', 0))
            if duration <= 0:
                logger.warning(f"视频时长为0，使用默认时间点: {video_path}")
                return 1.0
            
            logger.info(f"视频时长: {duration}秒")
            
            # 智能选择时间点
            if duration < 30:
                # 短视频：选择中间位置
                optimal_time = duration * 0.5
            elif duration < 300:  # 5分钟
                # 中等长度：选择10%位置，避免开头可能的黑屏
                optimal_time = duration * 0.1
            else:
                # 长视频：选择5%位置
                optimal_time = duration * 0.05
            
            # 确保时间点合理（至少1秒，最多不超过视频长度）
            optimal_time = max(1.0, min(optimal_time, duration - 1))
            
            logger.info(f"为视频 {video_path.name} 选择最佳时间点: {optimal_time}秒 (总时长: {duration}秒)")
            return optimal_time
            
        except Exception as e:
            logger.error(f"选择最佳时间点失败: {e}")
            return 1.0
    
    def generate_thumbnail_base64(self, video_path: Path, time_offset: Optional[float] = None, 
                                 width: int = 320, height: int = 180) -> Optional[str]:
        """
        生成缩略图并返回base64编码
        
        Args:
            video_path: 视频文件路径
            time_offset: 提取时间点（秒），如果为None则自动选择最佳时间点
            width: 缩略图宽度
            height: 缩略图高度
            
        Returns:
            base64编码的缩略图数据，失败返回None
        """
        try:
            # 生成临时缩略图
            temp_path = video_path.parent / f"temp_thumbnail_{video_path.stem}.jpg"
            thumbnail_path = self.generate_thumbnail(video_path, temp_path, time_offset, width, height)
            
            if thumbnail_path and thumbnail_path.exists():
                # 读取图片并转换为base64
                with open(thumbnail_path, 'rb') as f:
                    image_data = f.read()
                    base64_data = base64.b64encode(image_data).decode('utf-8')
                
                # 清理临时文件
                try:
                    temp_path.unlink()
                except:
                    pass
                
                return f"data:image/jpeg;base64,{base64_data}"
            else:
                return None
                
        except Exception as e:
            logger.error(f"生成base64缩略图失败: {e}")
            return None
    
    def get_video_info(self, video_path: Path) -> Optional[dict]:
        """
        获取视频信息
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            视频信息字典，失败返回None
        """
        try:
            if not video_path.exists():
                return None
            
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                import json
                return json.loads(result.stdout)
            else:
                logger.error(f"获取视频信息失败: {result.stderr}")
                return None
                
        except Exception as e:
            logger.error(f"获取视频信息异常: {e}")
            return None

# 便捷函数
def generate_project_thumbnail(project_id: str, video_path: Path) -> Optional[str]:
    """
    为项目生成缩略图
    
    Args:
        project_id: 项目ID
        video_path: 视频文件路径
        
    Returns:
        base64编码的缩略图数据
    """
    generator = ThumbnailGenerator()
    return generator.generate_thumbnail_base64(video_path)

