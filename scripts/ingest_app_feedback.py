#!/usr/bin/env python3
"""把 PostHog 里的应用内反馈写进 GitHub。

故障开 Issue，想法开 Ideas 讨论，其他开 Q&A 讨论。
同一条反馈编号只写一次。邮箱不进入公开帖，脚本也不读取它。

用法
  python3 scripts/ingest_app_feedback.py --dry-run
  python3 scripts/ingest_app_feedback.py --days 14

需要 POSTHOG_PERSONAL_API_KEY。POSTHOG_PROJECT_ID 缺省为文档里的 450605。
写入时使用已登录的 gh（Actions 里是 GITHUB_TOKEN）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.request
from typing import Any

REPO = os.environ.get("AUTOCLIP_REPO", "zhouxiaoka/autoclip")
POSTHOG_HOST = os.environ.get("POSTHOG_HOST", "https://us.posthog.com").rstrip("/")
DEFAULT_PROJECT_ID = "450605"
MAX_PER_RUN = 20
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.I,
)
ID_RE = re.compile(
    r"(?:反馈编号：\s*|<!--\s*feedback-id:\s*)([0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})",
    re.I,
)
SECRET_RE = re.compile(
    r"sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{8,}|github_pat_[A-Za-z0-9_]{8,}"
    r"|xox[baprs]-[A-Za-z0-9-]+|(?:api[_-]?key|token|secret|password|bearer)\s*[:=]\s*\S+",
    re.I,
)


def scrub(value: Any, limit: int) -> str:
    text = "" if value is None else str(value)
    text = SECRET_RE.sub("[redacted]", text).replace("\r\n", "\n").strip()
    return text[:limit]


def normalize_event(raw: dict[str, Any]) -> dict[str, str] | None:
    feedback_id = scrub(raw.get("feedback_id"), 80).lower()
    if not UUID_RE.match(feedback_id):
        return None
    category = scrub(raw.get("category"), 20).lower()
    if category not in {"bug", "idea", "other"}:
        return None
    text = scrub(raw.get("text"), 2000)
    if len(text) < 4:
        return None
    return {
        "feedback_id": feedback_id,
        "category": category,
        "text": text,
        "source": scrub(raw.get("source"), 40),
        "stage": scrub(raw.get("stage"), 80),
        "error_message": scrub(raw.get("error_message"), 500),
        "version": scrub(raw.get("app_version") or raw.get("version"), 40),
        "os": scrub(raw.get("os"), 40),
        "arch": scrub(raw.get("arch"), 40),
        "llm_provider": scrub(raw.get("llm_provider"), 80),
        "llm_model": scrub(raw.get("llm_model"), 80),
        "timestamp": scrub(raw.get("timestamp") or raw.get("time"), 40),
    }


def title_for(item: dict[str, str]) -> str:
    prefix = "[想法] " if item["category"] == "idea" else "[反馈] "
    line = " ".join(item["text"].split())[:60] or "应用内反馈"
    return (prefix + line)[:120]


def public_body(item: dict[str, str]) -> str:
    lines = [
        "来自应用内反馈，由自动收件写入。",
        "",
        f"反馈编号：{item['feedback_id']}",
        f"<!-- feedback-id:{item['feedback_id']} -->",
        "",
        item["text"],
        "",
        "环境",
        f"- 版本：{item['version'] or '未知'}",
        f"- 系统：{item['os'] or '未知'} / {item['arch'] or '未知'}",
        f"- 来源：{item['source'] or '未知'}",
    ]
    if item["stage"]:
        lines.append(f"- 阶段：{item['stage']}")
    if item["llm_provider"]:
        model = f" / {item['llm_model']}" if item["llm_model"] else ""
        lines.append(f"- 模型：{item['llm_provider']}{model}")
    if item["error_message"]:
        lines.extend(["", "错误", item["error_message"]])
    lines.extend(["", "邮箱留在维护者的收件记录里，不写在这条公开帖上。"])
    return "\n".join(lines)


def route(category: str) -> dict[str, Any]:
    if category == "bug":
        return {"kind": "issue", "labels": ["bug", "needs-triage", "from-app"]}
    if category == "idea":
        return {"kind": "discussion", "category": "Ideas"}
    return {"kind": "discussion", "category": "Q&A"}


def plan_posts(events: list[dict[str, Any]], known_ids: set[str], *, limit: int = MAX_PER_RUN) -> list[dict[str, Any]]:
    ordered = sorted(events, key=lambda row: str(row.get("timestamp") or row.get("time") or ""))
    seen = {item.lower() for item in known_ids}
    posts: list[dict[str, Any]] = []
    for raw in ordered:
        item = normalize_event(raw)
        if item is None or item["feedback_id"] in seen:
            continue
        seen.add(item["feedback_id"])
        dest = route(item["category"])
        posts.append({
            **dest,
            "feedback_id": item["feedback_id"],
            "title": title_for(item),
            "body": public_body(item),
        })
        if len(posts) >= limit:
            break
    return posts


def known_ids_in(texts: list[str]) -> set[str]:
    found: set[str] = set()
    for text in texts:
        found.update(match.group(1).lower() for match in ID_RE.finditer(text or ""))
    return found


def _http_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, body: Any = None) -> Any:
    data = None
    hdrs = {"Accept": "application/json", **(headers or {})}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=hdrs)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def fetch_events(days: int) -> dict[str, Any]:
    key = os.environ.get("POSTHOG_PERSONAL_API_KEY")
    project = os.environ.get("POSTHOG_PROJECT_ID") or DEFAULT_PROJECT_ID
    if not key:
        return {"ok": False, "items": [], "note": "没有 POSTHOG_PERSONAL_API_KEY"}
    query = f"""
      SELECT timestamp, properties.feedback_id, properties.category, properties.source, properties.stage,
             properties.text, properties.app_version, properties.os, properties.arch,
             properties.llm_provider, properties.llm_model, properties.error_message
      FROM events
      WHERE event = 'feedback_submitted' AND timestamp > now() - INTERVAL {int(days)} DAY
      ORDER BY timestamp ASC
      LIMIT 300
    """
    try:
        payload = _http_json(
            f"{POSTHOG_HOST}/api/projects/{project}/query/",
            method="POST",
            headers={"Authorization": f"Bearer {key}"},
            body={"query": {"kind": "HogQLQuery", "query": query}},
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:200]
        return {"ok": False, "items": [], "note": f"PostHog HTTP {exc.code}: {detail}"}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "items": [], "note": f"PostHog 失败：{exc}"}
    cols = [
        "timestamp", "feedback_id", "category", "source", "stage", "text",
        "app_version", "os", "arch", "llm_provider", "llm_model", "error_message",
    ]
    items = [dict(zip(cols, row)) for row in payload.get("results") or []]
    return {"ok": True, "items": items, "note": ""}


def _run(cmd: list[str], *, input_text: str | None = None) -> tuple[int, str, str]:
    import subprocess
    proc = subprocess.run(cmd, input=input_text, text=True, capture_output=True, timeout=60)
    return proc.returncode, proc.stdout, proc.stderr


def _gh_json(args: list[str]) -> Any:
    rc, out, err = _run(["gh", *args])
    if rc != 0:
        raise RuntimeError((err or out or "gh 失败").strip())
    return json.loads(out or "null")


def fetch_known_ids() -> set[str]:
    rc, out, err = _run([
        "gh", "issue", "list", "--repo", REPO, "--state", "all", "--limit", "100",
        "--label", "from-app", "--json", "body",
    ])
    if rc != 0:
        message = f"{err}\n{out}".lower()
        if "from-app" in message and ("not found" in message or "404" in message):
            issues: list[dict[str, Any]] = []
        else:
            raise RuntimeError((err or out or "读取已有 issue 失败").strip())
    else:
        issues = json.loads(out or "[]")
    texts = [item.get("body") or "" for item in issues or []]
    rc, out, err = _run([
        "gh", "issue", "list", "--repo", REPO, "--state", "all", "--limit", "30",
        "--search", "反馈编号 in:body", "--json", "body",
    ])
    if rc == 0:
        texts.extend((item.get("body") or "") for item in json.loads(out or "[]"))
    owner, name = REPO.split("/", 1)
    data = _gh_json([
        "api", "graphql", "-f", f"owner={owner}", "-f", f"name={name}", "-f",
        "query=query($owner:String!,$name:String!){repository(owner:$owner,name:$name){discussions(first:50,orderBy:{field:CREATED_AT,direction:DESC}){nodes{body}}}}",
    ])
    nodes = (((data.get("data") or {}).get("repository") or {}).get("discussions") or {}).get("nodes") or []
    texts.extend((node.get("body") or "") for node in nodes)
    return known_ids_in(texts)


def ensure_from_app_label() -> None:
    rc, _, _ = _run(["gh", "api", f"repos/{REPO}/labels/from-app"])
    if rc == 0:
        return
    rc, _, err = _run([
        "gh", "label", "create", "from-app", "--repo", REPO, "--color", "6e7781",
        "--description", "应用内反馈自动写入。不是路线图承诺。",
    ])
    if rc != 0 and "already exists" not in (err or "").lower():
        raise RuntimeError((err or "无法创建 from-app 标签").strip())


def discussion_category_id(name: str) -> tuple[str, str]:
    owner, repo = REPO.split("/", 1)
    data = _gh_json([
        "api", "graphql", "-f", f"owner={owner}", "-f", f"name={repo}", "-f",
        "query=query($owner:String!,$name:String!){repository(owner:$owner,name:$name){id discussionCategories(first:25){nodes{id name}}}}",
    ])
    repository = (data.get("data") or {}).get("repository") or {}
    nodes = (repository.get("discussionCategories") or {}).get("nodes") or []
    by_name = {node.get("name"): node.get("id") for node in nodes}
    chosen = by_name.get(name) or by_name.get("General")
    if not chosen:
        raise RuntimeError(f"找不到讨论分类 {name}")
    return repository.get("id") or "", chosen


def create_issue(post: dict[str, Any]) -> str:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as handle:
        handle.write(post["body"])
        path = handle.name
    try:
        cmd = ["gh", "issue", "create", "--repo", REPO, "--title", post["title"], "--body-file", path]
        for label in post["labels"]:
            cmd.extend(["--label", label])
        rc, out, err = _run(cmd)
    finally:
        os.unlink(path)
    if rc != 0:
        raise RuntimeError((err or out or "创建 issue 失败").strip())
    return (out or "").strip()


def create_discussion(post: dict[str, Any]) -> str:
    repo_id, category_id = discussion_category_id(post["category"])
    payload = {
        "query": """
          mutation($input: CreateDiscussionInput!) {
            createDiscussion(input: $input) { discussion { url } }
          }
        """,
        "variables": {"input": {
            "repositoryId": repo_id,
            "categoryId": category_id,
            "title": post["title"],
            "body": post["body"],
        }},
    }
    rc, out, err = _run(["gh", "api", "graphql", "--input", "-"], input_text=json.dumps(payload))
    if rc != 0:
        raise RuntimeError((err or out or "创建 discussion 失败").strip())
    data = json.loads(out or "{}")
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False)[:500])
    return (((data.get("data") or {}).get("createDiscussion") or {}).get("discussion") or {}).get("url") or ""


def apply_posts(posts: list[dict[str, Any]]) -> list[str]:
    if not posts:
        return []
    if any(post["kind"] == "issue" for post in posts):
        ensure_from_app_label()
    urls: list[str] = []
    errors: list[str] = []
    for post in posts:
        try:
            url = create_issue(post) if post["kind"] == "issue" else create_discussion(post)
            urls.append(url or post["feedback_id"])
            print(url or post["feedback_id"])
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{post['feedback_id']}: {exc}")
            print(f"失败 {post['feedback_id']}: {exc}", file=sys.stderr)
    if errors:
        raise RuntimeError(f"{len(errors)} 条没有写入")
    return urls


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--dry-run", action="store_true", help="只打印将要写入的标题，不创建")
    args = parser.parse_args(argv)
    loaded = fetch_events(args.days)
    if not loaded["ok"]:
        print(loaded["note"], file=sys.stderr)
        return 1
    try:
        known = fetch_known_ids()
    except Exception as exc:  # noqa: BLE001
        print(f"读取已有反馈编号失败：{exc}", file=sys.stderr)
        return 1
    posts = plan_posts(loaded["items"], known)
    if args.dry_run:
        preview = [{"kind": p["kind"], "title": p["title"], "feedback_id": p["feedback_id"]} for p in posts]
        print(json.dumps(preview, ensure_ascii=False, indent=2))
        return 0
    if not posts:
        print("没有新的应用内反馈。")
        return 0
    try:
        apply_posts(posts)
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
