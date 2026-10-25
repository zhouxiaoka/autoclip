/**
 * Clipboard / deep-link key guide (1.5.8).
 * Pure: no React, no logging, no telemetry. Callers must not put the key in a URL,
 * event, or log line. A route is a suggestion until the user confirms.
 */

export const CUSTOM_PROVIDER_ID = '__custom__'
export const KEY_SAVE_ERRORS = new Set(['invalid_key', 'permission_denied', 'insufficient_quota'])

export type GuideTarget = { id: string; hosts: string[] }
export type GuideEndpoint = {
  id: string
  providerId: string
  baseUrl: string
  apiKey?: string | null
  hasKey?: boolean
}

export type KeyRoute = {
  key: string
  baseUrl: string
  providerId: string | null
  conflict: boolean
}

export type Placement =
  | { action: 'unchanged'; connectionId: string }
  | { action: 'blocked'; connectionId: string }
  | { action: 'update'; connectionId: string; apiKey: string; baseUrl?: string }
  | { action: 'create'; providerId: string; apiKey: string; baseUrl: string; custom: boolean; name: string }

export type SaveToastKind = 'saved' | 'invalid' | 'failed' | 'unverified'

const PREFIXES: Array<[RegExp, string]> = [
  [/^AIza[0-9A-Za-z\-_]{20,}/, 'gemini'],
  [/^xai-[A-Za-z0-9\-_]{16,}/, 'grok'],
  [/^sk-proj-[A-Za-z0-9\-_]{16,}/, 'openai'],
  [/^sk-svcacct-[A-Za-z0-9\-_]{16,}/, 'openai'],
  [/^sk-or-v1-[A-Za-z0-9\-_]{16,}/, 'openrouter'],
]

const GENERIC_SK = /^sk-[A-Za-z0-9][A-Za-z0-9_-]{19,}$/
const LABELED = /(?:api[ _-]?key|token|secret|密钥)\s*[:=：]\s*['"]?([A-Za-z0-9_\-.]{16,200})/i
const BEARER = /bearer\s+([A-Za-z0-9_\-.]{16,200})/i

export function keyTail(value: string): string {
  const trimmed = value.trim()
  if (trimmed.length < 8) return ''
  return trimmed.slice(-4)
}

export function prefixProviderId(apiKey: string): string | null {
  const key = apiKey.trim()
  for (const [pattern, id] of PREFIXES) {
    if (pattern.test(key)) return id
  }
  return null
}

export function looksLikeApiKey(value: string): boolean {
  const key = value.trim()
  if (key.length < 20 || key.length > 200) return false
  if (/\s/.test(key)) return false
  if (/^https?:/i.test(key) || /^autoclip:/i.test(key)) return false
  if (prefixProviderId(key)) return true
  if (GENERIC_SK.test(key)) return true
  if (/^[0-9a-f]{32,64}$/i.test(key)) return false
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(key)) return false
  if (key.length >= 32 && /[A-Za-z]/.test(key) && /\d/.test(key) && /^[A-Za-z0-9_\-.]+$/.test(key)) return true
  return false
}

/** Pull one likely key out of clipboard or paste text. URLs and ordinary sentences are not keys. */
export function extractApiKey(raw: string): string | null {
  const text = (raw || '').trim()
  if (!text || text.length > 4000) return null
  if (/^autoclip:/i.test(text)) return null
  if (/^https?:\/\//i.test(text)) return null
  const labeled = text.match(LABELED)
  if (labeled && looksLikeApiKey(labeled[1])) return labeled[1]
  const bearer = text.match(BEARER)
  if (bearer && looksLikeApiKey(bearer[1])) return bearer[1]
  if (looksLikeApiKey(text)) return text
  const tokens = text.match(/[A-Za-z0-9_\-.]{20,200}/g) || []
  const keys = tokens.filter(looksLikeApiKey)
  return keys.length === 1 ? keys[0] : null
}

export function hostOf(url: string): string {
  try {
    return new URL(url.trim()).hostname.toLowerCase().replace(/^\[|\]$/g, '')
  } catch {
    return ''
  }
}

/** Keep an http(s) endpoint. Empty path becomes /v1. Credentials in the URL are rejected. */
export function normalizeGuideBaseUrl(raw: string): string {
  const trimmed = (raw || '').trim()
  if (!/^https?:\/\//i.test(trimmed)) return ''
  try {
    const url = new URL(trimmed)
    if (url.username || url.password) return ''
    url.hash = ''
    url.search = ''
    let path = url.pathname.replace(/\/+$/, '')
    if (path.endsWith('/chat/completions')) path = path.slice(0, -'/chat/completions'.length).replace(/\/+$/, '')
    if (!path) path = '/v1'
    url.pathname = path
    return url.toString().replace(/\/$/, '')
  } catch {
    return ''
  }
}

function targetByHost(baseUrl: string, targets: GuideTarget[]): string | null {
  const host = hostOf(baseUrl)
  if (!host) return null
  const hits = targets.filter(target => target.hosts.some(item => item.toLowerCase() === host))
  return hits.length === 1 ? hits[0].id : null
}

function knownId(id: string | null | undefined, targets: GuideTarget[]): string | null {
  if (!id) return null
  return targets.some(target => target.id === id) ? id : null
}

/**
 * Host match wins when it agrees with a prefix. A disagreement is a conflict:
 * the user picks. No match does not fall back to a sponsor or any other preset.
 */
export function inferProviderId(key: string, baseUrl: string, targets: GuideTarget[]): { providerId: string | null; conflict: boolean } {
  const prefix = knownId(prefixProviderId(key), targets)
  const host = targetByHost(baseUrl, targets)
  if (prefix && host && prefix !== host) return { providerId: null, conflict: true }
  if (host) return { providerId: host, conflict: false }
  if (prefix) return { providerId: prefix, conflict: false }
  return { providerId: null, conflict: false }
}

export function routeKey(key: string, baseUrl: string, targets: GuideTarget[], explicitProviderId?: string | null): KeyRoute {
  const normalized = normalizeGuideBaseUrl(baseUrl)
  const inferred = inferProviderId(key, normalized, targets)
  const explicit = knownId(explicitProviderId, targets)
  if (explicit && inferred.providerId && explicit !== inferred.providerId) {
    return { key, baseUrl: normalized, providerId: null, conflict: true }
  }
  if (inferred.conflict) return { key, baseUrl: normalized, providerId: null, conflict: true }
  return { key, baseUrl: normalized, providerId: explicit || inferred.providerId, conflict: false }
}

const QUERY_KEYS = ['key', 'api_key', 'token']
const QUERY_URLS = ['base_url', 'url', 'server', 'address']

/** New API substitutes `{key}` and `{address}` before opening the URL. */
export function parseAutoclipLink(raw: string): { key: string; baseUrl: string; providerId: string | null } | null {
  const text = (raw || '').trim()
  if (!/^autoclip:/i.test(text)) return null
  let parsed: URL
  try {
    parsed = new URL(text)
  } catch {
    return null
  }
  if (parsed.protocol !== 'autoclip:') return null
  if (parsed.username || parsed.password) return null
  const params = parsed.searchParams
  const key = QUERY_KEYS.map(name => params.get(name) || '').map(value => value.trim()).find(Boolean) || ''
  if (!key || /\s/.test(key) || key.length < 8 || key.length > 200) return null
  if (/^https?:/i.test(key)) return null
  const baseRaw = QUERY_URLS.map(name => params.get(name) || '').find(value => value.trim()) || ''
  const providerId = (params.get('provider') || '').trim() || null
  return { key, baseUrl: normalizeGuideBaseUrl(baseRaw), providerId }
}

export function endpointProviderId(endpoint: GuideEndpoint): string {
  return endpoint.providerId === 'compatible' ? CUSTOM_PROVIDER_ID : endpoint.providerId
}

export function needsOverwrite(endpoint: GuideEndpoint | undefined, apiKey: string): boolean {
  if (!endpoint) return false
  const saved = (endpoint.apiKey || '').trim()
  if (!saved && !endpoint.hasKey) return false
  if (saved && saved === apiKey.trim()) return false
  return true
}

export function planPlacement(input: {
  endpoints: GuideEndpoint[]
  providerId: string
  apiKey: string
  baseUrl?: string
  overwrite: boolean
  officialBaseUrl?: string
}): Placement {
  const apiKey = input.apiKey.trim()
  const custom = input.providerId === CUSTOM_PROVIDER_ID
  const baseUrl = custom ? normalizeGuideBaseUrl(input.baseUrl || '') : (input.officialBaseUrl || '').trim()
  const host = hostOf(baseUrl)
  const existing = input.endpoints.find(endpoint => {
    if (custom) return endpoint.providerId === 'compatible' && host && hostOf(endpoint.baseUrl) === host
    return endpoint.providerId === input.providerId
  })
  if (existing) {
    const saved = (existing.apiKey || '').trim()
    if (saved && saved === apiKey && (!custom || !baseUrl || hostOf(existing.baseUrl) === host)) {
      return { action: 'unchanged', connectionId: existing.id }
    }
    if (needsOverwrite(existing, apiKey) && !input.overwrite) return { action: 'blocked', connectionId: existing.id }
    return {
      action: 'update',
      connectionId: existing.id,
      apiKey,
      ...(custom && baseUrl ? { baseUrl } : {}),
    }
  }
  return {
    action: 'create',
    providerId: custom ? 'compatible' : input.providerId,
    apiKey,
    baseUrl,
    custom,
    name: host || 'custom',
  }
}

export function pasteShouldMove(text: string, currentProviderId: string, targets: GuideTarget[]): boolean {
  const key = extractApiKey(text)
  if (!key) return false
  const route = inferProviderId(key, '', targets)
  if (!route.providerId || route.conflict) return false
  return route.providerId !== currentProviderId
}

export function saveToast(rows: Array<{ status?: string; errorType?: string }>): { kind: SaveToastKind; errorType: string } {
  const failed = rows.filter(row => row.status === 'failed')
  const keyError = failed.find(row => row.errorType && KEY_SAVE_ERRORS.has(row.errorType))
  if (keyError) return { kind: 'invalid', errorType: keyError.errorType || 'invalid_key' }
  if (failed.length) return { kind: 'failed', errorType: failed[0].errorType || 'unknown' }
  if (rows.some(row => row.status === 'transient')) return { kind: 'unverified', errorType: rows.find(row => row.status === 'transient')?.errorType || 'timeout' }
  return { kind: 'saved', errorType: '' }
}
