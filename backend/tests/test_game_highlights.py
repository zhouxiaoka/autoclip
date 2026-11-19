import json

import pytest

from backend.services.studio import game_highlights as games, intelligence, planning
from backend.services.studio.models import ImportOptions, Preferences
from backend.tests.test_auto_vision_fallback import (
    configure,
    isolated_offline_settings,
    source,
)  # noqa: F401
from backend.tests.test_studio import root  # noqa: F401


@pytest.mark.parametrize(
    "mode,speech,expected",
    [
        ("auto", True, "subtitle"),
        ("auto", False, "visual"),
        ("visual", True, "visual"),
    ],
)
def test_game_plan_uses_speech_only_for_auto(
    source, monkeypatch, mode, speech, expected
):
    configure(monkeypatch, "unavailable", mode=mode)
    monkeypatch.setattr(
        intelligence,
        "vision_call",
        lambda *a, **kw: dict(
            content_type="gameplay", goal="highlight", reason="match", confidence=0.9
        ),
    )

    def evidence(*args):
        assert mode == "auto"
        return {"commentary": speech}

    monkeypatch.setattr(games, "commentary_evidence", evidence)
    plan = planning.recommend(source, ImportOptions())
    assert plan["recommended_analysis"] == expected
    assert plan["goal"] == "highlight"


def test_commentary_cuts_keep_both_anchors_and_deduplicate(tmp_path, monkeypatch):
    (tmp_path / "input.srt").write_text(
        "1\n00:00:01,000 --> 00:01:20,000\nFinal round\n"
    )
    events = [
        dict(action=34, reaction=47, score=93, label="Close finish"),
        dict(action=35, reaction=48, score=85, label="Same finish"),
        dict(action=80, reaction=11, score=99, label="Invalid"),
    ]

    def select(prompt, payload):
        assert json.loads(payload)["cues"][0][2] == "Final round"
        return {"events": events}

    monkeypatch.setattr(intelligence, "text_json", select)
    drafts = games.subtitle_drafts(
        tmp_path / "game.mp4", Preferences(goal="highlight", duration=30), 82
    )
    assert len(drafts) == 1
    (scene,) = drafts[0]["scenes"]
    assert scene["start"] < 34 < 47 < scene["end"]
    assert scene["end"] - scene["start"] == pytest.approx(30)


def test_noise_peaks_use_source_seconds_at_non_native_sample_rate(tmp_path):
    import wave
    import struct

    path = tmp_path / "match.wav"
    rate = 8000
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        for second in range(125):
            block = bytes(rate * 2)
            if 32 <= second < 34:
                block = struct.pack("<16h", *([12000] * 8 + [-12000] * 8)) * (
                    rate // 16
                )
            stream.writeframesraw(block)
    peaks = games.reaction_times(path, 125, 45)
    assert peaks and abs(peaks[0] - 32) <= 1


def test_delayed_retelling_uses_speech_resumption(monkeypatch):
    monkeypatch.setattr(
        games, "_voiced_frames", lambda *a: [False] * 500 + [True] * 600
    )
    onset = games._reaction_onset("unused", 52, 65, 30)
    assert 35 <= onset <= 39


def test_no_visual_pair_when_evidence_is_only_a_reaction(tmp_path, monkeypatch):
    monkeypatch.setattr(intelligence, "sample", lambda *a: [])
    monkeypatch.setattr(intelligence, "vision_call_at", lambda *a: {"events": []})
    assert games.verify_reaction(tmp_path / "video", 82, 180, 30) is None
