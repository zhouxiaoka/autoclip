"""
流水线「明确失败」异常。

原则：LLM 不可用、字幕缺失、大纲 / 评分为空、切片没产出文件——这些都必须让项目进 failed 态，
带上阶段和一句用户能照着做的提示；不能吞掉后继续跑成 `Completed · 0 切片`（#100 #11 #24 的共同表象）。
"""

from __future__ import annotations
import re


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
        # 稳定机器码。前端用来打开对应设置页，或避免打开错误的设置页。
        # llm_not_configured：没有可用提供商 / 缺少 API Key / 连接测试没通过
        # whisper_not_installed | whisper_install_failed | transcription_empty | subtitle_setup
        # timeline_empty：有效候选被时长筛选清空（不要再指到「设置 → 模型」）
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
# Legacy fallback when a caller returns [] without Step 2 diagnostics.
# The extractor itself distinguishes request, response and duration failures.
CODE_TIMELINE_EMPTY = "timeline_empty"
HINT_EMPTY_TIMELINE = (
    "短视频里的片段常被最短时长滤掉（短片约 20 秒起），或模型给出的时间戳对不上字幕。"
    "换一条更长、口播更完整的素材后再试。"
)


def empty_timeline_failure(topic_count: int) -> PipelineFailure:
    """旧调用方只返回空列表时的兜底。正常 Step 2 使用本轮报告分类。"""
    return PipelineFailure(
        "ANALYZE",
        f"时间线提取为空：{topic_count} 个话题在对齐并按时长筛选后没有留下可用片段。",
        HINT_EMPTY_TIMELINE,
        code=CODE_TIMELINE_EMPTY,
    )


def model_call_error_code(error: Exception) -> str:
    """Classify without publishing a provider body, URL, credential or local path."""
    status = getattr(error, "status_code", None)
    if status is None:
        status = getattr(error, "code", None)
    if not isinstance(status, int):
        match = re.search(r"(?:status(?:[_ ]code)?|http)\s*[:=]?\s*(\d{3})\b", str(error), re.I)
        status = int(match[1]) if match else None
    if status in (401, 403) or looks_like_llm_setup_error(str(error)):
        return "authentication"
    if status == 429:
        return "rate_limited"
    if status is not None:
        return "provider_error"
    name = type(error).__name__.lower()
    if isinstance(error, TimeoutError) or "timeout" in name:
        return "timeout"
    if isinstance(error, ConnectionError) or "connection" in name:
        return "connection"
    return "provider_error"


def timeline_failure_from_report(topic_count: int, report: dict) -> PipelineFailure:
    """Use current-run observations, not a guess that an empty timeline is short."""
    chunks = report.get("chunks", [])
    if report.get("parsed", 0):
        minimum = report.get("minimum_seconds")
        if minimum is not None:
            return PipelineFailure(
                "ANALYZE",
                f"时间线提取为空：{report['parsed']} 个有效候选在字幕边界校正后均未达到最短时长（{minimum:g} 秒）。",
                "相邻片段合并和补足后仍不够长。请使用口播连续、可形成完整话题的素材；降低评分阈值不会改变时长限制。",
                code=CODE_TIMELINE_EMPTY,
            )
        return empty_timeline_failure(topic_count)
    failed_calls = [chunk for chunk in chunks if chunk.get("outcome") == "call_failed"]
    if failed_calls:
        code = failed_calls[-1]["error_code"]
        hints = {
            "authentication": "请检查「设置 → 模型」中的密钥、模型权限和提供商配置，再测试连接。",
            "rate_limited": "提供商限制了请求频率或额度，请检查配额并稍后重试。",
            "timeout": "模型响应超时，请检查服务和网络后重试；本地模型请确认服务仍在运行。",
            "connection": "无法连接模型服务，请检查接口地址与网络；本地模型请先启动服务后重试。",
            "provider_error": "提供商未完成时间线请求，请检查模型可用性和接口兼容性后重试。",
        }
        return PipelineFailure(
            "ANALYZE", f"时间线模型调用失败：{len(failed_calls)}/{len(chunks)} 个字幕块调用失败，本次没有可用候选。",
            hints[code] + "大纲成功或测试连接成功，不能保证后续长文本请求也成功。", code=code,
        )
    if chunks and all(chunk.get("outcome") == "missing_subtitles" for chunk in chunks):
        return PipelineFailure("ANALYZE", "时间线所需的字幕分块无法读取。",
                               "请重新导入原视频及配套 SRT；保留原项目以便排查。", code="missing_resource")
    if any(chunk.get("outcome") == "chunk_error" for chunk in chunks):
        return PipelineFailure("ANALYZE", "时间线分块处理失败，本次没有可用候选。",
                               "请确认项目数据目录可读写并保留失败阶段反馈；这不是评分阈值问题。", code="unexpected")
    if chunks:
        rejected = {}
        for chunk in chunks:
            for reason, count in chunk.get("rejected", {}).items():
                rejected[reason] = rejected.get(reason, 0) + count
        invalid_ranges = rejected.get("invalid_time", 0) + rejected.get("outside_chunk_or_reversed", 0)
        detail = (f"其中 {invalid_ranges} 个候选的时间戳无效、倒序或不在当前字幕块内。" if invalid_ranges else "")
        cache_hint = "本次回放了项目中的模型缓存，未重新请求模型；请重新导入素材创建新项目再试。" if any(
            chunk.get("source") == "cache" for chunk in chunks
        ) else "请换用能稳定返回结构化时间线的模型后重试；本地模型需支持当前字幕长度。"
        return PipelineFailure(
            "ANALYZE", f"时间线模型回复没有有效时间区间（{topic_count} 个话题，{len(chunks)} 个字幕块）。{detail}",
            cache_hint + "这一步尚未进入评分或最短时长筛选。", code="invalid_response",
        )
    return empty_timeline_failure(topic_count)


def missing_subtitle_failure() -> PipelineFailure:
    """视频没有字幕，自动转写也没留下 srt。按当前 Whisper 状态区分下一步。"""
    from backend.services import whisper_runtime
    from backend.services.ai_model_settings import load
    settings = load()
    if settings and settings.transcription and settings.transcription.provider == 'sensevoice_local':
        return PipelineFailure('SUBTITLE', '没有字幕可分析：SenseVoice 本次没有生成可用字幕。',
                               '到「设置 → 转写」检查 SenseVoiceSmall 是否就绪，或导入 .srt 字幕后重试。',
                               code='subtitle_setup')

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
    if 'SenseVoice' in text:
        return PipelineFailure('SUBTITLE', text,
                               '' if '设置 → 转写' in text else '到「设置 → 转写」检查 SenseVoiceSmall，或导入 .srt 字幕。',
                               code='subtitle_setup')
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
