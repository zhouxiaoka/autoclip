# 官网发布信息审计（2026-11-06）

对照对象：GitHub Latest **v1.5.8**（2026-11-02 发布，`prerelease=false`，`draft=false`）。v1.5.9 当时没有 Release，不能写成当前正式版。线上页面取自 `https://zhouxiaoka.github.io/autoclip_intro/`，`last-modified: Thu, 05 Nov 2026 10:52:21 GMT`。源码是 `zhouxiaoka/autoclip_intro` 的 `main` @ `3f9280f`（`chore: sync download links to AutoClip v1.5.8`）。Pages 从该仓库 `main` 根目录发布，没有自定义域名。

## 根因

每日 `sync-release.yml` 在 11 月 3–5 日都成功，但脚本用首页**第一条下载链接**当作「当前版本」。下载链接已经是 1.5.8 之后，它认为没有变化，于是不再改介绍、发布教程和 `llms.txt`。这些句子从 1.5.0 起就在同步范围之外。`/releases/latest` 本身不会返回预发布；缺口是槽位不全，不是把 RC 当成了正式版。

## 过时项

| 页面 | 当时内容 | 应为 | 证据 |
| --- | --- | --- | --- |
| [首页](https://zhouxiaoka.github.io/autoclip_intro/) noscript 中文介绍 | 当前版本 1.5.0 | 当前版本 1.5.8 | 线上 HTML；同页下载链接与 JSON-LD `softwareVersion` 已是 1.5.8 |
| [首页](https://zhouxiaoka.github.io/autoclip_intro/) / [英文首页](https://zhouxiaoka.github.io/autoclip_intro/en/) noscript 英文介绍 | v1.5.0 for Windows and Apple Silicon | v1.5.8 | 同上。英文页由首页生成 |
| [发布教程](https://zhouxiaoka.github.io/autoclip_intro/guides/publish/) 八语 `hero.ver` | 当前正式版现为 v1.5.0 | v1.5.8；「自 v1.3.2 起」保留 | 线上八语字符串 |
| [llms.txt](https://zhouxiaoka.github.io/autoclip_intro/llms.txt) | Version 1.5.0 ships；中文「1.5.0 同时提供」 | 1.5.8。首次出片案例仍写 official 1.5.0 | 源码 `main` |
| [llms-full.txt](https://zhouxiaoka.github.io/autoclip_intro/llms-full.txt) | Current product (1.5.0)；安装包约 270 MB / 196 MB；Updated 2026-10-02 | 1.5.8；macOS 348 MB、Windows 195 MB；Updated 2026-11-02。1.5.0 首次出片案例和「1.5 pipeline」保留 | v1.5.8 资产字节数按 1024² 四舍五入 |
| 首页 FAQ / 首次打开 | 只写 macOS 右键打开 | v1.5.8 安装说明：macOS 15 及以上走「系统设置 → 隐私与安全性 → 仍要打开」，较旧系统右键打开。安装包仍未公证、未签名 | tag `v1.5.8` 的 `docs/USER_INSTALLATION_GUIDE.md` 与 `docs/FAQ.md` |
| 首页开发者「7 个工具」 | 固定成 7 个 MCP 工具 | 去掉具体个数。v1.5.8 的 `docs/CLI_AND_MCP.md` 已列出更多工具，包含 `start_quick_output` | 不改写成另一个未逐项点数的数字 |
| [项目介绍文档.md](https://zhouxiaoka.github.io/autoclip_intro/%E9%A1%B9%E7%9B%AE%E4%BB%8B%E7%BB%8D%E6%96%87%E6%A1%A3.md) | 早期 Web 架构：8GB 内存、B 站自动上传、移动端计划 | 停用说明，改指向官网和 Releases | 该文件在 Pages 根目录，HTTP 200，`content-type: text/markdown` |
| 官网 README | 仍写飞书反馈表，并称通知步骤还在 PR #105 | 首页反馈是 GitHub Issues / Discussions；通知在 `promote-release.yml` | 页面源码无飞书链接；2026-10-24 有一次 `autoclip-release` dispatch |

下载区、`hero.note`、JSON-LD `softwareVersion` 和安装包体积在线上已经是 1.5.8 / 348 MB / 195 MB，这次没有把它们改回 1.5.0。

## 明确保留

- `cases/autoclip-first-run/` 与各页「AutoClip 1.5.0」案例链：那是 2026-10-02 的首次出片记录。
- 发布教程「自 v1.3.2 起」。
- 游戏页眉标「使用场景 · 1.5.0」和 `content.js` 里的「游戏视觉 · 1.4.0」。这是该页的能力版本，不是当前下载版本；没有把 1.5.7 的杂志风 / 街头快剪写成新的首页承诺。
- 系统要求仍是 macOS 13+ Apple Silicon、Windows 10/11 x64，Intel Mac 无桌面安装包。v1.5.8 文档如此。
- 速度与费用数字仍标注 2026-10-01 的实测，不改写成 1.5.8 的新测量。

## 同步机制

官网 `data/release.json` 是提交进仓库的正式版快照。`scripts/sync_release.py` 按固定槽位改写当前版本，不靠「把旧版本号全局替换成新版本号」。

触发：

1. `promote-release.yml` 转正或撤回后，若配置了 `WEBSITE_DISPATCH_TOKEN`，发送 `autoclip-release`。目标若仍是 draft / prerelease，只警告、不发送。
2. 官网每天 03:17 UTC 读取 GitHub Latest。
3. 手动运行 Sync release info。留空取 Latest；填写的 tag 必须已是正式版。

失败：脚本以非 0 退出。workflow 不提交、不请求 Pages。线上继续显示上一份成功同步的正式版。次日 cron 或手动运行可以再试。缺少 macOS `.dmg` 或 Windows `.exe` 时同样不改页面。

首页日文到法文仍引用英文文案，这是现有目录里的显式回退，不是这次漏译。发布教程八语各自有「当前正式版」槽位。

## 尚未覆盖

- 首页模板区没有写 1.5.7 起的杂志风、街头快剪、新闻和电影风格。页面没有说只有两种包装，所以没有补营销文案。
- 游戏场景页没有按 1.5.8 重新验收，版本眉标保持原样。
- `install_publish_guide.py` 仍会在 `WITH_PUBLISH_GUIDE=1` 时用旧模板覆盖发布教程。默认安装不再这么做。
- 本仓库合入不会自动改 Pages。官网仓库的对应分支合入 `main` 后，Pages 才会更新。
