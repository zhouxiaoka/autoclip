#!/usr/bin/env python3
"""把最近的 Discussions 和未关闭的 feature issue 收成一份信号稿。

语义聚类由 Agent 来做。这里只排序、标出用词重叠，避免脚本假装自己懂产品。

用法
  python3 scripts/feature_signals.py
  python3 scripts/feature_signals.py --json
  python3 scripts/feature_signals.py --days 30
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from community_board import (  # noqa: E402
    discussion_heat,
    fetch_discussions,
    fetch_open_issues,
    find_overlaps,
)


def _parse_iso(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def _trunc(text: str, limit: int = 80) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_report(discussions: dict, issues: dict, *, since: dt.datetime) -> dict:
    posts = []
    for item in discussions.get("items") or []:
        created = _parse_iso(item.get("created_at") or "")
        updated = _parse_iso(item.get("updated_at") or "")
        stamp = updated or created
        if stamp is not None and stamp < since:
            continue
        posts.append({**item, "heat": discussion_heat(item)})
    posts.sort(key=lambda item: (-item["heat"], item.get("created_at") or "", item["id"]))

    backlog = []
    stray = []
    for item in issues.get("items") or []:
        labels = item.get("labels") or []
        tracked = item.get("status") or ("feature" in labels)
        if not tracked:
            continue
        row = {k: v for k, v in item.items() if k != "text"}
        row["text"] = item.get("text") or ""
        if item.get("status"):
            backlog.append(row)
        else:
            stray.append(row)

    overlap_input = [
        {"id": item["id"], "title": item["title"], "text": item.get("text") or ""}
        for item in [*posts, *backlog, *stray]
    ]
    return {
        "window": {"since": since.isoformat(), "days": None},
        "discussions": {"ok": discussions.get("ok", False), "note": discussions.get("note") or "", "items": posts},
        "backlog": backlog,
        "stray_feature_issues": [{k: v for k, v in item.items() if k != "text"} for item in stray],
        "overlaps": find_overlaps(overlap_input),
        "issues_note": "" if issues.get("ok") else issues.get("note") or "",
    }


def render_markdown(report: dict) -> str:
    posts = report["discussions"]["items"]
    lines = ["# Feature Signals", ""]
    if not report["discussions"]["ok"]:
        lines.append(f"Discussions 没有读到：{report['discussions']['note']}")
    else:
        lines.append(f"窗口内讨论 **{len(posts)}** 条。热度 = 赞成×2 + 评论 + 反应，只用于排序。")
    if report["issues_note"]:
        lines.append(f"Issue 没有读到：{report['issues_note']}")
    lines.append("")
    lines.append("## 讨论")
    if report["discussions"]["ok"] and not posts:
        lines.append("- 这个窗口里没有讨论。")
    for item in posts[:20]:
        lines.append(
            f"- {item['heat']:>3}  [{item['category']}] [{_trunc(item['title'], 60)}]({item['url']})"
            f"  ↑{item['upvotes']}  💬{item['comments']}"
        )
    if len(posts) > 20:
        lines.append(f"- … 另有 {len(posts) - 20} 条")
    lines.append("")
    lines.append("## 可能重复")
    if not report["overlaps"]:
        lines.append("- 没有足够的用词重叠。语义是否重复仍由人看。")
    for row in report["overlaps"][:12]:
        lines.append(f"- `{row['a']}` × `{row['b']}` · 共享 {'、'.join(row['shared'])}")
    lines.append("")
    lines.append("## 已在路线图")
    if not report["backlog"]:
        lines.append("- 没有带 status:* 标签的 open issue。")
    for item in report["backlog"]:
        lines.append(f"- `{item['status']}` [#{item['number']}]({item['url']}) {_trunc(item['title'], 70)}")
    lines.append("")
    lines.append("## 有 feature 标签、还没进路线图")
    if not report["stray_feature_issues"]:
        lines.append("- 没有。")
    for item in report["stray_feature_issues"]:
        lines.append(f"- [#{item['number']}]({item['url']}) {_trunc(item['title'], 70)}")
    lines.append("")
    lines.append("Agent 只产出聚类和排序。把一条讨论推进到 Planned 或 Building 之前，要等人确认。")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)
    report = build_report(fetch_discussions(), fetch_open_issues(), since=since)
    report["window"]["days"] = args.days
    if args.json:
        for item in report["discussions"]["items"]:
            item.pop("text", None)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    print(render_markdown(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
