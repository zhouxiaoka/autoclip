from __future__ import annotations

import io
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from backend.api.v1.studio import CoverRedesignBody
from backend.services import cover_brief as cb
from backend.services.studio import jobs, publish_kit, store


def _jpeg_bytes(color=(30, 60, 90), size=(640, 360)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def test_cover_redesign_body_accepts_allow_reference_once():
    default_body = CoverRedesignBody()
    assert default_body.allow_reference_once is False
    once_body = CoverRedesignBody(title="奥特曼复盘：我们产品做得太多了", allow_reference_once=True)
    assert once_body.allow_reference_once is True


def test_cross_language_confirmed_title_with_reference_once_calls_image_model(monkeypatch):
    frame = _jpeg_bytes()
    rows = [{"start": 0.0, "end": 45.0, "text": "I think we were trying to do too much on the product side."}]
    # Confirmed Chinese title on an English transcript MUST produce status='ready' (not needs_source_validation)
    brief = cb.plan(
        frame,
        title="奥特曼复盘：我们产品做得太多了",
        strategy="bilibili",
        size=(1146, 717),
        origin={"kind": "video_frame", "asset_id": "raw/input"},
        rows=rows,
        options=cb.Options(mode="editorial_edit"),
        locked=True,
    )
    assert brief.status == "ready"

    called = []
    cfg = SimpleNamespace(
        enabled=True,
        configured=True,
        allow_send_frame=False,
        provider="dashscope",
        model="qwen-image-2.1-pro",
    )
    monkeypatch.setattr(
        "backend.services.cover_fidelity.compare",
        lambda *_a, **_kw: {"status": "passed", "changed": [], "uncertain": [], "candidate_sha256": "deadbeef"},
    )
    data, audit = cb.make(
        brief,
        frame,
        cfg,
        can_send=True,
        allow_model=True,
        generate=lambda req: (called.append(req.model), _jpeg_bytes((80, 90, 100), (1146, 717)))[1],
        check=lambda _data, _lines: True,
    )
    assert called == ["qwen-image-2.1-pro"]
    assert audit["result"] == "model"
    assert audit["fallback_reason"] is None
    assert len(data) > 0


def test_variant_request_ai_cover_honors_allow_reference_once_when_global_opt_out(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(store, "directory", lambda pid: tmp_path / pid)
    project_id = "proj-cover-once"
    variant_id = "var-1"
    render_job_id = "a" * 32
    state = {
        "project_id": project_id,
        "output_variants": [
            {
                "id": variant_id,
                "strategy_id": "douyin",
                "render_job_id": render_job_id,
                "status": "completed",
                "cover": "design",
            }
        ],
        "jobs": [{"job_id": render_job_id, "title": "奥特曼复盘：我们产品做得太多了", "status": "completed"}],
    }
    (tmp_path / project_id).mkdir(parents=True, exist_ok=True)
    store.write(project_id, state)

    cfg = SimpleNamespace(
        enabled=True,
        configured=True,
        allow_send_frame=False,
        design_mode="crop_grade_text_only",
        provider="dashscope",
        model="qwen-image-2.1-pro",
    )
    monkeypatch.setattr("backend.services.cover.load_config", lambda: cfg)

    submitted = []

    def fake_submit(fn, *args, **kwargs):
        submitted.append((fn, args, kwargs))
        # Run synchronously to verify _ai_cover_job forwards allow_reference_once=True to publish_kit.ai_cover
        fn(*args, **{k: v for k, v in kwargs.items() if not k.startswith("_")})

    monkeypatch.setattr(jobs.cover_executor, "submit", fake_submit)
    captured_ai_cover = {}

    def fake_ai_cover(*args, **kwargs):
        captured_ai_cover["args"] = args
        captured_ai_cover["kwargs"] = kwargs
        return "model"

    monkeypatch.setattr(publish_kit, "ai_cover", fake_ai_cover)

    task = jobs.request_ai_cover(
        project_id,
        variant_id,
        render_job_id,
        allow_local=True,
        options=cb.Options(mode="editorial_edit"),
        title="奥特曼复盘：我们产品做得太多了",
        allow_reference_once=True,
    )
    assert task is not None
    assert submitted and submitted[0][2]["mode"] == "ai"
    assert captured_ai_cover["kwargs"].get("allow_reference_once") is True
    assert captured_ai_cover["kwargs"].get("title") == "奥特曼复盘：我们产品做得太多了"
    # Global setting remains opt-out
    assert cfg.allow_send_frame is False
    # Public status must not leak internal allow_reference_once key
    status = jobs.ai_cover_status(project_id, variant_id)
    assert status["status"] == "completed"
    assert "allow_reference_once" not in status


def test_measure_title_ink_skips_cleanly_without_numpy(monkeypatch):
    import builtins
    from backend.services import cover_fidelity

    real_import = builtins.__import__

    def block_numpy(name, *args, **kwargs):
        if name == "numpy" or name.startswith("numpy."):
            raise ModuleNotFoundError("No module named 'numpy'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", block_numpy)
    crop = Image.new("RGB", (200, 100), (20, 20, 20))
    layout = cover_fidelity.TitleLayout(
        bbox_pct=(10, 10, 90, 90),
        align="left",
        lines=[cover_fidelity.TitleLine(text="测试标题", color="#FFFFFF", weight="bold", height_pct=10.0)],
        emphasis="",
        emphasis_color="#FFFFFF",
    )
    # Must not raise ModuleNotFoundError on Windows portable Python builds without numpy
    cover_fidelity._measure_title_ink(crop, layout, (10, 10, 90, 90), 1080)
    assert layout.align == "left"
