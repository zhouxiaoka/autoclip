"""
Step 1: 大纲提取 - 从转写文本中提取结构性大纲
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path

# 修复导入问题
try:
    from utils.llm_client import LLMClient
    from utils.text_processor import TextProcessor
    from config import PROMPT_FILES, METADATA_DIR
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    from pathlib import Path
    shared_path = Path(__file__).parent.parent
    if str(shared_path) not in sys.path:
        sys.path.insert(0, str(shared_path))
    from utils.llm_client import LLMClient
    from utils.text_processor import TextProcessor
    from config import PROMPT_FILES, METADATA_DIR

logger = logging.getLogger(__name__)

class OutlineExtractor:
    """大纲提取器（重构版）"""
    
    def __init__(self, metadata_dir: Path = None, prompt_files: Dict = None):
        self.llm_client = LLMClient()
        self.text_processor = TextProcessor()
        
        # 使用传入的metadata_dir或默认值
        if metadata_dir is None:
            metadata_dir = METADATA_DIR
        self.metadata_dir = metadata_dir
        
        # 使用传入的prompt_files或默认值
        if prompt_files is None:
            prompt_files = PROMPT_FILES
        
        # 加载提示词
        with open(prompt_files['outline'], 'r', encoding='utf-8') as f:
            self.outline_prompt = f.read()
            
        # 创建用于存放中间文本块的目录
        self.chunks_dir = self.metadata_dir / "step1_chunks"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        # 创建用于存放中间SRT块的目录
        self.srt_chunks_dir = self.metadata_dir / "step1_srt_chunks"
        self.srt_chunks_dir.mkdir(parents=True, exist_ok=True)

    def extract_outline(self, srt_path: Path) -> List[Dict]:
        """
        从SRT文件提取视频大纲
        
        Args:
            srt_path: SRT文件路径
            
        Returns:
            视频大纲列表
        """
        logger.info("开始提取视频大纲...")
        
        # 1. 解析SRT文件
        try:
            srt_data = self.text_processor.parse_srt(srt_path)
            if not srt_data:
                logger.warning("SRT文件为空或解析失败")
                return []
        except Exception as e:
            logger.error(f"解析SRT文件失败: {e}")
            return []
            
        # 2. 基于时间智能分块
        chunks = self.text_processor.chunk_srt_data(srt_data, interval_minutes=30)
        logger.info(f"文本已按~30分钟/块切分，共{len(chunks)}个块")
        
        # 3. 保存文本块和SRT块到中间文件
        chunk_files = self._save_chunks_to_files(chunks)
        self._save_srt_chunks(chunks)
        
        all_outlines = []
        
        # 4. 逐一处理每个文本块文件
        for i, chunk_file in enumerate(chunk_files):
            logger.info(f"处理第{i+1}/{len(chunks)}个文本块: {chunk_file.name}")
            try:
                # 读取文本块内容
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    chunk_text = f.read()
                
                # 为每个块调用LLM
                input_data = {"text": chunk_text}
                response = self.llm_client.call_with_retry(self.outline_prompt, input_data)
                
                if response:
                    # 解析响应并附加块索引
                    # 注意：这里的chunk_index直接用i，与文件名和原始chunk对应
                    parsed_outlines = self._parse_outline_response(response, i)
                    all_outlines.extend(parsed_outlines)
                else:
                    logger.warning(f"处理第{i+1}个文本块时返回空响应")
            except Exception as e:
                logger.error(f"处理第{i+1}个文本块失败: {e}")
                continue
        
        # 5. 合并和去重
        final_outlines = self._merge_outlines(all_outlines)
        
        logger.info(f"大纲提取完成，共{len(final_outlines)}个话题")
        return final_outlines

    def _save_chunks_to_files(self, chunks: List[Dict]) -> List[Path]:
        """将文本块保存为单独的 .txt 文件"""
        chunk_files = []
        for chunk in chunks:
            chunk_index = chunk['chunk_index']
            text_content = chunk['text']
            file_path = self.chunks_dir / f"chunk_{chunk_index}.txt"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text_content)
            chunk_files.append(file_path)
        
        logger.info(f"所有文本块已保存到: {self.chunks_dir}")
        return chunk_files

    def _save_srt_chunks(self, chunks: List[Dict]):
        """将SRT数据块保存为单独的 .json 文件"""
        for chunk in chunks:
            chunk_index = chunk['chunk_index']
            srt_entries = chunk['srt_entries']
            file_path = self.srt_chunks_dir / f"chunk_{chunk_index}.json"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(srt_entries, f, ensure_ascii=False, indent=2)
        
        logger.info(f"所有SRT块已保存到: {self.srt_chunks_dir}")

    def _parse_outline_response(self, response: str, chunk_index: int) -> List[Dict]:
        """
        解析大模型的大纲响应 (与之前版本保持一致，无质量检查)
        
        Args:
            response: 大模型响应
            chunk_index: 当前处理的块索引
            
        Returns:
            解析后的大纲结构
        """
        outlines = []
        lines = response.split('\n')
        current_outline = None
        
        for line in lines:
            line = line.strip()
            
            if re.match(r'^\d+\.\s*\*\*', line):
                if current_outline:
                    outlines.append(current_outline)
                
                topic_name = line.split('**')[1] if '**' in line else line.split('.', 1)[1].strip()
                current_outline = {
                    'title': topic_name,
                    'subtopics': [],
                    'chunk_index': chunk_index
                }
            
            elif line.startswith('-') and current_outline:
                subtopic = line[1:].strip()
                if subtopic and len(subtopic) <= 200:
                    current_outline['subtopics'].append(subtopic)
        
        if current_outline:
            outlines.append(current_outline)
        
        return outlines
    
    def _merge_outlines(self, outlines: List[Dict]) -> List[Dict]:
        """
        合并和去重大纲，保留最先出现的版本
        """
        unique_outlines = {}
        for outline in outlines:
            title = outline['title']
            if title not in unique_outlines:
                unique_outlines[title] = outline
        return list(unique_outlines.values())
    
    def save_outline(self, outlines: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        保存大纲到文件
        """
        if output_path is None:
            output_path = METADATA_DIR / "step1_outline.json"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(outlines, f, ensure_ascii=False, indent=2)
        
        logger.info(f"大纲已保存到: {output_path}")
        return output_path
    
    def load_outline(self, input_path: Path) -> List[Dict]:
        """
        从文件加载大纲
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            return json.load(f)

def run_step1_outline(srt_path: Path, metadata_dir: Path = None, output_path: Optional[Path] = None, prompt_files: Dict = None) -> List[Dict]:
    """
    运行Step 1: 大纲提取
    """
    if metadata_dir is None:
        metadata_dir = METADATA_DIR
        
    extractor = OutlineExtractor(metadata_dir, prompt_files)
    outlines = extractor.extract_outline(srt_path)
    
    if output_path is None:
        output_path = metadata_dir / "step1_outline.json"
        
    extractor.save_outline(outlines, output_path)
    
    return outlines