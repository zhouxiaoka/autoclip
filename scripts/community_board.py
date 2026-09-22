#!/usr/bin/env python3
"""AutoClip 社区看板的共享模型。

Discussions 是公开入口，Issue 是已经决定要跟的需求，
GitHub Project 的 Status 是公开路线图。`status:*` 标签是给 Agent 读的镜像：
只看 Issue 的自动化不必申请 Project 权限。两边不一致时，以 Project 为准，
再把标签改回去。

本文件只依赖标准库。拉数据需要本机已登录的 `gh`。
"""
from __future__ import annotations

import json
import re
import subprocess
from typing import Any

REPO = "zhouxiaoka/autoclip"
PROJECT_TITLE = "AutoClip Roadmap"
DISCUSSIONS_URL = f"https://github.com/{REPO}/discussions"
ISSUES_URL = f"https://github.com/{REPO}/issues/new/choose"

# 公开路线图的列。Agent 不能自行把卡推进到 planned / building / testing / shipped。
STATUSES: list[dict[str, str]] = [
    {
        "id": "exploring",
        "name": "💡 Exploring",
        "label": "status:exploring",
        "color": "6e7781",
        "project_color": "GRAY",
        "description": "社区里出现过，还没决定要不要做",
    },
    {
        "id": "researching",
        "name": "🔬 Researching",
        "label": "status:researching",
        "color": "0969da",
        "project_color": "BLUE",
        "description": "值得研究。人确认后才进入这一列",
    },
    {
        "id": "planned",
        "name": "📅 Planned",
        "label": "status:planned",
        "color": "1f6feb",
        "project_color": "BLUE",
        "description": "已承诺做，还没开始写代码",
    },
    {
        "id": "building",
        "name": "🚧 Building",
        "label": "status:building",
        "color": "bf8700",
        "project_color": "YELLOW",
        "description": "正在做，或代码已在 main、还没发版",
    },
    {
        "id": "testing",
        "name": "🧪 Testing",
        "label": "status:testing",
        "color": "bc4c00",
        "project_color": "ORANGE",
        "description": "有可安装的包或可运行的版本，等人验收",
    },
    {
        "id": "shipped",
        "name": "🚀 Shipped",
        "label": "status:shipped",
        "color": "1a7f37",
        "project_color": "GREEN",
        "description": "已经出现在某次 Release 里",
    },
]

STATUS_BY_ID = {s["id"]: s for s in STATUSES}
STATUS_BY_LABEL = {s["label"]: s for s in STATUSES}
AGENT_LOCKED_STATUSES = {"planned", "building", "testing", "shipped"}

# 五个对外入口。slug 按 GitHub 现有分类和「空格变连字符」规则写死，便于文档链接。
CATEGORIES: list[dict[str, Any]] = [
    {
        "name": "Ideas",
        "emoji": ":bulb:",
        "slug": "ideas",
        "is_answerable": False,
        "create": True,
        "description": "希望 AutoClip 支持什么。先写场景，不要开 Issue。",
    },
    {
        "name": "Use Cases",
        "emoji": ":clapper:",
        "slug": "use-cases",
        "is_answerable": False,
        "create": True,
        "description": "你拿 AutoClip 做什么：游戏切片、播客、课程、短剧。",
    },
    {
        "name": "AI Models",
        "emoji": ":robot:",
        "slug": "ai-models",
        "is_answerable": False,
        "create": True,
        "description": "希望支持哪个模型或供应商，以及现在卡在哪。",
    },
    {
        "name": "Q&A",
        "emoji": ":raising_hand:",
        "slug": "q-a",
        "is_answerable": True,
        "create": True,
        "description": "怎么用、模型怎么选、效果怎么调。能复现的故障请开 Issue。",
    },
    {
        "name": "Announcements",
        "emoji": ":mega:",
        "slug": "announcements",
        "is_answerable": False,
        "create": True,
        "description": "维护者发布版本、已知问题和方向变化。",
    },
]

# 仓库里已有的默认分类。不删除，只改说明，避免把人赶到一个不存在的地方。
SIDE_CATEGORIES: list[dict[str, Any]] = [
    {
        "name": "General",
        "emoji": ":speech_balloon:",
        "slug": "general",
        "is_answerable": False,
        "create": False,
        "description": "对不上分类时再用。功能想法去 Ideas，用法去 Use Cases，模型去 AI Models。",
    },
    {
        "name": "Polls",
        "emoji": ":ballot_box:",
        "slug": "polls",
        "is_answerable": False,
        "create": False,
        "description": "需要社区投票时由维护者发起。日常想法仍发 Ideas。",
    },
    {
        "name": "Show and tell",
        "emoji": ":raised_hands:",
        "slug": "show-and-tell",
        "is_answerable": False,
        "create": False,
        "description": "展示你用 AutoClip 做出的成片。场景描述请发 Use Cases。",
    },
]

FEATURE_LABEL = {
    "name": "feature",
    "color": "1f6feb",
    "description": "已进入 backlog 的需求。还在设想的想法请发 Discussions，不要开 Issue。",
}

STOP_CHARS = set("的了是在我你他她它这那个和与或及也都很就还把被让给对从到为而而且并吗呢吧啊呀嘛着过地得")
STOP_BIGRAMS = {
    "希望", "支持", "可以", "一个", "什么", "怎么", "如何", "如果", "我们", "你们",
    "功能", "觉得", "应该", "想要", "需要", "就是", "还是", "这个", "那个", "一下",
}
EN_STOP = {
    "the", "and", "for", "with", "this", "that", "auto", "clip", "autoclip",
    "please", "would", "like", "want", "need", "from", "have", "just", "into",
    "feature", "support",
}


def category_url(slug: str) -> str:
    return f"https://github.com/{REPO}/discussions/categories/{slug}"


def tokens(text: str) -> set[str]:
    """中文二字片段 + 英文词。用来提示可能重复，不代替人读。"""
    out: set[str] = set()
    for seg in re.findall(r"[\u4e00-\u9fff]+", text or ""):
        chars = [c for c in seg if c not in STOP_CHARS]
        s = "".join(chars)
        if len(s) >= 2:
            out.update(s[i : i + 2] for i in range(len(s) - 1))
        elif len(s) == 1:
            out.add(s)
    out -= STOP_BIGRAMS
    for word in re.findall(r"[a-z][a-z0-9+.-]{2,}", (text or "").lower()):
        if word not in EN_STOP:
            out.add(word)
    return out


def find_overlaps(items: list[dict[str, Any]], *, min_shared: int = 2) -> list[dict[str, Any]]:
    """items 需要 id / title / text。返回共享词达到阈值的配对。"""
    prepared = [(item, tokens(f"{item.get('title', '')}\n{item.get('text', '')}")) for item in items]
    found: list[dict[str, Any]] = []
    for i, (left, lt) in enumerate(prepared):
        if len(lt) < min_shared:
            continue
        for right, rt in prepared[i + 1 :]:
            shared = sorted(lt & rt)
            if len(shared) < min_shared:
                continue
            union = lt | rt
            score = len(shared) / len(union) if union else 0
            found.append({
                "a": left["id"],
                "b": right["id"],
                "shared": shared[:8],
                "jaccard": round(score, 2),
            })
    found.sort(key=lambda row: (-len(row["shared"]), -row["jaccard"], row["a"], row["b"]))
    return found


def discussion_heat(item: dict[str, Any]) -> int:
    return int(item.get("upvotes") or 0) * 2 + int(item.get("comments") or 0) + int(item.get("reactions") or 0)


def plan_categories(existing: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_name = {c.get("name"): c for c in existing}
    creates: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []
    for spec in [*CATEGORIES, *SIDE_CATEGORIES]:
        current = by_name.get(spec["name"])
        if current is None:
            if spec.get("create"):
                creates.append(spec)
            continue
        changed = {}
        for key, field in (("emoji", "emoji"), ("description", "description"), ("is_answerable", "isAnswerable")):
            if current.get(field) != spec[key]:
                changed[key] = spec[key]
        if changed:
            updates.append({"id": current.get("id"), "name": spec["name"], **changed})
    return {"create": creates, "update": updates}


def plan_labels(existing_names: set[str]) -> list[dict[str, str]]:
    wanted = [
        FEATURE_LABEL,
        *[
            {"name": spec["label"], "color": spec["color"], "description": spec["description"]}
            for spec in STATUSES
        ],
    ]
    return [label for label in wanted if label["name"] not in existing_names]


def plan_status_options(existing: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """返回要写入 Project Status 的选项；已经一致时返回 None。"""
    desired_names = [s["name"] for s in STATUSES]
    by_name = {o.get("name"): o for o in existing}
    same_names = [o.get("name") for o in existing] == desired_names
    same_desc = all(
        (by_name.get(s["name"]) or {}).get("description") == s["description"]
        and (by_name.get(s["name"]) or {}).get("color") == s["project_color"]
        for s in STATUSES
    )
    if same_names and same_desc:
        return None
    payload = []
    for spec in STATUSES:
        item: dict[str, Any] = {
            "name": spec["name"],
            "color": spec["project_color"],
            "description": spec["description"],
        }
        current = by_name.get(spec["name"])
        if current and current.get("id"):
            item["id"] = current["id"]
        payload.append(item)
    return payload


def status_of_labels(names: list[str]) -> str | None:
    found = [STATUS_BY_LABEL[name]["id"] for name in names if name in STATUS_BY_LABEL]
    return found[0] if len(found) == 1 else (found[-1] if found else None)


def gh_graphql(query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables or {}})
    proc = subprocess.run(
        ["gh", "api", "graphql", "--input", "-"],
        input=payload,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "gh graphql 失败").strip())
    data = json.loads(proc.stdout or "{}")
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"], ensure_ascii=False)[:500])
    return data.get("data") or {}


def fetch_discussions(*, limit: int = 50) -> dict[str, Any]:
    query = """
    query($owner: String!, $name: String!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        discussions(first: 50, after: $cursor, orderBy: {field: UPDATED_AT, direction: DESC}) {
          pageInfo { hasNextPage endCursor }
          nodes {
            number title url createdAt updatedAt body upvoteCount
            category { name }
            comments { totalCount }
            reactions { totalCount }
            author { login }
          }
        }
      }
    }
    """
    owner, name = REPO.split("/", 1)
    items: list[dict[str, Any]] = []
    cursor = None
    try:
        while len(items) < limit:
            data = gh_graphql(query, {"owner": owner, "name": name, "cursor": cursor})
            conn = data["repository"]["discussions"]
            for node in conn["nodes"]:
                items.append({
                    "id": f"discussion:{node['number']}",
                    "number": node["number"],
                    "title": node.get("title") or "",
                    "url": node.get("url") or "",
                    "category": (node.get("category") or {}).get("name") or "",
                    "created_at": node.get("createdAt") or "",
                    "updated_at": node.get("updatedAt") or "",
                    "author": (node.get("author") or {}).get("login") or "",
                    "upvotes": node.get("upvoteCount") or 0,
                    "comments": (node.get("comments") or {}).get("totalCount") or 0,
                    "reactions": (node.get("reactions") or {}).get("totalCount") or 0,
                    "text": node.get("body") or "",
                })
                if len(items) >= limit:
                    break
            if not conn["pageInfo"]["hasNextPage"]:
                break
            cursor = conn["pageInfo"]["endCursor"]
    except Exception as exc:  # noqa: BLE001 — 缺 gh / 权限时周报要能继续
        return {"ok": False, "items": [], "note": str(exc)}
    return {"ok": True, "items": items, "note": ""}


def fetch_open_issues() -> dict[str, Any]:
    proc = subprocess.run(
        ["gh", "issue", "list", "--repo", REPO, "--state", "open", "--limit", "100",
         "--json", "number,title,labels,url,createdAt,body"],
        text=True, capture_output=True, timeout=60,
    )
    if proc.returncode != 0:
        return {"ok": False, "items": [], "note": (proc.stderr or proc.stdout or "gh issue list 失败").strip()}
    items = []
    for raw in json.loads(proc.stdout or "[]"):
        labels = [label.get("name", "") for label in raw.get("labels") or []]
        items.append({
            "id": f"issue:{raw['number']}",
            "number": raw["number"],
            "title": raw.get("title") or "",
            "url": raw.get("url") or "",
            "labels": labels,
            "status": status_of_labels(labels),
            "created_at": raw.get("createdAt") or "",
            "text": raw.get("body") or "",
        })
    return {"ok": True, "items": items, "note": ""}
