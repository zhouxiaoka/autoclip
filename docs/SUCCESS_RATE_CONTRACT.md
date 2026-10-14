# 1.5.8 成功率共享契约

本文件是成功率版第 0 步的引用说明。实现只提供分类与字段白名单，**不改现有调用链、不发新事件、不重试**。并行线请直接 import，不要再各自发明一套码。

| 线 | 引用 |
|---|---|
| #3 付费前预检 / 上游错误分类 / 退避 | `backend.core.upstream_errors.classify_upstream_error`；`retryable` 决定是否重试（401/402/403/404 与余额、权限、地址错为 false） |
| #S 设置页接入校验 | 同一分类函数；提示用 `hint_key`（八语 catalog key） |
| #9 埋点 | `backend.core.llm_telemetry` 的字段集合与 `sanitize_*`；前端 `frontend/src/analytics/successRateContract.ts` |
| #10 发版回归门槛 | 故障注入的期望类型用 `UpstreamErrorType`；应拦下的组合要求 `billable_calls_before_failure = 0` |

源码：

- 分类：[`backend/core/upstream_errors.py`](../backend/core/upstream_errors.py)
- 埋点字段与脱敏：[`backend/core/llm_telemetry.py`](../backend/core/llm_telemetry.py)
- 前端常量与脱敏：[`frontend/src/analytics/successRateContract.ts`](../frontend/src/analytics/successRateContract.ts)

## 上游错误类型

| `upstream_error_type` | 典型来源 | 可重试 |
|---|---|---|
| `invalid_key` | OpenAI / DeepSeek 401 `invalid_api_key`；new-api 401「无效的令牌」；Gemini `API_KEY_INVALID` | 否 |
| `insufficient_quota` | DeepSeek 402；OpenAI `insufficient_quota`；new-api 403 `insufficient_user_quota` 或 401+额度关键词 | 否 |
| `permission_denied` | new-api 403 分组/模型权限；Gemini `PERMISSION_DENIED` | 否 |
| `model_not_found` | new-api 503 `model_not_found`；OpenAI 404 `model_not_found` | 否 |
| `bad_endpoint` | 404（无 model 语义）或响应体是 HTML（漏 `/v1`、填成控制台） | 否 |
| `rate_limited` | 429 / `rate_limit_exceeded` | 是 |
| `upstream_unavailable` | 500 / 502 / 503（非 model_not_found）/ 504 | 是 |
| `timeout` | 无状态码的超时异常 | 是 |
| `connection` | 无状态码的连接异常 | 是 |
| `output_truncated` | `finish_reason=length` | 否 |
| `unknown` | 其余（含未识别 400） | 否 |

new-api 令牌额度用尽与 key 写错都可能是 401「无效的令牌」。只有正文带额度/余额关键词时才标 `insufficient_quota`，否则 `invalid_key`。这是上游歧义，分类无法再拆。

`classify_upstream_error(status_code, body, *, finish_reason, error_name)` 只返回 `{error_type, retryable, hint_key}`。`hint_key` 是中文 catalog key，已写入八语 locale。

## 埋点字段

`success_rate_schema_version = 1`。新事件：

- `llm_request_finished`：provider、model、base_url_host、kind（text/vision）、stage、http_status（100–599）、upstream_error_type、prompt/completion/reasoning_tokens、retry_count、duration_ms、outcome（success/error）、finish_reason
- `asr_readiness_checked`：provider（whisper_local / sensevoice_local / cloud）、code、has_subtitle、blocked
- `provider_validation_finished`：provider、base_url_host、result（success/failed/skipped）、upstream_error_type

run 级（后续挂到现有 `studio_generation_finished` / `studio_production_finished` 与 Sentry tag，**不改事件名**）：

provider、model、base_url_host、http_status（400–599）、upstream_error_type、failure_stage、llm_calls、tokens、retry_count、billable_calls_before_failure

脱敏：`hostname_of_base_url` 只留域名，本机/局域网为 `local`；`sanitize_model` 拒绝空格与超长名。sanitize 结果不得含 key、完整 URL、用户正文。

provider 枚举与现有 experience 契约一致：dashscope / openai / gemini / deepseek / seed / kimi / glm / grok / infistar / api88 / compatible / ollama / lmstudio / other。

线 A（#9）在契约之上发送事件、把 run 级字段写入 generation / production，并把允许字段并进 `safeStudioProperties`。见 [`docs/analytics/LLM_TELEMETRY.md`](analytics/LLM_TELEMETRY.md)。

## 明确不做（第 0 步契约本身）

契约模块不改 `model_call_error_code` / `call_with_retry` / 设置页保存，也不自己打点。分类与脱敏只提供能力。
