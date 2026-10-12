"""Source checks that run before any model call (RC156 Win QA #10, #11).

The subtitle route needs two things the source either has or does not:
- at least one minimum-length clip of material (`profile_for(...).min_clip_sec`, 20 s for short sources);
- an audio track to transcribe, unless the user attached an SRT.

Both are known as soon as ffprobe can read the file, so a source that cannot
satisfy them fails here with a stable code and a translated sentence instead of
spending screening / clip-finding calls and then failing with timeline_empty or
a Whisper traceback. Both codes describe the user's input, not a bug, so they
are never sent to Sentry (see sentry_setup.UNREPORTED_STUDIO_ERROR_CODES).
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Optional

from backend.pipeline.failures import PipelineFailure
from backend.pipeline.quality import profile_for

logger = logging.getLogger(__name__)

SOURCE_TOO_SHORT = "source_too_short"
SOURCE_NO_AUDIO = "source_no_audio"
SOURCE_INPUT_CODES = frozenset({SOURCE_TOO_SHORT, SOURCE_NO_AUDIO})

# Every source shorter than the minimum is in the "short" tier, whose minimum is this value
# (test_media_precheck keeps the sentence and quality.profile_for in step).
SUBTITLE_MIN_SOURCE_SEC = 20
# These sentences are i18n keys in all eight frontend locales: keep them fixed (no interpolation).
TOO_SHORT_MESSAGE = "视频太短：不到 20 秒，按字幕切不出完整片段。请换一段 20 秒以上的视频。"
NO_AUDIO_MESSAGE = (
    "这个视频没有声音，无法生成字幕。请附上 SRT 字幕后重新导入；"
    "想按画面剪辑，可在「设置 → AI 模型」选用支持图片的模型并开启「画面识别」。"
)
NO_AUDIO_AFTER_SCREENING_MESSAGE = (
    "这个视频没有声音，无法生成字幕，画面判断也没有选出可按画面剪辑的内容。请附上 SRT 字幕后重新导入。"
)
# The visual route ran on a silent source and found nothing usable (RC156 Win QA #19): say why,
# instead of the bare validation sentence 「没有找到可用镜头」.
NO_AUDIO_VISUAL_MESSAGE = (
    "这个视频没有声音，无法生成字幕；按画面识别也没有找到可用片段。请附上 SRT 字幕后重新导入，改按字幕制作。"
)


def probe(video) -> dict:
    """One ffprobe call: {'duration': float | None, 'audio': bool | None}.

    None means "could not tell" (missing ffprobe, unreadable file, no streams); callers
    must not block on an unknown, only on a definite answer.
    """
    unknown = {"duration": None, "audio": None}
    try:
        from backend.utils.ffmpeg_utils import get_ffprobe_path
        result = subprocess.run(
            [get_ffprobe_path(), "-v", "error", "-show_entries", "stream=codec_type:format=duration",
             "-of", "json", str(video)],
            capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=30,
        )
        if result.returncode != 0:
            return unknown
        data = json.loads(result.stdout or "{}")
    except Exception as error:  # noqa: BLE001 - a precheck must never break the run it guards
        logger.debug("media precheck ffprobe unavailable: %s", type(error).__name__)
        return unknown
    if not isinstance(data, dict):
        return unknown
    streams = [row for row in data.get("streams") or [] if isinstance(row, dict)]
    try:
        duration = float((data.get("format") or {}).get("duration"))
    except (TypeError, ValueError, AttributeError):
        duration = None
    audio = any(row.get("codec_type") == "audio" for row in streams) if streams else None
    return {"duration": duration if duration and duration > 0 else None, "audio": audio}


def has_audio(video) -> Optional[bool]:
    return probe(video)["audio"]


def subtitle_minimum_seconds(duration: float) -> float:
    return float(profile_for(duration).min_clip_sec)


def too_short(duration: Optional[float]) -> bool:
    return duration is not None and 0 < duration < subtitle_minimum_seconds(duration)


def too_short_failure(stage: str = "INGEST") -> PipelineFailure:
    return PipelineFailure(stage, TOO_SHORT_MESSAGE, code=SOURCE_TOO_SHORT)


def no_audio_failure(stage: str = "INGEST", *, after_screening: bool = False,
                     after_visual: bool = False) -> PipelineFailure:
    message = (NO_AUDIO_VISUAL_MESSAGE if after_visual
               else NO_AUDIO_AFTER_SCREENING_MESSAGE if after_screening else NO_AUDIO_MESSAGE)
    return PipelineFailure(stage, message, code=SOURCE_NO_AUDIO)


def silent_visual_failure(video, srt_available: bool) -> Optional[PipelineFailure]:
    """The no-audio failure for a visual route that found nothing usable, or None.

    Only a definite "no audio track" without an attached SRT qualifies; an unknown probe keeps
    the original error.
    """
    if srt_available or has_audio(Path(video)) is not False:
        return None
    return no_audio_failure("ANALYZE", after_visual=True)


def subtitle_route_failure(video, *, srt_available: bool, duration: Optional[float] = None,
                           audio: Optional[bool] = None, stage: str = "INGEST") -> Optional[PipelineFailure]:
    """The reason the subtitle route cannot work for this source, or None.

    Pass `duration` / `audio` when the caller already probed; otherwise one ffprobe call fills them in.
    """
    if duration is None or (audio is None and not srt_available):
        info = probe(Path(video))
        duration = duration if duration is not None else info["duration"]
        audio = audio if audio is not None else info["audio"]
    if too_short(duration):
        return too_short_failure(stage)
    if not srt_available and audio is False:
        return no_audio_failure(stage)
    return None


def is_no_audio_text(text: str) -> bool:
    return (text or "").startswith("这个视频没有声音")


# ---------------------------------------------------------------- duration (#345) ---
SOURCE_UNREADABLE = "source_unreadable"
# i18n key in all eight frontend locales: keep it fixed (no interpolation).
UNREADABLE_MESSAGE = (
    "无法读取这个视频的时长，文件可能已损坏、格式不受支持，或路径里有特殊字符。"
    "请换一个文件，或先用其他软件转成 MP4 后重新导入。"
)
TOO_SHORT_1S_MESSAGE = "视频太短：不到 1 秒，无法制作。请换一段更长的视频。"


def sanitize_tool_output(text: str, video=None, limit: int = 600) -> str:
    """Tail of ffprobe/ffmpeg stderr with the source path and user home redacted."""
    import os
    import re
    out = text or ""
    if video is not None:
        for candidate in {str(video), str(Path(video).name), str(Path(video).parent)}:
            if candidate and candidate not in (".", ""):
                out = out.replace(candidate, "<source>")
    home = os.path.expanduser("~")
    if home and home not in ("~", "/"):
        out = out.replace(home, "~")
    out = re.sub(r"(?:[A-Za-z]:)?[\\/](?:[^\s'\"\\/:]+[\\/])+[^\s'\"\\/:]*", "<path>", out)
    return out.strip()[-limit:]


def _ffmpeg_decode_duration(video) -> tuple[Optional[float], str]:
    """Fallback: decode the file with ffmpeg and read the last ``time=``."""
    import re
    try:
        from backend.utils.ffmpeg_utils import get_ffmpeg_path
        result = subprocess.run(
            [get_ffmpeg_path(), "-hide_banner", "-nostdin", "-i", str(video), "-map", "0:v:0?", "-map", "0:a:0?",
             "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=180,
        )
    except Exception as error:  # noqa: BLE001
        return None, f"ffmpeg fallback unavailable: {type(error).__name__}"
    stderr = result.stderr or ""
    times = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
    if times:
        h, m, s = times[-1]
        value = int(h) * 3600 + int(m) * 60 + float(s)
        if value > 0:
            return round(value, 2), stderr
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
    if match:
        h, m, s = match.groups()
        value = int(h) * 3600 + int(m) * 60 + float(s)
        if value > 0:
            return round(value, 2), stderr
    return None, stderr


def probe_duration(video) -> tuple[Optional[float], str]:
    """Duration in seconds or None, plus diagnostics (ffprobe/ffmpeg stderr) when unreadable.

    Tries ffprobe format=duration first, then decodes with ffmpeg (#345: some Windows
    sources report no container duration to ffprobe).
    """
    probe_err = ""
    try:
        from backend.utils.ffmpeg_utils import get_ffprobe_path
        result = subprocess.run(
            [get_ffprobe_path(), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video)],
            capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=30,
        )
        probe_err = result.stderr or ""
        try:
            value = float(((json.loads(result.stdout or "{}") or {}).get("format") or {}).get("duration"))
        except (TypeError, ValueError, AttributeError):
            value = None
        if value and value > 0:
            return round(value, 2), ""
        if not probe_err:
            probe_err = f"ffprobe exit {result.returncode}: no duration"
    except Exception as error:  # noqa: BLE001
        probe_err = f"ffprobe unavailable: {type(error).__name__}"
    logger.warning("ffprobe could not read duration: %s", sanitize_tool_output(probe_err, video, 300))
    value, decode_err = _ffmpeg_decode_duration(video)
    if value:
        logger.info("source duration recovered by ffmpeg decode fallback: %.2fs", value)
        return value, ""
    return None, sanitize_tool_output(f"ffprobe: {probe_err}\nffmpeg: {decode_err}", video)


class SourceUnreadable(PipelineFailure):
    def __init__(self, detail: str, stage: str = "INGEST"):
        super().__init__(stage, UNREADABLE_MESSAGE, code=SOURCE_UNREADABLE)
        self.probe_detail = detail


def duration_or_fail(video, info_duration=None, stage: str = "INGEST") -> float:
    """Readable duration ≥ 1 s, else SourceUnreadable / source_too_short."""
    duration = float(info_duration or 0)
    if duration <= 0:
        found, detail = probe_duration(video)
        if found is None:
            raise SourceUnreadable(detail, stage)
        duration = found
    if duration < 1:
        raise PipelineFailure(stage, TOO_SHORT_1S_MESSAGE, code=SOURCE_TOO_SHORT)
    return duration
