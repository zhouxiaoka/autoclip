#!/usr/bin/env python3
"""
把官网 index.html 里的版本号 / 下载链接 / 安装包体积同步到主仓库最新（或指定）Release。

    python scripts/sync_release.py            # 取 zhouxiaoka/autoclip 的 latest release
    python scripts/sync_release.py v1.3.0     # 指定 tag
    python scripts/sync_release.py --check    # 只报告是否落后，不改文件（退出码 1 = 落后）

替代 README 里「发新版本时要改的地方」那三条手工步骤：
  1. hero 与下载区的版本号、下载链接（四语各一份）
  2. 下载卡上的安装包体积
  3. hero.note 里的版本号

只用标准库；由 .github/workflows/sync-release.yml 调用（repository_dispatch / 每日 cron / 手动）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "index.html"
REPO = "zhouxiaoka/autoclip"
ASSETS = {
    "mac": re.compile(r"^AutoClip\.Desktop_(?P<ver>[\d.]+)_aarch64\.dmg$"),
    "win": re.compile(r"^AutoClip\.Desktop_(?P<ver>[\d.]+)_x64-setup\.exe$"),
}


def fetch_release(tag: str | None) -> dict:
    url = f"https://api.github.com/repos/{REPO}/releases/" + (f"tags/{tag}" if tag else "latest")
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "autoclip-intro-sync"})
    token = os.getenv("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        return json.load(resp)


def pick_assets(release: dict) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for asset in release.get("assets", []):
        for key, pattern in ASSETS.items():
            if pattern.match(asset["name"]):
                found[key] = {"name": asset["name"], "size_mb": round(asset["size"] / 1024 / 1024)}
    missing = [k for k in ASSETS if k not in found]
    if missing:
        raise SystemExit(f"Release {release.get('tag_name')} 缺少产物：{missing}（可能该平台构建失败，或 Release 还在上传）")
    return found


def current_version(html: str) -> str:
    m = re.search(r"releases/download/v(\d+\.\d+\.\d+)/", html)
    if not m:
        raise SystemExit("index.html 里找不到 releases/download/vX.Y.Z/ 形式的下载链接")
    return m.group(1)


def rewrite(html: str, old: str, new: str, assets: dict[str, dict]) -> str:
    old_re = re.escape(old)
    # 1. 下载链接、JS 里的 REL / MAC / WIN、hero.note 等所有版本号（以 v 或 Desktop_ 为前缀，避免误伤别的数字）
    html = re.sub(rf"(?<=/v){old_re}(?=/)", new, html)                 # releases/download/v1.2.1/
    html = re.sub(rf"(?<=Desktop_){old_re}(?=_)", new, html)           # AutoClip.Desktop_1.2.1_...
    html = re.sub(rf"\bv{old_re}\b", f"v{new}", html)                  # 文案里的 v1.2.1
    # 2. 下载卡体积：<span class="ver">vX.Y.Z · NNN MB</span>，第一个是 macOS 卡，第二个是 Windows 卡
    sizes = iter([assets["mac"]["size_mb"], assets["win"]["size_mb"]])

    def _size(m: re.Match) -> str:
        return f'{m.group(1)}{next(sizes)} MB'

    html, n = re.subn(rf'(<span class="ver">v{re.escape(new)} · )\d+ MB', _size, html, count=2)
    if n != 2:
        print(f"警告：只替换了 {n}/2 处安装包体积", file=sys.stderr)
    return html


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tag", nargs="?", help="如 v1.3.0；不给则取 latest")
    ap.add_argument("--check", action="store_true", help="只比较，不写文件")
    args = ap.parse_args(argv)

    release = fetch_release(args.tag)
    tag = release["tag_name"]
    new = tag.lstrip("v")
    assets = pick_assets(release)

    html = INDEX.read_text(encoding="utf-8")
    old = current_version(html)
    print(f"官网当前 v{old} → Release {tag}（mac {assets['mac']['size_mb']} MB / win {assets['win']['size_mb']} MB）")

    updated = rewrite(html, old, new, assets)
    if updated == html:
        print("已是最新，无需改动")
        return 0
    if args.check:
        print("官网落后于最新 Release")
        return 1
    INDEX.write_text(updated, encoding="utf-8")
    changed = sum(1 for a, b in zip(html.splitlines(), updated.splitlines()) if a != b)
    print(f"index.html 已更新（{changed} 行）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
