#!/usr/bin/env python3
"""创始人三数日报：PostHog 口径 + GitHub from-app + Sentry 新增 Issue。

三个数的定义见 docs/analytics/DAILY_FOUNDER_REPORT.md。只依赖 Python 3 标准库。

需要 POSTHOG_PERSONAL_API_KEY。Sentry / 飞书 / gh 缺哪个就跳过哪个，并在日报里写明。

用法
  python3 scripts/daily_founder_report.py
  python3 scripts/daily_founder_report.py --date 2026-10-01
  python3 scripts/daily_founder_report.py --json
  python3 scripts/daily_founder_report.py --post
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

REPO = os.environ.get("AUTOCLIP_REPO", "zhouxiaoka/autoclip")
POSTHOG_HOST = os.environ.get("POSTHOG_HOST", "https://us.posthog.com").rstrip("/")
DEFAULT_PROJECT_ID = "450605"
SENTRY_HOST = os.environ.get("SENTRY_HOST", "https://sentry.io").rstrip("/")
SENTRY_ORG = os.environ.get("SENTRY_ORG", "autoclip-ts")
DASHBOARD_URL = "https://us.posthog.com/project/450605/dashboard/2158541"
SENTRY_NEW_URL = (
    "https://autoclip-ts.sentry.io/issues/"
    "?query=is%3Aunresolved+firstSeen%3A-24h+%21telemetry_test%3Atrue+%21environment%3Adevelopment"
)


def utc_day_bounds(day: dt.date) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc)
    return start, start + dt.timedelta(days=1)


def hogql_dt(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _http_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, body: Any = None, timeout: int = 45) -> Any:
    data = None
    hdrs = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json; charset=utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def _run(cmd: list[str], timeout: int = 60) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def headline_query(start: dt.datetime, end: dt.datetime) -> str:
    lookback = hogql_dt(start - dt.timedelta(days=34))
    a, b = hogql_dt(start), hogql_dt(end)
    return f"""
WITH deliveries AS (
  SELECT person_id, timestamp, properties.material_origin AS origin
  FROM events
  WHERE timestamp >= toDateTime('{lookback}')
    AND timestamp < toDateTime('{b}')
    AND toString(properties.analytics_environment) = 'production'
    AND properties.material_origin IN ('user', 'sample')
    AND (
      event = 'studio_download_saved'
      OR (event IN ('studio_export_finished', 'studio_generation_finished') AND properties.outcome = 'completed')
    )
), first_devices AS (
  SELECT person_id, argMin(origin, timestamp) AS first_origin, min(timestamp) AS first_at
  FROM deliveries
  GROUP BY person_id
), firsts AS (
  SELECT
    uniqIf(person_id, first_origin = 'user' AND first_at >= toDateTime('{a}') AND first_at < toDateTime('{b}')) AS first_real,
    uniqIf(person_id, first_origin = 'sample' AND first_at >= toDateTime('{a}') AND first_at < toDateTime('{b}')) AS first_sample
  FROM first_devices
), headline AS (
  SELECT
    uniqIf(toString(properties.feedback_id), event = 'feedback_submitted' AND properties.category = 'bug' AND match(toString(properties.app_version), '^1\\\\.5') AND toString(properties.feedback_id) != '') AS from_app_bugs_15,
    uniqIf(toString(properties.feedback_id), event = 'feedback_submitted' AND properties.category = 'bug' AND toString(properties.feedback_id) != '') AS from_app_bugs_all,
    uniqIf(person_id, event = 'app_opened' AND toString(properties.analytics_environment) = 'production' AND toString(properties.app_version) = '1.5.0' AND toString(properties.os) = 'windows') AS dau_15_windows,
    uniqIf(person_id, event = 'app_opened' AND toString(properties.analytics_environment) = 'production' AND toString(properties.app_version) = '1.5.0' AND toString(properties.os) = 'macos') AS dau_15_macos,
    uniqIf(person_id, event = 'studio_generation_finished' AND toString(properties.analytics_environment) = 'production' AND toString(properties.material_origin) = 'user' AND toString(properties.outcome) = 'failed') AS gen_fail_user
  FROM events
  WHERE timestamp >= toDateTime('{a}')
    AND timestamp < toDateTime('{b}')
    AND event IN ('feedback_submitted', 'app_opened', 'studio_generation_finished')
)
SELECT
  h.from_app_bugs_15, h.from_app_bugs_all, f.first_real, f.first_sample,
  h.dau_15_windows, h.dau_15_macos, h.gen_fail_user
FROM headline h
CROSS JOIN firsts f
"""


def fetch_posthog(start: dt.datetime, end: dt.datetime) -> dict[str, Any]:
    key = os.environ.get("POSTHOG_PERSONAL_API_KEY")
    project = os.environ.get("POSTHOG_PROJECT_ID") or DEFAULT_PROJECT_ID
    if not key:
        return {"ok": False, "note": "没有 POSTHOG_PERSONAL_API_KEY", "metrics": {}}
    try:
        payload = _http_json(
            f"{POSTHOG_HOST}/api/projects/{project}/query/",
            method="POST",
            headers={"Authorization": f"Bearer {key}"},
            body={"query": {"kind": "HogQLQuery", "query": headline_query(start, end)}},
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:200]
        return {"ok": False, "note": f"PostHog HTTP {exc.code}: {detail}", "metrics": {}}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "note": f"PostHog 失败：{exc}", "metrics": {}}
    row = (payload.get("results") or [[0, 0, 0, 0, 0, 0, 0]])[0]
    while len(row) < 7:
        row.append(0)
    return {
        "ok": True,
        "note": "",
        "metrics": {
            "from_app_bugs_15": _int(row[0]),
            "from_app_bugs_all": _int(row[1]),
            "first_real_clips": _int(row[2]),
            "first_sample_clips": _int(row[3]),
            "dau_15_windows": _int(row[4]),
            "dau_15_macos": _int(row[5]),
            "gen_fail_user": _int(row[6]),
        },
    }


def _issue_labels(item: dict[str, Any]) -> list[str]:
    labels = item.get("labels") or []
    names: list[str] = []
    for label in labels:
        if isinstance(label, dict):
            names.append(str(label.get("name") or ""))
        else:
            names.append(str(label))
    return [name for name in names if name]


def created_on(item: dict[str, Any], day: dt.date) -> bool:
    raw = str(item.get("createdAt") or item.get("created_at") or "")
    parsed = None
    if raw:
        try:
            parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            parsed = None
    return parsed is not None and parsed.astimezone(dt.timezone.utc).date() == day


def filter_from_app(items: list[dict[str, Any]], day: dt.date) -> list[dict[str, Any]]:
    selected = []
    for item in items:
        if item.get("number") in (None, 0):
            continue
        if "from-app" not in _issue_labels(item):
            continue
        if not created_on(item, day):
            continue
        selected.append({
            "number": item.get("number"),
            "title": item.get("title") or "",
            "url": item.get("url") or item.get("html_url") or "",
            "createdAt": item.get("createdAt") or item.get("created_at") or "",
            "labels": _issue_labels(item),
        })
    return selected


def fetch_github_from_app(day: dt.date) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": False, "items": [], "note": ""}
    fields = "number,title,url,createdAt,labels"
    if shutil.which("gh"):
        rc, stdout, stderr = _run(["gh", "issue", "list", "--repo", REPO, "--state", "all", "--limit", "50", "--json", fields])
        if rc != 0:
            out["note"] = (stderr or stdout or "gh 失败").strip()
            return out
        raw = json.loads(stdout or "[]")
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            out["note"] = "没有 gh，也没有 GH_TOKEN"
            return out
        try:
            payload = _http_json(
                f"https://api.github.com/repos/{REPO}/issues?state=all&per_page=50",
                headers={"Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28"},
            )
        except Exception as exc:  # noqa: BLE001
            out["note"] = f"GitHub API 失败：{exc}"
            return out
        raw = payload if isinstance(payload, list) else []
    return {"ok": True, "items": filter_from_app(raw, day), "note": ""}


def fetch_sentry(day: dt.date) -> dict[str, Any]:
    token = os.environ.get("SENTRY_AUTH_TOKEN")
    if not token:
        return {"ok": False, "items": [], "note": "没有 SENTRY_AUTH_TOKEN，跳过新增 Issue"}
    nxt = day + dt.timedelta(days=1)
    query = f"firstSeen:>={day.isoformat()} firstSeen:<{nxt.isoformat()} !telemetry_test:true !environment:development"
    url = (
        f"{SENTRY_HOST}/api/0/organizations/{SENTRY_ORG}/issues/"
        f"?query={urllib.parse.quote(query)}&statsPeriod=24h&limit=25"
    )
    try:
        payload = _http_json(url, headers={"Authorization": f"Bearer {token}"})
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "items": [], "note": f"Sentry 失败：{exc}"}
    if not isinstance(payload, list):
        return {"ok": False, "items": [], "note": f"Sentry 返回异常：{str(payload)[:160]}"}
    items = []
    for issue in payload:
        items.append({
            "id": issue.get("shortId") or issue.get("id"),
            "title": (issue.get("title") or issue.get("culprit") or "")[:120],
            "count": _int(issue.get("count")),
            "permalink": issue.get("permalink") or "",
        })
    return {"ok": True, "items": items, "note": ""}


def render_markdown(data: dict[str, Any]) -> str:
    day = data["day"]
    ph = data["posthog"]
    metrics = ph.get("metrics") or {}
    github = data["github"]
    sentry = data["sentry"]
    lines = [
        f"## AutoClip 创始人日报 {day}",
        "",
        "UTC 完整日。空数 = 没收到符合口径的事件，先看收数，不要当成转化率为零。",
        "",
        "| 数 | 值 | 口径 |",
        "| --- | --- | --- |",
        f"| ① 1.5 应用内故障 | **{metrics.get('from_app_bugs_15', '—')}** | `feedback_submitted` + bug + 版本 1.5，按反馈编号去重 |",
        f"| ② 真实首次出片 / 示例 | **{metrics.get('first_real_clips', '—')}** / {metrics.get('first_sample_clips', '—')} | 设备第一次 user/sample 完成交付 |",
        f"| ③ 1.5.0 Windows / Mac | **{metrics.get('dau_15_windows', '—')}** / **{metrics.get('dau_15_macos', '—')}** | production `app_opened` |",
        "",
    ]
    if not ph.get("ok"):
        lines.append(f"PostHog：{ph.get('note') or '未查询'}")
        lines.append("")
    else:
        lines.append(
            f"旁注：全版本应用内故障 {metrics.get('from_app_bugs_all', 0)}；"
            f"1.5 真实素材制作失败设备 {metrics.get('gen_fail_user', 0)}。"
            "失败不计入②。"
        )
        lines.append("")
    lines.append("### GitHub from-app")
    if not github.get("ok"):
        lines.append(github.get("note") or "未查询")
    elif not github.get("items"):
        lines.append("当天没有新建 from-app Issue。收件任务可能还没跑。")
    else:
        for item in github["items"]:
            lines.append(f"- [#{item['number']}]({item['url']}) {item['title']}")
    lines.append("")
    lines.append("### Sentry 当日新增 Issue")
    lines.append("不把事件量并进①。连接重置单独看。")
    if not sentry.get("ok"):
        lines.append(sentry.get("note") or "未查询")
    elif not sentry.get("items"):
        lines.append("当天没有新的未解决问题。")
    else:
        lines.append(f"新增 {len(sentry['items'])} 个。")
        for item in sentry["items"][:8]:
            title = item["title"] or item["id"]
            if item.get("permalink"):
                lines.append(f"- [{item['id']}]({item['permalink']}) {title}")
            else:
                lines.append(f"- {item['id']} {title}")
        if len(sentry["items"]) > 8:
            lines.append(f"- … 另有 {len(sentry['items']) - 8} 个")
    lines.append("")
    lines.append(f"[三数看板]({DASHBOARD_URL}) · [Sentry 新增]({SENTRY_NEW_URL})")
    return "\n".join(lines)


def post_feishu(markdown: str, title: str) -> None:
    url = os.environ.get("FEISHU_WEBHOOK_URL")
    if not url:
        raise SystemExit("未配置 FEISHU_WEBHOOK_URL，无法发送。")
    body: dict[str, Any] = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": title}, "template": "blue"},
            "elements": [{"tag": "markdown", "content": markdown}],
        },
    }
    secret = os.environ.get("FEISHU_WEBHOOK_SECRET")
    if secret:
        ts = str(int(dt.datetime.now(dt.timezone.utc).timestamp()))
        string_to_sign = f"{ts}\n{secret}"
        sign = base64.b64encode(hmac.new(string_to_sign.encode("utf-8"), b"", digestmod=hashlib.sha256).digest()).decode()
        body["timestamp"], body["sign"] = ts, sign
    result = _http_json(url, method="POST", body=body)
    if result.get("code") not in (0, None) or (result.get("StatusCode") not in (0, None)):
        raise SystemExit(f"飞书 webhook 返回错误：{result}")
    print("已发送到飞书。", file=sys.stderr)


def build_report(day: dt.date) -> dict[str, Any]:
    start, end = utc_day_bounds(day)
    return {
        "day": day.isoformat(),
        "window": {"since": start.isoformat(), "until": end.isoformat()},
        "posthog": fetch_posthog(start, end),
        "github": fetch_github_from_app(day),
        "sentry": fetch_sentry(day),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", help="UTC 日期 YYYY-MM-DD，默认昨天")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    parser.add_argument("--post", action="store_true", help="发送到飞书（需要 FEISHU_WEBHOOK_URL）")
    parser.add_argument("--title", default="")
    args = parser.parse_args()
    if args.date:
        day = dt.date.fromisoformat(args.date)
    else:
        day = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    data = build_report(day)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0 if data["posthog"].get("ok") else 1
    markdown = render_markdown(data)
    print(markdown)
    if args.post:
        post_feishu(markdown, args.title or f"AutoClip 创始人日报 {day.isoformat()}")
    return 0 if data["posthog"].get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
