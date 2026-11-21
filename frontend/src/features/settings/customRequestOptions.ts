export type ReasoningEffort = 'none' | 'minimal' | 'low' | 'medium' | 'high' | 'xhigh'
export interface CustomRequestDraft {
  http_headers?: Record<string, string> | null
  has_http_headers?: boolean
  reasoning_effort?: ReasoningEffort | null
  extra_body?: Record<string, unknown>
  /** Unsaved editor text. Never sent to the backend or stored. */
  _http_headers_text?: string
  _extra_body_text?: string
}

const HEADER_NAME = /^[!#$%&'*+.^_`|~0-9A-Za-z-]{1,100}$/
const BLOCKED_HEADERS = new Set(['host', 'content-length', 'transfer-encoding', 'connection', 'proxy-authorization', 'proxy-connection', 'trailer', 'te', 'upgrade'])
const RESERVED_FIELDS = new Set(['model', 'messages', 'stream', 'stream_options', 'max_tokens', 'max_completion_tokens', 'max_output_tokens', 'response_format', 'api_key', 'base_url', 'timeout', 'headers', 'http_headers', 'extra_headers', 'extra_body', 'reasoning_effort'])

function object(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}
function finiteJson(value: unknown, depth = 0): boolean {
  if (depth > 20) return false
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return true
  if (typeof value === 'number') return Number.isFinite(value)
  if (Array.isArray(value)) return value.every(item => finiteJson(item, depth + 1))
  return object(value) && Object.values(value).every(item => finiteJson(item, depth + 1))
}

function parsed(value: CustomRequestDraft) {
  const headers = value._http_headers_text === undefined ? value.http_headers
    : value._http_headers_text.trim() ? JSON.parse(value._http_headers_text) : value.has_http_headers ? undefined : {}
  const body = value._extra_body_text === undefined ? value.extra_body || {}
    : value._extra_body_text.trim() ? JSON.parse(value._extra_body_text) : {}
  return { headers, body }
}

export function requestOptionsIssue(value: CustomRequestDraft): 'headers' | 'body' | null {
  let headers: unknown
  let body: unknown
  try {
    headers = value._http_headers_text === undefined ? value.http_headers
      : value._http_headers_text.trim() ? JSON.parse(value._http_headers_text) : undefined
  } catch { return 'headers' }
  if (headers !== undefined && headers !== null) {
    if (!object(headers) || Object.keys(headers).length > 32) return 'headers'
    const seen = new Set<string>()
    for (const [name, text] of Object.entries(headers)) {
      const lower = name.toLowerCase()
      if (!HEADER_NAME.test(name) || BLOCKED_HEADERS.has(lower) || seen.has(lower)) return 'headers'
      if (typeof text !== 'string' || text.length > 4096 || /[^\x20-\x7e]/.test(text)) return 'headers'
      seen.add(lower)
    }
  }
  try {
    body = value._extra_body_text === undefined ? value.extra_body || {}
      : value._extra_body_text.trim() ? JSON.parse(value._extra_body_text) : {}
    if (!object(body) || Object.keys(body).length > 64 || Object.keys(body).some(key => RESERVED_FIELDS.has(key)) || !finiteJson(body)) return 'body'
    const bytes = encodeURIComponent(JSON.stringify(body)).replace(/%[A-F\d]{2}/gi, 'x').length
    if (bytes > 16384) return 'body'
  } catch { return 'body' }
  return null
}

export function wireRequestOptions<T extends CustomRequestDraft>(value: T): Omit<T, '_http_headers_text' | '_extra_body_text' | 'has_http_headers'> {
  if (requestOptionsIssue(value)) throw new Error('Invalid custom request options')
  const { _http_headers_text, _extra_body_text, has_http_headers: _has, ...rest } = value
  const { headers, body } = parsed(value)
  return {
    ...rest,
    ...(_http_headers_text !== undefined ? { http_headers: headers } : {}),
    ...(_extra_body_text !== undefined ? { extra_body: body } : {}),
  }
}
