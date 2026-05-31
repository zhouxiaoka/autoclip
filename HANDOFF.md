# AutoClip — 项目状态 / 进度 / 计划

> 更新：2026-05-30 · 分支 `main`（领先 origin 若干 commit，未 push）

AutoClip 是一款 AI 视频切片工具：输入 B站/YouTube 链接或本地视频，自动识别精彩片段、
生成切片与合集。本文是项目的当前状态与路线图的单一事实来源。

---

## 一、架构与交付形态

| 层 | 技术 | 目录 |
|----|------|------|
| 后端 | FastAPI + Celery（桌面模式用本地队列）+ SQLite | `backend/` |
| 前端 | React + TypeScript + Ant Design + Vite | `frontend/` |
| 桌面壳 | Tauri 2 + Rust | `src-tauri/` |
| LLM | OpenAI / Gemini(google-genai) / 通义千问(dashscope) / 硅基流动 | `backend/core/llm_providers.py` |

三种交付形态：**Docker 部署**、**本地脚本启动**（`start_autoclip.sh`）、**桌面客户端**（macOS DMG）。
近期工作集中在桌面客户端。

---

## 二、当前进度（已完成且验证）

桌面客户端打包链路从"打不出能用的包"做到了**端到端可装可用**：

1. **统一打包路线** —— 砍掉历史上互相打架的 PyInstaller / prepare_resources 两条死路线，
   只保留 python-build-standalone（PBS）：便携 Python + 后端源码 + 静态 ffmpeg/ffprobe 全部打进
   `.app`，用户机器零依赖。脚本：`scripts/build_macos_arm.sh`。

2. **修好一连串发版阻断 bug**（都已实测验证）：
   - **ffmpeg 不可用**：原来打包的是 homebrew 动态版（57 个 `/opt/homebrew` 依赖），换成静态
     arm64 ffmpeg+ffprobe（零非系统依赖），并让 Rust 启动器通过 `AUTOCLIP_FFMPEG_PATH`/
     `AUTOCLIP_FFPROBE_PATH` 指向内置二进制。
   - **黑屏**：Vite 把 React/antd 拆成两个 vendor chunk，antd 先于 React 初始化 → `createContext`
     报错、React 不挂载。去掉手动分包后正常渲染。
   - **项目列表一直转圈**：`/api/v1/projects/` 因缺 `pytz` 报 500。补齐 `pytz` 及 LLM SDK
     (`openai`/`google-genai`/`dashscope`) 到 `requirements.txt`。
   - **依赖漂移护栏**：构建期 AST 扫描后端所有 import，缺任何一个直接 fail，杜绝"开发能跑、打包就 500"。

3. **CI 统一** —— 7 个从未成功的桌面构建工作流 → 1 个 `desktop-build.yml`（跑 PBS 脚本，
   `v*` tag 自动挂 Release）。保留 `ci.yml`（测试）、`i18n-sync.yml`（文档）、
   `nightly-desktop-smoke.yml`（后端冒烟）。

4. **仓库清理** —— 删掉约 30 个废弃脚本、嵌套鬼目录、94M 旧 PyInstaller 备份等；
   `scripts/` 只剩 4 个活脚本；重写 `scripts/README.md` 与 `BUILD_GUIDE.md`。

5. **Gemini SDK 迁移** —— 从已停更的 `google-generativeai` 迁到统一的 `google-genai`。

**产物**：`src-tauri/target/release/bundle/macos/AutoClip Desktop_1.0.0_aarch64.dmg`（~260M）。

---

## 三、遗漏 / 未验证（按优先级）

> 已闭环（不再是遗漏）：**完整切片流程**已在打包后的 app 里端到端跑通（粘 B站 链接 → 下载 →
> 字幕 → DashScope 分析 → 评分 → 标题 → 切割 → 出 5 个切片，79s 完成）；**无字幕视频**现在可
> 在「设置 → 语音转写」按需安装 faster-whisper 自动转写（实测安装 214MB、转写出 SRT）。

### 中
- **签名/公证**：目前 ad-hoc 签名，未做 Apple Developer ID 签名 + 公证，用户首次必须右键打开。
- **仅 arm64**：没有 Intel mac / Windows / Linux 包。
- **依赖未锁版本**：`requirements.txt` 多数包没固定版本，跨时间/跨机器构建有漂移风险。
- **构建慢**：每次构建都重装全部 pip 依赖（PBS python 被 `rm -rf` 重建）。可缓存已装好的运行时。
- **Gemini 迁移未对真实 API 验证**：代码与新版 google-genai SDK 接口已对齐并能 import，但没有
  Gemini key 实际调用过（DashScope 路径已实跑验证）。

### 低
- **前端单 bundle ~1.5MB**：去掉分包后是一个大 chunk，桌面端无所谓，若以后也跑 Web 可考虑按路由懒加载。
- **单步重试 `submit_single_step_task`** 仍走 Redis send_task（桌面没改），目前没有入口用到；
  整条流水线的 `.delay()` 已由 DesktopAwareTask 接管本地执行。

---

## 四、未来计划（路线图）

1. **正式签名与公证**：申请 Apple Developer ID，签名 + notarize，消除"右键打开"。
2. **多平台打包**：把 `build_macos_arm.sh` 的 runner / PBS URL / ffmpeg URL / tauri target 参数化，
   扩到 Intel mac、Windows、Linux（PBS 与静态 ffmpeg 都有对应平台版本；faster-whisper 本就跨平台）。
3. **依赖锁定**：固定 `requirements.txt` 版本（或引入 lock 文件），保证可复现构建。
4. **构建提速**：缓存 PBS python + 已装依赖，避免每次重装。
5. **自动 UI 冒烟**：在 CI 里加一步，验证打包后的前端能挂载（而不仅是后端接口通）。
6. 产品向：B站上传、字幕编辑、批量处理、云端同步（见 RELEASE_CHECKLIST.md 后续计划）。

---

## 五、关键文件

- 打包脚本：`scripts/build_macos_arm.sh`（说明见 `scripts/README.md`、`BUILD_GUIDE.md`）
- 后端启动器（Rust）：`src-tauri/src/backend_manager.rs`
- 桌面后端入口：`backend/desktop_main.py`
- ffmpeg 路径解析：`backend/utils/ffmpeg_utils.py`
- LLM 提供商：`backend/core/llm_providers.py`
- 桌面流水线本地执行：`backend/core/celery_app.py`（DesktopAwareTask）、`backend/utils/task_submission_utils.py`
- Whisper 运行时（按需安装）：`backend/services/whisper_runtime.py`、`whisper_model_manager.py`、
  前端 `frontend/src/components/SpeechRecognitionConfig.tsx`
- 前端 API 配置：`frontend/src/utils/apiConfig.ts`
- CI：`.github/workflows/desktop-build.yml`

## 六、安装（给用户）

1. 双击 DMG → 拖 `AutoClip Desktop` 到 Applications
2. **首次右键应用 → 打开**（ad-hoc 签名，绕过 Gatekeeper）
3. 进设置页填 LLM API key 即可使用

命令行排查后端：
```bash
'/Applications/AutoClip Desktop.app/Contents/MacOS/autoclip-desktop'
# 应看到 Backend started on port: XXXXX / Application startup complete
```
