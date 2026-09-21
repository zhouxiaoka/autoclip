#!/usr/bin/env python3
"""应用内反馈收件的纯函数测试。不访问 PostHog 或 GitHub。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingest_app_feedback import known_ids_in, plan_posts, public_body  # noqa: E402


def event(**overrides):
    base = {
        "timestamp": "2026-09-21T00:00:00Z",
        "feedback_id": "11111111-1111-4111-8111-111111111111",
        "category": "bug",
        "text": "进度停在分析中",
        "source": "failure",
        "stage": "ANALYZE",
        "app_version": "1.3.1",
        "os": "windows",
        "arch": "x64",
        "llm_provider": "ollama",
        "llm_model": "qwen2.5",
        "error_message": "timeout sk-test-abc1234567890",
        "contact": "person@example.com",
    }
    base.update(overrides)
    return base


def test_bug_becomes_issue_without_email_or_secret() -> None:
    posts = plan_posts([event()], set())
    assert len(posts) == 1
    post = posts[0]
    assert post["kind"] == "issue"
    assert post["labels"] == ["bug", "needs-triage", "from-app"]
    assert "person@example.com" not in post["body"]
    assert "sk-test-abc1234567890" not in post["body"]
    assert "[redacted]" in post["body"]
    assert "11111111-1111-4111-8111-111111111111" in post["body"]


def test_ideas_and_questions_go_to_discussions() -> None:
    posts = plan_posts([
        event(timestamp="2026-09-21T00:00:02Z", feedback_id="33333333-3333-4333-8333-333333333333", category="other", text="安装包在哪下载"),
        event(timestamp="2026-09-21T00:00:01Z", feedback_id="22222222-2222-4222-8222-222222222222", category="idea", text="希望导出时记住比例"),
    ], set())
    assert [post["kind"] for post in posts] == ["discussion", "discussion"]
    assert [post["category"] for post in posts] == ["Ideas", "Q&A"]
    assert posts[0]["title"].startswith("[想法] ")


def test_known_ids_and_invalid_rows_are_skipped() -> None:
    known = known_ids_in([
        "反馈编号：11111111-1111-4111-8111-111111111111",
        "<!-- feedback-id:44444444-4444-4444-8444-444444444444 -->",
    ])
    posts = plan_posts([
        event(),
        event(feedback_id="not-a-uuid", text="这条没有编号"),
        event(feedback_id="55555555-5555-4555-8555-555555555555", category="nope", text="分类不对"),
        event(feedback_id="66666666-6666-4666-8666-666666666666", text="短"),
        event(feedback_id="77777777-7777-4777-8777-777777777777", text="这条是新的故障"),
    ], known)
    assert [post["feedback_id"] for post in posts] == ["77777777-7777-4777-8777-777777777777"]


def test_same_batch_and_cap() -> None:
    rows = [
        event(timestamp=f"2026-09-21T00:00:{index:02d}Z", feedback_id=f"88888888-8888-4888-8888-{index:012d}", text=f"第 {index} 条反馈内容")
        for index in range(25)
    ]
    rows.append(event(
        timestamp="2026-09-21T00:00:03Z",
        feedback_id="88888888-8888-4888-8888-000000000000",
        text="重复的第一条也应该被丢掉",
    ))
    posts = plan_posts(rows, set(), limit=20)
    assert len(posts) == 20
    assert len({post["feedback_id"] for post in posts}) == 20


def test_public_body_has_no_contact_field() -> None:
    item = {
        "feedback_id": "11111111-1111-4111-8111-111111111111",
        "category": "bug",
        "text": "打不开设置页",
        "source": "settings",
        "stage": "",
        "error_message": "",
        "version": "1.3.1",
        "os": "macos",
        "arch": "arm64",
        "llm_provider": "",
        "llm_model": "",
    }
    body = public_body(item)
    assert "contact" not in body
    assert "邮箱留在维护者的收件记录里" in body


if __name__ == "__main__":
    test_bug_becomes_issue_without_email_or_secret()
    test_ideas_and_questions_go_to_discussions()
    test_known_ids_and_invalid_rows_are_skipped()
    test_same_batch_and_cap()
    test_public_body_has_no_contact_field()
    print("ok")
