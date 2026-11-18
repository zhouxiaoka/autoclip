/** Byte reservation. The same predicate is what the D1 UPDATE WHERE clause enforces. */

export interface QuotaState {
  landed: number
  reserved: number
}

export interface Limits {
  landedCap: number
  inflightCap: number
  retentionSeconds: number
  incompleteSeconds: number
  manifestMax: number
  subtitleMax: number
  excerptMax: number
  originalMax: number
  ratePerHour: number
  partTtl: number
}

export const PROPOSED_LIMITS: Limits = {
  landedCap: 4 * 1024 * 1024 * 1024,
  inflightCap: 2 * 1024 * 1024 * 1024,
  retentionSeconds: 14 * 24 * 60 * 60,
  incompleteSeconds: 24 * 60 * 60,
  manifestMax: 256 * 1024,
  subtitleMax: 2 * 1024 * 1024,
  excerptMax: 200 * 1024 * 1024,
  originalMax: 2 * 1024 * 1024 * 1024,
  ratePerHour: 20,
  partTtl: 900,
}

export function limitsFrom(env: Record<string, string | undefined>): Limits {
  const num = (key: string, fallback: number) => {
    const raw = env[key]
    if (raw == null || raw === '') return fallback
    const value = Number(raw)
    if (!Number.isSafeInteger(value) || value < 0) return fallback
    return value
  }
  return {
    landedCap: num('LANDED_BYTES_CAP', PROPOSED_LIMITS.landedCap),
    inflightCap: num('INFLIGHT_BYTES_CAP', PROPOSED_LIMITS.inflightCap),
    retentionSeconds: num('RETENTION_SECONDS', PROPOSED_LIMITS.retentionSeconds),
    incompleteSeconds: num('INCOMPLETE_SECONDS', PROPOSED_LIMITS.incompleteSeconds),
    manifestMax: num('MANIFEST_MAX', PROPOSED_LIMITS.manifestMax),
    subtitleMax: num('SUBTITLE_MAX', PROPOSED_LIMITS.subtitleMax),
    excerptMax: num('EXCERPT_MAX', PROPOSED_LIMITS.excerptMax),
    originalMax: num('ORIGINAL_MAX', PROPOSED_LIMITS.originalMax),
    ratePerHour: num('RATE_PER_HOUR', PROPOSED_LIMITS.ratePerHour),
    partTtl: num('PART_TTL_SECONDS', PROPOSED_LIMITS.partTtl),
  }
}

export function tryReserve(state: QuotaState, bytes: number, limits: Pick<Limits, 'landedCap' | 'inflightCap'>):
  { ok: true } | { ok: false; reason: 'bad_bytes' | 'landed_cap' | 'inflight_cap' } {
  if (!Number.isSafeInteger(bytes) || bytes < 0) return { ok: false, reason: 'bad_bytes' }
  if (state.landed + state.reserved + bytes > limits.landedCap) return { ok: false, reason: 'landed_cap' }
  if (state.reserved + bytes > limits.inflightCap) return { ok: false, reason: 'inflight_cap' }
  return { ok: true }
}

export function roleCap(role: string, limits: Limits): number | null {
  if (role === 'subtitle') return limits.subtitleMax
  if (role === 'excerpt') return limits.excerptMax
  if (role === 'original') return limits.originalMax
  if (role === 'manifest') return limits.manifestMax
  return null
}

/** Keys listed in the bucket that this service did not record should be deleted. Never touch other prefixes. */
export function orphanKeys(listed: string[], live: ReadonlySet<string>): string[] {
  return listed.filter((key) => key.startsWith('cases/') && !live.has(key))
}
