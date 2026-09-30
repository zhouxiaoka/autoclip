"""Speaker-centred framing math and whole-clip subtitle styles for Studio drafts."""
import itertools
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.services.publish_export import (
    SUBTITLE_STYLES,
    portrait_subtitle_style,
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


def test_split_shots_collapses_flicker_and_caps_count():
    # Cuts closer than MIN_SHOT to the previous boundary (or the end) are transitions, not shots.
    assert framing.split_shots(20, [0.1, 5.0, 5.2, 12.0, 19.9]) == [(0.0, 5.0), (5.0, 12.0), (12.0, 20)]
    assert framing.split_shots(3, []) == [(0.0, 3)]
    montage = framing.split_shots(300, [i * 0.5 for i in range(1, 600)], max_shots=10)
    assert len(montage) == 10 and montage[0][0] == 0.0 and montage[-1][1] == 300


def test_sample_offsets_stay_clear_of_cuts():
    # Short shot: one look in the middle, never on the cut frames themselves.
    assert framing.sample_offsets(10, 11) == [pytest.approx(10.375)]
    three = framing.sample_offsets(10, 14)
    assert len(three) == 3 and three[0] >= 10.3 and three[-1] + framing.PAIR_GAP <= 13.7
    long = framing.sample_offsets(0, 20)
    assert len(long) >= 7 and long[0] == pytest.approx(.3) and all(b - a == pytest.approx(framing.SAMPLE_INTERVAL) for a, b in itertools.pairwise(long))
    assert framing.sample_offsets(0, .2) == [0]


def test_frame_shot_classifies_cards_and_speakers():
    fraction = framing.window_fraction(1280, 720, 1080, 1920)
    # Nobody in the frame → show the whole shot (quote card, slide).
    assert framing.frame_shot([(0.3, None), (1.5, None), (2.7, None)], 4.0, 3.0, fraction) == [{"start": 4.0, "crop_x": .5, "mode": "fit"}]
    # One missed detection out of three still frames on the person.
    [point] = framing.frame_shot([(0.3, .3), (1.5, None), (2.7, .32)], 4.0, 3.0, fraction)
    assert point["mode"] == "crop" and point["crop_x"] == pytest.approx(framing.crop_x_for_center(.31, fraction), abs=1e-3)
    # A long two-shot switches inside once the other speaker persists.
    samples = [(0, .3), (2.5, .3), (5, .7), (7.5, .7), (10, .7)]
    track = framing.frame_shot(samples, 20.0, 12.0, fraction)
    assert [p["start"] for p in track] == [20.0, 25.0] and all(p["mode"] == "crop" for p in track)


def test_merge_points_drops_invisible_changes():
    points = [{"start": 0, "crop_x": .3, "mode": "crop"}, {"start": 2, "crop_x": .32, "mode": "crop"},
              {"start": 5, "crop_x": .5, "mode": "fit"}, {"start": 6, "crop_x": .5, "mode": "fit"},
              {"start": 8, "crop_x": .31, "mode": "crop"}]
    assert [p["start"] for p in framing.merge_points(points)] == [0, 5, 8]


def test_auto_frame_aligns_the_track_to_cuts(monkeypatch, tmp_path):
    monkeypatch.setattr(framing, "is_installed", lambda: True)
    monkeypatch.setattr(framing, "_grab_pair", lambda video, at, folder, key: (folder / f"{key}-{at:.3f}-1.jpg", folder / f"{key}-2.jpg"))
    # Scene "talk" (15 s): a quote card for 3 s, then the left speaker until a cut at 9 s, then the right speaker.
    monkeypatch.setattr(framing, "detect_cuts", lambda video, start, length: [3.0, 9.0] if start == 0 else [])
    def speaker(pair):
        at = float(pair[0].name.split("-")[-2])
        if pair[0].name.startswith("empty") or at < 3:
            return None
        return .3 if at < 9 else .7
    monkeypatch.setattr(framing, "_speaker_center", speaker)
    draft = Draft(id="d", title="t", aspect="portrait", layout="crop",
                  scenes=[Scene(id="talk", label="a", start=0, end=15), Scene(id="empty", label="b", start=15, end=16)])
    result = framing.auto_frame(tmp_path / "input.mp4", draft, 1280, 720)
    fraction = result["window_fraction"]
    by_id = {s["id"]: s for s in result["scenes"]}
    talk = by_id["talk"]
    assert talk["shots"] == 3 and talk["fit_shots"] == 1 and talk["switches"] == 2
    assert [(p["start"], p["mode"]) for p in talk["crop_track"]] == [(0.0, "fit"), (3.0, "crop"), (9.0, "crop")], "points sit exactly on the cuts"
    assert talk["crop_track"][1]["crop_x"] == pytest.approx(framing.crop_x_for_center(.3, fraction), abs=1e-3)
    assert talk["crop_track"][2]["crop_x"] == pytest.approx(framing.crop_x_for_center(.7, fraction), abs=1e-3)
    assert talk["crop_x"] == talk["crop_track"][0]["crop_x"], "static crop_x doubles as the opening position"
    # A scene without anybody, in a draft that does have people: shown whole rather than cropped blindly.
    assert by_id["empty"]["crop_track"] == [{"start": 0.0, "crop_x": .5, "mode": "fit"}]


def test_auto_frame_leaves_people_free_footage_alone(monkeypatch, tmp_path):
    monkeypatch.setattr(framing, "is_installed", lambda: True)
    monkeypatch.setattr(framing, "_grab_pair", lambda video, at, folder, key: (folder / f"{key}-1.jpg", folder / f"{key}-2.jpg"))
    monkeypatch.setattr(framing, "detect_cuts", lambda video, start, length: [2.0])
    monkeypatch.setattr(framing, "_speaker_center", lambda pair: None)
    draft = Draft(id="d", title="t", aspect="portrait", layout="crop", scenes=[Scene(id="game", label="a", start=0, end=6)])
    [scene] = framing.auto_frame(tmp_path / "input.mp4", draft, 1280, 720)["scenes"]
    assert scene["crop_x"] is None and scene["crop_track"] is None and scene["faces"] == 0 and scene["samples"] > 0


def test_layout_filter_switches_to_fit_on_card_shots():
    scene = Scene(id="s", label="a", start=10, end=25, crop_track=[
        {"start": 0, "crop_x": .5, "mode": "fit"}, {"start": 3, "crop_x": .2, "mode": "crop"},
        {"start": 9, "crop_x": .8, "mode": "crop"}, {"start": 12, "crop_x": .5, "mode": "fit"}])
    assert framing.fit_spans(scene) == [(0, 3), (12, 15)]
    graph = framing.layout_filter(scene, .5, 1080, 1920)
    assert graph.startswith("[0:v]split=3[c][bg][fg];") and graph.endswith("[base]")
    assert "crop=1080:1920:x='(iw-ow)*if(lt(t,12.0),if(lt(t,9.0),if(lt(t,3.0),0.5,0.2),0.8),0.5)'" in graph
    assert "gblur" in graph and "enable='between(t,0.0,3.0)+between(t,12.0,15.0)'" in graph
    # No fit shots → the plain moving crop, nothing blurred or overlaid.
    plain = framing.layout_filter(Scene(id="s", label="a", start=0, end=5, crop_x=.4), .5, 1080, 1920)
    assert plain == "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920:x='(iw-ow)*0.4':y=(ih-oh)/2,setsar=1[base]"


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
    tracked = Scene(id="s", label="a", start=0, end=5, crop_track=[{"start": 0, "crop_x": .2}, {"start": 2, "crop_x": .9, "mode": "fit"}])
    assert [(p.crop_x, p.mode) for p in tracked.crop_track] == [(.2, "crop"), (.9, "fit")], "mode defaults to crop for tracks saved before fit existed"
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
        assert f"force_style='{portrait_subtitle_style(style)}'" in graph
        landscape, _last = _build_filter(req, {"layout": "fit", "w": 1920, "h": 1080}, srt, None, None, name)
        assert f"force_style='{style}'" in landscape
    default_graph, _ = _build_filter(req, {"layout": "fit", "w": 1080, "h": 1920}, srt, None, None)
    unknown_graph, _ = _build_filter(req, {"layout": "fit", "w": 1080, "h": 1920}, srt, None, None, "nope")
    assert default_graph == unknown_graph, "unknown styles fall back to the clean default"
