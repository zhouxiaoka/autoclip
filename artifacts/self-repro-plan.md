# 不依赖反馈者的自复现记录

基线：`integration/1.5.8-rc` @ `1e61168dd00790deee0ab26dacd29dead64fa8e6`。
本记录在该 tip 上补了 #410 的重试，并在同一台 Linux 云主机上跑完下面列出的检查。
没有 Windows 安装包，也没有 macOS 安装包。下面凡是写「还要 Desktop Build」的，都是我们自己的机器，不是再向反馈者要日志。

## #487 卡住的「正在制作」/ `service_restarted` / 约 0% CPU

反馈（v1.5.6，Windows x64）：3 小时片在准备素材 99% 后出现 “The service restarted. Please generate again.”；13 分钟片停在 “Producing ready-to-post videos” 超过 15 分钟，0 条成片，任务管理器里 AutoClip 约 0% CPU、约 5 MB。

### 今天已经复现（通过）

1. **杀后端，任务落成 `service_restarted`。** 用现成的 provider e2e `kill_backend` 路径（`scripts/provider_e2e/harness.py` 的 `run_case`，`fault=kill`，`restart_after_kill=True`），mock 供应商，隔离数据目录。结果：`passed=true`，`error_code=service_restarted`，`status=failed`，`failure_stage=production`，`shutdown_kind=crash`，文案「应用刚重启，这次制作已中断，请重试。」耗时 53s。这是 Linux 上的 `SIGKILL`，不是 Windows 安装包，但走的是同一套恢复代码。
2. **活着的空闲进程不会被标成重启失败。** `test_idle_producer_stays_in_production_until_the_process_exits`：子进程卡在 `time.sleep`，本机测得 `status=sleeping`、`cpu_percent=0.0`、RSS 约 9.7 MB，恢复逻辑保持 `production` / 「正在制作可发布成片」。杀掉该进程之后，同一项目变成 `service_restarted`。
3. **自动拉起上限是 3 次。** `src-tauri/src/backend_manager.rs` 里 `MAX_CRASH_RESTARTS = 3`，`should_auto_restart` 在已重启 3 次或主动停止时返回 false；间隔 1s、2s、4s。单测 `unexpected_exit_restarts_and_intentional_stop_does_not` 写了这些断言。这台机器的 Cargo 1.83 编不过桌面壳（依赖要求 `edition2024`），**这个 Rust 单测今天没有执行**。健康检查只看进程是否退出；端口连不上但进程还在时，只打日志，不拉起。
4. **界面在后端消失后不再只停到窗口失焦。** 快轮询合同没改：网络错误仍然最多再试 2 次（一共 3 次失败），HTTP 错误立刻停，没有成功快照时也停。若最后一帧还是制作中，页面开着时改为每 10 秒再读一次；后端拉起来并把任务写成 `service_restarted` 之后，这一下会换掉「正在制作」。焦点 / 可见性刷新仍在。`workspace-polling.test.cjs` 锁住快预算（`calls===4`）和慢探测读到 `failed`。八语目录和 `failure_messages.json` 的 `service_restarted` 由 `studio-system-messages.test.cjs` 锁住。英文现在是 “The app restarted and this run was interrupted. Try again.”，不是反馈里那句 1.5.6 的 “The service restarted. Please generate again.”
5. **时间上限是另一条失败，不是重启。** `AUTOCLIP_CLIP_JOB_BUDGET_SEC` 覆盖默认 20 分钟（`test_env_budget_overrides_the_default_and_is_still_a_timeout`）。超时的错误码是 `timeout`，不会重试。反馈里的 15 分钟还没到默认上限。

相关回归：`backend/tests/test_studio_restart_recovery.py`、`backend/tests/test_job_budget.py`、`scripts/tests/test_provider_e2e.py` 里 `kill_backend` / `service_restarted` 的判定。本次一起跑过，通过。

### Desktop Build 之后，在我们的 Mac / Windows 上做

只杀后端，不要杀壳。壳死了就没有健康循环，也谈不上自动拉起。

macOS（从终端启动，环境变量才能进到后端；`open -a` 不会替你带上）：

```bash
AUTOCLIP_CLIP_JOB_BUDGET_SEC=20 \
  "/Applications/AutoClip.app/Contents/MacOS/AutoClip"
# 另开一个终端。任务进入「正在制作可发布成片」之后：
pgrep -lf autoclip-backend
# 记下 pid、RSS。只杀这一条：
kill -9 <backend-pid>
```

Windows（PowerShell，同样从终端起，不要只双击）：

```powershell
$env:AUTOCLIP_CLIP_JOB_BUDGET_SEC = '20'
& "$env:LOCALAPPDATA\AutoClip\AutoClip.exe"   # 以实际安装路径为准
# 制作进行中，只结束后端：
Get-Process autoclip-backend | Format-Table Id,CPU,WorkingSet64
Stop-Process -Name autoclip-backend -Force
```

我们要记的证据（都在测试机上）：

- 杀之前、杀之后 `autoclip-backend` 与 `AutoClip` 各自的 PID、CPU、工作集。5 MB 量级更像壳；Python 后端空转也已经接近 10 MB，带模型会更大。两条要分开看。
- 壳的 stderr：`后端进程意外退出，N 秒后自动重启（第 k 次）`。第 4 次应出现 `自动重启次数已用尽`，之后端口不再起来。
- 拉起之后读本机 `studio.json`（数据目录下该项目的 `metadata/studio.json`）和项目接口：`error_code=service_restarted`，`failure_stage`，`shutdown_kind`，文案为目录句。
- **窗口保持聚焦**再杀一次：快轮询失败后，大约 10 秒内应自己换成 `service_restarted` 的失败句，不必先切走窗口。切走再切回来仍然会刷新。安装包上还没眼见过。
- 另开一轮把 `AUTOCLIP_CLIP_JOB_BUDGET_SEC` 设成 `20`，后端保持存活：应在约 20 秒以 `timeout` 停，而不是 `service_restarted`，CPU 在等待模型时可以接近 0。

### 仍然只有反馈者本人能提供的

没有。进程分别是谁、界面有没有停在旧快照，用安装包在我们自己的机器上就能看。

## #410 WinError 32，yt-dlp 重命名被占用

反馈原文：

```text
ERROR: Unable to rename file: [WinError 32] The process cannot access the file because it is being used by another process: '...\raw\input.f299.mp4.part' -> '...\raw\input.f299.mp4'. Giving up after 3 retries
```

错误码当时是 `unexpected`。重试用尽之后现在是 `file_locked`，用户句是「下载的文件正被其他程序占用，请关闭占用它的程序后重试。」不带路径，也不带 yt-dlp 的英文。成功率 v4 的剔除名单没有加这个码。

### 今天已经确认

yt-dlp 2026.08.19 的 `FileDownloader.try_rename` 只对 `errno` 为 `EACCES` / `EINVAL` 的错误重试。Windows 的 WinError 32（共享冲突）映射成 `EACCES`。默认 `file_access_retries=3`，中间只在 warn 里睡约 10ms，然后抛出上面那句 “Giving up after 3 retries”。

本机是 Linux，打不开真正的 WinError 32（打开着的文件仍然能 `rename`）。测试注入的是同一个 `errno.EACCES`，并带上 `winerror=32` 和两个文件名：

- 不套我们的参数：4 次 `os.replace`（1 次加上 3 次重试），睡眠 `[0.01, 0.01, 0.01]`，然后 “Giving up after 3 retries”。这就是反馈里的行为。**默认重试不够。**
- `recovery_options`：同一把锁在第 4 次放开则成功，睡眠含 `0.25 / 0.5 / 0.75` 秒。一直锁住则 9 次尝试后 “Giving up after 8 retries”，退避合计 9 秒。
- `download_with_recovery` 在 yt-dlp 已经放弃之后**不会**再开第二次整段下载（`continuedl` 仍为 true，重试留在这一次 `YoutubeDL` 里）。放弃的是共享冲突时，抛出 `PipelineFailure`，码 `file_locked`，`studio_error_code` 不再是 `unexpected`，可见文案不含 `WinError`、路径或 “Giving up”。别的 rename 失败（例如磁盘满）仍是原来的 `DownloadError`。调用方若自己传了 `file_access_retries` 或 `retry_sleep_functions['file_access']`，不会被覆盖。

对应测试：`backend/tests/test_download_rename_lock.py`。改动在 `backend/utils/download_recovery.py` 的 `FILE_ACCESS_RETRIES = 8` 和 `file_access_backoff`。这是草稿 PR 里的修复，还没有进安装包。

### 我们的 Windows 机器上还要做的

安装含这次修复的包之后，不必用 YouTube。准备一个几 MB 的本地文件，让 yt-dlp 把它收成 `out.mp4`，在 rename 前用只共享读的句柄按住目标：

```python
import ctypes, time
from ctypes import wintypes
GENERIC_READ, FILE_SHARE_READ, OPEN_EXISTING = 0x80000000, 0x1, 3
INVALID = wintypes.HANDLE(-1).value
path = r"C:\path\to\out.mp4"  # rename 的目标，不是 .part
handle = ctypes.windll.kernel32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING, 0, None)
assert handle != INVALID
time.sleep(2)  # 短于约 9 秒的预算，修复后应成功
ctypes.windll.kernel32.CloseHandle(handle)
```

再跑一轮 `time.sleep(30)`：应在大约 9 秒后失败。yt-dlp 的 stderr 仍是 “Giving up after 8 retries”。任务的 `error_code` 应是 `file_locked`，界面是那句中文，而不是 `unexpected` 或带路径的英文。Linux 上做不到这一步。

### 仍然只有反馈者本人能提供的

没有。锁是本机杀毒、索引或别的进程，用上面的句柄就能复现同一类 WinError 32。

## #481 YouTube “Sign in to confirm you’re not a bot”

反馈把整段 yt-dlp 英文记成 `unexpected`（v1.5.6）。tip 上这条应变为 `source_blocked`，用户句是「这个视频当前无法访问…」，不带视频 id、不带 yt-dlp 原文，也没有 HTTP 状态码（它不是 403/412/429 那一句）。

### 今天已经复现（通过）

- 单测使用反馈里的整句，弯引号是 U+2019。`test_gated_link_is_source_blocked_without_status_hint` 通过。
- 这台云主机直接跑了 tip 锁定的 yt-dlp 2026.08.19：

```bash
yt-dlp --skip-download --no-warnings --no-playlist -J \
  "https://www.youtube.com/watch?v=XuoqKYxDHVc"
```

退出码 1。stderr 与反馈原文逐字相同（含 U+2019）。这是本机出口 IP 被 YouTube 拦住，不能写成用户机器上的结果。映射单测用的就是这串字。

### Desktop Build 之后

在我们的 Windows 上对同一个 URL 再跑一次打包里的 yt-dlp：不带 Cookie 应得到同一句，界面应是 `source_blocked` 的中文提示，而不是 `unexpected`。再用本机已登录浏览器的 Cookie 走导入，看这个 URL 能否下下来。那是我们自己的账号和网络。

### 仍然只有反馈者本人能提供的

没有。他们家的网络是否比机房更松，用我们自己的家庭宽带或手机热点对比即可。

## #428 Ollama 空时间线（`invalid_response`）

反馈文案：

```text
时间线模型回复没有有效时间区间（82 个话题，14 个字幕块）。 请换用能稳定返回结构化时间线的模型后重试；本地模型需支持当前字幕长度。这一步尚未进入评分或最短时长筛选。
```

错误码是 `invalid_response`，不是 `timeline_empty`（后者才会写最短时长）。

### 今天已经确认（通过，没有活的 Ollama）

`test_issue_428_empty_intervals_are_invalid_response_after_the_chunk_budget`：82 个话题、14 个字幕块、没有有效区间，`user_message()` 与上面整句一致，`classify_for_retry` 认为可重试。块内循环的预算是 3 次（`MAX_ATTEMPTS`），`test_all_live_invalid_replies_stop_after_three_repair_attempts` 和 `backend/tests/test_result_retry.py` 通过。外层 `run_step2_timeline` 只对 `timeline_empty` 再跑一整轮，所以这句出现时，块内的 3 次已经用完。本环境没有 Ollama，也没有为它去拉模型。

### 我们自己若要看真实 qwen2.5:7b

在已装 Ollama 的机器上（CI 没有这项）：

```bash
ollama serve
ollama pull qwen2.5:7b
autoclip run <带字幕的口播.mp4> --provider ollama --srt <file.srt> --json
```

看 `error_code` 是 `invalid_response` 还是 `timeline_empty`，以及块报告里的 `attempts` 是否到 3。不需要反馈者的工程文件。

### 仍然只有反馈者本人能提供的

没有。句子和重试次数已经在单元测试里对上。

## #434 导出字幕成了 Thin

### 今天已经确认（通过，无改动）

`backend/services/studio/packaging_render.py` 的 `FONT` 是 `Noto Sans SC Medium`。`test_packaged_cjk_loads_bundled_font_in_real_ffmpeg` 在本机 ffmpeg 上通过：ASS 使用该家族，fontselect 命中 `NotoSansSC-Medium`，不命中变量字体的 Thin 默认实例。八语和打包检查没有因为这次改动而动。

`publish_export.py` 的字幕烧录仍会先找系统字体（macOS 上包括 PingFang）。那是另一条路径，现有这条断言没有失败，所以没有改它。

### Desktop Build 之后

用 Windows 安装包打开一条 9:16、带英文字幕的成片，对比编辑预览和导出文件的字重、有没有底框。这是我们看画面，不是再向 #434 要材料。

### 仍然只有反馈者本人能提供的

没有。对方已说会在下一版安装包上自己看；我们这边的门是安装包冒烟，不是他们的回复。

## 进度条文案（和 20 分钟模型预算）

「模型步骤最多约 20 分钟」以前只要进度条在就会出现，下载、本地 Whisper、导出也算进去。现在只有内容分析 / 片段定位带这句。下载、字幕处理、视频导出只保留已进行时间和「进度为估算」。八语沿用原来的那句 key，没有新句子。`studio-progress.test.cjs` 与 `studio-results-status.test.cjs` 锁住。

## 这次没有做

YouTube Cookie 产品、精确百分比、跨重启续跑、长下载墙钟、#481 的产品改动、Ollama 模型质量、预览和 ASS 字重对齐。`file_locked` 没有放进成功率 v4 的剔除名单。跨进程占文件这种环境失败仍会计入产品失败，避免这次顺手改测量口径。
