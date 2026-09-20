# AutoClip 周更发版清单

> 节奏：**每周一版**，版本号只是周次编号（`1.3.0 → 1.4.0 → …`，周中热修用 `x.y.1`）。
> 目标不是「这版把什么做完」，而是「把 main 上已验证的改动每周发出去」。`HANDOFF.md` 里的 v1.3 / v1.4 分组只是优先级队列。
> 一次完整发版（打 tag 到 Release 出包）约 25 分钟，全部由 `desktop-build.yml` 自动完成；人要做的只有下面打勾的事。

## 周中（周一 – 周五）

- [ ] 只合并 **CI 全绿 + 有验证记录** 的 PR（PR 描述里要有「怎么验的」）。外部 PR 按 `HANDOFF.md` 第三节原则处理。
- [ ] 每个合入的 PR 都在 `CHANGELOG.md` 的 `## [未发布]` 里留一行（新增 / 修复 / 改进），写给用户看，不写内部实现。
- [ ] 每版至少带一条 **失败态改善** 或 **安装体验改善**（issue 区最缺的两类）。
- [ ] 周报（`scripts/weekly_digest.py`）里新出现的高频问题，当周能修就进这版，修不了写进 `HANDOFF.md` 待办。

## 切版（周六 / 周日，冻结后 24 小时内）

- [ ] main CI 绿（`gh run list --branch main --limit 1`）。
- [ ] `python scripts/bump_version.py --check` 四处版本号一致。
- [ ] 本地跑一遍 `pytest backend/tests`、`cd frontend && npm run lint && npm run typecheck && npm run build`、`python -m backend.eval`。
- [ ] 通读 `CHANGELOG.md [未发布]`：措辞面向用户、每条能对应到 issue 或 PR、没有泄露内部路径 / 密钥。
- [ ] `python scripts/bump_version.py X.Y.0 --commit`
      → 改 `tauri.conf.json` / `Cargo.toml` / `pyproject.toml` / `desktop_config.py`，把 `[未发布]` 滚成 `[X.Y.0] - 日期`。
- [ ] `git push origin main && git tag vX.Y.0 && git push origin vX.Y.0`
      → 触发 `desktop-build.yml`：macOS arm64 DMG + Windows x64 安装包并行构建，`release` job 用 `scripts/release_notes.py`
      从 CHANGELOG 抽该版本段落 + 平台说明生成 Release 正文并挂产物。
- [ ] 看 Actions 里 Desktop Build 全绿、Release 页两个文件都在（少一个 = 对应平台构建失败，看 run 日志）。

## 发版后（当天）

- [ ] **真机验证（人做，CI 覆盖不到）**：
  - Windows：干净机器装 `-setup.exe` → 能启动 → 设置页保存 provider → 跑通一条本地视频。**Windows 下载量是 DMG 的 3 倍，这一步不能省。**
  - macOS：右键打开 DMG 里的应用 → 同上。
- [ ] 更新置顶帖 #96 的版本号与「v1.x 修了什么」小节。
- [ ] 上一版 Release 的 `needs-info` / 已修复 issue：引导升级后关闭（模板回复见 `HANDOFF.md` 第三节）。
- [ ] `HANDOFF.md` 头部「更新：日期 · main@sha」与第四节勾选状态同步。

## 热修（周中发现影响面大的 bug）

- [ ] 单独分支 → PR → CI 绿 → 合入 → `bump_version.py X.Y.1 --commit` → 打 tag。不攒到周末。

## 明确不做

- 不在切版日合新功能；周六冻结后只合修 CI / 修 CHANGELOG 措辞的改动。
- 不手工编辑四处版本号（用脚本），不手工写 Release 正文（从 CHANGELOG 生成）。
- 不为了「凑一版大的」推迟发版。main 上有可发的就发。

## 相关文件

| 用途 | 位置 |
|---|---|
| 版本号统一 + CHANGELOG 滚动 | `scripts/bump_version.py` |
| Release 正文生成 | `scripts/release_notes.py`（被 `desktop-build.yml` 的 `release` job 调用） |
| 构建 workflow | `.github/workflows/desktop-build.yml`（tag `v*` 触发；`workflow_dispatch` 可只勾一个平台试构建） |
| 打包脚本 | `scripts/build_macos_arm.sh`、`scripts/build_windows_x64.sh`（说明见 `BUILD_GUIDE.md`、`scripts/README.md`） |
| 每周反馈周报 | `scripts/weekly_digest.py` |
| 当前状态 / 待办 | `HANDOFF.md` |
