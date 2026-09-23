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
        # 稳定机器码，前端用来打开「设置 → 转写」并换一句对得上的说明。
        # whisper_not_installed | whisper_install_failed | transcription_empty | subtitle_setup
        self.code = code

    @property
    def message(self) -> str:
        return str(self.args[0]) if self.args else ""

    def user_message(self) -> str:
        return f"{self.message} {self.hint}".strip()


HINT_CHECK_LLM = "请到「设置 → 模型」检查提供商、API Key 与模型名，点「测试连接」确认后重试。"
HINT_SUBTITLE = "到「设置 → 转写」安装 Whisper 模型让 AutoClip 自动转写，或导入 .srt 字幕后重试。"
HINT_LOWER_THRESHOLD = "到「设置 → 模型 → 最低评分阈值」调低后重试，或换一个更强的模型。"
HINT_CHECK_FFMPEG = "确认 ffmpeg 可用（桌面版内置；Docker / 脚本模式请检查 PATH），以及原视频文件完整可播放。"


def missing_subtitle_failure() -> PipelineFailure:
    """视频没有字幕，自动转写也没留下 srt。按当前 Whisper 状态区分下一步。"""
    from backend.services import whisper_runtime

    status = whisper_runtime.get_status()
    state = status.get("status")
    if state == "error":
        return PipelineFailure(
            "SUBTITLE",
            "没有字幕可分析：视频不带字幕，且 Whisper 上次安装没有成功。",
            "到「设置 → 转写」重试安装，或重新导入时带上 .srt 字幕。",
            code="whisper_install_failed",
        )
    if state != "installed":
        return PipelineFailure(
            "SUBTITLE",
            "没有字幕可分析：视频不带字幕，且本地 Whisper 还没安装。",
            "到「设置 → 转写」安装 Whisper 并下载一个模型，或重新导入时带上 .srt 字幕。",
            code="whisper_not_installed",
        )
    return PipelineFailure(
        "SUBTITLE",
        "没有字幕可分析：视频不带字幕，Whisper 已安装，但这次转写没有生成可用字幕。",
        "确认视频里有清晰人声后重试，或重新导入时带上 .srt 字幕。",
        code="transcription_empty",
    )


def failure_from_speech_error(message: str) -> PipelineFailure:
    """转写异常收成同一套失败码，不再把「设置 → 语音识别」和「设置 → 转写」叠在一起。"""
    text = (message or "").strip().replace("设置 → 语音识别", "设置 → 转写")
    from backend.services import whisper_runtime

    state = whisper_runtime.get_status().get("status")
    not_installed = ("未安装" in text) or ("没有可用的语音识别" in text)
    if not_installed:
        if state == "error":
            return missing_subtitle_failure()
        return PipelineFailure(
            "SUBTITLE",
            "没有字幕可分析：视频不带字幕，且本地 Whisper 还没安装。",
            "到「设置 → 转写」安装 Whisper 并下载一个模型，或重新导入时带上 .srt 字幕。",
            code="whisper_not_installed",
        )
    if any(token in text for token in ("未识别出任何语音", "没有从这段视频", "可用语音")):
        return PipelineFailure(
            "SUBTITLE",
            "没有字幕可分析：视频不带字幕，Whisper 已安装，但这次转写没有生成可用字幕。",
            "确认视频里有清晰人声后重试，或重新导入时带上 .srt 字幕。",
            code="transcription_empty",
        )
    hint = "" if "设置 → 转写" in text else HINT_SUBTITLE
    return PipelineFailure("SUBTITLE", text, hint, code="subtitle_setup")
