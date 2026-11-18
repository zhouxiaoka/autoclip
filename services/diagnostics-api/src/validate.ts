import allowlist from '../../../backend/services/diagnostics/allowlist.json' with { type: 'json' }

const SECRET = /sk-|bearer\s|api[_-]?key\s*[:=]|authorization\s*[:=]|password\s*[:=]|\/Users\/|\\Users\\|https?:\/\/\S+\?/i
const SECRET_PARTS = new Set([
  'token', 'secret', 'signature', 'sign', 'password', 'passwd', 'pwd',
  'credential', 'cookie', 'apikey', 'key', 'sig', 'sid', 'auth',
])

export function manifestProblems(manifest: unknown, maxBytes: number): string[] {
  const problems: string[] = []
  if (!manifest || typeof manifest !== 'object' || Array.isArray(manifest)) return ['not_object']
  const record = manifest as Record<string, unknown>
  const allowed = new Set(allowlist.manifest_keys)
  for (const key of Object.keys(record)) {
    if (!allowed.has(key)) problems.push('extra_keys')
  }
  if (record.schema !== allowlist.schema || record.purpose !== allowlist.purpose) problems.push('schema')
  if (record.not_for_training !== true) problems.push('purpose')
  const encoded = new TextEncoder().encode(JSON.stringify(record))
  if (encoded.byteLength > maxBytes) problems.push('too_large')
  walk(record, problems)
  if ('source_link' in record && !sourceLinkOk(record.source_link)) problems.push('source_link')
  const scanned = { ...record }
  delete scanned.source_link
  if (SECRET.test(JSON.stringify(scanned))) problems.push('secret_or_path')
  return problems
}

function decodeBounded(value: string): string {
  let current = value
  for (let i = 0; i < 3; i++) {
    try {
      const next = decodeURIComponent(current.replace(/\+/g, '%20'))
      if (next === current || next.length > 2000) break
      current = next
    } catch {
      break
    }
  }
  return current
}

function secretName(name: string): boolean {
  const folded = decodeBounded(name).toLowerCase().replace(/-/g, '_')
  const parts = folded.split(/[^a-z0-9_]+/).flatMap((piece) => piece.split('_')).filter(Boolean)
  return parts.some((part) => SECRET_PARTS.has(part))
}

function unsafeText(value: string): boolean {
  for (const sample of [value, decodeBounded(value)]) {
    const folded = sample.toLowerCase().replace(/\\/g, '/')
    if (folded.includes('sk-') || folded.includes('/users/')) return true
  }
  return false
}

function sourceLinkOk(value: unknown): boolean {
  if (typeof value !== 'string' || value.length === 0 || value.length > 300 || /\s/.test(value)) return false
  if (/^(file|data|javascript|blob):/i.test(value)) return false
  let url: URL
  try {
    url = new URL(value)
  } catch {
    return false
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return false
  if (url.username || url.password || url.hash) return false
  if (url.port && (Number(url.port) < 1 || Number(url.port) > 65535)) return false
  if (unsafeText(url.pathname)) return false
  const search = url.search.startsWith('?') ? url.search.slice(1) : url.search
  for (const pair of search.split('&').filter(Boolean)) {
    const eq = pair.indexOf('=')
    const key = eq === -1 ? pair : pair.slice(0, eq)
    const item = eq === -1 ? '' : pair.slice(eq + 1)
    if (secretName(key) || unsafeText(item)) return false
  }
  return !unsafeText(value)
}

function walk(value: unknown, problems: string[]): void {
  if (!value || typeof value !== 'object') {
    if (typeof value === 'string' && (value.includes('\n') || value.length > 400)) problems.push('prose')
    return
  }
  if (Array.isArray(value)) {
    for (const item of value) walk(item, problems)
    return
  }
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (allowlist.forbidden_keys.includes(key.toLowerCase())) problems.push('forbidden_key')
    walk(item, problems)
  }
}

const MD5_64 = /^[A-Za-z0-9+/]{22}==$/

export function fileProblems(files: unknown, limits: { subtitleMax: number; excerptMax: number; originalMax: number; partBytes: number }): string[] {
  if (!Array.isArray(files)) return ['files']
  const problems: string[] = []
  const roles = new Set<string>()
  for (const file of files) {
    if (!file || typeof file !== 'object') return ['files']
    const row = file as Record<string, unknown>
    const role = row.role
    if (role !== 'excerpt' && role !== 'original' && role !== 'subtitle') return ['role']
    if (roles.has(role)) return ['duplicate_role']
    roles.add(role)
    const bytes = row.bytes
    const cap = role === 'subtitle' ? limits.subtitleMax : role === 'excerpt' ? limits.excerptMax : limits.originalMax
    if (typeof bytes !== 'number' || !Number.isSafeInteger(bytes) || bytes < 0 || bytes > cap) problems.push('size')
    if (typeof row.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(row.sha256)) problems.push('checksum')
    if (typeof bytes === 'number' && Number.isSafeInteger(bytes) && bytes > limits.partBytes) {
      const parts = Math.ceil(bytes / limits.partBytes)
      const digests = row.part_md5s
      if (!Array.isArray(digests) || digests.length !== parts || digests.some((item) => typeof item !== 'string' || !MD5_64.test(item))) problems.push('part_md5')
    }
  }
  return problems
}
