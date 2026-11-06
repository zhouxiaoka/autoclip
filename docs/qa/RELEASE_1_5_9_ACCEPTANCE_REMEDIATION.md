# 1.5.9 装包验收：已证、待证、阻断

记录日期：2026-11-06。对照计划 `docs/RELEASE_1_5_9_PLAN.md` 的 A1-5、A1-6、A2-5、A3-5，以及 `docs/TESTING_ACCEPTANCE.md` 的 validation 与生产包分工。

本文只写已经读到的安装包行为和源码事实。Windows 段落来自同日脱敏交接，当作观察，不把其中的操作建议当成已授权动作。没有改 hosts、防火墙或 RDP。没有重打包，没有 tag / Promote，没有付费调用。

当前 RC 尖端 `648336de` 只比装包提交多了网站同步（#568）。下面的装包事实仍属于 `001acd8e`。

## 包身份

| 平台 | 构建 | 源 SHA | 包 | SHA-256 |
|---|---|---|---|---|
| macOS arm64 | Desktop Build `42160880524` 成功，artifact `13477836319` | `001acd8e64e05d9e39a0de83117c34d3d31fa3d4` | `AutoClip Desktop_1.5.9_aarch64.dmg` | `f58f98f95c83d8859bdb667f15f72dd1b3daa94a923b4994378c68f2da7e28b5`（与 `internal-build-provenance.json` 一致） |
| Windows x64 | 同一次构建，artifact `13478077116` | 同上 | `AutoClip Desktop_1.5.9_x64-setup.exe` | 脱敏记录为 `9adb59b0…c3b9f572`，204,234,244 bytes；完整值留在原始证据，不在本文展开 |

Mac 安装在隔离目录，没有替换 `/Applications` 里的现有应用，也没有动用户自己的 8000 端口后端。Windows 记录的是 Server 2025 交互会话里的已安装包，不是 session 0。

正式安装包的启动器把 `AUTOCLIP_BUILD_ENVIRONMENT` 写成 `production`。这与 `scripts/macos_release_contract.py` 的发布合同一致：验收进程不能靠继承环境变量把正式包改成 validation。`docs/TESTING_ACCEPTANCE.md` 把 validation 定义为另一次补充构建（前端 `VITE_TELEMETRY_VALIDATION=true`，受控后端 `AUTOCLIP_BUILD_ENVIRONMENT=validation`），并且写明它不替代最终生产安装包。因此这次不把正式包改成 validation，也不把已经收到的 production 事件当成 validation 门禁通过。

## 分项

### A1-5 制作中强杀后端

**Mac：行为已见到，环境不是 validation。** 只杀死隔离验收后端后，壳拉起新后端。首页卡片原文是「制作：应用刚重启，这次制作已中断，请重试。」按钮是「重新生成」。本地记录 `restart_reason=crash`、`crash_exit=sigkill`、`crash_stage=screening`、`billable_calls_before_failure=0`。PostHog 一条 `studio_generation_finished`（production，1.5.9，macos/aarch64，同样的 crash 字段）。Sentry 一条 `PYTHON-FASTAPI-5Z`，`ServiceRestarted`，标签 `crash_exit=sigkill`、`crash_stage=screening`、`restart_reason=crash`、`build_environment=production`，次数 1。Mac 这次是在心跳文件已经写成 `screening` 之后才杀的，不能用来解释 Windows 的 `idle`。

**Windows：恢复和卡片已见到；`crash_stage` 与当时阶段不一致，根因未证。** 本地视频加字幕、`auto_start=true`。14:24:01.049 读到 running / screening，14:24:01.732 用 `Stop-Process -Force` 杀掉安装包后端（约 0.68 秒）。新后端起来，首页同样是重启文案加「重新生成」。PostHog production：`restart_reason=crash`、`crash_exit=nonzero_other`（强制结束、退出码不是信号 9，和 Mac 的 `sigkill` 不是同一枚举）、`failure_stage=screening`，但 `crash_stage=idle`。死亡实例的 `.hb` 正文（`ts` / `stage`）没有保存，不能拿崩溃后新实例的心跳代替。`idle` 的形成原因保持未知。0.68 秒只说明轮询和强杀的间隔，不是已证实根因。

源码里两件可以分开看、但都还不能选定 Windows 根因的事实：

- `inspect_project` 在工作线程进入 `_inspect` 之前就把 analysis 写成 `phase=screening`。`set_stage('screening')` 要等 `@_tracked('screening')` 真正进入才写进内存。
- 心跳文件由后台线程每 15 秒（制作中）或 60 秒（idle）替换。`set_stage` 当时只改内存。`read_scene` 在缺少 `.hb` 时给出 `crash_stage=unknown`，不是 `idle`；现有测试 `test_a1_2_crash_fields_from_heartbeat_exit_and_fault` 锁着这一点。所以报出 `idle` 表示当时读到的文件内容就是 `idle`。没有那份正文，就不能区分「线程还没进入 set_stage」「磁盘仍是上一拍 idle」或「读错了 instance」。

这次不改心跳写入。在正文缺失时改写入时机，会把未证实的原因写成修复。复测要先保存死亡 instance 的 `.hb` 安全字段 `ts` 和 `stage`，再决定要不要改代码。

Windows 这次的 Sentry 交付不可核验：当时 QA 的 `#winqa-sentry` hosts 黑洞和 `winqa-sentry-ip` 出站规则还在，后端日志有 `getaddrinfo failed`。空查询不能当成「没有发送」或「正确地没上报」。脱敏记录写 14:50 执行过清理；本机这次没有再读那台 VM 的 hosts 或防火墙，也不修改它们。Mac 上收到的那条 production Sentry 不能填这个洞。

### A1-6 活动中的正常退出

**Mac：只证明了空闲退出。** 没有进行中的制作时 Cmd+Q，进程直接退出，没有出现「仍然退出」。标记文件内容是 `user_quit`。其后的 Sentry 查询没有第二条 `service_restarted`。这不能代替「制作中选择仍然退出」。稍后想在同一隔离包上补活动中的 Cmd+Q，这次启动没有出现可访问窗口，按键没有落到 QuitGuard，该项仍待证。

**Windows：不是托盘确认。** 制作中（processing=1，generation=screening）对主窗口调用了 `CloseMainWindow`。标记是 `user_quit`。QuitGuard 的 CDP helper 以连接关闭失败告终，没有可信的「仍然退出」点击，也没有实际走托盘。不能用标记反推对话框已经出现。同一 Sentry 黑洞下，也不能把查无事件当成 user_quit 没有上报。

源码：`QuitGuard` 只在项目列表里存在 producing / pending，或 `studio_generation_status` 为 screening、production、rendering 时打开对话框；否则直接退出。活动中的确认仍要在看得见窗口时重做。

### A2-5 删除视频与需要登录的链接

**Mac 已见到有名分类，按钮文案和计划用词不是同一句。** 已删除链接终态 `source_not_found`，卡片是「找不到这个视频，它可能已被删除或链接不正确…」，不是「错误」，计费次数 0。私密链接终态 `source_blocked`，卡片说明无法访问并提到登录，主按钮是「选择已登录的浏览器」，不是计划里的「使用浏览器登录状态」。后者是导入表单上的字段标签；失败卡按下后才回到那个表单。不把两句收成一句，避免无根因地改八语。

**Windows 两次都是 `connection` / `ingest`，不能用 Mac 的 yt-dlp 原文解释。** 输入是真实 URL：`https://www.youtube.com/watch?v=dQw4w9WgXcZDELETED999` 与 `https://www.youtube.com/watch?v=K4Rux5hrHMI`。大约 127–132 秒后失败，`llm_calls=0`，`billable_calls_before_failure=0`。首页或项目页主按钮是「重试」，没有浏览器登录按钮。yt-dlp 异常类型、匹配短语、DNS/TLS/超时原文都没有保存。因此不能判断是网络超时被现有规则收成 `connection`，还是分类器漏掉了 unavailable / sign-in 短语。不改分类，也不改文案。

补充一个源码事实，避免把卡片上的「模型服务」读成已经打过模型：`failure_messages.json` 里 `connection` 的句子就是「无法连接模型服务…」。下载超时和若干网络短语也会映射到这个码。`llm_calls=0` 与「没有模型调用」一致，但不能代替缺失的 yt-dlp 原文。

### A3-5 零余额预检

**Mac 与 Windows 都未测。** 没有专用的 88API 零余额 key。没有用正常 key 冒充，没有建号、充值，也没有编造预检结果。

要补的输入是：隔离配置里的 88API（`billing_probe=new_api`）key，其 `hard_limit_usd - total_usage/100 <= 0`。预检本身是账单接口的 GET，不是模型推理；key 和余额数字不进证据、不进日志。命中后应在制作前出现余额不足和「去充值」，且 `billable_calls_before_failure=0`。

解锁不是零花费路径。现有「测试连接」会要一条非空模型回答，那是计费调用。没有不花钱的解锁。换一把仍有余额的专用 key 并做测试连接之前，需要单独的花费授权。本记录不创建也不充值任何账号。

## 本轮已执行（不是真机通过）

本地无外网的回归：

- `test_screening_record_can_diverge_from_saved_heartbeat`：项目阶段可以已经是 screening，磁盘心跳仍是 idle；`write_once` 之后 `read_scene` 才变成 screening。缺文件仍是 `unknown`，不是 idle。
- `test_observe_download_failure_splits_network_from_source_without_echoing_text`：`timed out` → `timeout`/`connection`，`getaddrinfo` → `dns`/`connection`，unavailable → `source_not_found`，private → `source_blocked`。输出不含原文。
- `scripts/tests/test_acceptance_capture.py` 与 `scripts/tests/test_macos_release_contract.py`：7 项通过。正式包观察为 production 时，`--expect validation` 失败。

采集命令（不杀进程、不打印下载器原文）：

```bash
python scripts/qa/acceptance_capture.py heartbeat --marker-dir <shutdown_markers> --pid <backend-pid>
python scripts/qa/acceptance_capture.py download-error --exception-type DownloadError --seconds <elapsed> --text-file <local-error.txt>
python scripts/check_telemetry_environment.py --observed <allowlisted.json> --expect production
python scripts/check_telemetry_environment.py --print-validation-build
```

在已安装的 `001acd8e` 上读到子进程 `AUTOCLIP_BUILD_ENVIRONMENT=production`。检查脚本接受这个观察，并拒绝把它当成 validation。validation 构建标志只打印，不写进正式启动器。

同一隔离进程里，项目列表已经是 `processing` / analysis `screening` 时，最新心跳行的 `stage` 仍是 `idle`。快照留在本机隔离目录，不入库。这复现了两个时钟可以不一致，但没有强杀，所以不能把 Windows 那次 `crash_stage=idle` 收成已经定位。强杀前要保存的就是这份 `ts`/`stage` 再加当时的 backend PID。

活动中的 Mac Cmd+Q 没有完成。CoreGraphics 能看到窗口 69829（1200×801），但本次 `screencapture` 无法从该窗口取图，Accessibility 的窗口数为 0，Cmd+Q 没有让进程退出。不能把这次算成「仍然退出」已测。Windows 托盘确认仍由 PM 在虚拟机上做，这里不去连那台机器。

## 不在这次改动里的事

- 不把正式包或它的启动器改成 validation，也不增加让已安装正式包改报 validation 的开关。
- 不根据未保存的心跳正文改 `set_stage` 的写盘时机。
- 不把 Mac 的 unavailable / private 原文套到 Windows 的 `connection`。
- 不改 Windows QA 的 hosts、防火墙、RDP。14:50 的清理只存在于脱敏记录；本机没有复核那台 VM 的当前规则。
- 不把「有名字的 connection」或 helper 的局部成功旗标当成 A2-5 通过。

## 下一轮还缺什么

1. 强杀前运行上面的 `heartbeat` 命令，保存死亡 instance 的 `ts`、`stage` 和 backend PID。有了正文才能决定要不要改写盘时机。这次没有改 `set_stage`。
2. Mac 要在当前会话能对窗口截图并送入 Cmd+Q 之后，再于 `processing` 未结束时点「仍然退出」。Windows 托盘确认由 PM 做。窗口没起来或按键没送达，保持未完成。
3. Windows 两条 URL 用 `download-error` 保存 `exception_type`、`token`、`code`、`seconds`。`timeout` 或 `dns` 表示网络被收成 `connection`；`unavailable` / `sign_in` 才说明分类器没命中。不要保存异常全文，也不要套用 Mac 原文。
4. 专用零余额 key 仍缺。A3-5 未测。测试连接会发起计费请求，没有不花钱的解锁。
5. validation 收数需要单独构建，不重打这次正式包。待批准的最小动作只是：用 `VITE_TELEMETRY_VALIDATION=true` 打一版前端，并且后端不要走会覆盖成 production 的正式启动器。本变更不实现那条启动器分叉，也不派发 Desktop Build。
