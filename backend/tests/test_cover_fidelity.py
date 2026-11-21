import io

import pytest
from PIL import Image

from backend.services import cover, cover_brief as cb
from backend.services.studio import intelligence
from backend.tests.test_cover_brief import brief


def jpeg(color):
    out = io.BytesIO()
    Image.new("RGB", (320, 180), color).save(out, format="JPEG")
    return out.getvalue()


def mock_title_layout(monkeypatch):
    from backend.services import cover_fidelity
    layout = cover_fidelity.TitleLayout(
        bbox_pct=(8, 16, 55, 32), align="left", emphasis="better", emphasis_color="#2288aa",
        lines=[dict(text="A better question?", color="#ffffff", weight="bold", height_pct=6)],
    )
    monkeypatch.setattr(cover_fidelity, "read_title_layout", lambda *_: layout)


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({}, "passed"),
        ({"cover_hands": 1}, "failed"),
        ({"cover_facing": "left"}, "failed"),
        ({"background": "changed"}, "failed"),
        ({"pose": "uncertain"}, "unavailable"),
        ({"hands": None}, "unavailable"),
    ],
)
def test_comparison_controls_model_adoption_after_ocr(monkeypatch, change, expected):
    frame, art = jpeg("#554030"), jpeg("#604530")
    verdict = dict(
        reference_hands=0,
        cover_hands=0,
        reference_facing="right",
        cover_facing="right",
        identity="preserved",
        hands="preserved",
        pose="preserved",
        orientation="preserved",
        background="preserved",
        body_boundary="preserved",
        evidence="两图主体和背景特征可见。",
    )
    calls = []
    mock_title_layout(monkeypatch)

    def vision(content, config):
        calls.append(
            [p["image_url"]["url"] for p in content if p["type"] == "image_url"]
        )
        return {**verdict, **change}

    monkeypatch.setattr(intelligence, "source_frame_analysis_allowed", lambda: True)
    monkeypatch.setattr(intelligence, "vision_call", vision)
    _, audit = cb.make(
        brief(frame),
        frame,
        cover.CoverConfig(enabled=True, base_url="fixture", model="offline"),
        can_send=True,
        generate=lambda _: art,
        check=lambda *_: True,
    )
    assert audit["result"] == ("model" if expected == "passed" else "local_design")
    assert audit["model_fidelity"]["status"] == expected
    expect_repair = change and change.get("hands", "") is not None
    assert [len(call) for call in calls] == ([2, 3] if expect_repair else [2])
    assert len(set(calls[0])) == 2


def test_existing_cover_survives_unavailable_comparison(monkeypatch):
    frame, art = jpeg("#554030"), jpeg("#604530")
    monkeypatch.setattr(intelligence, "source_frame_analysis_allowed", lambda: False)
    monkeypatch.setattr(
        intelligence, "vision_call", lambda *_: pytest.fail("No source-frame consent")
    )
    with pytest.raises(cb.Rejected) as exc:
        cb.make(
            brief(frame),
            frame,
            cover.CoverConfig(enabled=True, base_url="fixture", model="offline"),
            can_send=True,
            generate=lambda _: art,
            check=lambda *_: True,
            previous=True,
        )
    assert exc.value.audit["model_fidelity"]["status"] == "unavailable"


def test_opposite_single_face_landmarks_veto_even_without_visual_service(monkeypatch):
    from backend.services import cover_fidelity

    offsets = iter([-0.29, 0.277])
    monkeypatch.setattr(cover_fidelity, "_nose_offset", lambda _: next(offsets))
    monkeypatch.setattr(
        intelligence,
        "vision_call",
        lambda *_: pytest.fail("local reversal is decisive"),
    )
    result = cover_fidelity.compare(jpeg("#544030"), jpeg("#664530"))
    assert result["status"] == "failed" and result["changed"] == ["orientation"]


@pytest.mark.parametrize("previous", [False, True])
@pytest.mark.parametrize("repaired", ["preserved", "changed", "uncertain"])
def test_repair_sends_only_source_and_reads_rejected_layout_then_rechecks(monkeypatch, repaired, previous):
    frame, first, second = [jpeg(color) for color in ("#543", "#654", "#765")]
    generated, checked = [], []
    mock_title_layout(monkeypatch)

    def generate(request):
        generated.append(request)
        return [first, second][len(generated) - 1]

    def compare(source, artwork, layout_reference=None):
        checked.append((source, artwork, layout_reference))
        if artwork == first:
            return dict(status="failed", changed=["hands"], uncertain=[],
                        observations=dict(reference_hands=0, cover_hands=2, evidence="底边新增两只手"))
        return dict(status="passed" if repaired == "preserved" else "failed",
                    changed=[] if repaired == "preserved" else ["title_layout"],
                    candidate_sha256="checked")

    from backend.services import cover_fidelity
    monkeypatch.setattr(cover_fidelity, "compare", compare)
    _, audit = cb.make(brief(frame), frame, cover.CoverConfig(enabled=True, base_url="fixture", model="offline"),
                       can_send=True, generate=generate, check=lambda *_: True, previous=previous)
    assert len(generated) == 2
    assert generated[1].reference == frame and not getattr(generated[1], "layout_reference", None)
    assert "可见 0 只手" in generated[1].prompt and "#2288aa" in generated[1].prompt
    assert checked == [(frame, first, None), (frame, second, first)]
    assert audit["result"] == ("model" if repaired == "preserved" else "local_design")


@pytest.mark.parametrize(("layout", "status"), [("preserved", "passed"), ("changed", "failed"), (None, "unavailable")])
def test_repair_layout_must_be_visible_to_the_verifier(monkeypatch, layout, status):
    from backend.services import cover_fidelity

    frame, artwork, first = [jpeg(c) for c in ("#432", "#543", "#654")]
    def vision(content, _config):
        assert len([item for item in content if item["type"] == "image_url"]) == 3
        return dict(dict.fromkeys(cover_fidelity.ASPECTS, "preserved"),
                    reference_hands=0, cover_hands=0, reference_facing="left", cover_facing="left",
                    title_layout=layout, photo_quality="preserved", evidence="核对原帧的照片及首版标题")
    monkeypatch.setattr(intelligence, "source_frame_analysis_allowed", lambda: True)
    monkeypatch.setattr(intelligence, "vision_call", vision)
    assert cover_fidelity.compare(frame, artwork, first)["status"] == status


@pytest.mark.parametrize(("lines", "valid"), [(["A better", "question?"], True), (["A worse", "question?"], False)])
def test_layout_reader_binds_lines_to_the_approved_title(monkeypatch, lines, valid):
    from backend.services import cover_fidelity
    def vision(content, config):
        assert len([item for item in content if item["type"] == "image_url"]) == 1
        if "定位首版" in content[0]["text"]:
            return {"bbox": [150, 120, 850, 400]}
        return dict(bbox_pct=[5, 5, 60, 35], align="left", emphasis="better", emphasis_color="#aa2222",
                    lines=[dict(text=line, weight="bold", color="#ffffff", height_pct=8) for line in lines])
    monkeypatch.setattr(intelligence, "source_frame_analysis_allowed", lambda: True)
    monkeypatch.setattr(intelligence, "vision_call", vision)
    assert bool(cover_fidelity.read_title_layout(jpeg("#765"), "A better question?")) == valid


def test_bind_measured_lines_restores_fullwidth_punctuation():
    from backend.services.cover_fidelity import TitleLayout, _bind_title_lines
    layout = TitleLayout(bbox_pct=[40, 6, 96, 24], align="right", emphasis="12", emphasis_color="#4488ff",
                         lines=[dict(text=t, color="#ffffff", weight="bold", height_pct=8)
                                for t in ("最好的", "12个月?")])
    assert _bind_title_lines(layout, "最好的12个月？") and layout.lines[-1].text == "12个月？"
    assert not _bind_title_lines(layout, "最好的13个月？")
