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

DOWNLOAD_NOTES = """\
### 下载与安装 / Download and install

| 平台 | 文件 | 首次打开 |
|---|---|---|
| macOS 15 及以上（Apple Silicon）| `AutoClip.Desktop_{ver}_aarch64.dmg` | 双击一次。若被拦截：系统设置 → 隐私与安全性 → **仍要打开**（[Apple](https://developer.apple.com/news/?id=saqachfa)） |
| 较旧的 macOS（Apple Silicon）| 同上 | 未公证：右键应用 → **打开** |
| Windows 10/11 x64 | `AutoClip.Desktop_{ver}_x64-setup.exe` | 未签名：SmartScreen → **更多信息 → 仍要运行** |
| CLI / MCP（Python 3.11+）| `autoclip-{ver}-cli-mcp.zip` / `autoclip_mcp-{ver}-py3-none-any.whl` | ZIP 内含安装与模型配置说明，需 FFmpeg |

Intel Mac 目前没有桌面安装包，请用 Docker（`DOCKER.md`）或 CLI。Linux 同样没有桌面安装包，请用 Docker、上面的 `uvx`，或 `pip install -e .` 跑 `autoclip` CLI。

两个桌面包都内置便携 Python 与静态 ffmpeg，不需要预装任何东西；Windows 安装包按用户安装，不需要管理员权限，缺 WebView2 会自动下载。
不下载 ZIP 时：`uvx autoclip-mcp` 安装并启动 MCP，`npx skills add zhouxiaoka/autoclip` 安装 skill。从源码安装仍可用（在仓库根目录 `python -m pip install --no-deps .`）。

安装后若项目列表是空的，点首页「用示例项目看看效果」。示例在安装包内，不需要 API Key。
没有字幕的视频，第一次要下载本地转写组件（约 220 MB，国内网络约 15 分钟）。装不上或太慢时，打开「设置 → 默认模型 → 语音转字幕」，改用百炼云端转写；音频会上传到云端。导入被拦住时，点「改用云端转写」。

A video without subtitles downloads the local transcription component the first time (about 220 MB, about 15 minutes on a slow network). Built-in portable Python + static ffmpeg, nothing else to install. On macOS 15 and later, double-click once; if blocked, open System Settings → Privacy & Security → Open Anyway ([Apple](https://developer.apple.com/news/?id=saqachfa)). Older macOS: right-click the app → Open. Windows is unsigned (SmartScreen → More info → Run anyway). There is no Intel Mac desktop build; use Docker or the CLI. If a listed file is missing, that platform's build failed for this tag — see the Desktop Build workflow run.
Without the ZIP: `uvx autoclip-mcp` installs and starts MCP, and `npx skills add zhouxiaoka/autoclip` installs the skill. Installing from a source checkout still works (`python -m pip install --no-deps .` from the repo root).
"""

FEEDBACK_NOTES = """\
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
    parts = [f"## AutoClip Desktop v{ver}\n", DOWNLOAD_NOTES.format(ver=ver)]
    section = changelog_section(ver)
    if section:
        parts.append("### 更新 / Changes\n\n" + section + "\n")
    else:
        parts.append(f"_CHANGELOG.md 里没有 [{ver}] 段；完整变更见 [CHANGELOG.md](https://github.com/zhouxiaoka/autoclip/blob/main/CHANGELOG.md)。_\n")
    parts.append(FEEDBACK_NOTES)
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
