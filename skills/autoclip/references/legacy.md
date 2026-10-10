# 旧的切片、合集与 Upload-Post

当前产品默认走 `skills/autoclip/SKILL.md`：链接或本地长视频 → 成片、封面、文案、发布包。

只有用户明确要原始高光切片、合集，或把已经切好的片段经 Upload-Post 发出去时，才用这里的接口。这些工具在 MCP 里标为 deprecated。

## 调用方式

1. 有 MCP → 用工具，不要自己拼命令。
2. 没有 MCP → `autoclip run <video> --json`（或 `python -m backend.cli run ...`）。
3. 两者都没有 → 按 `docs/CLI_AND_MCP.md` 安装。

版本仍用 `get_version` 或 `autoclip --version` 读取，不要对照写死的版本号。

## 工具

| 工具 | 何时用 |
|---|---|
| `check_environment` | 第一次用、或出片失败时先体检：ffmpeg / Whisper / 模型连接 |
| `clip_video` | 视频不长，且客户端允许一次长时间调用；同步返回结果并推送进度 |
| `start_clip_job` + `get_job_status` | 长视频，或单次工具调用有超时。按 `poll_after_sec` 轮询；没有该字段时每 10–20 秒一次 |
| `get_project` / `list_projects` | 回看之前的项目 |
| `list_providers` | 用户问能用什么模型、能不能离线 |
| `export_clip` | 把已有切片渲成 9:16、烧字幕、加标题卡 |
| `publish_clip` + `get_publish_status` | 经 Upload-Post 发到 TikTok / Instagram / YouTube Shorts / X / LinkedIn。先 `list_publish_profiles` |

`get_job_status` 查不到任务时返回 `unknown`，进程中断时返回 `interrupted`。不要把查不到的任务说成 `completed`。

`clip_video` 与 `start_clip_job` 的参数：

- `video_path`：绝对路径。相对路径先解析。
- `srt_path`：有现成字幕一定传，跳过 Whisper。
- `category`：`default` / `knowledge` / `business` / `opinion` / `experience` / `speech` / `content_review` / `entertainment`。不确定就 `default`。
- `min_score`：0–1，默认 0.7。切片为 0 时用 0.5 重试。
- `provider`：不传就用桌面应用里的模型。免费或离线用 `ollama`（默认 `qwen2.5:7b`）或 `lmstudio`（同时传 `model`）。
- `model` / `base_url`：只在用户明确指定时传。
- 不要传 `api_key`。密钥读环境变量 `AUTOCLIP_API_KEY`，或让用户在桌面设置里填写。

## 发到海外平台（Upload-Post）

1. 先 `list_publish_profiles`。`configured=false` 时，让用户到 https://app.upload-post.com/api-keys 取 key，然后 `autoclip publish --api-key <key> --user <profile> --save`，或设置 `UPLOAD_POST_API_KEY` / `UPLOAD_POST_USER`。profile 没连平台时，让用户到 https://app.upload-post.com/manage-users 连接。
2. `publish_clip(project_id, clip_id, platforms=["tiktok","youtube"], user=…)`。不传 `preset` 时自动渲 9:16（`shorts`，不超过 60 秒）。私密试发：`extra={"privacy_level": "SELF_ONLY"}`（TikTok）、`extra={"privacyStatus": "unlisted"}`（YouTube）。
3. 拿到 `request_id` 后，`get_publish_status` 每 10 秒查一次。`final=true` 时报告每个平台的 `url` 或 `error`。`skipped=true` 表示该 profile 没连这个平台，不是失败。
4. 默认只发用户点名的那一条，不要一次把整个项目都发出去。

## CLI

```bash
autoclip run talk.mp4 --json
autoclip run talk.mp4 --srt talk.srt --min-score 0.5 --json
autoclip run talk.mp4 --provider ollama --json
autoclip doctor --json
autoclip list --json
autoclip show <project_id> --json
autoclip publish <project_id> --clip 2 --platform tiktok --platform youtube --wait --json
autoclip publish --list-profiles
autoclip publish --status <request_id>
```

`--json` 时 stdout 只有一个 JSON 对象，进度走 stderr。不加 `--json` 时 stdout 只打印 `project_id`。退出码：0 成功，1 流水线失败，2 参数或环境错误。

模型 key 用 `AUTOCLIP_API_KEY` 或桌面设置，不要写进命令行然后贴回对话。

## 结果怎么念

`clips[]` 按评分倒序：`title`、`start_time`、`end_time`、`score_100`、`reason`、`file`。`collections[]` 有 `title`、`summary`、`clip_ids`、`file`。

给用户看时列出评分、时间段、标题和一句理由。合集单独一段。提一句桌面应用首页也能看到这个项目。

## 常见问题

- 没有字幕、第一次很慢：Whisper 要下载模型。`check_environment` 里 `whisper.ok=false` 时，让用户在桌面「设置 → 转写」安装，或传 `srt_path`。
- 模型连不上：看 `check_environment` 的 `llm.error`。`ollama` 不可达时提示 `ollama serve` 和 `ollama pull qwen2.5:7b`。云端缺 key 时让用户在桌面设置里填，或设置 `AUTOCLIP_API_KEY`。
- 切片为 0：把 `min_score` 降到 0.5。仍为 0 说明内容不适合切高光。
- 本地地址被系统代理拦成 502：AutoClip 对 localhost 和内网会绕过代理。
- 一次只跑一个切片任务。连续 `start_clip_job` 会排队。
