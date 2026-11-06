#!/usr/bin/env python3
"""把官网里「当前正式版」信息同步到 GitHub Release。

只接受非 draft、非 prerelease 的 Release。不传 tag 时用
``/releases/latest``（GitHub 的 Latest，不含预发布）。显式 tag 若仍是
预发布或草稿，直接失败且不改文件。平台安装包缺失同样失败，页面保持上次成功的正式版。

会改：下载链接、安装包体积、首页版本提示、noscript 介绍、发布教程里的
「当前正式版」、llms 摘要里的当前版本与体积、``data/release.json``、
上述页面的 sitemap lastmod。

不会改：案例名、功能首次出现的版本（例如自 v1.3.2、1.4 游戏视觉、
1.5.0 首次出片案例）。

    python3 scripts/sync_release.py
    python3 scripts/sync_release.py v1.5.8
    python3 scripts/sync_release.py --check
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = "zhouxiaoka/autoclip"
SITE = "https://zhouxiaoka.github.io/autoclip_intro/"
VERSION = r"\d+\.\d+\.\d+"
MAC_ASSET = re.compile(rf"^AutoClip\.Desktop_(?P<ver>{VERSION})_aarch64\.dmg$")
WIN_ASSET = re.compile(rf"^AutoClip\.Desktop_(?P<ver>{VERSION})_x64-setup\.exe$")
CLI_ASSET = re.compile(rf"^autoclip-(?P<ver>{VERSION})-cli-mcp\.zip$")

# 发布教程八语里「当前正式版」的位置。历史版本「自 v1.3.2」不在这些模式里。
PUBLISH_SLOTS = (
    (rf"现为 v{VERSION}", "现为 v{version}"),
    (rf"current release \(v{VERSION}\)", "current release (v{version})"),
    (rf"現在 v{VERSION}", "現在 v{version}"),
    (rf"지금 v{VERSION}", "지금 v{version}"),
    (rf"versión actual \(v{VERSION}\)", "versión actual (v{version})"),
    (rf"versão atual \(v{VERSION}\)", "versão atual (v{version})"),
    (rf"сейчас v{VERSION}", "сейчас v{version}"),
    (rf"version actuelle \(v{VERSION}\)", "version actuelle (v{version})"),
)

SITEMAP_LOCS = (
    f"{SITE}",
    f"{SITE}en/",
    f"{SITE}guides/publish/",
    f"{SITE}llms.txt",
    f"{SITE}llms-full.txt",
)


def site_root_from(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "index.html").is_file() and (candidate / "llms.txt").is_file():
            return candidate
    raise SystemExit("找不到官网根目录（需要 index.html 与 llms.txt）")


def fail(message: str) -> None:
    raise SystemExit(message)


def fetch_release(tag: str | None, opener=None) -> dict:
    url = f"https://api.github.com/repos/{REPO}/releases/" + (f"tags/{tag}" if tag else "latest")
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "autoclip-intro-sync",
            "Cache-Control": "no-cache",
        },
    )
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with (opener or urllib.request.urlopen)(req, timeout=30) as resp:
            payload = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        fail(f"GitHub Release API 不可用，页面保持原样：{exc.__class__.__name__}")
    if not isinstance(payload, dict):
        fail("GitHub Release API 返回了无法识别的内容，页面保持原样")
    return payload


def require_stable(release: dict, requested_tag: str | None) -> str:
    tag = str(release.get("tag_name") or "")
    if not re.fullmatch(rf"v{VERSION}", tag):
        fail(f"拒绝无法识别的 tag：{tag or '（空）'}")
    if requested_tag and requested_tag != tag:
        fail(f"请求的 tag {requested_tag} 与接口返回的 {tag} 不一致，页面保持原样")
    if release.get("draft") or release.get("prerelease"):
        kind = "草稿" if release.get("draft") else "预发布"
        fail(f"拒绝{kind} {tag}。官网只跟正式 Latest，页面保持原样")
    return tag[1:]


def pick_assets(release: dict, version: str) -> dict[str, dict]:
    found: dict[str, dict] = {}
    patterns = {"mac": MAC_ASSET, "win": WIN_ASSET, "cli": CLI_ASSET}
    for asset in release.get("assets") or []:
        name = str(asset.get("name") or "")
        for key, pattern in patterns.items():
            match = pattern.match(name)
            if not match:
                continue
            if match.group("ver") != version:
                fail(f"{release.get('tag_name')} 的 {name} 版本与 tag 不一致，页面保持原样")
            size = asset.get("size")
            url = asset.get("browser_download_url")
            if not isinstance(size, int) or size <= 0 or not url:
                fail(f"{name} 缺少体积或下载地址，页面保持原样")
            found[key] = {
                "name": name,
                "bytes": size,
                "size_mb": round(size / 1024 / 1024),
                "url": url,
            }
    missing = [key for key in ("mac", "win") if key not in found]
    if missing:
        fail(
            f"{release.get('tag_name')} 缺少桌面安装包 {missing}。"
            "可能该平台构建失败或仍在上传，页面保持原样"
        )
    ordered = {key: found[key] for key in ("mac", "win", "cli") if key in found}
    return ordered


def release_document(release: dict, version: str, assets: dict[str, dict]) -> dict:
    return {
        "source": "github-release",
        "repository": REPO,
        "tag": release["tag_name"],
        "version": version,
        "draft": False,
        "prerelease": False,
        "published_at": release.get("published_at") or "",
        "html_url": release.get("html_url") or f"https://github.com/{REPO}/releases/tag/{release['tag_name']}",
        "download_page": f"https://github.com/{REPO}/releases/latest",
        "assets": assets,
    }


def _sub_count(pattern: str, repl, text: str, minimum: int, label: str) -> str:
    updated, count = re.subn(pattern, repl, text)
    if count < minimum:
        fail(f"{label} 只找到 {count} 处，期望至少 {minimum}。为避免写错页面，本次不改文件")
    return updated


def patch_index(html: str, version: str, assets: dict[str, dict]) -> str:
    html = _sub_count(
        rf"(?<=/v){VERSION}(?=/)",
        version,
        html,
        2,
        "下载链接",
    )
    html = _sub_count(
        rf"(?<=Desktop_){VERSION}(?=_)",
        version,
        html,
        2,
        "安装包文件名",
    )
    html = _sub_count(
        rf'("softwareVersion": "){VERSION}(")',
        rf"\g<1>{version}\2",
        html,
        1,
        "softwareVersion",
    )
    html = _sub_count(
        rf"(data-i18n=\"hero\.note\">)v{VERSION}",
        rf"\g<1>v{version}",
        html,
        1,
        "hero.note 默认文案",
    )
    html = _sub_count(
        rf"(['\"]hero\.note['\"]\s*:\s*['\"])v{VERSION}",
        rf"\g<1>v{version}",
        html,
        2,
        "hero.note 文案",
    )
    html = _sub_count(rf"当前版本 {VERSION}", f"当前版本 {version}", html, 1, "中文介绍版本")
    html = _sub_count(rf"v{VERSION} for Windows", f"v{version} for Windows", html, 1, "英文介绍版本")
    sizes = iter((assets["mac"]["size_mb"], assets["win"]["size_mb"]))

    def _size(match: re.Match) -> str:
        try:
            size = next(sizes)
        except StopIteration:
            fail("下载卡体积多于两处，页面保持原样")
        return f"{match.group(1)}v{version} · {size} MB</span>"

    html, count = re.subn(
        rf'(<span class="ver">)v{VERSION} · \d+ MB</span>',
        _size,
        html,
    )
    if count != 2:
        fail(f"下载卡体积找到 {count} 处，期望 2。页面保持原样")
    return html


def patch_publish(html: str, version: str) -> str:
    for pattern, template in PUBLISH_SLOTS:
        html = _sub_count(pattern, template.format(version=version), html, 1, f"发布教程 {pattern}")
    if len(re.findall(r"自 v1\.3\.2", html)) < 1:
        fail("发布教程丢掉了「自 v1.3.2」，已中止")
    return html


def patch_llms(text: str, version: str) -> str:
    text = _sub_count(rf"Version {VERSION} ships", f"Version {version} ships", text, 1, "llms.txt 英文版本")
    text = _sub_count(rf"(?<=。){VERSION}(?= 同时提供)", version, text, 1, "llms.txt 中文版本")
    return text


def patch_llms_full(text: str, version: str, assets: dict[str, dict], published_at: str) -> str:
    day = published_at[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}T.*", published_at or "") else None
    if day:
        text = _sub_count(r"(?<=Updated: )\d{4}-\d{2}-\d{2}", day, text, 1, "llms-full 更新日期")
    text = _sub_count(
        rf"## Current product \({VERSION}\)",
        f"## Current product ({version})",
        text,
        1,
        "llms-full 当前版本标题",
    )
    text = _sub_count(
        rf"macOS ~\d+ MB, Windows ~\d+ MB",
        f"macOS ~{assets['mac']['size_mb']} MB, Windows ~{assets['win']['size_mb']} MB",
        text,
        1,
        "llms-full 安装包体积",
    )
    text = _sub_count(rf"(?<=。){VERSION}(?= 提供 Windows)", version, text, 1, "llms-full 中文版本")
    if "Official AutoClip 1.5.0" not in text or "same 1.5 pipeline" not in text:
        fail("llms-full 的历史案例或 1.5 链路表述被改动，已中止")
    return text


def patch_sitemap(xml: str, day: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        return xml
    for loc in SITEMAP_LOCS:
        pattern = rf"(<loc>{re.escape(loc)}</loc>\s*<lastmod>)\d{{4}}-\d{{2}}-\d{{2}}(</lastmod>)"
        xml, count = re.subn(pattern, rf"\g<1>{day}\2", xml, count=1)
        if count != 1:
            fail(f"sitemap 缺少 {loc}，页面保持原样")
    return xml


def render(root: Path, release: dict, requested_tag: str | None = None) -> dict[str, str]:
    version = require_stable(release, requested_tag)
    assets = pick_assets(release, version)
    document = release_document(release, version, assets)
    published = document["published_at"]
    day = published[:10] if published else ""
    files = {
        "index.html": patch_index((root / "index.html").read_text(encoding="utf-8"), version, assets),
        "guides/publish/index.html": patch_publish(
            (root / "guides/publish/index.html").read_text(encoding="utf-8"), version
        ),
        "llms.txt": patch_llms((root / "llms.txt").read_text(encoding="utf-8"), version),
        "llms-full.txt": patch_llms_full(
            (root / "llms-full.txt").read_text(encoding="utf-8"), version, assets, published
        ),
        "sitemap.xml": patch_sitemap((root / "sitemap.xml").read_text(encoding="utf-8"), day),
        "data/release.json": json.dumps(document, ensure_ascii=False, indent=2) + "\n",
    }
    return files


def apply_files(root: Path, files: dict[str, str], check: bool) -> list[str]:
    changed = []
    for rel, content in files.items():
        path = root / rel
        current = path.read_text(encoding="utf-8") if path.is_file() else None
        if current != content:
            changed.append(rel)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
    return changed


def rebuild_pages(root: Path, check: bool) -> bool:
    scripts = root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from build_search_pages import build

    previous = os.getcwd()
    os.chdir(root)
    try:
        return bool(build(check))
    finally:
        os.chdir(previous)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tag", nargs="?", help="如 v1.5.8；不给则取 GitHub Latest（不含预发布）")
    parser.add_argument("--check", action="store_true", help="只比较，不写文件；落后时退出码为 1")
    parser.add_argument("--root", type=Path, help="官网根目录；默认从本文件位置向上找")
    args = parser.parse_args(argv)

    root = args.root.resolve() if args.root else site_root_from(Path(__file__).resolve().parent)
    try:
        release = fetch_release(args.tag or None)
        files = render(root, release, args.tag or None)
    except SystemExit:
        raise
    changed = apply_files(root, files, args.check)
    pages_changed = False
    if not args.check and changed:
        pages_changed = rebuild_pages(root, check=False)
        # 英文静态页由生成器写出后，再确认生成结果本身没有落回旧版本。
        files = render(root, release, args.tag or None)
        drifted = apply_files(root, files, check=True)
        if drifted:
            fail("生成英文页之后发布槽位又不一致：" + ", ".join(drifted))
    elif args.check:
        pages_changed = rebuild_pages(root, check=True)
    if not changed and not pages_changed:
        print(f"官网已与正式版 {release['tag_name']} 一致")
        return 0
    if args.check:
        print("官网发布信息落后：" + ", ".join(changed + (["generated pages"] if pages_changed else [])))
        return 1
    print(f"已同步到正式版 {release['tag_name']}：" + ", ".join(changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
