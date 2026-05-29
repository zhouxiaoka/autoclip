# AutoClip Desktop — macOS 发布交接文档

> 状态：构建链路已跑通，DMG 已产出，待用户安装测试验证
> 日期：2026-05-29
> 分支：`main` (有 1 个未推的 commit + 未提交的本地改动)

---

## 一、当前进展概览

### 已完成
- ✅ PR #61 合并到 main（fix/problem-fixes-from-main 那一批改动）
- ✅ PR #66 合并到 main（仓库清理：删 .trae/、BUILD_SUMMARY.md、ffmpeg-unified 75MB binary 等）
- ✅ Issue #65 已开（CI desktop builds 全部失败，待后续跟进）
- ✅ Tauri dev 模式跑通（`cargo tauri dev` → 前端 :3000 + 后端动态端口 + 一切正常）
- ✅ macOS arm64 release 构建跑通：
  - **App**: `src-tauri/target/release/bundle/macos/AutoClip Desktop.app` (260MB)
  - **DMG**: `src-tauri/target/release/bundle/macos/AutoClip Desktop_1.0.0_aarch64.dmg` (140MB)

### 待办
- ⏳ **用户验证**：双击 DMG → 拖到 Applications → 右键打开（首次需绕过 Gatekeeper）→ 验证后端启动、前端可用
- ⏳ 写 RELEASE_NOTES、改 README 加安装说明
- ⏳ 打 git tag、上传 DMG 到 GitHub Release

### 已知问题（不阻塞首次发布）
- Windows / Linux / Universal macOS 构建工作流全部失败（issue #65）
- 仅 Apple Silicon (arm64)，未包 Intel mac
- Ad-hoc 签名，没有 Apple Developer 公证 → 用户首次必须右键打开

---

## 二、为什么之前一直黑屏？踩坑历程

### 根本原因
**项目里有两条「打包路线」并存，互相打架**：
1. **PyInstaller 路线** (`scripts/build_backend.py`)：把后端打包成单二进制
2. **prepare_resources 路线** (`scripts/prepare_resources.py`)：复制 backend 源码 + 单平台 ffmpeg

而 `tauri.conf.json` 的 `beforeBuildCommand` 同时调了两个，相互覆盖；`build_macos_arm.sh` 又用第三种方式（命令行 `pyinstaller --onefile` 直接打）。**没有一条路线是端到端调通过的**。

### 黑屏的真实原因链
1. 我先尝试 `build_macos_arm.sh` + `pyinstaller --onefile` → 缺 `celery.fixups` hidden import → 后端启动崩溃 → 前端等不到端口 → 黑屏
2. 然后试 `build_backend.py` 的 spec（带 `collect_submodules('celery')`）→ 输出是目录而不是单文件 → backend_manager.rs 的查找逻辑勉强支持，但加上 Tauri resource 声明的 extended attributes 又触发 `Permission denied (os error 13)`
3. 删掉 resource 声明手动复制 → app bundle 没签名 → "应用程序已损坏"
4. ad-hoc 签名后 → 后端依然崩溃（PyInstaller 包还是缺东西）→ 黑屏

每一步都在修上一个症状，没回到根因。**根因是 venv 是 miniconda 链接出来的、不可移植**，而 PyInstaller 路线对依赖的兼容性是个无底洞。

### 最终的解决方案
切到 **python-build-standalone (PBS)** 路线 —— 用 astral-sh 维护的官方便携 Python 替换 venv：

```
src-tauri/resources/
├── python/        # PBS Python 3.13.13 (含 pip 装好的所有依赖)
├── backend/       # 后端源码（rsync 复制，排除 cache/test/log）
└── ffmpeg/ffmpeg  # ffmpeg 二进制（用 ditto 复制避免 xattr）
```

`backend_manager.rs` 已经支持这个布局：先找 PyInstaller 二进制 → 没有就找 `venv/bin/python` → 没有就找 `python/bin/python3`（新加的 PBS 路径）→ 兜底走系统 python3。

---

## 三、关键改动（未提交）

### 1. `src-tauri/src/backend_manager.rs` (+9)
在 venv 查找之后新增 PBS Python 路径支持：
```rust
let pbs_python = backend_work_dir.join("python").join("bin").join("python3");
if pbs_python.exists() {
    return Ok(Self::python_launch(
        pbs_python.to_string_lossy().to_string(),
        backend_work_dir,
    ));
}
```

### 2. `src-tauri/tauri.conf.json`
- `devUrl` 改为 `http://localhost:3000`（Vite 默认端口）
- `beforeDevCommand` 改为 `cd ../frontend && npm run dev`
- `beforeBuildCommand` 清空（`build_macos_arm.sh` 全包了）
- `bundle.resources` 改为 `[]`（不通过 Tauri 声明，构建后手动注入避免 macOS 26 上 extended attributes 触发 Permission denied）

### 3. `scripts/build_macos_arm.sh` 全部重写
新流程：
1. 检查 node/python3/cargo/tauri
2. 下载 PBS Python 3.13.13 arm64 到 `build/pbs-cache/`（带文件大小校验，避免半截下载被复用）
3. 解压到 `src-tauri/resources/python/`
4. 用 PBS python 跑 `pip install -r requirements.txt`（PIP 镜像默认走清华源）
5. rsync 复制 `backend/` 到 `src-tauri/resources/backend/`（排除 cache/test/log）
6. ditto 复制 ffmpeg 到 `src-tauri/resources/ffmpeg/ffmpeg`
7. 前端 `npm ci && npm run build`
8. `cargo tauri build --bundles app`（只打 app，不让 Tauri 自己打 DMG，避免 bundle_dmg.sh 在 macOS 26 上挂）
9. 把 `python/`、`backend/`、`ffmpeg/` 复制进 `App/Contents/Resources/resources/`
10. `codesign --force --deep --sign -` ad-hoc 签名
11. `hdiutil create` 手动打 DMG

### 4. 网络问题处理
GitHub release 直连不稳，脚本里加了 ghproxy.com / mirror.ghproxy.com 镜像兜底。但今天测下来三个都不通，最终是用户开了代理之后直连成功。**未来重跑：要么保持代理开着，要么 PBS tarball 已经在 `build/pbs-cache/` 缓存好了（24MB）会跳过下载。**

---

## 四、下一步操作清单

### 立即（用户）
1. **双击 DMG 测试安装**：
   ```
   open 'src-tauri/target/release/bundle/macos/AutoClip Desktop_1.0.0_aarch64.dmg'
   ```
   拖 AutoClip Desktop 到 Applications
2. **右键打开**绕过 Gatekeeper 警告
3. 验证：窗口出现、显示前端 UI（不是黑屏）、上传视频能跑

### 测试通过后（开发者）
1. 提交本地改动并推上去：
   ```bash
   git add scripts/build_macos_arm.sh src-tauri/src/backend_manager.rs src-tauri/tauri.conf.json
   git commit -m "feat: portable macOS desktop build via python-build-standalone"
   git push
   ```
2. 写 `RELEASE_NOTES.md` 用户向（提到首次右键打开、仅 arm64 等）
3. 在 README 加 macOS 安装步骤
4. 创建 git tag、GitHub Release，上传 DMG

### 测试不通过（黑屏 / 启动失败）
按这个顺序排查：
1. **命令行直接跑 app 看输出**：
   ```bash
   '/Applications/AutoClip Desktop.app/Contents/MacOS/autoclip-desktop'
   ```
   应该看到 "后端服务启动中" → "Backend started on port: XXXXX"
2. 如果是 `Backend error: ModuleNotFoundError: No module named 'XXX'` → 把模块加到 `requirements.txt`，重跑构建
3. 如果是 `Backend error: ... Permission denied` → 检查 `App/Contents/Resources/resources/python/bin/python3` 是否可执行
4. 如果窗口出来但是黑屏 → 右键 inspect element 看 Console，可能是前端 `apiConfig.ts` 没收到后端端口事件

---

## 五、相关文件 / 链接

- PR #61: https://github.com/zhouxiaoka/autoclip/pull/61 (已合)
- PR #66: https://github.com/zhouxiaoka/autoclip/pull/66 (已合，仓库清理)
- Issue #65: https://github.com/zhouxiaoka/autoclip/issues/65 (CI desktop builds failing)
- Backup branch: `backup/local-main-2026-05-28` (本地 main 分叉前的 4 个旧 commit 备份)
- 本次会话之前的 plan: `/Users/zhoukk/.claude/plans/swift-giggling-wilkes.md` (基于 PyInstaller 路线，已被 PBS 路线替代)

## 六、未确定/风险点

1. **DMG 在用户机器上还没真正打开过** — 这是最大的未验证项
2. PBS Python 在 `App/Contents/Resources/resources/python/` 下，签名后是否还能被 macOS 安全策略接受需要测一下
3. 后端首次启动会创建 `~/Library/Application Support/AutoClip` 数据目录，权限正常下没问题
4. 没有 API 密钥时后端会 warn 但不崩溃，UI 会进设置页让用户填 — 是预期行为
5. CI 上这条路线还跑不通（issue #65），目前只是本地能打包
