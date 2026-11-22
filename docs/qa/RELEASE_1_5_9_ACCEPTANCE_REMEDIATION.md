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

**Windows 14:24 强杀：恢复和卡片已见到，死亡瞬间的 `.hb` 正文没有留下。** 本地视频加字幕、`auto_start=true`。14:24:01.049 读到 running / screening，14:24:01.732 用 `Stop-Process -Force` 杀掉安装包后端（约 0.68 秒）。新后端起来，首页同样是重启文案加「重新生成」。PostHog production：`restart_reason=crash`、`crash_exit=nonzero_other`、`failure_stage=screening`，但 `crash_stage=idle`。那一次的死亡正文没有保存，不能单独证明写盘滞后。

**同日 16:51–17:22 补采（同一安装包，PID 3696，同一 `analysis.instance`）把 idle 收成写盘滞后，不是读错文件。** 三组互不拼接的采样：

- 17:11:06 live phase=screening，`.hb` stage=`analyze`，age 约 0.9 秒，随后有本地 fixture POST。
- 17:13:51–17:13:59 另一次尝试：phase=screening，同一 instance 的 `.hb` stage=`screening`，age 约 8 秒。
- 17:15:51 另一次尝试：phase=screening，同一 instance、同一 PID，`.hb` stage=`idle`，`hb.ts` 比采样早 30.457 秒。

补采没有新的强杀→拉起链，不能把 A1-5 的崩溃恢复改成通过。`analyze` 与 phase=screening 同时出现，符合阶段栈取最高优先级（screening < analyze）；崩溃阶段报的是当时还活着的最深阶段，不是项目 phase 列。`idle` 且文件比现场旧约 30 秒，符合空闲节拍 60 秒、`set_stage` 只改内存、写线程在 `wait` 里不被唤醒。这是已证缺口。

源码修复（尚未装进 `001acd8e`）：阶段解析结果变化时唤醒心跳线程，由该线程自己写当前 instance 的文件，并在文件里写下本进程 pid。工作线程仍然不 fsync。缺文件仍是 `crash_stage=unknown`。另一个 instance 的文件不会被这次写入改掉。仍留下的边界：`inspect_project` 把 phase 写成 screening 之后、工作线程还没 `set_stage` 之前，文件可以仍是 idle；写盘本身也还有一次替换的窗口。这两处是毫秒级，不是补采里那 30 秒。

Windows 14:24 的 Sentry 交付不可核验：当时 QA 的 hosts 黑洞还在。补采只读到 hosts 已是 0 字节、QA 防火墙规则为空，没有改 hosts、防火墙或 RDP。空查询仍然不能当成「没有发送」。Mac 上那条 production Sentry 不能填这个洞。

### A1-6 活动中的正常退出

**Mac：只证明了空闲退出。** 没有进行中的制作时 Cmd+Q，进程直接退出，没有出现「仍然退出」。标记文件内容是 `user_quit`。其后的 Sentry 查询没有第二条 `service_restarted`。这不能代替「制作中选择仍然退出」。稍后想在同一隔离包上补活动中的 Cmd+Q，这次启动没有出现可访问窗口，按键没有落到 QuitGuard，该项仍待证。

**Windows：托盘确认阻断，不是产品缺陷结论。** 早先制作中对主窗口调用了 `CloseMainWindow`，标记是 `user_quit`，那不是托盘。补采没有再调用 `CloseMainWindow`。早期能读到系统托盘和主窗口；随后直接 helper 被 AMSI 拒绝（`ScriptContainedMaliciousContent`），quser 变为 Disc。没有打开托盘菜单，没有点到「退出应用」或「仍然退出」。不改 Defender。该项保持 `BLOCKED_NEED_INTERACTIVE_DESKTOP`。

源码顺序（Tauri 2.8.5）：托盘「退出应用」和 macOS Cmd+Q 都是菜单 id `quit`。托盘回调把该 id 留给全局 `on_menu_event`，两者写进同一条 `menu.global_event_listeners`，所以会进 `handle_quit_click`，而不是被托盘回调丢掉。前端监听就绪后发 `close-requested`。有进行中的制作才出现「仍然退出」；否则直接 `confirm_quit`。`confirm_quit` → `quit_app` → `stop_with_intent(UserQuit)`：先通知后端写 `user_quit`，再结束进程，然后 `exit(0)`。监听还没就绪时退出不弹窗。托盘里的「停止后端服务」是另一个菜单项，它停后端、不退出应用，不经过这个对话框。源码没有发现「退出应用」绕过 QuitGuard 的缺口。Mac 本会话 CoreGraphics 能看到窗口，但截图和 Accessibility 按键到不了，不重复那次失败动作。活动中的真机确认仍未做。

### A2-5 删除视频与需要登录的链接

**Mac 已见到有名分类，按钮文案和计划用词不是同一句。** 已删除链接终态 `source_not_found`，卡片是「找不到这个视频，它可能已被删除或链接不正确…」，不是「错误」，计费次数 0。私密链接终态 `source_blocked`，卡片说明无法访问并提到登录，主按钮是「选择已登录的浏览器」，不是计划里的「使用浏览器登录状态」。后者是导入表单上的字段标签；失败卡按下后才回到那个表单。不把两句收成一句，避免无根因地改八语。

**Windows 补采：两条 URL 都是 yt-dlp 超时，`connection` 分类成立，卡片文案指错了对象。** 已安装 yt-dlp、无 cookie：删除链接 126.650 秒 `DownloadError` / `timed out` → `connection`；登录候选 126.186 秒同样是 `timed out` → `connection`。新建删除项目的接口结果是 phase=screening、`error_code=connection`、`failure_stage=ingest`。既有登录项目页读到「无法连接模型服务，请检查接口地址与网络；本地模型请先启动服务后重试。」主按钮「重试」，不是浏览器登录。这台 VM 没有拿到 unavailable / sign-in 原文，所以不能说分类器漏了删除或登录。不把超时改成 `source_not_found` 或 `source_blocked`。

已证的文案缺口：`failure_messages.json` 的 `connection` 是模型服务那句，下载超时以前也用它。源码修复保持错误码 `connection`，下载阶段改用「下载视频时网络超时或中断。请检查网络后重试，或换一个视频链接。」首页、项目页和导入页在 `failure_stage` 为 ingest 或 download 时用这句；分析阶段的 `connection` 仍是模型服务那句。`source_not_found` / `source_blocked` 和「选择已登录的浏览器」不动。导入页不再把这种下载失败送去「模型设置」。这套文案在 `001acd8e` 安装包里还不存在，真机界面要等以后的包。删除/登录专用上游文本这次仍然没拿到，A2 的那一半不能算通过。

### A3-5 零余额预检

**Mac 与 Windows 都未测。** 没有专用的 88API 零余额 key。没有用正常 key 冒充，没有建号、充值，也没有编造预检结果。

要补的输入是：隔离配置里的 88API（`billing_probe=new_api`）key，其 `hard_limit_usd - total_usage/100 <= 0`。预检本身是账单接口的 GET，不是模型推理；key 和余额数字不进证据、不进日志。命中后应在制作前出现余额不足和「去充值」，且 `billable_calls_before_failure=0`。

解锁不是零花费路径。现有「测试连接」会要一条非空模型回答，那是计费调用。没有不花钱的解锁。换一把仍有余额的专用 key 并做测试连接之前，需要单独的花费授权。本记录不创建也不充值任何账号。

## 本轮源码回归（不是装包通过）

下面这些测试锁的是源码行为。`001acd8e` 安装包还没有这些修复，不能把测试通过写成真机通过。

- `test_stage_change_publishes_without_waiting_out_the_idle_interval`：空闲节拍被调到 60 秒后，`set_stage('screening')` 仍会在 2 秒内写进当前 instance 的文件，文件里的 pid 是本进程；另一个 instance 的文件不变；缺文件的 `crash_stage` 仍是 `unknown`。
- `test_deepest_live_stage_wins_across_threads_until_that_frame_pops`：另一线程的 analyze 压过 screening，弹出后回到 screening。这是 `analyze` 与 phase=screening 可以同时出现的原因，不改优先级。
- `test_screening_record_can_diverge_from_saved_heartbeat`：工作线程的 `set_stage` 自己不写盘。
- `test_ingest_connection_sentence_is_not_the_model_service_sentence` 与 `test_observe_code_matches_the_download_path`：超时和 DNS 仍是 `connection`，用户句不是模型服务那句，也不含「登录」「删除」「模型」；unavailable 仍是 `source_not_found`，private 仍是 `source_blocked`。观察器的码和下载路径的码一致。八个 locale 都有这句，且互不相同。
- `scripts/tests/test_acceptance_capture.py`：`--pid` 不会写进没有该 pid 的心跳行；只有文件自己的 pid 与参数相等时 `pid_bound` 才为真。下载错误输出不含原文，且不导入 yt_dlp。
- 前端 `failure-action.test.cjs`：ingest 的 `connection` 用下载句、步骤「下载」、主操作仍是重试；analyze 的 `connection` 仍是模型服务句；导入页保留浏览器登录按钮，下载连接失败不再走「模型设置」。

采集命令不杀进程、不打印下载器原文。`--pid` 只是待核对的声明，不是绑定结果：

```bash
python scripts/qa/acceptance_capture.py heartbeat --marker-dir <shutdown_markers> --pid <backend-pid>
python scripts/qa/acceptance_capture.py download-error --exception-type DownloadError --seconds <elapsed> --text-file <local-error.txt>
python scripts/check_telemetry_environment.py --observed <allowlisted.json> --expect production
```

`--observed` 只接受 `AUTOCLIP_BUILD_ENVIRONMENT`、`AUTOCLIP_APP_VERSION`、`AUTOCLIP_MODE`。正式包观察为 production 时，`--expect validation` 失败。`--print-validation-build` 只打印另一次构建需要的两个标志，不创建构建，也不算 validation 完成。

## 不在这次改动里的事

- 不改正式包合同，不改 `backend_manager.rs` 让 release 启动器发出 validation，不派发 Desktop Build，不重打 `001acd8e`。
- 不把超时改成 `source_not_found` 或 `source_blocked`，也不为超时加浏览器登录按钮。
- 不改 Windows 的 hosts、防火墙、RDP、Defender。补采读到 hosts 为空；那是读取结果，不是本仓库做的清理。
- 不把生产遥测观察叫做 validation 通过。

## validation 要另一次受控构建（本轮不做）

可执行条件，缺一就不算 validation：

1. 单独的 Desktop 构建，前端 `VITE_TELEMETRY_VALIDATION=true`。
2. 后端不要由 release 启动器拉起。该启动器在 `src-tauri/src/backend_manager.rs` 把 `AUTOCLIP_BUILD_ENVIRONMENT` 写成 `production`。validation 进程要自己以 `AUTOCLIP_BUILD_ENVIRONMENT=validation` 启动，Sentry 才会带 `telemetry_test=true`。
3. 隔离的 PostHog / Sentry 项目或 DSN，不把现有 production 流量当测试流量。
4. 从活着的后端读到 `analytics_environment=validation`，再从实际收到的事件核对同一字段。只打印构建标志不算这一步。
5. 若要断言「没有事件」，需要一个没有 production 出口的窗口，并且事先批准。本轮没有改 sink，也没有派发构建。

## 仍未测

1. 新源码的心跳和下载文案都没有装进 `001acd8e`。Windows 补采没有新的强杀→拉起。Mac 活动中的「仍然退出」和 Windows 托盘「仍然退出」都没有做成。Mac 窗口在本会话里不能截图、不能送入按键，不重复该动作。Windows 需要重新 Active 的交互桌面，且不能用 `CloseMainWindow` 或绕过 AMSI。
2. A2 的删除/登录专用上游文本在这台 Windows 上没出现，只有超时。分类码 `connection` 对超时是对的；专用文案和浏览器登录按钮要等真正的 unavailable / sign-in 原文。
3. A3-5 未测。没有真实零余额 key。测试连接会发起计费请求，没有授权。
4. validation 构建、隔离 sink、实收事件核对都还没有做。
