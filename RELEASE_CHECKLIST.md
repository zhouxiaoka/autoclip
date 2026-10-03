# AutoClip 发版流程

> 2026-09-29 起所有发版都按这份执行。背景：9-22 到 9-27 六天发了 5 个版本，每版都没经过真机验收就直接推给全部用户，
> 热修又带出新问题。原则变成：**攒批、验收、先小范围、再推给所有人**。
> 先构建未打标签的内部安装包并完成双平台产品验收，通过后才创建公开标签。构建和 Release 正文由 `desktop-build.yml` 自动完成。2026-10-02 起按 [完整测试验收工作流](docs/TESTING_ACCEPTANCE.md) 留可校验证据；转正必须通过 Release Acceptance。勾选清单本身不代表验收通过。

## 0. 先给问题分级

发现问题时先定级，级别决定要不要马上发版。

| 级别 | 什么情况 | 怎么处理 |
|---|---|---|
| **S1 优先热修** | 装不上、打不开、升级失败、丢数据、安全漏洞、常见升级配置挡住核心入口或主流程集中失败 | 立即排查、止血并准备最小补丁（见第 4 节）；验收通过后发布，时限不能覆盖质量门槛 |
| **S2 进本周常规版** | 某个功能在特定条件下失败，有绕过办法 | 修好合进 main，周四随常规版发出 |
| **S3 排进计划** | 体验问题、文案、少见的边界情况 | 进 Roadmap，不单独发版 |

大多数用户反馈是 S2。把 S2 当 S1 处理，版本数就会失控。

## 1. 节奏与版本号

- **常规版每周最多一版**，建议周四切版。main 上没有可发的就不发，不为凑版本发版。
- **热修版只为 S1**，不受每周一版限制，但只包含修复那个问题的最小改动。
- 版本号：`X.Y.Z+1` 用于兼容性修复；1.5.1、1.5.2、1.5.3 保留为未通过验收的预发布。下一候选只在源码中准备编号；公开标签和正式发布须有会话授权。内部修复、重复构建不递增公开版本号。新功能单独进入后续常规版本；修复期间不合新功能。
- 同一个 tag 永远不重打。发现问题就用下一个补丁号。

## 2. 周中（合入 main）

- [ ] 只合并 **CI 全绿 + PR 描述写了「怎么验的」** 的 PR。外部 PR 按 `HANDOFF.md` 第三节原则处理。
- [ ] 每个合入的 PR 在 `CHANGELOG.md` 的 `## [未发布]` 里留一行，写给用户看，不写内部实现。
- [ ] 周报（`scripts/weekly_digest.py`）里的高频问题按第 0 节定级。

## 3. 常规版

### 3.1 切版前（周三）
- [ ] main CI 绿：`gh run list --branch main --limit 1`
- [ ] `python scripts/bump_version.py --check` 版本号一致
- [ ] 本地统一检查：`python scripts/quality_gate.py --report /absolute/local/evidence/quality.json`；记录提交和未提交改动
- [ ] 通读 `CHANGELOG.md [未发布]`：面向用户、能对应到 issue / PR、没有内部路径 / 密钥

### 3.2 标签前：内部构建与双平台产品验收
- [ ] 用 `bump_version.py X.Y.Z --commit` 准备未公开候选版本，但**不打 tag**；后续修复继续使用这个未公开编号
- [ ] 完整源码检查与 PR CI 通过；冻结完整提交 SHA，推送候选分支
- [ ] 在该分支运行 **Desktop Build**（`workflow_dispatch`），同时选 macOS / Windows。只生成 Actions artifacts，不创建 Release；已有公开版本号或已有标签会被拒绝
- [ ] 构建与安装/升级检查全绿；下载双平台包、签名和 `internal-desktop-provenance`，核对源码 SHA、run ID、全部包哈希
- [ ] 运行 `scripts/internal_acceptance.py init` 生成全 pending 的内部记录；逐项完成以下矩阵和每条修复，真实模型、费用、环境及限制按实际记录
- [ ] 有 pending / failed / skipped 场景或未解释的主流程失败时，继续在内部修复、重建、重新验收，**不得打 tag**

两个平台执行 [必测矩阵](docs/TESTING_ACCEPTANCE.md#4-最终安装包的必测矩阵)，包括下面基础项以及迁移、无字幕/视觉、失败恢复、保存/包装和隐私监控。记录内部包 SHA-256、完整提交、系统与运行时；脱敏结果进入 `docs/internal-builds/COMMIT/internal-acceptance.json` 与摘要，原始截图/日志留本地：

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
2. **Mac 上的 Windows 虚拟机或经授权的测试者（产品验收必须）**：Parallels Desktop / VMware Fusion + Windows 11 ARM（x64 安装包可在 ARM 版 Windows 上仿真运行），
   或 UTM（免费）。做一次快照当「干净机器」，每次发版还原快照后走上面四项。这是界面、WebView2、真实下载唯一能亲眼看的地方。
   仿真环境里性能和个别驱动行为和真机不同，记录时注明「ARM 虚拟机」。
3. **Pre-release 测试者（建议）**：经授权联系测试者，使用合法素材按必测矩阵记录结果和包哈希；一句“能用”不足以替代验收。

第 2 层没有证据时保持 **NO-GO**。延长观察期或写免责声明不能替代 Windows 产品验收；不转正、不推给全部用户。

### 3.3 内部验收通过后：打 tag → Pre-release
- [ ] 将人工审阅过的脱敏内部 manifest 和摘要提交到独立证据分支；保留被验收的源码提交，不能因提交报告而改变构建身份
- [ ] 运行 **Internal Acceptance**：源码完整 SHA、内部 Desktop Build run ID、已提交 manifest 路径；它核对双平台全部场景、修复、包哈希、时间及实名复核
- [ ] Internal Acceptance 成功且用户已授权本版本后，在**被验收的原提交**创建带注解标签：注解必须有独立一行 `Internal-Acceptance-Run: RUN_ID`；不要在验收后再 bump / 合入修改
- [ ] 推送标签。tag 的 Desktop Build 会核对上述不可变验收回执；缺失或提交不符时，阻断打包和 Pre-release
- [ ] exact tag CI、双平台构建、Windows 安装/升级和运行时全绿；Release 为 Pre-release，全部 DMG / EXE / wheel / ZIP / updater / 签名 / provenance 齐全
- [ ] 核对正式构建包哈希与内部包；最终包仍须按必测矩阵留证。发生重建/换包时重跑受影响场景，不能把内部包记录改时间后冒充最终包验收

此时应用内更新和官网还不推送该候选；只有手动下载 Pre-release 的人能装。标签后的核对与观察是第二道门槛，不能取代标签前的内部产品验收。

### 3.4 观察期（24 小时，热修版可缩短到 4 小时）
- [ ] Sentry：新版本的错误数 / 受影响用户数，和上一版同期对比，没有新的高频错误
- [ ] 应用内反馈（`from-app` issue）没有集中出现同一个问题
- [ ] 手动下载 Pre-release 的用户没有报 S1
- [ ] 两个平台都有实际设备及完成流程；去重、版本、样本量、观察时间和限制写入摘要，零事件不能填“没有问题”

### 3.5 转正：推给所有人
- [ ] Actions → **Release Acceptance** → tag、该 tag 的 build run ID、已提交的脱敏验收 manifest 路径；等待成功
- [ ] Actions → **Promote / Halt Release** → `tag=vX.Y.Z`，`action=promote`，`acceptance_run_id=上一步成功 run ID`
  → 该版本变成 latest，应用内更新开始推送，官网同步
- [ ] 更新置顶帖 #96 的版本号和「这版修了什么」
- [ ] 本版修复的 issue：回复「已在 vX.Y.Z 修复，请升级」后关闭；重复的 issue 合并到一个跟踪 issue 再一起关
- [ ] `HANDOFF.md` 头部状态同步

## 4. 热修（S1）

1. 从**出问题的 tag** 拉分支，不从 main 拉，避免捎带未验证的改动：
   ```bash
   git switch -c codex/hotfix-1.5.1 v1.5.0
   ```
2. 只放修复这一个问题的最小改动，加一条能复现这个问题的回归测试。
3. 在 hotfix 分支 review；源码检查和 CI 绿后准备未打标签的候选，先按 3.2 完成内部双平台验收和 Internal Acceptance，再按 3.3 在被验收提交打标签。把必需的质量/发布门槛带入，不混入其他运行时整理。
4. 同一组修复 **cherry-pick 或合并回 main**，别让下个常规版把问题带回来。
5. 走 3.3 双平台基线与本次回归 + 3.4 观察（可缩短到 4 小时）+ 3.5 Acceptance 与转正；hotfix 不跳过关键场景。

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
- 不在内部产品验收不过时打 tag，也不在最终包验收不过时转正；内部发现问题继续修同一个未公开候选，不靠递增版本号推进。
- 不重打同名 tag，不手工改四处版本号（用脚本），不手工写 Release 正文（从 CHANGELOG 生成）。
- 不直接用 `gh release edit` 或 GitHub 网页按钮绕过 Acceptance；promote 会重新检查当前包哈希与构建，旧记录不能放行新包。
- 热修分支不合新功能；切版日不合新功能。

## 相关文件

| 用途 | 位置 |
|---|---|
| 版本号统一 + CHANGELOG 滚动 | `scripts/bump_version.py` |
| 源码质量统一入口 | `scripts/quality_gate.py`、`.github/workflows/ci.yml` |
| 完整场景、证据与责任 | `docs/TESTING_ACCEPTANCE.md`、`AGENTS.md` |
| 验收校验 + Actions 证据 | `scripts/release_acceptance.py`、`.github/workflows/release-acceptance.yml` |
| Release 正文生成 | `scripts/release_notes.py`（`desktop-build.yml` 的 `release` job 调用） |
| 标签前产品验收 | `scripts/internal_acceptance.py`、`.github/workflows/internal-acceptance.yml`；成功回执绑定提交和内部包哈希 |
| 构建并发 Pre-release | `.github/workflows/desktop-build.yml`（tag `v*` 触发；`workflow_dispatch` 可只勾一个平台试构建，不会发布） |
| 转正 / 撤回 | `.github/workflows/promote-release.yml` |
| 应用内更新地址 | `src-tauri/tauri.conf.json` → `plugins.updater.endpoints`（`releases/latest/download/latest.json`） |
| 打包脚本 | `scripts/build_macos_arm.sh`、`scripts/build_windows_x64.sh` |
| 每周反馈周报 | `scripts/weekly_digest.py` |
| 当前状态 / 待办 | `HANDOFF.md` |
