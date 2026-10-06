# Windows 安装包视频链路验收（#118）

`scripts/verify_windows_install.py` 只能由安装目录里的便携 Python 执行。CI 用 `--launch-desktop` 启动安装后的桌面 exe，由它启动内置后端，使用全新临时数据目录，不从开发环境加载 backend。

在原有安装/覆盖升级、来源守卫、内置 ffmpeg 和 yt-dlp 检查之外，`scripts/installed_video_acceptance.py`：

1. 在真实后端 API 保存兼容 provider、模型和字幕分析模式，再读回持久配置并测试连接。旧安装包走其旧配置 API，新包走命名连接 API。
2. 用仓库公开访谈前 45 秒与其真实字幕，通过 `POST /api/v1/studio/import` 上传视频和 SRT（`auto_start=true`，`platforms=douyin`），进入 Studio 自动生成。
3. 轮询 `GET /api/v1/studio/{id}`，直到 `generation.status` 为 `completed` 或 `partial`；若为 `failed` 或超时，断言带上该次响应体。成片在项目目录 `output/studio/{job_id}.mp4`，内置 ffprobe 验证 H.264/AAC，且时长不少于 20 秒。
4. 确认连接、大纲、时间线、评分、标题确实经过 HTTP 模型协议调用。

模型端是仅监听 loopback 的固定 OpenAI 协议 fixture，无真实 API key、无外部模型调用或费用。它提供确定的合法回复，用于验证安装包依赖、持久设置、任务派发和视频产出；不证明真实模型的剪辑质量，不代替 #116 的 5/60 分钟对照，也不代替 #124 的人工看片。

`Windows Install Smoke` 可从分支运行并复用 `Desktop Build` 安装包；报告包含 Python、安装资源目录、各阶段结果和实际产出规格。正式验收以成功的 Windows workflow 报告为准。
