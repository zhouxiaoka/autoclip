# scripts/

构建与运维脚本。桌面客户端只有**一条**打包路线（python-build-standalone，下称 PBS），
历史上的 PyInstaller / prepare_resources 路线及其脚本已全部移除。

## 脚本清单

| 脚本 | 用途 |
|------|------|
| `build_macos_arm.sh` | 桌面打包（macOS Apple Silicon）。端到端产出 `.app` + `.dmg`。 |
| `build_windows_x64.sh` | 桌面打包（Windows x64）。在 Git Bash 里跑，产出 NSIS 安装包 `*-setup.exe`。 |
| `lib/desktop_build_common.sh` | 上面两个脚本共用的平台无关步骤（便携 Python 下载、pip、后端拷贝、依赖检查、前端构建）。不直接执行。 |
| `verify_desktop.sh` | 后端冒烟测试：`cargo check` + 起后端，校验 `/health` 与 `/api/v1/video-categories`。被 `nightly-desktop-smoke.yml` 调用。 |
| `monitor_whisper.py` | 运行期 Whisper 任务监控，被根目录 `start_autoclip.sh` / `check_whisper_status.sh` 调用。 |

## 打包桌面客户端

### macOS arm64

```bash
./scripts/build_macos_arm.sh
```

产物：
```
src-tauri/target/release/bundle/macos/
├── AutoClip Desktop.app
└── AutoClip Desktop_<version>_aarch64.dmg
```

### Windows x64

在 **Git Bash** 中执行（需要 Node.js、Rust MSVC 工具链、Visual Studio Build Tools C++ 组件、cargo-tauri）：

```bash
bash scripts/build_windows_x64.sh
```

产物：
```
src-tauri/target/release/bundle/nsis/
└── AutoClip Desktop_<version>_x64-setup.exe
```

Windows 与 macOS 的唯一结构差异：macOS 是构建后把 `python/ backend/ ffmpeg/` 注入 `.app`
再签名；Windows 的安装包没法事后注入，所以资源在 `src-tauri/tauri.windows.conf.json`
的 `bundle.resources` 里声明，由 Tauri 打进 NSIS。这个文件只在 Windows 上构建时才会被
Tauri 合并，不影响 macOS。

### 两个脚本共同做了什么（`lib/desktop_build_common.sh`）

1. 下载便携 Python 运行时（python-build-standalone，缓存在 `build/pbs-cache/`；国内镜像优先，自动回退）
2. 用便携 Python 安装 `requirements.txt` 的全部依赖
3. 拷贝后端源码到 `src-tauri/resources/backend/`（排除缓存 / tests / 运行数据；用 Python `shutil` 实现，Windows 没有 rsync）
4. **依赖完整性检查**：AST 扫描后端所有第三方 import，缺任何一个就让构建失败
   （防止"开发机能跑、打包就 500"）
5. 构建前端（`npm ci && npm run build`）

平台脚本各自负责：静态 ffmpeg/ffprobe（macOS: osxexperts arm64 静态包；Windows: BtbN win64 gpl 包）、
`cargo tauri build`、打包与签名。

### 运行时怎么找到这些资源（`src-tauri/src/backend_manager.rs`）

- Python：`resources/python/bin/python3`（unix）或 `resources/python/python.exe`（Windows）
- ffmpeg：`resources/ffmpeg/ffmpeg[.exe]`，通过 `AUTOCLIP_FFMPEG_PATH` / `AUTOCLIP_FFPROBE_PATH` 传给后端
- 数据目录：Rust 侧设置 `AUTOCLIP_APP_DIR=<平台数据目录>/AutoClip`
  （macOS `~/Library/Application Support/AutoClip`，Windows `%APPDATA%\AutoClip`）
- Windows 额外：`PYTHONUTF8=1`（后端 stdout 有 emoji，否则 GBK 控制台直接 UnicodeEncodeError）、
  `CREATE_NO_WINDOW`（不弹黑框）

### 前置依赖

- Node.js 18+、Rust、cargo-tauri (`cargo install tauri-cli`)
- macOS：`aarch64-apple-darwin` target；Windows：MSVC 工具链 + VS Build Tools
- 系统 **不需要** 预装 Python / ffmpeg —— 脚本会自带便携版

### 环境变量

- `PIP_INDEX_URL`：pip 源，默认清华镜像；CI 里设为 `https://pypi.org/simple`
- `PBS_VERSION` / `PBS_PYTHON_VERSION`：覆盖便携 Python 版本（默认见 `lib/desktop_build_common.sh`）

## CI

`.github/workflows/desktop-build.yml`：
- `workflow_dispatch`：可勾选只构建 macOS 或只构建 Windows
- `v*` tag：两个平台并行构建，`release` job 汇总产物挂到 GitHub Release（任一平台失败不阻塞另一平台上传）

## 开发模式（不打包）

直接用 Tauri 开发模式，热重载：
```bash
cd src-tauri && cargo tauri dev
```
（前端 :3000 + 后端动态端口，由 `backend_manager.rs` 拉起）
