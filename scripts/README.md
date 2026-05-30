# scripts/

构建与运维脚本。桌面客户端只有**一条**打包路线（python-build-standalone，下称 PBS），
历史上的 PyInstaller / prepare_resources 路线及其脚本已全部移除。

## 脚本清单

| 脚本 | 用途 |
|------|------|
| `build_macos_arm.sh` | **唯一的桌面打包脚本**（macOS Apple Silicon）。端到端产出 `.app` + `.dmg`。 |
| `verify_desktop.sh` | 后端冒烟测试：`cargo check` + 起后端，校验 `/health` 与 `/api/v1/video-categories`。被 `nightly-desktop-smoke.yml` 调用。 |
| `monitor_whisper.py` | 运行期 Whisper 任务监控，被根目录 `start_autoclip.sh` / `check_whisper_status.sh` 调用。 |

## 打包桌面客户端（macOS arm64）

```bash
./scripts/build_macos_arm.sh
```

产物：
```
src-tauri/target/release/bundle/macos/
├── AutoClip Desktop.app
└── AutoClip Desktop_1.0.0_aarch64.dmg
```

### 这个脚本做了什么

1. 下载便携 Python 运行时（python-build-standalone，缓存在 `build/pbs-cache/`）
2. 用便携 Python 安装 `requirements.txt` 的全部依赖
3. **依赖完整性检查**：AST 扫描后端所有第三方 import，缺任何一个就让构建失败
   （防止"开发机能跑、打包就 500"）
4. rsync 拷贝后端源码到 `src-tauri/resources/backend/`
5. 下载**静态** ffmpeg + ffprobe（arm64，自包含，零 homebrew 依赖，缓存在 `build/ffmpeg-cache/`）
6. 构建前端（`npm ci && npm run build`）
7. `cargo tauri build --bundles app`
8. 把 `python/`、`backend/`、`ffmpeg/` 注入 `.app/Contents/Resources/resources/`
9. ad-hoc 签名 + `hdiutil` 手动打 DMG

### 前置依赖

- Node.js 18+、Rust（带 `aarch64-apple-darwin` target）、cargo-tauri (`cargo install tauri-cli`)
- 系统 **不需要** 预装 Python / ffmpeg —— 脚本会自带便携版

### 环境变量

- `PIP_INDEX_URL`：pip 源，默认清华镜像；CI 里设为 `https://pypi.org/simple`

## CI

`.github/workflows/desktop-build.yml` 在 `workflow_dispatch` 和 `v*` tag 上跑同一个
`build_macos_arm.sh`，打 tag 时把 DMG 挂到 GitHub Release。

> 当前仅 macOS arm64。PBS 与静态 ffmpeg 对 Intel/Windows/Linux 都有对应版本，
> 后续把 runner、下载 URL、tauri target 参数化即可泛化。

## 开发模式（不打包）

直接用 Tauri 开发模式，热重载：
```bash
cd src-tauri && cargo tauri dev
```
（前端 :3000 + 后端动态端口，由 `backend_manager.rs` 拉起）
