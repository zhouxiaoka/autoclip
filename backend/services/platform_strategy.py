"""One source of truth for platform-oriented video output defaults.

Content discovery decides which moments deserve an output. This module only
describes how an already-selected moment should be packaged for a destination.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Literal

DurationPolicy = Literal["short", "long", "adaptive"]


@dataclass(frozen=True)
class PlatformStrategy:
    id: str
    label: str
    transport: Literal["download_only", "upload_post", "bilibili_direct"]
    transport_platform: str | None
    width: int | None
    height: int | None
    layout: Literal["blur", "crop", "fit", "none"]
    duration_policy: DurationPolicy
    min_recommended_duration_sec: int | None
    # Hard platform limit only (e.g. YouTube Shorts 180 s). Longer outputs are trimmed at a
    # sentence boundary. Platforms that accept long uploads leave this None so content stays whole.
    max_duration_sec: int | None
    subtitle_style: Literal["clean", "bold", "box", "accent"]
    title_style: str
    title_motion: bool
    cover_aspect: Literal["portrait", "landscape", "original"]
    aliases: tuple[str, ...] = ()
    # Typical length that performs well; guidance only, never enforced by trimming.
    recommended_max_duration_sec: int | None = None
    # Automatic packaging: which template wraps the clip, and the language its audience reads.
    template: Literal["interview_zh", "podcast_en", "landscape", "none"] = "none"
    audience_language: Literal["zh", "en"] = "zh"

    @property
    def aspect(self) -> Literal["portrait", "landscape", "original"]:
        if self.width and self.height:
            return "portrait" if self.height > self.width else "landscape"
        return "original"

    def export_spec(self) -> dict[str, object]:
        return {
            "label": self.label,
            "w": self.width,
            "h": self.height,
            "layout": self.layout,
            "max_sec": self.max_duration_sec,
            "strategy_id": self.id,
            "duration_policy": self.duration_policy,
            "min_recommended_duration_sec": self.min_recommended_duration_sec,
            "recommended_max_duration_sec": self.recommended_max_duration_sec,
            "template": self.template,
            "audience_language": self.audience_language,
            "subtitle_style": self.subtitle_style,
            "title_style": self.title_style,
            "title_motion": self.title_motion,
            "cover_aspect": self.cover_aspect,
        }

    def public_summary(self) -> dict[str, object]:
        data = asdict(self)
        data["aliases"] = list(self.aliases)
        data["aspect"] = self.aspect
        return data


_STRATEGIES = (
    # Hard limits checked 2026-09: Douyin uploads up to ~15 min, TikTok up to 60 min, Reels up to
    # 20 min (only <=3 min is recommended to new viewers), YouTube Shorts is capped at 3 min.
    PlatformStrategy("douyin", "抖音 9:16", "download_only", None, 1080, 1920, "blur", "short", 15, None, "accent", "comic", True, "portrait", ("douyin",), 90, "interview_zh", "zh"),
    PlatformStrategy("tiktok", "TikTok 9:16", "upload_post", "tiktok", 1080, 1920, "crop", "short", 15, None, "bold", "comic", True, "portrait", ("tiktok",), 90, "podcast_en", "en"),
    PlatformStrategy("instagram_reels", "Instagram Reels 9:16", "upload_post", "instagram", 1080, 1920, "crop", "short", 15, None, "bold", "card", True, "portrait", ("instagram", "reels"), 180, "podcast_en", "en"),
    PlatformStrategy("youtube_shorts", "YouTube Shorts 9:16", "upload_post", "youtube", 1080, 1920, "crop", "short", 15, 180, "bold", "card", True, "portrait", ("shorts", "youtube_shorts"), 60, "podcast_en", "en"),
    PlatformStrategy("youtube_long", "YouTube 横屏", "upload_post", "youtube", 1920, 1080, "fit", "long", 180, None, "clean", "editorial", False, "landscape", ("youtube_long",), None, "landscape", "en"),
    PlatformStrategy("bilibili", "B站横屏", "bilibili_direct", "bilibili", 1920, 1080, "fit", "adaptive", 180, None, "clean", "editorial", False, "landscape", ("bilibili",), None, "landscape", "zh"),
    PlatformStrategy("xiaohongshu", "小红书 9:16", "download_only", None, 1080, 1920, "blur", "short", 20, None, "box", "card", True, "portrait", ("xiaohongshu",), 90, "interview_zh", "zh"),
    PlatformStrategy("original", "原画重编码", "download_only", None, None, None, "none", "adaptive", None, None, "clean", "plain", False, "original", ("original",)),
)

PLATFORM_STRATEGIES = {strategy.id: strategy for strategy in _STRATEGIES}
_ALIASES = {alias: strategy.id for strategy in _STRATEGIES for alias in strategy.aliases}
LEGACY_PRESET_STRATEGIES = {
    "douyin": "douyin", "xiaohongshu": "xiaohongshu", "shorts": "youtube_shorts",
    "bilibili": "bilibili", "original": "original",
}


def platform_strategy(strategy_id: str) -> PlatformStrategy:
    key = _ALIASES.get(strategy_id.strip().lower(), strategy_id.strip().lower())
    try:
        return PLATFORM_STRATEGIES[key]
    except KeyError as error:
        raise ValueError(f"未知平台策略: {strategy_id}") from error


def normalize_platform_ids(strategy_ids: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    for raw in strategy_ids:
        strategy_id = platform_strategy(str(raw)).id
        if strategy_id not in normalized:
            normalized.append(strategy_id)
    if not normalized:
        raise ValueError("至少要选择一个发布平台")
    return normalized


def strategy_for_legacy_preset(preset: str) -> PlatformStrategy:
    try:
        return platform_strategy(LEGACY_PRESET_STRATEGIES[preset])
    except KeyError as error:
        raise ValueError(f"未知预设: {preset}（可选 {', '.join(LEGACY_PRESET_STRATEGIES)}）") from error


def legacy_export_presets() -> dict[str, dict[str, object]]:
    return {key: strategy_for_legacy_preset(key).export_spec() for key in LEGACY_PRESET_STRATEGIES}


def default_strategy_for_transport(platforms: Iterable[str]) -> PlatformStrategy:
    """Compatibility default for old upload requests without strategy intent."""
    names = {str(platform).strip().lower() for platform in platforms}
    if names & {"tiktok", "instagram", "youtube", "facebook", "threads", "pinterest"}:
        return platform_strategy("youtube_shorts")
    if "bilibili" in names:
        return platform_strategy("bilibili")
    return platform_strategy("original")


def list_platform_strategies() -> list[dict[str, object]]:
    return [strategy.public_summary() for strategy in _STRATEGIES]


VERTICAL_ONLY_TRANSPORTS = frozenset({"tiktok", "instagram"})


def incompatible_transport_platforms(strategy_id: str, platforms: Iterable[str]) -> list[str]:
    """Return upload targets that cannot receive a completed variant of this strategy."""
    if platform_strategy(strategy_id).aspect == "portrait":
        return []
    return [str(p) for p in platforms if str(p).strip().lower() in VERTICAL_ONLY_TRANSPORTS]
