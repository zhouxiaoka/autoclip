"""
Step 2: 时间线提取 - 为大纲中的每个话题定位具体时间区间
"""
import json
import logging
import math
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from collections import defaultdict, Counter

# 导入依赖
from ..utils.llm_client import LLMClient
from ..utils.text_processor import TextProcessor
from .quality import to_seconds, to_srt_time, save_report
from .failures import PipelineFailure, model_call_error_code, timeline_failure_from_report
from ..core.shared_config import PROMPT_FILES, METADATA_DIR

logger = logging.getLogger(__name__)

class TimelineExtractor:
    """从大纲和SRT字幕中提取精确时间线"""
    
    def __init__(self, metadata_dir: Path = None, prompt_files: Dict = None):
        self.llm_client = LLMClient()
        self.text_processor = TextProcessor()
        
        # 使用传入的metadata_dir或默认值
        if metadata_dir is None:
            metadata_dir = METADATA_DIR
        self.metadata_dir = metadata_dir
        
        # 加载提示词
        prompt_files_to_use = prompt_files if prompt_files is not None else PROMPT_FILES
        with open(prompt_files_to_use['timeline'], 'r', encoding='utf-8') as f:
            self.timeline_prompt = f.read()
            
        # SRT块的目录
        self.srt_chunks_dir = self.metadata_dir / "step1_srt_chunks"
        self.timeline_chunks_dir = self.metadata_dir / "step2_timeline_chunks"
        self.llm_raw_output_dir = self.metadata_dir / "step2_llm_raw_output"

    def extract_timeline(self, outlines: List[Dict]) -> List[Dict]:
        """
        提取话题时间区间。
        新版特性：
        - 基于预先分块的SRT
        - 按块批量处理
        - 缓存原始LLM响应，避免重复调用
        - 保存每个块的处理结果作为中间文件，增强健壮性
        """
        logger.info("开始提取话题时间区间...")
        # Counts and stable codes only: safe to share without subtitles, keys or paths.
        self.extraction_report = {"topics": len(outlines), "chunks": [], "parsed": 0, "output": 0}
        # Clear this stage's previous-run result before any early failure.
        save_report({"step2": {"input": 0, "output": 0, "dropped": [], "merged": [],
                               "extended": 0, "trimmed": 0},
                     "step2_extraction": self.extraction_report}, self.metadata_dir)
        
        if not outlines:
            logger.warning("大纲数据为空，无法提取时间线。")
            save_report({"step2_extraction": self.extraction_report}, self.metadata_dir)
            return []

        if not self.srt_chunks_dir.exists():
            logger.error(f"SRT块目录不存在: {self.srt_chunks_dir}。请先运行Step 1。")
            self.extraction_report["chunks"] = [{"outcome": "missing_subtitles"}]
            save_report({"step2_extraction": self.extraction_report}, self.metadata_dir)
            return []

        # 1. 创建本步骤需要的目录
        self.timeline_chunks_dir.mkdir(parents=True, exist_ok=True)
        self.llm_raw_output_dir.mkdir(parents=True, exist_ok=True)

        # 时长画像追加到提示词（覆盖提示词里写死的 90 秒 / 3–6 分钟）
        from .quality import load_profile
        profile = load_profile(self.metadata_dir)
        timeline_prompt = self.timeline_prompt + (profile.prompt_hint() if profile else "")

        # 2. 按 chunk_index 对所有大纲进行分组
        outlines_by_chunk = defaultdict(list)
        for outline in outlines:
            chunk_index = outline.get('chunk_index')
            if chunk_index is not None:
                outlines_by_chunk[chunk_index].append(outline)
            else:
                self.extraction_report["chunks"].append({"outcome": "missing_subtitles", "topics": 1})
                logger.warning(f"  > 话题 '{outline.get('title', '未知')}' 缺少 chunk_index，将被跳过。")

        all_timeline_data = []
        current_srt_entries = []
        # 3. 每个块独立调用模型（并行），结果按块顺序合并，并存为独立的JSON文件
        import threading
        from .concurrency import map_chunks
        parse_lock = threading.Lock()

        def timeline_chunk(item):
            chunk_index, chunk_outlines = item
            srt_entries, parsed = [], []
            logger.info(f"处理块 {chunk_index}，其中包含 {len(chunk_outlines)} 个话题...")
            chunk_report = {"index": chunk_index, "topics": len(chunk_outlines),
                            "attempts": 0, "outcome": "missing_subtitles"}
            
            # 结果文件只用于诊断；本次返回值仅由本次验证成功的块组成
            chunk_output_path = self.timeline_chunks_dir / f"chunk_{chunk_index}.json"

            try:
                # 首先加载对应的SRT块文件，无论是否使用缓存都需要这些信息
                srt_chunk_path = self.srt_chunks_dir / f"chunk_{chunk_index}.json"
                if not srt_chunk_path.exists():
                    logger.warning(f"  > 找不到对应的SRT块文件: {srt_chunk_path}，跳过整个块。")
                    return chunk_report, srt_entries, parsed
                
                with open(srt_chunk_path, 'r', encoding='utf-8') as f:
                    srt_chunk_data = json.load(f)

                if not srt_chunk_data:
                    logger.warning(f"  > SRT块文件为空: {srt_chunk_path}，跳过整个块。")
                    return chunk_report, srt_entries, parsed

                # 获取时间范围信息
                chunk_start_time = srt_chunk_data[0]['start_time']
                chunk_end_time = srt_chunk_data[-1]['end_time']

                srt_entries = srt_chunk_data
                llm_cache_path = self.llm_raw_output_dir / f"chunk_{chunk_index}.txt"
                cached = llm_cache_path.exists()
                chunk_report["source"] = "cache" if cached else "model"
                input_data = {
                    "outline": [{"title": o.get("title"), "subtopics": o.get("subtopics")} for o in chunk_outlines],
                    "srt_text": "\n\n".join(
                        f"{sub['index']}\n{sub['start_time']} --> {sub['end_time']}\n{sub['text']}"
                        for sub in srt_chunk_data
                    ),
                }
                # Cache replay follows the same parser. An invalid cache is a
                # failed chunk, never permission to silently make a paid call.
                attempts = 1 if cached else 3
                for retry_count in range(attempts):
                    raw_response = ""
                    try:
                        chunk_report["attempts"] += 1
                        if cached:
                            raw_response = llm_cache_path.read_text(encoding='utf-8')
                        else:
                            try:
                                raw_response = self.llm_client.call_with_retry(timeline_prompt, input_data)
                            except Exception as call_error:
                                # The client already retries transport failures. Do not
                                # multiply its request budget by the JSON repair loop.
                                chunk_report.update(outcome="call_failed", error_code=model_call_error_code(call_error))
                                logger.error("块 %s 模型调用失败: %s", chunk_index, call_error)
                                break
                            if raw_response:
                                cache_file = self.llm_raw_output_dir / f"chunk_{chunk_index}_attempt_{retry_count}.txt"
                                cache_file.write_text(raw_response, encoding='utf-8')
                        if not raw_response:
                            chunk_report["outcome"] = "empty_response"
                            logger.warning("块 %s 响应为空，跳过", chunk_index)
                            break
                        with parse_lock:  # the parser reports through instance state
                            parsed_items = self._parse_and_validate_response(
                                raw_response, chunk_start_time, chunk_end_time, chunk_index
                            )
                            chunk_report.update(self._last_parse_diagnostics)
                        if parsed_items:
                            chunk_report["outcome"] = "parsed"
                            chunk_output_path.write_text(
                                json.dumps(parsed_items, ensure_ascii=False, indent=2), encoding='utf-8'
                            )
                            parsed = parsed_items
                            break
                        input_data['additional_instruction'] = (
                            "仅返回有效 JSON 数组，使用英文双引号；起止时间必须引用当前字幕块，结束晚于开始。"
                        )
                    except Exception as parse_error:
                        chunk_report["outcome"] = "chunk_error"
                        logger.error("块 %s 第 %s 次解析失败: %s", chunk_index, retry_count + 1, parse_error)
                    if retry_count == attempts - 1:
                        self._save_debug_response(raw_response, chunk_index, "final_parse_failure")
                        logger.warning("块 %s 无有效时间线%s", chunk_index, "（缓存无效）" if cached else "")

            except Exception as e:
                chunk_report["outcome"] = "chunk_error"
                logger.error(f"  > 处理块 {chunk_index} 时出错: {str(e)}")
                return chunk_report, srt_entries, parsed
            return chunk_report, srt_entries, parsed

        for chunk_report, srt_entries, parsed in map_chunks(timeline_chunk, outlines_by_chunk.items()):
            self.extraction_report["chunks"].append(chunk_report)
            current_srt_entries.extend(srt_entries)
            all_timeline_data.extend(parsed)
        
        logger.info("本次成功提取 %s 个话题。", len(all_timeline_data))
        self.extraction_report["parsed"] = len(all_timeline_data)

        # 最终排序：在返回所有结果前，按开始时间进行全局排序
        if all_timeline_data:
            logger.info("按开始时间对所有话题进行最终排序...")
            try:
                # 使用 text_processor 将时间字符串转换为秒数以便正确排序
                all_timeline_data.sort(key=lambda x: self.text_processor.time_to_seconds(x['start_time']))
                logger.info("排序完成。")
                
                # 为所有片段按时间顺序分配固定的ID
                logger.info("为所有片段按时间顺序分配固定ID...")
                for i, timeline_item in enumerate(all_timeline_data):
                    timeline_item['id'] = str(i + 1)
                logger.info(f"已为 {len(all_timeline_data)} 个片段分配了固定ID（1-{len(all_timeline_data)}）")
                
            except Exception as e:
                logger.error(f"对最终结果排序时出错: {e}。返回未排序的结果。")

        # 5. 程序化校正：对齐字幕边界 / 时长上下限 / 去重合并（docs/QUALITY_AND_PUBLISH_PLAN.md 线 1-B）
        if all_timeline_data:
            try:
                from .quality import refine_timeline
                srt_entries = sorted(current_srt_entries, key=lambda cue: to_seconds(cue["start_time"]))
                refined, report = refine_timeline(all_timeline_data, srt_entries, profile)
                save_report({"step2": report}, self.metadata_dir)
                self.extraction_report["minimum_seconds"] = report["profile"]["min_clip_sec"]
                self.extraction_report["total_seconds"] = report["profile"]["total_sec"]
                self.extraction_report["filtered"] = len(report["dropped"])
                logger.info(
                    f"时间线校正: {report['input']} → {report['output']} 段，"
                    f"合并 {len(report['merged'])}，丢弃 {len(report['dropped'])}，"
                    f"延长 {report['extended']}，截断 {report['trimmed']}，"
                    f"吸附偏移 p90={report.get('snap_offset_p90', 0)}s"
                )
                all_timeline_data = refined
            except Exception as e:  # noqa: BLE001
                logger.error("时间线校正失败: %s", e)
                self.extraction_report["refinement_failed"] = True
                save_report({"step2_extraction": self.extraction_report}, self.metadata_dir)
                raise PipelineFailure("ANALYZE", "时间线字幕边界校正失败，本次未导出未经校验的片段。",
                                      "原素材已保留，请提交失败阶段反馈以便排查。", code="unexpected") from e

        self.extraction_report["output"] = len(all_timeline_data)
        save_report({"step2_extraction": self.extraction_report}, self.metadata_dir)
        return all_timeline_data
        
    def _parse_and_validate_response(self, response: str, chunk_start: str, chunk_end: str, chunk_index: int) -> List[Dict]:
        """增强的解析LLM的批量响应、验证并调整时间"""
        validated_items = []
        reasons = Counter()
        self._last_parse_diagnostics = {"outcome": "invalid_response", "rejected": reasons}
        
        # 保存原始响应用于调试
        self._save_debug_response(response, chunk_index, "original_response")
        
        try:
            # 尝试解析JSON
            parsed_response = self.llm_client.parse_json_response(response)
            # Compatible endpoints sometimes retain the input envelope or omit
            # the array around one topic. Accept only unambiguous known shapes.
            if isinstance(parsed_response, dict):
                arrays = [parsed_response[key] for key in ("timeline", "outline")
                          if isinstance(parsed_response.get(key), list)]
                if len(arrays) == 1:
                    parsed_response = arrays[0]
                elif not arrays and all(key in parsed_response for key in ("start_time", "end_time")):
                    parsed_response = [parsed_response]
            
            if not isinstance(parsed_response, list):
                reasons["invalid_container"] += 1
                logger.warning(f"  > 块 {chunk_index} LLM返回的不是一个列表")
                self._save_debug_response(f"类型: {type(parsed_response)}, 内容: {parsed_response}", chunk_index, "not_list")
                return []
            self._last_parse_diagnostics["outcome"] = "no_valid_ranges"
            if not parsed_response:
                reasons["empty_array"] += 1
            
            for raw_item in parsed_response:
                if not isinstance(raw_item, dict):
                    reasons["non_object"] += 1
                    continue
                timeline_item = dict(raw_item)
                # Some models preserve the input title instead of renaming it.
                if 'outline' not in timeline_item and isinstance(timeline_item.get('title'), str):
                    timeline_item['outline'] = timeline_item['title']
                if 'outline' not in timeline_item or 'start_time' not in timeline_item or 'end_time' not in timeline_item:
                    reasons["missing_fields"] += 1
                    logger.warning(f"  > 从LLM返回的某个JSON对象格式不正确: {timeline_item}")
                    continue
                
                # 将 chunk_index 添加回对象中，以便后续步骤使用
                timeline_item['chunk_index'] = chunk_index
                
                # 验证和调整时间范围
                try:
                    # 验证时间格式
                    if not self._validate_time_format(timeline_item['start_time']):
                        reasons["invalid_time"] += 1
                        logger.warning(f"  > 话题 '{timeline_item['outline']}' 开始时间格式不正确: {timeline_item['start_time']}")
                        continue
                    
                    if not self._validate_time_format(timeline_item['end_time']):
                        reasons["invalid_time"] += 1
                        logger.warning(f"  > 话题 '{timeline_item['outline']}' 结束时间格式不正确: {timeline_item['end_time']}")
                        continue
                    
                    start_sec = self._timeline_seconds(timeline_item['start_time'])
                    end_sec = self._timeline_seconds(timeline_item['end_time'])
                    chunk_start_sec = to_seconds(chunk_start)
                    chunk_end_sec = to_seconds(chunk_end)
                    start_sec = max(start_sec, chunk_start_sec)
                    end_sec = min(end_sec, chunk_end_sec)
                    if end_sec <= start_sec:
                        reasons["outside_chunk_or_reversed"] += 1
                        logger.warning("  > 时间区间倒序或不在当前字幕块内，跳过: %s", timeline_item)
                        continue
                    # Normalize before downstream sorting: .5 means half a second,
                    # not five milliseconds, and MM:SS must gain the hours field.
                    timeline_item['start_time'] = to_srt_time(start_sec)
                    timeline_item['end_time'] = to_srt_time(end_sec)

                    logger.info(f"  > 定位成功: {timeline_item['outline']} ({timeline_item['start_time']} -> {timeline_item['end_time']})")
                    validated_items.append(timeline_item)
                except Exception as e:
                    reasons["invalid_time"] += 1
                    logger.error(f"  > 验证单个时间戳时出错: {e} - 项目: {timeline_item}")
                    continue
            
            return validated_items

        except Exception as e:
            reasons["malformed_json"] += 1
            logger.error(f"  > 块 {chunk_index} 解析LLM响应时出错: {e}")
            # 保存详细的错误信息
            error_info = {
                "error": str(e),
                "error_type": type(e).__name__,
                "response_length": len(response),
                "response_preview": response[:200],
                "chunk_index": chunk_index,
                "chunk_start": chunk_start,
                "chunk_end": chunk_end
            }
            import json
            self._save_debug_response(json.dumps(error_info, indent=2, ensure_ascii=False), chunk_index, "parse_error")
            return []

    @staticmethod
    def _timeline_seconds(value: Any) -> float:
        if isinstance(value, bool):
            raise ValueError("boolean is not a timestamp")
        if isinstance(value, (int, float)):
            result = float(value)
        elif isinstance(value, str):
            value = value.strip()
            if re.fullmatch(r'\d+(?:[.,]\d{1,3})?', value):
                result = float(value.replace(',', '.'))
            elif re.fullmatch(r'\d+:[0-5]\d(?:[,.]\d{1,3})?', value):
                result = to_seconds(value)
            elif re.fullmatch(r'\d+:[0-5]\d:[0-5]\d(?:[,.]\d{1,3})?', value):
                result = to_seconds(value)
            else:
                raise ValueError("invalid timestamp")
        else:
            raise ValueError("invalid timestamp type")
        if not math.isfinite(result) or result < 0:
            raise ValueError("invalid timestamp range")
        return result

    def _validate_time_format(self, time_str: Any) -> bool:
        try:
            self._timeline_seconds(time_str)
            return True
        except (ValueError, TypeError):
            return False

    def _convert_time_format(self, time_str: str) -> str:
        """
        转换时间格式：SRT格式 -> FFmpeg格式
        """
        if not time_str or time_str == "end":
            return time_str
        return time_str.replace(',', '.')

    def _save_debug_response(self, response: str, chunk_index: int, error_type: str) -> None:
        """保存调试响应到文件"""
        try:
            debug_dir = self.metadata_dir / "debug_responses"
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_dir / f"chunk_{chunk_index}_{error_type}.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response)
            logger.info(f"调试响应已保存到: {debug_file}")
        except Exception as e:
            logger.error(f"保存调试响应失败: {e}")

    def save_timeline(self, timeline_data: List[Dict], output_path: Optional[Path] = None) -> Path:
        """
        保存时间区间数据
        """
        if output_path is None:
            output_path = METADATA_DIR / "step2_timeline.json"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(timeline_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"时间数据已保存到: {output_path}")
        return output_path

    def load_timeline(self, input_path: Path) -> List[Dict]:
        """
        从文件加载时间数据
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            return json.load(f)

def run_step2_timeline(outline_path: Path, metadata_dir: Path = None, output_path: Optional[Path] = None, prompt_files: Dict = None) -> List[Dict]:
    """
    运行Step 2: 时间点提取
    """
    if metadata_dir is None:
        metadata_dir = METADATA_DIR
        
    extractor = TimelineExtractor(metadata_dir, prompt_files)
    
    # 加载大纲
    with open(outline_path, 'r', encoding='utf-8') as f:
        outlines = json.load(f)
        
    timeline_data = extractor.extract_timeline(outlines)
    
    # 保存结果
    if output_path is None:
        output_path = metadata_dir / "step2_timeline.json"
        
    extractor.save_timeline(timeline_data, output_path)
    if not timeline_data:
        raise timeline_failure_from_report(len(outlines), extractor.extraction_report)
    
    return timeline_data
