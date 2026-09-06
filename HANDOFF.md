# AutoClip — 项目状态 / 进度 / 计划

> 更新：2026-09-06 · 基于 `main@17100c0`（v1.2.0）+ 分支 `cursor/v1.2.1-docker-hotfix-85bc`

AutoClip 是一款 AI 视频切片工具：输入 B站/YouTube 链接或本地视频，自动识别精彩片段、
生成切片与合集。本文是项目当前状态与近期计划的单一事实来源；长期规划见 `ROADMAP.md`。

---

## 一、架构与交付形态

| 层 | 技术 | 目录 |
|----|------|------|
| 后端 | FastAPI + Celery（桌面模式用本地线程）+ SQLite | `backend/` |
| 前端 | React + TypeScript + Ant Design + Vite | `frontend/` |
| 桌面壳 | Tauri 2 + Rust | `src-tauri/` |
| LLM | OpenAI / Gemini(google-genai) / 通义千问(dashscope) / 硅基流动 | `backend/core/llm_providers.py` |

三种交付形态：**桌面客户端**（macOS arm64 DMG，主推）、**Docker 部署**（README 推荐路径）、
**本地脚本启动**（`start_autoclip.sh`）。

---

## 二、当前状态

### 已完成
- **v1.2.0（2026-06-03）**：桌面端 DMG 端到端可用（内置便携 Python + 静态 ffmpeg + 按需安装 faster-whisper），
  `desktop-build.yml` 在 tag 上跑通并自动挂 Release；v1.2.0 DMG 已有 2000+ 下载。
- **PostHog 匿名埋点** + 隐私政策 + 设置页开关（`docs/ANALYTICS.md`、`docs/PRIVACY*.md`）。
- **Calm Premium 视觉系统**落地（`DESIGN.md`）。
- Nightly 后端冒烟（`nightly-desktop-smoke.yml`）持续全绿。

### v1.2.1 止血（本分支，待合并发版）
问题根源：README 推荐的 `docker compose` 路径从 2025-09 起就没能跑通过一次完整处理
（issue #88 给出 7 条可复现问题，全部核验属实），是 issue 区大量"用不了"的来源。本分支修复：
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

### 仍未完成（ROADMAP Phase 0）
| 项 | 状态 |
|---|---|
| Apple Developer ID 签名 + 公证 | 未做，`signingIdentity: null`，用户需右键打开 |
| 多平台包（Windows / Intel mac / Linux） | 未做；Windows 是 issue 里最大的单一需求（#2 #19 #35 #73 #86） |
| Sentry 崩溃上报 | 未接 |
| Tauri updater 自动更新 | 未接 |
| 依赖锁版本 / 构建缓存 | 未做 |
| `ruff` / `npm run typecheck` 在 CI 中仍是 `continue-on-error` | 6 个 `NodeJS.Timeout` 类型错误待清 |

---

## 三、GitHub 待办快照（2026-09-06）

### Open PR（9 个，均未 review；外部贡献者的 CI 需维护者在 Actions 里批准后才会跑）
| PR | 建议 |
|----|------|
| #85 日志 FileHandler `encoding="utf-8"` | 合并，无风险 |
| #84 Gemini 改用 `-latest` 模型别名 | 合并前用真实 key 调一次 |
| #83 `youtube.py` 五连修（cookie 回退、字幕/视频拆分下载、`Path` 遮蔽、`project_name` 可选） | 合并；与本分支在 `youtube.py` 有小冲突，谁后合谁 rebase |
| #79 README star chart | 确认新图表域名可信后合并 |
| #78 Atlas Cloud provider | 引导改为通用「OpenAI-compatible + 自定义 base_url」provider，一并解决 #72 #57 |
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

### v1.2.1（本分支）→ 发版
- [ ] 合并本分支；在 Actions 批准并合并 #85 #84 #83
- [ ] 打 `v1.2.1` tag（`desktop-build.yml` 自动出 DMG）
- [ ] 建 label 体系并给 issue 打标；关闭上表"可关闭"项，置顶一个「已知问题与当前状态」issue

### v1.3 · 补齐 Phase 0 + 最高频需求
- [ ] OpenAI-compatible provider 支持自定义 `base_url`（#72 #57，吸收 #78）
- [ ] `build_macos_arm.sh` 参数化 runner / PBS URL / ffmpeg URL / tauri target → Windows x64 包，再 Intel mac
- [ ] Apple 签名 + 公证；Tauri updater；Sentry
- [ ] 锁定 `requirements.txt`；缓存 PBS + 依赖
- [ ] 清掉 6 个 `NodeJS.Timeout` 错误，`ruff` / `typecheck` 改为阻断

### v1.4 · 产品质量
- [ ] 切片质量回归集（#59 "5 分钟视频切出 3 个 2 分钟"、#11 切片为 0、#24 进度）
- [ ] Step 3 评分后端可插拔（接纳 #75 思路）；ASR 后端可插拔（#67）
- [ ] 之后按 `ROADMAP.md` 进入 Phase 1（Supabase 账号骨架）

---

## 五、关键文件

- 打包脚本：`scripts/build_macos_arm.sh`（说明见 `scripts/README.md`、`BUILD_GUIDE.md`）
- 后端启动器（Rust）：`src-tauri/src/backend_manager.rs`（注入 `AUTOCLIP_DESKTOP_MODE` / ffmpeg 路径 / `AUTOCLIP_APP_VERSION`）
- 桌面后端入口：`backend/desktop_main.py`
- 任务提交（桌面本地线程 vs Celery）：`backend/utils/task_submission_utils.py`、`backend/core/celery_app.py`（DesktopAwareTask、task_routes）
- ffmpeg 路径解析：`backend/utils/ffmpeg_utils.py`
- LLM 提供商：`backend/core/llm_providers.py`
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
