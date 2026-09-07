"""
Step 3: 内容评分 - 对每个话题进行质量评分，筛选出高质量内容
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict

# 导入依赖
from ..utils.llm_client import LLMClient
from ..utils.text_processor import TextProcessor
from ..core.shared_config import PROMPT_FILES, METADATA_DIR, MIN_SCORE_THRESHOLD

logger = logging.getLogger(__name__)

class ClipScorer:
    """内容评分器"""
    
    def __init__(self, prompt_files: Dict = None, metadata_dir: Path = None):
        self.llm_client = LLMClient()
        self.text_processor = TextProcessor()
        self.metadata_dir = Path(metadata_dir) if metadata_dir else None
        
        # 加载提示词
        prompt_files_to_use = prompt_files if prompt_files is not None else PROMPT_FILES
        with open(prompt_files_to_use['recommendation'], 'r', encoding='utf-8') as f:
            self.recommendation_prompt = f.read()

        from .quality import load_srt_chunks
        self._srt_entries = load_srt_chunks(self.metadata_dir) if self.metadata_dir else []
    
    def score_clips(self, timeline_data: List[Dict]) -> List[Dict]:
        """
        为切片评分 (新版：按块批量处理，并使用LLM进行综合评估)
        """
        if not timeline_data:
            logger.warning("时间线数据为空，无法评分")
            return []
            
        logger.info(f"开始为 {len(timeline_data)} 个切片进行批量评分...")
        
        # 1. 按 chunk_index 对所有 timeline 数据进行分组
        timeline_by_chunk = defaultdict(list)
        for item in timeline_data:
            chunk_index = item.get('chunk_index')
            if chunk_index is not None:
                timeline_by_chunk[chunk_index].append(item)
            else:
                logger.warning(f"  > 话题 '{item.get('outline', '未知')}' 缺少 chunk_index，将被跳过。")
        
        all_scored_clips = []
        # 2. 遍历每个块，批量处理其中的所有话题
        for chunk_index, chunk_items in timeline_by_chunk.items():
            logger.info(f"处理块 {chunk_index}，其中包含 {len(chunk_items)} 个话题...")
            try:
                # 3. 使用LLM进行批量评估
                scored_chunk_items = self._get_llm_evaluation(chunk_items)
                
                if scored_chunk_items:
                    all_scored_clips.extend(scored_chunk_items)
                else:
                    logger.warning(f"块 {chunk_index} 的LLM评估返回为空，跳过。")

            except Exception as e:
                logger.error(f"  > 处理块 {chunk_index} 进行评分时出错: {str(e)}")
                continue

        # 4. 按最终得分对所有结果进行排序
        if all_scored_clips:
            all_scored_clips.sort(key=lambda x: x.get('final_score', 0), reverse=True)
            # 保持Step 2分配的固定ID，不再重新分配
            logger.info("按评分排序完成，保持原有固定ID不变")
            
            # 最终按ID排序，确保时间顺序的一致性
            all_scored_clips.sort(key=lambda x: int(x.get('id', 0)))
            logger.info("按ID排序完成，保持时间顺序")
                
        logger.info("所有切片评分完成")
        return all_scored_clips
    
    def _excerpt(self, clip: Dict) -> str:
        if not self._srt_entries:
            return ""
        from .quality import excerpt_between, to_seconds
        try:
            return excerpt_between(self._srt_entries, to_seconds(clip["start_time"]), to_seconds(clip["end_time"]))
        except (KeyError, ValueError, TypeError):
            return ""

    def _get_llm_evaluation(self, clips: List[Dict]) -> List[Dict]:
        """
        使用LLM进行批量评估，为每个clip添加 final_score 和 recommend_reason。
        数量对不上时按 outline 对齐，不再整块丢弃（#11）。
        """
        from .quality import align_scores

        try:
            input_for_llm = [
                {
                    "outline": clip.get('outline'),
                    "content": clip.get('content'),
                    "start_time": clip.get('start_time'),
                    "end_time": clip.get('end_time'),
                    "transcript": self._excerpt(clip),
                } for clip in clips
            ]

            response = self.llm_client.call_with_retry(self.recommendation_prompt, input_for_llm)
            parsed_list = self.llm_client.parse_json_response(response)
            scored, stats = align_scores(clips, parsed_list)
            logger.info(f"  > 评分对齐: 命中 {stats['matched']}，兜底 {stats['fallback']}")
            return scored

        except Exception as e:
            logger.error(f"LLM批量评估失败: {e}")
            scored, _ = align_scores(clips, [])
            return scored

    def save_scores(self, scored_clips: List[Dict], output_path: Path):
        """保存评分结果"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(scored_clips, f, ensure_ascii=False, indent=2)
        logger.info(f"评分结果已保存到: {output_path}")

def run_step3_scoring(timeline_path: Path, metadata_dir: Path = None, output_path: Optional[Path] = None, prompt_files: Dict = None) -> List[Dict]:
    """
    运行Step 3: 内容评分与筛选
    
    Args:
        timeline_path: 时间线文件路径
        output_path: 输出文件路径
        prompt_files: 自定义提示词文件
        
    Returns:
        高分切片列表
    """
    # 加载时间线数据
    with open(timeline_path, 'r', encoding='utf-8') as f:
        timeline_data = json.load(f)
    
    if metadata_dir is None:
        metadata_dir = METADATA_DIR

    from .quality import load_profile, select_clips, save_report

    scorer = ClipScorer(prompt_files, metadata_dir=metadata_dir)
    scored_clips = scorer.score_clips(timeline_data)

    profile = load_profile(metadata_dir)
    high_score_clips, select_info = select_clips(scored_clips, MIN_SCORE_THRESHOLD, profile)
    save_report({"step3": select_info}, metadata_dir)
    logger.info(
        f"评分筛选: 候选 {select_info['candidates']} → 保留 {select_info['selected']}"
        f"（阈值 {MIN_SCORE_THRESHOLD}，兜底补齐 {select_info['fallback_selected']}）"
    )

    all_scored_path = metadata_dir / "step3_all_scored.json"
    scorer.save_scores(scored_clips, all_scored_path)

    if output_path is None:
        output_path = metadata_dir / "step3_high_score_clips.json"
    scorer.save_scores(high_score_clips, output_path)

    return high_score_clips