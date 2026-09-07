---
name: autoclip
description: >-
  用 AutoClip 把本地长视频（讲座 / 访谈 / 播客录像 / 课程）切成带标题、评分的高光片段并串成合集。
  当用户要"切片""剪高光""把这个视频切成短视频""找出精彩片段""做合集"，
  或给出一个本地视频路径并希望得到片段列表时使用。优先走 MCP 工具（clip_video / start_clip_job），
  没有 MCP 时用 `autoclip` CLI 的 `--json` 输出。
---

# AutoClip：视频切高光

AutoClip 是本地运行的 AI 切片工具：字幕（自带 SRT 或本地 Whisper 转写）→ LLM 提取大纲与时间线 →
评分选段 → ffmpeg 出片 → 按主题聚成合集。产物在项目数据目录，和 AutoClip 桌面应用共用，桌面端能直接看到。

## 先选调用方式

1. **有 `autoclip` MCP 工具** → 用工具，不要自己拼命令。
2. **没有 MCP 但能跑 shell** → `autoclip run <video> --json`（或 `python -m backend.cli run ...`）。
3. 两者都没有 → 让用户安装：`pip install -e .`（仓库根目录）或参考 `docs/CLI_AND_MCP.md`。

## MCP 工具用法

| 工具 | 何时用 |
|---|---|
| `check_environment` | 第一次用、或出片失败时先体检：ffmpeg / Whisper / 模型连接 |
| `clip_video` | 视频 ≤ 30 分钟且客户端允许长工具调用；同步返回结果并推送进度 |
| `start_clip_job` + `get_job_status` | 长视频或工具调用有超时限制；每 10–20 秒轮询一次，`status` 为 `completed` 时 `result` 就是结果 |
| `get_project` / `list_projects` | 回看之前的项目 |
| `list_providers` | 用户问"能用什么模型 / 能不能不花钱" |
| `export_clip` | 用户要把切好的片段「直接发抖音 / 小红书 / Shorts」——渲 9:16、烧字幕、加标题卡 |

参数约定（`clip_video` 与 `start_clip_job` 相同）：
- `video_path`：绝对路径。用户给相对路径先解析成绝对路径。
- `srt_path`：有现成字幕一定传，跳过 Whisper 能省几分钟。
- `category`：`default` / `knowledge` / `business` / `opinion` / `experience` / `speech` / `content_review` / `entertainment`，影响提示词；不确定就 `default`。
- `min_score`：0–1，默认 0.7。**切片为 0 时用 0.5 重试**，不要直接说"没有精彩片段"。
- `provider`：不传就用桌面应用里配好的模型。要免费 / 离线时传 `ollama`（本机需装 Ollama，默认模型 `qwen2.5:7b`）或 `lmstudio`（要同时传 `model`）。
- `model` / `base_url` / `api_key`：只在用户明确指定时传。

## CLI 用法

```bash
autoclip run talk.mp4 --json                          # 用桌面应用里的模型配置
autoclip run talk.mp4 --srt talk.srt --min-score 0.5 --json
autoclip run talk.mp4 --provider ollama --json        # 本地 Ollama，无需 key
autoclip run talk.mp4 --provider openai --base-url https://api.deepseek.com/v1 --model deepseek-chat --api-key sk-...
autoclip doctor --json                                # 体检
autoclip list --json / autoclip show <project_id> --json
```

`--json` 时 stdout 只有一个 JSON 对象；进度走 stderr。不加 `--json` 时 stdout 只打印 `project_id`。
退出码：0 成功，1 流水线失败，2 参数 / 环境错误。

## 结果结构与呈现

`clips[]` 已按评分倒序：`title`、`start_time`、`end_time`（`HH:MM:SS,mmm`）、`score_100`（0–100）、`reason`、`file`（mp4 绝对路径）。
`collections[]`：`title`、`summary`、`clip_ids`、`file`。`clips_dir` / `collections_dir` 是输出目录。

给用户看结果时：
- 列出每个切片的 **评分 · 时间段 · 标题**，附上推荐理由一句；文件路径给出来但不要刷屏。
- 合集单独一段，说明它由哪些切片组成。
- 提一句"在 AutoClip 桌面应用首页也能看到这个项目"（同一数据目录）。

## 常见问题

- **没有字幕、首次运行很慢**：Whisper 模型首次下载；提前告知用户。Whisper 未安装时 `check_environment.whisper.ok=false`，让用户在桌面应用「设置 → 语音识别」一键安装，或传 `srt_path`。
- **模型连接失败**：`check_environment.llm.error` 给出了原因。`ollama` 不可达 → 提示 `ollama serve` 并 `ollama pull qwen2.5:7b`；云端 provider → 缺 key，让用户在桌面应用设置页填，或传 `api_key`。
- **切片为 0**：降低 `min_score` 到 0.5；仍为 0 说明内容本身不适合切高光（如纯音乐 / 无对话）。
- **系统代理导致本地地址 502**：AutoClip 对 localhost / 内网地址自动绕过代理，不需要用户改 Clash 规则。
- 一次只跑一个任务：MCP server 内部串行，连续 `start_clip_job` 会排队，属正常现象。
