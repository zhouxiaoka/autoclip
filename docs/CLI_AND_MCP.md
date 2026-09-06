# AutoClip 命令行、MCP 与本地模型

面向开发者的三种用法，全部复用桌面应用同一条流水线、同一个数据目录：

| 形态 | 一句话 | 入口 |
|---|---|---|
| CLI | `autoclip run video.mp4 --provider ollama` 一条命令出片 | `backend/cli.py` |
| MCP server | 让 Cursor / Claude Code / 任何 MCP 客户端直接调 AutoClip | `backend/mcp_server.py` |
| 本地模型预设 | 设置页 / CLI 直接选 Ollama、LM Studio，不用填 key | `backend/core/local_presets.py` |

共享逻辑在 `backend/services/local_runner.py`：不起 FastAPI / Celery，在当前进程里跑 `SimplePipelineAdapter`，
产物目录、metadata、SQLite 记录与桌面端一致——CLI 出的片，打开桌面应用首页就能看到。

---

## 1. 安装

```bash
git clone https://github.com/zhouxiaoka/autoclip.git && cd autoclip
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install -e .            # 得到 autoclip / autoclip-mcp 两个命令
```

不装包也能用：`python -m backend.cli ...`（在仓库根目录）。

需要 ffmpeg 在 PATH（`brew install ffmpeg`）。没有字幕的视频要本地 Whisper：`pip install faster-whisper`，
或在桌面应用「设置 → 语音识别」一键安装（两者共用模型目录）。

先体检：

```bash
autoclip doctor
# 数据目录 ~/Library/Application Support/AutoClip · Python 3.11.9
# ✓ ffmpeg   /opt/homebrew/bin/ffmpeg
# ✓ whisper  faster-whisper 已安装
# ✓ 模型     ollama · qwen2.5:7b · http://localhost:11434/v1
```

---

## 2. CLI

```bash
autoclip run talk.mp4                                  # 用桌面应用设置页里配好的模型
autoclip run talk.mp4 --provider ollama                # 本地 Ollama（默认 qwen2.5:7b，无需 key）
autoclip run talk.mp4 --provider lmstudio --model qwen2.5-7b-instruct
autoclip run talk.mp4 --provider openai --base-url https://api.deepseek.com/v1 --model deepseek-chat --api-key sk-...
autoclip run talk.mp4 --srt talk.srt --category knowledge --min-score 0.6
autoclip run talk.mp4 --json                           # 给脚本 / agent：stdout 只有一个 JSON

autoclip list                                          # 最近项目
autoclip show <project_id>                             # 切片、合集、文件路径
autoclip providers                                     # 提供商与本地预设，标出当前用的
autoclip doctor --provider ollama                      # 按指定 provider 体检
autoclip mcp                                           # 以 MCP server 运行（见下）
```

约定：
- 进度、说明走 **stderr**；**stdout** 只放 `project_id`（或 `--json` 时的 JSON），方便管道。
- 退出码：`0` 成功 · `1` 流水线失败 · `2` 参数 / 环境错误。
- `--provider` 等模型参数不改用户的正式设置，只在数据目录写一份 `cli-settings.json`。
- 视频默认**硬链接**进项目目录（不占双份空间），跨盘时自动复制；`--copy` 强制复制。
- `--no-db` 不写 SQLite（桌面应用里就看不到这个项目）。
- 数据目录：默认与桌面应用一致（mac `~/Library/Application Support/AutoClip`、Windows `%APPDATA%\AutoClip`、Linux `~/.local/share/AutoClip`），
  `--data-dir` 或 `AUTOCLIP_DATA_DIR` 可换。日志在 `<数据目录>/logs/cli.log`，`-v` 同时打到终端。
- `--min-score` 覆盖 step3 的阈值（0–1，默认 0.7）；**切片为 0 先试 0.5**。

`--json` 输出（节选）：

```json
{
  "ok": true,
  "project_id": "3f9c…",
  "name": "talk",
  "clips_dir": "…/projects/3f9c…/output/clips",
  "clips": [
    {"id": "2", "title": "为什么要做本地优先", "start_time": "00:12:03,000", "end_time": "00:14:40,000",
     "score": 0.91, "score_100": 91, "reason": "…", "file": "…/2_为什么要做本地优先.mp4"}
  ],
  "collections": [{"id": "1", "title": "产品哲学", "clip_ids": ["2", "5"], "file": "…/产品哲学.mp4"}],
  "counts": {"clips": 6, "collections": 2},
  "elapsed_sec": 412.3,
  "llm": {"provider": "ollama", "model": "qwen2.5:7b", "base_url": "http://localhost:11434/v1"}
}
```

---

## 3. MCP server

stdio 传输，依赖 `mcp` Python SDK（`requirements.txt` 已锁定；兼容 1.x `FastMCP` 与 2.x `MCPServer`）。

**Cursor**（`~/.cursor/mcp.json`）或 **Claude Desktop**（`claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "autoclip": { "command": "/path/to/autoclip/venv/bin/autoclip", "args": ["mcp"] }
  }
}
```

**Claude Code**：

```bash
claude mcp add autoclip -- /path/to/autoclip/venv/bin/autoclip mcp
```

没装包时把 `command` 换成 `/path/to/autoclip/venv/bin/python`，`args` 为 `["-m", "backend.mcp_server"]`，
并加 `"env": {"PYTHONPATH": "/path/to/autoclip"}`。

工具：

| 工具 | 说明 |
|---|---|
| `clip_video(video_path, srt_path?, name?, category?, min_score?, provider?, model?, base_url?, api_key?)` | 同步出片，期间通过 MCP progress 通知推进度；返回切片 / 合集 / 文件路径 |
| `start_clip_job(同上)` | 后台出片，立刻返回 `project_id`（客户端对单次调用有超时时用） |
| `get_job_status(project_id)` | `status` queued / running / completed / failed，`percent` / `stage` / `message`，完成后带 `result` |
| `get_project(project_id)` | 读已处理项目（含桌面应用建的） |
| `list_projects(limit=20)` | 最近项目 |
| `list_providers()` | 云端 provider + 本地预设 + 当前配置 |
| `check_environment(provider?, …)` | ffmpeg / Whisper / 模型连接体检 |

实现要点：
- 流水线里散落着 `print()`，会污染 stdout 协议通道；server 启动时把 `sys.stdout` 指到 stderr，真正的 stdout 只交给 MCP 传输层。
- 全局 LLM 配置是进程级的，任务用 `threading.Lock` 串行；`start_clip_job` 连发会排队。
- 任务状态在内存里；server 重启后 `get_job_status` 会退回从磁盘读项目结果。

**Agent skill**：`skills/autoclip/SKILL.md` 教 agent 何时用哪个工具、参数怎么选、结果怎么呈现、切片为 0 怎么办。
复制到 `~/.cursor/skills/autoclip/` 或 `~/.claude/skills/autoclip/` 即生效。

---

## 4. 本地模型预设（Ollama / LM Studio）

底层就是 OpenAI 兼容接口 + `base_url`，预设只是把地址和默认模型填好、把 key 变成可选：

| 预设 | 地址 | 默认模型 | 备注 |
|---|---|---|---|
| `ollama` | `http://localhost:11434/v1` | `qwen2.5:7b` | `ollama pull qwen2.5:7b`；中文字幕分析效果稳定 |
| `lmstudio` | `http://localhost:1234/v1` | （以服务端列出的为准） | LM Studio 里加载模型并启动 Local Server |

**设置页**：模型提供商下拉多了「Ollama（本地）」「LM Studio（本地）」；选中后显示服务地址（可改端口 / 局域网机器）、
自动拉取 `/v1/models` 列出可选模型，隐藏 API Key。切回云端 provider 时模型名自动恢复为该 provider 的默认值。

**后端**：`settings.json` 里 `llm_provider` 存 `ollama` / `lmstudio`，`LLMManager._apply_local_preset` 在加载时解析成
`openai` + `base_url`，API key 用占位符 `EMPTY`（不会把用户的 OpenAI key 发给本地服务）。
`get_current_provider_info()` 同时返回展示用的 `provider`（预设名）和 `backend_provider`（`openai`）。

Docker / CLI 环境变量同样可用：`LLM_PROVIDER=ollama LLM_MODEL=qwen2.5:7b`（容器内访问宿主机用
`OPENAI_BASE_URL=http://host.docker.internal:11434/v1`）。

**代理问题**：macOS 上开着 Clash 等系统代理时，`httpx` 会把 `localhost` 请求也送进代理，表现为 502 / 超时。
`llm_providers.is_local_url()` 识别 loopback / 内网 / `*.local` / `host.docker.internal` 地址，
对这些地址创建 `trust_env=False` 的 `httpx.Client`，用户无需改代理规则。

相关 API（桌面模式）：
- `GET /api/v1/settings/local-presets` — 预设列表
- `GET /api/v1/settings/compatible-models?base_url=…` — 列出兼容服务的模型
- `POST /api/v1/settings/test-api` — `provider` 接受 `ollama` / `lmstudio`

---

## 5. 测试

```bash
cd backend && python -m pytest tests/test_local_presets.py tests/test_cli.py -q
```

- `test_local_presets.py`：预设解析、LLMManager 还原、`test-api` 接受预设、本地地址绕过代理、`is_local_url`
- `test_cli.py`：参数解析、`--help` 子进程、项目目录准备与 SQLite 注册（隔离引擎）、结果汇总与评分归一、进度监听、MCP 工具注册

真跑一次（需要 Ollama 或云端 key）：

```bash
autoclip run /path/to/talk.mp4 --provider ollama --min-score 0.5 --json
```
