# AutoClip 埋点规范（Tracking Plan）

给 Kris 审的规范文档。1.5.7 起按本文件体系统一埋点：先登记，再发送；字段和枚举只引用本规范与第 0 步契约（`backend.core.upstream_errors`、`backend.core.llm_telemetry`、`frontend/src/analytics/successRateContract.ts`），禁止再复制一套分类或脱敏。

**本 PR 只交文档。** 纯埋点代码另开 PR，等本规范确认后再改、再合。已开的上报 PR 标 `[WIP]`，不继续大改。

配套：

- 分类与脱敏：[`docs/SUCCESS_RATE_CONTRACT.md`](../SUCCESS_RATE_CONTRACT.md)、[`backend/core/upstream_errors.py`](../../backend/core/upstream_errors.py)、[`backend/core/llm_telemetry.py`](../../backend/core/llm_telemetry.py)、[`frontend/src/analytics/successRateContract.ts`](../../frontend/src/analytics/successRateContract.ts)
- 线 A 发送说明：`docs/analytics/LLM_TELEMETRY.md`（随纯埋点 PR，规范确认后）
- 机读目录：`docs/analytics/event_catalog.json`（随纯埋点 PR；未登记事件、缺必填、或载荷含违禁值，校验测试必须失败）
- 看板 SQL 草案：[`success_rate.sql`](success_rate.sql)

先看 §1–§5（规则、漏斗、触发点）、§10–§11（隐私硬性 / 脱敏 / 开关关闭）、§6–§7（口径与看板），再看 §8（旧事件盘点）。§8 的删除/改名只是方案，**不在纯埋点 PR 里执行**，以免现有看板断数。

---

## 1. 原则

1. **先登记后发送。** 新事件必须写入本文件 + `event_catalog.json`，并补齐八语无关（埋点无 UI 文案）的校验测试。未登记的事件名不得出现在生产者里。
2. **只发枚举、计数、布尔、随机 token。** 不上报 key、完整 URL、提示词、字幕/转写、视频标题、文件名、带用户名的本机路径、用户正文、内部项目/作业 ID。`base_url` 只留 host；本机/内网记 `local`。详见 §10–§11。schema 校验必须拦住这些值。
3. **终态与请求分开。** 按钮点击不是成功。后台受理用 `*_accepted`，真正做完用 `*_finished`。浏览器点击下载不是落盘。
4. **失败必有身份。** 失败的 run 级事件必须有 `error_code` + `failure_stage`。模型失败另带 `upstream_error_type`（站点拒绝、素材太短/无音轨等不算上游错误）。
5. **同一匿名 ID。** 前端 PostHog `distinct_id` 经 `PUT /settings/analytics-identity` 写入 `analytics.json`；后端事件与 Sentry `user.id` 只用这个 ID。分析开关关闭时不写、不对齐（§10.1）。
6. **生产与验收隔离。** 业务看板只看 `analytics_environment=production` 且目标 `app_version`。validation 单独列，不进转化率。

---

## 2. 命名规则

### 2.1 事件名

```
<domain>_<object>_<verb>
```

- **domain**：`app` / `setup` / `provider` / `studio` / `asr` / `llm` / `mcp` / `feedback`
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

### 2.3 `outcome` 口径

| 值 | 用于 | 含义 |
| --- | --- | --- |
| `success` / `error` | 新事件（`llm_request_finished`、`provider_validation_finished.result`） | 第 0 步契约 |
| `completed` / `failed` / `partial` | 现有 Studio 终态 | 已上线，不改名；新事件不要再扩 `completed` |
| `recommended` / `auto_started` / `manual` / `fallback` | 仅 `studio_screen_finished` | 初筛如何结束 |
| `skipped` | 校验被跳过 | 线 B 设置校验 |

查询成功率时：**新事件用 `outcome=success`；Studio 出片用 `outcome=completed`。** 公式里写清楚，不要混加。

---

## 3. 公共属性

每条业务事件（非 `$` 系统事件）必须能回答：谁、哪个版本、哪台系统、哪次会话。

| 属性 | 来源 | 规则 | 必填 |
| --- | --- | --- | --- |
| `distinct_id` | PostHog 匿名 ID；后端读 `analytics.json` | 与 Sentry `user.id` 相同；禁止 email / IP | 是（SDK 自动；后端显式传） |
| `app_version` | 前端 `VITE_APP_VERSION` / 生命周期 `version`；后端 `AUTOCLIP_APP_VERSION` | `MAJOR.MINOR.PATCH`，无 `v` 前缀 | 是 |
| `os` | 生命周期 super property | **统一** `macos` / `windows` / `linux` / `unknown`。禁止再写 `darwin` / `win32` | 是（前端 register；后端补） |
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
| `attempt_id` | 一次后台观察（重试换新） |
| `artifact_id` | 同一导出作业的成片 |

禁止把内部 `project_id` / `run_id` / `job_id` 当作新事件属性。旧 legacy 事件若已带，不回填、不扩散。

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

只描述 **模型 HTTP 上游**。实现与提示见第 0 步契约，此处不另造值。

| 值 | 用户原因？ | 计入产品失败分母？ |
| --- | --- | --- |
| `invalid_key` | 是（密钥错/过期） | 否 |
| `insufficient_quota` | 是（余额/额度） | 否 |
| `permission_denied` | 是（分组/模型权限） | 否 |
| `model_not_found` | 是（选了没有的模型） | 否 |
| `bad_endpoint` | 是（地址漏 `/v1`、填成控制台） | 否 |
| `rate_limited` | 否（产品应退避） | 是 |
| `upstream_unavailable` | 否（5xx） | 是 |
| `timeout` | 否（产品/网络，算产品侧直到能拆开） | 是 |
| `connection` | 否（同上） | 是 |
| `output_truncated` | 否 | 是 |
| `unknown` | 否 | 是 |

**不要**把 `source_blocked`（B 站 403）、`source_too_short`、`source_no_audio` 标成 `upstream_error_type`。

### 4.3 `error_code` 与归因

Studio `error_code` 仍用现有闭集（`STUDIO_ERROR_CODES`）。成功率口径把失败分成三类：

| 归因 `failure_attribution` | 包含 | 按次/按人分母 |
| --- | --- | --- |
| `user` | `insufficient_quota`；`invalid_key`；`permission_denied`；`model_not_found`；`bad_endpoint`；`llm_not_configured`；`source_too_short`；`source_no_audio`；`source_unreadable`；`whisper_not_installed`（且无字幕） | **剔除** |
| `environment` | `source_blocked`；`service_restarted` | **剔除** |
| `product` | 其余（`unexpected`、`rate_limited`、`timeout`、`connection`、`provider_error`、`invalid_response`、`transcription_empty`、`render` 失败等） | **计入** |

查询里用 `error_code` + `upstream_error_type` 映射到上表，不要在事件上再发一个自由文本归因。机器校验用 `event_catalog.json` 的 `user_caused_error_codes` / `user_caused_upstream_types` / `environment_error_codes`。

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
| `setup_action` | `placement`, `action` | `later` / `open_settings` |
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
| `llm_request_finished` | `provider`, `kind`, `outcome`, `duration_ms` | **诊断**，每条模型调用。失败带 `upstream_error_type`、`failure_stage`、`http_status` |

阶段细节看 run 上的 `failure_stage`，不要为每个 pipeline step 再发明一个 finished 事件。

### 5.5 出片

自动出片与确认制作是两条产品路径，**都算一次出片尝试**。

| 事件 | 必填 | 说明 |
| --- | --- | --- |
| `studio_confirm_requested` / `_accepted` | `analysis_mode` | 仅确认制作路径 |
| `studio_generation_finished` | `outcome` | 自动出片终态：`completed` / `partial` / `failed` |
| `studio_production_finished` | `outcome` | 确认制作终态 |

失败两者都必须有 `error_code`、`failure_stage`；模型失败加 `provider`、`base_url_host`、`upstream_error_type`、`http_status`、`billable_calls_before_failure`。身份按 **本次 run 实际调用**，不用设置页最后保存值。

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
- 出片后回访：首次 `studio_generation_finished|studio_production_finished` 且 `outcome=completed` 之后 7 日内是否再次 `app_opened`

### 5.8 触发点（文件 + 函数）

发送层必须 catch：埋点失败不得改变产品行为。开关关闭或无 key 时，下列函数仍可被调用，但**不得发网络请求**（见 §10.1）。

| 事件 | 何时 | 文件 | 函数 |
| --- | --- | --- | --- |
| `app_installed` / `app_opened` / `app_updated` | 桌面启动；安装只发一次 | `frontend/src/analytics/lifecycle.ts` | `trackLaunch` |
| `setup_presented` / `setup_action` | 引导实际显示 / 用户点稍后或去设置 | `frontend/src/features/settings/FirstRunSetup.tsx` → `experience.ts` | `trackExperience` |
| `import_blocked` | 未配置服务商就被导入挡住 | `frontend/src/features/studio/CreativeImport.tsx` | `trackExperience('import_blocked', …)` |
| `settings_section_viewed` | 打开设置分区 | `frontend/src/pages/SettingsPage.tsx` | `trackExperience` |
| `provider_configuration_save_*` / `provider_connection_test_*` | 设置页保存 / 连接测试 | `frontend/src/analytics/experience.ts` | `beginExperience` |
| `provider_validation_finished` | 保存前真实小请求终态（线 B 挂钩） | `backend/core/llm_emit.py`（预留） | `emit_provider_validation_finished` |
| `asr_readiness_checked` | 导入页探针变化；以及后端受理导入/初筛 | 前端 `CreativeImport.tsx` → `studio.ts`；后端 `backend/services/studio/jobs.py` | `trackAsrReadiness` / `emit_asr_readiness_checked`（`inspect_project`） |
| `studio_import_requested` / `_accepted` / `_request_failed` | 用户提交导入 | `frontend/src/analytics/studio.ts` | `observeStudioOperation('studio_import', …)` |
| `studio_screen_finished` | 观察器看到初筛终态 | `frontend/src/analytics/workflow.ts` | `WorkflowTracker.observeStudio` |
| `llm_request_finished`（text） | 每一次 `LLMProvider.call` 返回或抛错 | `backend/core/llm_providers.py` → `llm_emit.py` | `LLMProvider.__init_subclass__` 包装 → `observe_provider_call` → `request_finished` |
| `llm_request_finished`（vision） | 每一次 `vision_call` 结束 | `backend/services/studio/intelligence.py` | `vision_call` → `emit_vision_request` |
| run 级字段（挂到现有出片终态，不改事件名） | `studio.json` 写入失败/部分成功身份 | `backend/services/studio/store.py` | `write` → `_ensure_failure_identity` + `_attach_run_telemetry`；上下文 `llm_emit.track_run` |
| `studio_generation_finished` / `studio_production_finished` | 观察器看到出片终态（读 snapshot 上的 run 字段） | `frontend/src/analytics/workflow.ts` + `observer.ts` | `observeStudio` / `startWorkflowObserver` |
| `studio_confirm_*` | 用户确认制作 | `frontend/src/analytics/studio.ts` | `observeStudioOperation('studio_confirm', …)` |
| `studio_export_*` | 提交/完成渲染 | `studio.ts` + `workflow.ts` | `observeStudioOperation` / `observeStudio` |
| `studio_download_requested` / `_saved` / `_failed` | 用户要文件；**仅原生落盘**发 saved | `frontend/src/analytics/studio.ts` | `studioDownloadRequested` / `observeStudioDownload` |
| `studio_qa_checked` | 渲染进程跑完 QA | `backend/services/studio/qa/telemetry.py` | `emit_checked` |
| Sentry `user.id` = PostHog `distinct_id` | 前端拿到匿名 ID 后 | `frontend/src/analytics/posthog.ts` → `PUT /settings/analytics-identity` → `qa/telemetry.py` → `sentry_setup.py` | `publishAnonymousId` / `remember_distinct_id` / `sync_anonymous_user`；前端 `setAnonymousUser` |

`llm_request_finished`、run 级字段、`asr_readiness_checked`、身份对齐、schema 校验是线 A 纯埋点 PR 要挂钩的部分；挂钩位置以本表为准，不得另开入口。`prompt` / `input_data` / 转写正文只留在被调用函数内，不得传入发送层。

---

## 6. 核心指标口径

窗口默认 **发布后 7 日**，过滤：

```
analytics_environment = production
app_version = 当前发布版本
runtime = desktop   -- 主指标；web 可另列
```

`partial` 算出片未成功（分子只认 `completed`）。

### 6.1 按次出片成功率（主指标，目标 ≥95%）

**一次尝试** = 一条 `studio_generation_finished` 或 `studio_production_finished`。

- **分母**：上述事件中，`failure_attribution ≠ user` 且 `≠ environment` 的次数。  
  即：成功 + 产品侧失败。用户原因（余额不足、无音轨、密钥/地址/未配置等）和环境（站点拒绝、服务重启）不进分母。
- **分子**：分母里 `outcome=completed` 的次数。
- **公式**：`countIf(completed) / countIf(qualifying)`

归因优先级：先看 `upstream_error_type` 是否属于用户原因；否则看 `error_code`。`outcome=completed` 一律算成功，忽略错误字段。

按服务商拆分用事件上的 `provider`（本次 run），**禁止**再用「最后保存的 provider」近似。

### 6.2 按人首次出片成功率

**一个人** = 一个 `distinct_id`。

1. 取该版本、生产环境里，这个人的 **第一条** 出片终态（generation 与 production 按时间合并，取最早）。
2. 若这条是用户原因或环境失败：**不计入分母**（配置没配好、素材不能用，不算「首次尝试出片」）。继续看到下一条合格尝试；若一直没有合格尝试，此人不进分母。
3. 第一条合格尝试若 `completed`，分子 +1；否则 +0。

**公式**：`uniqIf(distinct_id, first_qualifying_is_completed) / uniq(distinct_id with ≥1 qualifying attempt)`

不要用「曾经成功过的人数 / 打开过应用的人数」冒充本指标——那是激活，不是首次出片成功率。

### 6.3 漏斗（辅助，不替代 6.1）

同一 `distinct_id`、7 日滚动（或发布窗口），步与步之间允许不等待：

1. `app_opened`
2. `provider_validation_finished` 且 `result=success`（1.5.8 线 B 上线前，暂用 `provider_connection_test_finished` 且 `outcome=completed`）
3. `studio_import_accepted`
4. `studio_screen_finished` 且 `outcome ∈ (recommended, auto_started, manual)`
5. 出片终态 `outcome=completed`
6. `studio_download_saved` 或 `studio_export_finished` 且 `outcome=completed`

每步转化用漏斗图，不把诊断事件插进主漏斗。

---

## 7. PostHog 成功率看板配置

新建看板，名称建议：**AutoClip｜1.5.8 出片成功率**。不要改 2026-09-30 Studio V2 看板的历史口径。项目：`450605`。

公共过滤（每张 insight 都加）：

- 事件属性 `analytics_environment = production`
- 事件属性 `app_version = <本版>`（发版后改，或用「最新正式版」看板变量）
- 日期：发布日起 7 天，或滚动 7 天并在图题写明

| # | 图 | Insight 类型 | 事件 | 过滤 / 拆解 | 公式或读法 |
| --- | --- | --- | --- | --- | --- |
| 1 | 按次出片成功率 | Trends · formula | A `studio_generation_finished` + `studio_production_finished` | 排除 user/environment（见下） | `A_completed / A_qualifying`。A 用两条事件的 **Trends 公式** 或一条 HogQL |
| 2 | 按人首次出片成功率 | HogQL / SQL insight | 同上 | 按 `distinct_id` 取 earliest qualifying | 见下方 HogQL |
| 3 | 按服务商按次成功率 | Trends · 公式，breakdown `provider` | 同上 | 同上 | 看 api88 / deepseek / … 不要用设置页 provider |
| 4 | 按 `failure_stage` × `error_code` | Trends · total count | 失败的出片终态 | `outcome ∈ (failed, partial)` | 堆叠或表格；`unexpected` 要下钻 `llm_request_finished` |
| 5 | 按 `upstream_error_type` | Trends | `llm_request_finished` | `outcome=error`，breakdown `upstream_error_type`、`provider` | 诊断用，不是 6.1 分母 |
| 6 | 配置→能跑 | Funnel | `app_opened` → `provider_validation_finished` (`result=success`) → `studio_import_accepted` | 生产 + 版本 | 线 B 上线后主看 |
| 7 | 导入→出片 | Funnel | `studio_import_accepted` → `studio_screen_finished` → 出片 `completed` | `material_origin=user` | 真实素材，排除 sample |
| 8 | 出片→落盘 | Funnel | 出片 `completed` → `studio_download_saved` | `download_mode=native` | 浏览器下载不进 |
| 9 | D7 回访 | Retention | `app_opened` | 起始事件 `app_installed` 或首次出片成功 | 第一列 D1、第七列 D7 |
| 10 | 收数健康 | Trends | 核心事件列表 | 按 event 分列 | 无收数先查同意/发布，不判产品失败 |

排除用户原因 / 环境（HogQL 条件，图 1–3 共用）：

```sql
-- qualifying = 成功，或失败但不属于用户/环境
(
  properties.outcome = 'completed'
  OR (
    properties.outcome IN ('failed', 'partial')
    AND coalesce(properties.upstream_error_type, '') NOT IN
        ('invalid_key', 'insufficient_quota', 'permission_denied', 'model_not_found', 'bad_endpoint')
    AND coalesce(properties.error_code, '') NOT IN
        ('llm_not_configured', 'source_too_short', 'source_no_audio', 'source_unreadable',
         'whisper_not_installed', 'source_blocked', 'service_restarted',
         'invalid_key', 'insufficient_quota')  -- 若 error_code 复用了上游名
  )
)
```

图 2 HogQL 草案（按人首次合格尝试）：

```sql
SELECT
  uniqIf(distinct_id, first_outcome = 'completed') AS first_success_users,
  uniq(distinct_id) AS qualifying_users,
  first_success_users / qualifying_users AS first_attempt_success_rate
FROM (
  SELECT
    distinct_id,
    argMin(properties.outcome, timestamp) AS first_outcome
  FROM events
  WHERE event IN ('studio_generation_finished', 'studio_production_finished')
    AND properties.analytics_environment = 'production'
    AND properties.app_version = {version}
    AND timestamp >= now() - INTERVAL 7 DAY
    AND (
      properties.outcome = 'completed'
      OR (
        properties.outcome IN ('failed', 'partial')
        AND coalesce(properties.upstream_error_type, '') NOT IN
            ('invalid_key', 'insufficient_quota', 'permission_denied', 'model_not_found', 'bad_endpoint')
        AND coalesce(properties.error_code, '') NOT IN
            ('llm_not_configured', 'source_too_short', 'source_no_audio', 'source_unreadable',
             'whisper_not_installed', 'source_blocked', 'service_restarted')
      )
    )
  GROUP BY distinct_id
)
```

可审查 SQL 副本放在 `docs/analytics/success_rate.sql`（与本规范一起落地）。线上看板建好后把 insight 链接回写本节，仿照 [`dashboards-20260930/README.md`](dashboards-20260930/README.md)。

---

## 8. 现有事件盘点与迁移

盘点范围：前端 `captureBusinessEvent` / `posthog.capture`、后端 `qa.telemetry` / `llm_emit` / `mcp_telemetry`。`$pageview`、`$identify`、PostHog `survey *` 不算业务目录。

### 8.1 保留（漏斗或诊断仍要用）

| 事件 | 角色 | 动作 |
| --- | --- | --- |
| `app_installed` / `app_opened` / `app_updated` | 生命周期 | 保留；`os` 统一为 macos/windows/linux |
| `setup_*` / `import_blocked` / `settings_section_viewed` | 引导 | 保留 |
| `provider_configuration_save_*` / `provider_connection_test_*` / `model_settings_load_*` / `model_discovery_*` | 设置 | 保留；线 B 后主看 `provider_validation_finished` |
| `studio_import_*` / `studio_screen_finished` / `studio_confirm_*` / `studio_generation_finished` / `studio_production_finished` | 主漏斗 | 保留；补 run 级字段（线 A 已做） |
| `studio_export_*` / `studio_download_*` | 交付 | 保留 |
| `asr_readiness_checked` / `llm_request_finished` / `provider_validation_finished` | 1.5.8 成功率 | 保留 |
| `studio_rescreen_*` / `studio_plan_update_*` / `studio_variant_*` / `studio_cover_*` / `studio_auto_frame_*` | 编辑/重试 | 保留，不进主漏斗 |
| `social_publish_*` | 发布 | 保留；`scheduled`/`inbox` 不算 completed |
| `studio_qa_checked` / `studio_template_*` / `studio_output_rated` / `studio_output_shared` | 质量与包装 | 保留，诊断 |
| `mcp_tool_called` / `mcp_job_finished` | MCP | 保留，独立域 |
| `feedback_opened` / `feedback_dismissed` | 反馈 | 保留；不要再用裸 `posthog.capture` 绕过白名单（后续收口） |
| `example_project_open_*` / `example_project_viewed` | 示例 | 保留；`material_origin=sample` 不进真实出片率 |

### 8.2 重复或命名不一（迁移）

| 现状 | 问题 | 方案 |
| --- | --- | --- |
| `provider_test_requested/accepted/request_failed` + `provider_test_finished`（`api.ts` 旧设置） | 与 `provider_connection_test_*` 重复；verb 还多一个 `accepted` | **废弃旧 `provider_test_*`**。1.5.8 只认 `provider_connection_test_*` + `provider_validation_finished` |
| `import_requested/accepted/request_failed` + `import_finished`（旧 `/projects/upload`） | 与 `studio_import_*` 并行 | 旧导入路径若仍存在：继续发但标 `legacy=true`；看板不用。Studio 成为唯一漏斗 |
| `processing_requested/accepted` + `processing_started/finished/task_observed` | 旧内容管线；与 Studio `failure_stage` 重叠 | **冻结**：不再加字段。成功率不读这些事件 |
| `processing_failed` | 裸失败，无 run 身份 | **停止发送**（代码若仍调用则改为 no-op 或改走 Studio 终态） |
| `media_download_*` vs `studio_download_*` | 两套下载 | 新交付只看 `studio_download_*`。`media_download_*` 仅旧剪辑页 |
| `clips_exported` | 名字像导出成功，实际是旧下载触发 | **废弃**，查询忽略 |
| `video_imported` | 与 `studio_import_accepted` 重复 | **废弃** |
| `api_key_configured` | 保存 key 就发，不管能不能用 | **废弃**；用 `provider_configuration_save_finished` + `provider_validation_finished` |
| `example_project_opened` | 过早触发 | 已由 `example_project_open_*` / `example_project_viewed` 替代，**停止发送** |
| `outcome=completed` vs `success` | 两套成功值 | 新事件一律 `success`/`error`；旧 Studio 终态保持 `completed`，查询映射 |
| `os=darwin/win32` vs `macos/windows` | 两套系统名 | 新发送统一 macos/windows/linux；查询用 `if(os IN ('darwin','macos'), 'macos', …)` |
| `version` vs `app_version` | `app_installed` 仍带 `version` | 继续 register `app_version`；生命周期事件可同时带两者一个版本，新查询只用 `app_version` |
| `error_type` vs `upstream_error_type` | 线 A 校验钩子曾用过 `error_type` | **只报 `upstream_error_type`** |

### 8.3 无用或易误导（废弃）

| 事件 | 原因 | 动作 |
| --- | --- | --- |
| `clips_exported` | 语义错误 | 代码删除调用；PostHog 隐藏 |
| `video_imported` | 被 Studio 导入替代 | 同上 |
| `processing_failed` | 无阶段、无归因 | 同上 |
| `api_key_configured` | 不能代表可出片 | 同上 |
| `example_project_opened` | 已被替代 | 同上 |
| `sponsor_link_opened` | 可留作增长，但不进成功率 | 保留但移出核心目录 |

废弃事件 **90 天**后从代码删除；此前生产者改为不发送。看板过滤 `event not in (...)`。纯埋点 PR **不删不改名**，只继续发新事件。

`os` 统一为 `macos` / `windows` / `linux` 也只是方案：现有 `darwin` / `win32` 继续上报，查询用 `if(os IN ('darwin','macos'), 'macos', …)`。不要在尽早上线的上报 PR 里改取值。

### 8.4 缺口（本规范要求补齐，按线落地）

| 缺口 | 谁做 | 状态 |
| --- | --- | --- |
| 模型单次 `llm_request_finished` | 线 A 纯埋点 PR | **等本规范确认**后再改代码 |
| run 级 provider/错误身份 | 线 A 纯埋点 PR | 同上 |
| `asr_readiness_checked` | 线 A 纯埋点 PR | 同上 |
| Sentry / PostHog id 对齐 | 线 A 纯埋点 PR | 同上 |
| `provider_validation_finished` 挂钩 | 线 A 预留，线 B 调用 | 发射函数预留；线 B 再调 |
| 后端事件补 `app_version` / `os` | 线 A 纯埋点 PR | 新增字段；不改已有 `darwin`/`win32` |
| 事件目录校验（未登记 / 缺字段 / 违禁值即失败） | 线 A 纯埋点 PR | `event_catalog.json` + §9 夹具 |
| 旧事件停止发送 / 删除 | 后续，90 天 | **本规范只写方案** |
| `os` 取值统一 | 后续 | **本规范只写方案** |
| `backend_exit`（#1 续跑） | 1.5.9 | 本版不发 |
| 线上看板 7 张 insight | 埋点上线后由负责人建 | 本文件 §7 是配置方案 |

---

## 9. 校验合同

`event_catalog.json` 是唯一机读目录。校验测试必须失败，当：

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

测试位置：`backend/tests/test_event_catalog.py`、`frontend/tests/event-catalog.test.cjs`。新增事件的 PR 必须同时改本文件、JSON 目录和测试。

`$` 前缀、PostHog survey 事件、以及测试里故意使用的假名（`disabled`、`test`）不在目录里，扫描时排除。

---

## 10. 隐私硬性要求（PM / Kris）

上报内容一律不得含：**key**、**带用户名的本地路径**（`/Users/xxx`、`C:\Users\xxx`）、**视频标题 / 文件名**、**转写文本**、**提示词**。`base_url` **只保留 host**（本机/内网记 `local`）。这五类值出现在任意属性名或任意字符串值里，schema 校验必须失败。

产品默认开埋点。用户关掉后，或构建未配置 PostHog key 时，**一条事件也不许出网**。

### 10.1 开关关闭时的行为

| 开关 | 存在哪 | 关闭后 |
| --- | --- | --- |
| 设置页「使用分析」 | 前端 `setAnalyticsEnabled(false)` → `localStorage` 键 `autoclip.analytics.optOut=true` | `isAnalyticsEnabled()` 为 false；`captureBusinessEvent` 直接 return；`posthog.opt_out_capturing()`；停 flag 网络；`syncSentryUser(null)`；**不再** `PUT /settings/analytics-identity`；观察器 `workflow.clear()` |
| 未配置 `VITE_PUBLIC_POSTHOG_KEY` | 构建 | `initAnalytics` 不初始化 SDK，零网络 |
| `privacy.json` 的 `analytics: false` | 桌面数据目录（与崩溃报告同文件） | 后端 `qa.telemetry._analytics_allowed()` / MCP 发送 / `llm_emit._post_event` 全部 no-op |
| 崩溃报告另开 | `privacy.json` `crash_reports`；前端 `autoclip.crashReports.optOut` | 与分析开关独立；分析关时 Sentry 仍不得带 PostHog id 去「补发」业务事件 |

关闭时允许：生产者函数被调用、本地算脱敏字典、写测试夹具。禁止：对 `us.i.posthog.com`（或自建 host）发 capture/identify/flag；把未发送的事件缓冲到以后再补发。打开开关后只收**之后**的事件。

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
| `duration_ms` / `*_tokens` / `llm_calls` / `retry_count` / `billable_calls_before_failure` / `session_number` | 非负整数 | 转 int | 附带的说明文字丢掉 |
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
sanitize_model("sk-abc123deadbeef")                                           →  None
sanitize_llm_request_properties({prompt: "…", title: "我的旅行vlog"})         →  不含这两键
```

Schema 测试必须用 §9 的 12 条夹具证明：sanitize 之后仍含这五类值，或未 sanitize 就发送，都失败。
