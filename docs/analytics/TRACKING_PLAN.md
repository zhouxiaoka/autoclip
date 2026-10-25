# AutoClip 埋点规范（Tracking Plan）

给 Kris 审的规范文档。1.5.7 起按本文件体系统一埋点：先登记，再发送。字段和枚举只引用第 0 步契约（#354，merge `8f49726`，已在 main）：`backend.core.upstream_errors`、`backend.core.llm_telemetry`、`frontend/src/analytics/successRateContract.ts`。禁止再复制一套分类或脱敏；后续代码直接 import 这三处。

**本 PR 只交文档。** 纯埋点代码另开 PR，等本规范确认后再改、再合。已开的上报 PR 标 `[WIP]`，不继续大改。

**本文是埋点唯一准绳。** [`docs/ANALYTICS.md`](../ANALYTICS.md) 与 [`docs/ANALYTICS_V2.md`](../ANALYTICS_V2.md) 是 2026-09 的历史说明，北极星不再是 `clips_exported`。查询、看板、校验和新事件都以本文件 + [`event_inventory.json`](event_inventory.json) 为准。

配套：

- 分类与脱敏：[`docs/SUCCESS_RATE_CONTRACT.md`](../SUCCESS_RATE_CONTRACT.md)、[`backend/core/upstream_errors.py`](../../backend/core/upstream_errors.py)、[`backend/core/llm_telemetry.py`](../../backend/core/llm_telemetry.py)、[`frontend/src/analytics/successRateContract.ts`](../../frontend/src/analytics/successRateContract.ts)
- 线 A 发送说明：`docs/analytics/LLM_TELEMETRY.md`（随纯埋点 PR #361，规范确认后）
- **本规范的机读清单：** [`event_inventory.json`](event_inventory.json)（事件名、状态、legacy 映射）。`scripts/check_tracking_inventory.py` 校验这份清单。
- **生产者目录：** `docs/analytics/event_catalog.json`（随 #361）。它必须由本清单生成，或在 CI 里对照本清单；未登记、缺必填、违禁值，校验测试必须失败。两份漂移即失败。
  运行时副本位于 `backend/core/event_catalog.json`，通过 Python package data 随 wheel 分发，也随 backend 目录进入桌面与 Docker 包；`test_event_catalog_package.py` 校验它与此处目录逐字节一致，并在仓库外安装 wheel 后验证加载。修改目录时须同步两份 JSON。
- 看板 SQL 草案：[`success_rate.sql`](success_rate.sql)

先看 §1–§5（规则、漏斗、触发点）、§10–§11（隐私硬性 / 脱敏 / 开关关闭）、§6–§7（口径与看板），再看 §8（全量盘点）和 §12（过渡计划 / 1.5.7 收口）。§8 的删除/改名 **不在 #361 纯埋点 PR 里执行**。过渡保留（查询继续映射历史值）；**1.5.7 必须收口**：单一 `os` / `outcome`、只报 `app_version`、QA/MCP/反馈公共信封、旧事件停发或打 `legacy=true`。`feedback_submitted` 是 `user_submitted` 例外，允许 `text`/`contact`。

---

## 1. 原则

1. **先登记后发送。** 新事件必须写入本文件 + `event_catalog.json`，并补齐八语无关（埋点无 UI 文案）的校验测试。未登记的事件名不得出现在生产者里。
2. **只发枚举、计数、布尔、随机 token。** 不上报 key、完整 URL、提示词、字幕/转写、视频标题、文件名、带用户名的本机路径、内部项目/作业 ID。`base_url` 只留 host；本机/内网记 `local`。详见 §10–§11。schema 校验必须拦住这些值。**例外：** `feedback_submitted` 是 `user_submitted`，可以带用户写下的 `text` 和可选 `contact`（见 §10）。`ingest_app_feedback.py` 据此开 Issue。
3. **终态与请求分开。** 按钮点击不是成功。后台受理用 `*_accepted`，真正做完用 `*_finished`。浏览器点击下载不是落盘。
4. **失败必有身份。** 失败的 run 级事件必须有 `error_code` + `failure_stage`。模型失败另带 `upstream_error_type`（站点拒绝、素材太短/无音轨等不算上游错误）。
5. **同一匿名 ID。** 前端 PostHog 在 webview localStorage 持久化匿名 UUID，待桌面后端就绪后经 `PUT /settings/analytics-identity` 原子写入 app 数据目录的 `analytics.json`；失败有限重试。Tauri 下次启动把已有 UUID 通过 `AUTOCLIP_ANONYMOUS_DEVICE_ID` 交给后端，并给 webview bootstrap 同一 ID。后端以共享文件为准、环境变量兜底；晚到的 ID 更新 Sentry 全局 scope，发送前再次读取。只接受 UUID，不接受标题、密钥、邮箱、路径或正文。分析开关关闭时不对齐（§10.1）。
6. **生产与验收隔离。** 业务看板只看 `analytics_environment=production` 且目标 `app_version`。validation 单独列，不进转化率。

---

## 2. 命名规则

### 2.1 事件名

```
<domain>_<object>_<verb>
```

- **domain**：`app` / `setup` / `provider` / `studio` / `asr` / `llm` / `mcp` / `feedback` / `social`
- **object**：被观察的对象（`generation`、`import`、`download`），不是内部函数名
- **verb** 闭集：

| verb | 含义 | 何时发 |
| --- | --- | --- |
| `opened` / `installed` / `updated` / `viewed` / `presented` / `shown` | 曝光或生命周期 | 实际显示/启动后 |
| `requested` | 用户发起或客户端发出请求 | 调用发出时 |
| `accepted` | 服务端受理（排队/落盘），工作未完成 | HTTP 成功返回且已建任务 |
| `request_failed` | 请求本身失败（未受理） | 4xx/5xx/网络，没有后台作业 |
| `finished` | 一次尝试到达终态 | 成功、失败、部分成功都发 |
| `checked` | 探针/校验，不是用户主路径终态 | ASR 就绪、QA、设置校验 |
| `selected` / `rated` / `shared` | 显式选择或评价 | 用户动作 |

禁止：

- 过去式混用（`imported` 与 `import_finished` 并存）
- 裸阶段名（`processing_failed`）
- 把「下载触发」叫 `clips_exported`
- 同一动作两套 verb（`provider_test_finished` 与 `provider_connection_test_finished`）

### 2.2 请求三件套

异步作业：`<name>_requested` → `<name>_accepted` → 观察后 `<object>_finished`。

同步调用：`<name>_requested` → `<name>_finished`（`outcome` 区分结果）。不要再发明 `*_accepted`。

### 2.3 `outcome` 口径（查询统一为 `success` / `error` / `partial`）

**查询规范值**（看板、HogQL、成功率一律先规范化再算）：

| 规范值 | 含义 |
| --- | --- |
| `success` | 这次尝试成功 |
| `error` | 这次尝试失败 |
| `partial` | 部分成功（出片有成片也有失败变体） |
| `recommended` / `auto_started` / `manual` / `fallback` | 仅 `studio_screen_finished`，不是出片成败 |
| `blocked` | 仅 experience（被设置/引导挡住） |
| `skipped` | 校验被跳过 |

**生产者现状与过渡：**

| 生产者现在发的 | 规范成 | 何时改生产者 |
| --- | --- | --- |
| Studio `completed` | `success` | **1.5.7** 起生产者只发 `success`；此前与历史查询映射 |
| Studio / experience `failed` | `error` | 同上 |
| `llm_request_finished` `success` / `error` | 已是规范值 | 保持 |
| `provider_test_finished` `success` / `failed` | `success` / `error` | 该事件 **1.5.7** 停发或打 `legacy=true` |
| experience `completed` / `failed` / `blocked` | `success` / `error` / `blocked` | **1.5.7** 改 `completed`→`success` |
| `provider_validation_finished.result` `success` / `failed` / `skipped` | 这是 `result` 不是 `outcome` | 保持 |

查询映射（历史 + 过渡期）：

```sql
multiIf(
  properties.outcome IN ('completed', 'success'), 'success',
  properties.outcome IN ('failed', 'error'), 'error',
  properties.outcome
) AS outcome_canon
```

§6.1 分子用 `outcome_canon = 'success'`（包含历史 `completed`）。不要把 `success` 和 `completed` 加两次。MCP 工具结果用布尔 `ok`，不发明第二套 outcome。

---

## 3. 公共属性

每条业务事件（非 `$` 系统事件）必须能回答：谁、哪个版本、哪台系统、哪次会话。

| 属性 | 来源 | 规则 | 必填 |
| --- | --- | --- | --- |
| `distinct_id` | PostHog 匿名 ID；后端读 `analytics.json` | 与 Sentry `user.id` 相同；禁止 email / IP | 是（SDK 自动；后端显式传） |
| `app_version` | 前端 `VITE_APP_VERSION`；后端 `AUTOCLIP_APP_VERSION` 或 `backend.__version__` | `MAJOR.MINOR.PATCH`，无 `v` 前缀。**禁止**再把版本写进 `version`（MCP / `app_installed` 过渡期见 §4.4） | 是 |
| `os` | 生命周期 super property；后端 `event_catalog.detect_os()` | **只允许** `macos` / `windows` / `linux` / `unknown`。`darwin`→`macos`，`win32`→`windows`。查询见 §4.4 | 是（前端 register；后端补） |
| `arch` | Tauri 在前端脚本之前注入原生架构；后端使用 native env / `platform.machine()` | `arm64`→`aarch64`，`amd64` / `x64`→`x86_64`；只发 `aarch64` / `x86_64` / `unknown`。浏览器无法可靠识别 Mac 架构时允许 `unknown`。PostHog loaded 同步注册 os/arch；业务 capture 再附加，不等版本异步查询 | UI 与后端公共信封是；历史/旁路事件可空 |
| `session_id` | PostHog `$session_id`（前端）；后端暂无会话 | 前端依赖 SDK，不要另造。后端事件用 `distinct_id` + 时间窗近似 | 前端是；后端可空 |
| `session_number` | 仅 `app_opened` | 本机启动次数，不是会话 ID | 仅该事件 |
| `analytics_environment` | 构建注入 | `production` / `development` / `validation` | 是 |
| `runtime` | 发送端 | `desktop` / `web` / `python` | 是 |
| `schema_version` | 生产者 | 公共信封，现为 `2` | 是 |
| `studio_schema_version` | Studio 事件 | 现为 `2` | Studio 事件必填 |
| `experience_schema_version` | 引导/设置事件 | 现为 `1` | experience 事件必填 |
| `success_rate_schema_version` | 成功率事件 | `1` | 成功率事件必填 |
| `entrypoint` | 前端 | `ui`；MCP 另用 `mcp` | 前端是 |

关联 token（可选，符合 `t-[a-z0-9-]{10,100}`）：

| token | 串什么 |
| --- | --- |
| `flow_id` | 同一项目从导入到出片/下载 |
| `operation_id` | 一次 API 的 requested 与结果 |
| `attempt_id` | 一次业务尝试（v4 终态取后端 AttemptReceipt 的 `attempt_id`；重试换新） |
| `artifact_id` | 同一导出作业的成片 |

禁止把内部 `project_id` / `run_id` / `job_id` 当作新事件属性。旧 legacy 事件若已带，不回填、不扩散。

**旁路也走同一信封。** QA（`studio_qa_checked`）、MCP（`mcp_tool_called` / `mcp_job_finished`）不得再裸 POST `/capture/`。后端一律叠 `envelope_properties()`（`app_version` / `os` / `analytics_environment` / `runtime` / `schema_version`）再加 `distinct_id`。#361 已给 `llm_emit` 加信封。QA / MCP / 反馈公共信封是 **1.5.7 必交任务**（§12.1 T4）。

**反馈是用户主动提交，不是旁路泄漏。** `feedback_submitted` 可以带 `text` / 可选 `contact`，发送可以走 `/capture/`，且不看匿名统计开关（没有 key 时才回退 GitHub）。**1.5.7 起 `/capture/` 载荷必须带同一信封字段。** 界面必须告知会先经 PostHog 再公开到 GitHub（邮箱不公开）。告知文案在 #361。`feedback_opened` / `feedback_dismissed` 仍是诊断事件，不带正文。

`legacy=true`：旧路径事件（§8.2）在 1.5.7 要么停发，要么每条带此布尔。Studio / 设置 / 线 A 新事件禁止带。#361 不改旧事件；1.5.7 清理 PR 补标记或停发。查询在标记齐之前用事件名列表。

---

## 4. 枚举

### 4.1 `failure_stage`

一次 **run**（生成或确认制作）停在哪一步。失败必填。

| 值 | 含义 |
| --- | --- |
| `screening` | 导入后初筛（含下载、推荐） |
| `dispatch` | 任务提交/调度 |
| `ingest` | 读素材、站点下载 |
| `subtitle` | 转写/字幕 |
| `analyze` | 文字模型分析（大纲/评分等） |
| `vision` | 视觉模型 |
| `outline` / `timeline` / `scoring` / `title` / `clustering` | 内容管线子阶段（有则写细的） |
| `production` | 确认制作后的内容生产（分不清子阶段时） |
| `render` | 导出/封装 |
| `other` | 对不上上面任一 |

别名（只在写入时规范化，不上报别名）：`INGEST→ingest`，`ANALYZE/HIGHLIGHT/analysis→analyze`，`EXPORT/DONE/rendering→render`，`visual_analysis→vision`。

### 4.2 `upstream_error_type`

只描述 **模型 HTTP 上游**。实现与提示见第 0 步契约，此处不另造值。分母规则为成功率 **v4**（与 §6.1、`event_catalog.json` → `attribution.success_rate_v4`、[`success_rate.sql`](success_rate.sql) 一致）。

| 值 | 全量口径分母 | 产品口径分母 |
| --- | --- | --- |
| `invalid_key` | **剔除**（用户：密钥错/过期） | **剔除** |
| `insufficient_quota` | **剔除**（用户：余额/额度） | **剔除** |
| `permission_denied` | **剔除**（用户：分组/模型权限） | **剔除** |
| `model_not_found` | 计入（v4 算产品失败：默认/推荐模型要能用） | 计入 |
| `bad_endpoint` | 计入（v4 算产品失败：地址校验应在前面拦住） | 计入 |
| `rate_limited` | 计入（产品应退避） | 计入 |
| `upstream_unavailable` | 计入（5xx） | 计入 |
| `timeout` | 计入 | 计入 |
| `connection` | 计入 | 计入（只有 `error_code = connection` 才在产品口径剔除，见 §4.3） |
| `output_truncated` | 计入 | 计入 |
| `unknown` | 计入 | 计入 |

**不要**把 `source_blocked`（B 站 403，或私密 / 地区限制 / 人机验证）、`source_not_found`（链接不存在或已删除）、`source_too_short`、`source_no_audio` 标成 `upstream_error_type`。

### 4.3 `error_code` 与归因

Studio `error_code` 仍用现有闭集（`STUDIO_ERROR_CODES`）。成功率 **v4** 把每个非成功 attempt 归到三类之一（`success_rate.sql` 图 3 的 `attribution` 列）：

| 归因 | 包含 | 全量口径分母 | 产品口径分母 |
| --- | --- | --- | --- |
| `user_both`（`user_hard`） | `outcome = cancelled`；`error_code ∈ (authentication, llm_auth_invalid, invalid_key, insufficient_quota, llm_not_configured, cancelled, user_cancelled)`；`upstream_error_type ∈ (invalid_key, insufficient_quota, permission_denied)` | **剔除** | **剔除** |
| `user_product_only`（`user_x`） | `error_code ∈ (connection, source_too_short, source_no_audio, source_unreadable, source_blocked, source_not_found)` | 计入 | **剔除** |
| `product` | 其余，**明确包括** `frame_extract_failed`（本地抽帧失败）、`store_lock_timeout`（本机项目存储锁等待超时，本地原因、用户修不了，不记到服务商，不是模型 `timeout`）、`whisper_not_installed`、`service_restarted`、`model_not_found`、`bad_endpoint`，以及 `unexpected`、`rate_limited`、`timeout`、`provider_error`、`invalid_response`、`transcription_empty`、`render` 等 | 计入 | 计入 |

`outcome_canon = success` 一律算成功，忽略错误字段。查询里用 `error_code` + `upstream_error_type` 映射到上表，不要在事件上再发一个自由文本归因。机器校验只用 `event_catalog.json` → `attribution.success_rate_v4`（`overall_excluded_*`、`product_extra_excluded_error_codes`、`product_failure_codes`、`flow_definition`）；同文件的 `user_caused_error_codes` / `user_caused_upstream_types` / `environment_error_codes` 是 v4 之前的口径，仅留作历史，**不得**再用于成功率。

`degrade_reason`（`enums.degrade_reason`）不是失败码，挂在成功出片上：`vision_unavailable_subtitle_fallback`、`vision_invalid_subtitle_fallback`、`frame_extract_subtitle_fallback`（AUTO 初筛本地抽帧失败，改走字幕）、`source_too_long_subtitle_route`（素材超过 120 分钟，视觉检查前直接走字幕）。它们不进成功率剔除列表，也不算失败；分布见 `success_rate.sql` 图 6。`frame_extract_failed` 列在 `product_error_codes`，计入分母。

### 4.4 `os` 与 `app_version`（唯一取值）

**`os` 只允许：** `macos` / `windows` / `linux` / `unknown`。

| 历史值 | 规范值 |
| --- | --- |
| `darwin` | `macos` |
| `win32` | `windows` |
| `macos` / `windows` / `linux` | 原样 |
| 其它 / 空 | `unknown` |

查询（过渡期 + 历史）：

```sql
multiIf(
  properties.os IN ('darwin', 'macos'), 'macos',
  properties.os IN ('win32', 'windows'), 'windows',
  properties.os = 'linux', 'linux',
  'unknown'
) AS os_canon
```

发送：lifecycle super property 和 #361 `envelope_properties()` 已经发规范值。此前内部测试包的 `workflow.safeStudioProperties` 与 `template_telemetry.OPERATING_SYSTEMS` 可能发出 `darwin`/`win32`。**本版 1.5.7 全生产者只发 `macos` / `windows` / `linux`**（侦不到才 `unknown`），禁止 `darwin`/`win32`。#361 不改已有 `darwin`/`win32`，以免打断现有看板。旧 1.5.7 测试包与正式包的成功率分界是 §6 的发布时间下限 `{release_1_5_7}`。

**版本只报 `app_version`。** `version` 是历史别名，查询 `coalesce(nullIf(properties.app_version, ''), nullIf(properties.version, ''))`。`app_installed` / `app_opened` / MCP 在 **1.5.7** 停发裸字段 `version`。

---

## 5. 完整漏斗与核心事件

漏斗只认下表 **核心事件**。诊断事件（模型单次、QA、模板预览）不进转化分母。

```
安装/打开 → 服务商配置与校验 → 导入 → 初筛 → 出片 → 导出/下载 → 回访
```

### 5.1 安装 / 打开

| 事件 | 必填 | 说明 |
| --- | --- | --- |
| `app_installed` | `app_version`, `os` | 本机首次启动；装机量代理，不是商店下载数 |
| `app_opened` | `app_version`, `os`, `session_number` | 每次启动；DAU / 回访分母 |
| `app_updated` | `from_version`, `to_version` | 版本变化 |

### 5.2 服务商配置与校验

| 事件 | 必填 | 说明 |
| --- | --- | --- |
| `setup_presented` | `placement`, `trigger` | 引导实际显示 |
| `setup_action` | `placement`, `action` | `later` / `open_settings` / `one_click`（赞助商一键获取只记 action + provider，不记 URL / key） |
| `import_blocked` | `reason` | 未配置就被导入挡住 |
| `provider_configuration_save_requested` / `_finished` | `provider`, `outcome`（finished） | 保存设置；保存成功 ≠ 能调用 |
| `provider_connection_test_requested` / `_finished` | `provider`, `outcome`（finished） | 现有连接测试 |
| `provider_validation_finished` | `provider`, `result` | **线 B 主事件**：保存前真实小请求。`result`=`success`/`failed`/`skipped`；失败带 `upstream_error_type`、`base_url_host` |

### 5.3 导入

| 事件 | 必填 | 说明 |
| --- | --- | --- |
| `asr_readiness_checked` | `provider`, `blocked`, `has_subtitle` | 探针与提交都发；`code` 有则带 |
| `studio_import_requested` | `source_type`, `material_origin` | 用户提交 |
| `studio_import_accepted` | 同上 | 后端已建项目 |
| `studio_import_request_failed` | `error_code` | 未建项目 |

### 5.4 处理阶段

| 事件 | 必填 | 说明 |
| --- | --- | --- |
| `studio_screen_finished` | `outcome` | 初筛结束。失败必带 `error_code`+`failure_stage` |
| `llm_request_finished` | `provider`, `kind`, `outcome`, `duration_ms` | **诊断**，每条模型调用。失败带 `upstream_error_type`、`failure_stage`、`http_status`；同服务商换候选时带 `degrade_count` |

阶段细节看 run 上的 `failure_stage`，不要为每个 pipeline step 再发明一个 finished 事件。

### 5.5 出片

自动出片与确认制作是两条产品路径，**都算一次出片尝试**。

| 事件 | 必填 | 说明 |
| --- | --- | --- |
| `studio_confirm_requested` / `_accepted` | `analysis_mode` | 仅确认制作路径 |
| `studio_generation_finished` | `outcome` | 自动出片终态：`success` / `partial` / `error`；可选 `trigger`（`initial` / `retry` / `variant_retry`，取自后端回执）。枚举里仍有 `append_platform`，但 1.5.7 不产生该值：追加平台留到 1.5.9 |
| `studio_production_finished` | `outcome` | 确认制作终态 |

失败两者都必须有 `error_code`、`failure_stage`；模型失败加 `provider`、`base_url_host`、`upstream_error_type`、`http_status`、`billable_calls_before_failure`。身份按 **本次 run 实际调用**，不用设置页最后保存值。

多目标尝试（R23 #228）有多个失败原因时，`error_code` / `upstream_error_type` 是主原因（产品类优先，同类取最早失败），其余原因放在两个可选字段，两个终态事件都可带，`event_catalog.json` 里登记在 `optional_properties`：

| 字段 | 说明 | 取值白名单 | 格式 |
| --- | --- | --- | --- |
| `secondary_error_codes` | 其余失败目标的 `error_code`，按失败顺序 | `enums.studio_error_code` 加 `http_4xx`/`http_5xx`；不在单内发 `unknown` | 英文逗号拼接，最多 3 个，无空格，例 `authentication,timeout` |
| `secondary_upstream_error_types` | 与上一字段同位置的 `upstream_error_type` | `enums.upstream_error_type`；没有或不在单内留空 | 英文逗号拼接，与上一字段等长，例 `invalid_key,` |

这两个字段只做诊断，**不进**成功率分母口径。页面提示用的 `secondary_failure_stages` 只存在分析记录里，不上报。

### 5.6 导出 / 下载

| 事件 | 必填 | 说明 |
| --- | --- | --- |
| `studio_export_requested` / `_accepted` | — | 提交渲染 |
| `studio_export_finished` | `outcome` | 渲染终态 |
| `studio_download_requested` | `download_mode` | 用户要文件 |
| `studio_download_saved` | `download_mode` | **仅原生落盘成功** |
| `studio_download_failed` | `error_code` | 原生保存失败 |

浏览器下载只有 `requested`，不能当交付成功。

### 5.7 回访

不单独发明 `user_returned`。用 `app_opened` 做留存：

- D1 / D7：安装后第 1 / 7 天是否再次 `app_opened`
- 出片后回访：首次 `studio_generation_finished|studio_production_finished` 且 `outcome_canon=success` 之后 7 日内是否再次 `app_opened`

### 5.8 触发点（文件 + 函数）

发送层必须 catch：埋点失败不得改变产品行为。开关关闭或无 key 时，下列函数仍可被调用，但**不得发网络请求**（见 §10.1）。

| 事件 | 何时 | 文件 | 函数 |
| --- | --- | --- | --- |
| `app_installed` / `app_opened` / `app_updated` | 桌面启动；安装只发一次 | `frontend/src/analytics/lifecycle.ts` | `trackLaunch` |
| `setup_presented` / `setup_action` | 引导实际显示 / 用户点稍后、去设置或赞助商一键获取 | `frontend/src/features/settings/FirstRunSetup.tsx` → `experience.ts` | `trackExperience` |
| `import_blocked` | 未配置服务商就被导入挡住 | `frontend/src/features/studio/CreativeImport.tsx` | `trackExperience('import_blocked', …)` |
| `settings_section_viewed` | 打开设置分区 | `frontend/src/pages/SettingsPage.tsx` | `trackExperience` |
| `provider_configuration_save_*` / `provider_connection_test_*` | 设置页保存 / 连接测试 | `frontend/src/analytics/experience.ts` | `beginExperience` |
| `provider_validation_finished` | 保存前真实小请求终态（线 B 挂钩） | `backend/core/llm_emit.py`（预留） | `emit_provider_validation_finished` |
| `asr_readiness_checked` | 导入页探针变化；以及后端受理导入/初筛 | 前端 `CreativeImport.tsx` → `studio.ts`；后端 `backend/services/studio/jobs.py` | `trackAsrReadiness` / `emit_asr_readiness_checked`（`inspect_project`） |
| `studio_import_requested` / `_accepted` / `_request_failed` | 用户提交导入 | `frontend/src/analytics/studio.ts` | `observeStudioOperation('studio_import', …)` |
| `studio_screen_finished` | 观察器看到初筛终态 | `frontend/src/analytics/workflow.ts` | `WorkflowTracker.observeStudio` |
| `llm_request_finished`（text） | 每一次 `LLMProvider.call` 返回或抛错 | `backend/core/llm_providers.py` → `llm_emit.py` | `LLMProvider.__init_subclass__` 包装 → `observe_provider_call` → `request_finished` |
| `llm_request_finished`（vision） | 每一次 `vision_call` 结束 | `backend/services/studio/intelligence.py` | `vision_call` → `emit_vision_request` |
| `degrade_count`（请求级 + run 级） | 同服务商换下一个候选时 +1 | `backend/core/llm_manager.py` → `llm_emit.py` | `note_same_provider_degrade` → `increment_degrade_count`。R1 的降级循环只调这个钩子 |
| run 级字段（挂到现有出片终态，不改事件名） | `studio.json` 写入失败/部分成功身份 | `backend/services/studio/store.py` | `write` → `_ensure_failure_identity` + `_attach_run_telemetry`；上下文 `llm_emit.track_run` |
| `studio_generation_finished` / `studio_production_finished` | 观察器看到出片终态（读 snapshot 上的 run 字段） | `frontend/src/analytics/workflow.ts` + `observer.ts` | `observeStudio` / `startWorkflowObserver` |
| `studio_confirm_*` | 用户确认制作 | `frontend/src/analytics/studio.ts` | `observeStudioOperation('studio_confirm', …)` |
| `studio_export_*` | 提交/完成渲染 | `studio.ts` + `workflow.ts` | `observeStudioOperation` / `observeStudio` |
| `studio_download_requested` / `_saved` / `_failed` | 用户要文件；**仅原生落盘**发 saved | `frontend/src/analytics/studio.ts` | `studioDownloadRequested` / `observeStudioDownload` |
| `studio_qa_checked` | 渲染进程跑完 QA | `backend/services/studio/qa/telemetry.py` | `emit_checked`（须叠信封） |
| `studio_rescreen_*` / `studio_plan_update_*` | 再筛 / 改计划 | `frontend/src/features/studio/api.ts` | `observeStudioOperation` |
| `studio_draft_create_*` / `studio_draft_save_*` / `studio_draft_duplicate_*` | 草稿 | 同上 | `observeStudioOperation` |
| `studio_rewrite_*` | 改写（不报 instruction 正文） | 同上 | `observeStudioOperation` |
| `studio_analysis_preferences_*` | 分析偏好 | 同上 | `observeStudioOperation` |
| `studio_framing_install_*` / `studio_framing_install_finished` | 取景运行时 | `api.ts` + `observer.ts` | `observeStudioOperation` / `emitOnce` |
| `studio_platform_append_*` / `studio_platforms_selected` | 追加平台 / 选择 | `api.ts` / `studio.ts` | `observeStudioOperation` / `trackQuickOutputPlatforms` |
| `studio_post_save_*` | 发布文案保存（不报正文） | `api.ts` | `observeStudioOperation` |
| `studio_variant_*` / `studio_cover_*` / `studio_auto_frame_*` | 变体 / 封面 / 取景 | `api.ts` + `workflow.ts` | `observeStudioOperation` / `observeStudio` |
| `output_branding_save_*` | 设置页片尾开关 | `frontend/src/features/settings/OutputBrandingSetting.tsx` | `beginExperience` |
| `feedback_opened` / `feedback_dismissed` / `feedback_submitted` | 反馈开关与提交 | `frontend/src/analytics/feedback.ts` | `trackFeedbackOpened` / `Dismissed` / `submitFeedback`。提交是用户主动功能：带 `text` / 可选 `contact`，可走 `/capture/`，不看统计开关；界面须告知经 PostHog |
| `mcp_tool_called` / `mcp_job_finished` | MCP 工具 | `backend/services/mcp_telemetry.py` | `record` / `_emit`（须叠信封；`version`→`app_version`） |
| Sentry `user.id` = PostHog `distinct_id` | 前端拿到匿名 ID 后 | `frontend/src/analytics/posthog.ts` → `PUT /settings/analytics-identity` → `qa/telemetry.py` → `sentry_setup.py` | `publishAnonymousId` / `remember_distinct_id` / `sync_anonymous_user`；前端 `setAnonymousUser` |

`llm_request_finished`、run 级字段、`asr_readiness_checked`、身份对齐、schema 校验是线 A 纯埋点 PR 要挂钩的部分；挂钩位置以本表为准，不得另开入口。`prompt` / `input_data` / 转写正文只留在被调用函数内，不得传入发送层。

---

## 6. 核心指标口径

口径 **v4**。窗口用固定 UTC 日期参数 `{date_from}`（含）/ `{date_to}`（不含）（报某版本时一般取发布日起 7 天），过滤：

```
analytics_environment = production
runtime = desktop                      -- 主指标；web 可另列
person_id NOT IN COHORT {internal_cohort_id}
-- version_releases 里的版本再加发布时间下限（含）：
--   timestamp >= toDateTime(released_at, 'UTC')
-- 1.5.7 的 released_at 是参数 {release_1_5_7}。执行 Promote 的人把 GitHub Release
-- published_at（UTC，YYYY-MM-DDTHH:MM:SSZ）写成 'YYYY-MM-DD HH:MM:SS' 填进 PostHog insight，
-- 不写进仓库。空字符串表示该版本先全部排除。
-- 1.5.6 及更早不在表里。
```

不在过滤里写死 `app_version`：按版本看用 [`success_rate.sql`](success_rate.sql) 图 5（每个 `app_version` 一行，按次 / 按流程、全量 / 产品、partial-delivery 率；流程归到其最后一次 attempt 的版本）。表 `version_releases` 里的版本只统计正式发布之后（含发布时间）的事件。

`partial` 算出片未成功（分子只认 `outcome_canon=success`），另列 **partial-delivery 率** = `partial` 次数 / 产品口径分母。

分母为 0（稀疏日期、版本或空窗口）时所有比率返回 NULL（`nullIf(分母, 0)`），不返回 NaN 或 0。线上看板（PostHog insight）合入后同步为本仓库 SQL；同步前线上旧 SQL 在分母为 0 时仍可能显示 NaN。示例→真实出片转化（`production_results.sql` 04）的样例设备和真实出片两侧都排除内部 cohort（641509，目前为空名单，结果不变）。

### 6.1 成功率（v4，2026-10-16；主指标，目标 ≥95%）

机器可读口径：`event_catalog.json` → `attribution.success_rate_v4`；SQL：[`success_rate.sql`](success_rate.sql)（两者必须一致，有测试）。

- **一次尝试（attempt）** = `studio_generation_finished` / `studio_production_finished` 按 `attempt_id` 去重后取最后一条（缺 `attempt_id` 的历史行按事件 uuid 计）。重试是新的 attempt。
- **一次流程（flow）** = 沿 `retry_of` 回溯到重试链根（最多 4 跳），用根 attempt 的 `flow_id` 作流程键；结果取该流程 / 重试链里 **最后一次** attempt（最终结果口径）；“最后”的排序键是 `(attempt_sequence, leaf, ts)`：先按终态事件的 `attempt_sequence`（后端回执 `sequence`，项目内严格递增，#419；没有序号按 0，有序号的 attempt 总排在旧 attempt 后面），其次看 `leaf`（`retry_of` 链末端 = 没有再被重试的那次），`ts`（观察时间）只用来打平，事件乱序到达不改结果（R25 #346）。**旧数据（#419 之前，没有 `attempt_sequence`）**：单 attempt 的流程、`retry_of` 链完整的流程照常计算，结果和改前一样；同一 flow 有多次 attempt 又没有链能证明哪次最后（多个链末端）的流程记为未知，不进图 1 / 图 5 的流程分子分母，单独输出 `unknown_flows`；attempt 级成功率不受影响（R26 #362）。`retry_of` = 被重试 attempt 的 `attempt_id`（失败态「重试」按钮产生）。**与 #416 的关系**：#416 的 SQL 用 `coalesce(retry_of, '')`，`attempt_sequence` 缺省按 0。没有 `retry_of` 时每次终态各自成 flow，不串链、不报错，因此 #416 可以单独合入 RC，也可以先于 #419。本 PR 才发出 `retry_of` 和 `attempt_sequence`；在那之前流程率等于按次（各自成 flow），不是「重试链最后一次」。看板要按重试链取末次时，用合入本 PR 之后的 `success_rate.sql`。
- **一个人** = `person_id`（不是 `distinct_id` / 设备）。
- **窗口** = 固定 UTC 日期参数 `{date_from}`（含）/ `{date_to}`（不含），不再用 `now() - 7d`。
- **过滤** = `analytics_environment = production`、`runtime = desktop`、排除内部 cohort `{internal_cohort_id}`（450605 为 641509）。表 `version_releases` 里的版本另加发布时间下限：`{release_1_5_7}` 由执行 Promote 的人在贴 SQL 时填写。GitHub Release `published_at`（UTC，形如 `YYYY-MM-DDTHH:MM:SSZ`）写成 `'YYYY-MM-DD HH:MM:SS'`（去掉 `T` 和 `Z`，含该时刻）；空字符串则该版本全部不计入。1.5.6 及更早不在表里。
- **全量成功率** 分母只剔除明确的用户行为：`outcome = cancelled`；`error_code ∈ (authentication, llm_auth_invalid, invalid_key, insufficient_quota, llm_not_configured, cancelled, user_cancelled)`；`upstream_error_type ∈ (invalid_key, insufficient_quota, permission_denied)`。
- **产品成功率** 在全量基础上再剔除：`error_code ∈ (connection, source_too_short, source_no_audio, source_unreadable, source_blocked, source_not_found)`。
- 两个口径都算 **产品失败**（不剔除）：`whisper_not_installed`、`service_restarted`、`model_not_found`、`bad_endpoint`。
- 每个口径都报 **按次** 与 **按流程** 两个率；`outcome_canon = success` 一律算成功，忽略错误字段。

按服务商拆分用事件上的 `provider`（本次 run 的目录 slug），**禁止**再用「最后保存的 provider」近似。

### 6.2 按人首次出片成功率

按 `person_id` 取窗口内第一条 **合格** attempt（按对应口径：全量 / 产品），是 `success` 则分子 +1。没有合格 attempt 的人不进分母。

不要用「曾经成功过的人数 / 打开过应用的人数」冒充本指标——那是激活，不是首次出片成功率。

### 6.3 漏斗（辅助，不替代 6.1）

同一 `person_id`、固定 UTC 窗口 `{date_from}` / `{date_to}`（与 §6.1 一致），步与步之间允许不等待：

1. `app_opened`
2. `provider_validation_finished` 且 `result=success`（1.5.7 线 B 上线前，暂用 `provider_connection_test_finished` 且 `outcome_canon=success`）
3. `studio_import_accepted`
4. `studio_screen_finished` 且 `outcome ∈ (recommended, auto_started, manual)`
5. 出片终态 `outcome_canon=success`
6. **保存（save）**：`studio_download_saved`（原生下载落盘，带 `artifact_id`）或 `studio_export_finished` 且 `outcome_canon=success`（带 `artifact_id`）。浏览器内下载、`studio_download_failed`、未带 `artifact_id` 的行不算保存。按 `person_id` 计一次。

每步转化用漏斗图，不把诊断事件插进主漏斗。

---

## 7. PostHog 成功率看板配置

新建看板，名称建议：**AutoClip｜1.5.7 出片成功率**。不要改 2026-09-30 Studio V2 看板的历史口径。项目：`450605`。

公共过滤（每张 insight 都加，v4）：

- 事件属性 `analytics_environment = production`、`runtime = desktop`
- 排除内部 cohort `{internal_cohort_id}`（450605 为 641509）
- 日期：固定 UTC 区间 `{date_from}` / `{date_to}`，写在图题里；不用滚动 7 天
- `version_releases`：1.5.7 只统计 `{release_1_5_7}` 及之后的事件。执行 Promote 的人把 GitHub Release `published_at`（UTC，`YYYY-MM-DDTHH:MM:SSZ`）写成 `'YYYY-MM-DD HH:MM:SS'` 后贴进 insight；空字符串则这一版先全部排除。1.5.6 及更早不在表里
- 不加 `app_version` 过滤，按版本看图 11（`success_rate.sql` 图 5）

| # | 图 | Insight 类型 | 事件 | 过滤 / 拆解 | 公式或读法 |
| --- | --- | --- | --- | --- | --- |
| 1 | 按日 按次 / 按流程成功率（全量 + 产品）+ partial-delivery 率 | SQL insight | `studio_generation_finished` + `studio_production_finished` | `success_rate.sql` 图 1 | attempt 去重；flow 沿 `retry_of` 取最后一次 attempt；分母按 §4.3 v4 |
| 2 | 按人首次出片成功率 | SQL insight | 同上 | `success_rate.sql` 图 2 | 按 `person_id`（不是 `distinct_id`）取第一条合格 attempt |
| 3 | 按服务商按次成功率 | SQL insight，按 `provider` 分组 | 同上 | 图 1 的 base / c，加 `provider` | 事件上的 run `provider` slug；不要用设置页 provider |
| 4 | 按 `failure_stage` × `error_code` × 归因 | SQL insight | 失败的出片终态（attempt 去重） | `success_rate.sql` 图 3 | 表格；`unexpected` 要下钻 `llm_request_finished` |
| 5 | 按 `upstream_error_type` | Trends | `llm_request_finished` | `outcome=error`，breakdown `upstream_error_type`、`provider` | 诊断用，不是 6.1 分母 |
| 6 | 配置→能跑 | Funnel | `app_opened` → `provider_validation_finished` (`result=success`) → `studio_import_accepted` | 生产 + 版本 | 线 B 上线后主看 |
| 7 | 导入→出片 | Funnel | `studio_import_accepted` → `studio_screen_finished` → 出片 `outcome_canon=success` | `material_origin=user` | 真实素材，排除 sample |
| 8 | 出片→落盘 | Funnel | 出片 `outcome_canon=success` → `studio_download_saved` | `download_mode=native` | 浏览器下载不进 |
| 9 | D7 回访 | Retention | `app_opened` | 起始事件 `app_installed` 或首次出片成功 | 第一列 D1、第七列 D7 |
| 10 | 收数健康 | Trends | 核心事件列表 | 按 event 分列 | 无收数先查同意/发布，不判产品失败 |
| 11 | 按版本成功率 | SQL insight | 同图 1 | `success_rate.sql` 图 5 | 每个 `app_version` 一行；与图 1 同一口径 |

图 1–4、11 的 HogQL 见 [`success_rate.sql`](success_rate.sql)（v4：attempt 去重、flow 沿 `retry_of` 取最后一次 attempt、`person_id`、固定 UTC 窗口、内部 cohort 参数、全量/产品双口径、partial-delivery 率、按版本）。该 SQL 在 CI 里用 DuckDB 对合成数据真实执行（`backend/tests/test_success_rate.py`）。本文件不再复制 SQL，避免两份漂移。

可审查 SQL 副本放在 `docs/analytics/success_rate.sql`（与本规范一起落地）。线上看板建好后把 insight 链接回写本节，仿照 [`dashboards-20260930/README.md`](dashboards-20260930/README.md)。

---

## 8. 现有事件盘点与迁移

盘点范围：`origin/main` 上前端 `captureBusinessEvent` / `posthog.capture` / `observeStudioOperation` / `observeOperation` / `beginExperience` / `emitOnce` / `events.ts` wrapper，后端 `qa.telemetry` / `mcp_telemetry` / `llm_emit`。`template_telemetry` 只产属性。Tauri/`src-tauri` 无埋点。`$pageview`、`$identify`、PostHog `survey *` 不算业务目录。完整名录见 [`event_inventory.json`](event_inventory.json)。

### 8.1 保留（漏斗或诊断仍要用）

| 事件 | 角色 | 动作 |
| --- | --- | --- |
| `app_installed` / `app_opened` / `app_updated` | 生命周期 | 保留；`os` 只报 macos/windows/linux |
| `setup_*` / `import_blocked` / `settings_section_viewed` | 引导 | 保留 |
| `provider_configuration_save_*` / `provider_connection_test_*` / `model_settings_load_*` / `model_discovery_*` / `output_branding_save_*` | 设置 | 保留；线 B 后主看 `provider_validation_finished` |
| `studio_import_*` / `studio_screen_finished` / `studio_confirm_*` / `studio_generation_finished` / `studio_production_finished` | 主漏斗 | 保留；补 run 级字段（线 A / #361） |
| `studio_export_*` / `studio_download_*` | 交付 | 保留 |
| `asr_readiness_checked` / `llm_request_finished` / `provider_validation_finished` | 1.5.7 成功率 | 保留 |
| `studio_rescreen_*` / `studio_plan_update_*` / `studio_variant_*` / `studio_cover_*` / `studio_auto_frame_*` | 编辑/重试 | 保留，不进主漏斗 |
| `studio_draft_create_*` / `studio_draft_save_*` / `studio_draft_duplicate_*` / `studio_rewrite_*` | 草稿/改写 | 保留，不进主漏斗；不报标题/instruction |
| `studio_analysis_preferences_*` / `studio_framing_install_*` / `studio_platform_append_*` / `studio_platforms_selected` / `studio_post_save_*` | Studio 设置与包装 | 保留，不进主漏斗 |
| `social_publish_*` | 发布 | 保留；`scheduled`/`inbox` 不算 success |
| `studio_qa_checked` / `studio_template_*` / `studio_output_rated` / `studio_output_shared` | 质量与包装 | 保留，诊断；QA 须叠信封 |
| `mcp_tool_called` / `mcp_job_finished` | MCP | 保留，独立域；须叠信封 |
| `feedback_opened` / `feedback_dismissed` / `feedback_submitted` | 反馈 | 保留。`feedback_submitted` 是用户主动提交：允许 `text` / 可选 `contact`，可走 `/capture/`；须有 PostHog 告知文案 |
| `example_project_open_*` / `example_project_viewed` | 示例 | 保留；`material_origin=sample` 不进真实出片率 |
| `sponsor_link_opened` | 增长 | 保留，不进成功率 |

### 8.2 重复或命名不一（迁移 / merge）

| 现状 | 问题 | merge / 查询 | 停发 |
| --- | --- | --- | --- |
| `provider_test_requested/accepted/request_failed` + `provider_test_finished`（`api.ts` 旧设置） | 与 `provider_connection_test_*` 重复；多一个 `accepted` | **废弃 `provider_test_*`**。`requested`→`provider_connection_test_requested`；`finished`→`provider_connection_test_finished`（`failed`→`error`）。`accepted`/`request_failed` 无对应 verb，只作诊断 | **1.5.7** |
| `import_requested/accepted/request_failed` + `import_finished`（旧 `/projects/upload`） | 与 `studio_import_*` 并行 | 继续发时打 `legacy=true`。漏斗只用 `studio_import_*` | **1.5.7** |
| `processing_requested/accepted/request_failed` + `processing_started/finished/task_observed` | 旧内容管线；与 Studio `failure_stage` 重叠 | 冻结，打 `legacy=true`。成功率不读 | **1.5.7** |
| `processing_failed` | 裸失败，无 run 身份 | 查询忽略；改为 no-op | **1.5.7**（能提前则提前） |
| `media_download_*` vs `studio_download_*` | 两套下载 | 新交付只看 `studio_download_*`。旧剪辑页继续发时打 `legacy=true` | **1.5.7** |
| `publish_export_requested/accepted/request_failed` + `publish_export_finished`（`api.ts` 旧发布导出） | 与 `studio_export_*` / `social_publish_*` 并行，规范此前漏行 | **废弃。** 查询：`publish_export_requested`→`studio_export_requested`；`publish_export_finished`→`studio_export_finished`（`outcome` 按 §2.3）。新发布看 `social_publish_*`。打 `legacy=true` | **1.5.7** |
| `clips_exported` | 名字像导出成功，实际是旧下载触发 | 查询忽略；不要当北极星 | **1.5.7** |
| `video_imported` | 与 `studio_import_accepted` 重复 | 查询忽略 | **1.5.7** |
| `api_key_configured` | 保存 key 就发 | 用 `provider_configuration_save_finished` + `provider_validation_finished`。代码已无调用点 | **1.5.7** 删 wrapper |
| `example_project_opened` | 过早触发 | 已被 `example_project_open_*` / `example_project_viewed` 替代。代码已无调用点 | **1.5.7** 删 wrapper |
| `outcome=completed` vs `success` | 两套成功值 | 查询用 §2.3 `outcome_canon` | 生产者 **1.5.7** 只发规范值 |
| `os=darwin/win32` vs `macos/windows` | 两套系统名 | 查询用 §4.4 `os_canon` | 生产者 **1.5.7** 只发规范值 |
| `version` vs `app_version` | 生命周期 / MCP 仍带 `version` | `coalesce(app_version, version)` | **1.5.7** 停发 `version` |
| `error_type` vs `upstream_error_type` | 线 A 校验钩子曾用过 `error_type` | **只报 `upstream_error_type`** | 已禁止 |

`legacy=true`：上表在 1.5.7 要么停发，要么每条带此布尔；Studio 路径永不带。#361 不改旧事件。

### 8.3 无用或易误导（废弃）

| 事件 | 原因 | 停发 | 删代码 |
| --- | --- | --- | --- |
| `clips_exported` | 语义错误 | 1.5.7 | 1.5.7 |
| `video_imported` | 被 Studio 导入替代 | 1.5.7 | 1.5.7 |
| `processing_failed` | 无阶段、无归因 | 1.5.7 | 1.5.7 |
| `api_key_configured` | 不能代表可出片 | 已不发 | 1.5.7 |
| `example_project_opened` | 已被替代 | 已不发 | 1.5.7 |
| `provider_test_*` | 被 `provider_connection_test_*` 替代 | 1.5.7 | 1.5.7 |
| `publish_export_*` | 被 `studio_export_*` / `social_publish_*` 替代 | 1.5.7 | 1.5.7 |
| `import_*` / `processing_*` / `media_download_*`（旧路径） | 被 Studio 替代 | 1.5.7 | 1.5.7 |

停发后看板过滤 `event not in (...)`。PostHog 隐藏废弃事件。#361 **不删不改名**。

### 8.4 缺口（本规范要求补齐，按线落地）

| 缺口 | 谁做 | 状态 |
| --- | --- | --- |
| 模型单次 `llm_request_finished` | 线 A #361 | 代码已写，等规范确认后合 |
| run 级 provider/错误身份 | 线 A #361 | 同上 |
| `asr_readiness_checked` | 线 A #361 | 同上 |
| Sentry / PostHog id 对齐 | 线 A #361 | 同上 |
| `provider_validation_finished` 挂钩 | 线 A 预留，线 B 调用 | 发射函数预留 |
| 后端线 A 事件补信封 | 线 A #361 | 新增字段；不改已有 `darwin`/`win32` |
| 事件目录对照本清单 | 线 A #361 + `check_tracking_inventory.py` | catalog 必须覆盖 inventory |
| QA / MCP / 反馈公共信封、`version`→`app_version` | 1.5.7 清理 PR | §12.1 T3 / T4 |
| feedback 告知文案（经 PostHog 送达 `text`/`contact`） | #361 | Kris：用户主动提交，不是隐私泄漏 |
| 旧事件停发或打 `legacy=true`；删死 wrapper | 1.5.7 清理 PR | §12.1 T5 |
| `os` / `outcome` / `app_version` 生产者统一 | 1.5.7 清理 PR | §12.1 T1 / T2 / T3 |
| `backend_exit`（#1 续跑） | 1.5.9 | 本版不发 |
| 线上看板 insight | 埋点上线后由负责人建 | 本文件 §7 |

---

## 9. 校验合同

[`event_inventory.json`](event_inventory.json) 是本规范的机读清单（单一来源）。#361 的 `event_catalog.json` 是生产者登记表：字段、`required`、`enums`、隐私夹具在 catalog；**事件名与 status 必须与 inventory 一致**。`scripts/check_tracking_inventory.py` 在 catalog 存在时做双向对照，漂移即失败。`backend.__version__ >= 1.5.7` 时同一脚本再扫生产者，强制 §12.1 五条验收。

校验测试必须失败，当：

1. 生产者出现 **未登记** 的业务事件名（`captureBusinessEvent`、`_post_event`、`qa.telemetry` 的 `event` 字段）。
2. 已登记事件的一次发送 **缺必填字段**（目录里 `required`；含 `required_when`）。
3. 字段值不在闭集（`enums`）或不满足类型。
4. 载荷含违禁 **属性名** 或违禁 **属性值**（§10–§11）。sanitize 之后仍含这些值，或未 sanitize 就发送，都算失败。

`event_catalog.json` 的 `privacy` 必须能被测试直接读出，至少包括：

```json
{
  "forbidden_keys": [
    "api_key", "authorization", "password", "prompt", "caption",
    "transcript", "transcription", "subtitle_text", "title", "video_title",
    "filename", "file_name", "file_path", "path", "base_url"
  ],
  "forbidden_substrings": [
    "sk-", "bearer ", "api_key=", "token=",
    "/Users/", "/home/", "C:\\Users\\", "C:/Users/"
  ],
  "forbidden_value_patterns": [
    "https?://\\S+/\\S+",
    "(?i)\\.(mp4|mov|mkv|webm|m4a|mp3|wav|srt|vtt|ass)$"
  ],
  "forbidden_value_samples": [
    "sk-abc123deadbeef",
    "/Users/xxx/Movies/talk.mp4",
    "C:\\Users\\xxx\\Videos\\interview.mov",
    "我的旅行vlog",
    "talk.mp4",
    "大家好今天我们来聊",
    "Write a viral title for:"
  ]
}
```

下列夹具对 `validate_event("llm_request_finished", payload)`（或任意已登记事件）**必须失败**。合法基线只含枚举/计数；在其上叠加一行即红：

| # | 叠加 | 拦住的类 |
| --- | --- | --- |
| 1 | `"api_key": "sk-abc123deadbeef"` | key（属性名 + 值） |
| 2 | `"authorization": "Bearer sk-abc"` | key |
| 3 | `"model": "sk-abc123deadbeef"` | key 出现在允许字段里 |
| 4 | `"path": "/Users/xxx/Movies/talk.mp4"` | 带用户名的本机路径（macOS） |
| 5 | `"file_path": "C:\\Users\\xxx\\Videos\\interview.mov"` | 带用户名的本机路径（Windows） |
| 6 | 任一字符串值含 `/Users/xxx` 或 `C:\\Users\\xxx` | 路径渗进任意字段 |
| 7 | `"title": "我的旅行vlog"` 或 `"filename": "talk.mp4"` | 视频标题 / 文件名 |
| 8 | `"caption": "大家好今天我们来聊"` | 转写 / 字幕 |
| 9 | `"prompt": "Write a viral title for:"` | 提示词 |
| 10 | `"transcript": "大家好今天我们来聊"` | 转写文本 |
| 11 | `"base_url": "https://api.openai.com/v1/chat/completions"` | 完整 URL；只允许 `base_url_host` |
| 12 | `"base_url_host": "https://api.openai.com/v1"` | host 字段仍带 scheme/path |

测试位置：`scripts/check_tracking_inventory.py`、`backend/tests/test_event_catalog.py`、`frontend/tests/event-catalog.test.cjs`。新增事件必须同时改本文件、`event_inventory.json`、（#361 起）`event_catalog.json` 和测试。

`$` 前缀、PostHog survey 事件、以及测试里故意使用的假名（`disabled`、`test`）不在目录里，扫描时排除。

---

## 10. 隐私硬性要求（PM / Kris）

上报内容一律不得含：**key**、**带用户名的本地路径**（`/Users/xxx`、`C:\Users\xxx`）、**视频标题 / 文件名**、**转写文本**、**提示词**。`base_url` **只保留 host**（本机/内网记 `local`）。这五类值出现在任意属性名或任意字符串值里，schema 校验必须失败。

产品默认开埋点。用户关掉后，或构建未配置 PostHog key 时，**业务事件一条也不许出网**。

**`feedback_submitted` 例外（`user_submitted`，Kris，2026-10-14）：** 用户点「发送」是主动把这句话交给我们，不是静默采集。该事件**可以**带 `text` 和可选 `contact`，**可以** POST `/capture/`，且**不看**匿名统计开关。`scripts/ingest_app_feedback.py` 读取这两列自动开 GitHub Issue / Discussion，这条链路保留。没有 PostHog key 或网络失败时，才打开预填的 GitHub 页。界面必须写明：内容和联系方式会发送给开发者，用于回复和创建 GitHub Issue。`feedback_opened` / `feedback_dismissed` 不带正文。其它自动采集事件仍不得报用户正文、邮箱或自由文本。

### 10.1 开关关闭时的行为

| 开关 | 存在哪 | 关闭后 |
| --- | --- | --- |
| 设置页「使用分析」 | 前端 `setAnalyticsEnabled(false)` → `localStorage` 键 `autoclip.analytics.optOut=true` | `isAnalyticsEnabled()` 为 false；`captureBusinessEvent` 直接 return；`posthog.opt_out_capturing()`；停 flag 网络；`syncSentryUser(null)`；**不再** `PUT /settings/analytics-identity`；观察器 `workflow.clear()` |
| 未配置 `VITE_PUBLIC_POSTHOG_KEY` | 构建 | `initAnalytics` 不初始化 SDK，零网络 |
| `privacy.json` 的 `analytics: false` | 桌面数据目录（与崩溃报告同文件） | 后端 `qa.telemetry._analytics_allowed()` / MCP 发送 / `llm_emit._post_event` 全部 no-op |
| 崩溃报告另开 | `privacy.json` `crash_reports`；前端 `autoclip.crashReports.optOut` | 与分析开关独立；分析关时 Sentry 仍不得带 PostHog id 去「补发」业务事件 |

关闭时允许：生产者函数被调用、本地算脱敏字典、写测试夹具。禁止：对 `us.i.posthog.com`（或自建 host）发**业务** capture/identify/flag；把未发送的事件缓冲到以后再补发。打开开关后只收**之后**的事件。

例外：用户点发送的 `feedback_submitted` 仍可出网（§10），不看此开关。

无 key 的开发构建与用户关闭同等对待：不污染线上。

### 10.2 一律不得出现在上报里（硬性）

| 类 | 例子 | 怎么处理 |
| --- | --- | --- |
| key | `sk-…`、`Authorization`、`Bearer`、`api_key=`、`token=` | 属性名丢弃；任一字符串值含这些标记则整键丢弃，`validate_event` 失败 |
| 带用户名的本机路径 | `/Users/xxx/Movies/talk.mp4`、`C:\Users\xxx\Videos\interview.mov`、`/home/xxx/…` | 不报 `path` / `file_path`；任一值含 `/Users/`、`/home/`、`C:\Users\`、`C:/Users/` 则失败 |
| 视频标题 / 文件名 | `我的旅行vlog`、`talk.mp4`、`interview.mov` | 没有 title/filename 字段；白名单丢掉自由文本；值匹配媒体扩展名则失败 |
| 转写文本 | 字幕、口播、`caption`、`transcript`、「大家好今天我们来聊」 | 只报 `has_subtitle: bool`；正文键和样本句必须失败 |
| 提示词 | `prompt`、模型 system/user 原文、`Write a viral title for:` | `prompt` / `input_data` 只留在 `LLMProvider.call` / `vision_call` 内，不传入发送层 |
| 完整 URL | `https://api.openai.com/v1/chat/completions?key=…` | **禁止**属性名 `base_url`。只报 `base_url_host`，且值只能是 host 或 `local` |

另外不上报：email、具体 IP（本机/局域网 → `local`）、模型响应原文、内部 `project_id` / `run_id` / `job_id`（新事件）。Sentry 只对齐 `user.id` = `distinct_id`。

---

## 11. 每个字段怎么脱敏

实现必须调用已合入 #354 的 helper，不要手写第二套：

- 后端：`backend.core.llm_telemetry.hostname_of_base_url` / `sanitize_model` / `sanitize_*_properties`
- 前端：`frontend/src/analytics/successRateContract.ts` 的同名函数；Studio 事件再过 `safeStudioProperties`
- 上游分类：`backend.core.upstream_errors.classify_upstream_error`（只把枚举写入事件）

**主策略是白名单。** 未列出的键全部丢掉——这是挡住标题、文件名、转写、提示词的第一道。第二道是 §9 对键名、子串、扩展名、样本句的扫描。

| 字段 | 允许值 | 脱敏方式 | 遇到硬性违禁时 |
| --- | --- | --- | --- |
| `base_url` | **不上报** | 禁止该键 | 有此键 → 校验失败 |
| `base_url_host` | 域名或 `local` | `hostname_of_base_url(raw)`：只取 host；丢掉 scheme / path / query / userinfo；localhost、内网、`0.0.0.0`、`host.docker.internal` → `local` | 输入是 URL、`/Users/xxx`、`C:\Users\xxx` 或含 `sk-` → 输出空；若仍把原值发出 → 失败 |
| `model` | `^[\w.\-:/]{1,64}$` | `sanitize_model` | 含 `sk-`、空格、路径、标题 → 丢弃 |
| `provider` | 闭集（含 ASR 三值） | `sanitize_provider` | 自由文本（可能是路径或标题）→ 丢弃 |
| `kind` / `outcome` / `result` / `finish_reason` / `failure_stage` / `upstream_error_type` / `error_code` / `source_type` / `material_origin` / `download_mode` / `analysis_mode` / `os` / `runtime` / `analytics_environment` 以及 `safeStudioProperties` 里的其它枚举 | 各自闭集 | 枚举校验，不在闭集则不写 | 标题/转写/路径进枚举字段 → 不匹配闭集，丢掉；若硬写出发 → 失败 |
| `http_status` | 100–599 的整数 | 范围裁剪 | 不接受字符串（避免 URL/路径） |
| `duration_ms` / `*_tokens` / `llm_calls` / `retry_count` / `degrade_count` / `billable_calls_before_failure` / `session_number` | 非负整数 | 转 int | 附带的说明文字丢掉 |
| `has_subtitle` / `blocked` / `ok` | 布尔 | `bool()` | **不报**字幕内容 |
| `code`（ASR） | `^[a-z][a-z0-9_]{1,64}$` | 只报就绪探针 code | 探针 message / 转写丢掉 |
| `distinct_id` | 匿名 ID 正则 | `ANONYMOUS_ID` | email、`/Users/xxx`、`../` → 拒绝 |
| `app_version` | `MAJOR.MINOR.PATCH` | 去 `v` 前缀 | 构建路径丢掉 |
| `flow_id` / `operation_id` / `attempt_id` / `artifact_id` | `t-[a-z0-9-]{10,100}` | 格式校验 | 文件名、内部 UUID 不匹配则丢掉 |
| `prompt` / `caption` / `transcript` / `title` / `filename` / `path` / `file_path` | **不上报** | 白名单外，发送前删除 | 残留 → §9 夹具失败 |
| 任意未列字段 | — | **丢掉** | 同上 |

对照：

```
hostname_of_base_url("https://api.openai.com/v1/chat/completions?key=sk-abc")  →  "api.openai.com"
hostname_of_base_url("/Users/xxx/models")                                      →  None
hostname_of_base_url("C:\\Users\\xxx\\AppData\\api")                           →  None
sanitize_model("sk-abc123deadbeef")                                           →  "redacted"
sanitize_model("https://api.openai.com/v1")                                   →  "redacted"
sanitize_llm_request_properties({prompt: "…", title: "我的旅行vlog"})         →  不含这两键
```

Schema 测试必须用 §9 的 12 条夹具证明：sanitize 之后仍含这五类值，或未 sanitize 就发送，都失败。

---

## 12. 过渡计划（1.5.7 收口）

以本文件日期 **2026-10-14** 为起点。**过渡保留**：查询继续用 §2.3 / §4.4 映射，覆盖此前内部测试包及更早公开版本里的 `completed` / `darwin` / `win32` / `version`。旧 1.5.7 测试包与正式包的成功率按 [`success_rate.sql`](success_rate.sql) 的 `{release_1_5_7}` / `version_releases` 切开：只统计该版本 GitHub Release `published_at`（UTC）及之后的事件。事件上没有 commit 或构建时间。**收口在本版 1.5.7**：该版本必须让所有生产者只发规范值，并停发或标记旧事件。生产者收口不靠日历日，不靠「观察期延长」。

| 节点 | 做什么 | 谁 |
| --- | --- | --- |
| 2026-10-14 | 本文件成为唯一准绳；`ANALYTICS.md` / `ANALYTICS_V2.md` 标为历史 | 本 PR（#362） |
| 规范确认后 | 合 #361：只加新事件与 catalog，不删旧事件、不改 `darwin`/`win32` | 线 A |
| #361 | 反馈告知文案：发送会先经 PostHog 再公开到 GitHub；`text`/`contact` 是用户主动提交 | 线 A |
| **1.5.7** | 完成 §12.1 五条任务；停发或打标 §8.2 / §8.3；删死 wrapper。`check_tracking_inventory.py` 在 `backend.__version__ >= 1.5.7` 时强制验收 | 清理 PR |

查询从现在起就用 §2.3 / §4.4 映射，这样正式包和历史查询的数字连续。本版 1.5.7 之后还在发、又未打 `legacy=true` 的旧事件名，视为规范违规，扫描应失败。

### 12.1 1.5.7 必须交付（任务 + 验收）

`event_inventory.json` 的 `transition.tasks` 与下表一一对应。`backend.__version__ >= 1.5.7` 时同一脚本扫生产者，任一条未完成即失败。更早的公开版本（1.5.6）不扫生产者。

| ID | 任务 | 验收（`scripts/check_tracking_inventory.py`，`__version__ >= 1.5.7`） |
| --- | --- | --- |
| T1 `single_os_enum` | 全生产者单一 `os`：只发 `macos` / `windows` / `linux`（侦不到才 `unknown`） | `workflow.ts`、`template_telemetry.py`、lifecycle、envelope 的 os 白名单不含 `darwin` / `win32` |
| T2 `single_outcome_enum` | 全生产者单一 `outcome`：出片/设置终态只发 `success` / `error` / `partial` | 生产者 `outcome` 白名单不含 `completed`。screen 仍可用 `recommended` / `auto_started` / `manual` / `fallback`；experience 可用 `blocked`；校验可用 `skipped` |
| T3 `app_version_only` | 版本只报 `app_version`，禁止裸字段 `version` | `app_installed` / `app_opened` / MCP 不再写 `version` |
| T4 `common_envelope` | QA / MCP / 反馈走公共信封 | QA、MCP 调用 `envelope_properties()`。反馈 `/capture/` 载荷必须带同一信封字段（`app_version` / `os` / `analytics_environment` / `runtime` / `schema_version`）。`feedback_submitted` 允许 `text`/`contact`，不看统计开关 |
| T5 `legacy_stopped_or_tagged` | §8.2 / §8.3 旧事件停发，或继续发时每条带 `legacy=true`；死 wrapper 删除 | 仍出现在生产者里的 legacy 事件名，同一文件必须带 `legacy: true` |

机读清单：`dates.close_transition` / `dates.stop_legacy_emit` / `dates.delete_wrappers` 均为 `"1.5.7"`。



### 1.5.7 终态事件身份字段

`studio_screen_finished` / `studio_generation_finished` / `studio_production_finished` 失败时必带 `failure_stage`（含服务重启、IO 失败、调度失败路径）、`upstream_error_type`；全部带 `provider`（目录 slug 或 `other`）与 `config_source`（`preset` = 目录 base URL + 目录模型 id，否则 `customized`）。不发送 URL 或自定义模型名。

身份归因（1.5.7 R22）：`provider` / `config_source` 只有一条规则（`failure_identity.connection_identity`），在**开始时冻结**，结束时不重读设置。
- 阶段：screening 用视觉连接；production/rendering 走视觉路线且目标不全是 content 时用视觉连接，否则用文本连接；确认路线（`confirmed_analysis`）优先于推荐路线。screening 的身份单独存为 `screening_identity`，自动流程里 production 重新冻结不会覆盖它；`studio_screen_finished` 读这一份。
- 一次 generation 尝试中途换阶段时，失败按失败阶段归因：screening 失败报视觉连接，production 失败报路线连接。
- 请求：每个模型请求在**发出前**冻结所用连接，结束时生成一条不可变请求记录（provider/config_source 成对，加上同一次请求的 model/host/http_status/upstream_error_type）。失败的记录随异常携带（沿显式 `__cause__` 链可找回，不看隐式 `__context__`）。R30（I563）起，脱敏边界在安全异常上冻结服务商 HTTP 状态码（`http_status` 字段，和快照同一处构造）；状态码只有一条读取规则：先读这个冻结字段，原始异常才沿 `__cause__` 找。
- 归因（1.5.7 R25）：失败按**出错的那次请求**的记录整条归因（`attribution_source=request`）；找不到请求记录时用阶段开始时冻结的身份（`attribution_source=phase`）；不取"最近一次请求"，运行中不读设置。落盘、run 快照、Sentry 都只读这一条，不逐字段合并。
- 旧记录：provider/config_source 不成对时整组（provider、config_source、model、base_url_host）当空，不补。写盘和读出时都按空处理（R26 #399）。
- `attribution_source`（1.5.7 R26，闭集 `request`/`phase`/`local`，随三个 studio 终态事件、Sentry tag 和 analysis_history 一起上报）：`request` = 失败请求自己的记录；`phase` = 没有请求记录的**模型类**失败，用阶段冻结的连接；`local` = 非模型失败（存储锁超时 `store_lock_timeout`、ffmpeg、本地渲染、请求发出前的本地校验），可带阶段身份但不带请求状态，不算服务商失败。R29（I500）起只查显式异常链 `__cause__`（`raise ... from`），不看隐式 `__context__`。analysis_history 另保留 `model`、`base_url_host`（R26 #400）。
- 归因快照（1.5.7 R29，设计见 `backend/core/failure_attribution.py` 模块说明）：离服务商调用最近、异常链完整的一层调用一次 `build_attribution` 生成快照，之后 dict、线程、store、事件都原样携带，下游不重新判定。脱敏边界（`log_safe_exception`、云端转写、封面）保留 `from None`，快照挂在安全异常（`AttributedError`）的 `.attribution` 上，只含来源、身份、状态码、上游类型、失败阶段，不含消息/URL/正文。连接错误和超时算模型侧（请求已发往服务商），用 `error_code`（`connection`/`timeout`）区分；`http_status` 只在真正收到 HTTP 响应时写。模型返回 200 但内容校验失败抛 `ModelResponseInvalid`，判模型侧，`error_code=invalid_response`。

`service_restarted` 失败另带 `shutdown_kind`，按上次进程在 `<标记目录>/<instance>` 留下的记录分类（标记目录由桌面壳启动时统一解析为 `<应用目录>/shutdown_markers`，经 `AUTOCLIP_SHUTDOWN_MARKER_DIR` 交给后端，壳写 `unacked` 也写这里；无壳运行时为 `<数据目录>/shutdown_markers`）（每个 instance 一条记录、一个目录、一套修剪规则）：

| 值 | 含义 |
|---|---|
| `clean` | 壳通知了正常退出或更新（记录为 `user_quit` / `update`），后端在超时前写好了标记 |
| `parent_lost` | 后端发现桌面壳先没了（壳被杀或崩溃），自己写了 `parent_lost` |
| `crash` | 该 instance 没有任何记录 |
| `unknown` | 壳发了退出通知但 3 秒内没拿到 200，退出前写了 `unacked`（unacked→unknown，不当 crash）；或记录不可读、内容无效、缺少/非法 instance id |

**四种取值都算产品失败**（PM 口径）：`shutdown_kind` 只用于拆分原因，不从任何分母里剔除样本；`clean` 是否单独处理放到 1.5.9 之后再议。同一个 instance 下的多个项目读到同一个分类；记录在没有任何项目还引用该 instance 时才删除，修剪只在启动恢复之后于后台执行一次（退出路径不扫项目）：超过 50 条时按时间修剪，仍被未恢复项目引用的不删；读不了的项目只保护比它最后修改时间更新的记录；超过 1 小时的孤儿 `.tmp` 一并清理。只发枚举，instance id 不出本机。

### 1.5.7 一键重试

终态事件可带 `retry_of`（被重试 attempt 的 `attempt_id`，`t-` id）。**attempt 归后端所有（#419）**：每个 v4 尝试是项目状态里的一条 AttemptReceipt（`attempt_id, flow_id, sequence, retry_of, kind, state, causes[]`），和业务状态同一次原子写入；失败态「重试」/「继续制作」/「重试这条」都走同一个 `POST /studio/{id}/retry`，后端校验父 attempt（必须是 failed/partial、没被重试过）、同一项目串行（第二个「重试这条」并入正在进行的那次）、幂等键防重复。前端观察器只投影回执：`studio_generation_finished` / `studio_production_finished` 的 `attempt_id`、`retry_of`、主因和 `secondary_*` 都取自回执，`$insert_id` = `studio-v1:{attempt_id}:finished`；顺序看 `sequence`，不看时间戳（终态事件带 `attempt_sequence` = 回执 `sequence`，`success_rate.sql` 按它取流程里最后一次 attempt，R25 #346）；重启或清空浏览器存储不改血缘。主因按 catalog 分层确定（产品优先，`failure_attribution`），页面另取第一个用户可修复的原因给「去设置」。不自动续跑。

**产出归属与结算范围（#419）**：每个成片版本创建时记 `produced_by_attempt` / `produced_by_plan`。一轮的结果和回执计数只用本轮盖章的产出，加上「重试这条」重做的产出（`redone_by_attempt`）。之前轮次没被重做的失败不算本轮，只记 `generation.not_redone_failed_count`（结果页可提示「本次重跑已完成，之前还有 N 条未完成」）。有 attempt 记录时，本轮没有盖章产出就不结算，不借用整个工作区，避免把 0 条自身产出记成 completed。只有 attempt 记录不存在（旧数据或被裁掉）才退回全工作区。范围内全是备选（on_demand）时判 validation。变体重试的计划和 route 取被重试产出的来源计划。
**已知限制**：(1) 1.5.7 不做追加平台。`POST /studio/{id}/platforms` 固定返回 `append_platform_unavailable`（409），不打开 attempt、不改 generation；结果页没有入口。`trigger=append_platform` 留在枚举里但本版不产生，留到 1.5.9。(2) 改动前生成的旧产物没有归属：回执不计它们的数量；对没有 attempt 记录的旧轮次，「重试这条」不带来源计划，结算仍走全工作区兜底。(3) 手动确认写下的草稿记在回执 `draft_ids` 里，成功率还不按草稿计。
