# AutoClip — 项目状态 / 进度 / 计划

> 更新：2026-09-06 · 基于 `main@a5c20ae`（**v1.2.1 已发布**：Release 含 macOS arm64 DMG 223 MB + Windows x64 安装包 145 MB）

AutoClip 是一款 AI 视频切片工具：输入 B站/YouTube 链接或本地视频，自动识别精彩片段、
生成切片与合集。本文是项目当前状态与近期计划的单一事实来源；长期规划见 `ROADMAP.md`。

---

## 一、架构与交付形态

| 层 | 技术 | 目录 |
|----|------|------|
| 后端 | FastAPI + Celery（桌面模式用本地线程）+ SQLite | `backend/` |
| 前端 | React + TypeScript + Ant Design + Vite | `frontend/` |
| 桌面壳 | Tauri 2 + Rust | `src-tauri/` |
| LLM | OpenAI 及一切 OpenAI 兼容接口（自定义 base_url）/ Gemini(google-genai) / 通义千问(dashscope) / 硅基流动 | `backend/core/llm_providers.py`、`llm_manager.py` |

三种交付形态：**桌面客户端**（macOS arm64 DMG 主推；Windows x64 安装包 v1.2.1 起提供，尚未在真机验证）、**Docker 部署**（README 推荐路径）、
**本地脚本启动**（`start_autoclip.sh`）。

---

## 二、当前状态

### 已完成
- **v1.2.0（2026-06-03）**：桌面端 DMG 端到端可用（内置便携 Python + 静态 ffmpeg + 按需安装 faster-whisper），
  `desktop-build.yml` 在 tag 上跑通并自动挂 Release；v1.2.0 DMG 已有 2000+ 下载。
- **PostHog 匿名埋点** + 隐私政策 + 设置页开关（`docs/ANALYTICS.md`、`docs/PRIVACY*.md`）。
- **Calm Premium 视觉系统**落地（`DESIGN.md`）。
- Nightly 后端冒烟（`nightly-desktop-smoke.yml`）持续全绿。

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
| Apple Developer ID 签名 + 公证 | 未做，`signingIdentity: null`，用户需右键打开 |
| 多平台包（Windows / Intel mac / Linux） | Windows x64 已在 runner 出包（#93），随 v1.2.1 Release 发布，**真机未验证**；Intel mac / Linux 未做 |
| Sentry 崩溃上报 | 未接 |
| Tauri updater 自动更新 | 未接 |
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

### 反馈收件箱（2026-09-07 搭好，替代 QQ 群 / 个人飞书）
原则：不再让用户来加维护者，反馈自己流到一个每周看一次的地方。三个入口：

| 入口 | 面向 | 实现 | 自动化 |
|------|------|------|--------|
| **飞书表单** | 不用 GitHub 的普通用户 | 多维表格「AutoClip 用户反馈」（个人账号 `my.feishu.cn`，base `EuYLb3lQ2awwDFsTkDXchabsnbd`，表「反馈」）。公开表单 `https://my.feishu.cn/share/base/shrcn8hKUG2icIJLpNry6uWVNJe`，字段：类型 / 反馈内容 / 平台 / 版本 / 截图日志 / 联系方式；内部字段 状态 / 处理备注 / 提交时间 | 自动化 `wkfTMIXp3h6zTWNk`：新记录 → 状态置「新」→ 飞书消息通知（带「打开记录」按钮） |
| **GitHub Issue Forms** | 开发者 | `.github/ISSUE_TEMPLATE/`：bug（版本 / 平台 / 模型必填）、feature、config.yml 联系链接（#96 / Discussions / 官网表单）。Discussions 已开启 | `.github/workflows/issue-hygiene.yml`：新 issue 自动回复节奏；`needs-info` 14+7 天自动关；60+14 天 stale；`pinned` / `feature` 不自动关 |
| **官网 `#feedback`** | 所有人 | `autoclip_intro` FAQ 区的「提交反馈」卡，指向飞书表单 + Issues / Discussions；QQ / 飞书二维码已撤 | — |

- 新 label：`needs-triage`（模板自动打）/ `needs-info` / `stale` / `pinned`（#96 已打）。
- #96 已加「怎么反馈」小节。
- 飞书 CLI：本机 `lark-cli` profile `personal`（app `cli_aa9ce7782ea39bcf`）；yahaha 账号下误建的同名空表可删。
- **未做**：应用内反馈入口（PostHog Surveys，设置页 + 失败态）；每周汇总周报自动化（issue + 表单 + survey → 飞书）。

---

## 四、迭代计划

### v1.2.1 发版
- [x] 合并 #89 #90 #91 #92 #93 #94
- [x] `workflow_dispatch` 只勾 Windows 试构建：通过，安装包 145 MB（run 34040814275）
- [x] 打 `v1.2.1` tag（`a5c20ae`）→ Desktop Build run 34042037733 全绿（Windows 10 min / mac 14 min），
      Release 两个文件齐：`AutoClip.Desktop_1.2.1_aarch64.dmg`（223 MB）、`AutoClip.Desktop_1.2.1_x64-setup.exe`（145 MB）；标题已改；#73 已关
- [ ] 把 Windows 安装包装到一台干净 Windows 上验证：能启动、设置页保存 provider、跑通一条本地视频
      （最可能翻车的点：NSIS 几千个 Python 文件、WebView2 引导、`%APPDATA%\AutoClip` 目录）
- [ ] 用真实 key 各测一遍 4 个 provider 的「测试连接」+ 一次完整处理（#92 改动了 provider 选择链路，单测覆盖了逻辑但没打过真接口；尤其 openai SDK 已是 3.x）
- [x] 关闭已修复 issue、关闭外部 PR #83 #84 #85 #78
- [x] label 体系 + 置顶帖 #96 + "用不了"类统一回复关闭
- [x] 外部 PR 全部留言关闭（见第三节表格）

### v1.3 · Phase 0 收尾 + 高频需求
- [ ] Windows 包稳定后：Intel mac（PBS `x86_64-apple-darwin` + osxexperts intel 静态包，脚本只需改两个变量）
- [ ] Apple Developer ID 签名 + 公证（去掉"右键打开"）；Windows 代码签名（去掉 SmartScreen 警告）
- [ ] Tauri updater 自动更新；Sentry 崩溃上报
- [ ] `ruff` 规则集收敛后改为阻断；`requirements-dev.txt` 拆出 pytest（Dockerfile / 桌面包不再装测试依赖）
- [ ] 设置页 provider 卡片 / 彩色 Tag 与 `DESIGN.md`（近乎单色、只用一个蓝）不符，改造时一并处理
- [ ] Docker 模式下开放设置页（目前 `check_desktop_mode` 直接 400，只能靠 .env）

### v1.4 · 产品质量
- [ ] 切片质量回归集（#59 "5 分钟视频切出 3 个 2 分钟"、#11 切片为 0、#24 进度）
- [ ] Step 3 评分后端可插拔（接纳 #75 思路）；ASR 后端可插拔（#67）
- [ ] 之后按 `ROADMAP.md` 进入 Phase 1（Supabase 账号骨架）

---

## 五、关键文件

- 打包脚本：`scripts/build_macos_arm.sh`、`scripts/build_windows_x64.sh`，共用 `scripts/lib/desktop_build_common.sh`（说明见 `scripts/README.md`）；Windows 资源声明在 `src-tauri/tauri.windows.conf.json`
- 后端启动器（Rust）：`src-tauri/src/backend_manager.rs`（注入 `AUTOCLIP_DESKTOP_MODE` / `AUTOCLIP_APP_DIR` / ffmpeg 路径 / `AUTOCLIP_APP_VERSION`；Windows 下 `PYTHONUTF8=1`）
- 桌面后端入口：`backend/desktop_main.py`
- 任务提交（桌面本地线程 vs Celery）：`backend/utils/task_submission_utils.py`、`backend/core/celery_app.py`（DesktopAwareTask、task_routes）
- ffmpeg 路径解析：`backend/utils/ffmpeg_utils.py`
- LLM 提供商：`backend/core/llm_providers.py`；provider / base_url 选择与热重载：`backend/core/llm_manager.py`；设置 API：`backend/api/v1/settings.py`
- YouTube 导入：`backend/api/v1/youtube.py`（`AUTOCLIP_YT_SUBTITLE_LANGS`、`AUTOCLIP_YT_CLIENT`）
- Whisper 运行时（按需安装）：`backend/services/whisper_runtime.py`、`whisper_model_manager.py`、
  前端 `frontend/src/components/SpeechRecognitionConfig.tsx`
- Docker：`Dockerfile`、`docker-compose.yml`（四服务共用 `autoclip:local`）、`docker-entrypoint.sh`
- CI：`.github/workflows/ci.yml`（backend / frontend / docker-smoke）、`desktop-build.yml`（tag 触发）

## 六、安装（给用户）

**桌面版（推荐）**
1. 从 Releases 下载 DMG → 拖 `AutoClip Desktop` 到 Applications
2. **首次右键应用 → 打开**（ad-hoc 签名，绕过 Gatekeeper）
3. 进设置页填 LLM API key 即可使用

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
