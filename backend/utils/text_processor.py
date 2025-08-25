"""
文本处理工具
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

# 修复导入问题
try:
    from core.shared_config import CHUNK_SIZE
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    from pathlib import Path
    backend_path = Path(__file__).parent.parent
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))
    from core.shared_config import CHUNK_SIZE

import pysrt

logger = logging.getLogger(__name__)

class TextProcessor:
    """文本处理工具类"""
    
    @staticmethod
    def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
        """
        将长文本按指定大小分块
        
        Args:
            text: 输入文本
            chunk_size: 分块大小
            
        Returns:
            文本块列表
        """
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        # 按段落分割
        paragraphs = text.split('\n')
        
        for paragraph in paragraphs:
            # 如果当前块加上新段落不超过限制，则添加
            if len(current_chunk) + len(paragraph) + 1 <= chunk_size:
                current_chunk += paragraph + '\n'
            else:
                # 如果当前块不为空，保存它
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                
                # 如果单个段落就超过限制，需要进一步分割
                if len(paragraph) > chunk_size:
                    # 按句子分割
                    sentences = re.split(r'[。！？]', paragraph)
                    temp_chunk = ""
                    for sentence in sentences:
                        if len(temp_chunk) + len(sentence) + 1 <= chunk_size:
                            temp_chunk += sentence + "。"
                        else:
                            if temp_chunk:
                                chunks.append(temp_chunk.strip())
                            temp_chunk = sentence + "。"
                    current_chunk = temp_chunk
                else:
                    current_chunk = paragraph + '\n'
        
        # 添加最后一个块
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def chunk_srt_data(self, srt_data: List[Dict], interval_minutes: int = 30, pause_threshold_ms: int = 1000) -> List[Dict]:
        """
        根据停顿时间，将SRT数据切分为大约相等时间长度的块。
        这可以避免在对话中间断开。

        Args:
            srt_data: SRT数据列表
            interval_minutes: 每个块的目标时间长度（分钟）
            pause_threshold_ms: 识别为停顿的最小毫秒数

        Returns:
            结构化的块列表，其中的 srt_entries 不包含临时处理字段。
        """
        if not srt_data:
            return []

        # 创建一个带有秒数的新列表，而不是修改原始数据
        srt_data_with_seconds = []
        for sub in srt_data:
            entry = sub.copy()
            entry['start_seconds'] = self.time_to_seconds(sub['start_time'])
            entry['end_seconds'] = self.time_to_seconds(sub['end_time'])
            srt_data_with_seconds.append(entry)

        interval_seconds = interval_minutes * 60
        chunks = []
        current_chunk_start_index = 0
        chunk_index = 0
        
        last_cut_time = 0
        
        while current_chunk_start_index < len(srt_data_with_seconds):
            target_cut_time = last_cut_time + interval_seconds
            
            # 寻找接近目标时间的最佳切分点
            best_cut_index = -1
            
            # 查找从当前块开始后的 90% 到 110% 目标时间内的一个停顿
            search_start_index = current_chunk_start_index
            while search_start_index < len(srt_data_with_seconds) and srt_data_with_seconds[search_start_index]['start_seconds'] < target_cut_time * 0.9:
                search_start_index += 1

            # 从搜索起点开始寻找超过阈值的停顿
            for i in range(search_start_index, len(srt_data_with_seconds) - 1):
                current_sub = srt_data_with_seconds[i]
                next_sub = srt_data_with_seconds[i+1]
                
                # 如果我们已经超出了目标时间的110%，就停止搜索
                if current_sub['start_seconds'] > target_cut_time * 1.1:
                    break
                
                # 计算两个字幕条目之间的停顿时间
                pause = next_sub['start_seconds'] - current_sub['end_seconds']
                if pause * 1000 >= pause_threshold_ms:
                    best_cut_index = i + 1  # 在停顿后切分
                    break
            
            # 如果没有找到合适的停顿点，就在目标时间点强制切分
            if best_cut_index == -1:
                # 寻找最接近目标时间的字幕条目
                i = current_chunk_start_index
                while i < len(srt_data_with_seconds) and srt_data_with_seconds[i]['start_seconds'] < target_cut_time:
                    i += 1
                best_cut_index = i if i < len(srt_data_with_seconds) else len(srt_data_with_seconds)

            # 如果切分点无效或过小，则将所有剩余部分作为一个块
            if best_cut_index <= current_chunk_start_index:
                 best_cut_index = len(srt_data_with_seconds)

            # 创建块
            chunk_entries_with_seconds = srt_data_with_seconds[current_chunk_start_index:best_cut_index]
            if not chunk_entries_with_seconds:
                break

            # 移除临时字段，得到干净的srt_entries
            chunk_entries = []
            for entry in chunk_entries_with_seconds:
                clean_entry = entry.copy()
                del clean_entry['start_seconds']
                del clean_entry['end_seconds']
                chunk_entries.append(clean_entry)
            
            start_time = chunk_entries[0]['start_time']
            end_time = chunk_entries[-1]['end_time']
            text = " ".join([entry['text'] for entry in chunk_entries])
            
            chunks.append({
                "chunk_index": chunk_index,
                "text": text,
                "start_time": start_time,
                "end_time": end_time,
                "srt_entries": chunk_entries
            })
            
            chunk_index += 1
            last_cut_time = chunk_entries_with_seconds[-1]['end_seconds']
            current_chunk_start_index = best_cut_index
            
        return chunks

    @staticmethod
    def parse_srt(srt_path: Path) -> List[Dict]:
        """
        解析SRT字幕文件
        
        Args:
            srt_path: SRT文件路径
            
        Returns:
            字幕数据列表，每个元素包含时间戳和文本
        """
        if not srt_path.exists():
            logger.error(f"SRT文件不存在: {srt_path}")
            return []
        
        if srt_path.stat().st_size == 0:
            logger.warning(f"SRT文件为空: {srt_path}")
            return []

        try:
            try:
                subs = pysrt.open(str(srt_path), encoding='utf-8')
            except UnicodeDecodeError:
                logger.warning("UTF-8解码失败，尝试使用 utf-8-sig...")
                subs = pysrt.open(str(srt_path), encoding='utf-8-sig')

            subtitles = []
            for sub in subs:
                subtitles.append({
                    'start_time': str(sub.start),
                    'end_time': str(sub.end),
                    'text': sub.text.strip(),
                    'index': sub.index
                })

            if not subtitles:
                logger.warning(f"成功打开SRT文件但未能解析出任何字幕内容: {srt_path}")
            
            return subtitles
        except Exception as e:
            logger.error(f"使用pysrt解析SRT文件'{srt_path}'时发生未知错误: {e}", exc_info=True)
            return []
    
    @staticmethod
    def extract_text_by_time_range(text: str, srt_data: List[Dict], 
                                  start_time: str, end_time: str) -> str:
        """
        根据时间范围从文本中提取对应内容
        
        Args:
            text: 完整文本
            srt_data: SRT字幕数据
            start_time: 开始时间 (格式: "00:01:25")
            end_time: 结束时间 (格式: "00:02:53")
            
        Returns:
            对应时间范围的文本内容
        """
        # 找到时间范围内的字幕
        target_subtitles = []
        
        for sub in srt_data:
            sub_start = sub['start_time']
            sub_end = sub['end_time']
            
            # 检查时间重叠
            if (sub_start <= end_time and sub_end >= start_time):
                target_subtitles.append(sub)
        
        # 提取对应的文本
        extracted_text = ""
        for sub in target_subtitles:
            extracted_text += sub['text'] + " "
        
        return extracted_text.strip()
    
    @staticmethod
    def time_to_seconds(time_str: str) -> float:
        """
        将SRT时间字符串（HH:MM:SS,mmm）转换为秒数
        
        Args:
            time_str: 时间字符串
            
        Returns:
            秒数
        """
        time_str = time_str.replace(',', '.')
        parts = time_str.split(':')
        
        if len(parts) == 3:
            h = int(parts[0])
            m = int(parts[1])
            s_parts = parts[2].split('.')
            s = int(s_parts[0])
            ms = int(s_parts[1]) if len(s_parts) > 1 else 0
            return h * 3600 + m * 60 + s + ms / 1000.0
        
        raise ValueError(f"无效的时间格式: {time_str}")
    
    @staticmethod
    def seconds_to_time(seconds: float) -> str:
        """
        将秒数转换为时间字符串
        
        Args:
            seconds: 秒数
            
        Returns:
            时间字符串 (格式: "00:01:25")
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}" 