/**
 * 1.5.8 成功率契约：与 backend/core/upstream_errors.py、llm_telemetry.py 对齐。
 * 只提供枚举、事件名和脱敏。不改现有 capture / safeStudioProperties 行为。
 */
export const SUCCESS_RATE_SCHEMA_VERSION = 1

export const SuccessRateEvent = {
  LlmRequestFinished: 'llm_request_finished',
  AsrReadinessChecked: 'asr_readiness_checked',
  ProviderValidationFinished: 'provider_validation_finished',
} as const

export const UPSTREAM_ERROR_TYPES = [
  'invalid_key',
  'insufficient_quota',
  'permission_denied',
  'model_not_found',
  'bad_endpoint',
  'rate_limited',
  'upstream_unavailable',
  'timeout',
  'connection',
  'output_truncated',
  'unknown',
] as const
export type UpstreamErrorType = (typeof UPSTREAM_ERROR_TYPES)[number]

export const RETRYABLE_UPSTREAM_ERROR_TYPES = [
  'rate_limited',
  'upstream_unavailable',
  'timeout',
  'connection',
] as const

export const TELEMETRY_PROVIDERS = [
  'dashscope', 'openai', 'gemini', 'deepseek', 'seed', 'kimi', 'glm', 'grok',
  'infistar', 'api88', 'compatible', 'ollama', 'lmstudio', 'other',
] as const
export const ASR_PROVIDERS = ['whisper_local', 'sensevoice_local', 'cloud'] as const
export const REQUEST_KINDS = ['text', 'vision'] as const
export const REQUEST_OUTCOMES = ['success', 'error'] as const
export const VALIDATION_RESULTS = ['success', 'failed', 'skipped'] as const
export const FINISH_REASONS = ['stop', 'length', 'content_filter', 'unknown'] as const
export const FAILURE_STAGES = [
  'screening', 'dispatch', 'production', 'ingest', 'subtitle', 'analyze',
  'vision', 'render', 'outline', 'timeline', 'scoring', 'title', 'clustering',
  'other',
] as const

export const RUN_LEVEL_FIELDS = [
  'provider', 'model', 'base_url_host', 'http_status', 'upstream_error_type',
  'failure_stage', 'llm_calls', 'prompt_tokens', 'completion_tokens',
  'reasoning_tokens', 'retry_count', 'billable_calls_before_failure',
] as const
export const LLM_REQUEST_FIELDS = [
  'success_rate_schema_version', 'provider', 'model', 'base_url_host', 'kind',
  'stage', 'http_status', 'upstream_error_type', 'prompt_tokens',
  'completion_tokens', 'reasoning_tokens', 'retry_count', 'duration_ms',
  'outcome', 'finish_reason',
] as const

export const UPSTREAM_HINT_KEYS: Record<UpstreamErrorType, string> = {
  invalid_key: '密钥无效或已过期，请到「设置 → 模型」检查密钥后重试。',
  insufficient_quota: '账户余额或令牌额度不足，请充值或更换令牌后再试。',
  permission_denied: '当前令牌没有该模型权限或分组不对，请到服务商控制台勾选模型或更换分组。',
  model_not_found: '当前分组或服务下没有这个模型，请换一个模型或分组。',
  bad_endpoint: '接口地址不正确（常见是漏了 /v1 或填成了控制台网址），请到「设置 → 模型」核对地址。',
  rate_limited: '提供商限制了请求频率或额度，请检查配额并稍后重试。',
  upstream_unavailable: '模型服务暂时不可用，请稍后重试。',
  timeout: '模型响应超时，请检查服务和网络后重试；本地模型请确认服务仍在运行。',
  connection: '无法连接模型服务，请检查接口地址与网络；本地模型请先启动服务后重试。',
  output_truncated: '模型输出被截断，请稍后重试或换一个模型。',
  unknown: '模型服务返回了无法识别的错误，请检查配置后重试。',
}

const MODEL_RE = /^[\w.\-:/]{1,64}$/
const HOST_RE = /^[a-z0-9](?:[a-z0-9._-]{0,251}[a-z0-9])?$/
const LOCAL_HOSTS = new Set(['localhost', '0.0.0.0', 'host.docker.internal', '::1'])
const SECRET_MARKERS = ['sk-', 'api_key', 'apikey', 'authorization', 'bearer ', 'token=']

export function isRetryableUpstreamError(type: string): boolean {
  return (RETRYABLE_UPSTREAM_ERROR_TYPES as readonly string[]).includes(type)
}

export function hintKeyForUpstreamError(type: string): string {
  return UPSTREAM_HINT_KEYS[type as UpstreamErrorType] ?? UPSTREAM_HINT_KEYS.unknown
}

export function hostnameOfBaseUrl(url?: string | null): string | undefined {
  if (typeof url !== 'string') return undefined
  const raw = url.trim()
  if (!raw) return undefined
  if (looksLikeSecret(raw) && !raw.includes('://') && !raw.includes('/')) return undefined
  let host = ''
  try {
    host = new URL(raw.includes('://') ? raw : `https://${raw}`).hostname.toLowerCase().replace(/^\[|\]$/g, '')
  } catch {
    return undefined
  }
  if (!host) return undefined
  if (isLocalHost(host)) return 'local'
  if (host.length > 253 || !HOST_RE.test(host)) return undefined
  return host
}

export function sanitizeModel(name?: string | null): string | undefined {
  if (typeof name !== 'string') return undefined
  const cleaned = name.trim()
  if (!cleaned || cleaned.length > 64 || !MODEL_RE.test(cleaned)) return undefined
  return cleaned
}

export function sanitizeProvider(value?: string | null, allowAsr = false): string | undefined {
  if (typeof value !== 'string') return undefined
  const key = value.trim().toLowerCase()
  if ((TELEMETRY_PROVIDERS as readonly string[]).includes(key)) return key
  if (allowAsr && (ASR_PROVIDERS as readonly string[]).includes(key)) return key
  return undefined
}

export function sanitizeUpstreamErrorType(value?: string | null): UpstreamErrorType | undefined {
  if (typeof value === 'string' && (UPSTREAM_ERROR_TYPES as readonly string[]).includes(value)) {
    return value as UpstreamErrorType
  }
  return undefined
}

export type SuccessRateProperties = Record<string, string | number | boolean>

export function sanitizeLlmRequestProperties(value: Record<string, unknown> | null | undefined): SuccessRateProperties {
  return sanitize(value, 'request')
}

export function sanitizeRunProperties(value: Record<string, unknown> | null | undefined): SuccessRateProperties {
  return sanitize(value, 'run')
}

function sanitize(value: Record<string, unknown> | null | undefined, kind: 'request' | 'run'): SuccessRateProperties {
  const raw = value && typeof value === 'object' ? value : {}
  const out: SuccessRateProperties = { success_rate_schema_version: SUCCESS_RATE_SCHEMA_VERSION }
  const provider = sanitizeProvider(asString(raw.provider))
  if (provider) out.provider = provider
  const model = sanitizeModel(asString(raw.model))
  if (model) out.model = model
  let host = hostnameOfBaseUrl(asString(raw.base_url) || asString(raw.base_url_host))
  if (!host && typeof raw.base_url_host === 'string') {
    const candidate = raw.base_url_host.trim().toLowerCase()
    if (candidate === 'local' || HOST_RE.test(candidate)) {
      host = candidate === 'local' || isLocalHost(candidate) ? 'local' : candidate
    }
  }
  if (host) out.base_url_host = host
  const errorType = sanitizeUpstreamErrorType(asString(raw.upstream_error_type) || asString(raw.error_type))
  if (errorType) out.upstream_error_type = errorType
  if (kind === 'request') {
    putEnum(out, raw, 'kind', REQUEST_KINDS)
    putEnum(out, raw, 'stage', FAILURE_STAGES)
    putEnum(out, raw, 'outcome', REQUEST_OUTCOMES)
    putEnum(out, raw, 'finish_reason', FINISH_REASONS)
    putHttpStatus(out, raw.http_status, 100)
    for (const key of ['prompt_tokens', 'completion_tokens', 'reasoning_tokens', 'retry_count', 'duration_ms']) {
      putCount(out, raw, key)
    }
  } else {
    putEnum(out, raw, 'failure_stage', FAILURE_STAGES)
    putHttpStatus(out, raw.http_status, 400)
    for (const key of ['llm_calls', 'prompt_tokens', 'completion_tokens', 'reasoning_tokens', 'retry_count', 'billable_calls_before_failure']) {
      putCount(out, raw, key)
    }
  }
  return out
}

function looksLikeSecret(text: string): boolean {
  const lowered = text.toLowerCase()
  return SECRET_MARKERS.some(marker => lowered.includes(marker))
}

function isLocalHost(host: string): boolean {
  if (LOCAL_HOSTS.has(host) || host.endsWith('.local') || host.endsWith('.localhost')) return true
  const v4 = host.match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/)
  if (v4) {
    const a = Number(v4[1])
    const b = Number(v4[2])
    return a === 127 || a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 169 && b === 254)
  }
  return /^f[cd][0-9a-f]{2}:|^fe80:/.test(host)
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined
}

function putEnum(out: SuccessRateProperties, raw: Record<string, unknown>, key: string, allowed: readonly string[]): void {
  const value = raw[key]
  if (typeof value === 'string' && allowed.includes(value)) out[key] = value
}

function putCount(out: SuccessRateProperties, raw: Record<string, unknown>, key: string): void {
  const value = raw[key]
  if (typeof value === 'number' && Number.isFinite(value) && Number.isInteger(value) && value >= 0) out[key] = value
}

function putHttpStatus(out: SuccessRateProperties, value: unknown, minimum: number): void {
  if (typeof value === 'number' && Number.isInteger(value) && value >= minimum && value <= 599) {
    out.http_status = value
  }
}
