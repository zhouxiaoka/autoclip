import allowlist from '../../../backend/services/diagnostics/allowlist.json' with { type: 'json' }

const SECRET = /sk-|bearer\s|api[_-]?key\s*[:=]|authorization\s*[:=]|password\s*[:=]|\/Users\/|\\Users\\|https?:\/\/\S+\?/i

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
  if (SECRET.test(JSON.stringify(record))) problems.push('secret_or_path')
  return problems
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

export function fileProblems(files: unknown, limits: { subtitleMax: number; excerptMax: number; originalMax: number }): string[] {
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
  }
  return problems
}
