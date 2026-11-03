# 1.5.7 出片成功率埋点（线 A）

机读目录：[`event_catalog.json`](event_catalog.json)。未登记事件或缺必填字段，校验测试失败。

事件、查询和验收一起改。字段与枚举以第 0 步契约为准：[`docs/SUCCESS_RATE_CONTRACT.md`](../../docs/SUCCESS_RATE_CONTRACT.md)、`backend/core/upstream_errors.py`、`backend/core/llm_telemetry.py`、`frontend/src/analytics/successRateContract.ts`。

本线只发送事件、把 run 级字段写入 generation / production，并把允许字段并进 `safeStudioProperties`。不上报 key、提示词、字幕、模型原文或完整 URL；`base_url` 只留域名，本机地址记为 `local`。

## 事件

| 事件 | 谁发 | 何时 |
| --- | --- | --- |
| `llm_request_finished` | 后端 `core/llm_emit.py`（经 `llm_telemetry` 导出） | 每个 Provider.`call` 与 studio `vision_call` 的成功和失败 |
| `studio_generation_finished` | 前端观察 + 后端写入 run 字段 | 自动出片终态 |
| `studio_production_finished` | 前端观察 + 后端写入 run 字段 | 确认制作终态 |
| `asr_readiness_checked` | 前端导入探针/提交；后端 inspect 入口 | 生成前转写是否就绪 |
| `provider_validation_finished` | 后端挂钩（线 B 调用） | 设置页接入校验结束 |

`distinct_id` 与界面 PostHog 匿名 ID 相同（`PUT /settings/analytics-identity` → `analytics.json`）。Sentry 只设 `user.id`，不设 IP / email。

## 字段

`success_rate_schema_version = 1`。

### `llm_request_finished`

| 字段 | 规则 |
| --- | --- |
| `provider` | 闭集：dashscope / openai / gemini / deepseek / seed / kimi / glm / grok / infistar / api88 / compatible / ollama / lmstudio / other |
| `model` | `[\w.\-:/]{1,64}`，不合规则省略 |
| `base_url_host` | 只域名；环回/内网/`.local` → `local` |
| `kind` | `text` / `vision` |
| `stage` | 管线阶段或 `other`（契约 `FAILURE_STAGES`） |
| `http_status` | 100–599 的整数，可空 |
| `upstream_error_type` | 契约闭集：`invalid_key` / `insufficient_quota` / `permission_denied` / `model_not_found` / `bad_endpoint` / `rate_limited` / `upstream_unavailable` / `timeout` / `connection` / `output_truncated` / `unknown` |
| `prompt_tokens` / `completion_tokens` / `reasoning_tokens` | 非负计数 |
| `retry_count` | 非负；本请求在结果重试环中的次数（`invalid_response`/`timeline_empty` 最多 2）；SDK 内部重试记不到 |
| `degrade_count` | 非负；同服务商候选降级次数。R1 在换下一个候选时调用 `note_same_provider_degrade()` |
| `duration_ms` | 非负耗时 |
| `outcome` | `success` / `error` |
| `finish_reason` | `stop` / `length` / `content_filter` / `unknown` |
| `failure_stage` | 失败必填，∈ `FAILURE_STAGES`（契约请求白名单之外的线 A 扩展，便于和 run 级对齐） |

### 生成 / 出片 run 级

挂在现有 `studio_generation_finished` / `studio_production_finished` 上，不改事件名：

| 字段 | 规则 |
| --- | --- |
| `provider` / `model` / `base_url_host` | 与上表相同；按本次 run 实际调用 |
| `http_status` | 失败时 400–599 |
| `upstream_error_type` | 上表闭集；站点拒绝（`source_blocked`）和找不到片源（`source_not_found`）不标 |
| `failure_stage` | 失败必填 |
| `error_code` | 失败必填，∈ 现有 studio 错误码（缺失时后端写成 `unexpected`） |
| `billable_calls_before_failure` | 失败时必有；成功路径不发 |
| `retry_count` | 本次 run 累加的请求重试次数（E2：每次逻辑调用的重试增量之和，不是「最后一次」） |
| `degrade_count` | 本次 run 已发生的同服务商降级次数 |
| `llm_calls` / `prompt_tokens` / `completion_tokens` | 本次 run 累计，可空 |

失败的 `llm_request_finished` 总会带上闭集里的 `upstream_error_type`：无法分类的 HTTP 记 `unknown`，没有状态码的超时记 `timeout`，断连记 `connection`。run / generation 的 `http_status` 与 `upstream_error_type` 以最近一次请求为准；连续失败时保留最后一次失败的字段，最近一次缺失的字段不沿用此前失败值。本地失败（没有 HTTP 状态的超时、断连）的快照和持久化字段仍不带 `upstream_error_type`。回归验收覆盖 429 后接 503、无法分类的 HTTP（请求事件为 `unknown`）和无 HTTP 状态的超时（请求事件为 `timeout`，快照仍为空）。

查询这些字段时以当前尝试为单位；同一项目重新生成不包含历史调用与 tokens。同一 generation 内，初筛和制作的独立 `track_run` 累加调用、prompt/completion/reasoning tokens 与降级次数，请求重试也计入调用数；进度重复写入或保存失败后重试不重复累计。`retry_count` 表示本次 run 内累加的重试次数（E2）：每次逻辑调用只计入相对上次峰值的增量，并行分块不会少算或多算。结果类失败 `invalid_response` / `timeline_empty` 最多再试 2 次（不含首次，合计最多 3 次尝试，见 `backend/core/result_retry.py`）；HTTP/传输类失败不在此重试。零调用 worker 显式写入 0，同一 generation 已累计的调用与 tokens 保留，新 generation 则从 0 开始。没有当前 run 时不回退到项目历史；项目成本报表 `llm_usage.summary(project_id)` 仍累计历史。回归验收：初筛 1 次成功加制作 2 次成功，保存 3 次调用、33 prompt tokens、12 completion tokens；制作改为 1 次失败后重试成功时，保存 3 次调用、22 prompt tokens、8 completion tokens。另验同一项目独立生成、零调用新生成及保存失败重试的计数隔离。

### `asr_readiness_checked`

| 字段 | 规则 |
| --- | --- |
| `provider` | `whisper_local` / `sensevoice_local` / `cloud` |
| `code` | readiness 闭集（`whisper_not_installed` 等） |
| `has_subtitle` | 布尔 |
| `blocked` | 转写未就绪且没有字幕 |

### `provider_validation_finished`（预留）

| 字段 | 规则 |
| --- | --- |
| `provider` | 与请求事件相同 |
| `base_url_host` | 只域名 |
| `result` | `success` / `failed` / `skipped` |
| `upstream_error_type` | 与请求事件相同闭集 |

## 查询

见 `docs/analytics/release_validation.sql` 末尾「1.5.7 成功率埋点」。失败事件缺 `error_code` 或 `failure_stage` 视为收数缺陷，不是失败原因。

S5：仅 AUTO 模式的视觉校验失败或初筛不可用时，方案保存 `degrade_reason=vision_unavailable_subtitle_fallback`，`studio_screen_finished` 与 `studio_generation_finished` 从该方案读取并按尝试去重。此字段只接受这个固定代码，不发送原因正文；不计入同服务商模型候选切换的 `degrade_count`。用户手动选择视觉仍阻断，不切换服务商。

R11：`degrade_reason` 闭集扩为四个固定代码（`event_catalog.json` 的 `enums.degrade_reason`）：上面的 `vision_unavailable_subtitle_fallback`、解析失败的 `vision_invalid_subtitle_fallback`、本地抽帧失败（错误码 `frame_extract_failed`，不算视觉服务不可用）后改走字幕的 `frame_extract_subtitle_fallback`、素材超过 120 分钟直接走字幕的 `source_too_long_subtitle_route`。都使用原分析服务商，都不是失败；均不计入 `degrade_count`。

验收：模拟校验失败和连接不可用，核对 AUTO 使用原分析连接走字幕出片、八语界面显示切换提示、重复观察仅上报一次固定代码，未知代码及正文被丢弃；手动视觉仍被阻断。安装包 validation 收数使用下述 S5 查询，按事件分别核对路线与终态，不把降级本身当成制作失败。
