#!/usr/bin/env python3
"""社区看板纯函数测试。不访问 GitHub。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from community_board import (  # noqa: E402
    CATEGORIES,
    STATUSES,
    find_overlaps,
    plan_categories,
    plan_labels,
    plan_status_options,
    tokens,
)
from feature_signals import build_report  # noqa: E402
import datetime as dt


def test_tokens_share_subtitle_phrase() -> None:
    left = tokens("希望支持自动字幕样式")
    right = tokens("字幕样式模板")
    assert "字幕" in left & right
    assert "希望" not in left


def test_overlaps_ignore_short_titles() -> None:
    rows = find_overlaps([
        {"id": "a", "title": "字幕样式", "text": "烧录字幕时选样式"},
        {"id": "b", "title": "字幕样式模板", "text": "导出时套用字幕样式"},
        {"id": "c", "title": "Windows 签名", "text": "SmartScreen"},
    ])
    pairs = {(row["a"], row["b"]) for row in rows}
    assert ("a", "b") in pairs
    assert all("c" not in pair for pair in pairs)


def test_category_plan_creates_missing_and_updates_copy() -> None:
    plan = plan_categories([
        {"id": "1", "name": "Ideas", "emoji": ":bulb:", "description": "old", "isAnswerable": False},
        {"id": "2", "name": "General", "emoji": ":speech_balloon:", "description": "Chat about anything and everything here", "isAnswerable": False},
    ])
    created = {item["name"] for item in plan["create"]}
    assert {"Use Cases", "AI Models", "Q&A", "Announcements"} <= created
    assert "General" not in created
    updated = {item["name"] for item in plan["update"]}
    assert "Ideas" in updated
    assert "General" in updated


def test_labels_and_status_are_idempotent() -> None:
    assert plan_labels({status["label"] for status in STATUSES} | {"feature"}) == []
    existing = [
        {"id": f"opt-{spec['id']}", "name": spec["name"], "description": spec["description"], "color": spec["project_color"]}
        for spec in STATUSES
    ]
    assert plan_status_options(existing) is None
    rewritten = plan_status_options([{"id": "todo", "name": "Todo", "description": "", "color": "GRAY"}])
    assert rewritten is not None
    assert [item["name"] for item in rewritten] == [spec["name"] for spec in STATUSES]
    assert "id" not in rewritten[0]


def test_report_splits_backlog_and_window() -> None:
    since = dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc)
    report = build_report(
        {"ok": True, "note": "", "items": [
            {"id": "discussion:1", "title": "自动字幕样式", "text": "烧录时选择字幕样式", "created_at": "2026-09-10T00:00:00Z",
             "updated_at": "2026-09-10T00:00:00Z", "upvotes": 3, "comments": 1, "reactions": 0, "category": "Ideas", "url": "https://example.test/1"},
            {"id": "discussion:2", "title": "旧帖", "text": "太早", "created_at": "2026-08-01T00:00:00Z",
             "updated_at": "2026-08-01T00:00:00Z", "upvotes": 9, "comments": 0, "reactions": 0, "category": "Ideas", "url": "https://example.test/2"},
        ]},
        {"ok": True, "note": "", "items": [
            {"id": "issue:7", "number": 7, "title": "字幕样式", "text": "字幕样式已经在做", "labels": ["feature", "status:building"], "status": "building", "url": "https://example.test/i/7"},
            {"id": "issue:8", "number": 8, "title": "随便说说", "text": "还没进看板", "labels": ["feature"], "status": None, "url": "https://example.test/i/8"},
        ]},
        since=since,
    )
    assert [item["id"] for item in report["discussions"]["items"]] == ["discussion:1"]
    assert report["backlog"][0]["number"] == 7
    assert report["stray_feature_issues"][0]["number"] == 8
    assert any(row["a"] == "discussion:1" and row["b"] == "issue:7" for row in report["overlaps"])


def test_seed_file_matches_statuses() -> None:
    seed = json.loads((Path(__file__).resolve().parents[1] / "docs" / "community" / "roadmap-seed.json").read_text(encoding="utf-8"))
    assert set(seed["columns"]) == {spec["id"] for spec in STATUSES}
    slugs = {spec["slug"] for spec in CATEGORIES}
    assert {"ideas", "use-cases", "ai-models", "q-a", "announcements"} <= slugs
    for status_id, items in seed["columns"].items():
        for item in items:
            assert item["title"].strip()
            assert item["track"] in {"new-issue", "existing-issue", "readme"}
            if item["track"] == "existing-issue":
                assert isinstance(item["issue"], int)
            if status_id == "shipped":
                assert item["track"] == "readme"


if __name__ == "__main__":
    test_tokens_share_subtitle_phrase()
    test_overlaps_ignore_short_titles()
    test_category_plan_creates_missing_and_updates_copy()
    test_labels_and_status_are_idempotent()
    test_report_splits_backlog_and_window()
    test_seed_file_matches_statuses()
    print("ok")
