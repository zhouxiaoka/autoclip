# 🚀 AutoClip Desktop 构建指南

桌面客户端只有**一条**打包路线：python-build-standalone（PBS）。它把便携 Python 运行时、
后端源码、静态 ffmpeg/ffprobe 全部打进 `.app`，用户机器**无需预装 Python 或 ffmpeg**。

> 历史上的 PyInstaller / prepare_resources 路线（以及对应的 6+ 个 CI 工作流）从未成功产出可用包，已全部移除。

## 本地构建（macOS Apple Silicon）

```bash
./scripts/build_macos_arm.sh
```

产物：
```
src-tauri/target/release/bundle/macos/
├── AutoClip Desktop.app                    # 应用包（~550M）
└── AutoClip Desktop_1.0.0_aarch64.dmg      # DMG 安装包（~260M）
```

脚本各步骤说明见 [`scripts/README.md`](scripts/README.md)。

### 前置依赖

| 工具 | 版本 | 说明 |
|------|------|------|
| Node.js | 18+ | 前端构建 |
| Rust | stable | 带 `aarch64-apple-darwin` target |
| cargo-tauri | 2.x | `cargo install tauri-cli` |

系统 **不需要** 预装 Python / ffmpeg —— 脚本自带便携版（首次构建会下载并缓存到 `build/`）。

## CI / 发布（GitHub Actions）

`.github/workflows/desktop-build.yml` 跑同一个 `build_macos_arm.sh`：

```bash
# 手动触发：仓库页面 → Actions → "Desktop Build (macOS arm64)" → Run workflow

# 或打 tag 触发，并自动把 DMG 挂到 GitHub Release：
git tag v1.0.0
git push origin v1.0.0
```

## 安装与首次运行

DMG 是 ad-hoc 签名（未做 Apple 公证），所以：

1. 双击 DMG，把 `AutoClip Desktop` 拖到 Applications
2. **首次打开右键点应用 → 选「打开」** 以绕过 Gatekeeper
3. 后端会自动启动并在 `~/Library/Application Support/AutoClip` 建数据目录

## 故障排除

命令行直接跑 app 看后端输出：
```bash
'/Applications/AutoClip Desktop.app/Contents/MacOS/autoclip-desktop'
```
应看到 `Backend started on port: XXXXX` 和 `Application startup complete`。

| 现象 | 排查 |
|------|------|
| `ModuleNotFoundError: No module named 'X'` | 把 `X` 加进 `requirements.txt` 重新构建（构建期的依赖检查应该已经拦下，正常不会发生）|
| 窗口黑屏 | 前端没挂载，看 WebView 控制台；通常是打包/资源问题 |
| 视频处理失败 | 确认 `Contents/Resources/resources/ffmpeg/{ffmpeg,ffprobe}` 存在且可执行 |
| 构建失败想重来 | `rm -rf src-tauri/target build/pbs-cache build/ffmpeg-cache` 后重跑（会重新下载）|

## 已知限制

- 仅 Apple Silicon (arm64)，暂无 Intel / Windows / Linux 包
- ad-hoc 签名、未公证，首次需右键打开
