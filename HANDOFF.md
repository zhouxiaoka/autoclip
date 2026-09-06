# AutoClip — 项目状态 / 进度 / 计划

> 更新：2026-09-06 · 基于 `main@992239a`（#89 #90 #91 #92 #93 #94 已全部合入，v1.2.1 待打 tag）

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

三种交付形态：**桌面客户端**（macOS arm64 DMG 主推；Windows x64 安装包首版待验证）、**Docker 部署**（README 推荐路径）、
**本地脚本启动**（`start_autoclip.sh`）。

---

## 二、当前状态

### 已完成
- **v1.2.0（2026-06-03）**：桌面端 DMG 端到端可用（内置便携 Python + 静态 ffmpeg + 按需安装 faster-whisper），
  `desktop-build.yml` 在 tag 上跑通并自动挂 Release；v1.2.0 DMG 已有 2000+ 下载。
- **PostHog 匿名埋点** + 隐私政策 + 设置页开关（`docs/ANALYTICS.md`、`docs/PRIVACY*.md`）。
- **Calm Premium 视觉系统**落地（`DESIGN.md`）。
- Nightly 后端冒烟（`nightly-desktop-smoke.yml`）持续全绿。

### v1.2.1（已全部合入 main，待打 tag 发版）
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
- **#93** Windows x64 打包脚本 + workflow（未在真机跑过，见下方 todo）

### 仍未完成（ROADMAP Phase 0）
| 项 | 状态 |
|---|---|
| Apple Developer ID 签名 + 公证 | 未做，`signingIdentity: null`，用户需右键打开 |
| 多平台包（Windows / Intel mac / Linux） | Windows x64 脚本 + workflow 已合入（#93）但**尚未在 Windows runner 上跑过**；Intel mac / Linux 未做 |
| Sentry 崩溃上报 | 未接 |
| Tauri updater 自动更新 | 未接 |
| 依赖锁版本 / 构建缓存 | 直接依赖已锁定（#94）；PBS + ffmpeg 下载有 actions/cache，Rust 有 rust-cache |
| `ruff` 在 CI 中仍是 `continue-on-error` | typecheck 已阻断（#90）；ruff 存量 ~130 条多为风格规则，需先收敛规则集再阻断 |

---

## 三、GitHub 待办快照（2026-09-06）

### Open PR（外部；本仓库自己的 6 个 PR 已全部合入）
| PR | 建议 |
|----|------|
| #85 #84 #83 | **已通过 #91 合入**（cherry-pick），GitHub 不会自动关闭 → 手动关闭并留言致谢 + 指向 #91 |
| #78 Atlas Cloud provider | **已被 #92 替代**：设置页 OpenAI 提供商填 base_url 即可接 Atlas Cloud → 留言后关闭 |
| #79 README star chart | 确认新图表域名可信后合并 |
| #75 TwelveLabs Pegasus 评分（opt-in） | 先定义"Step 3 评分后端可插拔"接口再接；SDK 放 extra 而非主 requirements |
| #82 1080p60 + 全英文 prompt/UI + 迁移脚本（49 文件） | 要求拆分，否则关闭 |
| #86 Windows `.vbs` 开发态启动器 | 关闭或移入 `scripts/`；真正需求是 Windows 安装包 |
| #76 TakoAPI 徽章 | 关闭 |

### Open issue 分类（55 个，全部无 label）
- **Docker/部署不可用**（本分支修复后可关闭并引导重试）：#1 #4 #5 #6 #9 #15 #21 #33 #47 #50 #51 #52 #62 #88
- **Windows 部署**：#2 #19 #35 #73 → 等 Windows 包
- **"用不了"类**：#7 #26 #30 #31 #32 #39 #42 #43 #59 → 回复 v1.2.1 + 桌面版
- **功能请求**：#57 智谱、#72 本地模型 URL（同一需求：自定义 base_url）、#67 FunASR/SenseVoice、#45 阿里云国际
- **已修复可关闭**：#54（pytz/openai 已进 requirements）、#55（桌面版内置 ffmpeg）、#53（本分支）
- **待复现的产品 bug**：#11 切片为 0、#24 进度错误、#38 缩略图、#20 导入报错、#27 加载失败、#77 API 连接测试失败
- **噪音**：#3 #13 #23 #25 #34 #41 #58 #60 #80 #87；分享贴：#40 #56

---

## 四、迭代计划

### v1.2.1 发版（代码已齐，剩人工动作）
- [x] 合并 #89 #90 #91 #92 #93 #94
- [ ] **先在 Actions 手动 `workflow_dispatch` `Desktop Build`，只勾 Windows**，看 NSIS 包能否产出；
      装到一台干净 Windows 上验证：能启动、设置页保存 provider、跑通一条本地视频
      （最可能翻车的点：NSIS 打几千个 Python 文件耗时、WebView2 引导、`%APPDATA%\AutoClip` 目录）
- [ ] 打 `v1.2.1` tag → mac + Windows 并行构建，`release` job 自动挂产物（Windows 失败不影响 DMG）
- [ ] 用真实 key 各测一遍 4 个 provider 的「测试连接」+ 一次完整处理（#92 改动了 provider 选择链路，单测覆盖了逻辑但没打过真接口；尤其 openai SDK 已是 3.x）
- [ ] 关闭已修复 issue：#88 #47 #50 #51 #52 #53 #54 #55 #62 #73（Windows 包出来后）；关闭外部 PR #83 #84 #85 #78（见上表）
- [ ] 建 label 体系（bug / docker / windows / feature / question / invalid）并给 issue 打标；置顶一个「已知问题与当前状态」issue，把"用不了"类（#7 #26 #30 #31 #32 #39 #42 #43 #59）统一回复到 v1.2.1

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
