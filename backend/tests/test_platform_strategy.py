from backend.services.platform_strategy import (
    legacy_export_presets,
    normalize_platform_ids,
    platform_strategy,
    strategy_for_legacy_preset,
)


def test_normalize_platform_ids_preserves_order_and_aliases():
    assert normalize_platform_ids(["tiktok", "instagram", "reels", "shorts", "youtube_shorts"]) == [
        "tiktok", "instagram_reels", "youtube_shorts",
    ]


def test_short_and_long_youtube_are_distinct_strategies():
    shorts = platform_strategy("youtube_shorts")
    long = platform_strategy("youtube_long")

    assert shorts.transport_platform == long.transport_platform == "youtube"
    assert shorts.aspect == "portrait" and shorts.max_duration_sec == 60
    assert long.aspect == "landscape" and long.min_recommended_duration_sec == 180
    assert long.max_duration_sec is None


def test_legacy_presets_keep_existing_keys_and_render_specs():
    presets = legacy_export_presets()

    assert set(presets) == {"douyin", "xiaohongshu", "shorts", "bilibili", "original"}
    assert presets["shorts"]["strategy_id"] == "youtube_shorts"
    assert presets["shorts"]["max_sec"] == 60
    assert presets["bilibili"]["w"] == 1920
    assert presets["bilibili"]["subtitle_style"] == "clean"
    assert strategy_for_legacy_preset("douyin").id == "douyin"


def test_platform_selection_rejects_empty_or_unknown_values():
    import pytest

    with pytest.raises(ValueError, match="至少要选择"):
        normalize_platform_ids([])
    with pytest.raises(ValueError, match="未知平台策略"):
        normalize_platform_ids(["not-a-platform"])
