# 接入 opencode CLI（AutoClip MCP）

[opencode](https://opencode.ai) 是终端里的 AI agent。把 AutoClip 作为本地 MCP server 接进去之后，
你在 opencode 里给出一个视频路径，它就会调 AutoClip 出片——切高光、看结果、导 9:16、发平台，
不用自己拼 `autoclip` 参数。

| 你想做的 | 怎么做 |
|---|---|
| 一条命令接入（推荐） | `autoclip mcp install opencode` |
| 写进某个项目 | `autoclip mcp install opencode --scope project --dir <项目目录>` |
| 只看配置片段、不改文件 | `autoclip mcp install opencode --print` |
| 现有配置带注释，确认要重写 | 加 `--force`（先备份为 `opencode.json.bak`） |

## 1. 前置条件

- AutoClip CLI 装好（MCP server 与 CLI 同源）：`pip install -r requirements.txt && pip install -e .`，
  见 [CLI / MCP 指南](CLI_AND_MCP.md) 第 1 节；不装包也能用仓库里的 `python -m backend.mcp_server`
- `ffmpeg` 在 PATH、模型能连上：`autoclip doctor` 检查（云端 key，或本地 Ollama / LM Studio）
- opencode 已安装（`opencode --version`）

## 2. 一键接入

```bash
autoclip mcp install opencode
# ✓ 已写入 ~/.config/opencode/opencode.json（Windows: %USERPROFILE%\.config\opencode\opencode.json）
```

命令做的事：

- 按 `autoclip` → `autoclip-mcp` → `python -m backend.mcp_server` 的顺序探测启动命令（结果在输出的 `entry` 里）
- 把 `mcp.autoclip` **合并**写进配置（`type: local`），其它键原样保留；文件已存在时先备份 `opencode.json.bak`
- 重装**不会丢同名条目里的自定义字段**：更新 `type` / `command`；模块回退时刷新 `cwd`，
  并把当前安装路径放到 `PYTHONPATH` 最前面，保留其余模块路径、环境变量、`timeout` 和 `enabled=false`（后者会给出提示）
- 优先识别已有配置文件：只有 `opencode.jsonc` 时写它；`opencode.json` 和 `opencode.jsonc` 同时存在且 jsonc 里已有 `mcp` 段时，
  **写入前直接拒绝**（jsonc 覆盖 json，避免“写入成功但实际加载旧配置”）
- 配置带注释 / 尾随逗号（JSONC，opencode 支持）时默认**不动文件**、只打印片段；加 `--force` 才会先备份再重写成纯 JSON

| 参数 | 作用 |
|---|---|
| `--scope global`（默认） | 全局配置 `~/.config/opencode/opencode.json` |
| `--scope project --dir <目录>` | 只在这个项目生效：`<目录>/opencode.json` |
| `--name <名字>` | 配置里的服务名（默认 `autoclip`；opencode 里工具会带 `autoclip_` 前缀） |
| `--print` / `--json` | 只打印片段 / 输出机器可读报告 |

环境变量：设了 `OPENCODE_CONFIG` 就严格写它指向的文件，不改写同目录的 `.jsonc`；设了 `XDG_CONFIG_HOME` 用 `$XDG_CONFIG_HOME/opencode/opencode.json`。

## 3. 手动配置

`opencode.json`（或 `opencode.jsonc`）：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "autoclip": {
      "type": "local",
      "command": ["C:\\Users\\<你>\\autoclip\\venv\\Scripts\\autoclip.exe", "mcp"],
      "enabled": true
    }
  }
}
```

- macOS / Linux：`"command": ["/path/to/autoclip/venv/bin/autoclip", "mcp"]`
- 没装包（在仓库里跑）：`"command": ["<python 绝对路径>", "-m", "backend.mcp_server"], "cwd": "<仓库根目录>", "environment": {"PYTHONPATH": "<仓库根目录>"}`

opencode 会合并多处配置（全局 + 项目），项目里的同名 server 覆盖全局。

## 4. 在 opencode 里出片

重启 opencode（或新开会话）让它加载 MCP，然后直接说：

```text
把 D:\Videos\lecture.mp4 切片                        # 用桌面应用里配好的模型
把 C:\Users\me\Downloads\podcast.mp4 切片，用 ollama   # 本地模型，不用 key
刚才那个项目第 2 条切片导成 Shorts
```

opencode 会依次调 `check_environment`、`clip_video`（长视频走 `start_clip_job` + `get_job_status` 轮询），
按 **评分 · 时间段 · 标题** 把结果整理给你。产物和桌面应用共用一个数据目录，桌面端首页能直接看到。

## 5. Agent skill（可选，建议装）

`skills/autoclip/SKILL.md` 教 agent 何时用哪个工具、`min_score` 怎么调、结果怎么呈现：

```bash
cp -r skills/autoclip ~/.config/opencode/skills/autoclip   # 全局（Windows 放 %USERPROFILE%\.config\opencode\skills\）
```

只在一个项目里生效，就放 `.opencode/skills/autoclip/`。opencode 也会读 `~/.claude/skills/`，给 Claude Code 装过的无需重复。

## 6. 排错

| 现象 | 处理 |
|---|---|
| opencode 里没有 `autoclip` 工具 | 用 `--print` 确认目标文件路径；同目录只留一份 `opencode.json` / `.jsonc`；新开会话再试 |
| 报「jsonc 里已有 mcp 段」 | `opencode.jsonc` 覆盖 `opencode.json`：只保留一份配置，或手动把片段合并进 jsonc |
| 工具能列出但一调就报错 | 先在终端 `autoclip doctor`：多半是 ffmpeg 不在 PATH、Whisper 没装（传 `srt_path` 可绕过）、模型没 key |
| 切片数为 0 | 让 opencode 用 `min_score=0.5` 重试；纯音乐 / 无对话的视频本身不适合切高光 |
| 首次出片特别慢 | 无字幕时本地 Whisper 转写，首次要下模型；已有 SRT 就传进去，或改用 `ollama` |
| MCP 协议被日志污染 | AutoClip 已把 stdout 留给协议（print 都进 stderr）；自建包装脚本时别往 stdout 打日志 |

相关：[CLI / MCP 全量说明](CLI_AND_MCP.md) · [opencode MCP 文档](https://opencode.ai/docs/mcp-servers/) · [opencode skills 文档](https://opencode.ai/docs/skills/)
