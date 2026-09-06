# 更新日志

本文档记录了AutoClip项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

## [1.2.1] - 2026-09-06

> 止血版：让 README 推荐的 `docker compose` 路径和本地脚本路径真正能跑通一次完整处理（issue #88 及其一长串重复 issue）。

### 新增
- **OpenAI 兼容接口自定义 `base_url`**：设置页 OpenAI 提供商新增「接口地址」，可接智谱 / DeepSeek / OpenRouter / 本地 Ollama、vLLM、LM Studio 等；自建服务可不填 key（#72 #57，替代 #78）
- **Windows x64 安装包**（首个版本，NSIS，按用户安装）：`scripts/build_windows_x64.sh` + `desktop-build.yml` Windows job；与 macOS 共用 `scripts/lib/desktop_build_common.sh`（#73）
- Docker / 脚本模式可用环境变量配置 LLM：`LLM_PROVIDER`、`API_MODEL_NAME`、`OPENAI_BASE_URL`、`API_{DASHSCOPE,OPENAI,GEMINI,SILICONFLOW}_API_KEY`；compose 透传给 api 与 worker，CI docker-smoke 断言其生效
- `requirements.txt` 直接依赖全部锁定版本（与 CI / Docker 实装一致；3.11 与便携 3.13 均可解析）

### 修复
- **设置页选择的 LLM 提供商从未被持久化**：`api_provider` / `api_base_url` 现在真正写入 `settings.json` 并被流水线读取；`/settings/current-provider` 不再固定返回通义千问；设置保存后 API 进程与 Celery worker 按文件 mtime 自动重载，不必重启
- 模型选择框（`mode="tags"`）手动输入后会把数组发给后端导致保存失败，已归一为字符串
- Docker 镜像无法构建：`.dockerignore` 误排除 `docker-entrypoint.sh` / `docker-dev-entrypoint.sh`（#1 #4 #9 #47 #50 #88）
- Windows 克隆后容器无法启动：新增 `.gitattributes`，shell 脚本强制 LF 行尾（#73 #88）
- Docker 下任何任务都不执行：compose / dev compose 的 Celery worker 未指定 `-Q`，只监听默认队列；现在消费 `celery,processing,video,notification,upload`。本地脚本 `start_autoclip.sh` 同步补齐 `celery` 与 `video` 队列（#88）
- Docker 下项目提交后立刻被标记失败：`task_submission_utils` 里一段仅用于诊断的 `redis.Redis(host='localhost')` 位于 `try` 内并向上抛异常；改为走 `REDIS_URL` 且失败仅记 warning（#88）
- YouTube 解析在作者机器以外 500：`youtube.py` 中硬编码的 `/Users/zhoukk/...` yt-dlp 路径与 `cwd` 改为 `sys.executable -m yt_dlp` + 数据目录；同步清理 `fix_project_thumbnails.py` 与设置页里的硬编码路径（#88）
- LLM 评分步骤对 list 输入未做 JSON 序列化（`_build_full_input`）（#53）
- 一次请求 5 种字幕语言触发 YouTube 429：默认改为 `zh-Hans,zh,en`，可用 `AUTOCLIP_YT_SUBTITLE_LANGS` 覆盖（#88）

### 改进
- Docker 基础镜像 `python:3.9-slim` → `python:3.11-slim`（当前 yt-dlp 已不支持 3.9，且 3.9 下只能拿到 360p）
- `docker-compose.yml` 四个服务共用 `autoclip:local` 镜像，只需构建一次
- CI 新增 `docker-smoke` job：构建镜像、拉起 redis + api + worker、校验健康检查、yt-dlp 可用、REDIS_URL 连通、worker 监听了全部路由队列
- 桌面壳启动后端时注入 `AUTOCLIP_APP_VERSION`，后端 `/settings` 不再固定返回 `1.0.0`
- 桌面壳按平台设置数据目录 `AUTOCLIP_APP_DIR`（macOS 路径不变；Windows 为 `%APPDATA%\AutoClip`），Windows 下强制 `PYTHONUTF8=1` 且不弹控制台窗口
- `src-tauri/Cargo.toml` 版本与 `tauri.conf.json` 对齐
- `desktop-build.yml` 改为 macOS + Windows 并行构建，`release` job 汇总产物，单一平台失败不阻塞另一平台上传

### 移除
- 删除无任何引用的 `backend/api/v1/youtube_improved.py`

## [1.2.0] - 2026-06-03

> 接入产品分析,为后续账号 / 商业化打数据地基。

### 新增
- 接入 PostHog 匿名产品分析：覆盖安装/启动/更新、素材导入、出片导出、流程失败、设置 API key 等关键事件，每条事件自动携带应用版本/系统/架构等全局属性
- 设置页新增「隐私与数据」开关，可随时关闭匿名使用统计（关闭立即停止上报，重启仍生效）
- 新增埋点体系文档 `docs/ANALYTICS.md` 与中英文隐私政策 `docs/PRIVACY.md` / `docs/PRIVACY.en.md`

### 历史累积（1.0.0 之后陆续加入、此前未单独记录）
- 视频标题编辑、B站多账号管理与账号健康状态监控、拖拽排序、视频分类、Docker 管理脚本

## [1.1.0] - 2026-05-31

> 让 macOS 桌面客户端真正可装、可用、能出片。

### 新增
- 🖥️ 桌面客户端零依赖安装：内置便携 Python 运行时 + 静态 ffmpeg/ffprobe，用户无需预装 Python/ffmpeg
- 🗣️ 本地字幕转写（按需安装）：无字幕视频可在「设置 → 语音转写」一键安装 faster-whisper 并自选模型

### 修复
- 修复桌面应用启动黑屏（前端 vendor chunk 加载顺序导致 React 未挂载）
- 修复项目列表一直「加载中」（运行时缺少 pytz 等依赖导致接口 500）
- 修复导入/重试时「重试失败 / 已开始重试」提示疯狂弹窗的循环
- 修复处理一直卡在 0%「初始化中」（桌面模式流水线改为本地执行，不再依赖 Redis）
- 修复换机后无法处理视频（内置 ffmpeg 改为静态自包含版本并正确接入后端）

### 改进
- AI 提供商 Gemini 迁移到官方新版 `google-genai` SDK
- CI 桌面构建统一为一条经过验证的流程（python-build-standalone）
- 仓库清理：移除大量历史脚本与一次性文档，整理项目结构

## [1.0.0] - 2024-01-15

### 新增
- 🎬 支持YouTube视频下载
- 🎬 支持B站视频下载
- 🎬 支持本地文件上传
- 🤖 AI智能视频分析
- ✂️ 自动视频切片
- 📚 智能合集生成
- 🎨 现代化Web界面
- 🚀 异步任务处理
- 📊 实时进度监控
- 🔐 B站账号管理
- 📱 响应式设计
- 🛠️ 一键启动脚本

### 技术特性
- FastAPI后端框架
- React + TypeScript前端
- Celery异步任务队列
- Redis消息代理
- SQLite数据库
- WebSocket实时通信
- 通义千问AI集成

## [0.9.0] - 2024-01-01

### 新增
- 基础项目架构
- 核心API接口
- 基础前端界面
- 视频处理流水线
- AI分析服务

### 技术栈
- Python 3.8+
- React 18
- FastAPI
- Celery
- Redis
- SQLite

---

## 版本说明

### 版本号格式

我们使用语义化版本控制 (SemVer)：

- **主版本号**: 不兼容的API修改
- **次版本号**: 向下兼容的功能性新增
- **修订号**: 向下兼容的问题修正

### 变更类型

- **新增**: 新功能
- **改进**: 现有功能的改进
- **修复**: Bug修复
- **移除**: 移除的功能
- **安全**: 安全相关的修复

### 链接

- [Unreleased]: https://github.com/zhouxiaoka/autoclip/compare/v1.2.0...HEAD
- [1.2.0]: https://github.com/zhouxiaoka/autoclip/releases/tag/v1.2.0
- [1.1.0]: https://github.com/zhouxiaoka/autoclip/releases/tag/v1.1.0
- [1.0.0]: https://github.com/zhouxiaoka/autoclip/releases/tag/v1.0.0
