# 为什么发完版总带着 bug，以及怎么拦住

`RELEASE_CHECKLIST.md` 从 2026-09-29 就写了：先 Pre-release，双平台真机冒烟，观察期过了再转正。
1.4.0 和 1.5.0 都没有按它做完：Windows 没有界面验收，观察期没走完，就变成了 latest。
后面来的反馈不是「流程不够完整」，是**用户拿到的安装包、用户会走的路，没有被当成验收对象**。

pytest 1100+ 通过、源码在 Mac 上能出片、CI 静默安装能跑 ffmpeg，都代替不了：

> 一个陌生人下载正式安装包，第一次用自己的素材，能不能保存出一条成片，失败时知不知道下一步做什么。

## 1.5.0 实际发生了什么

2026-10-01 按「尽快正式发布」把 Pre-release 转成 latest。`docs/RELEASE_1_5.md` 自己写了：Windows 没有人工界面验收，观察期没走完。CI 冒烟用的是本地视频 + SRT + 协议 fixture。

转正后不到一天，三路信号对上同一条缝：

| 来源 | 信号 | 说明 |
|---|---|---|
| Sentry `PYTHON-FASTAPI-2C` | `ValidationError` in `migrate_legacy`，release `1.5.0`，约 1 万次 / 3 小时 | `GET /settings/ai-models` 读 1.4 的 `cover.json` 时整页 500。设置页英文文案就是 `Loading…` |
| GitHub #257 / #258 | Windows x64 1.5.0，来源 `settings`，from-app | 「AI models … just Loading…」 |
| PostHog（桌面 `app_version=1.5.0`） | 10-01：59 人打开、551 次拉设置、8 次失败、55 次出片、21 次保存；10-02 上午：15 人打开、175 次拉设置、7 次失败 | 能打开的人里只有一部分走完设置；失败次数被前端包一层，远小于 Sentry 的 500 重试 |
| Sentry `PYTHON-FASTAPI-1T` / `26` | `whisper_not_installed`、`subtitle_setup`，1.5.0 生产 | 无字幕路径仍在炸。#247 / #249 是 1.4 / 1.3.5 的同一句 Whisper 失败 |
| Sentry `AUTOCLIP-FRONTEND-7/8/9/A` | `useAppUpdate` / `FirstRunSetup` | **开发环境、1.4.0、vite react-refresh**，不是这次正式包。观察期不要被开发噪音带偏 |

1.5.0 漏出去的不是新功能，是 **G1（设置页能打开）** 和 **G3（无字幕）**。同事在发版前已经抓住过「wheel 漏 ONNX / 字体名不对 / YouTube 长视频挂起」——那些是冷安装和真实素材，正好说明：**人眼看过的路径能拦住，没看过的路径会在转正后几小时变成 issue。**

`docs/acceptance/v1.5.0.json` 按当时真实情况填写：`windows_ui=false`，`no_subtitle_path=false`，`observation_hours=0`。门禁脚本必须拒绝这份记录。

## 根因（每次漏出去的都是这三类）

1. **验的是源码，发的是安装包。** 1.5.0 漏打包人物检测 ONNX、中文字体家族名不匹配，都是「开发目录能跑、冷安装不行」。
2. **验的是有字幕的快乐路径。** 应用内反馈反复是本地 Whisper「模型已下载仍失败」。安装冒烟默认带着 SRT，这条路根本没走。
3. **Windows 占安装包下载约八成，却用 Mac + CI 无界面冒烟代替。** 没有窗口、没有设置页、没有 SmartScreen，转正后才第一次见到。1.5.0 的 Loading 卡死就是这条。

## 四层测试

| 层 | 拦什么 | 现在谁跑 | 过了才能做什么 |
|---|---|---|---|
| L0 回归 | 逻辑、契约、打包清单、**脏的 1.4 配置不能 500** | 每个 PR 的 CI | 合入 main |
| L1 安装包自动冒烟 | 覆盖升级、内置运行时、有字幕出片、wheel 冷安装 | tag 构建的 `smoke-windows-x64` | 出 Pre-release |
| L2 真机黄金路径 | 人眼看见的窗口、设置、无字幕、真实链接 | 你或虚拟机，写进 `docs/acceptance/vX.Y.Z.json` | 才允许转正 |
| L3 观察期 | 新版本 Sentry / PostHog / `from-app` 有没有新的 S1 | Pre-release 挂着，应用内更新还拿不到 | `promote-release.yml` |

L0 过了只证明「没把已有测试写坏」。L1 过了只证明「安装器能写盘、后端能起、带着 SRT 能出片」。对用户负责的是 L2 + L3。

观察期最少看这三个数字，再决定转正：

1. Sentry：该 `release` 有没有新的高频 issue（1.5.0 的 `PYTHON-FASTAPI-2C` 就是）
2. PostHog：`model_settings_load_finished` 失败、`processing_failed`、`studio_generation_finished` / `studio_download_saved`
3. GitHub：`from-app` 是否集中同一句话

开发环境（`environment=development`、带 `/@react-refresh`）的 Sentry 不当作正式包证据。

## 四条黄金路径（转正前必须亲手过）

对象必须是 **Pre-release 安装包**，不是 `npm run dev`，不是仓库里的 `python -m backend`。

| 编号 | 路径 | 怎样算过 | 不过就不要转正 |
|---|---|---|---|
| G1 | 干净安装 → 首次打开 → **设置页 AI 模型能从 Loading 变成可编辑** → 连接 AI → 保存 | 窗口起来；设置不是转圈；Key 测通后才能导入；失败有下一步 | 装不上 / 打不开 / 设置一直 Loading / 保存了假连上。1.5.0 #257 #258 |
| G2 | 本地视频 **带字幕** → 选一个平台 → 保存成片 | 能预览，文件能播，封面和文案在 | 有字幕还出不来，主流程坏了 |
| G3 | 本地视频 **无字幕** → 转写 → 出片或可执行的失败 | Whisper / SenseVoice / 云端转写任一走通；失败必须能「去转写设置 / 换 SRT」，不能只说处理失败 | 这是目前最多的 from-app 反馈。#247 #249，Sentry `whisper_not_installed` |
| G4 | YouTube 或 B 站链接（作者字幕）→ 进度在动 → 出片 | 用内置 ffmpeg 合并，进度不是假的 | Windows 链接导入反复在这里炸 |

Windows 和 macOS 各走一遍 G1–G4。没有 Windows 真机就用虚拟机，见 `RELEASE_CHECKLIST.md` 3.3；**做不了就不转正**，不要再写一句「仅经 CI 冒烟」然后推给所有人。

本版 CHANGELOG 里每一条用户可见的修复，至少在一台机器的安装包上确认过。

## 转正门禁（机器会拦）

`Promote / Halt Release` 在 `action=promote` 时会跑 `scripts/check_release_gate.py`。常规版必须同时满足：

- Windows 界面冒烟通过（含 G1 设置页）
- macOS 界面冒烟通过
- G2（有字幕）通过
- G3（无字幕）通过
- 观察满 24 小时

热修可以只验受影响平台，观察可以缩短到 4 小时，但仍要 G2。脚本**没有「尽快发布」开关**。要强行转正只能绕开这个 workflow，那是明确选择，不是默认路径。

验收记录用 `docs/acceptance/TEMPLATE.json` 复制成 `docs/acceptance/vX.Y.Z.json`，观察期结束再提交，跟版本一起留下。`v1.5.0.json` 是一次没过门禁却转正的记录，不要当样板。

## 反馈怎么变成测试

同一句 Whisper / 设置 Loading / 导入失败再来，说明上一版没有把这条路径封住。

1. 先定级：S1 热修，S2 进本周版，S3 不单独发版。不要把 S2 当 S1 连夜发。设置页打不开、主流程 100% 失败是 S1。
2. 在**安装包**上复现，不在源码里「感觉修了」。
3. 合入修复时带一条会失败的回归（单元、安装冒烟或黄金路径编号）。1.5.0 的设置 500 对应 `test_get_ai_models_survives_broken_legacy_cover`。
4. 回复「请升级」之前，确认这条回归在 CI 或 L1 里。只让用户升级、不留测试，等于邀请下一版再炸一次。

## 下一版先做什么（1.5.x，不夹新功能）

1. 设置页 Loading 是 S1：脏的 1.4 封面配置不能再 500。修进补丁，用 1.5.0 安装包在 Windows 上打开设置确认。
2. 用 1.5.0 / 补丁包在 Windows（真机或虚拟机）走完 G1–G4，结果写入验收 JSON。latest 已经出去了，这是补课。
3. Whisper「已下载仍失败」若在 1.5.0 复现，按 S1/S2 修进补丁，不要再攒功能。
4. 之后每个 tag：L1 必须绿，L2 记录必须能通过门禁，才 promote。

## 明确不做

- 不为了发版再扩一圈功能。验证面已经比验收能力大。
- 不把示例项目、源码 CLI、Linux pytest 当成桌面激活证据。
- 不重打同名 tag，不跳过 Pre-release。
- 不把开发环境的 Sentry（react-refresh、`environment=development`）当成正式包观察结论。
- 不在这里再写一份和 `RELEASE_CHECKLIST.md` 重复的长清单。操作步骤仍看那份；**过不过由门禁决定**。
