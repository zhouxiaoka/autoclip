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


def test_verified_win_outranks_placement_and_titles_use_observations(
    monkeypatch, tmp_path
):
    from backend.services.studio.models import Scene

    scenes = [
        Scene(id="top", start=0, end=20, label="Top ten"),
        Scene(id="win", start=22, end=45, label="He must be furious"),
    ]
    monkeypatch.setattr(intelligence, "sample", lambda *a, **kw: [])

    def reply(*args):
        return {
            "reviews": [
                {
                    "id": "win",
                    "outcome": "match_win",
                    "final_for_player": True,
                    "proof": "Final Results: 1st",
                    "frame": 5,
                    "subject": "First place on the results screen",
                    "detail": "He looks devastated",
                },
                {
                    "id": "top",
                    "outcome": "placement",
                    "proof": "Final Results: 8th",
                    "frame": 4,
                    "subject": "Eighth place on the results screen",
                    "detail": "",
                },
            ]
        }

    monkeypatch.setattr(intelligence, "vision_call_at", reply)
    reviewed = games.review_outcomes(tmp_path / "video", scenes, "en")
    assert [s.id for s in reviewed] == ["win", "top"]
    assert reviewed[0].label == "First place on the results screen"
    assert [(s.start, s.end) for s in reviewed] == [(22, 45), (0, 20)]


def test_other_players_result_cannot_promote_or_title_clip(monkeypatch, tmp_path):
    from backend.services.studio.models import Scene

    monkeypatch.setattr(intelligence, "sample", lambda *a, **k: [])
    monkeypatch.setattr(
        intelligence,
        "vision_call_at",
        lambda *a: {
            "reviews": [
                {
                    "id": "other",
                    "outcome": "match_win",
                    "final_for_player": False,
                    "frame": 5,
                    "proof": "Opponent won",
                    "subject": "Winner!",
                },
                {
                    "id": "ours",
                    "outcome": "placement",
                    "frame": 7,
                    "proof": "8th",
                    "subject": "Finish in eighth place",
                },
            ]
        },
    )
    scenes = [
        Scene(id=x, start=i * 10, end=i * 10 + 9)
        for i, x in enumerate(["other", "ours"])
    ]
    ranked = games.review_outcomes(tmp_path / "recording", scenes, "en")
    assert [s.id for s in ranked] == ["ours", "other"]
    assert ranked[-1].label == "Gameplay clip"


def test_original_game_post_keeps_reviewed_title(tmp_path, monkeypatch):
    from backend.services.studio import jobs, post_copy

    monkeypatch.setattr(
        jobs,
        "_packaging_inputs",
        lambda _, cache: cache.update(gameplay=True, entries=[]),
    )
    monkeypatch.setattr(
        post_copy,
        "build_posts",
        lambda *a, **kw: {
            "original": {
                "title": "He looks devastated",
                "description": "Clip",
                "tags": [],
            }
        },
    )
    value = {
        "title": "Board stops moving",
        "origin": "visual-highlight",
        "scenes": [{"start": 0, "end": 10}],
    }
    posts = jobs._posts_for("test", [("original", value)], {})
    assert next(iter(posts.values())) == {
        "title": "Board stops moving",
        "description": "Clip",
        "tags": [],
    }


def test_transcript_win_nomination_with_quote_beats_higher_placement_score(
    tmp_path, monkeypatch
):
    (tmp_path / "input.srt").write_text(
        "1\n00:00:05,000 --> 00:00:10,000\nFinished ninth\n\n2\n00:01:30,000 --> 00:01:42,000\nI won that match\n"
    )
    events = [
        dict(
            action=5,
            reaction=10,
            label="Ninth place",
            score=99,
            outcome="placement",
            quote="Finished ninth",
        ),
        dict(
            action=90,
            reaction=96,
            label="Match win",
            score=81,
            outcome="match_win",
            quote="I won that match",
        ),
    ]
    monkeypatch.setattr(intelligence, "text_json", lambda *a: {"events": events})
    monkeypatch.setattr(
        intelligence,
        "vision_call_at",
        lambda *a: pytest.fail("text-only route sent frames"),
    )
    drafts = games.subtitle_drafts(
        tmp_path / "video.mp4", Preferences(goal="highlight"), 105
    )
    assert [d["title"] for d in drafts] == ["Match win", "Ninth place"]
