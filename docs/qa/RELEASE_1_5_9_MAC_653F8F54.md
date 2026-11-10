# 1.5.9 Mac 装包验收 `653f8f54`

日期：2026-11-07。只记录这一台 Mac arm64。没有 tag、Promote、validation 另构建、付费调用或 A3。没有改系统 hosts、防火墙或安全权限。没有动 `/Applications` 里的现有应用，也没有动用户自己的 8000 端口后端。

入库证据在 `docs/qa/evidence/653f8f54/`。下面不再写个人安装路径。

## 两份被测物

同一份 DMG 装出来之后，下午为了避开共享 WebKit，验收副本的 bundle id 被改过并做了 ad-hoc 重签。改完之后的界面和超时不能记成原 DMG 通过。之后没有再改 bundle 或签名。

| | 原安装副本 | 改过的验收副本 |
|---|---|---|
| 来源 | Desktop Build `42251959542`，artifact `13522627812` | 同一安装目录上的副本，不是新包 |
| DMG SHA-256 | `ee65b3883ddd4f2232a2aaafe0e3b43c40e338ff1c3de0653fe080738baeb786` | 安装后 Info.plist 已改，不再等于原 DMG 的 bundle |
| 源 SHA | `653f8f54ae9bc81630fb02033270c09d6379490e` | 后端代码仍是这一份，壳的标识被改过 |
| bundle id | `com.autoclip.desktop` | `com.autoclip.desktop.qa653f8f54` |
| 签名 | 安装包自带 | 改 plist 后 ad-hoc |
| 版本 | 1.5.9 | 1.5.9 |
| 子进程环境 | `AUTOCLIP_BUILD_ENVIRONMENT=production`，`AUTOCLIP_APP_VERSION=1.5.9` | 同左。超时那次还设置了只属于该进程的 `https_proxy=http://127.0.0.1:8877`，并排除了本机地址 |
| 用在 | A1-5、A1-6、直连 YouTube 的 `source_not_found`、早晨的 `dall-e-3` 保存拒绝 | 英文界面、诱导超时、中文超时卡片、`doubao-seedream-5-0-flash-260915` 的 422 |

改 bundle 的文件修改时间是 2026-11-07 14:25:58（本机时钟）。A1 证据文件的磁盘修改时间更早：心跳 JSON 01:16:50，首页卡片 01:18:32，退出对话框 01:27:33。这只说明这些文件写入早于改包，不是截图里的采集时钟。截图文件没有采集时间字段，不补写。

这不是 `001acd8e` 那一包。

## 原安装副本

### A1-5

Parent 已核对入库的心跳和图，内容和遥测一致：`stage=screening`，`crash_exit=sigkill`，句子是「应用刚重启，这次制作已中断，请重试。」按钮「重新生成」。

入库文件：

- `a15-death-hb.json`：文件内已有 `ts=1793985375.8672042`、`stage=screening`、`pid=31788`、`age_at_sample=0.042`、`kill_gap_s=0.0`。`ts` 是采样时写进这份 JSON 的数值。换算成本机时钟约 2026-11-07 01:16:15，只解释这个字段，不把它写成截图时间。
- `a15-prekill-hb.json`、`a15-studio-sanitized.json`：恢复记录里有 `crash_exit=sigkill`、`crash_stage=screening`、`restart_reason=crash`。
- `a15-card.png`：同一句和「重新生成」。文件本身没有采集时间。

执行链边界：这份 JSON 没有包 SHA、bundle id 或 DMG 哈希，也没有另一份独立的 kill 日志。`kill_gap_s` 是采样时写进同一份 JSON 的字段，不能当成单独的 kill 记录。不把包身份或截图时间补进这些文件。能归属到原副本，是因为这些文件的磁盘修改时间早于 14:25:58 的 bundle 改写，并且 parent 核对过内容与遥测一致。遥测侧 parent 已看过同秒的 production 字段；本记录不代替那次核对。

### A1-6：fixture-assisted

`a16-dialog.png` 有「正在制作 1 个项目」和「仍然退出」。点击后的 marker 内容是 `user_quit`。进行中状态是本机挂起服务撑住的，不是完整模型制作。

Sentry 只复查了 `PYTHON-FASTAPI-5Z`：到 17:29 UTC，last seen 仍是 17:16:21Z。这不是全域没有新事件。PostHog 只查了 17:28–17:32 的 `studio_generation_finished`，该窗口没有新行。

更早有一次 Cmd+Q 发生在界面还没把进行中项目算进去的时候，应用直接退出，没有对话框。那一次不算本项。

### A2：原包只有 `source_not_found`

不经代理时，删除候选和登录候选都在数秒内失败，码是 `source_not_found`，阶段 `ingest`，句子是「找不到这个视频…」。原包上没有出现下载超时句，也没有 sign-in 原文。登录候选没有被记成 `source_blocked`。

原包没有改语言。英文页不属于原 DMG。入库的 `a2-model-card.png` 是模型连接对照（关闭的 `127.0.0.1:9`，码 `connection`，阶段 `outline`，句子是「无法连接模型服务…」），不是下载超时。早晨的删除句页面截图没有放进这个 PR，不把未入库的图写成已复核。

### #565：只记接口 422，保持 PARTIAL

原包上 `PUT /api/v1/settings/ai-models` 把分析模型写成 `dall-e-3` 返回 422，正文含「生图」，不含密钥。当时设置没有被写成这个模型。这不能当成 `doubao-seedream-5-0-flash-260915` 的界面通过。

## 改过的验收副本

这些结果不能标成原 DMG PASS。

### 英文和诱导超时：PARTIAL

YouTube 直连在这台机器上仍是 `source_not_found`。为了让已安装下载器走出超时，只给这个进程设置了 `https_proxy=http://127.0.0.1:8877`（本机接受连接但不回答）。约 181 秒后：`error_code=connection`，`failure_stage=ingest`，句子是「下载视频时网络超时或中断。请检查网络后重试，或换一个视频链接。」`a2c-result.json` 记的是这个结果。这是套接字挂起引起的超时，不是 YouTube 上游返回的 `timed out`。

页面都在改过的副本上：

- 中文首页 `a2c-zh-home.png`：该句，按钮「重新生成」，没有「模型设置」。步骤前缀仍是「制作」，因为项目列表没有 `failure_stage`。
- 英文首页 `a2c-en-reload.png`、项目页 `a2c-en-project.png`、导入页 `a2c-en-import.png`。导入页按钮是 “Use another video”。项目页句子正确，旁边仍有 “Model settings”。这是当时装包里的行为；按钮修复在另一个 PR，没有进这个包。
- `iso-first.png` 只说明改过的副本能显示英文，不是原包的语言结果。

### #565：`doubao-seedream-5-0-flash-260915` 仍是 PARTIAL

设置页能打开。分析槽当时是 `fixture-language`。点开后界面写还没有已连接的服务商，所以没有在界面里把这个生图 id 选进去并保存，也没有做试跑。同一进程上对该 id 的保存接口返回 422，正文含「生图」，不含密钥，也不回显模型 id。拒绝后 readiness 仍是 `configured` / `fixture-language`，不是 `image_model_in_analysis`，也不是三灯全绿。设置页截图没有入库。

### #567：新 key 名未证

已收到的事件带 `release=autoclip-backend@1.5.9` 和 `build_environment=production`。事件标签里没有 key 名称字段。不打印 DSN。没有改 key，没有另做 validation 构建。

## 没有通过的项

- 完整导入、制作、导出：仍是 BLOCKED。见下面的资源核对。没有用 fixture 跑出成片。
- 原 DMG 上的下载超时句和英文界面：没有。下午这两项只存在于改过的副本，而且超时是本机代理诱导的。
- A3、validation、Windows：不做。

## 2026-11-07 晚些时候新增

没有再改 bundle id、签名或共享偏好。原 GUI 没有启动。旧 bundle 的 WebKit 文件修改时间仍是 `1793988643`。用户 8000 端口后端还在。

从原 DMG 另拷了一份未改 plist 的应用，bundle id 仍是 `com.autoclip.desktop`，Info.plist SHA-256 与 DMG 内的一致：`5b0d64db198a7aed9a4cbe2d43559c488d9e237e1b46cbe1402bc3cedf6e1cfd`。用这份包里的 `backend.desktop_main` 起了后端，没有开窗口。

### 更新清单

`releases/latest/download/latest.json` 能读到，版本是 `1.5.8`。darwin-aarch64 的目标文件名是 `AutoClip.Desktop_1.5.8_aarch64.app.tar.gz`。没有 1.5.9 的 latest.json，没有造一份。

### sign-in：原包后端见到 `source_blocked`

一个公开、需要确认年龄才能看的页面，没有登录、没有读 Cookie。原包后端导入后项目是 `source_blocked`，阶段 `ingest`，句子是产品自己的「这个视频当前无法访问，可能是私密、地区或年龄限制，或网站要求登录确认…」。句子里没有链接。这不是 timeout，也不是 `source_not_found`。

### #565：界面拒绝和就绪门都看到了，仍不是真实上游

隔离配置里写了一个本机 `127.0.0.1:9` 的 seed 连接和 `doubao-seedream-5-0-flash-260915`。这是防错夹具，不是连上了豆包。

原包后端：

- 保存该配置返回 422，正文含「生图」，不回显密钥和模型 id。
- 文件直接放进隔离 profile 后，readiness 是 `image_model_in_analysis`，`trial_ok` 为空。分析灯和转写灯都不是通过，不是三灯全绿。
- 同一后端的试跑接口 `probe_kind=trial` 立刻返回 `image_model_in_analysis`，`trial_passed` 为空，没有把灯点亮。

窗口是已经改过 bundle id 的那份副本，因为原 GUI 会写共享 WebKit。截图：

- `565-settings.png`：分析槽是这个 id，并推荐改用 `doubao-seed-2-1-lite-260915`。
- `565-save.png`：点保存后提示「该模型是生图模型，只能用于封面，不能做分析。」文件里的模型 id 没有被写成别的。
- `565-home.png`：导入区写着这个 id 不能做分析，模型灯是叉，转写灯是叉，FFmpeg 是勾。不是三灯全绿。

设置摘要页没有单独的「试跑一段」按钮；试跑走的是上面那个原包接口。

### 成片：BLOCKED

数据卷可用约 262 GiB。产品目录里的 whisper tiny 约 75 MB、base 约 145 MB，放得下。QA profile 里的 whisper 目录是空的，readiness 是 `whisper_not_installed`。没有 Ollama、LM Studio，也没有现成的本地对话模型。分析槽现在是上面的生图夹具，产品会在调用前拦住。没有下载一套对话模型来冒充完整制作，也没有可播放的导出。
