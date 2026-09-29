# AutoClip 发版流程

> 2026-09-29 起所有发版都按这份执行。背景：9-22 到 9-27 六天发了 5 个版本，每版都没经过真机验收就直接推给全部用户，
> 热修又带出新问题。原则变成：**攒批、验收、先小范围、再推给所有人**。
> 构建和 Release 正文由 `desktop-build.yml` 自动完成；下面打勾的是人要做的事。

## 0. 先给问题分级

发现问题时先定级，级别决定要不要马上发版。

| 级别 | 什么情况 | 怎么处理 |
|---|---|---|
| **S1 立即热修** | 装不上、打不开、升级失败、丢数据、安全漏洞、主流程对某个平台 100% 失败 | 24 小时内发补丁版（见第 4 节） |
| **S2 进本周常规版** | 某个功能在特定条件下失败，有绕过办法 | 修好合进 main，周四随常规版发出 |
| **S3 排进计划** | 体验问题、文案、少见的边界情况 | 进 Roadmap，不单独发版 |

大多数用户反馈是 S2。把 S2 当 S1 处理，版本数就会失控。

## 1. 节奏与版本号

- **常规版每周最多一版**，建议周四切版。main 上没有可发的就不发，不为凑版本发版。
- **热修版只为 S1**，不受每周一版限制，但只包含修复那个问题的最小改动。
- 版本号：`1.4.x` 只有修复；新功能进 `1.5.0`。修复期间不合新功能。
- 同一个 tag 永远不重打。发现问题就用下一个补丁号。

## 2. 周中（合入 main）

- [ ] 只合并 **CI 全绿 + PR 描述写了「怎么验的」** 的 PR。外部 PR 按 `HANDOFF.md` 第三节原则处理。
- [ ] 每个合入的 PR 在 `CHANGELOG.md` 的 `## [未发布]` 里留一行，写给用户看，不写内部实现。
- [ ] 周报（`scripts/weekly_digest.py`）里的高频问题按第 0 节定级。

## 3. 常规版

### 3.1 切版前（周三）
- [ ] main CI 绿：`gh run list --branch main --limit 1`
- [ ] `python scripts/bump_version.py --check` 版本号一致
- [ ] 本地：`pytest backend/tests`、`cd frontend && npm run lint && npm run typecheck && npm test`、`python -m backend.eval`
- [ ] 通读 `CHANGELOG.md [未发布]`：面向用户、能对应到 issue / PR、没有内部路径 / 密钥

### 3.2 打 tag → 自动出 Pre-release
- [ ] `python scripts/bump_version.py X.Y.Z --commit`
- [ ] `git push origin main && git tag vX.Y.Z && git push origin vX.Y.Z`
- [ ] Desktop Build 全绿，Release 页是 **Pre-release**，DMG / `setup.exe` / `latest.json` 都在

此时**应用内更新拿不到这个版本**（它读的是 `releases/latest/download/latest.json`，Pre-release 不算 latest），官网也不会更新。只有手动下载的人能装。

### 3.3 真机冒烟（发给所有人前必须做，每台约 10 分钟）
两个平台各一次，结果写进 `docs/RELEASE_X_Y.md`（版本、机器、系统版本、结果、截图或日志）：

- [ ] **Windows**（下载量约 80%，不能省）
  - [ ] 从上一个正式版**覆盖升级**：安装过程不报文件占用，启动后设置和项目都在
  - [ ] 干净安装：能启动，设置页保存模型
  - [ ] 本地视频导入 → 出片 → 预览 → 导出
  - [ ] YouTube 或 B 站链接导入 → 进度在动 → 出片
- [ ] **macOS**：同上四项（首次打开仍需右键打开，直到完成公证）
- [ ] 本版 CHANGELOG 里每条修复，至少在一台机器上亲手确认过

#### 没有 Windows 真机时（当前情况）

Windows 验收分三层，前两层必须过，第三层补上界面和真实网络：

1. **CI 自动冒烟（必须，tag 构建自动跑，不过就不会出 Release）**：`desktop-build.yml` 的 `smoke-windows-x64` 在干净的 windows-latest 上
   装上一个正式版 → 模拟残留后端占住 `_asyncio.pyd` → 静默覆盖安装本次构建 → 用安装目录自带的 Python 跑 `scripts/verify_windows_install.py`
   （内置 ffmpeg 出片、中文文件名、yt-dlp 拿到 ffmpeg、桌面后端启动、来源守卫）。覆盖了近两周 Windows 反馈里的主要故障点，
   但**看不到界面**，也不下载真实链接。
2. **Mac 上的 Windows 虚拟机（必须，约 15 分钟）**：Parallels Desktop / VMware Fusion + Windows 11 ARM（x64 安装包可在 ARM 版 Windows 上仿真运行），
   或 UTM（免费）。做一次快照当「干净机器」，每次发版还原快照后走上面四项。这是界面、WebView2、真实下载唯一能亲眼看的地方。
   仿真环境里性能和个别驱动行为和真机不同，记录时注明「ARM 虚拟机」。
3. **Pre-release 测试者（建议）**：在 Discussions 里招 3–5 位 Windows 用户（优先找报过 #163 #173 #183 这类问题的人），
   Pre-release 发出后 @ 他们装上试一条自己的视频，在观察期内回帖。有人确认通过再转正。

第 2 层做不了的那一次发版，要在 Release 正文顶部写明「本版 Windows 仅经 CI 冒烟验收，未经界面验收」，并把观察期延长到 48 小时。

### 3.4 观察期（24 小时，热修版可缩短到 4 小时）
- [ ] Sentry：新版本的错误数 / 受影响用户数，和上一版同期对比，没有新的高频错误
- [ ] 应用内反馈（`from-app` issue）没有集中出现同一个问题
- [ ] 手动下载 Pre-release 的用户没有报 S1

### 3.5 转正：推给所有人
- [ ] Actions → **Promote / Halt Release** → `tag=vX.Y.Z`，`action=promote`
  → 该版本变成 latest，应用内更新开始推送，官网同步
- [ ] 更新置顶帖 #96 的版本号和「这版修了什么」
- [ ] 本版修复的 issue：回复「已在 vX.Y.Z 修复，请升级」后关闭；重复的 issue 合并到一个跟踪 issue 再一起关
- [ ] `HANDOFF.md` 头部状态同步

## 4. 热修（S1）

1. 从**出问题的 tag** 拉分支，不从 main 拉，避免捎带未验证的改动：
   ```bash
   git switch -c hotfix/1.4.2 v1.4.1
   ```
2. 只放修复这一个问题的最小改动，加一条能复现这个问题的回归测试。
3. PR 进 `hotfix/1.4.2`，CI 绿后 `bump_version.py 1.4.2 --commit`，在 hotfix 分支上打 tag。
4. 同一组修复 **cherry-pick 或合并回 main**，别让下个常规版把问题带回来。
5. 走 3.3 冒烟（只测受影响的平台和流程）+ 3.4 观察（可缩短到 4 小时）+ 3.5 转正。

## 5. 坏版本已经推给所有人了

按顺序做：

1. **止血，先让新用户别再升级**：Actions → **Promote / Halt Release** → `tag=坏版本`，`action=halt`，`fallback_tag=上一个好版本`。
   坏版本退回 Pre-release，好版本重新成为 latest，应用内更新和官网都退回去。
2. **告知**：在坏版本的 Release 正文顶部和 #96 写明「vX.Y.Z 有已知问题：…，请暂缓升级 / 已升级的请等待 vX.Y.Z+1」。
3. **往前修，不回滚**：Tauri 更新器不会给已升级的用户降级，只能按第 4 节发补丁版解决他们的问题。
4. **收口反馈**：同一问题的 issue 合并到一个跟踪 issue，补丁版转正后统一回复并关闭。
5. **复盘一行**：在 CHANGELOG 或 `docs/RELEASE_X_Y.md` 里写「为什么这次没被拦住」，并补上对应的测试或冒烟检查项，同类问题不再从同一个地方漏出去。

## 6. 明确不做

- 不跳过 Pre-release 直接推给所有人，热修也不跳过。
- 不在冒烟不过的情况下转正；冒烟不过就修，修完用新补丁号重新打 tag。
- 不重打同名 tag，不手工改四处版本号（用脚本），不手工写 Release 正文（从 CHANGELOG 生成）。
- 热修分支不合新功能；切版日不合新功能。

## 相关文件

| 用途 | 位置 |
|---|---|
| 版本号统一 + CHANGELOG 滚动 | `scripts/bump_version.py` |
| Release 正文生成 | `scripts/release_notes.py`（`desktop-build.yml` 的 `release` job 调用） |
| 构建并发 Pre-release | `.github/workflows/desktop-build.yml`（tag `v*` 触发；`workflow_dispatch` 可只勾一个平台试构建，不会发布） |
| 转正 / 撤回 | `.github/workflows/promote-release.yml` |
| 应用内更新地址 | `src-tauri/tauri.conf.json` → `plugins.updater.endpoints`（`releases/latest/download/latest.json`） |
| 打包脚本 | `scripts/build_macos_arm.sh`、`scripts/build_windows_x64.sh` |
| 每周反馈周报 | `scripts/weekly_digest.py` |
| 当前状态 / 待办 | `HANDOFF.md` |
