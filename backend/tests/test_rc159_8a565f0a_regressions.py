"""Regression tests for 1.5.9-rc dual-platform QA acceptance findings (8a565f0a).

Covers:
1. Project list pagination returns newest-first beyond 20 projects (Windows QA saw
   "我的项目 20" stuck on the oldest 20 SQLite rows after leaving the results page).
2. post_copy accepts equivalent valid JSON shapes on attempt 1 without burning a
   second model call, and logs a safe closed-set rejection reason when truly invalid.
3. cover_planner increments degrade_count BEFORE intelligence.vision_call emits
   llm_request_finished so the degrading event itself records degrade_count=1
   without double-counting.
"""
from __future__ import annotations

import io
import json
import logging
from datetime import datetime, timedelta, timezone

from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core import llm_emit, llm_telemetry
from backend.models.base import Base
from backend.models.project import Project, ProjectStatus, ProjectType
from backend.schemas.base import PaginationParams
from backend.schemas.project import ProjectFilter, ProjectStatus as SchemaProjectStatus
from backend.services import cover_planner
from backend.services.project_service import ProjectService
from backend.services.studio import cover_design as cd, intelligence, post_copy


def _jpeg(color: str) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (160, 90), color).save(buf, format="JPEG")
    return buf.getvalue()


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_projects_paginated_returns_newest_first_beyond_page_size(monkeypatch):
    monkeypatch.setattr(
        "backend.services.studio.project_completion.sync_project_completion",
        lambda *_args, **_kwargs: None,
    )
    db = _make_session()
    try:
        base_time = datetime(2026, 11, 1, 8, 0, 0, tzinfo=timezone.utc)
        for idx in range(1, 26):
            status = ProjectStatus.COMPLETED if idx % 2 == 1 else ProjectStatus.FAILED
            db.add(
                Project(
                    id=f"proj-{idx:02d}",
                    name=f"Project {idx:02d}" + (" Alpha" if idx in (3, 25) else ""),
                    description=f"desc {idx:02d}",
                    project_type=ProjectType.DEFAULT,
                    status=status,
                    created_at=base_time + timedelta(hours=idx),
                    updated_at=base_time + timedelta(hours=idx),
                )
            )
        db.commit()

        service = ProjectService(db)
        page1 = service.get_projects_paginated(PaginationParams(page=1, size=20))
        assert page1.pagination.total == 25
        assert page1.pagination.has_next is True
        assert [item.id for item in page1.items] == [f"proj-{idx:02d}" for idx in range(25, 5, -1)]

        page2 = service.get_projects_paginated(PaginationParams(page=2, size=20))
        assert page2.pagination.has_next is False
        assert [item.id for item in page2.items] == [f"proj-{idx:02d}" for idx in range(5, 0, -1)]

        completed = service.get_projects_paginated(
            PaginationParams(page=1, size=5),
            ProjectFilter(status=SchemaProjectStatus.COMPLETED),
        )
        assert completed.pagination.total == 13
        assert [item.id for item in completed.items] == ["proj-25", "proj-23", "proj-21", "proj-19", "proj-17"]

        searched = service.get_projects_paginated(
            PaginationParams(page=1, size=10),
            ProjectFilter(search="Alpha"),
        )
        assert searched.pagination.total == 2
        assert [item.id for item in searched.items] == ["proj-25", "proj-03"]
    finally:
        db.close()


def test_post_copy_normalizes_equivalent_json_shapes_without_retry():
    lines = ["We over-diversified on the product side and need to refocus."]

    for shape in (
        {"douyin": {"title": "我们产品想做太多了", "description": "复盘失误并聚焦核心", "tags": ["product"]}},
        {"title": "我们产品想做太多了", "description": "复盘失误并聚焦核心", "tags": ["product"]},
        {"posts": [{"platform": "douyin", "title": "我们产品想做太多了", "description": "复盘失误并聚焦核心", "tags": ["product"]}]},
    ):
        calls = []

        def fake_call(_prompt, _payload, _shape=shape):
            calls.append(1)
            return _shape

        result = post_copy.build_posts("产品复盘", lines, ["douyin"], call=fake_call)
        assert len(calls) == 1
        assert result["douyin"]["title"] == "我们产品想做太多了"
        assert result["douyin"]["description"] == "复盘失误并聚焦核心"
        assert result["douyin"]["tags"] == ["product"]


def test_post_copy_rejection_logs_safe_reason_code(caplog):
    secret_user_text = "TOP_SECRET_USER_PROMPT_FRAGMENT"
    responses = iter([
        {"unexpected_key": secret_user_text},
        {"posts": {"douyin": {"title": "聚焦核心产品", "description": "保持克制", "tags": []}}},
    ])

    with caplog.at_level(logging.WARNING, logger="backend.services.studio.post_copy"):
        result = post_copy.build_posts("原标题", ["line one"], ["douyin"], call=lambda *_: next(responses))

    assert result["douyin"]["title"] == "聚焦核心产品"
    warnings = [rec.getMessage() for rec in caplog.records if "Post copy rejected" in rec.getMessage()]
    assert len(warnings) == 1
    assert "error_type=ValueError" in warnings[0]
    assert "reason=posts_missing" in warnings[0]
    assert secret_user_text not in warnings[0]


def _fake_vision_response(payload: dict):
    class FakeResp:
        headers = {"Content-Type": "application/json"}

        def __init__(self):
            self._buf = io.BytesIO(json.dumps(payload).encode("utf-8"))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size=-1):
            return self._buf.read(size)

    return FakeResp()


def _cover_ctx():
    return {
        "title": "聚焦核心产品",
        "subtitle": "",
        "platform": "douyin",
        "aspect": "portrait",
        "design": {"accent": "", "emphasis": ""},
    }


def _cover_candidates():
    return [
        (_jpeg("navy"), None, 0.0, False, 1.0),
        (_jpeg("maroon"), None, 0.0, False, 5.0),
    ]


def test_cover_planner_degrade_count_reaches_llm_request_finished_before_emit(monkeypatch):
    monkeypatch.setattr(
        "backend.services.studio.vision_settings.effective",
        lambda: {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "api_key": "sk-test", "model": "qwen4-max", "timeout": 30},
    )
    monkeypatch.setattr(intelligence, "source_frame_analysis_allowed", lambda: True)
    monkeypatch.setattr(cd, "_thumb", lambda _raw: "data:image/jpeg;base64,AA==")

    events = []
    monkeypatch.setattr(llm_emit, "_submit_event", lambda name, props, **kw: events.append((name, dict(props))) or True)

    # Case 1: output_truncated -> VisionRequestError inside vision_call
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: _fake_vision_response({
            "choices": [{"message": {"content": '{"best": 1'}, "finish_reason": "length"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }),
    )
    with llm_telemetry.track_run():
        outcome = cover_planner.inspect(_cover_candidates(), _cover_ctx(), [])
        snap = llm_telemetry.run_snapshot()
    assert outcome["status"] == "vision_unavailable"
    assert snap["degrade_count"] == 1
    assert len(events) == 1
    assert events[0][0] == "llm_request_finished"
    assert events[0][1]["degrade_count"] == 1

    # Case 2: valid JSON response but unusable direction -> invalid_direction
    events.clear()
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: _fake_vision_response({
            "choices": [{"message": {"content": json.dumps({"best": 99})}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10},
        }),
    )
    with llm_telemetry.track_run():
        outcome = cover_planner.inspect(_cover_candidates(), _cover_ctx(), [])
        snap = llm_telemetry.run_snapshot()
    assert outcome["status"] == "invalid_direction"
    assert snap["degrade_count"] == 1
    assert len(events) == 1
    assert events[0][1]["degrade_count"] == 1

    # Case 3: explicit best=0 -> no_suitable_frame (NOT a degrade)
    events.clear()
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=None: _fake_vision_response({
            "choices": [{"message": {"content": json.dumps({"best": 0})}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10},
        }),
    )
    with llm_telemetry.track_run():
        outcome = cover_planner.inspect(_cover_candidates(), _cover_ctx(), [])
        snap = llm_telemetry.run_snapshot()
    assert outcome["status"] == "no_suitable_frame"
    assert snap["degrade_count"] == 0
    assert len(events) == 1
    assert events[0][1]["degrade_count"] == 0
