"""Cover production contracts, with local reference photos and offline image providers."""

import io
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from PIL import Image

from backend.services import cover, cover_brief as cb
from backend.services.studio import publish_kit
from backend.tests.test_cover import _project, data_dir, fake_frame  # noqa: F401 (shared fixtures)


@pytest.mark.parametrize(
    "observed",
    [
        "最好的12个月",
        "最好的12个月？记者",
        "最好的13个月？",
        "最坏的12个月？",
        "最好的12个月？最好的12个月？",
    ],
)
def test_copy_is_a_whitelist(observed):
    assert not cb.matches(observed, "最好的12个月？")
    assert not cb.matches("can do it", "cannot do it")
    assert cb.matches("I LOVE\nCOMPETITION", "I LOVE COMPETITION")


def brief(frame, **changes):
    values = dict(
        title="A better question?",
        strategy="youtube_long",
        size=(320, 180),
        origin={"kind": "user_frame"},
        locked=True,
        options=cb.Options(mode="editorial_edit"),
    )
    return cb.plan(frame, **{**values, **changes})


@pytest.mark.parametrize("flag", ["allow_cutout", "allow_background_replace"])
def test_edit_permissions_are_independent(fake_frame, flag):
    terms = {"allow_cutout": "可沿真实轮廓抠图", "allow_background_replace": "可替换为"}
    edit = brief(fake_frame, options=cb.Options(mode="editorial_edit", **{flag: True}))
    assert all((term in cb.compile_prompt(edit)) == (key == flag == "allow_cutout") for key, term in terms.items())
    assert not edit.permissions["allow_background_replace"]
    strict = brief(fake_frame, options=cb.Options(**{flag: True}))
    assert not any(strict.permissions[k] for k in terms)
    assert not strict.copy_spec["show_nameplate"]


@pytest.mark.parametrize("entry", ["publish", "studio"])
def test_wrong_text_retries_with_same_photo_and_delivers_target_size(data_dir, fake_frame, monkeypatch, entry):
    from backend.core import image_providers
    from backend.services.studio import store

    cfg = cover.CoverConfig(
        enabled=True,
        model="offline-model",
        api_key="fixture",
        allow_send_frame=True,
        design_mode="editorial_edit",
    )
    monkeypatch.setattr(cover, "load_config", lambda: cfg)
    requests = []
    title = "最好的12个月？"

    def generate(*, request, **_):
        requests.append(request)
        return fake_frame

    if entry == "publish":
        _project(data_dir)
        monkeypatch.setattr(cover, "generate_image", generate)
        monkeypatch.setattr(
            cover,
            "read_image_text",
            lambda **_: title.rstrip("？") if len(requests) == 1 else title,
        )
        cover.generate_cover(project_id="p1", clip_id="1", title=title)
        meta = cover.read_cover_meta("p1", "1", "bilibili")
        artifact = cover.cover_path("p1", "1", "bilibili")
    else:
        _project(data_dir)
        store.write("p1", {"jobs": [{"job_id": "render", "title": title}]})
        publish_kit.frame_path("p1", "render", "xiaohongshu").write_bytes(fake_frame)
        monkeypatch.setattr(image_providers, "generate_image", generate)
        monkeypatch.setattr(publish_kit, "_title_ok", lambda *_: len(requests) > 1)
        assert publish_kit.ai_cover("p1", "render", "xiaohongshu", title=title) == "model"
        meta = json.loads(publish_kit.cd_meta_path("p1", "render", "xiaohongshu").read_text())
        artifact = publish_kit.kit_cover_path("p1", "render", "xiaohongshu")
    assert len(requests) == 2 and all(req.reference == fake_frame for req in requests)
    assert (artifact.parent / meta["model_original_file"]).read_bytes() == fake_frame
    assert meta["prompt"] == requests[-1].prompt
    assert meta["visual_review"] == "pending" and meta["checks"]["text"] == "passed"
    with Image.open(artifact) as img:
        assert img.size == (meta["export_spec"]["width"], meta["export_spec"]["height"])


def test_uncertain_source_cannot_use_editorial_request_or_assert_a_claim(fake_frame):
    b = brief(
        fake_frame,
        title="Everyone panicked",
        locked=False,
        origin={"kind": "unverified"},
    )
    assert b.status == "needs_source_validation" and b.content["evidence_status"] == "insufficient"
    with pytest.raises(ValueError, match="核实"):
        cb.make(
            b,
            fake_frame,
            None,
            can_send=True,
            generate=lambda *_: pytest.fail(),
            check=None,
        )


def test_cache_identity_includes_every_edit_input(fake_frame):
    b = brief(fake_frame)

    def key(item):
        return cb.fingerprint(item, "provider", "model")

    assert (
        len(
            {
                key(b),
                key(brief(fake_frame, title="New title")),
                key(brief(fake_frame, options=cb.Options())),
                key(
                    brief(
                        fake_frame,
                        options=cb.Options(recipe="bold_statement", mode="editorial_edit"),
                    )
                ),
                key(brief(fake_frame, size=(100, 200))),
                key(brief(fake_frame, origin={"kind": "user_frame", "asset_id": "b"})),
                cb.fingerprint(b, "provider", "other"),
            }
        )
        == 7
    )


def test_late_worker_cannot_change_winning_image_or_sibling_variant(data_dir, fake_frame):
    args = ("p", "render", "douyin")
    meta = publish_kit.cd_meta_path(*args, "v1")
    second = publish_kit.cd_meta_path(*args, "v2")
    first_token = cb.begin(meta)
    ready = Event()

    def late():
        ready.wait(5)
        cb.save(meta, first_token, b"outdated", fake_frame, {})

    with ThreadPoolExecutor(1) as executor:
        loser = executor.submit(late)
        cb.save(meta, cb.begin(meta), b"new", fake_frame, {"result": "model"})
        cb.save(second, cb.begin(second), b"sibling", fake_frame, {"result": "local_design"})
        ready.set()
        with pytest.raises(ValueError, match="取代"):
            loser.result()
    assert publish_kit.cover_file(*args, "v1")[0].read_bytes() == b"new"
    assert publish_kit.cover_file(*args, "v2")[0].read_bytes() == b"sibling"


@pytest.mark.parametrize("send,supported", [(False, True), (True, False)])
def test_no_text_only_request_when_reference_cannot_be_used(fake_frame, send, supported):
    from backend.core.image_providers import ImageError

    calls = []

    def unavailable(req):
        calls.append(req.reference)
        raise ImageError("unsupported", unsupported_edit=True)

    data, state = cb.make(
        brief(fake_frame),
        fake_frame,
        cover.CoverConfig(enabled=True, api_key="fixture"),
        can_send=send,
        generate=unavailable,
        check=lambda *_: None,
    )
    assert calls == ([fake_frame] if send else [])
    assert state["result"] == "local_design" and state["visual_review"] == "pending"
    assert Image.open(io.BytesIO(data)).size == (320, 180)


def test_failed_replacement_preserves_previous_file_and_records_unavailable(data_dir, fake_frame, monkeypatch):
    from backend.core.image_providers import ImageError

    _project(data_dir)
    prior = cover.generate_cover(project_id="p1", clip_id="1", title="保留原图", force_local=True)
    meta = cover.meta_path("p1", "1", "bilibili")
    before = meta.read_bytes()
    cfg = cover.CoverConfig(
        enabled=True, api_key="fixture", provider="openai", model="fixture-image", allow_send_frame=True
    )
    monkeypatch.setattr(cover, "load_config", lambda: cfg)
    monkeypatch.setattr(cover, "generate_image", lambda **_: fake_frame)

    def fail(**_):
        raise ImageError("offline")

    monkeypatch.setattr(cover, "read_image_text", fail)
    with pytest.raises(cover.ModelCoverRejected):
        cover.generate_cover(
            project_id="p1", clip_id="1", title="换封面？", design_options='{"mode":"editorial_edit"}'
        )
    assert meta.read_bytes() == before and cover.get_cover("p1", "1")["path"] == prior["path"]
    rejection = json.loads(meta.with_suffix(".last-failure.json").read_text())
    assert rejection["previous_preserved"] and rejection["validation"] == "unavailable"
    assert rejection["fallback_reason"] == "text_unavailable" and rejection["attempts"] == 1


def test_mobile_typesetting_keeps_units_and_short_emphasis_together(fake_frame):
    b = cb.plan(
        fake_frame,
        title="最好的12个月？",
        strategy="douyin",
        size=(1080, 1920),
        origin={"kind": "user_frame"},
        locked=True,
        options=cb.Options(recipe="photo_focus", accent="#5A8BFF", emphasis="12"),
    )
    assert b.design["typesetting"]["lines"] == ["最好的12个月？"]
    english = brief(
        fake_frame,
        title="what is the biggest risk for open AI?",
        size=(1280, 720),
        options=cb.Options(recipe="tech_question", emphasis="biggest risk"),
        centre=0.75,
    )
    lines = english.design["typesetting"]["lines"]
    assert any("biggest risk" in line for line in lines) and any("open AI?" in line for line in lines)
    assert english.copy_spec["exact_text"] in cb.compile_prompt(english)


def test_model_request_is_independent_of_local_poster_geometry(fake_frame):
    b = brief(fake_frame)
    original = cb.compile_prompt(b)
    b.design.update(composition_intent="LOCAL CROP GUIDE", layout="photo_above_caption")
    b.design["typesetting"].update(lines=["LOCAL PROOF"], font_size=7, text_origin=[1, 2])
    b.design["rationale"]["typography"] = "LOCAL CAPTION BLOCK"
    assert cb.compile_prompt(b) == original
    assert b.copy_spec["exact_text"] in original
    b.design["protected_regions"] = ["visible_shoulders_and_chest", "right_look_room"]
    directed = cb.compile_prompt(b)
    assert all(word in directed for word in ("双肩", "胸口", "右侧"))
    assert "LOCAL" not in directed


def test_local_face_collision_does_not_block_editorial_image_request(fake_frame, monkeypatch):
    def collision(_brief):
        raise ValueError("画幅与文字要求冲突，无法保留清晰脸部")

    monkeypatch.setattr(cb, "_measure", collision)
    b = brief(fake_frame)
    assert b.status == "ready"
    cfg = cover.CoverConfig(enabled=True, base_url="fixture", model="offline")
    def make_image(can_send, previous=False):
        return cb.make(b, fake_frame, cfg, can_send=can_send, generate=lambda req: req.reference,
                       check=lambda *_: True, previous=previous)
    assert make_image(True)[1]["result"] == "model"
    assert make_image(False)[1]["result"] == "source_frame"
    with pytest.raises(cb.Rejected):
        make_image(False, previous=True)
    local = brief(fake_frame, options=cb.Options(mode="crop_grade_text_only"))
    assert local.status == "constraint_conflict"
