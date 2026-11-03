# 1.5.9 计划：拉回从未成功的设备

> 起草：2026-11-03，基线 `integration/1.5.8-rc @ b706c76d`（= `v1.5.8`）。
> 数据：PostHog 450605（production · desktop · 排除 cohort 641509）近 21 天；Sentry 10-16 起断流，11-05 后再拉。
> 范围只有三刀。本地模型、转写兜底、D#508 可选 key 放 1.5.10。不做账号 / credits，不做新模板。

## 0. 版本目标（用 `docs/analytics/success_rate.sql` 同口径验收）

| 指标 | 1.5.7 基线 | 1.5.9 目标 | 说明 |
|---|---|---|---|
| attempt 成功率（图 5，全量口径） | 45.3% | ≥ 55% | 转正后 7 天窗口 |
| 从未成功设备（图 8） | 38.2% | ≤ 30% | 同窗口 |
| `service_restarted` 次数 / 千次 attempt | 126‰（236/1873） | 带 `restart_reason` 100%，`crash` 的 100% 带现场；次数减半是 1.5.10 目标 | 1.5.8 已有 9 条，8 条 `crash` |
| `error_code=unexpected` 占失败比 | 15.2%（149/983） | ≤ 3% | 其中 `unexpected_type=other` ≤ 1% |
| `insufficient_quota` 每设备重复 attempt | 2.1（132/63） | ≤ 1.3 | 第一次额度失败后不再让用户空跑 |

1.5.9 转正 7 天后，我按这五行查一次数据给结论；任一行没达标要在 1.5.10 写明原因。

## 1. 共同前置

- 分支从 `origin/main`（已含 1.5.8）切 `integration/1.5.9-rc`；本地 `main` 先 fast-forward。
- 先补 `CHANGELOG.md` 的 `[1.5.8] - 2026-11-02` 段（把「未发布」整段改名，不改内容），新开 `[未发布]`。
- 新增 / 修改任何事件属性，按 AGENTS 要求三处同改：`backend/core/event_catalog.json` → `frontend/src/analytics/successRateContract.ts` → `docs/analytics/success_rate.sql`（或新查询）+ `backend/tests/test_failure_code_catalog.py` 一类校验测试。
- 八语：所有新用户文案进 `frontend/src/i18n/locales/{zh,en,ja,ko,es,pt,ru,fr}.json` 和 `backend/core/failure_messages.json`。
- 每刀至少一条「修复前失败、修复后通过」的回归测试，放在 `backend/tests/`；不能只加断言数。

## 2. 刀一 · `service_restarted` 带出崩溃现场

### 现状
- `restart_reason` 已在 1.5.8 落地（`backend/services/studio/shutdown_marker.py`）：标记缺失 → `crash`。1.5.8 的 9 条里 8 条是 `crash`，不是用户关窗。
- `crash` 目前只说明「后端进程没来得及写标记就没了」，不知道是 Python 自己崩（原生库段错误 / OOM / 未捕获致命错误）还是被系统杀。
- `service_restarted` 在 `backend/core/sentry_setup.py` 的 `UNREPORTED_STUDIO_ERROR_CODES` 里，从不上 Sentry。
- Rust 壳 `src-tauri/src/backend_manager.rs` 的 `health_check_loop` / `restart_if_unexpected_exit` 在 `try_wait()` 拿到退出状态后直接丢弃，没有写盘。

### 改动
**1A 壳写退出码（Rust）**
- `try_wait()` 返回 `Ok(Some(status))` 且 `!intentional_stop` 时，在 `shutdown_marker_dir/<instance>` 不存在的前提下写入 `exit:<code>`（Unix 信号写 `signal:<n>`，`code()` 为 None 时写 `exit:unknown`）。复用现有 `record_unacknowledged_intent` 的「已有标记不覆盖」规则。
- 自动重启之前写，写失败不阻塞重启。

**1B 后端读退出码并细分（Python）**
- `shutdown_marker._restart_from_text`：`exit:*` / `signal:*` 仍归 `restart_reason=crash`（枚举不变），另解析出 `crash_exit`：枚举 `access_violation`（0xC0000005）、`stack_overflow`（0xC00000FD）、`heap_corruption`（0xC0000374）、`abort`（3 / SIGABRT）、`sigsegv`、`sigkill`、`oom`（Linux 137）、`nonzero_other`、`zero`、`unknown`（无标记）。只发枚举，不发原始数字。
- `restart_recovery.reconcile_interrupted_projects` 把 `crash_exit` 写进 generation / analysis 的失败记录；`attempts.py` 第 421 行那组导出键加 `crash_exit`、`crash_stage`、`crash_uptime_bucket`、`crash_rss_bucket`、`crash_disk_bucket`。

**1C 运行心跳**
- 新建 `backend/services/studio/run_heartbeat.py`：后端常驻 daemon 线程，每 15 秒写 `<marker_dir>/<instance>.hb`（JSON，原子替换）：`ts`、`uptime_s`、`rss_mb`、`free_disk_mb`、`stage`（当前最深的 producing 阶段：`screening/download/subtitle/analyze/render/idle`）、`ffmpeg_children`（在跑的 ffmpeg 子进程数）。没有活跃制作时每 60 秒一次。
- 恢复时读心跳，产出分桶枚举：`crash_stage` 同上；`crash_uptime_bucket` ∈ `lt_1m/lt_10m/lt_1h/ge_1h`；`crash_rss_bucket` ∈ `lt_1g/lt_2g/lt_4g/ge_4g`；`crash_disk_bucket` ∈ `lt_1g/lt_5g/ge_5g`。心跳超过 120 秒没更新也当 `crash`（已有逻辑不变，只是多给现场）。
- 心跳文件随 `shutdown_marker.release/prune` 一起清理。

**1D faulthandler**
- `backend/desktop_main.py` 启动时 `faulthandler.enable(file=<marker_dir>/<instance>.fault, all_threads=True)`。Windows 上它接管访问违例，能把原生崩溃的 Python 栈写下来。
- 恢复时若 `.fault` 非空：`crash_exit` 不变，追加 `crash_has_fault=true`；把栈里的 `File "..."` 只保留文件名 + 函数名 + 行号（`before_send` 同样的脱敏规则），作为 Sentry 事件的 `stacktrace`，正文仍是 `[message omitted for privacy]`。

**1E Sentry 放行一条**
- `service_restarted` 且 `restart_reason=crash`：每个死掉的 instance 只发 **一条** 合成事件（`sentry_setup.capture_crash_recovery(instance, fields)`），`fingerprint=['studio','service_restarted',crash_exit,crash_stage]`，tags 走现有白名单（新增 `crash_exit`、`crash_stage` 进 `allowed`）。仍受每日上限。同一 instance 多个项目不重复发。

**1F 已知候选（有证据再修，不硬凑）**
- Sentry 断流前 `core.database.sqlite_pragmas OperationalError` 834 条：查是哪条 pragma 在什么情况下抛（`database is locked` / `disk I/O error`），如果是启动期和渲染并发抢 SQLite，把 pragma 设置改成失败降级而不是抛。只在能写出复现测试时才动。
- 渲染阶段 RSS：如果 1.5.8 的心跳数据显示 `crash_stage=render` 且 `rss ≥ 4g` 占多数，1.5.10 再做 HTML 模板串行渲染。1.5.9 只收数据。

### 验收（A1）
- A1-1 单测 `test_shutdown_marker.py`：`exit:3221225477` → `(crash, access_violation)`；`signal:9` → `(crash, sigkill)`；`exit:0` → `(crash, zero)`；已有 `user_quit` 标记时壳写 `exit:*` 不覆盖。
- A1-2 单测 `test_studio_restart_recovery.py`：心跳文件 + 退出标记 + `.fault` 三种组合，恢复后 generation 带齐 `crash_exit/crash_stage/crash_uptime_bucket/crash_rss_bucket/crash_disk_bucket/crash_has_fault`；缺任一文件时对应字段为 `unknown`，不抛。
- A1-3 单测 `test_sentry_setup.py`：`restart_reason=crash` 发且只发一条 / instance；`restart_reason=user_quit|update|unknown` 不发；`.fault` 栈经过脱敏后不含路径分隔符和 `Users\|home/`。
- A1-4 Rust 单测（`backend_manager.rs` 的 `mod tests`）：`crash_marker_text(status)` 对 Windows NTSTATUS、Unix 信号、正常退出三类输出正确；并有现有风格的源码断言「写标记在 `should_auto_restart` 判断之后、`start()` 之前」。
- A1-5 真机（Windows x64 + macOS arm64 各一次，装包）：制作中用 `taskkill /F /PID <python>` / `kill -9` 杀后端 → 自动拉起 → 首页卡片显示「应用刚重启」+ 重试；PostHog validation 环境收到 `studio_generation_finished`，`restart_reason=crash`、`crash_exit=sigkill`（Win 为 `nonzero_other`，taskkill 退出码 1）、`crash_stage` 为被杀时的阶段；Sentry validation 收到一条 `service_restarted` 事件。
- A1-6 真机：正常退出（Cmd+Q / 托盘退出，选「仍然退出」）→ `restart_reason=user_quit`，Sentry 不收。
- A1-7 事件目录：`event_catalog.json` 新增六个属性及枚举，`successRateContract.ts` 同步，`success_rate.sql` 新增「图 10：`service_restarted` 按 `crash_exit × crash_stage`」，`test_failure_code_catalog.py` 通过。
- A1-8 心跳写盘不进 `store.lock`，不在请求线程；`pytest backend/tests/test_pipeline_concurrency.py` 与 QA 性能基线不退化（心跳 15 秒一次、单文件 < 1 KB）。

## 3. 刀二 · 把 `unexpected` 变成有名字的失败

### 现状
- 1.5.7 的 150 条 `unexpected` 里 150 条都在 `screening`（Win 132 / Mac 18）；`production/render` 只有 13 条。
- `screening` = `_inspect`（`jobs.py:2104`）：URL 下载 → `recommend` → 缩略图。`download_with_recovery`（`backend/utils/download_recovery.py:98`）只把 `_BLOCKED_HTTP_ERROR` 和 `_link_failure` 命中的转成 `PipelineFailure`，其余 `yt_dlp.utils.DownloadError` 原样抛出，`studio_error_code` 既不认它也不是 `ValueError`，落到 `unexpected`。Sentry 断流前 `DownloadError` 286 条、`planning.recommend ValidationError` 57 条，和这个分布一致。
- 用户看到的是 `failure_messages.json` 的「这次处理没有完成，请重试」，没有下一步。

### 改动
**2A 先让它有名字（无论根因）**
- `studio_error_code` 返回 `unexpected` 的地方，同时产出 `unexpected_type`：异常类名经白名单映射，白名单 `['DownloadError','ExtractorError','ValidationError','KeyError','TypeError','AttributeError','IndexError','OperationalError','RuntimeError','OSError','PermissionError','MemoryError','TimeoutError','JSONDecodeError','UnicodeDecodeError','CalledProcessError','other']`。实现放 `backend/core/failure_attribution.py`，`build_attribution` 把它带进 snapshot，`export_attribution` 导出。
- 写进 store 失败记录、attempt 导出、`studio_generation_finished` / `studio_production_finished` / `studio_screen_finished`。

**2B 把已知的几类映射成真实错误码**
- `download_with_recovery` 末尾：未命中的 `DownloadError` 按文本分类成现有码（优先级从上到下，都用小写子串，不回传原文）：
  - `sign in to confirm` / `not a bot` / `login required` / `private video` / `members-only` → `source_blocked`（已有 `SOURCE_BLOCKED_HINT`，1.5.8 的「使用浏览器登录状态」主按钮能接上）
  - `video unavailable` / `has been removed` / `does not exist` / `404` → `source_not_found`
  - `unable to download webpage` / `timed out` / `connection reset` / `ssl` / `getaddrinfo` / `proxy` → `connection`
  - `ffmpeg` / `postprocess` / `merge` → `frame_extract_failed`
  - `unsupported url` / `no video formats` → 新码 `source_unsupported`（加入 `studio_error_code` 枚举、`failure_messages.json` 八语：「这个链接不是可下载的视频页，请换一个视频链接或先下载后导入」）
  - 其余仍 `unexpected`，但 `unexpected_type=DownloadError`。
- `planning.recommend` 的 pydantic `ValidationError`：这是模型返回的结构不合规，归 `invalid_response`（走现有自动重试 2 次），不再是 `unexpected`。
- `_inspect` 里 `ensure_project_thumbnail` 的失败不得让 screening 失败：缩略图失败只记 warning，继续 `awaiting_confirmation`。
- `studio_error_code` 里 `ValueError → validation` 这一条保留，但 `pydantic.ValidationError` 要在它之前被判成 `invalid_response`。

**2C 用户文案**
- `unexpected` 的句子改成带阶段和出口：「{阶段}没有完成。请重试一次；再失败请在失败卡上点「反馈」，我们会收到失败阶段和错误类型（不含视频内容）。」八语。
- 失败卡的「反馈」已自动带 `error_code`，补带 `unexpected_type`（`frontend/src/analytics/feedback.ts`）。

### 验收（A2）
- A2-1 单测 `backend/tests/test_download_recovery_classification.py`（新建）：上面每条文本样例各一条断言（含大小写、带 URL 的原文），断言抛出的 `PipelineFailure.code` 正确且 `user_message()` 不含原文 / URL；未命中样例保持原异常但 `unexpected_type=DownloadError`。
- A2-2 单测：`recommend` 收到缺字段 JSON → `error_code=invalid_response`，触发现有重试路径（复用 `test_result_retry.py` 的夹具）。
- A2-3 单测：`ensure_project_thumbnail` 抛 `OSError` 时 `_inspect` 仍进入 `awaiting_confirmation`。
- A2-4 单测 `test_failure_code_catalog.py`：`unexpected_type` 只接受白名单值，任何其它类名落 `other`；`source_unsupported` 进入 `studio_error_code` 枚举、八语句子齐全、`success_rate.sql` 的归因列表把它放进 `user_x`（用户侧素材问题）。
- A2-5 真机：导入一个已删除的 YouTube 链接 → 失败卡显示「找不到视频」而不是「错误」；导入一个需要登录的链接 → 主按钮是「使用浏览器登录状态」。
- A2-6 数据：1.5.9 转正 7 天后，`error_code=unexpected` 占失败 ≤ 3%，`unexpected_type=other` ≤ 1%。

## 4. 刀三 · 额度耗尽：进门前拦、失败后不空跑、说清钱

### 现状（这一刀的前提要先纠正）
- 1.5.7 的 136 条 `insufficient_quota` 里 **135 条 `billable_calls_before_failure=0`**：后端已经在第一次调用就停了，不存在「失败前多扣几笔」。`pipeline/concurrency.py` 的「等兄弟块跑完」对额度场景没有实际成本。
- 真正的问题是：63 台设备平均撞了 2.1 次；用户看不到余额、看不到「这次没扣」，于是反复重试（#491 的「钱也扣了」大概率是服务商侧余额本来就为 0 或上一轮成功出片的费用）。

### 改动
**3A 付费调用前查余额（赞助商 / New API 系）**
- `backend/presets/provider_presets.json` 给 88API、Infistar（先核对它是不是 New API）加 `billing_probe: "new_api"`。
- 新建 `backend/core/quota_precheck.py`：`GET {base}/dashboard/billing/subscription` 读 `hard_limit_usd`，`GET {base}/dashboard/billing/usage?start_date=&end_date=` 读 `total_usage`（美分），剩余 = limit − usage/100。单次 3 秒超时、整体 fail-open（接口不存在 / 超时 / 非 JSON 都视为 `unavailable`，照常制作）。结果缓存 60 秒。
- 接入点：`readiness.ensure_analysis_usable()`（导入前检查）和 `_submit_production` 之前各查一次；剩余 ≤ 0 → 直接以 `error_code=provider_error`、`upstream_error_type=insufficient_quota`、`billable_calls_before_failure=0` 结束，不发任何模型请求。
- 新事件属性 `quota_precheck` ∈ `skipped/ok/exhausted/unavailable`，挂在 `asr_readiness_checked`（导入前）和两条终态上。不上报余额数值。

**3B 第一次额度失败后锁住「重试」**
- 复用保存校验失败时的「生成前拦住」机制（`provider_validation` 的 failed 状态）：当最近一次失败 `upstream_error_type=insufficient_quota`，该服务商标记 `quota_exhausted_at`；重试按钮变成「核对余额并测试连接」，测试连接成功（非空回答）才解锁。1.5.8 X3 的「去充值」保持在最前。
- 换服务商不受锁影响。

**3C 把钱说清楚**
- 失败卡（`ProjectCard.tsx`、`StudioResults.tsx`、`failureAction.ts`）在 `insufficient_quota` 时固定三句：「服务商回复余额不足。」「这次制作没有向服务商发出计费请求 / 发出了 N 次可能计费的请求。」「充值后点测试连接再重试。」八语。N 取 `billable_calls_before_failure`，为 0 时用第一种说法。
- 3A 命中 `exhausted` 时文案加一句「余额在开始前已核对」。

### 验收（A3）
- A3-1 单测 `backend/tests/test_quota_precheck.py`（新建，mock HTTP）：limit 10 / usage 1000¢ → `exhausted`；usage 500¢ → `ok`；404 / 超时 / 非 JSON → `unavailable` 且不抛；60 秒缓存命中不发第二次请求；非 `billing_probe` 服务商 → `skipped` 且 0 次请求。
- A3-2 单测：`exhausted` 时 `_submit_production` 不调用任何 `llm.call` / `vision_call`（patch 后断言 0 次），终态 `billable_calls_before_failure=0`，`quota_precheck=exhausted`。
- A3-3 单测（前端 vitest）：`failureAction` 在 `insufficient_quota` 且 `billable=0` / `billable=3` 两种输入下给出对应句子与主按钮「核对余额并测试连接」；测试连接成功后按钮恢复为「重试」。
- A3-4 Provider E2E Gate 的 mock 矩阵新增一条「余额探测返回 exhausted」用例，期望 `billable_calls_before_failure=0`；live 不新增条数。
- A3-5 真机：88API 用一个余额为 0 的 key 导入 → 导入前检查就提示余额不足并给「去充值」，不进入制作；充值 / 换 key 后测试连接通过，重试可用。
- A3-6 数据：1.5.9 转正 7 天后，`insufficient_quota` 每设备 attempt ≤ 1.3，`quota_precheck=exhausted` 的次数 ≥ 同期 `insufficient_quota` 终态数（说明大多数在门口被拦）。

## 5. 顺手项与明确不做

- `#434` 字幕 Thin 字体：`#446` 已改 `FONT = 'Noto Sans SC Medium'`（`packaging_render.py:20`），随 1.5.7 发布。不进 1.5.9 代码；在 issue 上请报告人用 1.5.8 验证，无回应按 needs-info 流程。
- 不动 `pipeline/concurrency.py` 的兄弟块语义（数据证明不是成本来源）。
- 不改 Sentry 每日上限（11-05 配额恢复后另看丢弃率）。

## 6. 发版门槛（不变，列出来是为了核对）

- `python scripts/quality_gate.py --report /tmp/quality-1.5.9.json` 全组通过。
- 新增 / 改动的事件属性在 `event_catalog.json`、`successRateContract.ts`、SQL、校验测试四处一致。
- 未打 tag 的候选分支跑一次 Desktop Build；Internal Acceptance 覆盖 A1-5、A1-6、A2-5、A3-5（双平台装包，记录包哈希 / 源 SHA / OS）。
- tag 走 Pre-release → 24 小时观察 → Release Acceptance → Promote。1.5.8 这次 `isPrerelease` 先于 Promote 被改掉的事不再发生。

## 7. 我检查时会看的东西

1. 每条 A-编号对应到具体测试名或验收记录行，没有对应的视为未做。
2. 「修复前失败」的证据：A2-1、A2-2、A3-2 至少各贴一次在基线上跑红的输出。
3. 事件属性只发枚举和分桶，不发路径、URL、余额数字、原始退出码、异常正文。
4. 心跳、退出标记、`.fault` 三个文件都在 `shutdown_marker_dir` 下，`prune` 能清，Windows 覆盖安装不受影响。
5. 八语 key 齐、`npm run typecheck` 和 i18n 检查通过。
6. 1.5.9 转正 7 天后按第 0 节五行拉数据。
