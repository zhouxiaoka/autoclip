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

## 不在这次改动里的事

- 不把正式包或它的启动器改成 validation，也不增加让已安装正式包改报 validation 的开关。
- 不根据未保存的心跳正文改 `set_stage` 的写盘时机。
- 不把 Mac 的 unavailable / private 原文套到 Windows 的 `connection`。
- 不改 Windows QA 的 hosts、防火墙、RDP。14:50 的清理只存在于脱敏记录；本机没有复核那台 VM 的当前规则。
- 不把「有名字的 connection」或 helper 的局部成功旗标当成 A2-5 通过。

## 下一轮还缺什么

1. 死亡 instance 的 `.hb` 只保存 `ts` 和 `stage`，并标明 instance，不能只留新进程的心跳。
2. 看得见窗口时，在 `processing` 仍为进行中的情况下走真实 Cmd+Q 或托盘，并留下「仍然退出」被按下的证据。
3. Windows 两条 URL 的脱敏 yt-dlp 类别：匹配到的短语类别、耗时、是否超时或 DNS 失败。不要保存异常全文。
4. 专用 `API88_ZERO_KEY`。没有它，A3-5 继续保持未测。
5. 若要 validation 收数，另做 `TESTING_ACCEPTANCE.md` 写明的 validation 构建；不要复用这次 production 安装包。
