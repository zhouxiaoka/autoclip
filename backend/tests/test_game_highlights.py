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


def test_retrospective_cue_can_only_add_a_visually_confirmed_win(monkeypatch, tmp_path):
    from backend.services.studio.models import Scene

    prefs = Preferences(goal="highlight", duration=45)
    ordinary = Scene(id="placement", start=5, end=50, label="Eighth place")
    rows = [(140, 150, "That's quite a win rate")]
    monkeypatch.setattr(intelligence, "sample", lambda *a, **kw: [])
    def inspect_group(phase, parts):
        import re
        ids = re.findall(r"候选编号 ([\w-]+)", str(parts))
        return {"reviews": [dict(id=i, frame=6, proof="Final results", subject="First place",
                                 final_for_player=(n == 0), outcome="match_win") for n,i in enumerate(ids)]}
    monkeypatch.setattr(intelligence, "vision_call_at", inspect_group)
    ranked = games._recover_result_windows(tmp_path/"video", rows, 240, prefs, [ordinary], set())
    assert len(ranked) == 2 and ranked[0].start < 100 < ranked[0].end
    assert ranked[1].id == ordinary.id
    monkeypatch.setattr(intelligence, "vision_call_at", lambda *a: pytest.fail("duplicate verification"))
    assert games._recover_result_windows(tmp_path/"video", rows, 240, prefs, ranked, {ranked[0].id}) == ranked


def test_unreadable_optional_counter_keeps_the_primary_scan(monkeypatch):
    def invalid(*args):
        raise intelligence.VisionRequestError("invalid_response", "bad grid")
    monkeypatch.setattr(intelligence, "vision_call_at", invalid)
    assert games._optional_observation("game_counter", []) == {}
    def offline(*args):
        raise intelligence.VisionRequestError("network", "network down")
    monkeypatch.setattr(intelligence, "vision_call_at", offline)
    with pytest.raises(intelligence.VisionRequestError, match="network"):
        games._optional_observation("game_counter", [])


def test_scout_milestone_must_show_the_named_rollover(monkeypatch, tmp_path):
    # Replay the two different scout decisions from the same match, including
    # the positive editorial verdict on the later window.
    goal = {"goal": "29 rollover", "target": 29, "mode": "rollover", "box": [470, 658, 595, 772]}
    monkeypatch.setattr(games, "_read_game_objectives", lambda *a: [goal])
    monkeypatch.setattr(games, "reaction_times", lambda *a: [])
    monkeypatch.setattr(intelligence, "sample", lambda *a, **kw: [])
    chapter = 0

    def counter(folder, count, target):
        values = [None] * count
        if count == 48:
            values[12:15] = [28, 29, 0] if chapter == 1 else [None, 29, None]
        else:
            values[count // 2] = 29
        return {**target, "values": values}

    def respond(phase, parts):
        nonlocal chapter
        if phase == "game_chapter":
            chapter += 1
            evidence = ("目标29 rollover，LEVEL从29回到00" if chapter == 1 else
                        "目标列表含29 rollover；LEVEL为A8，首次变为29，完成本段首次触达29级")
            return {"events": [{"before": 13, "after": 14, "evidence": evidence}]}
        ids = [p["text"].split("候选编号 ")[1].split("，")[0] for p in parts
               if p["type"] == "text" and p["text"].startswith("候选编号 ")]
        return {"reviews": [{"id": ident, "outcome": "milestone", "standalone": "independent",
                             "frame": 5, "subject": "等级升到29" if ident.startswith("chapter-2") else "等级从29回到00",
                             "proof": "A8 → 29 → F0" if ident.startswith("chapter-2") else "29 → 00"}
                            for ident in ids]}

    monkeypatch.setattr(games, "_read_counter_grid", counter)
    monkeypatch.setattr(intelligence, "vision_call_at", respond)
    scenes, coverage = games.analyze_game_chapters(tmp_path / "video", Preferences(duration=45), 800, "", None)
    assert len(scenes) == 1 and scenes[0].start < 400
    same_reset = [r for r in coverage["selection"] if r["id"].startswith("chapter-1-")]
    assert {r["disposition"] for r in same_reset} == {"selected", "duplicate"}
    assert same_reset[0]["rollover_times"] == same_reset[1]["rollover_times"]
    rejected = next(r for r in coverage["selection"] if r["id"] == "chapter-2-1")
    assert rejected["disposition"] == "unconfirmed_goal"


def test_rollover_needs_ordered_readings_on_the_same_counter(tmp_path, monkeypatch):
    from backend.services.studio.models import Scene

    goal = {"goal": "Phase 12 rollover", "mode": "rollover", "target": 12}
    scene = Scene(id="s", start=50, end=85, label="Phase resets")
    audit = {"outcome": "milestone", "nomination": "A change on the HUD", "objective": goal["goal"]}
    history = {goal["goal"]: [(20, 12), (21, 0), (55, 12), (60, 10), (70, None), (75, 0)]}
    monkeypatch.setattr(intelligence, "sample", lambda *args, **kw: [])
    dense = [None] * 16
    monkeypatch.setattr(games, "_read_counter_grid", lambda *args: {"values": dense})
    assert not games._confirm_rollover(tmp_path/"video", scene, audit.copy(), [goal], history, None)
    dense[8:10] = [12, 0]
    checked = dict(audit)
    assert games._confirm_rollover(tmp_path/"video", scene, checked, [goal], history, None)
    assert scene.start < checked["rollover_times"][0] < checked["rollover_times"][1] < scene.end


def test_independent_score_cap_can_share_the_rollover_hud(tmp_path, monkeypatch):
    from backend.services.studio.models import Scene

    goal = {"goal": "Phase 12 rollover", "mode": "rollover", "target": 12}
    scene = Scene(id="score", start=50, end=85, label="Score reaches 999999")
    audit = {"outcome": "milestone", "nomination": "Goal panel: Phase 12 rollover; score hits the cap."}
    monkeypatch.setattr(intelligence, "sample", lambda *args: pytest.fail("independent score requested OCR"))
    assert games._confirm_rollover(tmp_path/"video", scene, audit, [goal], {}, None)


def test_rollover_locator_accepts_a_single_fenced_payload_after_transcription():
    raw = ('目标列表（右侧 GOALS）逐行：\n- "2 million"\n- "Clear 29-3"\n- "29 rollover"\n'
           '阶段转换用 LEVEL 字段。\n\n```json\n{"goals":[{"goal":"29 rollover",'
           '"target":29,"mode":"rollover","box":[470,655,600,775]}]}\n```')
    assert intelligence.decode_json(raw)["goals"][0]["target"] == 29
    unfenced = raw.replace("```json\n", "").removesuffix("\n```")
    assert intelligence.decode_json(unfenced)["goals"][0]["target"] == 29
    with pytest.raises(ValueError):
        intelligence.decode_json(unfenced + "\n{}")
    with pytest.raises(ValueError):
        intelligence.decode_json(raw + '\n```json\n{}\n```')


def test_missing_goal_location_cannot_approve_a_named_rollover_target(tmp_path):
    from backend.services.studio.models import Scene

    scene = Scene(id="redisplay", start=1, end=46, label="等级显示由A8变为29")
    audit = {"outcome": "milestone", "nomination": "对应目标'Clear 29-3'与'29 rollover'的起始节点"}
    assert not games._confirm_rollover(tmp_path / "video", scene, audit, [], {}, None)
    assert audit["disposition"] == "unconfirmed_goal"


def test_review_can_identify_reset_on_another_goals_candidate(tmp_path):
    from backend.services.studio.models import Scene

    scene = Scene(id="alternate", start=1, end=46, label="等级从29回绕到00")
    goal = {"goal": "29 rollover", "mode": "rollover", "target": 29}
    audit = {"outcome": "milestone", "nomination": "画面目标 Clear 29-3；状态读数 28 → 29",
             "proof": "帧6为29，帧7显示00，确认回绕。objective:29 rollover"}
    assert games._confirm_rollover(tmp_path / "video", scene, audit, [goal],
                                   {"29 rollover": [(5, 28), (15, 29), (25, 0)]}, "Clear 29-3")
    assert audit.get("rollover_times") == [15, 25]


def test_commentary_review_requires_distinct_consequence(tmp_path, monkeypatch):
    from backend.services.studio.models import Scene

    cases = [
        ("flash", "action_feedback", "routine", None, 3, 5),
        ("plain", "play", "routine", None, 3, 5),
        ("bronze", "podium", "podium", 3, 2, 6),
        ("rank", "placement", "podium", 9, 2, 6),
        ("survival", "recovery", "recovery", None, 2, 6),
        ("guess", "action_feedback", "recovery", None, 5, 5),
        ("champion", "match_win", "routine", None, None, None),
    ]
    scenes = [Scene(id=k, start=i*60, end=i*60+45, evidence="commentary nomination")
              for i,(k,*_) in enumerate(cases)]
    monkeypatch.setattr(intelligence, "sample", lambda *a, **kw: [])
    def review(phase, parts):
        ids = [p["text"].split()[1].split("，")[0] for p in parts
               if p["type"] == "text" and p["text"].startswith("候选编号 ")]
        return {"reviews": [dict(id=k, outcome=outcome, impact=impact, final_rank=rank,
                                 before_frame=before, after_frame=after, frame=5, subject=k,
                                 proof="Visible change", final_for_player=k=="champion")
                            for k,outcome,impact,rank,before,after in cases if k in ids]}
    monkeypatch.setattr(intelligence, "vision_call_at", review)
    audit = {}
    ranked = games.review_outcomes(tmp_path/"video", scenes, "en", commentary_selection=audit)
    assert [s.id for s in ranked] == ["champion", "bronze", "survival"]
    assert audit["plain"]["disposition"] == "routine"
    assert audit["guess"]["disposition"] != "selected"


@pytest.mark.parametrize(("readings", "same_match", "expected"), [
    ([5, 5, 5, 5, 6, 6, 7, 7], True, (5, 7)),
    ([0, 0, None, 0, 0, 2, 2, 2], True, (0, 2)),
    ([5, 5, 6, 6, 6, 6, 6, 6], True, None),
    ([5, 5, 7, 0, 1, 1, 2, 2], True, None),
    ([0, 0, 0, 1, 2, 2, 2, 2], False, None),
    ([None]*6 + [0, 2], True, None),
    ([0, 0, 0, 0, 0, 0, 0, 82], True, None),
])
def test_commentary_reads_the_players_elimination_tally(readings, same_match, expected):
    assert games._elimination_change(readings, same_match) == expected


def test_commentary_recovers_small_counter_glyphs(tmp_path, monkeypatch):
    from backend.services.studio.models import Scene

    scene = Scene(id="two-knockouts", start=20, end=65)
    row = {"impact": "routine", "same_match": True, "elimination_box": [660, 700, 707, 737],
           "elimination_counts": [5, 5, 5, 5, 6, 6, 6, 6]}
    monkeypatch.setattr(intelligence, "sample", lambda *a: [])
    readings = [5, 5, 5, 5, 6, 6, 7, 7]
    monkeypatch.setattr(games, "_read_counter_grid", lambda *a: {"values": readings})
    assert games._review_eliminations(tmp_path/"video", scene, row) == ((5, 7), readings)
    readings[-2:] = [6, 6]
    assert games._review_eliminations(tmp_path/"video", scene, row) == (None, readings)


def test_incomplete_grid_can_use_same_hud_at_the_same_frame():
    tracks = [
        dict(goal="rollover", mode="rollover", target=29, box=[10,20,30,40], values=[29,None,None,4]),
        dict(goal="reach", mode="reach", target=3, box=[10,20,30,40], values=[29,0,None,6]),
        dict(goal="lines", mode="reach", target=30, box=[10,30,30,50], values=[29,7,0,6]),
    ]
    games._reconcile_counter_tracks(tracks)
    assert tracks[0]["values"] == [29,0,None,None]
    assert tracks[2]["values"] == [29,7,0,6]


def test_unreadable_elimination_field_can_reuse_location_but_not_other_counts(tmp_path, monkeypatch):
    from backend.services.studio.models import Scene

    scene = Scene(id="nominee", start=0, end=45, evidence="Big kill")
    row = dict(impact="routine", same_match=True, elimination_counts=[None]*8)
    box = [630, 720, 700, 765]
    monkeypatch.setattr(intelligence, "sample", lambda *a: [])
    def read(folder, count, goal):
        assert count == 8 and goal["box"] == box
        return {"values": [5,5,5,5,6,6,7,7]}
    monkeypatch.setattr(games, "_read_counter_grid", read)
    assert games._review_eliminations(tmp_path/"video", scene, row, box)[0] == (5,7)


def test_long_commentary_keeps_late_sentences_within_source_cue(tmp_path, monkeypatch):
    text = "Move slowly through the room. " * 32 + "The switch lights up and the door opens."
    (tmp_path / "input.srt").write_text(f"1\n00:00:00,000 --> 00:01:40,000\n{text}\n")
    rows = []

    def nominate(prompt, payload):
        rows.extend(json.loads(payload)["cues"])
        return {"events": [dict(action=94, reaction=99, score=91, label="Door opens",
                                outcome="play", quote="the door opens")]}

    monkeypatch.setattr(intelligence, "text_json", nominate)
    games.subtitle_drafts(tmp_path / "video.mp4", Preferences(goal="highlight"), 100)
    assert " ".join(row[2] for row in rows) == text
    assert 80 < rows[-1][0] < rows[-1][1] == 100


@pytest.mark.parametrize("impact", ["unexpected_reaction", "demonstration"])
def test_commentary_pair_needs_matching_local_speech_and_ordered_frames(tmp_path, monkeypatch, impact):
    from backend.services.studio.models import Scene

    scenes = [Scene(id=str(i), start=i*40, end=i*40+30) for i in range(3)]
    monkeypatch.setattr(intelligence, "sample", lambda *a, **kw: [])
    def review(phase, parts):
        return {"reviews": [dict(id=s.id, outcome="action_feedback", impact=impact, frame=6,
                                 before_frame=3, after_frame=6 if i != 2 else 2,
                                 spoken_quote="the door flew open", proof="Closed then open", subject="Door opens")
                            for i,s in enumerate(scenes)]}
    monkeypatch.setattr(intelligence, "vision_call_at", review)
    ranked = games.review_outcomes(tmp_path/"video", scenes, "en", commentary_selection={},
                                   commentary_text={"0":"Whoa, the door flew open!", "1":"nothing yet", "2":"the door flew open"})
    assert [scene.id for scene in ranked] == ["0"]


def test_chapters_coverage_includes_sample_interval_and_podium_accepts_rank_one(tmp_path, monkeypatch):
    from backend.services.studio.models import Scene

    monkeypatch.setattr(games, "_read_game_objectives", lambda *a: [])
    monkeypatch.setattr(games, "reaction_times", lambda *a: [])
    monkeypatch.setattr(intelligence, "sample", lambda *a, **kw: [])

    def respond(phase, parts):
        if phase == "game_chapter":
            return {"events": [{"before": 5, "after": 6, "evidence": "Boss defeated"}]}
        return {"reviews": [{"id": "chapter-1-1", "outcome": "milestone", "standalone": "independent",
                             "frame": 5, "proof": "Boss defeated", "subject": "Boss defeated"}]}

    monkeypatch.setattr(intelligence, "vision_call_at", respond)
    scenes, coverage = games.analyze_game_chapters(tmp_path / "video", Preferences(duration=45), 400, "", None)
    assert scenes and isinstance(coverage["sample_interval"], float) and coverage["note"]

    # Podium rank 1 with outcome="placement" is retained at tier 3 rather than dropped.
    monkeypatch.setattr(
        intelligence,
        "vision_call_at",
        lambda *a: {"reviews": [{"id": "p1", "outcome": "placement", "impact": "podium", "final_rank": 1,
                                 "before_frame": 2, "after_frame": 6, "frame": 6, "proof": "1st place", "subject": "拿下第一名"}]},
    )
    ranked = games.review_outcomes(tmp_path / "video", [Scene(id="p1", start=0, end=30)], "source", commentary_selection={})
    assert [s.id for s in ranked] == ["p1"] and ranked[0].label == "拿下第一名"


def test_degraded_or_overlong_commentary_plan_never_enables_frame_review(tmp_path, monkeypatch):
    from backend.services.studio import jobs

    seen = []
    monkeypatch.setattr(
        games,
        "subtitle_drafts",
        lambda video, prefs, duration, instruction="", *, auto_frame_review=False, selection_log=None: (
            seen.append(auto_frame_review),
            [{"id": "d1", "title": "t", "scenes": [{"id": "s1", "start": 0, "end": 20, "label": "t"}], "origin": "subtitle-highlight"}],
        )[1],
    )
    base_plan = {
        "recommended_analysis": "subtitle",
        "preferences": {"goal": "highlight", "duration": 45},
        "analysis_preferences": {"analysis_mode": "auto"},
        "local_evidence": {"commentary": True},
        "source_duration": 600,
    }
    jobs._content_drafts("p1", {**base_plan, "degrade_reason": "vision_unavailable"}, tmp_path / "v.mp4", ("original",))
    jobs._content_drafts("p1", {**base_plan, "source_duration": 9000}, tmp_path / "v.mp4", ("original",))
    jobs._content_drafts("p1", base_plan, tmp_path / "v.mp4", ("original",))
    assert seen == [False, False, True]


def test_subtitle_drafts_caps_final_output_at_six(tmp_path, monkeypatch):
    lines = "\n\n".join(f"{i+1}\n00:{i*3:02d}:00,000 --> 00:{i*3:02d}:20,000\nMoment {i}" for i in range(10))
    (tmp_path / "input.srt").write_text(lines)

    def nominate(_prompt, payload):
        cues = json.loads(payload)["cues"]
        return {"events": [
            {"action": c[0] + 2, "reaction": c[0] + 10, "score": 90, "outcome": "play", "quote": c[2], "label": c[2]}
            for c in cues
        ]}

    monkeypatch.setattr(intelligence, "text_json", nominate)
    monkeypatch.setattr(intelligence, "source_frame_analysis_allowed", lambda: True)
    monkeypatch.setattr(intelligence, "sample", lambda *a, **kw: [])
    monkeypatch.setattr(
        intelligence,
        "vision_call_at",
        lambda phase, parts: {"reviews": [
            {"id": p["text"].split()[1].split("，")[0], "outcome": "action_feedback", "impact": "recovery",
             "before_frame": 2, "after_frame": 6, "frame": 6, "proof": "Clutch", "subject": "Clutch"}
            for p in parts if p.get("type") == "text" and p["text"].startswith("候选编号 ")
        ]},
    )
    drafts = games.subtitle_drafts(tmp_path / "video.mp4", Preferences(goal="highlight", duration=30), 2000, auto_frame_review=True)
    assert len(drafts) == 6
