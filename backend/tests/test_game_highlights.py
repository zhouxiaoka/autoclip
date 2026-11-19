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


@pytest.mark.parametrize(("row", "expected"), [
    ({"subject": "最后落块后棋盘定住", "detail": "主播抱头起身"}, "最后落块后棋盘定住，主播抱头起身"),
    ({"subject": "最后落块后棋盘定住", "detail": "主播向后仰靠然后用双手抱头从椅子上起身"}, "最后落块后棋盘定住"),
    ({"subject": "结算画面里可以看到第一名的金色奖章和参赛选手名字", "core": "拿下第一名"}, "拿下第一名"),
    ({"subject": "Wins the final round", "detail": "The board shows nine knockouts and a golden medal"}, "Wins the final round"),
    ({"subject": "棋盘定住", "detail": "主播懊恼抱头"}, "棋盘定住"),
    ({"outcome": "milestone", "subject": "赢下整局获评大师", "core": "获评大师"}, "获评大师"),
])
def test_title_keeps_complete_short_observations(row, expected):
    assert games._highlight_title(row, "Gameplay clip") == expected


def test_verified_reaction_gets_close_views_without_losing_window_ends():
    from backend.services.studio.models import Scene

    scene = Scene(id="clip", start=30, end=75, label="Action")
    coarse = games._review_times(scene, None)
    times = games._review_times(scene, 59)
    assert len(times) == len(set(times)) == 8
    assert times == sorted(times)
    assert {55, 58, 59, 61, coarse[0], coarse[-1]} <= set(times)
    assert games._review_times(scene, 85) == coarse



def test_reaction_title_uses_game_result_and_first_gesture():
    row = {
        "outcome": "action_feedback", "subject": "消行后主播后仰", "detail": "扑向健身球",
        "action": "最后落块", "result": "棋盘定住", "reaction": "主播抱头起身",
    }
    assert games._highlight_title(row, "实况", paired=True) == "最后落块后棋盘定住，主播抱头起身"


def test_long_visual_scan_recovers_quiet_objective_and_skips_routine(monkeypatch, tmp_path):
    from backend.services.studio.models import Scene

    monkeypatch.setattr(intelligence, "_probe", lambda _: {"duration": 2400})
    monkeypatch.setattr(games, "_read_game_objectives", lambda *args: [])
    monkeypatch.setattr(games, "reaction_times", lambda *args: [2200])
    pair = Scene(id="reaction", label="Last move", start=2180, end=2220, evidence="Board stops")
    monkeypatch.setattr(games, "verify_reaction", lambda *args: pair)
    monkeypatch.setattr(intelligence, "sample", lambda *args, **kw: [])
    chapters = []

    def respond(phase, parts):
        if phase == "game_chapter":
            chapters.append(phase)
            nominations = {
                2: [{"before": 8, "after": 9, "evidence": "Target crossed"}],
                3: [{"before": 4, "after": 6, "evidence": "Routine play"}],
                5: [{"before": 3, "after": 5, "evidence": "Only a delayed gesture"}],
            }
            return {"events": nominations.get(len(chapters), [])}
        if phase == "game_outcomes":
            import re
            ids = re.findall(r"候选编号 ([\w-]+)", str(parts))
            return {"reviews": [dict(id=i, frame=5, proof="Visible result", subject="Goal crossed",
                                     outcome="action_feedback" if i == pair.id else "milestone",
                                     standalone={"chapter-3-1": "routine", "chapter-5-1": "aftermath"}
                                     .get(i, "independent")) for i in ids]}
        return {"events": [dict(id="end", start=2180, end=2220, label="Last move")]}

    monkeypatch.setattr(intelligence, "vision_call_at", respond)
    scenes, coverage = intelligence.analyze(tmp_path / "video", Preferences(goal="highlight", duration=45), gameplay=True)
    verdicts = {item["id"]: item["disposition"] for item in coverage["selection"]}
    assert verdicts["chapter-3-1"] == "routine"
    assert verdicts["chapter-5-1"] == "aftermath"
    assert any(400 < scene.start < 800 for scene in scenes)
    assert pair.id in {s.id for s in scenes}
    assert len(scenes) == 2


@pytest.mark.parametrize("verdict,expected", [("independent", True), ("aftermath", False)])
def test_missing_dense_pair_still_needs_visual_confirmation(tmp_path, monkeypatch, verdict, expected):
    monkeypatch.setattr(games, "_read_game_objectives", lambda *args: [])
    monkeypatch.setattr(games, "reaction_times", lambda *args: [850])
    monkeypatch.setattr(games, "verify_reaction", lambda *args: None)
    monkeypatch.setattr(intelligence, "sample", lambda *args, **kwargs: [])
    def review(phase, parts):
        if phase == "game_chapter":
            return {"events": []}
        return {"reviews": [{"id": "audio-landmark", "outcome": "action_feedback",
                             "frame": 5, "proof": "Board and player in frame",
                             "subject": "Board stops", "standalone": verdict}]}
    monkeypatch.setattr(intelligence, "vision_call_at", review)
    if expected:
        scenes, _ = games.analyze_game_chapters(tmp_path / "video", Preferences(), 900, "", None)
        assert len(scenes) == 1 and scenes[0].start < 850 < scenes[0].end
    else:
        with pytest.raises(games.UserFacingError, match="独立成片"):
            games.analyze_game_chapters(tmp_path / "video", Preferences(), 900, "", None)


def test_objective_readings_recover_quiet_changes_without_a_nomination():
    tracks = [
        {"goal": "Complete phase 12", "mode": "rollover", "target": 12,
         "values": [10, 11, 12, 0, 1]},
        {"goal": "Reach 500", "mode": "reach", "target": 500,
         "values": [410, 430, 510, 515, 520]},
    ]
    assert [(x["before"], x["after"]) for x in games._visible_goal_changes(tracks, 5)] == [(3, 4), (2, 3)]
    tracks[0]["values"] = [8, 0, 1, None, 0]
    tracks[1]["values"] = [510, 520, 530, 540, 550]
    assert games._visible_goal_changes(tracks, 5) == []


def test_grid_keeps_indices_when_a_counter_row_is_unreadable(tmp_path, monkeypatch):
    from PIL import Image

    for n in range(12):
        Image.new("RGB", (64, 48), "black").save(tmp_path / f"{n}.jpg")
    goal = {"box": [100, 100, 300, 250], "mode": "reach", "target": 10, "goal": "Reach 10"}
    monkeypatch.setattr(intelligence, "vision_call_at", lambda *a: {"rows": [[1, 2], [7, 8, 9, 10, 11, 12]]})
    track = games._read_counter_grid(tmp_path, 12, goal)
    assert track["values"] == [None] * 6 + [7, 8, 9, 10, 11, 12]
    assert games._visible_goal_changes([track], 12)[0]["after"] == 10
