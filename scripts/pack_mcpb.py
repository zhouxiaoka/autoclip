#!/usr/bin/env python3
"""Validate mcpb/ and pack dist/autoclip-mcp.mcpb. Does not publish to Smithery."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "mcpb"
DEFAULT_OUT = ROOT / "dist" / "autoclip-mcp.mcpb"
MCPB_PACKAGE = "@anthropic-ai/mcpb@2.1.2"
PUBLISH_COMMAND = (
    "smithery mcp publish ./dist/autoclip-mcp.mcpb -n io.github.zhouxiaoka/autoclip-mcp"
)


def _run(argv: list[str]) -> None:
    print("+", " ".join(argv), flush=True)
    subprocess.run(argv, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--validate-only", action="store_true", help="run mcpb validate and stop")
    args = parser.parse_args()
    if shutil.which("npx") is None:
        print("需要 Node.js 自带的 npx 才能运行 @anthropic-ai/mcpb", file=sys.stderr)
        return 1
    _run(["npx", "--yes", MCPB_PACKAGE, "validate", str(BUNDLE)])
    if args.validate_only:
        return 0
    out = args.out if args.out.is_absolute() else (ROOT / args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    _run(["npx", "--yes", MCPB_PACKAGE, "pack", str(BUNDLE), str(out)])
    print(f"packed {out}")
    print("Smithery 发布需要维护者自己的登录或 API key。此脚本不会执行：")
    print(PUBLISH_COMMAND)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
