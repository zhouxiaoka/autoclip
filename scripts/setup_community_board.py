#!/usr/bin/env python3
"""把 AutoClip 社区看板装到 GitHub 上。

默认只打印将要改什么。加上 --apply 才会写：

  - status:* 与 feature 标签
  - 用户名下的公开 Project「AutoClip Roadmap」，Status 改成六列

Discussion 分类没有公开的写入接口。脚本只对照现状并打印要在网页上新建或修改的分类。

--seed-issues 会按 docs/community/roadmap-seed.json 把「新开 issue」的条目建成
Issue 并放进 Project。已发版的历史只写进 Project 简介，不另开 Issue。

用法
  python3 scripts/setup_community_board.py
  python3 scripts/setup_community_board.py --apply
  python3 scripts/setup_community_board.py --apply --seed-issues
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from community_board import (  # noqa: E402
    CATEGORIES,
    FEATURE_LABEL,
    PROJECT_TITLE,
    REPO,
    STATUS_BY_ID,
    plan_categories,
    plan_labels,
    plan_status_options,
    gh_graphql,
)

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "docs" / "community" / "roadmap-seed.json"

REPO_QUERY = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    id
    owner {
      __typename
      id
      login
      ... on User { projectsV2(first: 20) { nodes { id title number public } } }
      ... on Organization { projectsV2(first: 20) { nodes { id title number public } } }
    }
    discussionCategories(first: 25) { nodes { id name emoji description isAnswerable } }
  }
}
"""

STATUS_FIELD_QUERY = """
query($id: ID!) {
  node(id: $id) {
    ... on ProjectV2 {
      items(first: 1) { totalCount }
      field(name: "Status") {
        ... on ProjectV2SingleSelectField { id options { id name description color } }
      }
    }
  }
}
"""


def _gh_api(method: str, path: str, payload: dict | None = None) -> dict | list:
    cmd = ["gh", "api", "--method", method, path]
    proc = subprocess.run(
        cmd,
        input=json.dumps(payload) if payload is not None else None,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or f"{method} {path} 失败").strip())
    if not proc.stdout.strip():
        return {}
    return json.loads(proc.stdout)


def load_context() -> dict:
    owner, name = REPO.split("/", 1)
    data = gh_graphql(REPO_QUERY, {"owner": owner, "name": name})
    return data["repository"]


def project_readme(seed: dict) -> str:
    lines = [
        "AutoClip 的公开路线图。想法在 Discussions，这里只放已经决定要跟的事。",
        "",
        "Exploring → Researching → Planned → Building → Testing → Shipped",
        "",
        "规则见仓库 `docs/COMMUNITY_BOARD.md`。",
        "",
        "## 已经发过版",
        "",
    ]
    for item in seed.get("columns", {}).get("shipped", []):
        lines.append(f"- {item['title']}")
    return "\n".join(lines)


def apply_categories(repo: dict) -> None:
    """GitHub 的公开 GraphQL 没有创建或修改 Discussion 分类的 mutation。这里只对照并打印清单。"""
    plan = plan_categories(repo["discussionCategories"]["nodes"])
    if not plan["create"] and not plan["update"]:
        print("分类已与设计一致。")
        return
    print("Discussion 分类需要在仓库网页上改（Settings → Discussions，或讨论页的分类编辑）：")
    for spec in plan["create"]:
        answerable = "，并设为可标记答案" if spec["is_answerable"] else ""
        print(f"  新建 {spec['emoji']} {spec['name']}{answerable}")
        print(f"    {spec['description']}")
    for spec in plan["update"]:
        print(f"  更新 {spec['name']}")
        if "emoji" in spec:
            print(f"    emoji {spec['emoji']}")
        if "description" in spec:
            print(f"    {spec['description']}")
        if "is_answerable" in spec:
            print(f"    可标记答案：{spec['is_answerable']}")


def apply_labels(*, write: bool) -> None:
    raw = _gh_api("GET", f"repos/{REPO}/labels?per_page=100")
    existing = {item["name"]: item for item in raw} if isinstance(raw, list) else {}
    missing = plan_labels(set(existing))
    wanted = [
        FEATURE_LABEL,
        *[
            {"name": spec["label"], "color": spec["color"], "description": spec["description"]}
            for spec in STATUS_BY_ID.values()
        ],
    ]
    if not missing and all(_label_matches(existing.get(label["name"]), label) for label in wanted):
        print("标签已齐。")
        return
    for label in missing:
        print(f"创建标签 {label['name']}")
        if write:
            _gh_api("POST", f"repos/{REPO}/labels", label)
    for label in wanted:
        current = existing.get(label["name"])
        if current and not _label_matches(current, label):
            print(f"更新标签 {label['name']}")
            if write:
                quoted = urllib.parse.quote(label["name"], safe="")
                _gh_api("PATCH", f"repos/{REPO}/labels/{quoted}", label)


def _label_matches(current: dict | None, wanted: dict) -> bool:
    if not current:
        return False
    return (
        (current.get("description") or "") == wanted["description"]
        and (current.get("color") or "").lower() == wanted["color"].lower()
    )


def ensure_project(repo: dict, seed: dict, *, write: bool) -> dict | None:
    projects = (repo["owner"].get("projectsV2") or {}).get("nodes") or []
    current = next((item for item in projects if item["title"] == PROJECT_TITLE), None)
    if current is None:
        print(f"创建公开 Project「{PROJECT_TITLE}」")
        if not write:
            return None
        created = gh_graphql(
            """
            mutation($input: CreateProjectV2Input!) {
              createProjectV2(input: $input) { projectV2 { id number public } }
            }
            """,
            {"input": {
                "ownerId": repo["owner"]["id"],
                "title": PROJECT_TITLE,
                "repositoryId": repo["id"],
            }},
        )["createProjectV2"]["projectV2"]
        current = created
    else:
        print(f"已有 Project「{PROJECT_TITLE}」#{current['number']}")
    if not write:
        return current
    gh_graphql(
        """
        mutation($input: UpdateProjectV2Input!) {
          updateProjectV2(input: $input) { projectV2 { id public } }
        }
        """,
        {"input": {
            "projectId": current["id"],
            "public": True,
            "shortDescription": "Discussions 收想法，这里只放已经决定要跟的事。",
            "readme": project_readme(seed),
        }},
    )
    field = gh_graphql(STATUS_FIELD_QUERY, {"id": current["id"]})["node"]
    status = field["field"]
    options = plan_status_options(status["options"])
    if options is None:
        print("Status 六列已对齐。")
    else:
        extra = [opt["name"] for opt in status["options"] if opt["name"] not in {s["name"] for s in options}]
        if extra and field["items"]["totalCount"]:
            print("Status 里有看板设计之外的列，而且 Project 已有卡片。为避免把卡片状态清掉，这次不改 Status。")
        else:
            if extra:
                print("将替换默认 Status 列：" + "、".join(extra))
            gh_graphql(
                """
                mutation($input: UpdateProjectV2FieldInput!) {
                  updateProjectV2Field(input: $input) { projectV2Field { ... on ProjectV2SingleSelectField { id } } }
                }
                """,
                {"input": {"fieldId": status["id"], "singleSelectOptions": options}},
            )
            print("Status 已写成六列。")
    return current


def seed_issues(project: dict | None, seed: dict, *, write: bool) -> None:
    if project is None:
        print("还没有 Project，跳过种子 Issue。先 --apply 创建看板。")
        return
    field = gh_graphql(STATUS_FIELD_QUERY, {"id": project["id"]})["node"]["field"]
    option_ids = {opt["name"]: opt["id"] for opt in field["options"]}
    for status_id, items in seed.get("columns", {}).items():
        if status_id == "shipped":
            continue
        spec = STATUS_BY_ID[status_id]
        for item in items:
            if item.get("track") != "new-issue":
                action = "加入已有 Issue" if item.get("issue") else "只记在文档里"
                print(f"{spec['name']} · {action} · {item['title']}")
                if write and item.get("issue"):
                    _place_existing(project["id"], field["id"], option_ids[spec["name"]], int(item["issue"]), spec["label"])
                continue
            print(f"{spec['name']} · 新建 Issue · {item['title']}")
            if not write:
                continue
            created = _gh_api("POST", f"repos/{REPO}/issues", {
                "title": item["title"],
                "body": _issue_body(item),
                "labels": ["feature", spec["label"]],
            })
            _add_to_project(project["id"], field["id"], option_ids[spec["name"]], created["node_id"])


def _issue_body(item: dict) -> str:
    lines = [item.get("body") or "见 `docs/COMMUNITY_BOARD.md` 的初始看板。", ""]
    if item.get("acceptance"):
        lines.extend(["## 验收", "", *[f"- [ ] {line}" for line in item["acceptance"]], ""])
    lines.append("来源：`docs/community/roadmap-seed.json`。讨论仍以 Discussions 为准，这里是已决定跟进的条目。")
    return "\n".join(lines)


def _place_existing(project_id: str, field_id: str, option_id: str, number: int, label: str) -> None:
    issue = _gh_api("GET", f"repos/{REPO}/issues/{number}")
    names = {item["name"] for item in issue.get("labels") or []}
    if label not in names:
        _gh_api("POST", f"repos/{REPO}/issues/{number}/labels", {"labels": [label]})
    _add_to_project(project_id, field_id, option_id, issue["node_id"])


def _add_to_project(project_id: str, field_id: str, option_id: str, content_id: str) -> None:
    added = gh_graphql(
        """
        mutation($input: AddProjectV2ItemByIdInput!) {
          addProjectV2ItemById(input: $input) { item { id } }
        }
        """,
        {"input": {"projectId": project_id, "contentId": content_id}},
    )
    gh_graphql(
        """
        mutation($input: UpdateProjectV2ItemFieldValueInput!) {
          updateProjectV2ItemFieldValue(input: $input) { projectV2Item { id } }
        }
        """,
        {"input": {
            "projectId": project_id,
            "itemId": added["addProjectV2ItemById"]["item"]["id"],
            "fieldId": field_id,
            "value": {"singleSelectOptionId": option_id},
        }},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="写入 GitHub。缺省只打印计划")
    parser.add_argument("--seed-issues", action="store_true", help="按种子文件放卡片。需已有 Project")
    args = parser.parse_args()
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    repo = load_context()
    print(f"仓库 {REPO} · 所有者 {repo['owner']['login']}（{repo['owner']['__typename']}）")
    apply_categories(repo)
    try:
        apply_labels(write=args.apply)
    except RuntimeError as exc:
        print(f"标签未改：{exc}")
    project = None
    try:
        project = ensure_project(repo, seed, write=args.apply)
    except RuntimeError as exc:
        print(f"Project 未改：{exc}")
        print("若报错与 project 权限有关，在本机执行 `gh auth refresh -s project,read:project` 后再跑 --apply。")
    if args.seed_issues:
        seed_issues(project, seed, write=args.apply)
    print("")
    print("分类表单不会随 API 挂上。建好分类后，在仓库 Settings → Discussions 里为每个分类选表单：")
    for spec in CATEGORIES:
        print(f"  {spec['name']:16} ← .github/DISCUSSION_TEMPLATE/{spec['slug']}.yml")
    if not args.apply:
        print("\n这是预览。确认后运行：python3 scripts/setup_community_board.py --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
