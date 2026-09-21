#!/usr/bin/env python3
"""把已签名的更新产物写成 Tauri updater 的 latest.json。

GitHub Release 下载 URL 会把文件名里的空格换成点，这里按同样规则拼 URL。
某个平台缺产物或缺 .sig 时跳过该平台；一个平台都没有则不写文件（退出码 0）。
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_DEFAULT = "zhouxiaoka/autoclip"


def github_asset_url(repo: str, tag: str, filename: str) -> str:
    safe = filename.replace(" ", ".")
    return f"https://github.com/{repo}/releases/download/{tag}/{safe}"


def read_signature(artifact: Path) -> Optional[str]:
    sig = Path(str(artifact) + ".sig")
    if not sig.is_file():
        return None
    text = sig.read_text(encoding="utf-8").strip()
    return text or None


def collect_platforms(
    *,
    repo: str,
    tag: str,
    artifacts: dict[str, Optional[Path]],
) -> dict[str, dict[str, str]]:
    platforms: dict[str, dict[str, str]] = {}
    for platform, path in artifacts.items():
        if path is None:
            continue
        if not path.is_file():
            raise SystemExit(f"找不到产物: {path}")
        signature = read_signature(path)
        if not signature:
            print(f"NOTE: 跳过 {platform}（没有 {path.name}.sig）")
            continue
        platforms[platform] = {
            "signature": signature,
            "url": github_asset_url(repo, tag, path.name),
        }
    return platforms


def build_manifest(
    *,
    version: str,
    notes: str,
    pub_date: str,
    platforms: dict[str, dict[str, str]],
) -> dict:
    return {
        "version": version.lstrip("v"),
        "notes": notes,
        "pub_date": pub_date,
        "platforms": platforms,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Write Tauri updater latest.json")
    parser.add_argument("--version", required=True, help="应用版本，例如 1.2.2 或 v1.2.2")
    parser.add_argument("--tag", help="GitHub Release tag，默认 v{version}")
    parser.add_argument("--notes", default="", help="更新说明")
    parser.add_argument("--repo", default=REPO_DEFAULT)
    parser.add_argument("--out", required=True, help="latest.json 输出路径")
    parser.add_argument("--pub-date", help="ISO-8601，默认当前 UTC")
    parser.add_argument("--darwin-aarch64", type=Path)
    parser.add_argument("--darwin-x86_64", type=Path)
    parser.add_argument("--windows-x86_64", type=Path)
    parser.add_argument("--linux-x86_64", type=Path)
    args = parser.parse_args()

    version = args.version.lstrip("v")
    tag = args.tag or f"v{version}"
    pub_date = args.pub_date or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    artifacts = {
        "darwin-aarch64": args.darwin_aarch64,
        "darwin-x86_64": args.darwin_x86_64,
        "windows-x86_64": args.windows_x86_64,
        "linux-x86_64": args.linux_x86_64,
    }
    platforms = collect_platforms(repo=args.repo, tag=tag, artifacts=artifacts)
    if not platforms:
        print("NOTE: 没有任何已签名平台，不写 latest.json（检查更新会优雅失败）")
        return 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = build_manifest(version=version, notes=args.notes, pub_date=pub_date, platforms=platforms)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK wrote {out} ({', '.join(platforms)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
