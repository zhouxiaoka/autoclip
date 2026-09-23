"""
流水线「明确失败」异常。

原则：LLM 不可用、字幕缺失、大纲 / 评分为空、切片没产出文件——这些都必须让项目进 failed 态，
带上阶段和一句用户能照着做的提示；不能吞掉后继续跑成 `Completed · 0 切片`（#100 #11 #24 的共同表象）。
"""

from __future__ import annotations


class PipelineFailure(RuntimeError):
    """带阶段与用户提示的流水线失败。

    stage: 与 simple_progress 的阶段名一致（INGEST / SUBTITLE / ANALYZE / HIGHLIGHT / EXPORT），
           前端失败态与应用内反馈会带上它。
    hint:  用户下一步能做什么（去哪个设置项、装什么），追加在错误正文后面。
    """

    def __init__(self, stage: str, message: str, hint: str = "", code: str = ""):
        super().__init__(message)
        self.stage = stage
        self.hint = hint
        # 稳定机器码。前端用来打开对应设置页。
        # llm_not_configured：没有可用提供商 / 缺少 API Key / 连接测试没通过
        self.code = code

    @property
    def message(self) -> str:
        return str(self.args[0]) if self.args else ""

    def user_message(self) -> str:
        return f"{self.message} {self.hint}".strip()


HINT_CHECK_LLM = "请到「设置 → 模型」检查提供商、API Key 与模型名，点「测试连接」确认后重试。"
# 缺密钥 / 提供商不可用 / 连接测试失败：明确要自备 key，并指到设置里的「模型」。
HINT_BRING_OWN_KEY = (
    "需要自备 API Key（本机 Ollama / LM Studio 则先启动服务）。"
    "到「设置 → 模型」填写提供商、密钥和模型名，点「测试连接」后再试。"
    "密钥在该提供商的控制台申请，只保存在这台机器上。"
)
CODE_LLM_NOT_CONFIGURED = "llm_not_configured"


def looks_like_llm_setup_error(text: str) -> bool:
    """调用模型失败，是因为没有可用密钥 / 连接测试没通过，而不是内容本身。"""
    raw = (text or "").lower()
    needles = (
        "没有可用的 llm",
        "缺少 api key",
        "未配置llm",
        "未配置 api",
        "api key为空",
        "api key 为空",
        "invalid api key",
        "incorrect api key",
        "api连接测试失败",
        "连接测试失败",
        "authentication",
        "unauthorized",
        "missing api key",
        "no api key",
    )
    return any(n in raw for n in needles)


def llm_key_failure(stage: str, message: str) -> PipelineFailure:
    return PipelineFailure(stage, message, HINT_BRING_OWN_KEY, code=CODE_LLM_NOT_CONFIGURED)


HINT_SUBTITLE = "到「设置 → 转写」安装 Whisper 模型让 AutoClip 自动转写，或导入 .srt 字幕后重试。"
HINT_LOWER_THRESHOLD = "到「设置 → 模型 → 最低评分阈值」调低后重试，或换一个更强的模型。"
HINT_CHECK_FFMPEG = "确认 ffmpeg 可用（桌面版内置；Docker / 脚本模式请检查 PATH），以及原视频文件完整可播放。"
