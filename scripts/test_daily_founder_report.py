#!/usr/bin/env python3
"""日报口径的纯函数测试。不访问 PostHog / Sentry / GitHub。"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from daily_founder_report import (  # noqa: E402
    filter_from_app,
    headline_query,
    hogql_dt,
    render_markdown,
    utc_day_bounds,
)


def test_utc_day_is_complete_calendar_day() -> None:
    start, end = utc_day_bounds(dt.date(2026, 10, 1))
    assert start.isoformat() == "2026-10-01T00:00:00+00:00"
    assert end.isoformat() == "2026-10-02T00:00:00+00:00"
    assert hogql_dt(start) == "2026-10-01 00:00:00"


def test_headline_query_keeps_official_filters() -> None:
    start, end = utc_day_bounds(dt.date(2026, 10, 1))
    sql = headline_query(start, end)
    assert "feedback_submitted" in sql
    assert "category = 'bug'" in sql
    assert "1.5.0" in sql
    assert "material_origin IN ('user', 'sample')" in sql
    assert "studio_download_saved" in sql
    assert "outcome = 'completed'" in sql
    assert "toDateTime('2026-10-01 00:00:00')" in sql
    assert "toDateTime('2026-10-02 00:00:00')" in sql
    assert "telemetry_test" not in sql


def test_render_uses_official_three_numbers() -> None:
    text = render_markdown({
        "day": "2026-10-01",
        "posthog": {
            "ok": True,
            "note": "",
            "metrics": {
                "from_app_bugs_15": 0,
                "from_app_bugs_all": 4,
                "first_real_clips": 0,
                "first_sample_clips": 0,
                "dau_15_windows": 18,
                "dau_15_macos": 1,
                "gen_fail_user": 4,
            },
        },
        "github": {"ok": True, "items": [{"number": 249, "title": "[反馈] 测试", "url": "https://example.test/249"}], "note": ""},
        "sentry": {"ok": True, "items": [{"id": "PYTHON-FASTAPI-1T", "title": "PipelineFailure", "permalink": "https://example.test/1T"}], "note": ""},
    })
    assert "① 1.5 应用内故障 | **0**" in text
    assert "② 真实首次出片 / 示例 | **0** / 0" in text
    assert "③ 1.5.0 Windows / Mac | **18** / **1**" in text
    assert "全版本应用内故障 4" in text
    assert "制作失败设备 4" in text
    assert "#249" in text
    assert "PYTHON-FASTAPI-1T" in text
    assert "17682" not in text


def test_from_app_filter_uses_label_and_utc_day() -> None:
    items = filter_from_app([
        {"number": 249, "title": "[反馈] 新", "url": "https://example.test/249", "createdAt": "2026-10-01T09:33:28Z", "labels": [{"name": "from-app"}, {"name": "bug"}]},
        {"number": 247, "title": "[反馈] 旧", "url": "https://example.test/247", "createdAt": "2026-09-30T14:32:16Z", "labels": [{"name": "from-app"}]},
        {"number": 122, "title": "功能", "url": "https://example.test/122", "createdAt": "2026-10-01T02:00:00Z", "labels": [{"name": "feature"}]},
        {"number": 0, "title": "", "createdAt": "0001-01-01T00:00:00Z", "labels": None},
    ], dt.date(2026, 10, 1))
    assert [item["number"] for item in items] == [249]


def test_render_explains_missing_sources() -> None:
    text = render_markdown({
        "day": "2026-09-30",
        "posthog": {"ok": False, "note": "没有 POSTHOG_PERSONAL_API_KEY", "metrics": {}},
        "github": {"ok": False, "items": [], "note": "没有 gh，也没有 GH_TOKEN"},
        "sentry": {"ok": False, "items": [], "note": "没有 SENTRY_AUTH_TOKEN，跳过新增 Issue"},
    })
    assert "没有 POSTHOG_PERSONAL_API_KEY" in text
    assert "没有 SENTRY_AUTH_TOKEN" in text
    assert "—" in text


if __name__ == "__main__":
    test_utc_day_is_complete_calendar_day()
    test_headline_query_keeps_official_filters()
    test_render_uses_official_three_numbers()
    test_from_app_filter_uses_label_and_utc_day()
    test_render_explains_missing_sources()
    print("ok")
