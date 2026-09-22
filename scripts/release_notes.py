#!/usr/bin/env python3
"""
从 CHANGELOG.md 抽出某个版本的段落，拼上平台安装说明，给 GitHub Release 当正文。
desktop-build.yml 的 release job 调它；本地也可以预览：

    python scripts/release_notes.py v1.3.0            # 打印
    python scripts/release_notes.py v1.3.0 -o body.md

版本在 CHANGELOG 里找不到时只输出平台说明（不让发版失败）。只用标准库。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"

PLATFORM_NOTES = """\
### 下载 / Download

| 平台 | 文件 | 首次打开 |
|---|---|---|
| macOS（Apple Silicon）| `AutoClip.Desktop_{ver}_aarch64.dmg` | 未公证：右键应用 → **打开** |
| Windows 10/11 x64 | `AutoClip.Desktop_{ver}_x64-setup.exe` | 未签名：SmartScreen → **更多信息 → 仍要运行** |

两个包都内置便携 Python 与静态 ffmpeg，不需要预装任何东西；Windows 安装包按用户安装，不需要管理员权限，缺 WebView2 会自动下载。
Intel Mac / Linux 暂无安装包，请用 Docker（`DOCKER.md`）或 `pip install -e .` 跑 `autoclip` CLI。

Built-in portable Python + static ffmpeg, nothing to install. macOS build is ad-hoc signed (right-click → Open on first launch);
Windows build is unsigned (SmartScreen → More info → Run anyway). If a file is missing, that platform's build failed for this tag — see the Desktop Build workflow run.

### 反馈 / Feedback
- 已知问题与当前状态：#96 · 能复现的故障走 [Issue 模板](https://github.com/zhouxiaoka/autoclip/issues/new/choose) · 想法与用法走 [Discussions](https://github.com/zhouxiaoka/autoclip/discussions)
"""


def changelog_section(version: str) -> str | None:
    """返回 `## [version]` 到下一个 `## [` 之间的正文（不含标题行）。"""
    if not CHANGELOG.exists():
        return None
    text = CHANGELOG.read_text(encoding="utf-8")
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.MULTILINE | re.DOTALL)
    if not m:
        return None
    body = m.group(1).strip()
    return body or None


def build(tag: str) -> str:
    ver = tag.lstrip("v")
    parts = [f"## AutoClip Desktop v{ver}\n"]
    section = changelog_section(ver)
    if section:
        parts.append(section + "\n")
    else:
        parts.append(f"_CHANGELOG.md 里没有 [{ver}] 段；完整变更见 [CHANGELOG.md](https://github.com/zhouxiaoka/autoclip/blob/main/CHANGELOG.md)。_\n")
    parts.append(PLATFORM_NOTES.format(ver=ver))
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tag", help="如 v1.3.0")
    ap.add_argument("-o", "--output", help="写到文件；不给则打印到 stdout")
    args = ap.parse_args(argv)

    body = build(args.tag)
    if args.output:
        Path(args.output).write_text(body, encoding="utf-8")
    else:
        sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
