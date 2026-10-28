"""MCPB entry. UV installs autoclip-mcp from this directory's pyproject.toml."""
from __future__ import annotations

import os
import sys


def _drop_unset_api_key() -> None:
    """A blank or uninterpolated user_config must not override desktop settings."""
    key = os.environ.get("AUTOCLIP_API_KEY")
    if key is None:
        return
    if not key.strip() or "${" in key:
        os.environ.pop("AUTOCLIP_API_KEY", None)


def main() -> int:
    _drop_unset_api_key()
    try:
        from backend.mcp_server import main as mcp_main
    except ImportError as exc:
        print(
            "找不到 PyPI 包 autoclip-mcp。请用 uv run --directory <mcpb 目录> src/server.py 启动。",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    return mcp_main()


if __name__ == "__main__":
    sys.exit(main())
