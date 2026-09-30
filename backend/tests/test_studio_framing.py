"""Speaker-centred framing math and whole-clip subtitle styles for Studio drafts."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.services.publish_export import (
    SUBTITLE_STYLES,
    ExportRequest,
    _build_filter,
)
from backend.services.studio import framing
from backend.services.studio.models import CropPoint, Draft, Scene


def test_crop_window_fraction_and_centering():
    # 16:9 source → 9:16 output covers the height, so the window is 9/16 of the height wide.
    fraction = framing.window_fraction(1280, 720, 1080, 1920)
    assert abs(fraction - (720 * 9 / 16) / 1280) < 1e-6
    assert framing.crop_x_for_center(.5, fraction) == pytest.approx(.5)
    # A face at 70% of the width puts the window's centre there; edges clamp instead of overshooting.
    assert framing.crop_x_for_center(.7, fraction) == pytest.approx((.7 - fraction / 2) / (1 - fraction))
    assert framing.crop_x_for_center(.02, fraction) == 0
    assert framing.crop_x_for_center(.99, fraction) == 1
    # Same aspect as the output: the whole frame is the window, nothing to move.
    assert framing.window_fraction(1080, 1920, 1080, 1920) == 1
    assert framing.crop_x_for_center(.9, 1.0) == .5


def test_segment_track_holds_until_a_new_speaker_persists():
    # One glance (single sample) at the other person must not move the window; two in a row do.
    samples = [(0, .3), (2.5, .31), (5, .8), (7.5, .3), (10, .8), (12.5, .82), (15, .8), (17.5, .3), (20, .3)]
    track = framing.segment_track(samples, min_hold=2, min_jump=.12)
    assert [(p["start"], round(p["crop_x"], 2)) for p in track] == [(0.0, .3), (10.0, .81), (17.5, .3)]
    assert framing.segment_track([]) == []
    assert framing.segment_track([(0, .5)]) == [{"start": 0.0, "crop_x": .5}]


def test_crop_expression_nests_hold_segments():
    scene = Scene(id="s", label="a", start=100, end=160, crop_x=.4)
    assert framing.crop_expression(scene, .5) == "0.4"
    assert framing.crop_expression(Scene(id="s", label="a", start=0, end=5), .5) == "0.5"
    scene.crop_track = [CropPoint(start=0, crop_x=.3), CropPoint(start=10, crop_x=.8), CropPoint(start=17.5, crop_x=.3)]
    assert framing.crop_expression(scene, .5) == "if(lt(t,17.5),if(lt(t,10.0),0.3,0.8),0.3)"


def test_auto_frame_builds_a_speaker_track_per_scene(monkeypatch, tmp_path):
    monkeypatch.setattr(framing, "is_installed", lambda: True)
    monkeypatch.setattr(framing, "_grab_pair", lambda video, at, folder, key: (folder / f"{key}-1.jpg", folder / f"{key}-2.jpg"))
    # Scene "talk": speaker on the left for the first half, on the right afterwards. Scene "empty": nobody.
    def speaker(pair):
        key = pair[0].name
        if key.startswith("empty"):
            return None
        index = int(key.split("-")[1])
        return .3 if index < 3 else .7
    monkeypatch.setattr(framing, "_speaker_center", speaker)
    draft = Draft(id="d", title="t", aspect="portrait", layout="crop",
                  scenes=[Scene(id="talk", label="a", start=0, end=15), Scene(id="empty", label="b", start=15, end=16)])
    result = framing.auto_frame(tmp_path / "input.mp4", draft, 1280, 720)
    fraction = result["window_fraction"]
    by_id = {s["id"]: s for s in result["scenes"]}
    talk = by_id["talk"]
    assert talk["faces"] == talk["samples"] == 7
    assert talk["switches"] == 1 and len(talk["crop_track"]) == 2
    assert talk["crop_track"][0]["crop_x"] == pytest.approx(framing.crop_x_for_center(.3, fraction), abs=1e-3)
    assert talk["crop_track"][1]["crop_x"] == pytest.approx(framing.crop_x_for_center(.7, fraction), abs=1e-3)
    assert talk["crop_x"] == talk["crop_track"][0]["crop_x"], "static crop_x doubles as the opening position"
    assert by_id["empty"]["crop_x"] is None and by_id["empty"]["crop_track"] is None


def test_auto_frame_requires_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(framing, "is_installed", lambda: False)
    draft = Draft(id="d", title="t", scenes=[Scene(id="s", label="a", start=0, end=5)])
    with pytest.raises(RuntimeError):
        framing.auto_frame(tmp_path / "input.mp4", draft, 1280, 720)


def test_scene_crop_and_subtitle_style_round_trip():
    draft = Draft(id="d", title="t", subtitle_style="accent",
                  scenes=[Scene(id="s", label="a", start=0, end=5, crop_x=.8), Scene(id="u", label="b", start=5, end=9)])
    dumped = draft.model_dump()
    assert dumped["subtitle_style"] == "accent"
    assert dumped["scenes"][0]["crop_x"] == .8 and dumped["scenes"][1]["crop_x"] is None
    assert dumped["scenes"][0]["crop_track"] is None
    tracked = Scene(id="s", label="a", start=0, end=5, crop_track=[{"start": 0, "crop_x": .2}, {"start": 2, "crop_x": .9}])
    assert [p.crop_x for p in tracked.crop_track] == [.2, .9]
    with pytest.raises(ValueError):
        Scene(id="s", label="a", start=0, end=5, crop_track=[{"start": -1, "crop_x": .2}])
    with pytest.raises(ValueError):
        Draft(id="d", title="t", subtitle_style="neon", scenes=[Scene(id="s", label="a", start=0, end=5)])
    with pytest.raises(ValueError):
        Scene(id="s", label="a", start=0, end=5, crop_x=1.5)


def test_subtitle_styles_reach_the_ffmpeg_filter(tmp_path):
    srt = tmp_path / "a.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:01,000\nhi\n", encoding="utf-8")
    req = ExportRequest("p", "c", layout="fit")
    for name, style in SUBTITLE_STYLES.items():
        graph, _last = _build_filter(req, {"layout": "fit", "w": 1080, "h": 1920}, srt, None, None, name)
        assert f"force_style='{style}'" in graph
    default_graph, _ = _build_filter(req, {"layout": "fit", "w": 1080, "h": 1920}, srt, None, None)
    unknown_graph, _ = _build_filter(req, {"layout": "fit", "w": 1080, "h": 1920}, srt, None, None, "nope")
    assert default_graph == unknown_graph, "unknown styles fall back to the clean default"
