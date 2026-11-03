import catalog from '@event-catalog'

/**
 * 1.5.7: closed error_code set for provider_connection_test_finished.
 * Only this code and an integer upstream HTTP status leave the app — never URL, key, path,
 * upstream body or message. Classification stays within the tested provider.
 * The list is event_catalog.json enums.connection_test_error_code.
 */
export const CONNECTION_TEST_ERROR_CODES: readonly string[] = catalog.enums.connection_test_error_code
export type ConnectionTestErrorCode = (typeof CONNECTION_TEST_ERROR_CODES)[number]

const BY_TYPE: Record<string, ConnectionTestErrorCode> = {
  invalid_key: 'invalid_key', insufficient_quota: 'insufficient_quota', permission_denied: 'permission_denied',
  model_not_found: 'model_not_found', bad_endpoint: 'bad_base_url', rate_limited: 'rate_limited',
  upstream_unavailable: 'http_5xx', timeout: 'timeout', connection: 'network',
  output_truncated: 'output_truncated', vision_unsupported: 'vision_unsupported',
}

export function isConnectionTestErrorCode(value: unknown): value is ConnectionTestErrorCode {
  return typeof value === 'string' && (CONNECTION_TEST_ERROR_CODES as readonly string[]).includes(value)
}

export function safeHttpStatus(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isInteger(value) && value >= 100 && value <= 599 ? value : undefined
}

/** Code for a failed validation result returned by the backend (HTTP 200). */
export function codeFromResult(result: { error_code?: unknown; error_type?: unknown; http_status?: unknown } | null | undefined): ConnectionTestErrorCode {
  if (isConnectionTestErrorCode(result?.error_code)) return result!.error_code as ConnectionTestErrorCode
  const type = typeof result?.error_type === 'string' ? result.error_type : ''
  if (Object.prototype.hasOwnProperty.call(BY_TYPE, type)) return BY_TYPE[type]
  const status = safeHttpStatus(result?.http_status)
  if (status && status >= 500) return 'http_5xx'
  if (status === 429) return 'rate_limited'
  return 'unknown'
}

/**
 * Code for a request that never produced a validation result (axios error).
 * HTTP 422 is the backend's local request validation (FastAPI/pydantic or a ValueError raised
 * before any upstream call); the fixed backend sentence is read locally only to pick the code.
 */
export function codeFromRequestError(error: unknown, context: { emptyKey?: boolean; desktop?: boolean } = {}): ConnectionTestErrorCode {
  const e = error as { code?: string; response?: { status?: number; data?: { detail?: unknown } } } | null
  const status = e?.response?.status
  if (typeof status === 'number') {
    if (status === 422) {
      const detail = typeof e?.response?.data?.detail === 'string' ? e.response.data.detail : ''
      if (context.emptyKey || /API Key|密钥/.test(detail)) return 'empty_key'
      if (/图像识别|图片输入/.test(detail)) return 'vision_unsupported'
      if (/地址|URL|url|控制台/.test(detail)) return 'bad_base_url'
      if (/模型/.test(detail)) return 'model_not_found'
      return 'invalid_request'
    }
    if (status === 401) return 'invalid_key'
    if (status === 403) return 'permission_denied'
    if (status === 404) return 'model_not_found'
    if (status === 429) return 'rate_limited'
    if (status >= 500 && status <= 599) return 'http_5xx'
    return 'unknown'
  }
  if (e?.code === 'ECONNABORTED' || e?.code === 'ETIMEDOUT') return 'timeout'
  // No response at all: in a browser page this is the CORS/blocked-origin signature; the
  // desktop shell talks to its own local backend, so there it is a plain network failure.
  if (e?.code === 'ERR_NETWORK') return context.desktop === false ? 'cors' : 'network'
  return 'unknown'
}
