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
