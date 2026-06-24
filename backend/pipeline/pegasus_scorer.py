"""
Pegasus 语义评分器 - 使用 TwelveLabs Pegasus 视频理解模型，直接对视频片段做语义评分。

这是 Step 3 评分的可选后端（opt-in）。默认的 :class:`ClipScorer`（见 ``step3_scoring.py``）
只读取字幕文本进行打分；而 Pegasus 会真正"看"视频片段的画面与声音，给出更贴近高光
（highlight）质量的评分。两者输出字段完全一致（``final_score`` / ``recommend_reason``），
因此后续步骤无需改动。

启用方式（环境变量）：

    SCORING_BACKEND=pegasus
    TWELVELABS_API_KEY=<your key>     # 免费额度见 https://twelvelabs.io

未配置 ``TWELVELABS_API_KEY`` 时不会启用，流水线回退到默认的字幕评分器。
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from ..core.shared_config import (
    PEGASUS_MAX_TOKENS,
    PEGASUS_MODEL_NAME,
    TWELVELABS_API_KEY,
)
from ..utils.text_processor import TextProcessor

logger = logging.getLogger(__name__)

# 让 Pegasus 直接返回结构化 JSON，省去脆弱的文本解析。
_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "highlight_score",
        "schema": {
            "type": "object",
            "properties": {
                "score": {
                    "type": "number",
                    "description": "0-10 的高光质量评分，10 表示极具传播力。",
                },
                "reason": {
                    "type": "string",
                    "description": "简短的推荐理由（中文）。",
                },
            },
            "required": ["score", "reason"],
        },
    },
}

_PROMPT = (
    "你是一名短视频高光剪辑师。请观看这个视频片段，评估它作为独立短视频高光"
    "的传播潜力（信息密度、情绪张力、画面与表达的吸引力）。"
    "返回 JSON：score 为 0-10 的评分（10 分最高），reason 为一句话中文推荐理由。"
)


class PegasusClipScorer:
    """使用 TwelveLabs Pegasus 对视频片段进行语义高光评分。

    与 :class:`~backend.pipeline.step3_scoring.ClipScorer` 接口一致，
    通过 ``score_clips`` / ``save_scores`` 暴露相同方法，可直接互换。
    """

    def __init__(
        self,
        video_path: Path,
        api_key: Optional[str] = None,
        model_name: str = PEGASUS_MODEL_NAME,
        max_tokens: int = PEGASUS_MAX_TOKENS,
    ):
        self.video_path = Path(video_path)
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.text_processor = TextProcessor()

        api_key = api_key or TWELVELABS_API_KEY
        if not api_key:
            raise ValueError(
                "未配置 TWELVELABS_API_KEY，无法使用 Pegasus 评分后端。"
                "请设置环境变量后重试（免费额度见 https://twelvelabs.io）。"
            )
        if not self.video_path.exists():
            raise FileNotFoundError(f"视频文件不存在，无法使用 Pegasus 评分: {self.video_path}")

        # 延迟导入，避免未启用该后端时强依赖 SDK。
        from twelvelabs import TwelveLabs

        self.client = TwelveLabs(api_key=api_key)
        self._asset_id: Optional[str] = None

    def _ensure_asset(self) -> str:
        """把本地视频上传为 TwelveLabs asset（每个评分器实例只上传一次）。"""
        if self._asset_id is not None:
            return self._asset_id

        logger.info(f"上传视频到 TwelveLabs 以进行 Pegasus 评分: {self.video_path}")
        with open(self.video_path, "rb") as f:
            asset = self.client.assets.create(
                method="direct", file=f, filename=self.video_path.name
            )
        self._asset_id = asset.id
        logger.info(f"视频上传完成，asset_id={self._asset_id}")
        return self._asset_id

    def score_clips(self, timeline_data: List[Dict]) -> List[Dict]:
        """为每个切片调用 Pegasus，写入 ``final_score`` 和 ``recommend_reason``。"""
        if not timeline_data:
            logger.warning("时间线数据为空，无法评分")
            return []

        from twelvelabs.types.video_context import VideoContext_AssetId

        asset_id = self._ensure_asset()
        video = VideoContext_AssetId(asset_id=asset_id)

        logger.info(f"开始使用 Pegasus 为 {len(timeline_data)} 个切片进行语义评分...")
        for clip in timeline_data:
            try:
                start = self.text_processor.time_to_seconds(clip["start_time"])
                end = self.text_processor.time_to_seconds(clip["end_time"])
                res = self.client.analyze(
                    model_name=self.model_name,
                    video=video,
                    prompt=_PROMPT,
                    start_time=start,
                    end_time=end,
                    response_format=_RESPONSE_FORMAT,
                    max_tokens=self.max_tokens,
                )
                score, reason = self._parse_result(res.data)
                clip["final_score"] = round(float(score), 2)
                clip["recommend_reason"] = reason
                logger.info(
                    f"  > Pegasus 评分成功: {start:.1f}-{end:.1f}s [分数: {clip['final_score']}]"
                )
            except Exception as e:  # 单个切片失败不应中断整批
                logger.error(f"  > Pegasus 评分失败 (切片 id={clip.get('id')}): {e}")
                clip["final_score"] = 0.0
                clip["recommend_reason"] = "Pegasus 评估失败"

        timeline_data.sort(key=lambda x: int(x.get("id", 0)))
        logger.info("Pegasus 评分完成")
        return timeline_data

    @staticmethod
    def _parse_result(data: Optional[str]) -> tuple:
        """从 Pegasus 返回的 JSON 字符串中提取 (score, reason)。

        服务端会把 json_schema 的元数据和取值一起返回，这里只取我们关心的字段。
        """
        if not data:
            raise ValueError("Pegasus 返回为空")
        parsed = json.loads(data)
        if "score" not in parsed:
            raise ValueError(f"Pegasus 返回缺少 score 字段: {data[:200]}")
        reason = parsed.get("reason") or "无推荐理由"
        return parsed["score"], reason

    def save_scores(self, scored_clips: List[Dict], output_path: Path):
        """保存评分结果（与默认评分器一致）。"""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(scored_clips, f, ensure_ascii=False, indent=2)
        logger.info(f"评分结果已保存到: {output_path}")
