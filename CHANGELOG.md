# 更新日志

本文档记录了AutoClip项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [未发布]

### 新增
- **发布到海外平台（Upload-Post）**：切片可经 [Upload-Post](https://www.upload-post.com) 一次发到 TikTok / Instagram / YouTube Shorts / Facebook / LinkedIn / X / Threads / Pinterest / Bluesky 等，
  与 B 站投稿并列；先按预设渲成片（竖屏平台默认 `shorts`），再异步提交并轮询各平台结果。视频处理仍全部在本地。
  入口：`autoclip publish`、MCP `publish_clip` / `get_publish_status` / `list_publish_profiles`、API `/api/v1/publish/upload-post/*`；
  配置用 `UPLOAD_POST_API_KEY` / `UPLOAD_POST_USER`、`autoclip publish --api-key … --user … --save`，或设置页「发布」。
  切片的「发布导出」里可以「发到海外平台」：勾选已连接的平台，默认先私密试发（`docs/PUBLISH_UPLOAD_POST.md`）。
  发布客户端按当前 Upload-Post 文档和 OpenAPI 重写：过期账号不拿来发，Reddit 暂不发送，超长 YouTube 标题单独截短，提交后每 10 秒查一次结果。无效 key 打线上接口会得到 401。进程中断后未提交的任务会标成失败，而不是一直停在排队。
  应用里的发布收成一条：切片上打开发布，现在发或定时，成片画幅跟着账号走。项目里看记录并取消还没发出的排期。记录可以换成月历；「排这一周」把还没发的切片按分数填进周一、三、五的 09:00，确认后才提交。
  B 站和海外账号在同一处配置、同一页勾选。设置里粘贴 Cookie 并校验，发布页出现 B 站；只发 B 站时渲成横屏，和竖屏账号一起发时各自渲。定时要晚于现在两小时，还没到点的可以取消。抖音、小红书、快手仍然没有投稿接口。
- **自动封面**：设置页「封面」可配 OpenAI 兼容、Seedream（火山方舟）或通义万相。发布页可预览、改文案、重新生成。B 站投稿优先用设计封面；生图失败或未生成时截帧兜底，封面失败不挡投稿。Seedream 参考帧走 generations 的 image 字段，校对用豆包视觉。

### 改进
- **设置「发布」把 B 站和海外拆开**：B 站 Cookie 输入和保存放在最上面，不再跟在海外密钥后面，避免一进来找不到贴 Cookie 的地方。
- **设置页模型名单跟得上服务商**：下拉换成当前常用型号，去掉已下架的 gpt-4o、gemini-1.5、qwen-turbo 等。通义领先 `qwen3.8-max` / `qwen3.8-flash`，Gemini 默认 `gemini-3.8-flash`（2.5 仅作旧账号兜底）。填写密钥后向服务商拉取最新 `/models`，与内置名单合并；拉不到时仍显示内置列表，可点刷新。
- **DeepSeek / Seed / Kimi / GLM / Grok 走官方接口**：设置页可直接选，不再借硅基流动。DeepSeek 默认 `deepseek-flash`（V4.1）；Seed 走火山方舟，默认 `doubao-seed-2-1-lite-260915`。硅基流动不再作为独立提供商出现（旧配置仍能读，打开设置页会切到 DeepSeek 官方）。
- **发布操作教程入口**：设置「发布」、切片发布页和周排期空态增加「操作教程」，打开官网 `guides/publish/`。具体步骤（Upload-Post 密钥、B 站 Application → Cookies 三个字段、仅自己试发）写在官网，改步骤不用发客户端。
- **应用内更新提示**：桌面端发现新版本后在后台下载。顶栏箭头放在语言、主题、设置这一组常驻入口的外面，提示从图标下面展开。点「暂不」只关掉这次提示，图标还在。没有新版本时箭头不出现。已经是最新版时一天查一次；发现过新版本或检查失败时，下次打开会再查。提示里的说明来自该版本的更新日志。
- **不再用飞书表格收集反馈。** 应用内反馈跟随八种界面语言。点发送不看匿名统计开关：故障进入 GitHub Issue，想法和其他进入 Discussions。邮箱不写进公开帖。
- **应用内反馈自动收件。** 每小时把新的 `feedback_submitted` 写进 GitHub，同一条反馈编号只写一次。

### 修复
- 数据库清理脚本失败时返回退出码 1。之前异常被接住后进程仍以 0 退出，调用方会以为清理已经成功。
- 发布导出 ffmpeg 失败时把错误文本切成了单个字符（`[-800]`），空输出直接 `IndexError`；改为切片 `[-800:]`

## [1.3.1] - 2026-09-21

### 改进
- **八语产品界面与官网**：中、英、日、韩、西、葡、俄、法覆盖主要界面、语言选择、表单日期组件和原生托盘；跟随系统或手动选择并保存，切换不重置正在编辑的内容。官网同步八语与可分享语言链接。
- **八语仓库主页**：中文、英文、日文、韩文、西班牙文、葡萄牙文、俄文、法文 README，统一下载入口、真实界面截图、使用说明和可核验的成就徽章；增加文档一致性检查。
- **联系方式精简**：README 移除 QQ、飞书和二维码，仅保留邮箱；同步整理安装、FAQ、Docker 和贡献指南。
- **匿名使用统计 v2**：区分导入、处理、导出、下载的请求与实际结果，增加版本和运行环境标记，避免重复统计；关闭统计后清理待观察任务，不采集 DOM 文本和原始错误内容。
- **崩溃诊断**：接入前端与 Python 错误上报、版本标记及前端 source maps；在发送前过滤请求、日志、变量和错误正文，设置中可关闭。
- **桌面更新**：新增手动检查更新和启动时的每日检查，确认后下载安装；为后续版本提供签名更新包。v1.3.0 用户需先手动安装本版。

### 修复
- 网页开发预览从统一版本配置读取版本号，避免继续显示旧版默认值。
- 手动检查更新遇到网络错误时显示失败，避免误报“已是最新版本”。
- 崩溃报告开关在发送前重新检查，后端关闭后无需重启即可拦截后续错误事件。

## [1.3.0] - 2026-09-20

### 新增
- **`autoclip` 命令行**：`autoclip run video.mp4 --provider ollama` 一条命令出片，`list / show / providers / doctor` 子命令，`--json` 给脚本与 agent；与桌面应用共用数据目录与 SQLite（`pip install -e .`；`docs/CLI_AND_MCP.md`）
- **MCP server**（`autoclip mcp`，stdio）：`clip_video`、`start_clip_job` / `get_job_status`、`get_project`、`list_projects`、`list_providers`、`check_environment`，Cursor / Claude 可直接调用；Agent skill `skills/autoclip/SKILL.md`
- **本地模型预设 Ollama / LM Studio**：设置页提供商下拉直接可选，自动列出服务端模型，无需 API Key；Docker / CLI 可用 `LLM_PROVIDER=ollama`
- `GET /settings/local-presets`、`GET /settings/compatible-models?base_url=`；`POST /settings/test-api` 接受 `ollama` / `lmstudio`
- **出片质量工程化**：按时长分档（短/中/长）覆盖提示词里写死的 90 秒规则；时间线对齐字幕边界并去重；评分数量不匹配不再整块丢、低于阈值保底 top-K。回归入口 `python -m backend.eval`
- **发布导出**：切片可渲成抖音/小红书/Shorts 9:16 或 B 站横屏（烧字幕 + 标题卡）。入口：详情页「导出」、`autoclip export`、MCP `export_clip`
- **Docker / 本地脚本模式可用设置页**：`GET/PUT /settings`、`/test-api`、`/current-provider`、`/compatible-models` 等配置端点不再要求桌面模式；Web 端设置页可直接保存 LLM 提供商与密钥到数据目录的 `settings.json`，api 与 worker 自动热重载。首屏如实显示 `.env` 里的 `LLM_PROVIDER` / `API_MODEL_NAME`（#100）
- **失败要像失败**：LLM 未配置 / 字幕缺失或为空 / 大纲提取全部失败或不可解析 / 时间线为空 / 没有片段过评分 / ffmpeg 没产出切片——
  流水线一律进 `failed`，带阶段（SUBTITLE / ANALYZE / EXPORT）和一句可执行的提示（去哪个设置项、装什么）。不再出现 `Completed · 0 切片`
  或永远 `processing`。`ProjectResponse` 新增 `error_message`（取最近失败任务，CLI 路径回退 `project_metadata.last_error`），详情页 / 项目卡 / 应用内反馈直接展示（#100 #11 #24）
- LLM 单个文本块失败仍继续（长视频偶发超时不毁整条），只有全部失败才报错
- **通义千问国际站**（#45）：设置页通义千问卡片新增「中国站 / 国际站」开关，alibabacloud.com 开通的 Key 可直接用；Docker 用 `DASHSCOPE_BASE_URL`。国际站走 OpenAI 兼容模式，按实例隔离，不改全局 SDK 地址
- **设置页「最低评分阈值」真正生效**：以前只改了 API 进程内存，流水线（worker / 本地线程）一直用常量 0.7；现在 step3 按 settings.json 热重载读取，CLI `--min-score` 仍优先。`chunk_size` / `max_clips` 同样进入 settings，供后续步骤接入
- 发版工具：`scripts/bump_version.py`（四处版本号统一 + CHANGELOG 滚动，`--check` 校验一致）、`scripts/release_notes.py`（Release 正文从 CHANGELOG 生成）；`RELEASE_CHECKLIST.md` 改写为周更流程

### 修复
- DashScope 提供商不再把完整 API Key 打进 INFO 日志
- **本地上传的项目从不自动开始处理**：`/projects/upload` 启动导入任务的代码引用了未定义的 `db`，`NameError` 被吞掉，项目一直停在 pending 等用户手点「开始处理」（自 2026-05 `593cc62b` 起）
- **桌面模式多线程写 SQLite 互相回滚**：文件型 SQLite 之前用 `StaticPool`（全进程一条连接），导入线程结束时的 ROLLBACK 会抹掉流水线线程刚写入的 Task 行（`ObjectDeletedError`、任务凭空消失、进度卡住）。改为默认连接池 + WAL，`StaticPool` 仅保留给 `:memory:`
- 桌面模式下 Celery 任务内的 `self.update_state()` 不再去连 Redis 结果后端（直接 ConnectionRefused 拖死导入任务）
- **开着浏览器「翻译此页」时切换提供商 / 输入模型名整页崩溃**（#100）：Chrome / Edge 翻译会把文本节点换成 `<font>`，React 更新时抛 `removeChild NotFoundError`。现在在挂载前对 `removeChild` / `insertBefore` 做守卫，节点已被外部脚本移动时跳过而不是崩；错误边界页识别到该情况会用中英双语提示关闭翻译
- 错误边界降级页按 `DESIGN.md` 重做（去掉紫色渐变与 AntD `Result`，单色卡片 + `Btn` 原语），「返回首页」在 HashRouter 下真正回到首页
- macOS 开着系统代理（Clash 等）时本地 Ollama / LM Studio 请求被送进代理导致 502：对 localhost / 内网地址不再读取代理环境变量
- 设置页首屏偶发不请求当前模型（`apiConfig.notifyListeners` 遍历中被 listener 自删）
- 从本地预设切回云端提供商时模型名不再残留 `qwen2.5:7b` 之类本地模型名

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

- [Unreleased]: https://github.com/zhouxiaoka/autoclip/compare/v1.3.1...HEAD
- [1.3.1]: https://github.com/zhouxiaoka/autoclip/compare/v1.3.0...v1.3.1
- [1.3.0]: https://github.com/zhouxiaoka/autoclip/compare/v1.2.1...v1.3.0
- [1.2.1]: https://github.com/zhouxiaoka/autoclip/compare/v1.2.0...v1.2.1
- [1.2.0]: https://github.com/zhouxiaoka/autoclip/releases/tag/v1.2.0
- [1.1.0]: https://github.com/zhouxiaoka/autoclip/releases/tag/v1.1.0
- [1.0.0]: https://github.com/zhouxiaoka/autoclip/releases/tag/v1.0.0
