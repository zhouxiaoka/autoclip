"""v1.6.3 regressions from real Xiaohongshu creator review (v1.6.1 mobile livestream test):
1. autoclip doctor / environment_report must verify ffmpeg has libass (subtitles/ass filter)
   instead of reporting green for Homebrew ffmpeg without libass.
2. Portrait full-bleed interview packaging must place TagPill / nameplate well above the
   2-line CaptionBox (y=1420 bottom-aligned) so opening yellow badges never overlap subtitles.
3. Auto cover headlines must strip leading ASR fillers and single-character stutters
   (e.g. '法把法律当傻子' -> '把法律当傻子') without truncating the start of valid words.
"""
from __future__ import annotations

import re
import types

from backend.services import local_runner
from backend.services.studio import cover_design, packaging_render
from backend.services.studio.models import Packaging, Scene


def test_environment_report_fails_when_ffmpeg_lacks_libass(monkeypatch):
    monkeypatch.setattr("backend.utils.ffmpeg_utils.get_ffmpeg_path", lambda: "/opt/homebrew/bin/ffmpeg")
    monkeypatch.setattr(local_runner.Path, "exists", lambda self: True)
    monkeypatch.setattr(local_runner, "_ffmpeg_has_libass", lambda ff: False)
    monkeypatch.setattr(local_runner, "check_llm_connection", lambda: {"ok": True, "provider": "deepseek", "model": "deepseek-flash"})

    rep = local_runner.environment_report()
    assert rep["ffmpeg"]["ok"] is False
    assert rep["ffmpeg"]["libass"] is False
    assert "libass" in rep["ffmpeg"]["error"]


def test_environment_report_passes_when_ffmpeg_has_libass(monkeypatch):
    monkeypatch.setattr("backend.utils.ffmpeg_utils.get_ffmpeg_path", lambda: "/opt/homebrew/bin/ffmpeg")
    monkeypatch.setattr(local_runner.Path, "exists", lambda self: True)
    monkeypatch.setattr(local_runner, "_ffmpeg_has_libass", lambda ff: True)
    monkeypatch.setattr(local_runner, "check_llm_connection", lambda: {"ok": True, "provider": "deepseek", "model": "deepseek-flash"})

    rep = local_runner.environment_report()
    assert rep["ffmpeg"]["ok"] is True
    assert rep["ffmpeg"]["libass"] is True


def test_portrait_full_bleed_tag_pill_does_not_overlap_caption_box():
    scenes = [Scene(id="s1", start=0.0, end=10.0)]
    pkg = Packaging(
        template="interview_zh",
        style="boxed",
        audience_language="zh",
        tags_enabled=True,
        captions_enabled=True,
        cues=[{"start": 0.0, "end": 4.0, "text": "这是一段两行长度的黑底测试字幕用来验证不会与开头黄标重叠"}],
        tags=[{"at": 0.5, "text": "关键观点"}],
    )
    ass = packaging_render.scene_ass(pkg, scenes, 0, layout="crop")
    cap_match = re.search(r"CaptionBox,.*?\\pos\(540,(\d+)\)", ass)
    tag_match = re.search(r"TagPill,.*?\\pos\(540,(\d+)\)", ass)
    assert cap_match and tag_match
    cap_y = int(cap_match.group(1))
    tag_y = int(tag_match.group(1))
    # 2-line CaptionBox (bottom-aligned at cap_y=1420) rises ~155px to y=1265;
    # TagPill center must sit clearly above that band (gap >= 220px from cap_y).
    assert cap_y - tag_y >= 220, f"TagPill y={tag_y} too close to CaptionBox y={cap_y}"


def test_clean_cover_headline_strips_asr_stutter_and_leading_fillers():
    assert cover_design.clean_cover_headline("法把法律当傻子") == "把法律当傻子"
    assert cover_design.clean_cover_headline("嗯，那个把法律当傻子") == "把法律当傻子"
    assert cover_design.clean_cover_headline("就是说 别再浪费时间了") == "别再浪费时间了"
    # Preserves normal headlines without leading stutter
    assert cover_design.clean_cover_headline("两百多万播放量背后的真相") == "两百多万播放量背后的真相"
    assert cover_design.clean_cover_headline("好好聊聊这件事") == "好好聊聊这件事"
