"""Step 3 scoring contract; provider selection remains with LLMClient by default."""
from __future__ import annotations

from typing import Any, Dict, List, Protocol, Sequence, TypedDict


class ScoreResult(TypedDict, total=False):
    id: str
    outline: str
    final_score: float
    recommend_reason: str


class ScoringBackend(Protocol):
    """Evaluate clips identified by id/outline, returning final_score and reason.

    Input includes transcript, content and absolute start/end times. Return a
    JSON-compatible list; scores use 0–1. Missing/invalid results are handled by
    the pipeline's alignment and fallback guards. Implementations must retain
    clip identifiers; they do not select, reorder or cut the source video.
    """

    def score(self, clips: Sequence[Dict[str, Any]]) -> List[ScoreResult]: ...


SCORING_CONTRACT = '''

## 本次评分输出契约（覆盖上文输入/输出示例）
你的任务是评估每个片段的内容价值，依据 transcript 原文、content 和 outline。
返回 JSON 数组，每个输入片段对应一个对象，保留原 id 和 outline：
[{"id":"原 id","outline":"原 outline","final_score":0.8,"recommend_reason":"基于原文的简短理由"}]
final_score 必须是 0 到 1 的有限数值；没有足够内容依据时不要编造高分。
不得只返回 id 到推荐理由的字典，不得省略分数，不要改变 id 或 outline。
'''


class LLMScoringBackend:
    """Current LLM scoring with a consistent schema for every category prompt."""

    def __init__(self, client: Any, prompt: str):
        self.client = client
        self.prompt = prompt + SCORING_CONTRACT

    def score(self, clips: Sequence[Dict[str, Any]]) -> List[ScoreResult]:
        response = self.client.call_with_retry(self.prompt, list(clips))
        results = self.client.parse_json_response(response)
        return results if isinstance(results, list) else []
