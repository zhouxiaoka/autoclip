import hashlib
import io

import pytest
from PIL import Image

from backend.services import cover_brief as cb
from backend.services.studio import cover_design as cd, framing, intelligence


def jpeg(color):
    out = io.BytesIO()
    Image.new("RGB", (160, 90), color).save(out, format="JPEG")
    return out.getvalue()


@pytest.fixture
def setup_plan(monkeypatch):
    first, second = jpeg("#556677"), jpeg("#884422")
    candidates = [(first, 0.55, 7, True, 2.0), (second, 0.3, 6, True, 5.0)]
    monkeypatch.setattr(framing, "detect_cuts", lambda *args: [3.0])
    monkeypatch.setattr(cd, "_candidates", lambda *args, **kw: candidates[:])
    monkeypatch.setattr(intelligence, "source_frame_analysis_allowed", lambda: True)
    calls = []
    reply = dict(
        best=2,
        runner_up=1,
        reason="第二机位露出完整肩线",
        rejection="第一机位的亮带占满文字区",
        subject="黑衣人物看向右侧",
        crop_boundary="人物在原片胸口截止",
        text_zone="right",
        composition="把标题放在眼神右方的暗墙上",
        lines=["最好的", "12个月？"],
        emphasis="12",
        typography="第一行较轻，第二行加重",
        color_reason="蓝色压住暖墙的橙色",
        accent="#4285FF",
    )

    def vision(content, config):
        calls.append(content)
        return reply

    monkeypatch.setattr(intelligence, "vision_call", vision)
    return candidates, reply, calls


def pick(rows=()):
    from backend.services import cover_planner as planner

    opts = cb.Options(mode="editorial_edit")
    context = planner.context(
        "最好的12个月？", "douyin", (720, 1280), opts, locked=True
    )
    trace = {}
    photo, _, _ = cd.pick_frame(
        None, {"start": 0.0, "end": 8.0}, rows, trace=trace, context=context
    )
    brief = cb.plan(
        photo,
        title=context["title"],
        strategy="douyin",
        size=(720, 1280),
        origin=trace,
        locked=True,
        options=opts,
        rows=rows,
        editorial_context=context,
    )
    return photo, brief


def test_one_visual_request_links_chosen_pixels_to_final_prompt(setup_plan):
    candidates, _, calls = setup_plan
    photo, brief = pick()
    assert photo == candidates[1][0] and len(calls) == 1
    assert brief.source["frame_sha256"] == hashlib.sha256(photo).hexdigest()
    assert brief.source["editorial_plan"]["runner_up_time"] == 2.0
    assert brief.design["layout"] == "right"
    prompt = cb.compile_prompt(brief)
    for part in [
        "眼神右方的暗墙",
        "胸口截止",
        "第一行较轻",
        "#4285FF",
        "最好的\n12个月？",
    ]:
        assert part in prompt


@pytest.mark.parametrize("fault", ["best", "copy", "consent"])
def test_unusable_plan_keeps_local_selection_and_locked_copy(
    setup_plan, monkeypatch, fault
):
    _, reply, calls = setup_plan
    if fault == "best":
        reply["best"] = 99
    elif fault == "copy":
        reply["lines"] = ["广告"]
    else:
        monkeypatch.setattr(
            intelligence, "source_frame_analysis_allowed", lambda: False
        )
    photo, brief = pick()
    assert len(calls) == (0 if fault == "consent" else 1)
    assert brief.source["editorial_plan"]["status"] != "planned"
    assert brief.copy_spec["exact_text"] == "最好的12个月？"
    assert "广告" not in cb.compile_prompt(brief)


def test_fixed_frame_redesign_keeps_photo_and_replans_when_intent_changes(setup_plan):
    from backend.services import cover_planner as planner

    _, reply, calls = setup_plan
    photo, first = pick()
    reply.update(best=1, runner_up=0, rejection="", composition="由右侧问句读回眼睛")
    ctx = planner.context(
        "最好的12个月？",
        "douyin",
        (720, 1280),
        cb.Options(mode="editorial_edit"),
        locked=True,
        previous=first.design["composition_intent"],
    )
    new = planner.bound(photo, first.source, ctx, [])
    assert len(calls) == 2 and sum(c["type"] == "image_url" for c in calls[-1]) == 1
    assert new["frame_sha256"] == first.source["frame_sha256"]
    assert new["direction"]["composition"] == "由右侧问句读回眼睛"
    assert (
        planner.bound(photo, dict(editorial_plan=new), ctx, []) == new
        and len(calls) == 2
    )


def test_change_frame_excludes_previous_candidate_before_vision(setup_plan):
    from backend.services import cover_planner as planner

    candidates, reply, calls = setup_plan
    reply.update(best=1, runner_up=0, rejection="")
    ctx = planner.context(
        "最好的12个月？",
        "douyin",
        (720, 1280),
        cb.Options(change_frame=True),
        locked=True,
    )
    trace = {}
    chosen, _, _ = cd.pick_frame(
        None, {"start": 0.0, "end": 8.0}, [], trace=trace, context=ctx, exclude_time=5.0
    )
    assert chosen == candidates[0][0] and trace["source_timestamp_sec"] == 2.0
    assert sum(c["type"] == "image_url" for c in calls[0]) == 1


def test_scene_with_title_evidence_precedes_first_shot(monkeypatch):
    from backend.services.studio import publish_kit as kit

    rows = [
        {"text": "First topic", "start": 1, "end": 3},
        {"text": "Other topic", "start": 6, "end": 8},
    ]
    monkeypatch.setattr(kit, "_scene_rows", lambda *a: rows)
    scenes = [{"start": 0, "end": 4}, {"start": 5, "end": 9}]
    scene, evidence = kit.cover_scene("p", scenes, "Other topic")
    assert scene == scenes[1] and evidence == rows[1:]


def test_studio_first_cover_then_automatic_model_job_reuses_decision(
    setup_plan, tmp_path, monkeypatch
):
    import json
    from backend.core import image_providers
    from backend.services import cover, publish_export
    from backend.services.studio import publish_kit as kit, store

    candidates, _, calls = setup_plan
    monkeypatch.setenv("AUTOCLIP_DATA_DIR", str(tmp_path))
    title = "最好的12个月？"
    rows = [{"text": title, "start": 1.0, "end": 7.0}]
    cfg = cover.CoverConfig(
        enabled=True,
        api_key="fixture",
        model="offline-model",
        design_mode="editorial_edit",
        allow_send_frame=True,
    )
    monkeypatch.setattr(cover, "load_config", lambda: cfg)
    monkeypatch.setattr(kit, "_scene_rows", lambda *a: rows)
    monkeypatch.setattr(
        publish_export, "_probe", lambda *a: {"width": 1280, "height": 720}
    )
    monkeypatch.setattr(kit, "_title_ok", lambda *a: True)
    requests = []

    def generate(*, request, **kwargs):
        requests.append(request)
        return candidates[1][0]

    monkeypatch.setattr(image_providers, "generate_image", generate)
    store.directory("fixture").mkdir(parents=True)
    store.write("fixture", {"jobs": [{"job_id": "render", "title": title}]})
    args = ("fixture", "render", "douyin")
    draft = {"scenes": [{"start": 0.0, "end": 8.0}], "title": title}
    kit.design_cover("fixture", None, draft, "render", "douyin", title, "variant")
    assert len(calls) == 1 and not requests
    assert kit.ai_cover(*args, variant_id="variant", reuse=True) == "model"
    assert len(calls) == len(requests) == 1
    assert requests[0].reference == candidates[1][0]
    assert "眼神右方的暗墙" in requests[0].prompt
    meta = json.loads(kit.cd_meta_path(*args, "variant").read_bytes())
    assert (
        meta["visual_review"] == "pending"
        and meta["brief"]["source"]["source_timestamp_sec"] == 5.0
    )
    kit.design_cover("fixture", None, draft, "render", "douyin", title, "variant")
    assert kit.ai_cover(*args, variant_id="variant", reuse=True) == "model"
    assert len(calls) == len(requests) == 1


def test_local_question_cover_prioritizes_the_approved_question_cue(
    setup_plan, monkeypatch
):
    from backend.services import cover_planner as planner

    candidates, _, _ = setup_plan
    rows = [
        {"start": 0.5, "end": 3.0, "text": "What changed?"},
        {"start": 3.0, "end": 8.0, "text": "Our approach changed."},
    ]
    monkeypatch.setattr(intelligence, "source_frame_analysis_allowed", lambda: False)
    ctx = planner.context(
        "What changed?", "youtube_long", (1280, 720), cb.Options(), locked=True
    )
    trace = {}
    photo, _, _ = cd.pick_frame(
        None, {"start": 0.0, "end": 8.0}, rows, context=ctx, trace=trace
    )
    assert photo == candidates[0][0]
    assert trace["source_timestamp_sec"] < 3.0


def test_per_line_type_directions_from_visual_provider_reach_image_prompt(setup_plan):
    _, reply, calls = setup_plan
    reply["typography"] = ["第一行使用细黑体", "第二行使用窄粗黑体"]
    _, brief = pick()
    assert len(calls) == 1
    assert brief.source["editorial_plan"]["status"] == "planned"
    prompt = cb.compile_prompt(brief)
    assert "第一行使用细黑体" in prompt and "第二行使用窄粗黑体" in prompt
