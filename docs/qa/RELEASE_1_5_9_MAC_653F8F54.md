# 1.5.9 Mac 装包验收 `653f8f54`

日期：2026-11-07。只测这一台 Mac arm64，不等 Windows。没有 tag、Promote、validation 另构建、付费调用或 A3。没有改 `/Applications` 里的现有应用，没有动用户 8000 端口后端，没有改 hosts、防火墙或安全权限。

安装目录：`/Users/zhoukk/AutoClipQA/159-mac-653f8f54/`。后端数据在该目录的 `profile`。证据在该目录的 `evidence/`，不入库。

## 包身份

| 项 | 值 |
|---|---|
| Desktop Build | `42251959542` success |
| 源 SHA | `653f8f54ae9bc81630fb02033270c09d6379490e` |
| artifact | `13522627812` `autoclip-desktop-macos-arm64` |
| DMG | `AutoClip Desktop_1.5.9_aarch64.dmg` |
| DMG SHA-256 | `ee65b3883ddd4f2232a2aaafe0e3b43c40e338ff1c3de0653fe080738baeb786`（与 `internal-build-provenance.json` 一致） |
| updater tar.gz SHA-256 | `32e72acd2c7b262f1c60737eba9f02fbffad459c7e709dcd272cd8a6a6a300e7` |
| 版本 | `CFBundleShortVersionString` 1.5.9，bundle `com.autoclip.desktop` |
| 子进程 | `AUTOCLIP_BUILD_ENVIRONMENT=production`，`AUTOCLIP_APP_VERSION=1.5.9`，`AUTOCLIP_MODE=desktop` |

这不是 `001acd8e` 那一包。

## 逐项

### A1-5 强杀恢复：PASS

本地 30 秒无声视频加 SRT，`auto_start`，没有模型调用。心跳进入 `screening` 后立刻 `SIGKILL` 隔离后端，壳还在。

杀前采样（`evidence/a15-death-hb.json`，读自当时的 `.hb`；恢复后该文件被清掉）：

- `pid` 31788，等于被杀进程
- `stage` `screening`，不是 idle
- age 0.042 秒，小于 15 秒
- 采样到 kill 的间隔按记录为 0.0 秒，小于 2 秒

恢复后的 studio 记录：`restart_reason=crash`，`crash_exit=sigkill`，`crash_stage=screening`，`failure_stage=screening`，`billable_calls_before_failure=0`，文案「应用刚重启，这次制作已中断，请重试。」与心跳阶段一致。

首页卡片截图 `evidence/a15-card.png`：同一句，按钮「重新生成」。

PostHog：2026-11-06 17:15–17:20 UTC 一条 `studio_generation_finished`，`app_version=1.5.9`，`os=macos`，`analytics_environment=production`，`restart_reason=crash`，`crash_stage=screening`，`crash_exit=sigkill`，`failure_stage=screening`。

Sentry：`PYTHON-FASTAPI-5Z` 最新事件 2026-11-06T17:16:21Z，`release=autoclip-backend@1.5.9`，`build_environment=production`，同样的 crash 字段。这是该 issue 的第 2 次（第 1 次是更早的 `001acd8e` 验收）。这次强杀对应这一条新事件。

### A1-6 活动退出：PASS（制作状态由本机 fixture 挂住）

先有一次 Cmd+Q 发生在界面还没把进行中的项目算进去的时候，应用直接退出，marker 是 `user_quit`，没有出现「仍然退出」。那一次不算本项通过。

随后重新打开。本地 127.0.0.1 挂起服务接住分析请求，没有外呼，也没有点「测试连接」。接口读到项目 `processing`，窗口标题出现「制作中，已阻止休眠」。这时 Cmd+Q，对话框是「正在制作 1 个项目」，按钮「后台继续」和「仍然退出」。截图 `evidence/a16-dialog.png`。点击「仍然退出」后进程退出，marker `b62a5ae977e0` 内容是 `user_quit`。

到 2026-11-06T17:29:41Z 再读 Sentry，`PYTHON-FASTAPI-5Z` 的 last seen 仍是 17:16:21Z，次数仍是 2。同一分钟 PostHog 没有新的 `studio_generation_finished`。没有把脚本 API 当成这次点击。

这不是完整制作导出通过。挂起的是本机 fixture。

### A2-5 下载文案：部分，超时句未出现

两条真实 YouTube URL（删除候选、登录候选）在这台 Mac 上都在数秒内失败，码都是 `source_not_found`，阶段 `ingest`，句子是「找不到这个视频，它可能已被删除或链接不正确…」。没有拿到 `timed out`，也没有拿到 sign-in。日志里没有这些原文短语。不把 Windows 的超时结果套过来，也不把登录候选说成 `source_blocked`。

页面：

- 首页 `evidence/a2-model-card.png` 上，名为 QA-A2-timeout 的卡片是「下载：找不到这个视频…」，按钮「重新生成」，没有「模型设置」。
- 项目页 `evidence/a2-project.png`：同一句，按钮「换一个视频」。
- 导入确认页 `evidence/a2-import-page.png`：同一句，按钮「换一个视频」，没有「模型设置」。

对照：把分析指到关闭的 `127.0.0.1:9` 后，本地文件失败码是 `connection`，阶段 `outline`，句子是「无法连接模型服务…」。首页卡片 `evidence/a2-model-card.png` 的 QA-model-connection 是这句，按钮「重试」。这不是下载超时。

英文界面没有改。语言存在这个 bundle id 的共享 WebKit 存储里，改它会碰到已安装应用的偏好。非中文页因此是 BLOCKED，不是失败。

### #565 生图模型槽位：PASS（接口）

`PUT /api/v1/settings/ai-models` 把分析模型写成 `dall-e-3`，返回 422，正文含「生图」，不含填写的密钥。当时没有 `ai-model-settings.json`。随后的 readiness 不是 `image_model_in_analysis`，`ready` 为 false。没有点「测试连接」，也没有把三盏灯写成就绪。

后来为了对照文案和退出，另外保存了语言模型 `fixture-language`。首页就绪行是「模型 ✓ fixture-language、转写 ×、画面 —、FFmpeg ✓」，见 `evidence/a2-model-home.png`。那不是生图模型被接受。

### #567 发布与 DSN

这次包的后端事件带着 `release=autoclip-backend@1.5.9` 和 `build_environment=production`，并已经到达现有 Sentry 项目。没有打印 DSN，没有改 `backend-1.5.9-plus`，没有另做 validation 构建。

### 导入、制作、导出

本地文件导入和制作启动已经发生（A1-5 的 screening，A1-6 的 processing）。没有做出可导出的成片。导出不记通过。示例视频和付费模型都没有用。

## 2026-11-07 下午补充

证据已放进本仓库 `docs/qa/evidence/653f8f54/`，供复核。`/opt/cursor/artifacts` 在这台机器上不可写，所以没有用那条上传路径。没有把误截到其他窗口的那张图放进来。

WebKit 隔离：只改了验收副本的 `CFBundleIdentifier` 为 `com.autoclip.desktop.qa653f8f54` 并重新 ad-hoc 签名。语言只用 `defaults write` 写这个新 id 的 `AppleLanguages`。旧 id `com.autoclip.desktop` 没有 `AppleLanguages`，它的 WebKit `localstorage.sqlite3` 修改时间在整个下午操作后仍是 `1793988643`。`$HOME` 改不了 WebKit 目录，因为目录跟 bundle id 走。

### A2 下载超时：PARTIAL

不经代理时，删除候选 URL 仍在约 3 秒内变成 `source_not_found`。这次为了让已安装下载器真正走出超时，只给验收进程设置了 `https_proxy=http://127.0.0.1:8877`（本机接受连接但不回答），并排除了 `127.0.0.1`。没有改 hosts、防火墙。约 181 秒后失败：`error_code=connection`，`failure_stage=ingest`，句子是「下载视频时网络超时或中断。请检查网络后重试，或换一个视频链接。」这是下载器的真实套接字超时，不是 YouTube 自己返回的 `timed out` 原文。YouTube 在这台机器上直接回答时仍是 `source_not_found`。登录候选此前也是 `source_not_found`，没有 sign-in 原文可留。

页面：

- 中文首页 `docs/qa/evidence/653f8f54/a2c-zh-home.png`：该句，按钮「重新生成」，没有「模型设置」。步骤前缀仍是「制作」，因为项目列表没有 `failure_stage`。
- 英文首页 `a2c-en-reload.png`：同一句的英文。
- 英文项目页 `a2c-en-project.png`：句子正确，但旁边有「Model settings」。这是项目页 `StudioResults` 在下载超时上仍给出的模型设置入口。导入确认页没有这个按钮。
- 英文导入页 `a2c-en-import.png`：同一句，按钮「Use another video」，没有模型设置。

### A1-6 标注

「仍然退出」那一次的进行中状态是本机挂起服务撑住的，不是完整模型制作。截图 `a16-dialog.png`。`user_quit` 写在隔离 profile 的 marker `b62a5ae977e0`。Sentry 只复查了 issue `PYTHON-FASTAPI-5Z`：到 17:29 UTC last seen 仍是 17:16:21Z。这不能当成所有 Sentry 项目都没有新事件。PostHog 只查了 17:28–17:32 的 `studio_generation_finished`，该窗口没有新行。

### #565 `doubao-seedream-5-0-flash-260915`：PARTIAL

设置页已打开（`settings-models.png` 留在本机 evidence，未入库）。分析槽当前是 `fixture-language`。点开后界面写「还没有已连接的服务商」，所以没有在界面里把这个生图 id 选进槽位并点保存。已安装后端对这个确切 id 的 `PUT /api/v1/settings/ai-models` 返回 422，正文含「生图」，不含密钥，也不回显模型 id。保存被拒绝后 readiness 仍是 `configured` / `fixture-language`，不是 `image_model_in_analysis`，也不是三灯全绿。先前的 `dall-e-3` 接口拒绝同样只说明保存门，不能代替这个 id 的界面试跑。

### #567

已收到的 Sentry 事件标签里没有 key 名称字段。因此新 key 名未证。不打印 DSN。release 仍是 `autoclip-backend@1.5.9`，`build_environment=production`。

### 导入制作导出：BLOCKED

这台机器没有 Ollama、LM Studio 或已安装的本地转写模型。不用 fixture 把分析跑完冒充完整成片。没有可播放的导出。

## 没有写成全通过的项

- 下载超时那句在这台 Mac 上没有触发。
- 真实 sign-in / `source_blocked` 这次没有出现。
- 英文界面。
- 导出。
- A3。
- Windows。
- validation。

第一次打开窗口时，WebKit 仍使用 bundle id `com.autoclip.desktop` 的共享存储。点过「稍后设置」。之后的界面操作仍可能写到这份共享存储。后端数据目录是隔离的。
