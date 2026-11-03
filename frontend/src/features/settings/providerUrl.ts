/**
 * Normalize a provider base URL. Cleanup only — never rejects.
 *
 * 1. Collapse whitespace (including interior spaces).
 * 2. Strip trailing slashes.
 * 3. Scheme: lowercase http/https; a host-like value without a scheme gets
 *    http:// for loopback/private/*.local, otherwise https://.
 * 4. Add or dedupe /v1 per provider convention. Empty input stays empty.
 */

const OPENAI_V1_PROVIDERS = new Set([
  'compatible', 'openai', 'api88', 'infistar', 'deepseek',
  'siliconflow', 'ollama', 'lmstudio', 'grok', 'kimi',
])

const VERSIONED = /^\/(?:v\d+(?:beta)?(?:\/openai)?|compatible-mode\/v\d+|api\/v\d+|api\/paas\/v\d+|openai\/v\d+)\/?$/i
const SCHEME = /^([a-zA-Z][a-zA-Z+\-.]*):\/\//
const IPV4 = /^(\d+)\.(\d+)\.(\d+)\.(\d+)$/
const LOCAL_NAMES = new Set(['localhost', '0.0.0.0', 'host.docker.internal', '::1'])

export function collapseSpaces(url?: string | null): string {
  return (url || '').replace(/\s+/g, '')
}

export function cleanupBaseUrl(url?: string | null): string {
  const raw = collapseSpaces(url).replace(/\/+$/, '')
  if (!raw) return ''
  const match = SCHEME.exec(raw)
  if (match) return match[1].toLowerCase() + raw.slice(match[1].length)
  if (raw.startsWith('//')) {
    const host = hostnameOf('http:' + raw)
    return (isLocalHost(host) ? 'http:' : 'https:') + raw
  }
  if (looksLikeHostUrl(raw)) {
    const host = hostOfSchemeless(raw)
    return `${isLocalHost(host) ? 'http' : 'https'}://${raw}`
  }
  return raw
}

export function normalizeProviderBaseUrl(url?: string | null, provider = 'compatible'): string {
  return normalizeProviderUrl(url, provider).url
}

export function normalizeProviderUrl(url?: string | null, provider = 'compatible'): { url: string; warnings: string[] } {
  const cleaned = cleanupBaseUrl(url)
  const warnings: string[] = []
  if (!cleaned) return { url: '', warnings }
  let parsed: URL
  try {
    parsed = new URL(cleaned)
  } catch {
    return { url: cleaned, warnings }
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return { url: cleaned, warnings }
  const host = parsed.hostname.toLowerCase()
  const key = (provider || '').trim().toLowerCase()
  let path = (parsed.pathname || '').replace(/\/+$/, '')
  if (key !== 'image') {
    for (const suffix of ['/chat/completions', '/completions']) {
      if (path.toLowerCase().endsWith(suffix)) {
        path = path.slice(0, -suffix.length).replace(/\/+$/, '')
        warnings.push('chat_completions')
        break
      }
    }
  }
  path = dedupeRepeatedV1(path)
  const normalizedPath = applyConvention(key, host, path)
  if (!path && normalizedPath === '/v1') warnings.push('missing_v1')
  parsed.pathname = normalizedPath || '/'
  parsed.search = ''
  parsed.hash = ''
  return { url: parsed.toString().replace(/\/+$/, ''), warnings }
}

function applyConvention(provider: string, host: string, path: string): string {
  if (host === 'fal.run' || host.endsWith('.fal.run')) return path
  if (provider !== 'image' && (provider === 'gemini' || host === 'generativelanguage.googleapis.com') && path.toLowerCase() === '/v1beta') return '/v1beta/openai'
  if (VERSIONED.test(path || '/')) return path
  if (path && path !== '/') return path
  if (provider === 'dashscope' || provider === 'image') return path
  if (provider === 'gemini' && host === 'generativelanguage.googleapis.com') return '/v1beta/openai'
  if (OPENAI_V1_PROVIDERS.has(provider) || provider === 'gemini') return '/v1'
  return path
}

function dedupeRepeatedV1(path: string): string {
  const parts = path.split('/').filter(Boolean)
  if (parts.length >= 2 && parts.every(part => /^v\d+$/i.test(part))) {
    if (new Set(parts.map(part => part.toLowerCase())).size === 1) return '/' + parts[0]
  }
  return path
}

function hostnameOf(url: string): string {
  try { return new URL(url).hostname.toLowerCase().replace(/^\[|\]$/g, '') } catch { return '' }
}

function isLocalHost(host?: string): boolean {
  const value = (host || '').toLowerCase()
  if (!value) return false
  if (LOCAL_NAMES.has(value) || value.endsWith('.local') || value.endsWith('.localhost')) return true
  const v4 = value.match(IPV4)
  if (v4) {
    const a = Number(v4[1])
    const b = Number(v4[2])
    return a === 127 || a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 169 && b === 254)
  }
  return /^f[cd][0-9a-f]{2}:|^fe80:/.test(value)
}

function hostOfSchemeless(raw: string): string {
  if (raw.startsWith('[')) {
    const end = raw.indexOf(']')
    return end === -1 ? '' : raw.slice(1, end)
  }
  const first = raw.split('/')[0]
  if ((first.match(/:/g) || []).length === 1 && /^\d+$/.test(first.split(':')[1] || '')) {
    return first.split(':')[0]
  }
  return first
}

function looksLikeHostUrl(raw: string): boolean {
  const host = hostOfSchemeless(raw).toLowerCase()
  if (!host) return false
  if (LOCAL_NAMES.has(host) || host.endsWith('.local') || host.endsWith('.localhost')) return true
  return IPV4.test(host) || host.includes('.') || host.includes(':')
}
