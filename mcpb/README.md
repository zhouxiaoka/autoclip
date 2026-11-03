# AutoClip MCPB

Smithery 本地 stdio 用的薄 MCP Bundle。包内不包含 AutoClip 后端源码。`pyproject.toml` 依赖已发布的 PyPI 包 `autoclip-mcp`，`src/server.py` 只转调 `backend.mcp_server:main`。

宿主启动命令是 `uv run --directory <本目录> src/server.py`。需要 PATH 里有 `uv`、`ffmpeg`、`ffprobe`。Python 3.10+ 由 UV 安装。

`AUTOCLIP_API_KEY` 可选。桌面应用已经保存模型密钥时留空。空白或未替换的 `${user_config...}` 不会写入环境变量，因此不会覆盖桌面设置。

`manifest.json` 的 `server.type` 是 `python`，因为当前 Smithery CLI 不识别 MCPB 的 `uv` 类型。启动命令仍然是 `uv`。清单不写 `tools`，避免 Smithery 因缺少 `inputSchema` 拒绝发布。

图标是桌面端 512×512 的 `src-tauri/icons/icon.png`。

打包与发布步骤见 `docs/CLI_AND_MCP.md`。在仓库根目录执行 `python scripts/pack_mcpb.py`。不要把 Smithery API key 写进仓库，也不要在这里执行 `smithery mcp publish`。
