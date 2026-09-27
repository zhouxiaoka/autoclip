# AutoClip — 项目状态 / 进度 / 计划

> 更新：2026-09-23 · **v1.3.3** 发版（项目列表旧枚举、进度轮询、导入崩溃、Whisper 安装/转写/下载）。
> v1.3.0 及更早需要先手动安装 v1.3.1，之后才能在设置里检查更新。
> 2026-09-20 的下载快照是 v1.2.1（Windows 1136 / DMG 334）。不要用刚挂上的下载数做平台对比。

AutoClip 是一款 AI 视频切片工具：输入 B站/YouTube 链接或本地视频，自动识别精彩片段、
生成切片与合集。本文是项目当前状态与近期计划的单一事实来源；长期规划见 `ROADMAP.md`。

---

## 一、架构与交付形态

| 层 | 技术 | 目录 |
|----|------|------|
| 后端 | FastAPI + Celery（桌面模式用本地线程）+ SQLite | `backend/` |
| 前端 | React + TypeScript + Ant Design + Vite | `frontend/` |
| 桌面壳 | Tauri 2 + Rust | `src-tauri/` |
| LLM | OpenAI 及 OpenAI 兼容接口（自定义 base_url）/ Gemini / Qwen (dashscope) / DeepSeek / Doubao Seed / Kimi / GLM / Grok / 本地预设 Ollama、LM Studio | `backend/core/llm_providers.py`、`llm_manager.py`、`local_presets.py` |
| CLI / MCP | `autoclip` 命令行 + MCP server（stdio），不起 FastAPI / Celery 直接跑流水线 | `backend/cli.py`、`mcp_server.py`、`services/local_runner.py` |

四种交付形态：**桌面客户端**（当前包是 v1.3.3 的 macOS arm64 DMG 与 Windows x64 安装包；Windows 包从 v1.2.1 起就有，干净机器上的完整出片仍没有记录）、**Docker 部署**（README 推荐路径）、
**本地脚本启动**（`start_autoclip.sh`）、**CLI / MCP**（`pip install -e .`，面向开发者与 agent，`docs/CLI_AND_MCP.md`）。

---

## 二、当前状态

### 已完成
- **v1.3.3（2026-09-23）**：热修稳定性。升级后旧项目状态不再让列表整页打不开；处理进度在终态和 4xx/5xx 后停止轮询；分类列表缺失时导入入口不崩溃；非 Mac 能装 Whisper；本地转写失败给出可读错误；桌面端下载模型不再被进度条写控制台打断。
- **v1.3.2（2026-09-22）**：同一页发布到 B 站和海外平台、自动封面（失败截帧、不挡投稿）、设置里 B 站 Cookie 提前、应用内更新提示、模型名单可拉取。真实 Upload-Post / B 站试发脚本已进仓库，这台机器上还没有密钥，没跑过真投稿。
- **v1.3.1（2026-09-21）**：八语界面与官网、八语 README、匿名统计 v2、崩溃上报、应用内检查更新。v1.3.0 及更早必须先手动安装这一版。生产构建验收见 `docs/UPDATES_AND_SENTRY.md`：一次前端异常能进 Sentry，且正文被去掉。该记录不代替 Windows 真机和真实视频出片。PostHog 新口径的线上接收也还没单独验收（`docs/ANALYTICS_V2.md`）。
- **v1.3.0（2026-09-20）**：CLI / MCP、Ollama 与 LM Studio 预设、时长画像与评分兜底、竖屏发布导出、Docker 设置页可保存、失败要写明阶段、Qwen 国际站、`min_score` 接到 step3、周更发版脚本。
- **v1.2.0（2026-06-03）**：桌面端 DMG 端到端可用（内置便携 Python + 静态 ffmpeg + 按需安装 faster-whisper），
  `desktop-build.yml` 在 tag 上跑通并自动挂 Release；v1.2.0 DMG 已有 2000+ 下载。
- **PostHog 匿名埋点** + 隐私政策 + 设置页开关（`docs/ANALYTICS.md`、`docs/PRIVACY*.md`）。
- **Calm Premium 视觉系统**落地（`DESIGN.md`）。
- Nightly 后端冒烟（`nightly-desktop-smoke.yml`）持续全绿。
- **开发者形态（2026-09-07）**：
  - `autoclip run video.mp4 --provider ollama` 一条命令出片；`list / show / providers / doctor / mcp` 子命令；`--json` 给脚本 / agent。
    与桌面应用共用数据目录和 SQLite，CLI 出的项目桌面首页直接可见。
  - MCP server（`autoclip mcp`）7 个工具：`clip_video`（同步 + 进度通知）、`start_clip_job` / `get_job_status`、`get_project`、`list_projects`、`list_providers`、`check_environment`；
    已用 `mcp` 2.x stdio 客户端实测。Agent skill 在 `skills/autoclip/SKILL.md`。
  - 本地模型预设 Ollama / LM Studio：设置页下拉可选、自动列出 `/v1/models`、隐藏 key；后端 `local_presets.py` 把预设解析为 `openai` + `base_url`。
  - 顺带修复：`httpx` 对 localhost 走系统代理（Clash）导致 502 → `is_local_url()` 对本地地址 `trust_env=False`；
    `apiConfig.notifyListeners` 遍历时被 listener 自删导致设置页首屏偶发不请求 `getCurrentProvider`。
  - 单测 `tests/test_local_presets.py`、`tests/test_cli.py`（共 24 条）；**尚未用真实视频端到端跑过 `autoclip run`**（见 v1.3 todo）。
- **出片质量 + 可发布成片（2026-09-07）**：方案 `docs/QUALITY_AND_PUBLISH_PLAN.md`。
  - 时长画像 `DurationProfile`（短/中/长）注入 step1/2 提示词，短视频不再套「最小 90 秒 / 目标 3–6 分钟」。
  - `refine_timeline`：对齐字幕 cue、时长上下限、重叠合并；`quality_report.json` 落盘。
  - 评分兜底：数量不匹配按 outline 对齐；低于阈值时保底 top-K（#11 切片为 0）。
  - 桌面 adapter 终于传入 `prompt/<category>/`。`AUTOCLIP_LLM_CACHE_DIR` 录制/回放。`python -m backend.eval` 约束回归（`backend/eval/cases/short-synthetic` 已过）。
  - 发布导出：`publish_export.py`（9:16 blur/crop、烧字幕、标题卡）；API `POST .../clips/{id}/export`；`autoclip export`；MCP `export_clip`；切片卡片「导出」Dialog。默认流水线仍是 16:9 copy。
  - **尚未用真实 5 分钟视频跑完整流水线对照**；竖屏预设只单测了 `original` 重编码。
- **#100 修复（2026-09-20）**：Docker Web 模式设置页崩溃 + 不能保存。复现结论：崩溃是 **Chrome「翻译此页」** 改写 DOM（文本节点 → `<font>`）
  导致 React `removeChild NotFoundError`，与 Gemini 无关；用户截图 UI 全英文即证据。修法：`utils/domTranslationGuard.ts` 在挂载前守卫
  `removeChild` / `insertBefore`（facebook/react#11538 建议），`ErrorBoundary` 识别该情况给中英双语提示并按 `DESIGN.md` 重做（去紫色渐变）。
  第二层：`/settings` 读写、`/test-api`、`/current-provider`、`/compatible-models` 等去掉 `check_desktop_mode()`，Docker / 脚本模式设置页可保存
  （settings.json 落 `./data`，api / worker 按 mtime 热重载；首屏如实反映 `.env`）。桌面专属端点（数据目录迁移 / 备份恢复 / 导入导出 / 配置同步）仍拦。
  单测 `tests/test_settings_web_mode.py`（6 条）；Playwright 对照：无守卫构建翻译后第 4 步崩，有守卫全流程通过。

### v1.2.1（2026-09-06 打 tag）
问题根源：README 推荐的 `docker compose` 路径从 2025-09 起就没能跑通过一次完整处理
（issue #88 给出 7 条可复现问题，全部核验属实），是 issue 区大量"用不了"的来源。#89 修复：
1. `.dockerignore` 放行 `docker-entrypoint.sh` / `docker-dev-entrypoint.sh`（镜像此前无法构建）
2. 新增 `.gitattributes`，shell 脚本强制 LF（Windows 克隆后容器起不来）
3. 清理 `youtube.py` / `fix_project_thumbnails.py` / `SettingsPage.tsx` 里的 `/Users/zhoukk` 硬编码
4. Docker 基础镜像 3.9 → 3.11（yt-dlp 要求）
5. 字幕语言默认 `zh-Hans,zh,en`，`AUTOCLIP_YT_SUBTITLE_LANGS` 可覆盖（避免 429）
6. `task_submission_utils` 去掉硬编码 localhost 的 Redis 诊断（Docker 下项目提交即失败）
7. compose / dev compose / `start_autoclip.sh` 的 worker 统一 `-Q celery,processing,video,notification,upload`
   （之前 Docker 下任务永远无人消费）
8. `_build_full_input` list 输入 JSON 序列化（#53）
9. CI 新增 `docker-smoke` job 守住以上路径；版本号对齐到 1.2.1；删除死代码 `youtube_improved.py`

随后合入：
- **#90** 清掉 6 个 `NodeJS.Timeout` 类型错误，`npm run typecheck` 在 CI 阻断
- **#91** 外部 PR #85（日志 utf-8）、#84（Gemini `-latest` 别名）、#83（youtube.py 五连修）以 cherry-pick 合入（保留原作者署名；原 PR 需手动关闭）
- **#94** `requirements.txt` 直接依赖全部锁定
- **#92** OpenAI 兼容 `base_url`（#72 #57，替代 #78）。**顺带发现并修复：设置页选的 provider 从来没被持久化，流水线一直用 dashscope**；
  LLMManager 现按 settings.json mtime 热重载，且支持 Docker 环境变量（`LLM_PROVIDER` / `OPENAI_BASE_URL` / `API_*_API_KEY`）
- **#93** Windows x64 打包脚本 + workflow。`workflow_dispatch` 只勾 Windows 在 `windows-latest` 上一次通过：
  安装包 145 MB，全程 ~22 min（`cargo install tauri-cli` 冷编译 8 min + 打包 13 min；rust-cache 首次为空，后续会快）。
  **尚未装到真机验证**（见下方 todo）

### 仍未完成（ROADMAP Phase 0）
| 项 | 状态 |
|---|---|
| Apple Developer ID 签名 + 公证 | 未做。v1.3.1 的更新包有 minisign `.sig`，安装包仍是 ad-hoc，macOS 首次要右键打开 |
| 多平台包（Windows / Intel mac / Linux） | Windows x64 已随 v1.3.1 发布，干净机器出片仍未记录；Intel mac / Linux 未做 |
| Sentry 崩溃上报 | 已接入。v1.3.1 生产构建验收过一次前端异常；安装包真机收数未做 |
| Tauri updater 自动更新 | v1.3.1 起可在设置里检查更新。v1.3.0 及更早要先手动安装 |
| 依赖锁版本 / 构建缓存 | 直接依赖已锁定（#94）；PBS + ffmpeg 下载有 actions/cache，Rust 有 rust-cache |
| `ruff` 在 CI 中仍是 `continue-on-error` | typecheck 已阻断（#90）；ruff 存量 ~130 条多为风格规则，需先收敛规则集再阻断 |

---

## 三、GitHub 待办快照（2026-09-06）

### 外部 PR（2026-09-06 全部处理完，当前 0 个 open）
原则：**外部 PR 谨慎对待，能不合入就不合入**；采纳的改动以 cherry-pick 进自己的 PR 并保留署名。

| PR | 处理 |
|----|------|
| #85 #84 #83 | 已 cherry-pick 进 #91 随 v1.2.1 发布，原 PR 留言关闭 |
| #78 Atlas Cloud provider | 被 #92 自定义 base_url 替代，留言关闭 |
| #79 README star chart | 关闭：官方 `api.star-history.com` 实测正常，PR 是把图片源换到不明第三方域名 |
| #76 TakoAPI 徽章 | 关闭 |
| #86 Windows `.vbs` 开发态启动器 | 关闭：Windows 安装包已随 v1.2.1 提供 |
| #82 1080p60 + 全英文 UI + 迁移脚本（49 文件） | 关闭：不可 review，且全英文与产品方向不符；欢迎单独提 1080p60 小 PR |
| #75 TwelveLabs Pegasus 评分 | 关闭：Step 3 评分后端可插拔接口定好之前不接任何具体厂商；v1.4 做接口时回引 |

### Issue 治理（2026-09-06 已执行）
label 体系：默认 9 个 + 新增 `docker` / `windows` / `feature`。**置顶帖 #96**「当前状态 / 已知问题 / 怎么反馈」，
"用不了"类 issue 统一回复到它。open 从 55 → 28（不含 #96），除分享贴 #40 #56 外全部有 label。

- **已关闭（v1.2.1 修复）**：#88 #47 #50 #53 #54 #55 #62；#51 #52（dev compose，措辞留了余地）
- **已关闭（not planned，回复引导到 #96）**："用不了"类 #7 #26 #30 #31 #32 #39 #42 #43 #59；噪音 #3 #13 #23 #25 #34 #41 #58 #60 #80 #87
- **仍 open · Docker/部署**（`docker,bug`）：#1 #4 #5 #6 #9 #15 #21 #33 → 老帖，可在 v1.2.1 Release 出来后统一引导重试再关
- **仍 open · Windows**（`windows`）：#2 #19 #35 → 可引导到 v1.2.1 Release 的 Windows 包后关闭（#73 已关）
- **仍 open · 功能请求**（`feature`）：#67 FunASR/SenseVoice、#45 阿里云国际（#57 #72 已由 #92 关闭）
- **仍 open · 待复现的产品 bug**（`bug`）：#11 切片为 0、#24 进度错误、#38 缩略图、#20 导入报错、#27 加载失败、#77 API 连接测试失败
- **仍 open · question**：#10 #14 #18 #36；分享贴 #40 #56 不动

### 2026-09-20 复审结论（open 16 条，含 #96）
| 处置 | Issue | 依据 |
|---|---|---|
| 修复（本轮） | #100 | 见上「#100 修复」；回复用户：关掉浏览器翻译 + 升级后可在设置页直接保存 |
| 引导升级 v1.2.1 后关闭 | #24 进度卡 20% | 评论里 newengine 的方案就是 worker 缺 `-Q`，#89 已修 |
| 合并为一条「缩略图链路」bug 或关闭 | #20 #38 #18（第三条） | 同根因：ffmpeg 提的 cover jpg 再喂 ffmpeg 解 mjpeg 失败；近一年无新报告 |
| 关闭（已修） | #27 缺 pytz（v1.1.0）、#14 前端硬编码 localhost（v1.2.1） | |
| 保留，v1.3 发版后引导复测 | #11 切片为 0 | 评分兜底 top-K 已在 main 未发版 |
| `needs-info` 走自动流程 | #77 | 只有一张截图 |
| 引导到 #96 关闭 | #10 #36 | 无有效信息 |
| 直接回复可用方案后关闭或转 feature | #45 阿里云国际 | 选「OpenAI 兼容」+ base_url `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` 即可；v1.3 在 dashscope 卡片加「国际站」开关 |
| 保留，排入 v1.4 | #67 SenseVoice | LauraGPT 已在 123mlly fork 提了修好词级时间戳的 PR（含 5 条回归测试），是 ASR 可插拔接口的第一个候选实现 |

外部 PR（2026-09-20）：#97 `ProjectResponse` 缺默认值（已核实 pydantic v2 下必填，`POST /projects/` 必 500，2 行 + 测试）、#98 文档 worker 补 `-Q`（与 #89 同源）→ **合入**；
#99 自己的 CI 修复 → 合入（main 自 `9f81b5c` 起 CI 红；本轮 #100 PR 已顺手删掉同一行）；
#101 i18n 英文本地化（18 文件 +1393，外部首次贡献）→ **不直接合大 PR**：先由维护者定 i18n 骨架（见 v1.3），再请作者按规范分批提。理由见 v1.3「i18n」。

### 反馈收件箱（2026-09-07 搭好，替代 QQ 群 / 个人飞书）
原则：不再让用户来加维护者，反馈自己流到一个每周看一次的地方。三个入口：

| 入口 | 面向 | 实现 | 自动化 |
|------|------|------|--------|
| **飞书表单** | 已停用（2026-09-21） | 八语界面之后不再用多维表格收反馈。旧表 `EuYLb3lQ2awwDFsTkDXchabsnbd` 留作历史，应用和周报都不再写入或读取 | — |
| **GitHub Issue Forms** | 开发者 | `.github/ISSUE_TEMPLATE/`：bug（版本 / 平台 / 模型必填）。功能想法走 Discussions。config.yml 联系链接（#96 / Ideas / Q&A） | `.github/workflows/issue-hygiene.yml`：新 issue 自动回复节奏；`needs-info` 14+7 天自动关；60+14 天 stale；`pinned` / `feature` 不自动关 |
| **官网 `#feedback`** | 待改 | `autoclip_intro` 若仍链到飞书表单，要在那个仓库改掉。本仓库不再把人送去那张表 | — |

- 新 label：`needs-triage`（模板自动打）/ `needs-info` / `stale` / `pinned`（#96 已打）。
- #96 已加「怎么反馈」小节。
- 飞书 CLI 不再用于收反馈。旧表可留档，不要再挂到应用或官网上。
- **应用内反馈**（2026-09-07 做完）：`frontend/src/analytics/feedback.ts` + `components/FeedbackDialog.tsx`。入口：设置页「反馈」区、项目卡失败态 `重试 · 反馈`、详情页失败态 `反馈问题`、切片为 0 空态。自动附带 版本 / OS / 架构 / provider / model / 失败阶段 / 错误文本；用户只写一句话 + 可选联系方式。
  - 事件：`feedback_opened` / `feedback_submitted` / `feedback_dismissed`（PostHog）。若 PostHog 项目里存在名为 **「AutoClip 应用内反馈」**（`FEEDBACK_SURVEY_NAME`，或 `VITE_PUBLIC_POSTHOG_FEEDBACK_SURVEY_ID` 指定 id）的 API 型 Survey（无 UI，第一题自由文本、第二题单选分类），会同时按 PostHog 约定发 `survey shown / sent / dismissed`，结果进 Surveys 面板。**Survey 尚未在 PostHog 后台创建**（不创建也不影响事件采集）。
  - 点「发送」不看匿名统计开关。句子进入 PostHog 的 `feedback_submitted`（带反馈编号）。每小时 `.github/workflows/ingest-feedback.yml` 把它写进 GitHub：故障开 Issue（`bug` / `needs-triage` / `from-app`），想法开 Ideas，其他开 Q&A。同一编号只写一次。邮箱不进公开帖。没有 PostHog key 或网络失败时，打开预填好的 GitHub 页面。收件需要仓库 secret `POSTHOG_PERSONAL_API_KEY`（`POSTHOG_PROJECT_ID` 可省略，默认 450605）。
- **每周反馈周报**：`scripts/weekly_digest.py`（仅标准库）。合并 GitHub 新 issue（`gh`，或 `GH_TOKEN` REST）+ Discussions + PostHog `feedback_submitted`（`POSTHOG_PERSONAL_API_KEY` + `POSTHOG_PROJECT_ID`，HogQL）→ markdown。可选发到飞书群机器人 webhook（`FEISHU_WEBHOOK_URL`，可选 `FEISHU_WEBHOOK_SECRET`），这只是把周报推给维护者，不再从飞书表格读反馈。`--json` 给 agent 做主题归纳，`--post --message-file` 发归纳后的版本。Cursor Automation（每周一 09:00 跑该脚本并归纳主题）的草稿已备好，待在 Automations 编辑器里配 secrets 后保存。

### 社区看板（2026-09-21）

公开路线图定为 **GitHub Discussions + GitHub Projects**，费用为零。Quackback 留到非开发者反馈明显多过 GitHub 再装。Featurebase、Linear、Productlane 不采用。规则、六列、初始看板和触发条件见 `docs/COMMUNITY_BOARD.md`。

- 想法、用法、模型、提问走 Discussions 五个分类；能复现的故障才开 Issue。功能请求模板已去掉。
- 已决定跟进的需求写成带 `status:*` 的 Issue，放进公开 Project「AutoClip Roadmap」。
- Agent 读 `scripts/feature_signals.py`，人确认后才能把卡推进到 Planned 及以后。操作说明在 `skills/product-board/SKILL.md`。
- 应用内反馈先到 PostHog，再由收件任务进入 Issue 或 Discussions。这些帖子不是路线图卡片。飞书表格不再收反馈。
- 装到 GitHub 上：`python3 scripts/setup_community_board.py --apply` 写标签和公开 Project。Discussion 分类没有写入接口，脚本会列出要在网页上新建或修改的分类。种子 Issue 另跑 `--seed-issues`，避免一次开出十几张旧账。

---

## 四、迭代计划

当前发布版本是 **v1.3.3**。合进 main 的改动先停在路线图的 Building，攒一批再打一个 tag，不为单个 PR 发版。社区新想法默认停在 Exploring。接下来先做 Windows 真机验证、安装包公证与代码签名、首页和项目卡。账号仍等公证和代码签名完成。排序见 `docs/COMMUNITY_BOARD.md`。

### v1.2.1 发版
- [x] 合并 #89 #90 #91 #92 #93 #94
- [x] `workflow_dispatch` 只勾 Windows 试构建：通过，安装包 145 MB（run 34040814275）
- [x] 打 `v1.2.1` tag（`a5c20ae`）→ Desktop Build run 34042037733 全绿（Windows 10 min / mac 14 min），
      Release 两个文件齐：`AutoClip.Desktop_1.2.1_aarch64.dmg`（223 MB）、`AutoClip.Desktop_1.2.1_x64-setup.exe`（145 MB）；标题已改；#73 已关
- [ ] 把 Windows 安装包装到一台干净 Windows 上验证：能启动、设置页保存 provider、跑通一条本地视频。v1.3.1 发布后这条仍没有记录（最可能翻车的点：NSIS 几千个 Python 文件、WebView2 引导、`%APPDATA%\AutoClip` 目录）
- [ ] 用真实 key 各测一遍 4 个 provider 的「测试连接」+ 一次完整处理（#92 改动了 provider 选择链路，单测覆盖了逻辑但没打过真接口；尤其 openai SDK 已是 3.x）。v1.3.1 没有补上这条记录
- [x] 关闭已修复 issue、关闭外部 PR #83 #84 #85 #78
- [x] label 体系 + 置顶帖 #96 + "用不了"类统一回复关闭
- [x] 外部 PR 全部留言关闭（见第三节表格）

### 已随 v1.3.0 / v1.3.1 发布
- [x] **八语界面与官网**（v1.3.1）：`i18next`，`locales/{zh,en,ja,ko,es,pt,ru,fr}.json`，设置与顶栏可切换或跟随系统。维护方式见 `docs/INTERNATIONALIZATION.md`
- [x] **应用内检查更新**（v1.3.1）：设置里可手动检查，启动时每天最多自动查一次。v1.3.0 及更早要先手动安装
- [x] **崩溃上报**（v1.3.1）：前端与 Python 都接了，发送前去掉正文。设置里可关。生产构建验收见 `docs/UPDATES_AND_SENTRY.md`
- [x] **匿名统计 v2**（v1.3.1）：区分请求和实际结果。线上接收还没单独验收
- [x] CLI / MCP、本地模型预设、时长画像与评分兜底、竖屏发布导出（v1.3.0）
- [x] Docker 设置页可保存；浏览器翻译不再把整页打崩（#100，v1.3.0）
- [x] 失败要写明阶段和原因；本地上传会自动开始；SQLite 不再因 `StaticPool` 互相回滚（v1.3.0）
- [x] Qwen 国际站（#45）；`min_score` 接到 step3；周更发版脚本（v1.3.0）

### v1.3.1 之后仍未完成
- [ ] Windows 包稳定后：Intel mac（PBS `x86_64-apple-darwin` + osxexperts intel 静态包，脚本只需改两个变量）
- [ ] Apple Developer ID 签名 + 公证（去掉「右键打开」）；Windows 代码签名（去掉 SmartScreen 警告）。更新包签名和安装包公证不是一件事
- [ ] `ruff` 规则集收敛后改为阻断；`requirements-dev.txt` 拆出 pytest（Dockerfile / 桌面包不再装测试依赖）
- [ ] 首页导入框、`ProjectTaskManager`、`CollectionPreviewModal` / `CreateCollectionModal`、B 站登录弹窗仍是 AntD 默认件，下一轮按 `frontend/src/ui/` 原语重做
- [ ] `ProjectCard.tsx` 只做了「去色 + 失败态反馈」的局部修补（仍是 AntD Card + 内联样式），应整体重写成 `ac-card`
- [ ] `chunk_size` / `max_clips_per_collection` 已进 settings，step1 / step5 尚未读取
- [ ] `DESIGN.md` 欠账清单（`ErrorBoundary` 已改）：`index.css:704-712`、`assets/background.svg`、`FileUpload.tsx`、`BilibiliDownload.tsx`、
      `BilibiliManager.css`、`CreateCollectionModal.css`、`CollectionPreviewModal_fixed.tsx` 仍有渐变 / 撞色
- [ ] CLI / MCP 端到端：用一条真实视频跑 `autoclip run --provider ollama --json` 和 MCP `start_clip_job` 轮询到 completed；
      `autoclip` 装进 Homebrew tap / PyPI（现在只有 `pip install -e .`）；README 首屏放一段 CLI 演示
- [ ] 桌面应用设置页加「Ollama 未运行」的就地提示（现在只在模型下拉里显示「未检测到模型」）。`min_score` 已在 v1.3.0 接到 step3
- [ ] 质量对照：拿一条 5 分钟、一条 60 分钟真视频，对比改前提示词口径 vs 现在的 duration profile；把结果补进 `backend/eval/cases/`
- [ ] 发布导出：抖音 / Shorts / B 站三预设各导一条人工看字幕与标题卡；说话人居中裁切仍未做。自动封面已在 v1.3.2

### v1.4 · 产品质量
- [ ] 切片质量回归集（#59 "5 分钟视频切出 3 个 2 分钟"、#11 切片为 0、#24 进度）
- [ ] **ASR 后端可插拔**（#67）：在 `utils/speech_recognizer.py` 抽 `ASRBackend` 协议（`transcribe(audio) -> cues`，cue 必须单调、不重叠、不超时长），
      faster-whisper 为默认实现；接口定稿后邀请 LauraGPT / 123mlly 把 fork 上的 SenseVoice 实现（词级 CTC 对齐 → cue 聚合 + 回归测试）按协议提 PR。
      不在接口之前合任何具体 ASR 厂商代码
- [ ] **Step 3 评分后端可插拔**（接纳 #75 思路）：同样先定协议再接厂商
- [ ] 用 v1.3.1 安装包在真机上看一次崩溃是否进 Sentry。代码和一次生产前端验收已经有了，#77 这类只有截图的 issue 仍要靠安装包上的栈
- [ ] 之后按 `ROADMAP.md` 进入 Phase 1（Supabase 账号骨架）。应用内更新和崩溃上报已经在 v1.3.1；Apple 公证和 Windows 代码签名完成前不开 Phase 1

---

## 五、关键文件

- 打包脚本：`scripts/build_macos_arm.sh`、`scripts/build_windows_x64.sh`，共用 `scripts/lib/desktop_build_common.sh`（说明见 `scripts/README.md`）；Windows 资源声明在 `src-tauri/tauri.windows.conf.json`
- 后端启动器（Rust）：`src-tauri/src/backend_manager.rs`（注入 `AUTOCLIP_DESKTOP_MODE` / `AUTOCLIP_APP_DIR` / ffmpeg 路径 / `AUTOCLIP_APP_VERSION`；Windows 下 `PYTHONUTF8=1`）
- 桌面后端入口：`backend/desktop_main.py`
- 任务提交（桌面本地线程 vs Celery）：`backend/utils/task_submission_utils.py`、`backend/core/celery_app.py`（DesktopAwareTask、task_routes）
- ffmpeg 路径解析：`backend/utils/ffmpeg_utils.py`
- LLM 提供商：`backend/core/llm_providers.py`（含 `is_local_url` / `make_openai_http_client` 绕过系统代理）；provider / base_url 选择与热重载：`backend/core/llm_manager.py`；本地预设：`backend/core/local_presets.py`；设置 API：`backend/api/v1/settings.py`（`/local-presets`、`/compatible-models`）
- CLI / MCP：`backend/cli.py`、`backend/mcp_server.py`，共用 `backend/services/local_runner.py`（环境 / LLM 覆盖 / 项目准备 / 跑流水线 / 结果汇总）；进度监听 `services/simple_progress.py#add_progress_listener`；打包 `pyproject.toml`；Agent skill `skills/autoclip/SKILL.md`；文档 `docs/CLI_AND_MCP.md`
- 出片质量：`backend/pipeline/quality.py`（时长画像 / refine / 评分兜底），接入 step1–3；回归 `backend/eval/`；方案 `docs/QUALITY_AND_PUBLISH_PLAN.md`
- 发布导出：`backend/services/publish_export.py`；API `POST /projects/{id}/clips/{id}/export`；CLI `autoclip export`；MCP `export_clip`；前端 `ClipCard` Dialog
- YouTube 导入：`backend/api/v1/youtube.py`（`AUTOCLIP_YT_SUBTITLE_LANGS`、`AUTOCLIP_YT_CLIENT`）
- Whisper 运行时（按需安装）：`backend/services/whisper_runtime.py`、`whisper_model_manager.py`、
  前端 `frontend/src/components/SpeechRecognitionConfig.tsx`
- 前端 UI 原语（`DESIGN.md` App Layer）：`frontend/src/ui/index.tsx` + `ui/ac.css`；已迁移页面：`pages/ProjectDetailPage.tsx`、`pages/SettingsPage.tsx`、`components/ClipCard.tsx`、`CollectionCard.tsx`、`SpeechRecognitionConfig.tsx`
- 反馈：`frontend/src/analytics/feedback.ts`、`components/FeedbackDialog.tsx`；运行时信息 `analytics/lifecycle.ts#getRuntimeInfo`。不再使用飞书表格。社区看板见 `docs/COMMUNITY_BOARD.md`
- 界面语言：`frontend/src/i18n/`、`docs/INTERNATIONALIZATION.md`
- 更新与崩溃上报：`frontend/src/desktop/updater.ts`、`frontend/src/desktop/sentry.ts`、`docs/UPDATES_AND_SENTRY.md`
- 浏览器翻译守卫 / 错误边界：`frontend/src/utils/domTranslationGuard.ts`（`main.tsx` 挂载前调用）、`components/ErrorBoundary.tsx`；
  Web 模式设置端点回归：`backend/tests/test_settings_web_mode.py`
- 周报：`scripts/weekly_digest.py`
- 本地联调（后端随机端口时）：`BACKEND_URL=http://127.0.0.1:PORT npm run dev`（`vite.config.ts` 代理可被覆盖）
- Docker：`Dockerfile`、`docker-compose.yml`（四服务共用 `autoclip:local`）、`docker-entrypoint.sh`
- CI：`.github/workflows/ci.yml`（backend / frontend / docker-smoke）、`desktop-build.yml`（tag 触发）

## 六、安装（给用户）

**桌面版（推荐，当前 v1.3.3）**
1. 从 Releases 下载：macOS 用 DMG，Windows 用 `x64-setup.exe`
2. macOS **首次右键应用 → 打开**（ad-hoc 签名，绕过 Gatekeeper）。Windows 安装包未做代码签名，可能要在 SmartScreen 里选择仍要运行
3. 已装 v1.3.0 或更早的，先手动装上 v1.3.1。之后在「设置 → 应用 → 检查更新」
4. 进设置页填 LLM API key，或选本机 Ollama / LM Studio

**Docker**
```bash
docker compose up -d --build
# 前端 http://localhost:3000 · API http://localhost:8000/api/v1/health/
```
Linux 宿主机首次启动前先 `mkdir -p data logs uploads && chmod -R 777 data logs uploads`
（容器以非 root 用户运行，bind mount 目录默认 root 所有）。

命令行排查桌面后端：
```bash
'/Applications/AutoClip Desktop.app/Contents/MacOS/autoclip-desktop'
# 应看到 Backend started on port: XXXXX / Application startup complete
```
